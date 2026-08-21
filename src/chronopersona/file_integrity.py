"""Portable identity checks for stable reads of local files."""

from __future__ import annotations

import os


def _portable_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
    )


def _same_view_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (*_portable_identity(info), int(info.st_ctime_ns))


def stable_read_unchanged(
    path_before: os.stat_result,
    handle_before: os.stat_result,
    handle_after: os.stat_result,
    path_after: os.stat_result,
) -> bool:
    """Return whether path and descriptor views identify one unchanged file.

    Python 3.13 on Windows can expose different ``st_ctime_ns`` values through
    ``stat`` and ``fstat`` for the same file. Cross-view identity therefore
    uses device, inode, size, and mtime, while ctime must remain stable within
    each API view across the read.
    """

    if len(
        {
            _portable_identity(path_before),
            _portable_identity(handle_before),
            _portable_identity(handle_after),
            _portable_identity(path_after),
        }
    ) != 1:
        return False
    return (
        _same_view_identity(path_before) == _same_view_identity(path_after)
        and _same_view_identity(handle_before) == _same_view_identity(handle_after)
    )
