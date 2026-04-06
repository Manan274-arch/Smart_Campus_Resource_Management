from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dependencies import get_db, get_current_user
from datetime import datetime
import models, schemas
from typing import List

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


@router.post("/", response_model=schemas.MaintenanceOut)
def report_issue(data: schemas.MaintenanceCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):

    resource = db.query(models.Resource).filter(models.Resource.resource_id == data.resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Create maintenance record
    new_issue = models.Maintenance(
        resource_id=data.resource_id,
        issue=data.issue
    )
    db.add(new_issue)

    # Mark the resource as under maintenance so it can't be booked
    resource.status = "under_maintenance"
    db.commit()
    db.refresh(new_issue)
    return new_issue


@router.get("/", response_model=List[schemas.MaintenanceOut])
def get_all_issues(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Maintenance).all()


@router.post("/{maintenance_id}/log")
def add_log(maintenance_id: int, data: schemas.MaintenanceLogCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):

    issue = db.query(models.Maintenance).filter(models.Maintenance.maintenance_id == maintenance_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Maintenance record not found")

    log = models.MaintenanceLog(
        maintenance_id=maintenance_id,
        update_text=data.update_text
    )
    db.add(log)
    db.commit()
    return {"message": "Log added"}


@router.patch("/{maintenance_id}/resolve")
def resolve_issue(maintenance_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):

    issue = db.query(models.Maintenance).filter(models.Maintenance.maintenance_id == maintenance_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Maintenance record not found")

    # Mark maintenance as resolved
    issue.status = "resolved"

    # Mark the resource as available again
    resource = db.query(models.Resource).filter(models.Resource.resource_id == issue.resource_id).first()
    if resource:
        resource.status = "available"

    db.commit()
    return {"message": "Issue resolved, resource is now available"}