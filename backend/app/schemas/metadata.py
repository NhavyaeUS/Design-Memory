"""Schemas for Webpage Metadata Extraction — Milestone 1B.2."""
from typing import Optional
from pydantic import BaseModel, Field


class MetadataExtractRequest(BaseModel):
    """Request payload for extracting metadata from a webpage URL."""
    url: str = Field(..., description="Target webpage URL (must be http or https)")


class MetadataExtractResponse(BaseModel):
    """Response containing extracted webpage metadata or fallback values."""
    url: str
    domain: str
    title: str
    description: Optional[str] = None
    favicon_url: Optional[str] = None
    image_url: Optional[str] = None
    suggested_type: Optional[str] = None
    success: bool
    status: str
    error: Optional[str] = None
