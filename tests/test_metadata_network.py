from __future__ import annotations

from email.message import Message
from urllib.request import ProxyHandler, Request

import pytest

from chronopersona.source_adapters.network import (
    MetadataNetworkError,
    _AllowlistedRedirectHandler,
    _RejectRedirectHandler,
    _allowed_host_set,
    fetch_metadata,
    fetch_metadata_response,
)


def test_metadata_network_requires_explicit_authorization() -> None:
    with pytest.raises(MetadataNetworkError, match="network access is disabled"):
        fetch_metadata(
            "https://metadata.example.org/data.json",
            allow_network=False,
            allowed_hosts=("metadata.example.org",),
            max_bytes=1024,
            timeout_seconds=5,
            user_agent="fixture",
        )


@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://metadata.example.org/data.json", "must use HTTPS"),
        ("https://other.example.org/data.json", "not in the exact allowlist"),
        ("https://user@metadata.example.org/data.json", "must not contain credentials"),
        ("https://metadata.example.org:444/data.json", "default HTTPS port"),
    ],
)
def test_metadata_url_policy_fails_before_network(url: str, expected: str) -> None:
    with pytest.raises(MetadataNetworkError, match=expected):
        fetch_metadata(
            url,
            allow_network=True,
            allowed_hosts=("metadata.example.org",),
            max_bytes=1024,
            timeout_seconds=5,
            user_agent="fixture",
        )


def test_redirect_cannot_escape_exact_host_allowlist() -> None:
    handler = _AllowlistedRedirectHandler(
        _allowed_host_set(("metadata.example.org",))
    )
    request = Request("https://metadata.example.org/start")

    with pytest.raises(MetadataNetworkError, match="not in the exact allowlist"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            Message(),
            "https://other.example.org/redirected",
        )


def test_evidence_gate_can_reject_every_redirect() -> None:
    handler = _RejectRedirectHandler()
    request = Request("https://metadata.example.org/start")

    with pytest.raises(MetadataNetworkError, match="redirect is not permitted"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            Message(),
            "https://metadata.example.org/redirected",
        )


def test_host_allowlist_rejects_wildcards_and_ports() -> None:
    for invalid in (("*.example.org",), ("example.org:443",), ()):
        with pytest.raises(MetadataNetworkError):
            _allowed_host_set(invalid)


class _FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        payload: bytes,
        content_length: str | None = None,
    ) -> None:
        self._url = url
        self._payload = payload
        self.status = 200
        self.headers = Message()
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def geturl(self) -> str:
        return self._url

    def read(self, limit: int) -> bytes:
        return self._payload[:limit]


class _FakeOpener:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def open(self, request, *, timeout: float):
        assert request.full_url == "https://metadata.example.org/data.json"
        assert timeout == 5.0
        return self._response


def _fetch_with_response(monkeypatch, response: _FakeResponse, *, max_bytes=1024):
    from chronopersona.source_adapters import network

    monkeypatch.setattr(
        network,
        "build_opener",
        lambda *handlers: _FakeOpener(response),
    )
    return network.fetch_metadata(
        "https://metadata.example.org/data.json",
        allow_network=True,
        allowed_hosts=("metadata.example.org",),
        max_bytes=max_bytes,
        timeout_seconds=5,
        user_agent="fixture",
    )


def test_allowlisted_metadata_response_is_returned(monkeypatch) -> None:
    payload = b'{"ok":true}'
    observed = _fetch_with_response(
        monkeypatch,
        _FakeResponse(
            url="https://metadata.example.org/data.json",
            payload=payload,
            content_length=str(len(payload)),
        ),
    )
    assert observed == payload


def test_metadata_response_preserves_transport_identity(monkeypatch) -> None:
    from chronopersona.source_adapters import network

    payload = b'{"ok":true}'
    response = _FakeResponse(
        url="https://metadata.example.org/final.json",
        payload=payload,
        content_length=str(len(payload)),
    )
    response.headers["Content-Type"] = "application/json"
    monkeypatch.setattr(
        network,
        "build_opener",
        lambda *handlers: _FakeOpener(response),
    )

    observed = fetch_metadata_response(
        "https://metadata.example.org/data.json",
        allow_network=True,
        allowed_hosts=("metadata.example.org",),
        max_bytes=1024,
        timeout_seconds=5,
        user_agent="fixture",
    )

    assert observed.payload == payload
    assert observed.requested_url == "https://metadata.example.org/data.json"
    assert observed.final_url == "https://metadata.example.org/final.json"
    assert observed.status == 200
    assert observed.content_type == "application/json"


def test_metadata_fetch_installs_an_empty_direct_proxy_policy(monkeypatch) -> None:
    from chronopersona.source_adapters import network

    payload = b"{}"
    response = _FakeResponse(
        url="https://metadata.example.org/data.json",
        payload=payload,
    )
    captured = []

    def build(*handlers):
        captured.extend(handlers)
        return _FakeOpener(response)

    monkeypatch.setenv("HTTPS_PROXY", "https://user:secret@proxy.example")
    monkeypatch.setattr(network, "build_opener", build)
    fetch_metadata_response(
        "https://metadata.example.org/data.json",
        allow_network=True,
        allowed_hosts=("metadata.example.org",),
        max_bytes=1024,
        timeout_seconds=5,
        user_agent="fixture",
    )

    proxies = [handler for handler in captured if isinstance(handler, ProxyHandler)]
    assert len(proxies) == 1
    assert proxies[0].proxies == {}


def test_final_response_url_is_revalidated(monkeypatch) -> None:
    with pytest.raises(MetadataNetworkError, match="not in the exact allowlist"):
        _fetch_with_response(
            monkeypatch,
            _FakeResponse(
                url="https://other.example.org/data.json",
                payload=b"{}",
            ),
        )


def test_declared_and_observed_response_size_limits_fail_closed(monkeypatch) -> None:
    with pytest.raises(MetadataNetworkError, match="declares 2048 bytes"):
        _fetch_with_response(
            monkeypatch,
            _FakeResponse(
                url="https://metadata.example.org/data.json",
                payload=b"{}",
                content_length="2048",
            ),
            max_bytes=1024,
        )

    with pytest.raises(MetadataNetworkError, match="exceeded max_bytes=4"):
        _fetch_with_response(
            monkeypatch,
            _FakeResponse(
                url="https://metadata.example.org/data.json",
                payload=b"12345",
            ),
            max_bytes=4,
        )


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), True])
def test_network_timing_limits_must_be_finite_numbers(invalid) -> None:
    with pytest.raises(MetadataNetworkError, match="timeout_seconds"):
        fetch_metadata(
            "https://metadata.example.org/data.json",
            allow_network=True,
            allowed_hosts=("metadata.example.org",),
            max_bytes=1024,
            timeout_seconds=invalid,
            user_agent="fixture",
        )
