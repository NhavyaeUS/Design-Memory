"""
Alembic env.py — wired to the Design Memory app settings and ORM models.

This file:
1. Reads the DATABASE_URL from our Settings (same source as the running app).
2. Imports all ORM models so Alembic can autogenerate migration scripts.
3. Enables FK constraints for SQLite during migrations.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

# Make 'app' importable from this file (migrations/env.py → backend/app/...)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import engine_from_config, event, pool

from alembic import context

# Import settings (reads DATABASE_URL from environment / .env)
from app.core.config import settings

# Import all models so Alembic autogenerate sees their metadata.
import app.models  # noqa: F401 — side-effects: registers all table metadata
from app.db.session import Base

# Alembic Config object
config = context.config

# Wire Alembic to our database URL (overrides alembic.ini's sqlalchemy.url).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata Alembic autogenerate compares against.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Enable FK enforcement during migrations
    @event.listens_for(connectable, "connect")
    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Required for SQLite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
