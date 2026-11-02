"""Service layer for Item CRUD and related operations."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.urls import extract_domain, normalize_url
from app.models.collection import Collection
from app.models.item import Item, Color, ResourceType, AnalysisStatus
from app.models.tag import Tag
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.search import sync_item_fts, remove_item_fts, search_fts5


class DuplicateResourceError(Exception):
    """Raised when an item creation would create an unforced duplicate."""
    def __init__(self, existing_item: Item, is_exact: bool, message: str):
        super().__init__(message)
        self.existing_item = existing_item
        self.is_exact = is_exact
        self.message = message


def _load_item(db: Session, item_id: int) -> Optional[Item]:
    """Load an item with all relationships eagerly to avoid lazy-load issues."""
    stmt = (
        select(Item)
        .options(
            selectinload(Item.tags),
            selectinload(Item.collections),
            selectinload(Item.colors),
        )
        .where(Item.id == item_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def _get_or_create_tags(db: Session, tag_names: list[str]) -> list[Tag]:
    """Return existing Tag rows for the given names, creating missing ones."""
    result = []
    for name in tag_names:
        name = name.strip().lower()
        if not name:
            continue
        tag = db.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()  # get the ID without committing
        result.append(tag)
    return result


def _sync_colors(db: Session, item: Item, color_datas: list) -> None:
    """Replace item.colors with the supplied list (preserving ORM cascade)."""
    # Clear existing colours and flush so SQLite deletes them before new ones are inserted.
    item.colors.clear()
    db.flush()
    for i, c in enumerate(color_datas):
        item.colors.append(
            Color(
                position=i,
                name=c.name,
                hex_value=c.hex_value,
                source=c.source,
            )
        )


def list_items(
    db: Session,
    *,
    include_archived: bool = False,
    resource_type: Optional[ResourceType] = None,
    collection_id: Optional[int] = None,
    favorites_only: bool = False,
    q: Optional[str] = None,
    sort: str = "new",
) -> list[Item]:
    stmt = select(Item).options(
        selectinload(Item.tags),
        selectinload(Item.collections),
        selectinload(Item.colors),
    )

    if not include_archived:
        stmt = stmt.where(Item.is_archived.is_(False))
    if resource_type:
        stmt = stmt.where(Item.resource_type == resource_type)
    if favorites_only:
        stmt = stmt.where(Item.is_favorite.is_(True))
    if collection_id is not None:
        stmt = stmt.where(
            Item.collections.any(Collection.id == collection_id)
        )

    # Sorting
    if sort == "old":
        stmt = stmt.order_by(Item.created_at.asc())
    elif sort == "az":
        stmt = stmt.order_by(Item.title.asc())
    else:  # "new" (default)
        stmt = stmt.order_by(Item.created_at.desc())

    items = list(db.execute(stmt).scalars().all())

    # Search: leverage SQLite FTS5 index with fallback for color hex/names
    if q:
        fts_ids = search_fts5(db, q)
        q_lower = q.strip().lower()
        filtered = []
        for it in items:
            searchable = " ".join([
                it.title,
                it.domain or "",
                it.notes or "",
                it.reason_for_saving or "",
                getattr(it, "meta_description", "") or "",
                " ".join(t.name for t in it.tags),
                " ".join(f"{c.name} {c.hex_value}" for c in it.colors),
            ]).lower()
            if (fts_ids is not None and it.id in fts_ids) or q_lower in searchable:
                filtered.append(it)
        items = filtered

    return items


def get_item(db: Session, item_id: int) -> Optional[Item]:
    return _load_item(db, item_id)


def create_item(db: Session, data: ItemCreate) -> Item:
    norm_url = None
    domain = data.domain
    if data.url:
        norm_url = normalize_url(data.url)
        extracted = extract_domain(data.url)
        if extracted:
            domain = extracted

    # Duplicate detection unless explicitly forced
    if not data.force:
        if norm_url:
            exact = db.execute(
                select(Item).where(
                    Item.normalized_url == norm_url,
                    Item.is_archived.is_(False),
                )
            ).scalar_one_or_none()
            if exact:
                raise DuplicateResourceError(
                    existing_item=exact,
                    is_exact=True,
                    message=f"URL is already saved as '{exact.title}'",
                )

        if domain and domain != "Colour palette":
            domain_dup = db.execute(
                select(Item).where(
                    Item.domain == domain,
                    Item.is_archived.is_(False),
                )
            ).scalars().first()
            if domain_dup:
                raise DuplicateResourceError(
                    existing_item=domain_dup,
                    is_exact=False,
                    message=f"{domain} is already saved as '{domain_dup.title}'",
                )

    # Determine title: preserve user title, or default to domain/URL fallback
    has_url = bool(data.url)
    title = (data.title or "").strip()
    if not title:
        title = domain or "Untitled Resource"

    item = Item(
        url=data.url,
        normalized_url=norm_url,
        domain=domain,
        resource_type=data.resource_type,
        title=title,
        color=data.color,
        color2=data.color2,
        aspect_ratio=data.aspect_ratio,
        font_family=data.font_family,
        notes=data.notes,
        reason_for_saving=data.reason_for_saving,
        is_favorite=data.is_favorite,
        is_pending=has_url,
        analysis_status=AnalysisStatus.pending.value if has_url else AnalysisStatus.completed.value,
        analysis_retries=0,
    )
    db.add(item)
    db.flush()  # populate item.id before relationships

    if data.colors:
        _sync_colors(db, item, data.colors)

    db.flush()
    sync_item_fts(db, item.id)

    # Schedule background analysis if item has a URL
    if has_url:
        import asyncio
        from app.services.analysis import analyze_item_async
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(analyze_item_async(item.id))
        except RuntimeError:
            pass

    return _load_item(db, item.id)


def update_item(db: Session, item_id: int, data: ItemUpdate) -> Optional[Item]:
    item = db.execute(
        select(Item)
        .options(
            selectinload(Item.tags),
            selectinload(Item.collections),
            selectinload(Item.colors),
        )
        .where(Item.id == item_id)
    ).scalar_one_or_none()

    if item is None:
        return None

    if data.title is not None:
        item.title = data.title
    if data.resource_type is not None:
        item.resource_type = data.resource_type
    if data.suggested_type is not None:
        item.suggested_type = data.suggested_type
    if data.notes is not None:
        item.notes = data.notes
    if data.reason_for_saving is not None:
        item.reason_for_saving = data.reason_for_saving
    if data.is_favorite is not None:
        item.is_favorite = data.is_favorite
    if data.is_archived is not None:
        item.is_archived = data.is_archived
    if data.color is not None:
        item.color = data.color

    # Replace tag list
    if data.tags is not None:
        item.tags = _get_or_create_tags(db, data.tags)

    # Replace collection membership
    if data.collection_ids is not None:
        collections = list(
            db.execute(
                select(Collection).where(Collection.id.in_(data.collection_ids))
            ).scalars().all()
        )
        item.collections = collections

    # Replace palette colours
    if data.colors is not None:
        _sync_colors(db, item, data.colors)

    item.updated_at = datetime.now(timezone.utc)
    db.flush()
    sync_item_fts(db, item.id)
    return _load_item(db, item.id)


def toggle_favorite(db: Session, item_id: int) -> Optional[Item]:
    item = db.execute(select(Item).where(Item.id == item_id)).scalar_one_or_none()
    if item is None:
        return None
    item.is_favorite = not item.is_favorite
    item.updated_at = datetime.now(timezone.utc)
    db.flush()
    sync_item_fts(db, item.id)
    return _load_item(db, item.id)


def archive_item(db: Session, item_id: int) -> Optional[Item]:
    item = db.execute(select(Item).where(Item.id == item_id)).scalar_one_or_none()
    if item is None:
        return None
    item.is_archived = True
    item.updated_at = datetime.now(timezone.utc)
    db.flush()
    sync_item_fts(db, item.id)
    return _load_item(db, item.id)


def delete_item(db: Session, item_id: int) -> bool:
    item = db.execute(select(Item).where(Item.id == item_id)).scalar_one_or_none()
    if item is None:
        return False
    remove_item_fts(db, item_id)
    db.delete(item)
    db.flush()
    return True


def check_domain_duplicate(db: Session, domain: str) -> Optional[Item]:
    """Return the first non-archived item with a matching domain, or None."""
    clean_dom = domain.strip().lower().removeprefix("www.")
    return db.execute(
        select(Item).where(Item.domain == clean_dom, Item.is_archived.is_(False))
    ).scalars().first()


def check_duplicate(db: Session, target: str) -> tuple[bool, bool, Optional[Item], str]:
    """
    Check if a URL or domain already exists as a non-archived resource.
    Returns: (is_duplicate, is_exact_match, existing_item, message)
    """
    target = target.strip()
    if not target:
        return False, False, None, ""

    if "://" in target:
        try:
            norm_url = normalize_url(target)
            exact = db.execute(
                select(Item).where(
                    Item.normalized_url == norm_url,
                    Item.is_archived.is_(False),
                )
            ).scalars().first()
            if exact:
                return True, True, exact, f"URL is already saved as '{exact.title}'"

            dom = extract_domain(target)
            if dom and dom != "Colour palette":
                domain_dup = db.execute(
                    select(Item).where(
                        Item.domain == dom,
                        Item.is_archived.is_(False),
                    )
                ).scalars().first()
                if domain_dup:
                    return True, False, domain_dup, f"{dom} is already saved as '{domain_dup.title}'"
        except Exception:
            pass

    # Domain-only check
    clean_dom = target.lower().removeprefix("www.")
    if clean_dom:
        domain_dup = db.execute(
            select(Item).where(
                Item.domain == clean_dom,
                Item.is_archived.is_(False),
            )
        ).scalars().first()
        if domain_dup:
            return True, False, domain_dup, f"{clean_dom} is already saved as '{domain_dup.title}'"

    return False, False, None, ""


def trigger_analysis(db: Session, item_id: int) -> Optional[Item]:
    """Manually request a fresh background analysis for an existing item."""
    item = _load_item(db, item_id)
    if not item or not item.url:
        return None

    item.analysis_status = AnalysisStatus.pending.value
    item.analysis_retries = 0
    item.analysis_error = None
    item.is_pending = True
    item.updated_at = datetime.now(timezone.utc)
    db.commit()

    import asyncio
    from app.services.analysis import analyze_item_async
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(analyze_item_async(item.id))
    except RuntimeError:
        pass

    return _load_item(db, item.id)
