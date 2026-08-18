"""Portable, canonical relative-path policy for committed identities.

Paths stored in manifests, configurations, checkpoints, and reports must mean
one thing on every supported host.  Native command-line paths may still use the
host operating system, but persisted relative paths use forward-slash POSIX
syntax and reject names that are unsafe or ambiguous on Windows.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any
import unicodedata


_WINDOWS_RESERVED_STEMS = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)
_WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"\\|?*')


class PortablePathError(ValueError):
    """Raised when a persisted relative path is not portable and canonical."""


def portable_relative_path(
    raw_path: Any,
    *,
    label: str = "path",
    required_prefix: tuple[str, ...] | None = None,
    suffix: str | None = None,
) -> Path:
    """Return an OS-native path for one canonical portable relative path.

    The persisted spelling must use forward slashes, contain no traversal or
    normalization aliases, and avoid Windows-reserved names.  Optional prefix
    and suffix constraints let callers keep their existing repository layout
    rules while sharing one cross-platform safety boundary.
    """

    if not isinstance(raw_path, str) or not raw_path:
        raise PortablePathError(f"{label} must be a nonempty string")
    if raw_path != raw_path.strip():
        raise PortablePathError(
            f"{label} must not have leading or trailing whitespace"
        )
    if unicodedata.normalize("NFC", raw_path) != raw_path:
        raise PortablePathError(f"{label} must use NFC Unicode normalization")
    if "\x00" in raw_path or any(ord(character) < 32 for character in raw_path):
        raise PortablePathError(f"{label} must not contain control characters")
    if any(character in raw_path for character in _WINDOWS_FORBIDDEN_CHARACTERS):
        raise PortablePathError(
            f"{label} must use a portable forward-slash relative path"
        )

    portable = PurePosixPath(raw_path)
    if (
        portable.is_absolute()
        or ".." in portable.parts
        or portable.as_posix() != raw_path
        or not portable.parts
    ):
        raise PortablePathError(
            f"{label} must be a canonical portable relative path"
        )

    for component in portable.parts:
        if component in {"", ".", ".."}:
            raise PortablePathError(
                f"{label} must be a canonical portable relative path"
            )
        if component.endswith((" ", ".")):
            raise PortablePathError(
                f"{label} contains a component ending in a space or period"
            )
        stem = component.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED_STEMS:
            raise PortablePathError(
                f"{label} contains a Windows-reserved path component"
            )

    if required_prefix is not None and portable.parts[: len(required_prefix)] != (
        required_prefix
    ):
        rendered = "/".join(required_prefix)
        raise PortablePathError(f"{label} must be under {rendered}/")
    if suffix is not None and portable.suffix != suffix:
        raise PortablePathError(f"{label} must end with {suffix}")

    return Path(*portable.parts)


def is_portable_relative_path(
    raw_path: Any,
    *,
    required_prefix: tuple[str, ...] | None = None,
    suffix: str | None = None,
) -> bool:
    """Return whether ``raw_path`` passes :func:`portable_relative_path`."""

    try:
        portable_relative_path(
            raw_path,
            required_prefix=required_prefix,
            suffix=suffix,
        )
    except PortablePathError:
        return False
    return True


def portable_path_identity(
    raw_path: Any,
    *,
    label: str = "path",
) -> tuple[str, ...]:
    """Return a cross-platform collision key for one persisted path.

    Windows path lookup is case-insensitive by default, so persisted path
    collections must not contain spellings that differ only by case.  NFC is
    already enforced by :func:`portable_relative_path`.
    """

    portable_relative_path(raw_path, label=label)
    return tuple(
        component.casefold() for component in PurePosixPath(raw_path).parts
    )
