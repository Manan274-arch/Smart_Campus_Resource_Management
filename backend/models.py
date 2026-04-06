from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Date, Text,
    UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


# ─── 1. ROLES ────────────────────────────────────────────────────────────────
class Role(Base):
    __tablename__ = "roles"

    role_id   = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), nullable=False, unique=True)

    # INTEGRITY: Check constraint — only valid roles allowed
    __table_args__ = (
        CheckConstraint("role_name IN ('admin','student','faculty','staff')",
                        name="chk_role_name"),
    )

    users = relationship("User", back_populates="role")


# ─── 2. USERS ────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    user_id       = Column(Integer, primary_key=True, index=True)
    name          = Column(String(100), nullable=False)
    email         = Column(String(150), nullable=False, unique=True)   # UNIQUE constraint
    password_hash = Column(String(255), nullable=False)
    role_id       = Column(Integer, ForeignKey("roles.role_id", ondelete="RESTRICT"), nullable=False)
    created_at    = Column(DateTime, server_default=func.now())

    # INTEGRITY: Email must contain '@'
    __table_args__ = (
        CheckConstraint("email LIKE '%@%'", name="chk_email_format"),
    )

    role     = relationship("Role", back_populates="users")
    bookings = relationship("Booking", back_populates="user")


# ─── 3. RESOURCE TYPES ───────────────────────────────────────────────────────
class ResourceType(Base):
    __tablename__ = "resource_types"

    type_id   = Column(Integer, primary_key=True, index=True)
    type_name = Column(String(100), nullable=False, unique=True)

    resources = relationship("Resource", back_populates="resource_type")


# ─── 4. RESOURCES ────────────────────────────────────────────────────────────
class Resource(Base):
    __tablename__ = "resources"

    resource_id = Column(Integer, primary_key=True, index=True)
    name        = Column(String(150), nullable=False)
    type_id     = Column(Integer, ForeignKey("resource_types.type_id", ondelete="RESTRICT"), nullable=False)
    location    = Column(String(200))
    status      = Column(String(50), nullable=False, default="available")

    # INTEGRITY: Status must be one of defined values
    __table_args__ = (
        CheckConstraint("status IN ('available','booked','maintenance','inactive')",
                        name="chk_resource_status"),
    )

    resource_type = relationship("ResourceType", back_populates="resources")
    bookings      = relationship("Booking", back_populates="resource")
    maintenance   = relationship("Maintenance", back_populates="resource")
    usage_stats   = relationship("ResourceUsageStat", back_populates="resource", uselist=False)


# ─── 5. TIME SLOTS ───────────────────────────────────────────────────────────
class TimeSlot(Base):
    __tablename__ = "time_slots"

    slot_id    = Column(Integer, primary_key=True, index=True)
    start_time = Column(String(10), nullable=False)   # e.g. "09:00"
    end_time   = Column(String(10), nullable=False)

    # INTEGRITY: start must be before end
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="chk_slot_order"),
        UniqueConstraint("start_time", "end_time", name="uq_slot_times"),
    )

    bookings = relationship("Booking", back_populates="time_slot")


# ─── 6. BOOKING STATUS ───────────────────────────────────────────────────────
class BookingStatus(Base):
    __tablename__ = "booking_status"

    status_id   = Column(Integer, primary_key=True, index=True)
    status_name = Column(String(50), nullable=False, unique=True)

    __table_args__ = (
        CheckConstraint("status_name IN ('confirmed','cancelled','pending','completed')",
                        name="chk_booking_status_name"),
    )

    bookings = relationship("Booking", back_populates="status")


# ─── 7. BOOKINGS ─────────────────────────────────────────────────────────────
class Booking(Base):
    __tablename__ = "bookings"

    booking_id  = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.user_id",    ondelete="CASCADE"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.resource_id", ondelete="CASCADE"), nullable=False)
    slot_id     = Column(Integer, ForeignKey("time_slots.slot_id",    ondelete="RESTRICT"), nullable=False)
    date        = Column(Date, nullable=False)
    status_id   = Column(Integer, ForeignKey("booking_status.status_id", ondelete="RESTRICT"), nullable=False)

    # INTEGRITY: No double-booking same resource + slot + date
    __table_args__ = (
        UniqueConstraint("resource_id", "slot_id", "date", name="uq_booking_slot"),
    )

    user      = relationship("User",          back_populates="bookings")
    resource  = relationship("Resource",      back_populates="bookings")
    time_slot = relationship("TimeSlot",      back_populates="bookings")
    status    = relationship("BookingStatus", back_populates="bookings")


# ─── 8. MAINTENANCE ──────────────────────────────────────────────────────────
class Maintenance(Base):
    __tablename__ = "maintenance"

    maintenance_id = Column(Integer, primary_key=True, index=True)
    resource_id    = Column(Integer, ForeignKey("resources.resource_id", ondelete="CASCADE"), nullable=False)
    issue          = Column(Text, nullable=False)
    status         = Column(String(50), nullable=False, default="open")
    reported_date  = Column(Date, nullable=False, server_default=func.current_date())

    __table_args__ = (
        CheckConstraint("status IN ('open','in_progress','resolved')",
                        name="chk_maintenance_status"),
    )

    resource = relationship("Resource",       back_populates="maintenance")
    logs     = relationship("MaintenanceLog", back_populates="maintenance_record")


# ─── 9. MAINTENANCE LOGS ─────────────────────────────────────────────────────
class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    log_id         = Column(Integer, primary_key=True, index=True)
    maintenance_id = Column(Integer, ForeignKey("maintenance.maintenance_id", ondelete="CASCADE"), nullable=False)
    update_text    = Column(Text, nullable=False)
    updated_at     = Column(DateTime, server_default=func.now())

    maintenance_record = relationship("Maintenance", back_populates="logs")


# ─── 10. RESOURCE USAGE STATS ─────────────────────────────────────────────────
class ResourceUsageStat(Base):
    __tablename__ = "resource_usage_stats"

    stat_id        = Column(Integer, primary_key=True, index=True)
    resource_id    = Column(Integer, ForeignKey("resources.resource_id", ondelete="CASCADE"),
                            nullable=False, unique=True)
    total_bookings = Column(Integer, nullable=False, default=0)
    usage_count    = Column(Integer, nullable=False, default=0)
    last_used      = Column(Date)

    # INTEGRITY: Counts cannot be negative
    __table_args__ = (
        CheckConstraint("total_bookings >= 0", name="chk_total_bookings_positive"),
        CheckConstraint("usage_count >= 0",    name="chk_usage_count_positive"),
    )

    resource = relationship("Resource", back_populates="usage_stats")