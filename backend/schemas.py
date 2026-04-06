from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import date, datetime


# ─── AUTH ─────────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role_id: int = 2  # default: student

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    user_id: int
    name: str
    email: str
    role_id: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


# ─── RESOURCES ────────────────────────────────────────────────────────────────
class ResourceOut(BaseModel):
    resource_id: int
    name: str
    type_id: int
    location: Optional[str]
    status: str
    type_name: Optional[str] = None

    class Config:
        from_attributes = True

class ResourceCreate(BaseModel):
    name: str
    type_id: int
    location: Optional[str] = None
    status: str = "available"


# ─── TIME SLOTS ───────────────────────────────────────────────────────────────
class TimeSlotOut(BaseModel):
    slot_id: int
    start_time: str
    end_time: str

    class Config:
        from_attributes = True


# ─── BOOKINGS ─────────────────────────────────────────────────────────────────
class BookingCreate(BaseModel):
    resource_id: int
    slot_id: int
    date: date

class BookingOut(BaseModel):
    booking_id: int
    user_id: int
    resource_id: int
    slot_id: int
    date: date
    status_id: int
    status_name: Optional[str] = None
    resource_name: Optional[str] = None
    slot_start: Optional[str] = None
    slot_end: Optional[str] = None

    class Config:
        from_attributes = True


# ─── MAINTENANCE ──────────────────────────────────────────────────────────────
class MaintenanceCreate(BaseModel):
    resource_id: int
    issue: str

class MaintenanceUpdate(BaseModel):
    status: str

class MaintenanceLogOut(BaseModel):
    log_id: int
    update_text: str
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class MaintenanceOut(BaseModel):
    maintenance_id: int
    resource_id: int
    issue: str
    status: str
    reported_date: Optional[date]
    resource_name: Optional[str] = None
    logs: List[MaintenanceLogOut] = []

    class Config:
        from_attributes = True


# ─── ANALYTICS ────────────────────────────────────────────────────────────────
class UsageStatOut(BaseModel):
    stat_id: int
    resource_id: int
    resource_name: Optional[str] = None
    total_bookings: int
    usage_count: int
    last_used: Optional[date]

    class Config:
        from_attributes = True

class AnalyticsSummary(BaseModel):
    total_users: int
    total_resources: int
    total_bookings: int
    active_maintenance: int
    top_resources: List[UsageStatOut]
    bookings_by_status: dict