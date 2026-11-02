"""
URL validation and normalization utilities — Milestone 1B.1.

Requirements:
- Accept valid HTTP and HTTPS URLs only.
- Reject missing schemes, unsupported schemes (ftp, javascript, data, file, etc.), and malformed URLs.
- Normalize URLs consistently for duplicate detection without merging distinct paths.
- Extract clean display domain (stripping leading 'www.').
- Filter out tracking query parameters (utm_*, fbclid, etc.) from normalized duplicate checks.
"""
from typing import Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ALLOWED_SCHEMES = {"http", "https"}

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "source",
}


class URLValidationError(ValueError):
    """Raised when a URL fails scheme or structural validation."""
    pass


def validate_url(url: str) -> None:
    """
    Validate that the URL string has a supported scheme (http or https) and a valid host.
    Raises URLValidationError with a helpful user-facing message if invalid.
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL cannot be empty.")

    url_clean = url.strip()
    if not url_clean:
        raise URLValidationError("URL cannot be empty.")

    try:
        parsed = urlparse(url_clean)
    except Exception as e:
        raise URLValidationError(f"Malformed URL: {e}") from e

    # Determine scheme
    scheme = parsed.scheme.lower() if parsed.scheme else ""
    if not scheme:
        raise URLValidationError("Missing URL scheme. URL must start with http:// or https://")

    if scheme not in ALLOWED_SCHEMES:
        raise URLValidationError(
            f"Unsupported scheme '{parsed.scheme}'. Only http:// and https:// URLs are supported."
        )

    # Must have :// after scheme
    if not url_clean.lower().startswith((f"{scheme}://")):
        raise URLValidationError("Malformed URL: scheme must be followed by '://'")

    # Disallow embedded credentials (username/password)
    if parsed.username or parsed.password:
        raise URLValidationError("URLs containing embedded credentials are not permitted.")

    host = parsed.hostname
    if not host:
        raise URLValidationError("Malformed URL: missing hostname.")

    # Basic hostname checks: no spaces, at least one dot or localhost
    if " " in host or "\t" in host or "\n" in host:
        raise URLValidationError("Malformed URL: hostname contains invalid whitespace.")

    if "." not in host and host != "localhost":
        raise URLValidationError(f"Malformed hostname '{host}'. Must contain a valid domain.")


def extract_domain(url: str) -> str:
    """Extract clean display domain without 'www.' prefix."""
    try:
        parsed = urlparse(url.strip())
        host = parsed.hostname or ""
        return host.lower().removeprefix("www.")
    except Exception:
        return ""


def normalize_url(url: str) -> str:
    """
    Normalize a URL for reliable duplicate detection:
    - Lowercase scheme and hostname.
    - Remove default ports (:80 for http, :443 for https).
    - Strip fragment identifiers.
    - Remove tracking query parameters (utm_*, etc.) and sort remaining query params.
    - Remove trailing slash from root path (https://example.com/ -> https://example.com).
    - Collapse redundant multiple slashes in path.
    """
    validate_url(url)
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()

    # Port normalization
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    netloc = f"{host}:{port}" if port else host

    # Path normalization
    path = parsed.path or ""
    # Collapse double slashes
    while "//" in path:
        path = path.replace("//", "/")
    # Strip trailing slash if path is longer than 1 char or if root slash
    if path == "/":
        path = ""
    elif path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")

    # Query normalization: remove tracking params and sort
    filtered_query = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        if k.lower() not in TRACKING_PARAMS:
            filtered_query.append((k, v))
    filtered_query.sort()
    query_str = urlencode(filtered_query)

    # Fragment is stripped for duplicate comparison
    return urlunparse((scheme, netloc, path, "", query_str, ""))
