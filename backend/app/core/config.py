"""Application settings loaded from environment variables / .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve the project root (one level above backend/)
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_DATA_DIR = _BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load a .env file from the backend directory if it exists.
        env_file=Path(__file__).resolve().parent.parent.parent / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite URL for the application database.
    # The 'data/' directory lives next to the backend/ folder and is gitignored.
    DATABASE_URL: str = f"sqlite:///{_DATA_DIR / 'design_memory.db'}"

    # SQLite URL for the test database (separate file, never touches real data).
    TEST_DATABASE_URL: str = f"sqlite:///{_DATA_DIR / 'design_memory_test.db'}"

    ENV: str = "development"


settings = Settings()

# Ensure the data directory exists so SQLite can create the database file.
_DATA_DIR.mkdir(parents=True, exist_ok=True)
