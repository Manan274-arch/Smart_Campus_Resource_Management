"""
models.py — SQLAlchemy ORM Models for Smart Campus Resource Management
======================================================================

Schema design (3NF):
  • Lookup tables for roles, resource_types, booking_status eliminate
    repeated strings; all references go through foreign keys.
  • Every CHECK, UNIQUE, and FK constraint is explicitly named so that
    migration tools (Alembic) can manage them deterministically.

Conflict-supporting booking system:
  • The old UNIQUE(resource_id, slot_id, date) constraint is replaced
    by a regular composite INDEX.  This lets the application layer
    insert multiple rows for the same resource / slot / date
    (e.g. "rejected_conflict" bookings) while still accelerating
    lookups via the index.
"""

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Date, Text,
    UniqueConstraint, CheckConstraint, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. ROLE — Normalised lookup for user roles
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Role(Base):
    """
    Normalized role lookup table.
    Allowed values are enforced at the DB level via CHECK constraint.
    """
    __tablename__ = "roles"

    role_id   = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), nullable=False, unique=True)

    __table_args__ = (
        # INTEGRITY — only these four role names are valid
        CheckConstraint(
            "role_name IN ('admin', 'student', 'faculty', 'staff')",
            name="chk_role_name",
        ),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    users = relationship("User", back_populates="role")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. USER — Campus user accounts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class User(Base):
    """
    Registered user of the campus system.
    Email is UNIQUE; a basic format CHECK ensures it contains '@'.
    """
    __tablename__ = "users"

    user_id       = Column(Integer, primary_key=True, index=True)
    name          = Column(String(100), nullable=False)
    email         = Column(String(150), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role_id       = Column(
        Integer,
        ForeignKey("roles.role_id", ondelete="RESTRICT", name="fk_user_role"),
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # INTEGRITY — email must contain '@'
        CheckConstraint("email LIKE '%@%'", name="chk_email_format"),
        # INDEX — fast FK lookup on role_id
        Index("ix_users_role_id", "role_id"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    role     = relationship("Role", back_populates="users")
    bookings = relationship("Booking", back_populates="user")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. RESOURCE TYPE — Normalised lookup for resource categories
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ResourceType(Base):
    """
    Normalised resource category (e.g. 'lab', 'lecture_hall', 'equipment').
    Prevents duplicate type strings via UNIQUE constraint.
    """
    __tablename__ = "resource_types"

    type_id   = Column(Integer, primary_key=True, index=True)
    type_name = Column(String(100), nullable=False, unique=True)

    # ── Relationships ────────────────────────────────────────────────────────
    resources = relationship("Resource", back_populates="resource_type")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. RESOURCE — Bookable campus resources
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Resource(Base):
    """
    A bookable campus resource (room, lab, projector, etc.).
    Status is constrained to 'available', 'maintenance', or 'inactive'.
    'booked' was intentionally removed — booking state is tracked via the
    bookings table, not on the resource itself, to stay in 3NF.
    """
    __tablename__ = "resources"

    resource_id = Column(Integer, primary_key=True, index=True)
    name        = Column(String(150), nullable=False)
    type_id     = Column(
        Integer,
        ForeignKey("resource_types.type_id", ondelete="RESTRICT", name="fk_resource_type"),
        nullable=False,
    )
    location   = Column(String(200))
    capacity   = Column(Integer)
    status     = Column(String(50), nullable=False, default="available")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # INTEGRITY — resource status must be one of these three values
        CheckConstraint(
            "status IN ('available', 'maintenance', 'inactive')",
            name="chk_resource_status",
        ),
        # INDEX — fast FK lookup on type_id
        Index("ix_resources_type_id", "type_id"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    resource_type = relationship("ResourceType", back_populates="resources")
    bookings      = relationship("Booking", back_populates="resource")
    maintenance   = relationship("Maintenance", back_populates="resource")
    usage_stats   = relationship(
        "ResourceUsageStat", back_populates="resource", uselist=False
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  5. TIME SLOT — Reusable booking time windows
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class TimeSlot(Base):
    """
    Predefined time windows used by bookings.
    UNIQUE(start_time, end_time) prevents duplicate slot definitions.
    CHECK ensures start_time < end_time.
    """
    __tablename__ = "time_slots"

    slot_id    = Column(Integer, primary_key=True, index=True)
    start_time = Column(String(10), nullable=False)   # e.g. "09:00"
    end_time   = Column(String(10), nullable=False)   # e.g. "10:00"

    __table_args__ = (
        # INTEGRITY — start must precede end
        CheckConstraint("start_time < end_time", name="chk_slot_order"),
        # UNIQUE — prevent duplicate slot definitions
        UniqueConstraint("start_time", "end_time", name="uq_slot_times"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    bookings = relationship("Booking", back_populates="time_slot")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  6. BOOKING STATUS — Normalised lookup for booking lifecycle states
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class BookingStatus(Base):
    """
    Normalized booking status lookup.
    Includes 'rejected_conflict' to support the conflict-aware booking model:
    when a new booking request targets a slot that is already confirmed, the
    system can record it as rejected_conflict rather than silently dropping it.
    """
    __tablename__ = "booking_status"

    status_id   = Column(Integer, primary_key=True, index=True)
    status_name = Column(String(50), nullable=False, unique=True)

    __table_args__ = (
        # INTEGRITY — only valid booking lifecycle states
        CheckConstraint(
            "status_name IN ('confirmed', 'cancelled', 'pending', "
            "'completed', 'rejected_conflict')",
            name="chk_booking_status_name",
        ),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    bookings = relationship("Booking", back_populates="status")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  7. BOOKING — Central reservation record
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Booking(Base):
    """
    A reservation request tying a user, resource, time-slot, and date.

    CONFLICT SUPPORT
    ────────────────
    The old UNIQUE(resource_id, slot_id, date) has been **removed**.
    A composite INDEX replaces it so that:
      • Multiple bookings for the same resource/slot/date CAN coexist
        (e.g. one 'confirmed' + one 'rejected_conflict').
      • Lookup performance is preserved via the index.
      • Conflict detection is handled at the application layer
        (see routers/bookings.py → check_availability).
    """
    __tablename__ = "bookings"

    booking_id  = Column(Integer, primary_key=True, index=True)
    user_id     = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE", name="fk_booking_user"),
        nullable=False,
    )
    resource_id = Column(
        Integer,
        ForeignKey("resources.resource_id", ondelete="CASCADE", name="fk_booking_resource"),
        nullable=False,
    )
    slot_id     = Column(
        Integer,
        ForeignKey("time_slots.slot_id", ondelete="RESTRICT", name="fk_booking_slot"),
        nullable=False,
    )
    date        = Column(Date, nullable=False)
    status_id   = Column(
        Integer,
        ForeignKey("booking_status.status_id", ondelete="RESTRICT", name="fk_booking_status"),
        nullable=False,
    )
    created_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # INDEX — replaces the old UNIQUE constraint; fast booking lookups
        # while allowing multiple rows for conflict support
        Index("ix_booking_resource_slot_date", "resource_id", "slot_id", "date"),
        # INDEX — fast FK lookups
        Index("ix_bookings_user_id", "user_id"),
        Index("ix_bookings_status_id", "status_id"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user      = relationship("User",          back_populates="bookings")
    resource  = relationship("Resource",      back_populates="bookings")
    time_slot = relationship("TimeSlot",      back_populates="bookings")
    status    = relationship("BookingStatus", back_populates="bookings")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  8. MAINTENANCE — Issue tracking for resources
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Maintenance(Base):
    """
    Tracks maintenance issues raised against a resource.
    Triggers in database.py automatically flip resource.status to
    'maintenance' on INSERT and back to 'available' when resolved.
    """
    __tablename__ = "maintenance"

    maintenance_id = Column(Integer, primary_key=True, index=True)
    resource_id    = Column(
        Integer,
        ForeignKey("resources.resource_id", ondelete="CASCADE", name="fk_maintenance_resource"),
        nullable=False,
    )
    issue         = Column(Text, nullable=False)
    status        = Column(String(50), nullable=False, default="open")
    reported_date = Column(Date, nullable=False, server_default=func.current_date())
    created_at    = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # INTEGRITY — maintenance lifecycle states
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved')",
            name="chk_maintenance_status",
        ),
        # INDEX — fast FK lookup on resource_id
        Index("ix_maintenance_resource_id", "resource_id"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    resource = relationship("Resource",       back_populates="maintenance")
    logs     = relationship("MaintenanceLog", back_populates="maintenance_record")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  9. MAINTENANCE LOG — Audit trail for maintenance updates
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class MaintenanceLog(Base):
    """
    Append-only audit log for maintenance status changes.
    Rows are typically inserted by the trg_log_maintenance_update trigger.
    """
    __tablename__ = "maintenance_logs"

    log_id         = Column(Integer, primary_key=True, index=True)
    maintenance_id = Column(
        Integer,
        ForeignKey("maintenance.maintenance_id", ondelete="CASCADE", name="fk_log_maintenance"),
        nullable=False,
    )
    update_text = Column(Text, nullable=False)
    updated_at  = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # INDEX — fast FK lookup on maintenance_id
        Index("ix_maintenance_logs_maintenance_id", "maintenance_id"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    maintenance_record = relationship("Maintenance", back_populates="logs")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  10. RESOURCE USAGE STAT — Aggregated usage metrics per resource
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ResourceUsageStat(Base):
    """
    Denormalized / materialised usage counters maintained by triggers.
    One row per resource (UNIQUE on resource_id).
    Both counts are CHECK-constrained to be >= 0.
    """
    __tablename__ = "resource_usage_stats"

    stat_id     = Column(Integer, primary_key=True, index=True)
    resource_id = Column(
        Integer,
        ForeignKey("resources.resource_id", ondelete="CASCADE", name="fk_stat_resource"),
        nullable=False,
        unique=True,
    )
    total_bookings = Column(Integer, nullable=False, default=0)
    usage_count    = Column(Integer, nullable=False, default=0)
    last_used      = Column(Date)
    created_at     = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # INTEGRITY — counts must never go negative
        CheckConstraint("total_bookings >= 0", name="chk_total_bookings_positive"),
        CheckConstraint("usage_count >= 0",    name="chk_usage_count_positive"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    resource = relationship("Resource", back_populates="usage_stats")