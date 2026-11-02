"""Tests for GET /api/v1/health — Milestone 1A.2."""


def test_health_returns_200(client):
    """The health endpoint must return HTTP 200."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_returns_json(client):
    """The response must be valid JSON."""
    response = client.get("/api/v1/health")
    data = response.json()  # raises ValueError if not valid JSON
    assert isinstance(data, dict)


def test_health_fields(client):
    """The expected fields must be present and correct."""
    data = client.get("/api/v1/health").json()
    assert data["status"] == "ok"
    assert data["service"] == "design-memory"
    assert "version" in data


def test_unknown_route_returns_404(client):
    """An unknown API path must return 404, not 500."""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
