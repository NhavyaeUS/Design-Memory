"""Collections API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.collection import CollectionCreate, CollectionOut, CollectionUpdate
from app.services import collections as svc

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=list[CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    return svc.list_collections(db)


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(data: CollectionCreate, db: Session = Depends(get_db)):
    return svc.create_collection(db, data)


@router.patch("/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: int, data: CollectionUpdate, db: Session = Depends(get_db)
):
    col = svc.update_collection(db, collection_id, data)
    if col is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    ok = svc.delete_collection(db, collection_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Collection not found")
