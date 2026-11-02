"""
Shared pytest fixtures.

Why a separate test database?
- Tests must never read or write the real user database.
- We create a fresh in-memory SQLite DB for each test session and apply the
  same schema via Alembic-compatible Base.metadata.create_all().
- Using create_all() here is intentional: it's fast for tests and we're
  testing the same schema that Alembic manages in production.

What is a pytest fixture?
- A function decorated with @pytest.fixture that provides reusable test setup
  and teardown.  Tests that declare the fixture name as a parameter receive
  the fixture's return value automatically.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app

# In-memory SQLite for tests — never touches the real database file.
TEST_DB_URL = "sqlite://"   # empty path = in-memory


@pytest.fixture(scope="session")
def engine():
    """Create the test engine and schema once for the whole test session."""
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db(engine):
    """
    Provide a database session that is rolled back after each test.
    This keeps tests isolated: no test sees another test's writes.
    """
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSession(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """
    Provide a FastAPI TestClient wired to the test database session.

    We override the get_db dependency so every request the TestClient makes
    uses the test session (and therefore the rollback after each test).
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass  # rollback is handled by the db fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
