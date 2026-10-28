import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from messmate.config import DATABASE_URL

# For SQLite, enable WAL mode and foreign key constraints
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    future=True
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Create all tables in the database and ensure column migrations."""
    # Import all models so that Base.metadata has knowledge of all tables
    import messmate.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Check and add approval_status column if missing in existing database
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN approval_status VARCHAR(20) DEFAULT 'approved'"))
            conn.commit()
        except Exception:
            pass  # Already present

