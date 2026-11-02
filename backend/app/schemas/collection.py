"""Pydantic schemas for Collection."""
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _norm_hex(value: str) -> str:
    v = value.strip()
    m = _HEX_RE.match(v)
    if not m:
        raise ValueError(f"Invalid HEX colour: '{value}'.")
    digits = m.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.upper()


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    color: str = Field(default="#B4C7EC", max_length=7)

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _norm_hex(v)


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    color: Optional[str] = Field(default=None, max_length=7)

    @field_validator("color", mode="before")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _norm_hex(v)


class CollectionOut(BaseModel):
    id: int
    name: str
    color: str

    model_config = {"from_attributes": True}
