"""Explicit, bounded network access for Stage 0 metadata qualification.

Network use is never implicit. Callers must provide an allowlist, response-byte
limit, timeout, user agent, and access-log destination. The access log stores a
sanitized endpoint shape rather than query values or source-C item locators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .official_metadata_adapters import MetadataAdapterError, sanitize_request_url


class BoundedNetworkError(RuntimeError):
    """Raised when a bounded metadata request cannot be completed safely."""


@dataclass(frozen=True)
class AccessLogEntry:
    schema_version: int
    started_at: str
    completed_at: str
    sanitized_url: str
    host: str
    status_code: int
    response_bytes: int
    response_sha256: str
    content_type: str | None
    max_bytes: int
    timeout_seconds: float
    user_agent: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_access_log(path: str | Path, entry: AccessLogEntry) -> None:
    """Append one canonical JSON line, creating the parent directory."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        entry.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered + "\n")


def bounded_fetch(
    locator: str,
    *,
    allowed_hosts: set[str] | frozenset[str],
    max_bytes: int,
    timeout_seconds: float,
    user_agent: str,
    access_log: str | Path,
) -> bytes:
    """Fetch one metadata response while enforcing host, time, and size bounds."""

    if max_bytes < 1:
        raise BoundedNetworkError("max_bytes must be positive")
    if timeout_seconds <= 0:
        raise BoundedNetworkError("timeout_seconds must be positive")
    if not user_agent.strip():
        raise BoundedNetworkError("user_agent must not be empty")
    parsed = urlsplit(locator)
    host = (parsed.hostname or "").lower()
    allowed = {value.lower() for value in allowed_hosts}
    if parsed.scheme != "https":
        raise BoundedNetworkError("metadata requests require HTTPS")
    if not host or host not in allowed:
        raise BoundedNetworkError(f"host is not allowlisted: {host or '<missing>'}")

    try:
        sanitized = sanitize_request_url(locator)
    except MetadataAdapterError as error:
        raise BoundedNetworkError(str(error)) from error

    started_at = _now()
    request = Request(
        locator,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/xml, application/json;q=0.9, */*;q=0.1",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            status = int(getattr(response, "status", 200))
            content_type = response.headers.get("Content-Type")
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > max_bytes:
                    raise BoundedNetworkError(
                        f"declared response size {declared_size} exceeds {max_bytes}"
                    )

            chunks: list[bytes] = []
            received = 0
            while True:
                chunk = response.read(min(64 * 1024, max_bytes - received + 1))
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)
                if received > max_bytes:
                    raise BoundedNetworkError(
                        f"response exceeded max_bytes={max_bytes}"
                    )
    except BoundedNetworkError:
        raise
    except HTTPError as error:
        raise BoundedNetworkError(
            f"metadata request failed with HTTP {error.code}"
        ) from error
    except URLError as error:
        raise BoundedNetworkError(f"metadata request failed: {error.reason}") from error
    except OSError as error:
        raise BoundedNetworkError(f"metadata request failed: {error}") from error

    payload = b"".join(chunks)
    completed_at = _now()
    entry = AccessLogEntry(
        schema_version=1,
        started_at=started_at,
        completed_at=completed_at,
        sanitized_url=sanitized,
        host=host,
        status_code=status,
        response_bytes=len(payload),
        response_sha256=hashlib.sha256(payload).hexdigest(),
        content_type=content_type,
        max_bytes=max_bytes,
        timeout_seconds=float(timeout_seconds),
        user_agent=user_agent,
    )
    append_access_log(access_log, entry)
    return payload
