"""Tags API — minimal endpoint to list unique tags."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.tag import Tag

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[str])
def list_tags(db: Session = Depends(get_db)) -> list[str]:
    """Return all unique tag names sorted alphabetically."""
    tags = db.execute(select(Tag.name).order_by(Tag.name.asc())).scalars().all()
    return list(tags)
