from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from auth import get_current_user
import models, schemas
from typing import List

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=schemas.AnalyticsSummary)
def get_summary(db: Session = Depends(get_db), _=Depends(get_current_user)):
    total_users     = db.query(func.count(models.User.user_id)).scalar()
    total_resources = db.query(func.count(models.Resource.resource_id)).scalar()
    total_bookings  = db.query(func.count(models.Booking.booking_id)).scalar()
    active_maint    = db.query(func.count(models.Maintenance.maintenance_id)).filter(
        models.Maintenance.status.in_(["open", "in_progress"])
    ).scalar()

    # Top 5 resources by usage
    top_stats = db.query(models.ResourceUsageStat).order_by(
        models.ResourceUsageStat.usage_count.desc()
    ).limit(5).all()

    top_resources = []
    for s in top_stats:
        out = schemas.UsageStatOut.from_orm(s)
        out.resource_name = s.resource.name if s.resource else None
        top_resources.append(out)

    # Bookings grouped by status
    status_counts = db.query(
        models.BookingStatus.status_name,
        func.count(models.Booking.booking_id)
    ).join(models.Booking, models.Booking.status_id == models.BookingStatus.status_id, isouter=True
    ).group_by(models.BookingStatus.status_name).all()

    bookings_by_status = {s: c for s, c in status_counts}

    return schemas.AnalyticsSummary(
        total_users=total_users,
        total_resources=total_resources,
        total_bookings=total_bookings,
        active_maintenance=active_maint,
        top_resources=top_resources,
        bookings_by_status=bookings_by_status
    )


@router.get("/usage", response_model=List[schemas.UsageStatOut])
def get_usage_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    stats = db.query(models.ResourceUsageStat).order_by(
        models.ResourceUsageStat.usage_count.desc()
    ).all()
    result = []
    for s in stats:
        out = schemas.UsageStatOut.from_orm(s)
        out.resource_name = s.resource.name if s.resource else None
        result.append(out)
    return result


@router.get("/bookings-by-date")
def bookings_by_date(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Returns booking counts grouped by date for charting."""
    rows = db.query(
        models.Booking.date,
        func.count(models.Booking.booking_id).label("count")
    ).group_by(models.Booking.date).order_by(models.Booking.date).all()
    return [{"date": str(r.date), "count": r.count} for r in rows]


@router.get("/resource-status")
def resource_status_distribution(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(
        models.Resource.status,
        func.count(models.Resource.resource_id).label("count")
    ).group_by(models.Resource.status).all()
    return [{"status": r.status, "count": r.count} for r in rows]