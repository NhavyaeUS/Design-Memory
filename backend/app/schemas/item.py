"""
Pydantic schemas for Item and Color request/response validation.

Why schemas separate from models?
- ORM models are tied to the database; schemas define the API contract.
- Schemas validate user input before it touches the database.
- Response schemas control exactly which fields are sent to the client,
  preventing accidental exposure of internal fields.
"""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.urls import extract_domain, normalize_url, validate_url, URLValidationError
from app.models.item import ResourceType

# Valid resource type strings (mirrors the frontend TYPES object)
VALID_TYPES = {t.value for t in ResourceType}

# HEX colour pattern: optional leading #, then 3 or 6 hex digits
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _norm_hex(value: str) -> str:
    """Normalise a 3- or 6-digit HEX to uppercase 6-char form with leading '#'."""
    v = value.strip()
    m = _HEX_RE.match(v)
    if not m:
        raise ValueError(f"Invalid HEX colour: '{value}'. Use 3 or 6 hex digits.")
    digits = m.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.upper()


# ─── Colour schemas ───────────────────────────────────────────────────────────

class ColorIn(BaseModel):
    """One colour in a palette — used for create/update."""
    name: str = Field(default="", max_length=200)
    hex_value: str = Field(..., max_length=7, description="3- or 6-digit HEX")
    source: str = Field(default="manual", pattern=r"^(manual|extracted)$")

    @field_validator("hex_value", mode="before")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        return _norm_hex(v)


class ColorOut(BaseModel):
    """Colour as returned from the API — always normalised."""
    id: int
    position: int
    name: str
    hex_value: str
    source: str

    model_config = {"from_attributes": True}


# ─── Item schemas ─────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    """Fields required to create a new resource."""
    title: Optional[str] = Field(default=None, max_length=500)
    url: Optional[str] = Field(default=None, max_length=2048)
    domain: str = Field(default="", max_length=255)
    resource_type: ResourceType
    color: str = Field(default="#B4C7EC", max_length=7)
    color2: Optional[str] = Field(default=None, max_length=7)
    aspect_ratio: str = Field(default="4/3", max_length=10)
    font_family: Optional[str] = Field(default=None, max_length=200)
    notes: str = Field(default="")
    reason_for_saving: str = Field(default="")
    is_favorite: bool = False
    # Palette colours — only meaningful when resource_type == color_palette
    colors: list[ColorIn] = Field(default_factory=list)
    # Explicit save-anyway flag to bypass duplicate warnings
    force: bool = Field(default=False)

    @field_validator("url")
    @classmethod
    def validate_item_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_clean = v.strip()
        if not v_clean:
            return None
        try:
            validate_url(v_clean)
        except URLValidationError as err:
            raise ValueError(str(err)) from err
        return v_clean

    @field_validator("color", mode="before")
    @classmethod
    def validate_primary_color(cls, v: str) -> str:
        return _norm_hex(v)

    @field_validator("color2", mode="before")
    @classmethod
    def validate_secondary_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _norm_hex(v)


class ItemUpdate(BaseModel):
    """Partial update — every field is optional. PATCH semantics."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    notes: Optional[str] = None
    reason_for_saving: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    color: Optional[str] = Field(default=None, max_length=7)
    # Tag replacement — if provided, replaces the full tag list for this item.
    tags: Optional[list[str]] = None
    # Collection assignment — if provided, replaces the full collection list.
    collection_ids: Optional[list[int]] = None
    # Palette colour replacement — if provided, replaces all colours in order.
    colors: Optional[list[ColorIn]] = None

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _norm_hex(v)

    @field_validator("tags", mode="before")
    @classmethod
    def normalise_tags(cls, v: Optional[list]) -> Optional[list[str]]:
        if v is None:
            return None
        return [t.strip().lower() for t in v if t.strip()]


class ItemOut(BaseModel):
    """Full item representation returned from the API."""
    id: int
    url: Optional[str]
    normalized_url: Optional[str] = None
    domain: str
    resource_type: ResourceType
    title: str
    color: str
    color2: Optional[str]
    aspect_ratio: str
    font_family: Optional[str]
    notes: str
    reason_for_saving: str
    is_favorite: bool
    is_archived: bool
    is_pending: bool
    created_at: datetime
    updated_at: datetime
    tags: list[str]
    collection_ids: list[int]
    colors: list[ColorOut]

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, item) -> "ItemOut":
        """Build an ItemOut from an ORM Item, flattening relationship fields."""
        return cls(
            id=item.id,
            url=item.url,
            normalized_url=getattr(item, "normalized_url", None),
            domain=item.domain,
            resource_type=item.resource_type,
            title=item.title,
            color=item.color,
            color2=item.color2,
            aspect_ratio=item.aspect_ratio,
            font_family=item.font_family,
            notes=item.notes,
            reason_for_saving=item.reason_for_saving,
            is_favorite=item.is_favorite,
            is_archived=item.is_archived,
            is_pending=item.is_pending,
            created_at=item.created_at,
            updated_at=item.updated_at,
            tags=[t.name for t in item.tags],
            collection_ids=[c.id for c in item.collections],
            colors=[ColorOut.model_validate(c) for c in item.colors],
        )


class DuplicateCheckResponse(BaseModel):
    """Result of checking a URL or domain for existing items."""
    is_duplicate: bool
    is_exact_match: bool = False
    existing_item: Optional[ItemOut] = None
    message: str = ""

