"""Explicit, bounded network access for metadata-only source adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from ..source_audit import MetadataTransportError


class MetadataNetworkError(MetadataTransportError):
    """Raised when a bounded metadata request cannot be completed safely."""


@dataclass(frozen=True)
class MetadataResponse:
    """One bounded response plus the transport identity used by evidence gates."""

    payload: bytes
    requested_url: str
    final_url: str
    status: int
    content_type: str | None


def _allowed_host_set(allowed_hosts: Sequence[str]) -> frozenset[str]:
    if isinstance(allowed_hosts, (str, bytes)) or not isinstance(
        allowed_hosts,
        Sequence,
    ):
        raise MetadataNetworkError(
            "allowed_hosts must be a host-name sequence",
            subtype="request-policy",
        )
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
                "allowed_hosts must contain exact host names without ports",
                subtype="request-policy",
            )
        normalized.add(host.casefold())
    if not normalized:
        raise MetadataNetworkError(
            "allowed_hosts must not be empty", subtype="request-policy"
        )
    return frozenset(normalized)


def _validate_metadata_url(url: str, *, allowed_hosts: frozenset[str]) -> str:
    if not isinstance(url, str) or not url or url != url.strip():
        raise MetadataNetworkError(
            "metadata URL must be a nonempty string", subtype="request-policy"
        )
    if any(ord(character) < 32 for character in url):
        raise MetadataNetworkError(
            "metadata URL must not contain control characters",
            subtype="request-policy",
        )
    parsed = urlsplit(url)
    if parsed.scheme.casefold() != "https":
        raise MetadataNetworkError(
            "metadata URL must use HTTPS", subtype="request-policy"
        )
    if parsed.username is not None or parsed.password is not None:
        raise MetadataNetworkError(
            "metadata URL must not contain credentials", subtype="request-policy"
        )
    try:
        port = parsed.port
    except ValueError as error:
        raise MetadataNetworkError(
            "metadata URL has an invalid port", subtype="request-policy"
        ) from error
    if port not in (None, 443):
        raise MetadataNetworkError(
            "metadata URL must use the default HTTPS port",
            subtype="request-policy",
        )
    host = parsed.hostname.casefold() if parsed.hostname is not None else ""
    if host not in allowed_hosts:
        raise MetadataNetworkError(
            f"metadata URL host {host!r} is not in the exact allowlist",
            subtype="request-policy",
        )
    if parsed.fragment:
        raise MetadataNetworkError(
            "metadata URL must not contain a fragment", subtype="request-policy"
        )
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


class _RejectRedirectHandler(HTTPRedirectHandler):
    """Reject redirects after the original bounded request is consumed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MetadataNetworkError(
            f"metadata response redirect is not permitted: HTTP {code}",
            subtype="redirect",
        )


def fetch_metadata_response(
    url: str,
    *,
    allow_network: bool,
    allowed_hosts: Sequence[str],
    max_bytes: int,
    timeout_seconds: float,
    user_agent: str,
    delay_seconds: float = 0.0,
    allow_redirects: bool = True,
) -> MetadataResponse:
    """Fetch one allowlisted HTTPS metadata response after authorization."""

    if not allow_network:
        raise MetadataNetworkError(
            "network access is disabled; pass the explicit live-execution flag",
            subtype="authorization",
        )
    hosts = _allowed_host_set(allowed_hosts)
    _validate_metadata_url(url, allowed_hosts=hosts)
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise MetadataNetworkError(
            "max_bytes must be a positive integer", subtype="request-policy"
        )
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or timeout_seconds <= 0
    ):
        raise MetadataNetworkError(
            "timeout_seconds must be finite and positive", subtype="request-policy"
        )
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise MetadataNetworkError(
            "user_agent must not be empty", subtype="request-policy"
        )
    if (
        isinstance(delay_seconds, bool)
        or not isinstance(delay_seconds, (int, float))
        or not math.isfinite(float(delay_seconds))
        or delay_seconds < 0
    ):
        raise MetadataNetworkError(
            "delay_seconds must be finite and not negative",
            subtype="request-policy",
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
    redirect_handler = (
        _AllowlistedRedirectHandler(hosts)
        if allow_redirects
        else _RejectRedirectHandler()
    )
    # Evidence-bearing metadata requests are direct-origin only. Inheriting a
    # host or environment proxy could route traffic (and proxy credentials)
    # outside the frozen exact-host boundary.
    opener = build_opener(ProxyHandler({}), redirect_handler)
    try:
        with opener.open(request, timeout=float(timeout_seconds)) as response:
            final_url = _validate_metadata_url(
                response.geturl(), allowed_hosts=hosts
            )
            raw_status = getattr(response, "status", None)
            if (
                not isinstance(raw_status, int)
                or isinstance(raw_status, bool)
                or raw_status != 200
            ):
                raise MetadataNetworkError(
                    f"metadata response status must be 200, got {raw_status!r}",
                    subtype="http-status",
                )
            raw_length = response.headers.get("Content-Length")
            if raw_length is not None:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    content_length = None
                if content_length is not None and content_length > max_bytes:
                    raise MetadataNetworkError(
                        f"metadata response declares {content_length} bytes, "
                        f"exceeding max_bytes={max_bytes}",
                        subtype="response-size",
                    )
            content_type = response.headers.get("Content-Type")
            payload = response.read(max_bytes + 1)
    except MetadataNetworkError:
        raise
    except (TimeoutError, socket.timeout) as error:
        raise MetadataNetworkError(
            "metadata request timed out", subtype="timeout"
        ) from error
    except ssl.SSLError as error:
        raise MetadataNetworkError(
            "metadata request failed TLS validation", subtype="tls"
        ) from error
    except HTTPError as error:
        raise MetadataNetworkError(
            f"metadata request returned HTTP {error.code}",
            subtype="http-status",
        ) from error
    except URLError as error:
        reason = error.reason
        subtype = (
            "dns"
            if isinstance(reason, socket.gaierror)
            else "timeout"
            if isinstance(reason, (TimeoutError, socket.timeout))
            else "tls"
            if isinstance(reason, ssl.SSLError)
            else "other"
        )
        raise MetadataNetworkError(
            "metadata request failed before a response", subtype=subtype
        ) from error
    except Exception as error:
        raise MetadataNetworkError(
            "metadata request failed before a response", subtype="other"
        ) from error

    if len(payload) > max_bytes:
        raise MetadataNetworkError(
            f"metadata response exceeded max_bytes={max_bytes}",
            subtype="response-size",
        )
    return MetadataResponse(
        payload=payload,
        requested_url=url,
        final_url=final_url,
        status=raw_status,
        content_type=content_type,
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
    allow_redirects: bool = True,
) -> bytes:
    """Backward-compatible payload-only metadata fetch."""

    return fetch_metadata_response(
        url,
        allow_network=allow_network,
        allowed_hosts=allowed_hosts,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
        delay_seconds=delay_seconds,
        allow_redirects=allow_redirects,
    ).payload
