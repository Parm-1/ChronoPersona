"""Parse legacy Stack Exchange Internet Archive item metadata.

Stack Exchange stopped publishing new dumps to Archive.org in 2024. This
adapter therefore inventories only a frozen legacy archive item and records
whether its item metadata attributes the dump to Stack Exchange. It does not
claim that Archive.org is the current official delivery mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any
from urllib.parse import quote


class StackExchangeInventoryError(ValueError):
    """Raised when the Stack Exchange archive inventory is malformed."""


_SAFE_ID = re.compile(r"[^A-Za-z0-9._:@+-]+")


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _safe_id(value: str) -> str:
    normalized = _SAFE_ID.sub("-", value.strip()).strip("-")
    return normalized or "unknown"


def _company_attributed(metadata: Mapping[str, Any]) -> bool:
    creators = _string_values(metadata.get("creator"))
    return any("stack exchange" in creator.lower() for creator in creators)


def _file_mtime(raw_file: Mapping[str, Any], file_name: str) -> int | None:
    raw_mtime = raw_file.get("mtime")
    if raw_mtime in {None, ""}:
        return None
    try:
        mtime = int(raw_mtime)
    except (TypeError, ValueError) as error:
        raise StackExchangeInventoryError(
            f"invalid mtime for {file_name!r}: {raw_mtime!r}"
        ) from error
    if mtime < 0:
        raise StackExchangeInventoryError(
            f"archive file {file_name!r} has negative mtime"
        )
    return mtime


def parse_stackexchange_archive_metadata(
    value: Mapping[str, Any],
    *,
    source_locator: str,
    source_id: str = "stackexchange-initial-nontechnical-posts",
) -> list[dict[str, Any]]:
    """Return per-site legacy dump files without downloading them."""

    files = value.get("files")
    if not isinstance(files, list):
        raise StackExchangeInventoryError("archive metadata has no files list")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise StackExchangeInventoryError("archive metadata has no metadata object")

    identifier = str(metadata.get("identifier") or "stackexchange")
    creators = _string_values(metadata.get("creator"))
    company_attributed = _company_attributed(metadata)

    selected_files: list[tuple[Mapping[str, Any], str, int, int | None]] = []
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
        if size <= 0:
            raise StackExchangeInventoryError(
                f"archive file {file_name!r} has non-positive size"
            )
        mtime = _file_mtime(raw_file, file_name)
        selected_files.append((raw_file, file_name, size, mtime))

    if not selected_files:
        raise StackExchangeInventoryError(
            "archive metadata contains no .7z site dumps"
        )

    mtimes = [mtime for _, _, _, mtime in selected_files if mtime is not None]
    if mtimes:
        snapshot_component = f"mtime-{max(mtimes)}"
        snapshot_basis = "maximum-numeric-file-mtime"
    else:
        snapshot_component = str(
            metadata.get("date")
            or metadata.get("publicdate")
            or "unknown-date"
        )
        snapshot_basis = "archive-item-date-fallback"
    snapshot_id = _safe_id(f"{identifier}@{snapshot_component}")

    records: list[dict[str, Any]] = []
    for raw_file, file_name, size, mtime in selected_files:
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
            f"https://archive.org/download/{quote(identifier, safe='')}/"
            + quote(file_name)
        )
        site_slug = file_name[:-3]
        records.append(
            {
                "schema_version": 1,
                "inventory_id": f"stackexchange:{snapshot_id}:{_safe_id(site_slug)}",
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
                    "archive_item_identifier": identifier,
                    "archive_item_creators": creators,
                    "company_attributed_archive_item": company_attributed,
                    "delivery_status": "legacy-archive; not current official delivery",
                    "archive_metadata_locator": source_locator,
                    "format": raw_file.get("format"),
                    "mtime": mtime,
                    "snapshot_basis": snapshot_basis,
                },
            }
        )
    return records
