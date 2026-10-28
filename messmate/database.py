import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from messmate.config import DATABASE_URL

# For SQLite, enable busy timeout, check_same_thread=False, and safe PRAGMAs
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 30

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
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
        except Exception:
            try:
                cursor.execute("PRAGMA journal_mode=DELETE")
            except Exception:
                pass
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
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(users)"))
            cols = [row[1] for row in result.fetchall()]
            if cols and "approval_status" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN approval_status VARCHAR(20) DEFAULT 'approved'"))
                conn.commit()
    except Exception:
        pass

