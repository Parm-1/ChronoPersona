"""Explicit, bounded network access for metadata-only source adapters."""

from __future__ import annotations

from collections.abc import Sequence
import math
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)


class MetadataNetworkError(RuntimeError):
    """Raised when a bounded metadata request cannot be completed safely."""


def _allowed_host_set(allowed_hosts: Sequence[str]) -> frozenset[str]:
    if isinstance(allowed_hosts, (str, bytes)) or not isinstance(
        allowed_hosts,
        Sequence,
    ):
        raise MetadataNetworkError("allowed_hosts must be a host-name sequence")
    normalized: set[str] = set()
    for host in allowed_hosts:
        if (
            not isinstance(host, str)
            or not host
            or host != host.strip()
            or ":" in host
            or "/" in host
            or "*" in host
        ):
            raise MetadataNetworkError(
                "allowed_hosts must contain exact host names without ports"
            )
        normalized.add(host.casefold())
    if not normalized:
        raise MetadataNetworkError("allowed_hosts must not be empty")
    return frozenset(normalized)


def _validate_metadata_url(url: str, *, allowed_hosts: frozenset[str]) -> str:
    if not isinstance(url, str) or not url or url != url.strip():
        raise MetadataNetworkError("metadata URL must be a nonempty string")
    if any(ord(character) < 32 for character in url):
        raise MetadataNetworkError("metadata URL must not contain control characters")
    parsed = urlsplit(url)
    if parsed.scheme.casefold() != "https":
        raise MetadataNetworkError("metadata URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise MetadataNetworkError("metadata URL must not contain credentials")
    try:
        port = parsed.port
    except ValueError as error:
        raise MetadataNetworkError("metadata URL has an invalid port") from error
    if port not in (None, 443):
        raise MetadataNetworkError("metadata URL must use the default HTTPS port")
    host = parsed.hostname.casefold() if parsed.hostname is not None else ""
    if host not in allowed_hosts:
        raise MetadataNetworkError(
            f"metadata URL host {host!r} is not in the exact allowlist"
        )
    if parsed.fragment:
        raise MetadataNetworkError("metadata URL must not contain a fragment")
    return url


class _AllowlistedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        super().__init__()
        self._allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urljoin(req.full_url, newurl)
        _validate_metadata_url(target, allowed_hosts=self._allowed_hosts)
        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            target,
        )


def fetch_metadata(
    url: str,
    *,
    allow_network: bool,
    allowed_hosts: Sequence[str],
    max_bytes: int,
    timeout_seconds: float,
    user_agent: str,
    delay_seconds: float = 0.0,
) -> bytes:
    """Fetch one allowlisted HTTPS metadata response after authorization."""

    if not allow_network:
        raise MetadataNetworkError(
            "network access is disabled; pass the explicit live-execution flag"
        )
    hosts = _allowed_host_set(allowed_hosts)
    _validate_metadata_url(url, allowed_hosts=hosts)
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise MetadataNetworkError("max_bytes must be a positive integer")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or timeout_seconds <= 0
    ):
        raise MetadataNetworkError("timeout_seconds must be finite and positive")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise MetadataNetworkError("user_agent must not be empty")
    if (
        isinstance(delay_seconds, bool)
        or not isinstance(delay_seconds, (int, float))
        or not math.isfinite(float(delay_seconds))
        or delay_seconds < 0
    ):
        raise MetadataNetworkError(
            "delay_seconds must be finite and not negative"
        )
    if delay_seconds:
        time.sleep(float(delay_seconds))

    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json, application/xml, text/xml;q=0.9, */*;q=0.1",
        },
    )
    opener = build_opener(_AllowlistedRedirectHandler(hosts))
    try:
        with opener.open(request, timeout=float(timeout_seconds)) as response:
            _validate_metadata_url(response.geturl(), allowed_hosts=hosts)
            raw_length = response.headers.get("Content-Length")
            if raw_length is not None:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    content_length = None
                if content_length is not None and content_length > max_bytes:
                    raise MetadataNetworkError(
                        f"metadata response declares {content_length} bytes, "
                        f"exceeding max_bytes={max_bytes}"
                    )
            payload = response.read(max_bytes + 1)
    except MetadataNetworkError:
        raise
    except Exception as error:
        raise MetadataNetworkError(f"metadata request failed: {error}") from error

    if len(payload) > max_bytes:
        raise MetadataNetworkError(
            f"metadata response exceeded max_bytes={max_bytes}"
        )
    return payload
