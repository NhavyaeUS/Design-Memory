"""Service layer for Collection CRUD."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.collection import Collection
from app.schemas.collection import CollectionCreate, CollectionUpdate


def list_collections(db: Session) -> list[Collection]:
    return list(db.execute(select(Collection).order_by(Collection.id)).scalars().all())


def get_collection(db: Session, collection_id: int) -> Optional[Collection]:
    return db.execute(
        select(Collection).where(Collection.id == collection_id)
    ).scalar_one_or_none()


def create_collection(db: Session, data: CollectionCreate) -> Collection:
    col = Collection(name=data.name, color=data.color)
    db.add(col)
    db.flush()
    return col


def update_collection(
    db: Session, collection_id: int, data: CollectionUpdate
) -> Optional[Collection]:
    col = db.execute(
        select(Collection).where(Collection.id == collection_id)
    ).scalar_one_or_none()
    if col is None:
        return None
    if data.name is not None:
        col.name = data.name
    if data.color is not None:
        col.color = data.color
    db.flush()
    return col


def delete_collection(db: Session, collection_id: int) -> bool:
    col = db.execute(
        select(Collection).where(Collection.id == collection_id)
    ).scalar_one_or_none()
    if col is None:
        return False
    db.delete(col)
    db.flush()
    return True
