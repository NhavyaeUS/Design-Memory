"""
Tests for Milestone 1B.5: SQLite FTS5 Full-Text Search.

Validates:
- FTS5 index initialization and prefix matching.
- Search across title, domain, notes, reason_for_saving, tags, and meta_description.
- Resilient sanitization of special characters, quotes, wildcards, and FTS5 operators.
- Preservation of filters (resource_type, collections, favorites, archive).
- Preservation of sorting options (new, old, az).
- Automatic index synchronization upon insert, update, and delete.
"""
import pytest
from app.models.collection import Collection
from app.models.item import Item, ResourceType
from app.models.tag import Tag
from app.services.items import (
    create_item,
    delete_item,
    list_items,
    update_item,
)
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.search import (
    build_safe_fts5_query,
    init_fts5,
    search_fts5,
    sync_item_fts,
)


def test_build_safe_fts5_query():
    """Punctuation, unbalanced quotes, colons, and operators are safely sanitized."""
    assert build_safe_fts5_query("") is None
    assert build_safe_fts5_query("   ") is None
    assert build_safe_fts5_query(":::***(((}}}") is None

    # Normal multi-word query becomes quoted prefix tokens
    res = build_safe_fts5_query("design system")
    assert res == '"design"* "system"*'

    # Unbalanced quotes or wildcards stripped
    res_unsafe = build_safe_fts5_query('title:"cool UI" * broken(')
    assert 'title' in res_unsafe
    assert 'cool' in res_unsafe
    assert 'UI' in res_unsafe
    assert 'broken' in res_unsafe
    # Ensure quotes are matched
    assert res_unsafe.count('"') % 2 == 0


def test_fts5_search_across_fields(db):
    """Search matches words in title, domain, notes, reason_for_saving, tags, or description."""
    init_fts5(db)

    item1 = Item(
        title="Linear App Redesign",
        domain="linear.app",
        notes="Fast keyboard shortcuts and snappy UI",
        reason_for_saving="Incredible micro-interactions",
        resource_type=ResourceType.website,
        meta_description="Issue tracking built for speed",
    )
    tag_speed = Tag(name="productivity")
    item1.tags.append(tag_speed)
    db.add(item1)
    db.commit()
    sync_item_fts(db, item1.id)

    # 1. Match by title word
    matches = search_fts5(db, "linear")
    assert matches is not None and item1.id in matches

    # 2. Match by domain
    matches_dom = search_fts5(db, "linear.app")
    assert matches_dom is not None and item1.id in matches_dom

    # 3. Match by notes
    matches_notes = search_fts5(db, "shortcuts")
    assert matches_notes is not None and item1.id in matches_notes

    # 4. Match by reason_for_saving
    matches_reason = search_fts5(db, "micro-interactions")
    assert matches_reason is not None and item1.id in matches_reason

    # 5. Match by meta_description
    matches_desc = search_fts5(db, "tracking")
    assert matches_desc is not None and item1.id in matches_desc

    # 6. Match by tag
    matches_tag = search_fts5(db, "productivity")
    assert matches_tag is not None and item1.id in matches_tag


def test_fts5_index_sync_on_update_and_delete(db):
    """Updating an item updates FTS5; deleting an item removes it from FTS5."""
    init_fts5(db)

    item = Item(
        title="Initial Title",
        domain="original.com",
        notes="Draft notes",
        resource_type=ResourceType.website,
    )
    db.add(item)
    db.commit()
    sync_item_fts(db, item.id)

    assert item.id in (search_fts5(db, "Initial") or [])

    # Update item
    update_item(db, item.id, ItemUpdate(title="Revised Masterpiece", notes="Polished notes"))
    # Old keyword no longer matches
    assert item.id not in (search_fts5(db, "Initial") or [])
    # New keyword matches
    assert item.id in (search_fts5(db, "Masterpiece") or [])

    # Delete item
    delete_item(db, item.id)
    assert item.id not in (search_fts5(db, "Masterpiece") or [])


def test_list_items_with_fts_and_filters(db):
    """Search respects resource_type, collections, favorites, archive, and sort."""
    init_fts5(db)

    col = Collection(name="Design Systems", color="#F6D5D2")
    db.add(col)
    db.flush()

    # Resource 1: website, favorite, in collection
    i1 = Item(
        title="Primer Design System",
        domain="primer.style",
        resource_type=ResourceType.ui,
        is_favorite=True,
        is_archived=False,
    )
    i1.collections.append(col)

    # Resource 2: website, not favorite, not in collection
    i2 = Item(
        title="Primer Typography Guide",
        domain="primer.style",
        resource_type=ResourceType.type,
        is_favorite=False,
        is_archived=False,
    )

    # Resource 3: archived
    i3 = Item(
        title="Primer Old Archive",
        domain="primer.style",
        resource_type=ResourceType.ui,
        is_favorite=False,
        is_archived=True,
    )
    db.add_all([i1, i2, i3])
    db.commit()
    sync_item_fts(db, i1.id)
    sync_item_fts(db, i2.id)
    sync_item_fts(db, i3.id)

    # Query 'primer' matches non-archived by default
    res_all = list_items(db, q="primer")
    ids_all = [x.id for x in res_all]
    assert i1.id in ids_all
    assert i2.id in ids_all
    assert i3.id not in ids_all  # archived excluded by default

    # Filter by resource_type == ui
    res_ui = list_items(db, q="primer", resource_type=ResourceType.ui)
    assert [x.id for x in res_ui] == [i1.id]

    # Filter by collection
    res_col = list_items(db, q="primer", collection_id=col.id)
    assert [x.id for x in res_col] == [i1.id]

    # Filter by favorites
    res_fav = list_items(db, q="primer", favorites_only=True)
    assert [x.id for x in res_fav] == [i1.id]

    # Include archived
    res_arch = list_items(db, q="primer", include_archived=True)
    assert i3.id in [x.id for x in res_arch]

    # Sorting az
    res_az = list_items(db, q="primer", sort="az")
    titles = [x.title for x in res_az]
    assert titles == sorted(titles)


def test_malformed_queries_do_not_crash(client, db):
    """Punctuation, unclosed quotes, and FTS5 keywords return 200 without SQL errors."""
    for bad_q in ['"broken quote', "NOT AND OR", ":::***^^^", "(unclosed", "test*"]:
        resp = client.get(f"/api/v1/items?q={bad_q}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
