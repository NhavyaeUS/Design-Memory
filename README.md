# Design Memory

A personal, local design-reference library for collecting, organizing, and inspecting visual design inspiration, color palettes, typography, and web references.

## Features

- **Resource Management**: Save and organize design resources (websites, color palettes, typography, UI patterns, imagery, tools, animations).
- **Color Palettes**: Palette creation, HEX/RGB/CMYK/HSL formats, manual editing, and CSS variable export.
- **Search & Collections**: Instant client-side filtering, tagging, and collection assignment.
- **URL & Duplicate Handling**: Scheme validation, tracking parameter stripping, exact/domain duplicate checks with optional override.
- **Safe Metadata Extraction**: Built-in SSRF protection, streaming byte limits, OpenGraph/meta tag parsing, and automatic fallback.

## Tech Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, SQLite, HTTPX, Pydantic v2
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (no external framework build steps)

## Quick Start

### 1. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Database Migrations & Seeding

```bash
# Apply migrations
alembic upgrade head

# (Optional) Seed initial collections and sample references
python scripts/seed.py
```

### 3. Run Locally

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000` in your browser.  
Interactive API docs are available at `http://localhost:8000/docs`.

### 4. Run Automated Tests

```bash
pytest -v
```
