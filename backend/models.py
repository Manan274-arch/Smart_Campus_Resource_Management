from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# --- roles table ---
class Role(Base):
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String, unique=True, nullable=False)

    users = relationship("User", back_populates="role")


# --- users table ---
class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role", back_populates="users")
    bookings = relationship("Booking", back_populates="user")


# --- resource_types table ---
class ResourceType(Base):
    __tablename__ = "resource_types"

    type_id = Column(Integer, primary_key=True, index=True)
    type_name = Column(String, unique=True, nullable=False)

    resources = relationship("Resource", back_populates="resource_type")


# --- resources table ---
class Resource(Base):
    __tablename__ = "resources"

    resource_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type_id = Column(Integer, ForeignKey("resource_types.type_id"))
    location = Column(String)
    status = Column(String, default="available")  # available / under_maintenance

    resource_type = relationship("ResourceType", back_populates="resources")
    bookings = relationship("Booking", back_populates="resource")
    maintenance = relationship("Maintenance", back_populates="resource")
    usage_stats = relationship("ResourceUsageStat", back_populates="resource")


# --- time_slots table ---
class TimeSlot(Base):
    __tablename__ = "time_slots"

    slot_id = Column(Integer, primary_key=True, index=True)
    start_time = Column(String, nullable=False)  # e.g. "09:00"
    end_time = Column(String, nullable=False)    # e.g. "10:00"

    bookings = relationship("Booking", back_populates="slot")


# --- booking_status table ---
class BookingStatus(Base):
    __tablename__ = "booking_status"

    status_id = Column(Integer, primary_key=True, index=True)
    status_name = Column(String, unique=True, nullable=False)  # confirmed / cancelled

    bookings = relationship("Booking", back_populates="status")


# --- bookings table ---
class Booking(Base):
    __tablename__ = "bookings"

    booking_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    resource_id = Column(Integer, ForeignKey("resources.resource_id"))
    slot_id = Column(Integer, ForeignKey("time_slots.slot_id"))
    date = Column(Date, nullable=False)
    status_id = Column(Integer, ForeignKey("booking_status.status_id"))

    user = relationship("User", back_populates="bookings")
    resource = relationship("Resource", back_populates="bookings")
    slot = relationship("TimeSlot", back_populates="bookings")
    status = relationship("BookingStatus", back_populates="bookings")


# --- maintenance table ---
class Maintenance(Base):
    __tablename__ = "maintenance"

    maintenance_id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.resource_id"))
    issue = Column(Text, nullable=False)
    status = Column(String, default="open")  # open / resolved
    reported_date = Column(DateTime, default=datetime.utcnow)

    resource = relationship("Resource", back_populates="maintenance")
    logs = relationship("MaintenanceLog", back_populates="maintenance")


# --- maintenance_logs table ---
class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    log_id = Column(Integer, primary_key=True, index=True)
    maintenance_id = Column(Integer, ForeignKey("maintenance.maintenance_id"))
    update_text = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)

    maintenance = relationship("Maintenance", back_populates="logs")


# --- resource_usage_stats table ---
class ResourceUsageStat(Base):
    __tablename__ = "resource_usage_stats"

    stat_id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.resource_id"))
    total_bookings = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)

    resource = relationship("Resource", back_populates="usage_stats")