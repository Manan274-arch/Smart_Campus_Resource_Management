from database import SessionLocal, engine, Base
import models

# Create all tables first (safe to run even if they exist)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# ── 1. Roles ──────────────────────────────────────────────
roles = ["student", "staff", "admin"]
for role_name in roles:
    exists = db.query(models.Role).filter(models.Role.role_name == role_name).first()
    if not exists:
        db.add(models.Role(role_name=role_name))

db.commit()
print("✓ Roles seeded")

# ── 2. Resource Types ─────────────────────────────────────
types = ["classroom", "lab", "sports", "auditorium", "meeting room"]
for type_name in types:
    exists = db.query(models.ResourceType).filter(models.ResourceType.type_name == type_name).first()
    if not exists:
        db.add(models.ResourceType(type_name=type_name))

db.commit()
print("✓ Resource types seeded")

# ── 3. Resources ──────────────────────────────────────────
classroom_type = db.query(models.ResourceType).filter(models.ResourceType.type_name == "classroom").first()
lab_type       = db.query(models.ResourceType).filter(models.ResourceType.type_name == "lab").first()
sports_type    = db.query(models.ResourceType).filter(models.ResourceType.type_name == "sports").first()
audio_type     = db.query(models.ResourceType).filter(models.ResourceType.type_name == "auditorium").first()
meeting_type   = db.query(models.ResourceType).filter(models.ResourceType.type_name == "meeting room").first()

resources_data = [
    ("Room A101",       classroom_type.type_id, "Block A, Floor 1"),
    ("Room A102",       classroom_type.type_id, "Block A, Floor 1"),
    ("Computer Lab 1",  lab_type.type_id,       "Block B, Floor 2"),
    ("Computer Lab 2",  lab_type.type_id,       "Block B, Floor 2"),
    ("Basketball Court",sports_type.type_id,    "Sports Complex"),
    ("Main Auditorium", audio_type.type_id,     "Central Block"),
    ("Meeting Room 1",  meeting_type.type_id,   "Admin Block"),
    ("Meeting Room 2",  meeting_type.type_id,   "Admin Block"),
]

for name, type_id, location in resources_data:
    exists = db.query(models.Resource).filter(models.Resource.name == name).first()
    if not exists:
        db.add(models.Resource(name=name, type_id=type_id, location=location, status="available"))

db.commit()
print("✓ Resources seeded")

# ── 4. Time Slots ─────────────────────────────────────────
slots = [
    ("08:00", "09:00"),
    ("09:00", "10:00"),
    ("10:00", "11:00"),
    ("11:00", "12:00"),
    ("12:00", "13:00"),
    ("13:00", "14:00"),
    ("14:00", "15:00"),
    ("15:00", "16:00"),
    ("16:00", "17:00"),
    ("17:00", "18:00"),
]

for start, end in slots:
    exists = db.query(models.TimeSlot).filter(
        models.TimeSlot.start_time == start,
        models.TimeSlot.end_time == end
    ).first()
    if not exists:
        db.add(models.TimeSlot(start_time=start, end_time=end))

db.commit()
print("✓ Time slots seeded")

# ── 5. Booking Statuses ───────────────────────────────────
statuses = ["confirmed", "cancelled"]
for status_name in statuses:
    exists = db.query(models.BookingStatus).filter(models.BookingStatus.status_name == status_name).first()
    if not exists:
        db.add(models.BookingStatus(status_name=status_name))

db.commit()
print("✓ Booking statuses seeded")

# ── 6. Usage Stat rows (one per resource) ─────────────────
all_resources = db.query(models.Resource).all()
for resource in all_resources:
    exists = db.query(models.ResourceUsageStat).filter(
        models.ResourceUsageStat.resource_id == resource.resource_id
    ).first()
    if not exists:
        db.add(models.ResourceUsageStat(
            resource_id=resource.resource_id,
            total_bookings=0,
            usage_count=0
        ))

db.commit()
print("✓ Usage stats initialized")

db.close()
print("\n All done! Database is ready.")