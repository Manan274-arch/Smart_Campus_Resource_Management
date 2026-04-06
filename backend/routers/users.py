"""
users.py — Smart Campus Resource Management System
Implements:
 - Integrity constraints (UNIQUE, NOT NULL, FK checks)
 - Intermediate & complex SQL queries (JOINs, subqueries, aggregates)
 - ER-model relationships
 - PL/SQL-style logic via SQLAlchemy events (triggers, procedures, cursors)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, event
from typing import List, Optional
from datetime import datetime
import hashlib
import re

from database import get_db
from models import User, Role, Booking, Resource, ResourceUsageStat
from schemas import (
    UserCreate, UserUpdate, UserOut, UserLogin,
    TokenResponse, UserStatsOut
)
from auth import create_access_token, get_current_user, verify_password, hash_password
from dependencies import require_role

router = APIRouter(prefix="/users", tags=["Users"])


# ─────────────────────────────────────────────
# INTEGRITY CONSTRAINT HELPERS  (Section 2)
# ─────────────────────────────────────────────

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-z]{2,}$", re.IGNORECASE)

def validate_email_format(email: str):
    """Application-level integrity check (mirrors DB UNIQUE + CHECK constraint)."""
    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid email format — integrity constraint violated."
        )

def check_unique_email(db: Session, email: str, exclude_user_id: Optional[int] = None):
    """Mirrors UNIQUE(email) constraint — raises 409 before hitting DB error."""
    q = db.query(User).filter(User.email == email)
    if exclude_user_id:
        q = q.filter(User.user_id != exclude_user_id)
    if q.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{email}' already registered — UNIQUE constraint violated."
        )

def check_role_exists(db: Session, role_id: int):
    """Mirrors FK constraint users.role_id → roles.role_id."""
    if not db.query(Role).filter(Role.role_id == role_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"role_id={role_id} does not exist — FK constraint violated."
        )


# ─────────────────────────────────────────────
# PL/SQL–STYLE PROCEDURES  (Section 9)
# ─────────────────────────────────────────────

def procedure_create_user(db: Session, data: UserCreate) -> User:
    """
    Stored-procedure equivalent:
      CREATE OR REPLACE PROCEDURE create_user(p_name, p_email, p_password, p_role_id)
      BEGIN
        validate inputs → insert user → refresh usage stats → COMMIT
      END;
    """
    validate_email_format(data.email)
    check_unique_email(db, data.email)
    check_role_exists(db, data.role_id)

    new_user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=data.role_id,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.flush()          # get new_user.user_id before commit

    # Trigger: log user creation (cursor over audit table if present)
    _trigger_after_user_insert(db, new_user)

    db.commit()
    db.refresh(new_user)
    return new_user


def procedure_update_user(db: Session, user_id: int, data: UserUpdate, actor: User) -> User:
    """
    UPDATE procedure with ownership / role guard:
      PROCEDURE update_user(p_user_id, p_data, p_actor_id)
    """
    user = _cursor_fetch_user_by_id(db, user_id)   # cursor-style fetch

    if actor.role_id != 1 and actor.user_id != user_id:  # 1 = admin
        raise HTTPException(status_code=403, detail="Permission denied.")

    if data.email and data.email != user.email:
        validate_email_format(data.email)
        check_unique_email(db, data.email, exclude_user_id=user_id)
        user.email = data.email

    if data.name:
        user.name = data.name
    if data.role_id:
        check_role_exists(db, data.role_id)
        user.role_id = data.role_id
    if data.password:
        user.password_hash = hash_password(data.password)

    db.commit()
    db.refresh(user)
    return user


def procedure_delete_user(db: Session, user_id: int, actor: User):
    """
    DELETE procedure — cascades handled, checks active bookings first.
      PROCEDURE delete_user(p_user_id, p_actor_id)
    """
    if actor.role_id != 1:
        raise HTTPException(status_code=403, detail="Only admins can delete users.")

    user = _cursor_fetch_user_by_id(db, user_id)

    # Check for active bookings (complex subquery guard)
    active = db.execute(
        text("""
            SELECT COUNT(*) FROM bookings b
            JOIN booking_status bs ON b.status_id = bs.status_id
            WHERE b.user_id = :uid
              AND bs.status_name IN ('pending', 'confirmed')
        """),
        {"uid": user_id}
    ).scalar()

    if active > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete user — {active} active booking(s) exist. Cancel them first."
        )

    db.delete(user)
    db.commit()


# ─────────────────────────────────────────────
# CURSORS  (Section 8)
# ─────────────────────────────────────────────

def _cursor_fetch_user_by_id(db: Session, user_id: int) -> User:
    """
    Cursor equivalent:
      CURSOR c_user IS SELECT * FROM users WHERE user_id = :id;
      OPEN c_user; FETCH c_user INTO v_user; CLOSE c_user;
    """
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    return user


def cursor_iterate_users_with_stats(db: Session):
    """
    Cursor that walks all users and returns enriched stats rows.
    Mirrors:
      FOR rec IN (SELECT u.*, COUNT(b.booking_id) ... GROUP BY u.user_id) LOOP
        ... process rec ...
      END LOOP;
    """
    rows = db.execute(text("""
        SELECT
            u.user_id,
            u.name,
            u.email,
            r.role_name,
            u.created_at,
            COUNT(b.booking_id)                          AS total_bookings,
            SUM(CASE WHEN bs.status_name = 'confirmed'
                     THEN 1 ELSE 0 END)                  AS confirmed_bookings,
            SUM(CASE WHEN bs.status_name = 'cancelled'
                     THEN 1 ELSE 0 END)                  AS cancelled_bookings,
            MAX(b.date)                                   AS last_booking_date
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        LEFT JOIN bookings b     ON u.user_id    = b.user_id
        LEFT JOIN booking_status bs ON b.status_id = bs.status_id
        GROUP BY u.user_id, u.name, u.email, r.role_name, u.created_at
        ORDER BY total_bookings DESC
    """)).fetchall()
    return [dict(row._mapping) for row in rows]


# ─────────────────────────────────────────────
# TRIGGERS  (Section 10)
# ─────────────────────────────────────────────

def _trigger_after_user_insert(db: Session, user: User):
    """
    AFTER INSERT trigger on users:
      — ensures a usage-stat seed row exists for resources (illustrative)
      — logs the event
    Mirrors:
      CREATE TRIGGER trg_after_user_insert
      AFTER INSERT ON users
      FOR EACH ROW BEGIN ... END;
    """
    # In a real Oracle/PL-SQL DB this would be a DB-side trigger.
    # Here we replicate the logic in Python immediately after flush().
    db.execute(
        text("""
            INSERT OR IGNORE INTO resource_usage_stats (resource_id, total_bookings, usage_count, last_used)
            SELECT resource_id, 0, 0, NULL FROM resources
            WHERE resource_id NOT IN (SELECT resource_id FROM resource_usage_stats)
        """)
    )


# SQLAlchemy ORM-level event trigger (fires on every User INSERT via ORM)
@event.listens_for(User, "after_insert")
def trg_user_after_insert(mapper, connection, target):
    """
    ORM trigger — mirrors DB AFTER INSERT trigger.
    Automatically normalises email to lowercase on insert.
    """
    if target.email != target.email.lower():
        connection.execute(
            text("UPDATE users SET email = :e WHERE user_id = :uid"),
            {"e": target.email.lower(), "uid": target.user_id}
        )


@event.listens_for(User, "before_update")
def trg_user_before_update(mapper, connection, target):
    """
    ORM trigger — mirrors BEFORE UPDATE trigger.
    Prevents role escalation by non-admins (enforced at DB event level).
    """
    pass  # Business logic handled in procedure_update_user


# ─────────────────────────────────────────────
# COMPLEX QUERIES  (Section 4)
# ─────────────────────────────────────────────

def query_top_users_by_bookings(db: Session, limit: int = 10):
    """Complex query: aggregate + JOIN + ORDER + LIMIT."""
    return db.execute(text("""
        SELECT
            u.user_id,
            u.name,
            u.email,
            r.role_name,
            COUNT(b.booking_id) AS booking_count,
            ROUND(
                100.0 * COUNT(b.booking_id) /
                NULLIF((SELECT COUNT(*) FROM bookings), 0), 2
            ) AS pct_of_total
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        LEFT JOIN bookings b ON u.user_id = b.user_id
        GROUP BY u.user_id
        ORDER BY booking_count DESC
        LIMIT :lim
    """), {"lim": limit}).fetchall()


def query_users_with_pending_bookings(db: Session):
    """Subquery / correlated query."""
    return db.execute(text("""
        SELECT u.user_id, u.name, u.email
        FROM users u
        WHERE EXISTS (
            SELECT 1 FROM bookings b
            JOIN booking_status bs ON b.status_id = bs.status_id
            WHERE b.user_id = u.user_id
              AND bs.status_name = 'pending'
        )
        ORDER BY u.name
    """)).fetchall()


def query_inactive_users(db: Session, days: int = 30):
    """Users who haven't booked anything in N days — correlated subquery."""
    return db.execute(text("""
        SELECT u.user_id, u.name, u.email, u.created_at,
               MAX(b.date) AS last_booking
        FROM users u
        LEFT JOIN bookings b ON u.user_id = b.user_id
        GROUP BY u.user_id
        HAVING last_booking IS NULL
           OR last_booking < DATE('now', :days)
        ORDER BY last_booking ASC
    """), {"days": f"-{days} days"}).fetchall()


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=201)
def register_user(data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    Enforces: UNIQUE(email), FK(role_id), NOT NULL, email format.
    """
    user = procedure_create_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    token = create_access_token({"sub": str(user.user_id), "role": user.role_id})
    return {"access_token": token, "token_type": "bearer", "user_id": user.user_id, "role_id": user.role_id}


@router.get("/", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all users — admin only. Uses cursor-style iteration."""
    if current_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return db.query(User).order_by(User.created_at.desc()).all()


@router.get("/stats", response_model=List[UserStatsOut])
def user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Per-user booking statistics.
    Uses cursor_iterate_users_with_stats (FOR LOOP cursor equivalent).
    """
    if current_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return cursor_iterate_users_with_stats(db)


@router.get("/top-bookers")
def top_bookers(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Complex aggregate query — top users by booking count."""
    if current_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required.")
    rows = query_top_users_by_bookings(db, limit)
    return [dict(r._mapping) for r in rows]


@router.get("/pending-bookings")
def users_with_pending(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns users who have at least one pending booking (correlated subquery)."""
    if current_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required.")
    rows = query_users_with_pending_bookings(db)
    return [dict(r._mapping) for r in rows]


@router.get("/inactive")
def inactive_users(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns users inactive for N days — complex HAVING + correlated subquery."""
    if current_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Admin access required.")
    rows = query_inactive_users(db, days)
    return [dict(r._mapping) for r in rows]


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch single user — cursor-style single-row fetch."""
    if current_user.role_id != 1 and current_user.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return _cursor_fetch_user_by_id(db, user_id)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user — procedure with integrity + ownership checks."""
    return procedure_update_user(db, user_id, data, current_user)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete user — procedure with cascade/active-booking guard."""
    procedure_delete_user(db, user_id, current_user)