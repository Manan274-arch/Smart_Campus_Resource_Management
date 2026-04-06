from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from dependencies import get_db, get_current_user
import models, schemas
from typing import List

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/usage", response_model=List[schemas.UsageStatOut])
def get_usage_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.ResourceUsageStat).all()


@router.get("/top-resources")
def get_top_resources(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Return top 5 most booked resources
    stats = db.query(models.ResourceUsageStat).order_by(
        models.ResourceUsageStat.total_bookings.desc()
    ).limit(5).all()

    result = []
    for stat in stats:
        resource = db.query(models.Resource).filter(models.Resource.resource_id == stat.resource_id).first()
        result.append({
            "resource_name": resource.name if resource else "Unknown",
            "total_bookings": stat.total_bookings,
            "usage_count": stat.usage_count,
            "last_used": stat.last_used
        })
    return result


@router.get("/bookings-per-day")
def get_bookings_per_day(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Group bookings by date and count them
    results = db.query(
        models.Booking.date,
        func.count(models.Booking.booking_id).label("count")
    ).group_by(models.Booking.date).order_by(models.Booking.date).all()

    return [{"date": str(r.date), "count": r.count} for r in results]


@router.get("/summary")
def get_summary(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    total_users = db.query(func.count(models.User.user_id)).scalar()
    total_resources = db.query(func.count(models.Resource.resource_id)).scalar()
    total_bookings = db.query(func.count(models.Booking.booking_id)).scalar()
    open_issues = db.query(func.count(models.Maintenance.maintenance_id)).filter(
        models.Maintenance.status == "open"
    ).scalar()

    return {
        "total_users": total_users,
        "total_resources": total_resources,
        "total_bookings": total_bookings,
        "open_maintenance_issues": open_issues
    }