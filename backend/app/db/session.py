"""SQLAlchemy engine and session dependency for FastAPI."""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _make_engine(url: str):
    engine = create_engine(
        url,
        # Required for SQLite: each connection must be used in the thread that created it.
        # connect_args below + check_same_thread=False is the standard FastAPI pattern.
        connect_args={"check_same_thread": False},
    )

    # Enable foreign-key enforcement for every new SQLite connection.
    # SQLite disables FK checks by default; this PRAGMA turns them on per-connection.
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = _make_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,   # We flush explicitly; avoids surprise queries mid-request
    autocommit=False,  # All writes go through an explicit transaction
    expire_on_commit=False,  # Keep ORM objects usable after session.commit()
)


class Base(DeclarativeBase):
    """Base class that all ORM models inherit from."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that opens a database session for a request,
    commits on success, rolls back on any error, and always closes.

    Usage:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
