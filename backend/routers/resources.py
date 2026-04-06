from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user, require_admin
import models, schemas
from typing import List, Optional

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("/", response_model=List[schemas.ResourceOut])
def list_resources(
    status: Optional[str] = None,
    type_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    query = db.query(models.Resource)
    if status:
        query = query.filter(models.Resource.status == status)
    if type_id:
        query = query.filter(models.Resource.type_id == type_id)
    resources = query.all()
    result = []
    for r in resources:
        out = schemas.ResourceOut.from_orm(r)
        out.type_name = r.resource_type.type_name if r.resource_type else None
        result.append(out)
    return result


@router.get("/types")
def list_resource_types(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.ResourceType).all()


@router.get("/{resource_id}", response_model=schemas.ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    r = db.query(models.Resource).filter(models.Resource.resource_id == resource_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    out = schemas.ResourceOut.from_orm(r)
    out.type_name = r.resource_type.type_name if r.resource_type else None
    return out


@router.post("/", response_model=schemas.ResourceOut)
def create_resource(
    data: schemas.ResourceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    resource = models.Resource(**data.dict())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.put("/{resource_id}", response_model=schemas.ResourceOut)
def update_resource(
    resource_id: int,
    data: schemas.ResourceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    r = db.query(models.Resource).filter(models.Resource.resource_id == resource_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    for k, v in data.dict().items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{resource_id}")
def delete_resource(resource_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    r = db.query(models.Resource).filter(models.Resource.resource_id == resource_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Resource not found")
    db.delete(r)
    db.commit()
    return {"message": "Resource deleted"}