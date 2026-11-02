"""Tests for database configuration — Milestone 1A.3."""
from sqlalchemy import text

from app.models.item import Item, ResourceType
from app.models.collection import Collection
from app.models.tag import Tag


def test_db_connection(db):
    """A basic query must succeed."""
    result = db.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_foreign_key_enforcement(db):
    """Inserting a Color with a non-existent item_id must raise an error."""
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.models.item import Color

    with pytest.raises(IntegrityError):
        db.execute(
            text("INSERT INTO colors (item_id, position, name, hex_value, source) VALUES (99999, 0, 'x', '#FF0000', 'manual')")
        )


def test_insert_and_retrieve_item(db):
    """An inserted item must be retrievable with the same field values."""
    item = Item(
        title="Test resource",
        domain="example.com",
        resource_type=ResourceType.website,
        color="#B4C7EC",
    )
    db.add(item)
    db.flush()

    fetched = db.get(Item, item.id)
    assert fetched is not None
    assert fetched.title == "Test resource"
    assert fetched.domain == "example.com"


def test_invalid_transaction_is_rolled_back(db):
    """After a rollback, the previously inserted item must not exist."""
    item = Item(
        title="Should disappear",
        domain="rollback.test",
        resource_type=ResourceType.tool,
        color="#F3D46A",
    )
    db.add(item)
    db.flush()
    item_id = item.id
    db.rollback()

    fetched = db.get(Item, item_id)
    assert fetched is None
