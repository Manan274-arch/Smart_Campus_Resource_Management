"""
seed.py — Populates the Smart Campus database with realistic data
=================================================================

Data volume  : ~7 000 bookings spread across 7 months (past + future).
Conflict sim : Duplicate (resource, slot, date) rows intentionally
               created and marked 'rejected_conflict'.

DBMS concepts demonstrated
──────────────────────────
• FUNCTION   : get_booking_count(db, resource_id) — scalar aggregate
• PROCEDURE  : rebuild_usage_stats(db) — GROUP BY / COUNT / MAX bulk rebuild
• CURSOR     : Booking generation loop processes combos one-by-one
• BULK INSERT: bulk_save_objects for high-throughput seeding
"""

from database import SessionLocal, engine, Base
import models
from auth import hash_password
from datetime import date, timedelta
from sqlalchemy import func as sa_func
import random
import math

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
TARGET_BOOKINGS       = 7000          # aim for this many booking rows
HISTORY_DAYS          = 210           # ~7 months of past data
FUTURE_DAYS           = 21            # ~3 weeks of upcoming bookings
CONFLICT_RATIO        = 0.10          # 10 % of bookings become rejected_conflict
PEAK_SLOT_IDS         = range(3, 9)   # slot_ids 3–8 → 10:00–16:00 (1-indexed)

# Status distribution weights (excluding rejected_conflict — handled separately)
STATUS_WEIGHTS = {
    "confirmed":  0.56,   # bumped up so after conflicts net ≈ 50 %
    "cancelled":  0.15,
    "pending":    0.15,
    "completed":  0.11,
}

# Resource popularity weights (index = resource seed order, higher = more popular)
RESOURCE_POPULARITY = [
    5, 5,           # Room A101, A102  — classrooms, moderate
    10, 8,          # CS Lab 1, Physics Lab — very popular
    4, 3,           # Main & Mini Auditorium
    6, 2,           # Basketball Court, Swimming Pool (often in maintenance)
    7, 6,           # Conference Room 1, Board Room
    6, 5, 4, 5, 3,  # extra resources (if more are added)
    3, 3, 3, 3, 3,  # fallback weights
    3, 3, 3, 3, 3,
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FUNCTION CONCEPT (PL/SQL equivalent)
#  FUNCTION get_booking_count(p_resource_id IN NUMBER) RETURN NUMBER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_booking_count(db, resource_id: int) -> int:
    """
    Returns the total number of bookings (all statuses) for a given resource.
    Maps to:  SELECT COUNT(*) FROM bookings WHERE resource_id = :rid;
    """
    return (
        db.query(sa_func.count(models.Booking.booking_id))
        .filter(models.Booking.resource_id == resource_id)
        .scalar()
    ) or 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROCEDURE CONCEPT (PL/SQL equivalent)
#  PROCEDURE rebuild_usage_stats AS
#    CURSOR c IS SELECT resource_id, COUNT(*), MAX(date) FROM bookings
#                WHERE status = 'confirmed' GROUP BY resource_id;
#  BEGIN  FOR r IN c LOOP ... END LOOP; COMMIT; END;
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def rebuild_usage_stats(db):
    """
    Rebuilds the resource_usage_stats table from scratch using
    GROUP BY / COUNT / MAX — equivalent to a stored procedure.
    """
    # Get the 'confirmed' status id for filtering
    confirmed = (
        db.query(models.BookingStatus)
        .filter_by(status_name="confirmed")
        .first()
    )
    confirmed_id = confirmed.status_id if confirmed else -1

    # Aggregate confirmed bookings per resource
    #   SELECT resource_id, COUNT(*), MAX(date)
    #   FROM bookings WHERE status_id = :cid
    #   GROUP BY resource_id
    agg_rows = (
        db.query(
            models.Booking.resource_id,
            sa_func.count(models.Booking.booking_id).label("total"),
            sa_func.max(models.Booking.date).label("last"),
        )
        .filter(models.Booking.status_id == confirmed_id)
        .group_by(models.Booking.resource_id)
        .all()
    )

    agg_map = {row.resource_id: (row.total, row.last) for row in agg_rows}

    # CURSOR-style loop over all resources
    resources = db.query(models.Resource).all()               # OPEN CURSOR
    stats_to_save = []

    for resource in resources:                                 # FETCH loop
        total, last_used = agg_map.get(resource.resource_id, (0, None))

        existing = (
            db.query(models.ResourceUsageStat)
            .filter_by(resource_id=resource.resource_id)
            .first()
        )

        if existing:
            existing.total_bookings = total
            existing.usage_count    = total
            existing.last_used      = last_used
        else:
            stats_to_save.append(
                models.ResourceUsageStat(
                    resource_id    = resource.resource_id,
                    total_bookings = total,
                    usage_count    = total,
                    last_used      = last_used,
                )
            )

    if stats_to_save:
        db.bulk_save_objects(stats_to_save)

    db.commit()                                                # implicit CLOSE CURSOR
    print("  ✓ Usage stats rebuilt (procedure-style)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPER — weighted random date (exponential: more recent = more likely)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _random_date(today: date) -> date:
    """
    Returns a date biased towards the present.
    ~85 % of dates fall in the past; ~15 % in the future.
    Past dates use an exponential distribution so recent weeks are denser.
    """
    if random.random() < 0.15:
        # Future date — uniform within FUTURE_DAYS
        delta = random.randint(1, FUTURE_DAYS)
        return today + timedelta(days=delta)
    else:
        # Past date — exponential: λ = 3 / HISTORY_DAYS  →  mean ≈ 70 days ago
        lam = 3.0 / HISTORY_DAYS
        days_ago = int(random.expovariate(lam))
        days_ago = min(days_ago, HISTORY_DAYS)   # cap at history window
        return today - timedelta(days=days_ago)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPER — pick status based on distribution weights
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _pick_status(status_map: dict, booking_date: date, today: date) -> int:
    """
    Returns a status_id based on weighted random selection.
    Past dates that drew 'confirmed' are upgraded to 'completed' 50 % of the time
    for extra realism.
    """
    names = list(STATUS_WEIGHTS.keys())
    weights = [STATUS_WEIGHTS[n] for n in names]
    chosen = random.choices(names, weights=weights, k=1)[0]

    # Past confirmed bookings sometimes convert to completed
    if chosen == "confirmed" and booking_date < today and random.random() < 0.50:
        chosen = "completed"

    return status_map[chosen]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN SEED FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def seed():
    """Master seed routine — idempotent (skips tables that already have rows)."""

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── 1. ROLES ──────────────────────────────────────────────────────────
        if not db.query(models.Role).first():
            db.add_all([
                models.Role(role_name="admin"),
                models.Role(role_name="student"),
                models.Role(role_name="faculty"),
                models.Role(role_name="staff"),
            ])
            db.commit()
            print("  ✓ Roles seeded (4)")

        # ── 2. USERS ──────────────────────────────────────────────────────────
        if not db.query(models.User).first():
            base_users = [
                # Admins
                ("Admin User",          "admin@campus.edu",       "admin123",    1),
                # Faculty
                ("Dr. Sarah Mitchell",  "s.mitchell@campus.edu",  "faculty123",  3),
                ("Prof. James Chen",    "j.chen@campus.edu",      "faculty123",  3),
                ("Dr. Priya Sharma",    "p.sharma@campus.edu",    "faculty123",  3),
                ("Prof. Robert Wilson",  "r.wilson@campus.edu",   "faculty123",  3),
                ("Dr. Emily Brooks",    "e.brooks@campus.edu",    "faculty123",  3),
                # Staff
                ("Carol Martinez",      "c.martinez@campus.edu",  "staff123",    4),
                ("Kevin Park",          "k.park@campus.edu",      "staff123",    4),
                ("Lisa Thompson",       "l.thompson@campus.edu",  "staff123",    4),
            ]
            # Generate 40 students
            first_names = [
                "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace",
                "Henry", "Iris", "Jack", "Karen", "Liam", "Mia", "Noah",
                "Olivia", "Paul", "Quinn", "Ryan", "Sophia", "Tom",
                "Uma", "Victor", "Wendy", "Xavier", "Yara", "Zane",
                "Aiden", "Bella", "Caleb", "Daisy", "Ethan", "Fiona",
                "Gavin", "Hannah", "Ivan", "Julia", "Kyle", "Luna",
                "Mason", "Nora",
            ]
            students = [
                (f"{name} Student", f"{name.lower()}@campus.edu", "student123", 2)
                for name in first_names
            ]

            all_users = base_users + students
            db.add_all([
                models.User(
                    name=u[0], email=u[1],
                    password_hash=hash_password(u[2]),
                    role_id=u[3],
                )
                for u in all_users
            ])
            db.commit()
            print(f"  ✓ Users seeded ({len(all_users)})")

        # ── 3. RESOURCE TYPES ─────────────────────────────────────────────────
        if not db.query(models.ResourceType).first():
            types = [
                models.ResourceType(type_name="Classroom"),
                models.ResourceType(type_name="Lab"),
                models.ResourceType(type_name="Auditorium"),
                models.ResourceType(type_name="Sports Facility"),
                models.ResourceType(type_name="Meeting Room"),
                models.ResourceType(type_name="Library Room"),
            ]
            db.add_all(types)
            db.commit()
            print(f"  ✓ Resource types seeded ({len(types)})")

        # ── 4. RESOURCES ──────────────────────────────────────────────────────
        if not db.query(models.Resource).first():
            resources = [
                # type_id 1 — Classrooms
                models.Resource(name="Room A101",          type_id=1, location="Block A, Floor 1",      capacity=60,  status="available"),
                models.Resource(name="Room A102",          type_id=1, location="Block A, Floor 1",      capacity=60,  status="available"),
                models.Resource(name="Room B201",          type_id=1, location="Block B, Floor 2",      capacity=40,  status="available"),
                models.Resource(name="Room C301",          type_id=1, location="Block C, Floor 3",      capacity=80,  status="available"),
                # type_id 2 — Labs
                models.Resource(name="CS Lab 1",           type_id=2, location="Block B, Floor 2",      capacity=35,  status="available"),
                models.Resource(name="CS Lab 2",           type_id=2, location="Block B, Floor 2",      capacity=35,  status="available"),
                models.Resource(name="Physics Lab",        type_id=2, location="Block C, Floor 1",      capacity=30,  status="available"),
                models.Resource(name="Electronics Lab",    type_id=2, location="Block C, Floor 2",      capacity=25,  status="available"),
                # type_id 3 — Auditoriums
                models.Resource(name="Main Auditorium",    type_id=3, location="Central Block",         capacity=500, status="available"),
                models.Resource(name="Mini Auditorium",    type_id=3, location="Block D",               capacity=150, status="available"),
                # type_id 4 — Sports
                models.Resource(name="Basketball Court",   type_id=4, location="Sports Complex",        capacity=50,  status="available"),
                models.Resource(name="Swimming Pool",      type_id=4, location="Sports Complex",        capacity=30,  status="maintenance"),
                models.Resource(name="Tennis Court",       type_id=4, location="Sports Complex",        capacity=10,  status="available"),
                # type_id 5 — Meeting rooms
                models.Resource(name="Conference Room 1",  type_id=5, location="Admin Block",           capacity=20,  status="available"),
                models.Resource(name="Board Room",         type_id=5, location="Admin Block, Floor 2",  capacity=15,  status="available"),
                # type_id 6 — Library
                models.Resource(name="Study Room A",       type_id=6, location="Library, Floor 1",      capacity=8,   status="available"),
                models.Resource(name="Study Room B",       type_id=6, location="Library, Floor 2",      capacity=8,   status="available"),
            ]
            db.add_all(resources)
            db.commit()
            print(f"  ✓ Resources seeded ({len(resources)})")

        # ── 5. TIME SLOTS ─────────────────────────────────────────────────────
        if not db.query(models.TimeSlot).first():
            slot_hours = [
                ("08:00", "09:00"), ("09:00", "10:00"), ("10:00", "11:00"),
                ("11:00", "12:00"), ("12:00", "13:00"), ("13:00", "14:00"),
                ("14:00", "15:00"), ("15:00", "16:00"), ("16:00", "17:00"),
                ("17:00", "18:00"),
            ]
            db.add_all([
                models.TimeSlot(start_time=s, end_time=e) for s, e in slot_hours
            ])
            db.commit()
            print(f"  ✓ Time slots seeded ({len(slot_hours)})")

        # ── 6. BOOKING STATUSES ───────────────────────────────────────────────
        if not db.query(models.BookingStatus).first():
            statuses = [
                models.BookingStatus(status_name="confirmed"),
                models.BookingStatus(status_name="cancelled"),
                models.BookingStatus(status_name="pending"),
                models.BookingStatus(status_name="completed"),
                models.BookingStatus(status_name="rejected_conflict"),
            ]
            db.add_all(statuses)
            db.commit()
            print(f"  ✓ Booking statuses seeded ({len(statuses)})")

        # ── 7. BOOKINGS — cursor-style generation with conflict simulation ───
        if not db.query(models.Booking).first():
            _seed_bookings(db)

        # ── 8. MAINTENANCE ────────────────────────────────────────────────────
        if not db.query(models.Maintenance).first():
            maint = [
                models.Maintenance(resource_id=12, issue="Pool pump failure — needs motor replacement",       status="open"),
                models.Maintenance(resource_id=5,  issue="Projector bulb burned out in CS Lab 1",            status="in_progress"),
                models.Maintenance(resource_id=1,  issue="AC unit not cooling properly — serviced",          status="resolved"),
                models.Maintenance(resource_id=8,  issue="Oscilloscope #3 showing erratic readings",        status="open"),
                models.Maintenance(resource_id=9,  issue="Stage lighting control panel malfunction",         status="in_progress"),
                models.Maintenance(resource_id=13, issue="Tennis court net torn — awaiting replacement",     status="open"),
            ]
            db.add_all(maint)
            db.commit()
            print(f"  ✓ Maintenance records seeded ({len(maint)})")

        # ── 9. REBUILD USAGE STATS (procedure-style) ──────────────────────────
        rebuild_usage_stats(db)

        # ── SUMMARY ───────────────────────────────────────────────────────────
        total_bookings = db.query(sa_func.count(models.Booking.booking_id)).scalar()
        total_users    = db.query(sa_func.count(models.User.user_id)).scalar()
        total_res      = db.query(sa_func.count(models.Resource.resource_id)).scalar()

        print("\n" + "═" * 60)
        print("  ✅  DATABASE SEEDED SUCCESSFULLY")
        print("═" * 60)
        print(f"  Total users       : {total_users}")
        print(f"  Total resources   : {total_res}")
        print(f"  Total bookings    : {total_bookings}")
        print()
        print("  Login credentials:")
        print("    Admin   : admin@campus.edu      / admin123")
        print("    Faculty : s.mitchell@campus.edu  / faculty123")
        print("    Student : alice@campus.edu       / student123")
        print("    Staff   : c.martinez@campus.edu  / staff123")
        print("═" * 60)

    except Exception as e:
        db.rollback()
        print(f"\n  ❌ Seeding failed: {e}")
        raise
    finally:
        db.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BOOKING GENERATION — cursor-style loop with conflict injection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _seed_bookings(db):
    """
    CURSOR CONCEPT — iterate over generated booking candidates one-by-one,
    decide status, and optionally inject a duplicate "rejected_conflict" row
    for the same (resource, slot, date) combination.

    Performance: all rows are collected in a list and flushed via
    bulk_save_objects in a single batch.
    """
    today = date.today()

    # ── Fetch lookup data ─────────────────────────────────────────────────────
    users     = db.query(models.User).filter(models.User.role_id != 1).all()
    resources = db.query(models.Resource).filter(
        models.Resource.status != "inactive"
    ).all()
    slots     = db.query(models.TimeSlot).all()

    # Build status_name → status_id map
    status_rows = db.query(models.BookingStatus).all()
    status_map  = {s.status_name: s.status_id for s in status_rows}

    if not users or not resources or not slots:
        print("  ⚠ Skipping bookings — prerequisite tables empty")
        return

    # ── Build resource popularity weights ─────────────────────────────────────
    res_weights = [
        RESOURCE_POPULARITY[i] if i < len(RESOURCE_POPULARITY) else 3
        for i in range(len(resources))
    ]

    # ── Build slot weights (peak hours heavier) ───────────────────────────────
    slot_weights = [
        3 if s.slot_id in PEAK_SLOT_IDS else 1
        for s in slots
    ]

    # ── Generate bookings ─────────────────────────────────────────────────────
    bookings_buffer = []          # accumulate ORM objects for bulk insert
    conflict_count  = 0
    occupied        = {}          # (resource_id, slot_id, date) → primary booking user_id

    # CURSOR: each iteration = one booking candidate
    iteration = 0
    while len(bookings_buffer) < TARGET_BOOKINGS:
        iteration += 1

        # Pick random user, resource (weighted), slot (weighted), date (expo)
        user     = random.choice(users)
        resource = random.choices(resources, weights=res_weights, k=1)[0]
        slot     = random.choices(slots,     weights=slot_weights, k=1)[0]
        bdate    = _random_date(today)

        combo = (resource.resource_id, slot.slot_id, bdate)

        # ── Conflict simulation ───────────────────────────────────────────────
        if combo in occupied:
            # This slot/resource/date was already booked.
            # Inject a rejected_conflict row with CONFLICT_RATIO probability.
            if random.random() < CONFLICT_RATIO / 0.3:
                # Only create conflict if the duplicate is a *different* user
                if occupied[combo] != user.user_id:
                    bookings_buffer.append(models.Booking(
                        user_id     = user.user_id,
                        resource_id = resource.resource_id,
                        slot_id     = slot.slot_id,
                        date        = bdate,
                        status_id   = status_map["rejected_conflict"],
                    ))
                    conflict_count += 1
            # Skip this iteration for the normal booking path
            continue

        # ── Normal booking ────────────────────────────────────────────────────
        sid = _pick_status(status_map, bdate, today)

        bookings_buffer.append(models.Booking(
            user_id     = user.user_id,
            resource_id = resource.resource_id,
            slot_id     = slot.slot_id,
            date        = bdate,
            status_id   = sid,
        ))
        occupied[combo] = user.user_id

        # Safety valve — avoid infinite loop if date/resource space is exhausted
        if iteration > TARGET_BOOKINGS * 5:
            break

    # ── Bulk insert ───────────────────────────────────────────────────────────
    db.bulk_save_objects(bookings_buffer)
    db.commit()

    # ── Print distribution summary ────────────────────────────────────────────
    status_counts = (
        db.query(
            models.BookingStatus.status_name,
            sa_func.count(models.Booking.booking_id),
        )
        .join(models.Booking, models.BookingStatus.status_id == models.Booking.status_id)
        .group_by(models.BookingStatus.status_name)
        .all()
    )

    print(f"  ✓ Bookings seeded: {len(bookings_buffer)} total, {conflict_count} conflicts")
    print("    Status distribution:")
    for name, cnt in sorted(status_counts, key=lambda x: -x[1]):
        pct = cnt / len(bookings_buffer) * 100
        bar = "█" * int(pct / 2)
        print(f"      {name:<20s} {cnt:>5d}  ({pct:5.1f}%)  {bar}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print("\n🌱 Seeding Smart Campus database …\n")
    seed()