"""
Comprehensive tests for Milestone 1B.2: Safe webpage metadata extraction.

Validates:
- SSRF prevention (IP checks, blocked hostnames, private/loopback/cloud metadata IP blocking).
- HTML metadata parsing (title, OpenGraph, Twitter card, description, favicon relative resolution, HTML entity unescaping).
- Metadata extraction service limits (streaming byte limit, timeouts, non-HTML content, safe redirects).
- SSRF redirect interception (preventing open redirect to internal targets).
- Metadata API endpoints (GET and POST).
- Item creation fallback behavior when title is omitted.
"""
import socket
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.core.html_meta import extract_meta_from_html
from app.core.ssrf import (
    SSRFError,
    is_safe_ip,
    resolve_and_validate_host,
    validate_url_for_ssrf,
)
from app.services.metadata import (
    MAX_RESPONSE_BYTES,
    extract_metadata,
)


# ─── 1. SSRF Unit Tests ───────────────────────────────────────────────────────

def test_is_safe_ip():
    """Verify safe public IPs pass and unsafe/private/loopback/cloud IPs fail."""
    # Globally routable public IPs
    assert is_safe_ip("8.8.8.8") is True
    assert is_safe_ip("1.1.1.1") is True
    assert is_safe_ip("142.250.190.46") is True
    assert is_safe_ip("2607:f8b0:4005:805::200e") is True

    # Loopback
    assert is_safe_ip("127.0.0.1") is False
    assert is_safe_ip("127.0.1.1") is False
    assert is_safe_ip("::1") is False

    # Private RFC 1918
    assert is_safe_ip("10.0.0.1") is False
    assert is_safe_ip("172.16.0.1") is False
    assert is_safe_ip("172.31.255.255") is False
    assert is_safe_ip("192.168.1.1") is False
    assert is_safe_ip("fc00::1") is False

    # Link-local / AWS / GCP cloud metadata
    assert is_safe_ip("169.254.169.254") is False
    assert is_safe_ip("fe80::1") is False

    # Carrier Grade NAT (100.64.0.0/10)
    assert is_safe_ip("100.64.0.1") is False
    assert is_safe_ip("100.127.255.254") is False

    # Multicast & Unspecified
    assert is_safe_ip("224.0.0.1") is False
    assert is_safe_ip("0.0.0.0") is False
    assert is_safe_ip("::") is False

    # Invalid string
    assert is_safe_ip("not.an.ip") is False


def test_resolve_and_validate_host_blocks_restricted_hostnames():
    """Verify localhost, internal, and local suffixes are rejected."""
    for host in ["localhost", "foo.localhost", "printer.local", "db.internal", "server.corp"]:
        with pytest.raises(SSRFError, match="restricted"):
            resolve_and_validate_host(host)


def test_resolve_and_validate_host_blocks_ip_literals():
    """Verify IP literals are checked directly without DNS."""
    with pytest.raises(SSRFError, match="private or reserved"):
        resolve_and_validate_host("127.0.0.1")

    with pytest.raises(SSRFError, match="private or reserved"):
        resolve_and_validate_host("169.254.169.254")

    # Safe public IP literal passes
    res = resolve_and_validate_host("8.8.8.8")
    assert res == ["8.8.8.8"]


def test_resolve_and_validate_host_dns_resolution(monkeypatch):
    """Verify DNS resolution checks all returned addresses."""
    # Mock socket.getaddrinfo returning a private IP
    def mock_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 80))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    with pytest.raises(SSRFError, match="restricted IP address"):
        resolve_and_validate_host("evil.example.com")

    # Mock socket.getaddrinfo returning a public safe IP
    def mock_safe_addrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_safe_addrinfo)
    resolved = resolve_and_validate_host("safe.example.com")
    assert resolved == ["93.184.216.34"]


def test_validate_url_for_ssrf():
    """Verify validate_url_for_ssrf combines URL validation and host checks."""
    with pytest.raises(SSRFError):
        validate_url_for_ssrf("http://127.0.0.1:8000/secrets")

    with pytest.raises(SSRFError):
        validate_url_for_ssrf("http://localhost:3000")


# ─── 2. HTML Metadata Parser Tests ────────────────────────────────────────────

def test_html_meta_parser_basic():
    """Extract standard title, description, and relative favicon."""
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Brand Identity &amp; Typography &mdash; Studio</title>
        <meta name="description" content="Curated design references and type samples.">
        <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
      </head>
      <body><h1>Content</h1></body>
    </html>
    """
    meta = extract_meta_from_html(html, "https://studio.design/portfolio")
    assert meta.title == "Brand Identity & Typography — Studio"
    assert meta.description == "Curated design references and type samples."
    assert meta.favicon_url == "https://studio.design/assets/favicon.svg"


def test_html_meta_parser_opengraph_priority():
    """OpenGraph title and description take priority over standard HTML tags."""
    html = """
    <html>
      <head>
        <title>Generic HTML Page Title</title>
        <meta property="og:title" content="Rich OpenGraph Title">
        <meta name="description" content="Generic HTML description.">
        <meta property="og:description" content="Detailed OG description for social cards.">
        <meta property="og:image" content="/images/og-preview.png">
        <link rel="apple-touch-icon" href="/touch-icon.png">
      </head>
      <body></body>
    </html>
    """
    meta = extract_meta_from_html(html, "https://example.com/article")
    assert meta.title == "Rich OpenGraph Title"
    assert meta.description == "Detailed OG description for social cards."
    assert meta.image_url == "https://example.com/images/og-preview.png"
    assert meta.favicon_url == "https://example.com/touch-icon.png"


def test_html_meta_parser_fallback_favicon_to_origin():
    """When no link icon is specified, fall back to /favicon.ico at origin."""
    html = "<html><head><title>No Favicon Tag</title></head><body></body></html>"
    meta = extract_meta_from_html(html, "https://sub.domain.org/path/page.html")
    assert meta.title == "No Favicon Tag"
    assert meta.favicon_url == "https://sub.domain.org/favicon.ico"


def test_html_meta_parser_malformed_html():
    """Parser gracefully handles unclosed tags and messy HTML without throwing."""
    html = "<title>Unclosed Title Tag<p>Some text<meta name='description' content='Broken meta'"
    meta = extract_meta_from_html(html, "https://messy.org/")
    assert meta.title is not None
    assert "Unclosed" in meta.title


# ─── 3. Metadata Service Tests (with Mocks) ───────────────────────────────────

def test_extract_metadata_success():
    """Extract metadata using a mock httpx transport returning HTML."""
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Awwwards &mdash; Website Awards</title>
        <meta name="description" content="The awards for design, creativity and innovation on the Internet.">
        <link rel="icon" href="/favicon-32x32.png">
      </head>
      <body></body>
    </html>
    """

    def handle_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=html,
            headers={"Content-Type": "text/html; charset=utf-8"},
            request=request,
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handle_request))

    result = extract_metadata(
        "https://www.awwwards.com",
        client=mock_client,
        verify_ssrf=False,
    )
    assert result.success is True
    assert result.status == "success"
    assert "Awwwards" in result.title
    assert "creativity and innovation" in result.description
    assert result.favicon_url == "https://www.awwwards.com/favicon-32x32.png"
    assert result.domain == "awwwards.com"


def test_extract_metadata_ssrf_blocked():
    """SSRF target is blocked without initiating network request."""
    # localhost
    res_local = extract_metadata("http://localhost:8000/api/v1/items")
    assert res_local.success is False
    assert res_local.status == "fallback"
    assert "SSRF blocked" in (res_local.error or "")
    assert res_local.title == "Localhost"

    # 127.0.0.1
    res_loopback = extract_metadata("http://127.0.0.1:5432")
    assert res_loopback.success is False
    assert "SSRF blocked" in (res_loopback.error or "")

    # Cloud metadata
    res_cloud = extract_metadata("http://169.254.169.254/latest/meta-data/")
    assert res_cloud.success is False
    assert "SSRF blocked" in (res_cloud.error or "")


def test_extract_metadata_timeout_fallback():
    """Times out gracefully and provides domain-based fallback."""
    def timeout_request(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out")

    mock_client = httpx.Client(transport=httpx.MockTransport(timeout_request))

    result = extract_metadata(
        "https://slowsite.com/gallery",
        client=mock_client,
        verify_ssrf=False,
    )
    assert result.success is False
    assert result.status == "fallback"
    assert "timed out" in (result.error or "")
    assert result.title == "Slowsite.com"
    assert result.favicon_url == "https://slowsite.com/favicon.ico"


def test_extract_metadata_non_html_content_type():
    """Non-HTML content (e.g. PDF download) falls back gracefully."""
    def pdf_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"%PDF-1.4 ...",
            headers={"Content-Type": "application/pdf"},
            request=request,
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(pdf_request))

    result = extract_metadata(
        "https://example.com/whitepaper.pdf",
        client=mock_client,
        verify_ssrf=False,
    )
    assert result.success is False
    assert result.status == "fallback"
    assert "Non-HTML" in (result.error or "")
    assert result.title == "Example.com"


def test_extract_metadata_streaming_byte_limit():
    """Response larger than 1MB is safely capped without memory blowup."""
    # Generate 1.5 MB of repeating HTML content
    large_html = "<html><head><title>Large Page</title></head><body>" + ("x" * (1500 * 1024)) + "</body></html>"

    def large_request(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=large_html,
            headers={"Content-Type": "text/html"},
            request=request,
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(large_request))

    result = extract_metadata(
        "https://largepage.com",
        client=mock_client,
        verify_ssrf=False,
    )
    assert result.success is True
    assert result.title == "Large Page"


def test_extract_metadata_safe_redirect():
    """Redirect to safe URL is followed and metadata extracted."""
    def redirect_flow(request: httpx.Request) -> httpx.Response:
        if request.url == "http://example.com/short":
            return httpx.Response(
                301,
                headers={"Location": "https://example.com/full-article"},
                request=request,
            )
        return httpx.Response(
            200,
            text="<html><head><title>Full Article Destination</title></head><body></body></html>",
            headers={"Content-Type": "text/html"},
            request=request,
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(redirect_flow))

    result = extract_metadata(
        "http://example.com/short",
        client=mock_client,
        verify_ssrf=False,
    )
    assert result.success is True
    assert result.title == "Full Article Destination"
    assert result.url == "https://example.com/full-article"


def test_extract_metadata_ssrf_redirect_blocked():
    """Redirect pointing to private internal target is blocked."""
    def evil_redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1:8000/admin"},
            request=request,
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(evil_redirect))

    result = extract_metadata(
        "https://public.example.com/open-redirect",
        client=mock_client,
        verify_ssrf=True,
    )
    # The first URL public.example.com would normally be checked via DNS.
    # If the redirect location is 127.0.0.1, it gets caught by SSRF check!
    assert result.success is False
    assert result.status == "fallback"


# ─── 4. FastAPI Endpoints Integration Tests ───────────────────────────────────

def test_api_metadata_extract_post_and_get(client):
    """Test POST and GET /api/v1/metadata/extract endpoints."""
    # Test POST with blocked SSRF URL -> returns 200 with fallback status
    resp = client.post("/api/v1/metadata/extract", json={"url": "http://127.0.0.1:8000"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["status"] == "fallback"
    assert "SSRF blocked" in data["error"]
    assert data["title"] == "127.0.0.1"

    # Test GET variant
    resp_get = client.get("/api/v1/metadata/extract", params={"url": "http://localhost:3000"})
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["success"] is False
    assert data_get["status"] == "fallback"
    assert data_get["title"] == "Localhost"


def test_create_item_with_omitted_title_uses_metadata_fallback(client, db, monkeypatch):
    """Creating an item with URL but without title automatically resolves title."""
    from app.services import metadata as meta_mod

    def mock_extract(url):
        return meta_mod.MetadataResult(
            url=url,
            domain="fontsinuse.com",
            title="Fonts In Use – Archive of Typography",
            description="A searchable archive of typographic design.",
            favicon_url="https://fontsinuse.com/favicon.ico",
            image_url=None,
            success=True,
            status="success",
        )

    monkeypatch.setattr(meta_mod, "extract_metadata", mock_extract)

    payload = {
        "url": "https://fontsinuse.com/typefaces/1234/helvetica",
        "resource_type": "type",
        "force": True,
    }
    resp = client.post("/api/v1/items", json=payload)
    assert resp.status_code == 201
    item = resp.json()
    assert item["title"] == "fontsinuse.com"
    assert item["analysis_status"] == "pending"

    # Process background analysis using the test database session
    from app.services.analysis import run_item_analysis_sync
    import app.services.analysis as analysis_mod
    monkeypatch.setattr(analysis_mod, "extract_metadata", mock_extract)
    run_item_analysis_sync(item["id"], db=db)

    updated = client.get(f"/api/v1/items/{item['id']}").json()
    assert updated["title"] == "Fonts In Use – Archive of Typography"
    assert updated["analysis_status"] == "completed"


def test_user_supplied_title_and_notes_are_never_overwritten(client):
    """Explicit user title and notes are strictly preserved, not overwritten."""
    payload = {
        "title": "My Custom Title For Site",
        "url": "https://custom-site.org/home",
        "notes": "My personal curated notes",
        "reason_for_saving": "Super inspiring layout",
        "resource_type": "website",
        "force": True,
    }
    resp = client.post("/api/v1/items", json=payload)
    assert resp.status_code == 201
    item = resp.json()
    assert item["title"] == "My Custom Title For Site"
    assert item["notes"] == "My personal curated notes"
    assert item["reason_for_saving"] == "Super inspiring layout"


def test_ssrf_safe_transport_dns_rebinding_defense():
    """Verify SSRFSafeTransport blocks connection if peer IP is private/loopback."""
    from app.core.ssrf import SSRFSafeTransport, SSRFError

    transport = SSRFSafeTransport()
    # Connecting to 127.0.0.1 directly triggers the socket peer check
    with httpx.Client(transport=transport) as safe_client:
        with pytest.raises(SSRFError, match="DNS rebinding blocked"):
            safe_client.get("http://127.0.0.1:8000")

