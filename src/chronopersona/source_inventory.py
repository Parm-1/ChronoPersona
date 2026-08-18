"""Validate and summarize metadata-only archive file inventories."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import re
from typing import Any


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
_ALLOWED_KINDS = {
    "revision-history-archive",
    "community-data-dump",
    "metadata-export",
}
_ALLOWED_HASH_ALGORITHMS = {"md5", "sha1", "sha256"}
_HASH_LENGTHS = {"md5": 32, "sha1": 40, "sha256": 64}
_FORBIDDEN_TEXT_FIELDS = {
    "text",
    "content",
    "body",
    "abstract",
    "full_text",
    "fulltext",
    "source_text",
    "document_text",
}


class SourceInventoryError(ValueError):
    """Raised when an archive inventory cannot support safe planning."""


def _forbidden_payload_keys(value: Any) -> tuple[str, ...]:
    found: list[str] = []

    def visit(current: Any, prefix: str) -> None:
        if isinstance(current, Mapping):
            for key, nested in current.items():
                key_text = str(key)
                location = f"{prefix}.{key_text}" if prefix else key_text
                if key_text.casefold() in _FORBIDDEN_TEXT_FIELDS:
                    found.append(location)
                visit(nested, location)
        elif isinstance(current, list):
            for index, nested in enumerate(current):
                visit(nested, f"{prefix}[{index}]")

    visit(value, "")
    return tuple(sorted(found))


def canonical_json_sha256(value: Any) -> str:
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def validate_source_inventory(
    records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Return all known archive identity, size, and download-boundary errors."""

    errors: list[str] = []
    inventory_ids: list[str] = []
    if not records:
        return ("source inventory must contain at least one record",)

    for index, record in enumerate(records):
        location = f"records[{index}]"
        if record.get("schema_version") != 1:
            errors.append(f"{location}.schema_version must be 1")
        inventory_id = record.get("inventory_id")
        if not isinstance(inventory_id, str) or not _ID.fullmatch(inventory_id):
            errors.append(f"{location}.inventory_id has invalid format")
        else:
            inventory_ids.append(inventory_id)
        for field in (
            "source_id",
            "snapshot_id",
            "file_name",
            "locator",
        ):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{location}.{field} must not be empty")
        if record.get("content_kind") not in _ALLOWED_KINDS:
            errors.append(
                f"{location}.content_kind must be one of "
                + ", ".join(sorted(_ALLOWED_KINDS))
            )
        size = record.get("size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errors.append(f"{location}.size_bytes must be a non-negative integer")
        hashes = record.get("hashes")
        if not isinstance(hashes, Mapping):
            errors.append(f"{location}.hashes must be an object")
        else:
            if not hashes:
                errors.append(f"{location}.hashes must contain at least one hash")
            for algorithm, digest in hashes.items():
                if algorithm not in _ALLOWED_HASH_ALGORITHMS:
                    errors.append(
                        f"{location}.hashes contains unsupported algorithm {algorithm!r}"
                    )
                expected_length = _HASH_LENGTHS.get(algorithm)
                if expected_length is not None and (
                    not isinstance(digest, str)
                    or re.fullmatch(
                        rf"[0-9a-f]{{{expected_length}}}",
                        digest,
                    )
                    is None
                ):
                    errors.append(
                        f"{location}.hashes.{algorithm} must be a lowercase "
                        f"{expected_length}-character hexadecimal digest"
                    )
        if record.get("downloaded") is not False:
            errors.append(
                f"{location}.downloaded must remain false in inventory audit"
            )
        if record.get("download_authorized") is not False:
            errors.append(
                f"{location}.download_authorized must remain false"
            )
        metadata = record.get("source_metadata")
        if not isinstance(metadata, Mapping):
            errors.append(f"{location}.source_metadata must be an object")
        else:
            forbidden = _forbidden_payload_keys(metadata)
            if forbidden:
                qualified = [
                    f"source_metadata.{field}" for field in forbidden
                ]
                errors.append(
                    f"{location}.source_metadata contains forbidden text fields: "
                    + ", ".join(qualified)
                )

    if len(inventory_ids) != len(set(inventory_ids)):
        errors.append("inventory_id values must be unique")
    return tuple(errors)


def summarize_source_inventory(
    records: Sequence[Mapping[str, Any]],
    *,
    source_locator: str,
) -> dict[str, Any]:
    """Produce deterministic size and file-count planning evidence."""

    if not isinstance(source_locator, str) or not source_locator:
        raise SourceInventoryError("source_locator must not be empty")
    by_source: Counter[str] = Counter()
    by_snapshot: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    bytes_by_source: Counter[str] = Counter()
    total_bytes = 0
    for record in records:
        source_id = str(record["source_id"])
        size = int(record["size_bytes"])
        by_source[source_id] += 1
        by_snapshot[str(record["snapshot_id"])] += 1
        by_kind[str(record["content_kind"])] += 1
        bytes_by_source[source_id] += size
        total_bytes += size

    output: dict[str, Any] = {
        "schema_version": 1,
        "audit_type": "source-archive-inventory",
        "source_locator": source_locator,
        "download_performed": False,
        "download_authorized": False,
        "file_count": len(records),
        "total_size_bytes": total_bytes,
        "minimum_free_space_bytes_with_25_percent_margin": (
            (total_bytes * 5 + 3) // 4
        ),
        "counts": {
            "source": dict(sorted(by_source.items())),
            "snapshot": dict(sorted(by_snapshot.items())),
            "content_kind": dict(sorted(by_kind.items())),
        },
        "bytes_by_source": dict(sorted(bytes_by_source.items())),
    }
    output["output_sha256"] = canonical_json_sha256(output)
    return output
