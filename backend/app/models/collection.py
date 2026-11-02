"""
Collection model.

- A collection has a name and a background colour (HEX).
- Resources belong to collections via the item_collection association table.
- Deleting a collection removes only the item_collection rows, not the resources.
- Deleting a resource removes only its item_collection rows, not the collection.
"""
from sqlalchemy import Column, ForeignKey, Integer, String, Table, UniqueConstraint

from app.db.session import Base

# Association table for the resource <-> collection many-to-many relationship.
item_collection = Table(
    "item_collection",
    Base.metadata,
    Column("item_id", Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
    Column("collection_id", Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
    UniqueConstraint("item_id", "collection_id", name="uq_item_collection"),
)


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    # Background colour for the collection card UI (6-char uppercase HEX, e.g. "#B4C7EC")
    color = Column(String(7), nullable=False, default="#B4C7EC")
