"""
Safe metadata extraction service — Milestone 1B.2.

Features:
- SSRF protection on initial request and every subsequent redirect hop.
- Strict connection (3s) and read (5s) timeouts.
- Response body limit enforcement (1MB max streamed) to prevent memory exhaustion.
- Re-direction loop with SSRF checks on every intermediate destination.
- Graceful fallback to domain/URL when metadata cannot be retrieved or parsed.
- Dependency injection friendly for testing without live network calls.
"""
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse
import httpx

from app.core.html_meta import extract_meta_from_html
from app.core.ssrf import SSRFError, resolve_and_validate_host
from app.core.urls import extract_domain, validate_url, URLValidationError


# Limits
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 1024 * 1024  # 1 MB
CONNECT_TIMEOUT_SECS = 3.0
READ_TIMEOUT_SECS = 5.0

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
    "(compatible; DesignMemory/1.0)"
)


@dataclass
class MetadataResult:
    """Result of metadata extraction."""
    url: str
    domain: str
    title: str
    description: Optional[str]
    favicon_url: Optional[str]
    image_url: Optional[str]
    success: bool
    status: str
    error: Optional[str] = None


def _format_fallback_title(url: str, domain: str) -> str:
    """Generate a clean user-friendly fallback title from domain or URL path."""
    if domain:
        # e.g., 'github.com' -> 'Github.com'
        parts = domain.split(".")
        if len(parts) >= 2:
            return parts[0].capitalize() + "." + ".".join(parts[1:])
        return domain.capitalize()
    return url


def _make_fallback_result(url: str, error: str) -> MetadataResult:
    """Create a safe fallback result when extraction fails or is blocked."""
    domain = extract_domain(url)
    fallback_title = _format_fallback_title(url, domain)

    fallback_favicon = None
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            fallback_favicon = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
    except Exception:
        pass

    return MetadataResult(
        url=url,
        domain=domain,
        title=fallback_title,
        description=None,
        favicon_url=fallback_favicon,
        image_url=None,
        success=False,
        status="fallback",
        error=error,
    )


def extract_metadata(
    url: str,
    *,
    client: Optional[httpx.Client] = None,
    verify_ssrf: bool = True,
) -> MetadataResult:
    """
    Safely extract title, description, favicon, and image from a webpage URL.

    Guarantees:
    - Never raises unhandled exceptions to callers.
    - SSRF protection stops private/local IP targets.
    - Limits response size and enforces strict timeouts.
    - Returns a valid MetadataResult even on failure (fallback status).
    """
    # 1. URL syntax validation
    try:
        validate_url(url)
    except URLValidationError as e:
        return _make_fallback_result(url, f"Invalid URL: {e}")

    current_url = url.strip()
    domain = extract_domain(current_url)

    # 2. SSRF check on initial target
    if verify_ssrf:
        try:
            parsed = urlparse(current_url)
            host = parsed.hostname or ""
            resolve_and_validate_host(host)
        except SSRFError as e:
            return _make_fallback_result(url, f"SSRF blocked: {e}")
        except Exception as e:
            return _make_fallback_result(url, f"Host validation failed: {e}")

    # 3. HTTP fetch with redirects and stream limits
    timeout = httpx.Timeout(
        connect=CONNECT_TIMEOUT_SECS,
        read=READ_TIMEOUT_SECS,
        write=5.0,
        pool=5.0,
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    own_client = False
    if client is None:
        client = httpx.Client(timeout=timeout, verify=True)
        own_client = True

    try:
        redirect_count = 0
        final_response = None
        html_content = ""

        while redirect_count <= MAX_REDIRECTS:
            # Stream request to enforce byte limit
            with client.stream(
                "GET",
                current_url,
                headers=headers,
                follow_redirects=False,
            ) as response:
                # Handle HTTP redirects safely
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        return _make_fallback_result(url, "Redirect missing Location header")

                    redirect_count += 1
                    if redirect_count > MAX_REDIRECTS:
                        return _make_fallback_result(url, f"Exceeded max redirects ({MAX_REDIRECTS})")

                    new_url = urljoin(current_url, location)
                    try:
                        validate_url(new_url)
                    except URLValidationError as e:
                        return _make_fallback_result(url, f"Redirect to invalid URL: {e}")

                    if verify_ssrf:
                        try:
                            parsed_next = urlparse(new_url)
                            next_host = parsed_next.hostname or ""
                            resolve_and_validate_host(next_host)
                        except SSRFError as e:
                            return _make_fallback_result(url, f"Redirect SSRF blocked: {e}")

                    current_url = new_url
                    continue

                if response.status_code >= 400:
                    return _make_fallback_result(
                        url, f"HTTP {response.status_code} {response.reason_phrase}"
                    )

                # Check Content-Type
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    # Non-HTML content (e.g. image, PDF); return fallback
                    return _make_fallback_result(
                        url, f"Non-HTML content type: {content_type}"
                    )

                # Read body in chunks up to MAX_RESPONSE_BYTES
                chunks = []
                total_bytes = 0
                for chunk in response.iter_bytes(chunk_size=8192):
                    chunks.append(chunk)
                    total_bytes += len(chunk)
                    if total_bytes >= MAX_RESPONSE_BYTES:
                        break

                raw_bytes = b"".join(chunks)
                # Decode using response encoding or fallback to utf-8
                encoding = response.encoding or "utf-8"
                html_content = raw_bytes.decode(encoding, errors="replace")
                final_response = response
                break

        if not html_content:
            return _make_fallback_result(url, "Empty response body")

        # 4. Extract metadata from HTML
        extracted = extract_meta_from_html(html_content, base_url=current_url)

        title = extracted.title or _format_fallback_title(url, domain)
        return MetadataResult(
            url=current_url,
            domain=extract_domain(current_url) or domain,
            title=title,
            description=extracted.description,
            favicon_url=extracted.favicon_url,
            image_url=extracted.image_url,
            success=True,
            status="success",
            error=None,
        )

    except httpx.TimeoutException as e:
        return _make_fallback_result(url, f"Request timed out: {e}")
    except httpx.RequestError as e:
        return _make_fallback_result(url, f"Network request error: {e}")
    except Exception as e:
        return _make_fallback_result(url, f"Metadata extraction failed: {e}")
    finally:
        if own_client:
            client.close()
