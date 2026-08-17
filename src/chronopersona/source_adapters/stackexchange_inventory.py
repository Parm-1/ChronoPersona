"""Parse the official Stack Exchange Internet Archive inventory metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class StackExchangeInventoryError(ValueError):
    """Raised when the Stack Exchange archive inventory is malformed."""


def parse_stackexchange_archive_metadata(
    value: Mapping[str, Any],
    *,
    source_locator: str,
    source_id: str = "stackexchange-initial-nontechnical-posts",
) -> list[dict[str, Any]]:
    """Return official per-site dump archive files without downloading them."""

    files = value.get("files")
    if not isinstance(files, list):
        raise StackExchangeInventoryError("archive metadata has no files list")
    metadata = value.get("metadata")
    snapshot_id = "unknown-snapshot"
    if isinstance(metadata, Mapping):
        snapshot_id = str(
            metadata.get("date")
            or metadata.get("publicdate")
            or metadata.get("identifier")
            or snapshot_id
        )
    records: list[dict[str, Any]] = []
    for raw_file in files:
        if not isinstance(raw_file, Mapping):
            continue
        file_name = raw_file.get("name")
        if not isinstance(file_name, str) or not file_name.lower().endswith(".7z"):
            continue
        if file_name.startswith("__"):
            continue
        raw_size = raw_file.get("size")
        try:
            size = int(raw_size)
        except (TypeError, ValueError) as error:
            raise StackExchangeInventoryError(
                f"invalid size for {file_name!r}: {raw_size!r}"
            ) from error
        hashes = {
            algorithm: str(raw_file[algorithm])
            for algorithm in ("md5", "sha1")
            if raw_file.get(algorithm)
        }
        if not hashes:
            raise StackExchangeInventoryError(
                f"archive file {file_name!r} has no md5 or sha1"
            )
        locator = (
            "https://archive.org/download/stackexchange/"
            + file_name.replace(" ", "%20")
        )
        site_slug = file_name[:-3]
        records.append(
            {
                "schema_version": 1,
                "inventory_id": (
                    f"stackexchange:{snapshot_id}:{site_slug}"
                ),
                "source_id": source_id,
                "snapshot_id": snapshot_id,
                "file_name": file_name,
                "locator": locator,
                "content_kind": "community-data-dump",
                "size_bytes": size,
                "hashes": hashes,
                "downloaded": False,
                "download_authorized": False,
                "source_metadata": {
                    "site_slug": site_slug,
                    "archive_metadata_locator": source_locator,
                    "format": raw_file.get("format"),
                    "mtime": raw_file.get("mtime"),
                },
            }
        )
    if not records:
        raise StackExchangeInventoryError(
            "archive metadata contains no .7z site dumps"
        )
    return records
