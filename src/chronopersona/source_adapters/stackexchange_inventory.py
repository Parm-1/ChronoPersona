"""Parse legacy Stack Exchange Internet Archive item metadata.

Stack Exchange stopped publishing new dumps to Archive.org in 2024. This
adapter therefore inventories only a frozen legacy archive item and records
whether its item metadata attributes the dump to Stack Exchange. It does not
claim that Archive.org is the current official delivery mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import re
from typing import Any
from urllib.parse import quote

from ..path_policy import PortablePathError, portable_relative_path


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
    normalized_creators = [" ".join(creator.split()) for creator in creators]
    return any("stack exchange" in creator.lower() for creator in normalized_creators)


def _file_mtime(raw_file: Mapping[str, Any], file_name: str) -> int | None:
    raw_mtime = raw_file.get("mtime")
    if raw_mtime in {None, ""}:
        return None
    if isinstance(raw_mtime, bool) or not (
        type(raw_mtime) is int
        or (
            isinstance(raw_mtime, str)
            and re.fullmatch(r"0|[1-9]\d*", raw_mtime) is not None
        )
    ):
        raise StackExchangeInventoryError(
            f"invalid mtime for {file_name!r}: {raw_mtime!r}"
        )
    mtime = int(raw_mtime)
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
    normalized_creators = [" ".join(creator.split()) for creator in creators]
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
        try:
            relative_name = portable_relative_path(
                file_name,
                label="Stack Exchange archive file",
                suffix=".7z",
            )
        except PortablePathError as error:
            raise StackExchangeInventoryError(str(error)) from error
        if len(relative_name.parts) != 1:
            raise StackExchangeInventoryError(
                "Stack Exchange archive file must be one canonical leaf"
            )
        raw_size = raw_file.get("size")
        if isinstance(raw_size, bool) or not (
            type(raw_size) is int
            or (
                isinstance(raw_size, str)
                and re.fullmatch(r"0|[1-9]\d*", raw_size) is not None
            )
        ):
            raise StackExchangeInventoryError(
                f"invalid size for {file_name!r}: {raw_size!r}"
            )
        size = int(raw_size)
        if size <= 0:
            raise StackExchangeInventoryError(
                f"archive file {file_name!r} has non-positive size"
            )
        mtime = _file_mtime(raw_file, file_name)
        raw_format = raw_file.get("format")
        if raw_format != "7z":
            raise StackExchangeInventoryError(
                f"archive file {file_name!r} format is not exact"
            )
        selected_files.append((raw_file, file_name, size, mtime))

    if not selected_files:
        raise StackExchangeInventoryError(
            "archive metadata contains no .7z site dumps"
        )
    selected_names = [file_name.casefold() for _, file_name, _, _ in selected_files]
    if len(selected_names) != len(set(selected_names)):
        raise StackExchangeInventoryError(
            "Stack Exchange archive file names collide case-insensitively"
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
            + quote(file_name, safe="")
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
                    "archive_item_creator_count": len(normalized_creators),
                    "archive_item_creators_sha256": hashlib.sha256(
                        "\n".join(normalized_creators).encode("utf-8")
                    ).hexdigest(),
                    "company_attributed_archive_item": company_attributed,
                    "delivery_status": "legacy-archive; not current official delivery",
                    "archive_metadata_locator": source_locator,
                    "format": "7z",
                    "mtime": mtime,
                    "snapshot_basis": snapshot_basis,
                },
            }
        )
    return records
