"""
SSRF (Server-Side Request Forgery) protection utilities — Milestone 1B.2.

Safeguards against internal network scanning, loopback access, link-local metadata
endpoints (e.g. AWS/GCP 169.254.169.254), and private intranet resources.
"""
import ipaddress
import socket
from typing import List, Optional
from urllib.parse import urlparse

from app.core.urls import validate_url, URLValidationError


class SSRFError(Exception):
    """Raised when a URL or resolved IP target violates SSRF security boundaries."""
    pass


# Prohibited host suffixes
BLOCKED_HOST_SUFFIXES = (
    "localhost",
    ".localhost",
    ".local",
    ".internal",
    ".localdomain",
    ".corp",
    ".home",
    ".lan",
    ".arpa",
)

# Shared Address Space / Carrier Grade NAT (RFC 6598: 100.64.0.0/10)
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def is_safe_ip(ip_str: str) -> bool:
    """
    Check if an IPv4 or IPv6 string is safe for outbound server requests.
    Returns False for loopback, private, link-local, multicast, CGNAT, or unspecified IPs.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if ip.is_loopback:
        return False
    if ip.is_private:
        return False
    if ip.is_link_local:
        return False
    if ip.is_multicast:
        return False
    if ip.is_reserved:
        return False
    if ip.is_unspecified:
        return False
    if not ip.is_global:
        return False

    # Explicit check for CGNAT (100.64.0.0/10)
    if ip.version == 4 and ip in CGNAT_NETWORK:
        return False

    return True


def resolve_and_validate_host(host: str) -> List[str]:
    """
    Resolve host via DNS and verify that every resolved IP address is globally routable.
    Raises SSRFError if the host resolves to any private, loopback, or non-global IP.
    """
    if not host or not isinstance(host, str):
        raise SSRFError("Host cannot be empty.")

    clean_host = host.strip().lower()
    # Strip brackets for IPv6 literals
    clean_host = clean_host.removeprefix("[").removesuffix("]")

    # Check prohibited suffix/hostname
    if clean_host == "localhost" or any(clean_host.endswith(sfx) for sfx in BLOCKED_HOST_SUFFIXES):
        raise SSRFError(f"Host '{host}' is restricted and cannot be requested.")

    # Check if host is already an IP address
    parsed_ip = None
    try:
        parsed_ip = ipaddress.ip_address(clean_host)
    except ValueError:
        pass

    if parsed_ip is not None:
        if not is_safe_ip(clean_host):
            raise SSRFError(f"IP address '{clean_host}' is private or reserved.")
        return [str(parsed_ip)]

    try:
        # Resolve both IPv4 and IPv6 addresses
        addr_infos = socket.getaddrinfo(
            clean_host,
            None,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as e:
        raise SSRFError(f"Failed to resolve host '{host}': {e}") from e
    except Exception as e:
        raise SSRFError(f"DNS resolution error for host '{host}': {e}") from e

    if not addr_infos:
        raise SSRFError(f"No IP addresses resolved for host '{host}'.")

    resolved_ips: List[str] = []
    for info in addr_infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        if ip_str not in resolved_ips:
            resolved_ips.append(ip_str)

    # Every resolved IP address must be safe
    for ip_str in resolved_ips:
        if not is_safe_ip(ip_str):
            raise SSRFError(
                f"Host '{host}' resolved to restricted IP address '{ip_str}'."
            )

    return resolved_ips


def validate_url_for_ssrf(url: str) -> None:
    """
    Validate both URL scheme/structure and ensure destination host is safe against SSRF.
    Raises URLValidationError or SSRFError if invalid or unsafe.
    """
    validate_url(url)
    parsed = urlparse(url.strip())
    host = parsed.hostname
    if not host:
        raise SSRFError("URL is missing a valid hostname.")
    resolve_and_validate_host(host)


# ─── DNS Rebinding / Post-Connect Enforcement ────────────────────────────────

import httpcore
import httpx


class SSRFSafeSyncBackend(httpcore.SyncBackend):
    """
    Custom network backend that intercepts socket creation after connect()
    to verify the actual peer IP address. Defends against DNS rebinding / TOCTOU
    where DNS resolution shifts to a private IP between check and connect.
    """
    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options=None,
    ):
        stream = super().connect_tcp(host, port, timeout, local_address, socket_options)
        try:
            peer_ip = stream._sock.getpeername()[0]
        except Exception as e:
            stream._sock.close()
            raise SSRFError(f"Failed to inspect peer IP: {e}") from e

        if not is_safe_ip(peer_ip):
            stream._sock.close()
            raise SSRFError(
                f"DNS rebinding blocked: connected peer '{peer_ip}' is private or reserved."
            )
        return stream


class SSRFSafeTransport(httpx.HTTPTransport):
    """HTTPX Transport powered by SSRFSafeSyncBackend for peer IP enforcement."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pool = httpcore.ConnectionPool(
            network_backend=SSRFSafeSyncBackend(),
            ssl_context=getattr(self, "_pool", None) and getattr(self._pool, "_ssl_context", None),
        )

