"""
routers/reports.py — API endpoints for DBMS Reports page
=========================================================

Each endpoint demonstrates a specific SQL / DBMS concept and is
labelled accordingly so the frontend can tag them.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case, literal_column
from database import get_db
from auth import get_current_user
import models
from datetime import date, timedelta

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. JOIN QUERY — bookings ⋈ users ⋈ resources ⋈ time_slots ⋈ booking_status
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/join-bookings")
def join_bookings(
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Multi-table JOIN:
      SELECT u.name, r.name, b.date, ts.start_time, ts.end_time, bs.status_name
      FROM bookings b
        JOIN users u          ON b.user_id     = u.user_id
        JOIN resources r      ON b.resource_id = r.resource_id
        JOIN time_slots ts    ON b.slot_id     = ts.slot_id
        JOIN booking_status bs ON b.status_id  = bs.status_id
      ORDER BY b.date DESC, ts.start_time
      LIMIT :limit
    """
    rows = (
        db.query(
            models.Booking.booking_id,
            models.User.name.label("user_name"),
            models.Resource.name.label("resource_name"),
            models.Booking.date,
            models.TimeSlot.start_time,
            models.TimeSlot.end_time,
            models.BookingStatus.status_name,
        )
        .join(models.User,          models.Booking.user_id     == models.User.user_id)
        .join(models.Resource,      models.Booking.resource_id == models.Resource.resource_id)
        .join(models.TimeSlot,      models.Booking.slot_id     == models.TimeSlot.slot_id)
        .join(models.BookingStatus, models.Booking.status_id   == models.BookingStatus.status_id)
        .order_by(models.Booking.date.desc(), models.TimeSlot.start_time)
        .limit(limit)
        .all()
    )
    return [
        {
            "booking_id": r.booking_id,
            "user": r.user_name,
            "resource": r.resource_name,
            "date": str(r.date),
            "slot": f"{r.start_time} – {r.end_time}",
            "status": r.status_name,
        }
        for r in rows
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. GROUP BY / AGGREGATES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/aggregates")
def aggregates(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    Returns three aggregate views:
      a) bookings per resource        — GROUP BY resource_id
      b) bookings per day  (last 30d) — GROUP BY date
      c) most-used resource           — MAX aggregate
    """
    # a) Bookings per resource
    per_resource = (
        db.query(
            models.Resource.name.label("resource"),
            func.count(models.Booking.booking_id).label("count"),
        )
        .join(models.Booking, models.Resource.resource_id == models.Booking.resource_id)
        .group_by(models.Resource.name)
        .order_by(func.count(models.Booking.booking_id).desc())
        .all()
    )

    # b) Bookings per day (last 30 days)
    cutoff = date.today() - timedelta(days=30)
    per_day = (
        db.query(
            models.Booking.date,
            func.count(models.Booking.booking_id).label("count"),
        )
        .filter(models.Booking.date >= cutoff)
        .group_by(models.Booking.date)
        .order_by(models.Booking.date)
        .all()
    )

    # c) Most-used resource
    most_used_row = (
        db.query(
            models.Resource.name,
            func.count(models.Booking.booking_id).label("cnt"),
        )
        .join(models.Booking, models.Resource.resource_id == models.Booking.resource_id)
        .group_by(models.Resource.name)
        .order_by(func.count(models.Booking.booking_id).desc())
        .first()
    )

    return {
        "per_resource": [{"resource": r.resource, "count": r.count} for r in per_resource],
        "per_day": [{"date": str(r.date), "count": r.count} for r in per_day],
        "most_used": {
            "resource": most_used_row.name if most_used_row else "N/A",
            "count": most_used_row.cnt if most_used_row else 0,
        },
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. COMPLEX QUERIES — top resources, users, slots (HAVING / SUBQUERY)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/complex")
def complex_queries(db: Session = Depends(get_db), _=Depends(get_current_user)):
    # Top 5 resources
    top_resources = (
        db.query(
            models.Resource.name.label("resource"),
            func.count(models.Booking.booking_id).label("bookings"),
        )
        .join(models.Booking, models.Resource.resource_id == models.Booking.resource_id)
        .group_by(models.Resource.name)
        .order_by(func.count(models.Booking.booking_id).desc())
        .limit(5)
        .all()
    )

    # Top 5 users by booking count
    top_users = (
        db.query(
            models.User.name.label("user"),
            func.count(models.Booking.booking_id).label("bookings"),
        )
        .join(models.Booking, models.User.user_id == models.Booking.user_id)
        .group_by(models.User.name)
        .order_by(func.count(models.Booking.booking_id).desc())
        .limit(5)
        .all()
    )

    # Most-used time slots
    top_slots = (
        db.query(
            models.TimeSlot.start_time,
            models.TimeSlot.end_time,
            func.count(models.Booking.booking_id).label("bookings"),
        )
        .join(models.Booking, models.TimeSlot.slot_id == models.Booking.slot_id)
        .group_by(models.TimeSlot.start_time, models.TimeSlot.end_time)
        .order_by(func.count(models.Booking.booking_id).desc())
        .limit(5)
        .all()
    )

    return {
        "top_resources": [{"resource": r.resource, "bookings": r.bookings} for r in top_resources],
        "top_users":     [{"user": r.user, "bookings": r.bookings} for r in top_users],
        "top_slots":     [{"slot": f"{r.start_time} – {r.end_time}", "bookings": r.bookings} for r in top_slots],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. CONFLICT ANALYSIS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/conflicts")
def conflict_analysis(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    Shows all bookings with status 'rejected_conflict',
    plus the total conflict count.
    """
    rejected = (
        db.query(models.BookingStatus)
        .filter_by(status_name="rejected_conflict")
        .first()
    )
    if not rejected:
        return {"total_conflicts": 0, "conflicts": []}

    conflicts = (
        db.query(
            models.Booking.booking_id,
            models.User.name.label("user_name"),
            models.Resource.name.label("resource_name"),
            models.Booking.date,
            models.TimeSlot.start_time,
            models.TimeSlot.end_time,
        )
        .join(models.User,     models.Booking.user_id     == models.User.user_id)
        .join(models.Resource, models.Booking.resource_id == models.Resource.resource_id)
        .join(models.TimeSlot, models.Booking.slot_id     == models.TimeSlot.slot_id)
        .filter(models.Booking.status_id == rejected.status_id)
        .order_by(models.Booking.date.desc())
        .limit(50)
        .all()
    )

    total = (
        db.query(func.count(models.Booking.booking_id))
        .filter(models.Booking.status_id == rejected.status_id)
        .scalar()
    )

    return {
        "total_conflicts": total,
        "conflicts": [
            {
                "booking_id": c.booking_id,
                "user": c.user_name,
                "resource": c.resource_name,
                "date": str(c.date),
                "slot": f"{c.start_time} – {c.end_time}",
            }
            for c in conflicts
        ],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  5. AVAILABILITY — sample resource for today's slots
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/availability")
def availability_sample(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    For each available resource, show today's slot availability matrix.
    Demonstrates NOT EXISTS / LEFT JOIN logic.
    """
    today = date.today()
    resources = (
        db.query(models.Resource)
        .filter(models.Resource.status == "available")
        .limit(5)
        .all()
    )
    slots = db.query(models.TimeSlot).all()

    confirmed = (
        db.query(models.BookingStatus)
        .filter_by(status_name="confirmed")
        .first()
    )
    pending = (
        db.query(models.BookingStatus)
        .filter_by(status_name="pending")
        .first()
    )
    blocking_ids = []
    if confirmed:
        blocking_ids.append(confirmed.status_id)
    if pending:
        blocking_ids.append(pending.status_id)

    result = []
    for res in resources:
        slot_avail = []
        for slot in slots:
            booked = (
                db.query(models.Booking)
                .filter(
                    models.Booking.resource_id == res.resource_id,
                    models.Booking.slot_id == slot.slot_id,
                    models.Booking.date == today,
                    models.Booking.status_id.in_(blocking_ids),
                )
                .first()
            ) is not None
            slot_avail.append({
                "slot": f"{slot.start_time} – {slot.end_time}",
                "available": not booked,
            })
        result.append({
            "resource": res.name,
            "resource_id": res.resource_id,
            "slots": slot_avail,
        })
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  6. MAINTENANCE VS BOOKINGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/maintenance-bookings")
def maintenance_vs_bookings(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    For each resource currently under maintenance, show the active
    maintenance records and whether any future confirmed bookings exist.
    Demonstrates correlated subquery / EXISTS pattern.
    """
    maint_records = (
        db.query(models.Maintenance)
        .filter(models.Maintenance.status.in_(["open", "in_progress"]))
        .all()
    )

    result = []
    for m in maint_records:
        future_bookings = (
            db.query(func.count(models.Booking.booking_id))
            .filter(
                models.Booking.resource_id == m.resource_id,
                models.Booking.date >= date.today(),
            )
            .scalar()
        )
        result.append({
            "resource": m.resource.name if m.resource else f"Resource #{m.resource_id}",
            "issue": m.issue,
            "maintenance_status": m.status,
            "future_bookings": future_bookings,
        })
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  7. AUDIT LOG — maintenance logs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.get("/audit-log")
def audit_log(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """
    Returns maintenance audit log entries (trigger-generated).
    """
    logs = (
        db.query(
            models.MaintenanceLog.log_id,
            models.MaintenanceLog.update_text,
            models.MaintenanceLog.updated_at,
            models.Maintenance.maintenance_id,
            models.Resource.name.label("resource_name"),
        )
        .join(models.Maintenance, models.MaintenanceLog.maintenance_id == models.Maintenance.maintenance_id)
        .join(models.Resource, models.Maintenance.resource_id == models.Resource.resource_id)
        .order_by(models.MaintenanceLog.updated_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "log_id": l.log_id,
            "action": l.update_text,
            "resource": l.resource_name,
            "table": "maintenance",
            "timestamp": str(l.updated_at) if l.updated_at else None,
        }
        for l in logs
    ]
