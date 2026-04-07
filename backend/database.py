from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./campus.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Enable foreign keys and create triggers on each connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()

    # INTEGRITY: Enable foreign key enforcement
    cursor.execute("PRAGMA foreign_keys = ON")

    # Triggers are wrapped in try/except because on first run the tables
    # don't exist yet — they will be created by Base.metadata.create_all()
    # On all subsequent connections the triggers will be created normally.

    try:
        # TRIGGER 1: Prevent booking a resource under maintenance
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_block_maintenance_booking
            BEFORE INSERT ON bookings
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'Resource is currently under maintenance')
                WHERE EXISTS (
                    SELECT 1 FROM maintenance
                    WHERE resource_id = NEW.resource_id
                    AND status IN ('open', 'in_progress')
                );
            END
        """)
    except Exception:
        pass

    try:
        # TRIGGER 2: Auto-update resource_usage_stats on new confirmed booking
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_update_usage_stats_insert
            AFTER INSERT ON bookings
            FOR EACH ROW
            WHEN NEW.status_id = (SELECT status_id FROM booking_status WHERE status_name = 'confirmed')
            BEGIN
                INSERT INTO resource_usage_stats (resource_id, total_bookings, usage_count, last_used)
                VALUES (NEW.resource_id, 1, 1, NEW.date)
                ON CONFLICT(resource_id) DO UPDATE SET
                    total_bookings = total_bookings + 1,
                    usage_count = usage_count + 1,
                    last_used = NEW.date;
            END
        """)
    except Exception:
        pass

    try:
        # TRIGGER 3: Log maintenance status changes
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_log_maintenance_update
            AFTER UPDATE OF status ON maintenance
            FOR EACH ROW
            BEGIN
                INSERT INTO maintenance_logs (maintenance_id, update_text, updated_at)
                VALUES (
                    NEW.maintenance_id,
                    'Status changed from ' || OLD.status || ' to ' || NEW.status,
                    datetime('now')
                );
            END
        """)
    except Exception:
        pass

    try:
        # TRIGGER 4: Set resource status to 'maintenance' when issue reported
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_resource_status_on_maintenance
            AFTER INSERT ON maintenance
            FOR EACH ROW
            BEGIN
                UPDATE resources SET status = 'maintenance'
                WHERE resource_id = NEW.resource_id;
            END
        """)
    except Exception:
        pass

    try:
        # TRIGGER 5: Restore resource to 'available' when maintenance resolved
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_resource_restore_on_resolve
            AFTER UPDATE OF status ON maintenance
            FOR EACH ROW
            WHEN NEW.status = 'resolved'
            BEGIN
                UPDATE resources SET status = 'available'
                WHERE resource_id = NEW.resource_id
                AND NOT EXISTS (
                    SELECT 1 FROM maintenance
                    WHERE resource_id = NEW.resource_id
                    AND status IN ('open', 'in_progress')
                    AND maintenance_id != NEW.maintenance_id
                );
            END
        """)
    except Exception:
        pass

    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()