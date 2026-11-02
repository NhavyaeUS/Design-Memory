"""API router for safe webpage metadata extraction — Milestone 1B.2."""
from fastapi import APIRouter, HTTPException, Query
from app.schemas.metadata import MetadataExtractRequest, MetadataExtractResponse
from app.services import metadata as meta_svc

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.post("/extract", response_model=MetadataExtractResponse)
def extract_metadata_post(payload: MetadataExtractRequest):
    """
    Safely extract title, description, and favicon from a webpage URL.
    Enforces SSRF prevention, timeouts, and byte limits.
    """
    res = meta_svc.extract_metadata(payload.url)
    return MetadataExtractResponse(
        url=res.url,
        domain=res.domain,
        title=res.title,
        description=res.description,
        favicon_url=res.favicon_url,
        image_url=res.image_url,
        success=res.success,
        status=res.status,
        error=res.error,
    )


@router.get("/extract", response_model=MetadataExtractResponse)
def extract_metadata_get(url: str = Query(..., description="Target webpage URL")):
    """
    GET variant of extract metadata for easy querying and frontend integration.
    """
    res = meta_svc.extract_metadata(url)
    return MetadataExtractResponse(
        url=res.url,
        domain=res.domain,
        title=res.title,
        description=res.description,
        favicon_url=res.favicon_url,
        image_url=res.image_url,
        success=res.success,
        status=res.status,
        error=res.error,
    )
