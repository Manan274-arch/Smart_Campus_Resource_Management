from pydantic import BaseModel, EmailStr
from datetime import date, datetime
from typing import Optional

# --- Auth ---

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role_id: int = 1  # default role: student

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# --- User ---

class UserOut(BaseModel):
    user_id: int
    name: str
    email: str
    role_id: int
    created_at: datetime

    class Config:
        from_attributes = True  # lets Pydantic read SQLAlchemy objects directly

# --- Resources ---

class ResourceOut(BaseModel):
    resource_id: int
    name: str
    location: str
    status: str
    type_id: int

    class Config:
        from_attributes = True

# --- Time Slots ---

class TimeSlotOut(BaseModel):
    slot_id: int
    start_time: str
    end_time: str

    class Config:
        from_attributes = True

# --- Bookings ---

class BookingCreate(BaseModel):
    resource_id: int
    slot_id: int
    date: date  # format: YYYY-MM-DD

class BookingOut(BaseModel):
    booking_id: int
    user_id: int
    resource_id: int
    slot_id: int
    date: date
    status_id: int

    class Config:
        from_attributes = True

# --- Maintenance ---

class MaintenanceCreate(BaseModel):
    resource_id: int
    issue: str

class MaintenanceLogCreate(BaseModel):
    update_text: str

class MaintenanceOut(BaseModel):
    maintenance_id: int
    resource_id: int
    issue: str
    status: str
    reported_date: datetime

    class Config:
        from_attributes = True

# --- Analytics ---

class UsageStatOut(BaseModel):
    stat_id: int
    resource_id: int
    total_bookings: int
    usage_count: int
    last_used: Optional[datetime]

    class Config:
        from_attributes = True