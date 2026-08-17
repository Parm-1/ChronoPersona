"""Redirect policy used by bounded metadata HTTP clients."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler


class RedirectPolicyError(RuntimeError):
    """Raised when a redirect escapes the explicit HTTPS host allowlist."""


class AllowlistedRedirectHandler(HTTPRedirectHandler):
    """Follow redirects only when the target remains HTTPS and allowlisted."""

    def __init__(self, allowed_hosts: set[str] | frozenset[str]) -> None:
        super().__init__()
        self.allowed_hosts = {host.lower() for host in allowed_hosts}

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        absolute = urljoin(req.full_url, newurl)
        parsed = urlsplit(absolute)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in self.allowed_hosts:
            raise RedirectPolicyError(
                f"redirect target is not approved: {parsed.scheme}://{host}"
            )
        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            absolute,
        )
