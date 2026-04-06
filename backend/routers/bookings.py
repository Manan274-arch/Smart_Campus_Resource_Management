from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dependencies import get_db, get_current_user
from datetime import datetime
import models, schemas
from typing import List

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("/", response_model=schemas.BookingOut)
def create_booking(data: schemas.BookingCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):

    # 1. Check resource exists
    resource = db.query(models.Resource).filter(models.Resource.resource_id == data.resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # 2. Block booking if resource is under maintenance
    if resource.status == "under_maintenance":
        raise HTTPException(status_code=400, detail="Resource is under maintenance")

    # 3. Check slot exists
    slot = db.query(models.TimeSlot).filter(models.TimeSlot.slot_id == data.slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Time slot not found")

    # 4. Availability check — same resource, same slot, same date, and not cancelled
    confirmed_status = db.query(models.BookingStatus).filter(models.BookingStatus.status_name == "confirmed").first()
    conflict = db.query(models.Booking).filter(
        models.Booking.resource_id == data.resource_id,
        models.Booking.slot_id == data.slot_id,
        models.Booking.date == data.date,
        models.Booking.status_id == confirmed_status.status_id
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="This slot is already booked")

    # 5. Create the booking
    new_booking = models.Booking(
        user_id=current_user.user_id,
        resource_id=data.resource_id,
        slot_id=data.slot_id,
        date=data.date,
        status_id=confirmed_status.status_id
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    # 6. Update usage stats
    stat = db.query(models.ResourceUsageStat).filter(
        models.ResourceUsageStat.resource_id == data.resource_id
    ).first()
    if stat:
        stat.total_bookings += 1
        stat.usage_count += 1
        stat.last_used = datetime.utcnow()
        db.commit()

    return new_booking


@router.get("/my", response_model=List[schemas.BookingOut])
def get_my_bookings(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Booking).filter(models.Booking.user_id == current_user.user_id).all()


@router.patch("/{booking_id}/cancel", response_model=schemas.BookingOut)
def cancel_booking(booking_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):

    booking = db.query(models.Booking).filter(models.Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Only the owner can cancel their booking
    if booking.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your booking")

    cancelled_status = db.query(models.BookingStatus).filter(models.BookingStatus.status_name == "cancelled").first()
    booking.status_id = cancelled_status.status_id
    db.commit()
    db.refresh(booking)
    return booking