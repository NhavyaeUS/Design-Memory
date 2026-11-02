"""
Item and Color ORM models.

Item represents every resource type in the frontend:
  website, image, type, ui, animation, tool, color_palette

Color represents one entry in a palette's ordered list of colours.
It belongs to an Item whose type is 'color_palette'.

Deletion rules:
- Deleting an Item cascades to its Color rows (FK ondelete=CASCADE).
- Deleting an Item removes its item_tag and item_collection rows (ondelete=CASCADE on those FKs).
- Removing a Color row is safe; the Item remains.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.collection import item_collection
from app.models.tag import Tag, item_tag


class ResourceType(str, enum.Enum):
    website = "website"
    image = "image"
    type = "type"
    ui = "ui"
    animation = "animation"
    tool = "tool"
    color_palette = "color_palette"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)

    # ── Core identity ─────────────────────────────────────────────────────────
    # Full URL as the user supplied it (used in "Open original").
    url = Column(String(2048), nullable=True)
    # Normalized URL for duplicate detection
    normalized_url = Column(String(2048), nullable=True, index=True)
    # Normalised hostname used for duplicate-domain warnings (e.g. "ono.studio").
    # For color_palette items this is the display string "Colour palette".
    domain = Column(String(255), nullable=False, default="")

    resource_type = Column(Enum(ResourceType), nullable=False)

    # ── Display fields ────────────────────────────────────────────────────────
    title = Column(String(500), nullable=False)
    # Primary preview colour HEX (e.g. "#B4C7EC")
    color = Column(String(7), nullable=False, default="#B4C7EC")
    # Secondary preview colour HEX (images, tools, animations)
    color2 = Column(String(7), nullable=True)
    # CSS aspect-ratio string for the preview tile (e.g. "4/3")
    aspect_ratio = Column(String(10), nullable=False, default="4/3")
    # Font family name — used for 'type' resources
    font_family = Column(String(200), nullable=True)

    # ── User content ──────────────────────────────────────────────────────────
    notes = Column(Text, nullable=False, default="")
    reason_for_saving = Column(Text, nullable=False, default="")

    # ── Status flags ─────────────────────────────────────────────────────────
    is_favorite = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    # True while metadata extraction is pending (Phase 1B)
    is_pending = Column(Boolean, nullable=False, default=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    tags = relationship(
        "Tag",
        secondary=item_tag,
        order_by=Tag.name,
        # Do not cascade deletes to the Tag row — another resource may share it.
        # The item_tag FK already has ondelete=CASCADE so the join row is cleaned up.
    )

    collections = relationship(
        "Collection",
        secondary=item_collection,
        # Again, no cascade to the Collection row itself.
    )

    # Palette colours — cascade deletion so removing an item removes its colours.
    colors = relationship(
        "Color",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="Color.position",
    )


class Color(Base):
    """
    One colour in a colour_palette Item.

    position: 0-based integer that determines display order.
    hex_value: always stored as uppercase 6-char HEX with leading '#' (e.g. "#263D32").
    source: 'manual' | 'extracted' — informational, matches the frontend's src field.
    """
    __tablename__ = "colors"
    __table_args__ = (
        UniqueConstraint("item_id", "position", name="uq_color_position"),
    )

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False, default="")
    hex_value = Column(String(7), nullable=False)  # "#RRGGBB" uppercase
    source = Column(String(20), nullable=False, default="manual")  # 'manual' | 'extracted'

    item = relationship("Item", back_populates="colors")
