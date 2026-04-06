"""
seed.py — Populates the database with initial data.

Also demonstrates SQL concepts in comments:
- Intermediate SQL: JOINs, GROUP BY, HAVING, subqueries
- Complex queries: window functions (via SQLAlchemy)
- PL/SQL concepts: procedures & functions mapped to Python functions
- Cursors: SQLAlchemy cursor-style iteration shown in seed_bookings()
"""

from database import SessionLocal, engine, Base
import models
from auth import hash_password
from datetime import date, timedelta
import random

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── ROLES ──────────────────────────────────────────────────────────────
        if not db.query(models.Role).first():
            roles = [
                models.Role(role_name="admin"),
                models.Role(role_name="student"),
                models.Role(role_name="faculty"),
                models.Role(role_name="staff"),
            ]
            db.add_all(roles)
            db.commit()
            print("✓ Roles seeded")

        # ── USERS ──────────────────────────────────────────────────────────────
        if not db.query(models.User).first():
            users = [
                models.User(name="Admin User",    email="admin@campus.edu",   password_hash=hash_password("admin123"),   role_id=1),
                models.User(name="Alice Student", email="alice@campus.edu",   password_hash=hash_password("alice123"),   role_id=2),
                models.User(name="Bob Faculty",   email="bob@campus.edu",     password_hash=hash_password("bob123"),     role_id=3),
                models.User(name="Carol Staff",   email="carol@campus.edu",   password_hash=hash_password("carol123"),   role_id=4),
                models.User(name="Dave Student",  email="dave@campus.edu",    password_hash=hash_password("dave123"),    role_id=2),
                models.User(name="Eve Faculty",   email="eve@campus.edu",     password_hash=hash_password("eve123"),     role_id=3),
            ]
            db.add_all(users)
            db.commit()
            print("✓ Users seeded")

        # ── RESOURCE TYPES ─────────────────────────────────────────────────────
        if not db.query(models.ResourceType).first():
            types = [
                models.ResourceType(type_name="Classroom"),
                models.ResourceType(type_name="Lab"),
                models.ResourceType(type_name="Auditorium"),
                models.ResourceType(type_name="Sports Facility"),
                models.ResourceType(type_name="Meeting Room"),
            ]
            db.add_all(types)
            db.commit()
            print("✓ Resource types seeded")

        # ── RESOURCES ──────────────────────────────────────────────────────────
        if not db.query(models.Resource).first():
            resources = [
                models.Resource(name="Room A101",        type_id=1, location="Block A, Floor 1",  status="available"),
                models.Resource(name="Room A102",        type_id=1, location="Block A, Floor 1",  status="available"),
                models.Resource(name="CS Lab 1",         type_id=2, location="Block B, Floor 2",  status="available"),
                models.Resource(name="Physics Lab",      type_id=2, location="Block C, Floor 1",  status="available"),
                models.Resource(name="Main Auditorium",  type_id=3, location="Central Block",     status="available"),
                models.Resource(name="Mini Auditorium",  type_id=3, location="Block D",           status="available"),
                models.Resource(name="Basketball Court", type_id=4, location="Sports Complex",    status="available"),
                models.Resource(name="Swimming Pool",    type_id=4, location="Sports Complex",    status="maintenance"),
                models.Resource(name="Conference Room 1",type_id=5, location="Admin Block",       status="available"),
                models.Resource(name="Board Room",       type_id=5, location="Admin Block, Floor 2", status="available"),
            ]
            db.add_all(resources)
            db.commit()
            print("✓ Resources seeded")

        # ── TIME SLOTS ─────────────────────────────────────────────────────────
        if not db.query(models.TimeSlot).first():
            slots = [
                models.TimeSlot(start_time="08:00", end_time="09:00"),
                models.TimeSlot(start_time="09:00", end_time="10:00"),
                models.TimeSlot(start_time="10:00", end_time="11:00"),
                models.TimeSlot(start_time="11:00", end_time="12:00"),
                models.TimeSlot(start_time="12:00", end_time="13:00"),
                models.TimeSlot(start_time="13:00", end_time="14:00"),
                models.TimeSlot(start_time="14:00", end_time="15:00"),
                models.TimeSlot(start_time="15:00", end_time="16:00"),
                models.TimeSlot(start_time="16:00", end_time="17:00"),
                models.TimeSlot(start_time="17:00", end_time="18:00"),
            ]
            db.add_all(slots)
            db.commit()
            print("✓ Time slots seeded")

        # ── BOOKING STATUS ─────────────────────────────────────────────────────
        if not db.query(models.BookingStatus).first():
            statuses = [
                models.BookingStatus(status_name="confirmed"),
                models.BookingStatus(status_name="cancelled"),
                models.BookingStatus(status_name="pending"),
                models.BookingStatus(status_name="completed"),
            ]
            db.add_all(statuses)
            db.commit()
            print("✓ Booking statuses seeded")

        # ── BOOKINGS (cursor-style seeding) ────────────────────────────────────
        # CURSOR CONCEPT: We iterate over (user, resource, slot) combinations
        # like a PL/SQL cursor would process result set rows one by one.
        if not db.query(models.Booking).first():
            confirmed_id = db.query(models.BookingStatus).filter_by(status_name="confirmed").first().status_id
            completed_id = db.query(models.BookingStatus).filter_by(status_name="completed").first().status_id

            # Fetch seed data using cursor-style iteration
            users     = db.query(models.User).filter(models.User.role_id != 1).all()    # non-admin users
            resources = db.query(models.Resource).filter(models.Resource.status == "available").all()
            slots     = db.query(models.TimeSlot).all()

            bookings_to_add = []
            used_combos = set()
            today = date.today()

            # CURSOR: iterate over users × generate bookings
            for user in users:                          # ← cursor row iteration
                for i in range(3):
                    resource = random.choice(resources)
                    slot     = random.choice(slots)
                    bdate    = today - timedelta(days=random.randint(0, 30))
                    combo    = (resource.resource_id, slot.slot_id, bdate)
                    if combo in used_combos:
                        continue
                    used_combos.add(combo)
                    status_id = completed_id if bdate < today else confirmed_id
                    bookings_to_add.append(models.Booking(
                        user_id=user.user_id,
                        resource_id=resource.resource_id,
                        slot_id=slot.slot_id,
                        date=bdate,
                        status_id=status_id
                    ))

            db.add_all(bookings_to_add)
            db.commit()
            print(f"✓ {len(bookings_to_add)} Bookings seeded")

        # ── MAINTENANCE ────────────────────────────────────────────────────────
        if not db.query(models.Maintenance).first():
            maintenance_records = [
                models.Maintenance(resource_id=8, issue="Pool pump failure — needs replacement", status="open"),
                models.Maintenance(resource_id=3, issue="Projector bulb burned out",             status="in_progress"),
                models.Maintenance(resource_id=1, issue="AC unit not cooling properly",          status="resolved"),
            ]
            db.add_all(maintenance_records)
            db.commit()
            print("✓ Maintenance records seeded")

        # ── RESOURCE USAGE STATS ───────────────────────────────────────────────
        # PROCEDURE CONCEPT: This is like a stored procedure that aggregates
        # booking data into the stats table — equivalent to:
        # PROCEDURE update_all_usage_stats AS BEGIN ... END;
        if not db.query(models.ResourceUsageStat).first():
            rebuild_usage_stats(db)

        print("\n✅ Database seeded successfully!")
        print("\nLogin credentials:")
        print("  Admin:   admin@campus.edu / admin123")
        print("  Student: alice@campus.edu / alice123")
        print("  Faculty: bob@campus.edu   / bob123")

    except Exception as e:
        db.rollback()
        print(f"❌ Seeding failed: {e}")
        raise
    finally:
        db.close()


# ── FUNCTION CONCEPT ──────────────────────────────────────────────────────────
# In PL/SQL: FUNCTION get_booking_count(p_resource_id IN NUMBER) RETURN NUMBER
# In Python:
def get_booking_count(db, resource_id: int) -> int:
    """Returns total confirmed bookings for a resource."""
    from sqlalchemy import func
    return db.query(func.count(models.Booking.booking_id)).filter(
        models.Booking.resource_id == resource_id
    ).scalar() or 0


# ── PROCEDURE CONCEPT ─────────────────────────────────────────────────────────
# In PL/SQL: PROCEDURE rebuild_usage_stats AS BEGIN ... END;
# In Python:
def rebuild_usage_stats(db):
    """
    Aggregates all booking data into resource_usage_stats.
    Equivalent to a PL/SQL stored procedure with a cursor loop.
    """
    from sqlalchemy import func
    from datetime import date

    resources = db.query(models.Resource).all()         # OPEN CURSOR

    for resource in resources:                          # FETCH loop
        count = get_booking_count(db, resource.resource_id)
        last_booking = db.query(func.max(models.Booking.date)).filter(
            models.Booking.resource_id == resource.resource_id
        ).scalar()

        existing = db.query(models.ResourceUsageStat).filter_by(
            resource_id=resource.resource_id
        ).first()

        if existing:
            existing.total_bookings = count
            existing.usage_count    = count
            existing.last_used      = last_booking
        else:
            db.add(models.ResourceUsageStat(
                resource_id    = resource.resource_id,
                total_bookings = count,
                usage_count    = count,
                last_used      = last_booking
            ))

    db.commit()                                         # CLOSE CURSOR (implicit)
    print("✓ Usage stats rebuilt")


if __name__ == "__main__":
    seed()