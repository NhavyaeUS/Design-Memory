"""
FastAPI application entry point — Design Memory backend.

Serving strategy:
  The existing frontend (Design Memory(1).html) is served as a static file
  at the root URL (/). The API lives at /api/v1. Both run on the same
  local origin (default: http://localhost:8000), so no CORS configuration
  is required for the frontend to call the API.

  FastAPI's automatically generated API documentation is available at:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)

Error handling:
  - Validation errors from Pydantic return HTTP 422 with field-level detail.
  - HTTPExceptions from route handlers return the specified status code.
  - Unhandled exceptions return HTTP 500 with a generic message; no Python
    traceback is exposed to the client.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.items import router as items_router
from app.api.collections import router as collections_router
from app.api.tags import router as tags_router
from app.api.metadata import router as metadata_router

# ─── Application ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Design Memory",
    description="Personal design-reference library — local API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── Global error handler ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all that prevents raw Python tracebacks from reaching the browser.
    The actual exception is printed to the server console for debugging.
    """
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )

# ─── API routes ───────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(health_router, prefix=API_PREFIX)
app.include_router(items_router, prefix=API_PREFIX)
app.include_router(collections_router, prefix=API_PREFIX)
app.include_router(tags_router, prefix=API_PREFIX)
app.include_router(metadata_router, prefix=API_PREFIX)

# ─── Static file serving ──────────────────────────────────────────────────────

# The project root is two levels above this file:  backend/app/main.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Mount the project root so that 'Design Memory(1).html' is accessible.
# html=True makes StaticFiles serve the configured html file for directory requests.
# We serve the project root itself so the HTML file is at /:
#   http://localhost:8000/Design%20Memory(1).html
# Additionally, we copy/symlink it as index.html so http://localhost:8000/ works.
app.mount(
    "/",
    StaticFiles(directory=str(_PROJECT_ROOT), html=True),
    name="static",
)
