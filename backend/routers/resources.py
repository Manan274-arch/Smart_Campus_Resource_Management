from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dependencies import get_db, get_current_user
import models, schemas
from typing import List

router = APIRouter(prefix="/resources", tags=["Resources"])


@router.get("/", response_model=List[schemas.ResourceOut])
def get_all_resources(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Resource).all()


@router.get("/available", response_model=List[schemas.ResourceOut])
def get_available_resources(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Only return resources that are not under maintenance
    return db.query(models.Resource).filter(models.Resource.status == "available").all()


@router.get("/slots", response_model=List[schemas.TimeSlotOut])
def get_time_slots(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.TimeSlot).all()


@router.get("/{resource_id}", response_model=schemas.ResourceOut)
def get_resource(resource_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    resource = db.query(models.Resource).filter(models.Resource.resource_id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource