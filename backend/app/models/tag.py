"""
Tag model.

Tags are shared across resources:
- A Tag row represents a unique lowercase tag string.
- item_tag is the many-to-many association table.
- Removing a tag from a resource deletes only the item_tag row, not the Tag row
  (other resources may still use it).
- Removing a resource cascades deletion of its item_tag rows only.
"""
from sqlalchemy import Column, ForeignKey, Integer, String, Table, UniqueConstraint

from app.db.session import Base

# Association table: one resource <-> many tags, one tag <-> many resources.
# No ORM class needed; SQLAlchemy handles the joins.
item_tag = Table(
    "item_tag",
    Base.metadata,
    Column("item_id", Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
    UniqueConstraint("item_id", "tag_id", name="uq_item_tag"),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # always lowercase
