from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database import get_db
from auth import get_current_user
import models, schemas
from typing import List
from datetime import date

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def check_availability(db: Session, resource_id: int, slot_id: int, booking_date: date, exclude_booking_id: int = None):
    """CURSOR-style availability check: iterate bookings for this slot/date."""
    query = db.query(models.Booking).filter(
        and_(
            models.Booking.resource_id == resource_id,
            models.Booking.slot_id == slot_id,
            models.Booking.date == booking_date,
        )
    )
    # Exclude current booking if updating
    if exclude_booking_id:
        query = query.filter(models.Booking.booking_id != exclude_booking_id)

    # Check booking status — only block on confirmed/pending
    existing = query.join(models.BookingStatus).filter(
        models.BookingStatus.status_name.in_(["confirmed", "pending"])
    ).first()
    return existing is None  # True = available


@router.get("/slots", response_model=List[schemas.TimeSlotOut])
def get_slots(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(models.TimeSlot).all()


@router.get("/availability")
def check_slot_availability(
    resource_id: int,
    date: date,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    """Return which slots are available for a resource on a date."""
    slots = db.query(models.TimeSlot).all()
    result = []
    for slot in slots:
        available = check_availability(db, resource_id, slot.slot_id, date)
        result.append({
            "slot_id": slot.slot_id,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "available": available
        })
    return result


@router.get("/", response_model=List[schemas.BookingOut])
def list_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Admin sees all, others see own
    if current_user.role_id == 1:
        bookings = db.query(models.Booking).all()
    else:
        bookings = db.query(models.Booking).filter(
            models.Booking.user_id == current_user.user_id
        ).all()

    result = []
    for b in bookings:
        out = schemas.BookingOut.from_orm(b)
        out.status_name  = b.status.status_name if b.status else None
        out.resource_name = b.resource.name if b.resource else None
        out.slot_start   = b.time_slot.start_time if b.time_slot else None
        out.slot_end     = b.time_slot.end_time if b.time_slot else None
        result.append(out)
    return result


@router.post("/", response_model=schemas.BookingOut)
def create_booking(
    data: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check resource exists
    resource = db.query(models.Resource).filter(models.Resource.resource_id == data.resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # Check resource not under maintenance (Python-level check before DB trigger)
    if resource.status == "maintenance":
        raise HTTPException(status_code=400, detail="Resource is currently under maintenance")

    # Check availability
    if not check_availability(db, data.resource_id, data.slot_id, data.date):
        raise HTTPException(status_code=409, detail="This slot is already booked for the selected date")

    # Get 'confirmed' status
    confirmed_status = db.query(models.BookingStatus).filter(
        models.BookingStatus.status_name == "confirmed"
    ).first()
    if not confirmed_status:
        raise HTTPException(status_code=500, detail="Booking status not configured")

    booking = models.Booking(
        user_id=current_user.user_id,
        resource_id=data.resource_id,
        slot_id=data.slot_id,
        date=data.date,
        status_id=confirmed_status.status_id
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    out = schemas.BookingOut.from_orm(booking)
    out.status_name   = booking.status.status_name
    out.resource_name = booking.resource.name
    out.slot_start    = booking.time_slot.start_time
    out.slot_end      = booking.time_slot.end_time
    return out


@router.delete("/{booking_id}")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    booking = db.query(models.Booking).filter(models.Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Only owner or admin can cancel
    if booking.user_id != current_user.user_id and current_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Not authorized")

    cancelled = db.query(models.BookingStatus).filter(
        models.BookingStatus.status_name == "cancelled"
    ).first()
    booking.status_id = cancelled.status_id
    db.commit()
    return {"message": "Booking cancelled"}