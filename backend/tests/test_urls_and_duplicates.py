"""
Tests for Milestone 1B.1 — URL validation and duplicate handling.
"""
import pytest
from app.core.urls import normalize_url, validate_url, URLValidationError


# ─── Pure Unit Tests for URL Validation & Normalization ───────────────────────

def test_validate_url_valid_http_and_https():
    """Valid http and https URLs pass validation."""
    validate_url("http://example.com")
    validate_url("https://studio-ono.design/case-studies/branding?ref=test#section")
    validate_url("https://sub.domain.co.uk:8080/path")


def test_validate_url_missing_scheme():
    """Missing scheme must raise URLValidationError."""
    with pytest.raises(URLValidationError, match="Missing URL scheme"):
        validate_url("example.com")
    with pytest.raises(URLValidationError, match="Missing URL scheme"):
        validate_url("www.example.com/page")


def test_validate_url_unsupported_schemes():
    """Unsupported schemes like ftp, javascript, file, data must be rejected."""
    for bad_url in [
        "ftp://files.example.com/doc.pdf",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,<h1>test</h1>",
        "ws://echo.websocket.org",
    ]:
        with pytest.raises(URLValidationError, match="Unsupported scheme"):
            validate_url(bad_url)


def test_validate_url_malformed():
    """Malformed URLs with missing or invalid hosts must be rejected."""
    with pytest.raises(URLValidationError, match="hostname"):
        validate_url("http://")
    with pytest.raises(URLValidationError, match="hostname"):
        validate_url("https://   /path")
    with pytest.raises(URLValidationError, match="hostname"):
        validate_url("https://nodots")


def test_normalize_url_removes_tracking_and_fragment():
    """Normalization strips tracking params, fragments, and trailing slashes."""
    url1 = "https://example.com/portfolio/?utm_source=twitter&utm_medium=social#hero"
    url2 = "https://example.com/portfolio"
    assert normalize_url(url1) == "https://example.com/portfolio"
    assert normalize_url(url2) == "https://example.com/portfolio"


def test_normalize_url_preserves_distinct_paths():
    """Distinct paths on the same domain are not merged."""
    u1 = normalize_url("https://example.com/work/project-a")
    u2 = normalize_url("https://example.com/work/project-b")
    assert u1 != u2


# ─── API Integration Tests for Add Resource & Duplicates ───────────────────────

def test_api_create_item_valid_urls(client):
    """API accepts valid http and https URLs and saves them."""
    res_http = client.post("/api/v1/items", json={
        "title": "HTTP Resource",
        "url": "http://http-reference.org/layout",
        "resource_type": "website",
        "color": "#AABBCC",
    })
    assert res_http.status_code == 201
    data_http = res_http.json()
    assert data_http["url"] == "http://http-reference.org/layout"
    assert data_http["domain"] == "http-reference.org"
    assert data_http["normalized_url"] == "http://http-reference.org/layout"

    res_https = client.post("/api/v1/items", json={
        "title": "HTTPS Resource",
        "url": "https://https-reference.org/case-study",
        "resource_type": "website",
        "color": "#112233",
    })
    assert res_https.status_code == 201
    data_https = res_https.json()
    assert data_https["url"] == "https://https-reference.org/case-study"
    assert data_https["domain"] == "https-reference.org"


def test_api_create_item_rejects_missing_and_unsupported_schemes(client):
    """API returns 422 with validation errors for invalid URL schemes."""
    # Missing scheme
    res1 = client.post("/api/v1/items", json={
        "title": "No Scheme",
        "url": "noscheme.com/page",
        "resource_type": "website",
        "color": "#112233",
    })
    assert res1.status_code == 422
    assert "Missing URL scheme" in res1.text

    # FTP scheme
    res2 = client.post("/api/v1/items", json={
        "title": "FTP URL",
        "url": "ftp://ftp.example.com",
        "resource_type": "website",
        "color": "#112233",
    })
    assert res2.status_code == 422
    assert "Unsupported scheme" in res2.text

    # Javascript scheme
    res3 = client.post("/api/v1/items", json={
        "title": "XSS URL",
        "url": "javascript:void(0)",
        "resource_type": "website",
        "color": "#112233",
    })
    assert res3.status_code == 422


def test_api_exact_duplicate_url_rejected_with_409(client):
    """Attempting to add an existing URL without force flag returns 409 Conflict."""
    first = client.post("/api/v1/items", json={
        "title": "Original Resource",
        "url": "https://duplicate-test.com/design",
        "resource_type": "website",
        "color": "#112233",
        "notes": "Custom user notes that must be preserved",
    })
    assert first.status_code == 201
    item_id = first.json()["id"]

    # Same URL with trailing slash and utm params should be detected as exact duplicate
    second = client.post("/api/v1/items", json={
        "title": "Second Attempt",
        "url": "https://duplicate-test.com/design/?utm_source=newsletter#top",
        "resource_type": "website",
        "color": "#999999",
    })
    assert second.status_code == 409
    err = second.json()["detail"]
    assert err["is_exact_match"] is True
    assert err["existing_item_id"] == item_id

    # Verify original item was NOT overwritten
    original = client.get(f"/api/v1/items/{item_id}").json()
    assert original["title"] == "Original Resource"
    assert original["notes"] == "Custom user notes that must be preserved"


def test_api_domain_duplicate_warning_with_different_paths(client):
    """Different path on same domain triggers 409 domain duplicate warning."""
    first = client.post("/api/v1/items", json={
        "title": "Home Page",
        "url": "https://shared-domain.com",
        "resource_type": "website",
        "color": "#112233",
    })
    assert first.status_code == 201

    # Different path on same domain
    second = client.post("/api/v1/items", json={
        "title": "About Page",
        "url": "https://shared-domain.com/about",
        "resource_type": "website",
        "color": "#223344",
    })
    assert second.status_code == 409
    err = second.json()["detail"]
    assert err["is_exact_match"] is False
    assert err["domain"] == "shared-domain.com"


def test_api_explicit_save_anyway_bypasses_duplicate(client):
    """When force=True is provided, duplicate check is bypassed and resource is created."""
    first = client.post("/api/v1/items", json={
        "title": "Domain Resource 1",
        "url": "https://force-save.com/item1",
        "resource_type": "website",
        "color": "#112233",
    })
    assert first.status_code == 201

    # Same domain with force=True succeeds
    forced = client.post("/api/v1/items", json={
        "title": "Domain Resource 2 (Forced)",
        "url": "https://force-save.com/item2",
        "resource_type": "website",
        "color": "#334455",
        "force": True,
    })
    assert forced.status_code == 201
    assert forced.json()["title"] == "Domain Resource 2 (Forced)"


def test_api_check_duplicate_endpoint(client):
    """GET /api/v1/items/check/duplicate returns exact and domain match metadata."""
    client.post("/api/v1/items", json={
        "title": "Existing Site",
        "url": "https://check-site.com/gallery",
        "resource_type": "website",
        "color": "#556677",
    })

    # Exact URL match (with tracking params stripped)
    res_exact = client.get("/api/v1/items/check/duplicate?target=https://check-site.com/gallery?utm_medium=cpc")
    assert res_exact.status_code == 200
    data_exact = res_exact.json()
    assert data_exact["is_duplicate"] is True
    assert data_exact["is_exact_match"] is True
    assert data_exact["existing_item"]["title"] == "Existing Site"

    # Domain match only (different path)
    res_dom = client.get("/api/v1/items/check/duplicate?target=https://check-site.com/pricing")
    assert res_dom.status_code == 200
    data_dom = res_dom.json()
    assert data_dom["is_duplicate"] is True
    assert data_dom["is_exact_match"] is False

    # Plain domain string match
    res_plain = client.get("/api/v1/items/check/duplicate?target=check-site.com")
    assert res_plain.status_code == 200
    assert res_plain.json()["is_duplicate"] is True

    # No match
    res_none = client.get("/api/v1/items/check/duplicate?target=https://unique-new-site.org")
    assert res_none.status_code == 200
    assert res_none.json()["is_duplicate"] is False
    assert res_none.json()["existing_item"] is None


def test_validate_url_rejects_embedded_credentials():
    """URLs containing username/password credentials must be rejected."""
    with pytest.raises(URLValidationError, match="embedded credentials"):
        validate_url("https://admin:secret123@example.com/dashboard")

    with pytest.raises(URLValidationError, match="embedded credentials"):
        validate_url("http://user@internal.org")


def test_repeated_submission_does_not_create_duplicates(client):
    """Repeated or concurrent submissions of the same URL do not create duplicate rows."""
    payload = {
        "title": "Concurrent Target",
        "url": "https://concurrent.example.com",
        "resource_type": "website",
        "color": "#778899",
    }

    # First attempt succeeds
    res1 = client.post("/api/v1/items", json=payload)
    assert res1.status_code == 201

    # Second identical attempt fails with 409
    res2 = client.post("/api/v1/items", json=payload)
    assert res2.status_code == 409

    # Third identical attempt fails with 409
    res3 = client.post("/api/v1/items", json=payload)
    assert res3.status_code == 409

    # Verify only 1 item exists for this domain
    items = client.get("/api/v1/items?q=concurrent").json()
    assert len(items) == 1
