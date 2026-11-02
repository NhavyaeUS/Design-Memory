"""Health endpoint — Milestone 1A.2."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """
    Returns a simple JSON health status.

    Useful for:
    - Confirming the backend is running before the frontend makes other requests.
    - Automated monitoring or smoke-tests.
    - FastAPI's interactive docs show it as the first endpoint.
    """
    return HealthResponse(
        status="ok",
        service="design-memory",
        version="0.1.0",
    )
