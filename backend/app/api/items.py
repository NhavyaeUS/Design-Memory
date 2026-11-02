"""Items API — full CRUD + favorite/archive actions."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.item import ResourceType
from app.schemas.item import DuplicateCheckResponse, ItemCreate, ItemOut, ItemUpdate
from app.services import items as svc
from app.services.items import DuplicateResourceError

router = APIRouter(prefix="/items", tags=["items"])


def _out(item) -> ItemOut:
    return ItemOut.from_orm(item)


@router.get("", response_model=list[ItemOut])
def list_items(
    archived: bool = Query(False, description="Include archived items"),
    type: Optional[ResourceType] = Query(None, description="Filter by resource type"),
    collection_id: Optional[int] = Query(None),
    favorites: bool = Query(False),
    q: Optional[str] = Query(None, description="Plain-text search"),
    sort: str = Query("new", pattern=r"^(new|old|az)$"),
    db: Session = Depends(get_db),
):
    return [_out(i) for i in svc.list_items(
        db,
        include_archived=archived,
        resource_type=type,
        collection_id=collection_id,
        favorites_only=favorites,
        q=q,
        sort=sort,
    )]


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = svc.get_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _out(item)


@router.post("", response_model=ItemOut, status_code=201)
def create_item(data: ItemCreate, db: Session = Depends(get_db)):
    try:
        return _out(svc.create_item(db, data))
    except DuplicateResourceError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": exc.message,
                "is_exact_match": exc.is_exact,
                "existing_item_id": exc.existing_item.id,
                "existing_title": exc.existing_item.title,
                "domain": exc.existing_item.domain,
            },
        )


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(item_id: int, data: ItemUpdate, db: Session = Depends(get_db)):
    item = svc.update_item(db, item_id, data)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _out(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    ok = svc.delete_item(db, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")


@router.post("/{item_id}/favorite", response_model=ItemOut)
def toggle_favorite(item_id: int, db: Session = Depends(get_db)):
    item = svc.toggle_favorite(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _out(item)


@router.post("/{item_id}/archive", response_model=ItemOut)
def archive_item(item_id: int, db: Session = Depends(get_db)):
    item = svc.archive_item(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return _out(item)


@router.post("/{item_id}/analyze", response_model=ItemOut)
def analyze_item(item_id: int, db: Session = Depends(get_db)):
    """Manually request a fresh background analysis for an existing item."""
    item = svc.trigger_analysis(db, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found or has no URL")
    return _out(item)


@router.get("/check/duplicate-domain", response_model=Optional[ItemOut])
def check_duplicate_domain(domain: str = Query(...), db: Session = Depends(get_db)):
    """
    Returns the existing item for this domain, or null if none.
    Preserved for backward compatibility with existing prototype clients.
    """
    item = svc.check_domain_duplicate(db, domain)
    return _out(item) if item else None


@router.get("/check/duplicate", response_model=DuplicateCheckResponse)
def check_duplicate_target(target: str = Query(..., description="URL or domain to check"), db: Session = Depends(get_db)):
    """
    Comprehensive duplicate check for a URL or domain.
    Returns whether a duplicate exists, whether it is an exact URL match, and the existing item.
    """
    is_dup, is_exact, existing, msg = svc.check_duplicate(db, target)
    return DuplicateCheckResponse(
        is_duplicate=is_dup,
        is_exact_match=is_exact,
        existing_item=_out(existing) if existing else None,
        message=msg,
    )
