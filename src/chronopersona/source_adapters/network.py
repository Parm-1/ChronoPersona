"""Explicit, bounded network access for metadata-only source adapters."""

from __future__ import annotations

import time
from urllib.request import Request, urlopen


class MetadataNetworkError(RuntimeError):
    """Raised when a bounded metadata request cannot be completed safely."""


def fetch_metadata(
    url: str,
    *,
    allow_network: bool,
    max_bytes: int,
    timeout_seconds: float,
    user_agent: str,
    delay_seconds: float = 0.0,
) -> bytes:
    """Fetch one metadata response only after explicit authorization."""

    if not allow_network:
        raise MetadataNetworkError(
            "network access is disabled; pass the explicit live-execution flag"
        )
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise MetadataNetworkError("metadata URL must be HTTP(S)")
    if max_bytes < 1:
        raise MetadataNetworkError("max_bytes must be positive")
    if timeout_seconds <= 0:
        raise MetadataNetworkError("timeout_seconds must be positive")
    if not user_agent.strip():
        raise MetadataNetworkError("user_agent must not be empty")
    if delay_seconds < 0:
        raise MetadataNetworkError("delay_seconds must not be negative")
    if delay_seconds:
        time.sleep(delay_seconds)

    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json, application/xml, text/xml;q=0.9, */*;q=0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
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
