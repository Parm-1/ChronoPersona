"""Prepare locator-redacted source review packets and hashed access logs.

The deterministic sampling layer intentionally preserves locators so a project
manager can resolve selected records. Those packets are not reviewer-ready for
held-out source C because locators can reveal native identifiers and dates.
This module creates a separate reviewer packet, protected access map, and
append-only event records that never contain retrieved source text.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .source_metadata import canonical_json_sha256


class SourceReviewError(ValueError):
    """Raised when held-out review blinding or access integrity fails."""


_FORBIDDEN_REVIEW_KEYS = {
    "metadata_locator",
    "content_locator",
    "native_timestamp",
    "native_item_id",
    "record_id",
    "era_window",
}
_SENSITIVE_STRING = re.compile(
    r"(?:https?://|ftp://|s3://|oai:|"
    r"\bPMC\d+\b|\b\d{4}\.\d{4,5}(?:v\d+)?\b|"
    r"\b(?:19|20)\d{2}-\d{2}-\d{2}(?:T|\b))",
    re.IGNORECASE,
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_PURPOSES = {
    "metadata-review",
    "content-review",
    "license-review",
    "version-review",
}
_ALLOWED_OUTCOMES = {"planned", "succeeded", "failed"}
_ALLOWED_LOCATOR_KINDS = {"metadata", "content"}
_EVENT_KEYS = frozenset(
    {
        "schema_version",
        "artifact_type",
        "access_map_sha256",
        "access_id",
        "blind_id",
        "source_id",
        "locator_kind",
        "locator_sha256",
        "reviewer",
        "purpose",
        "accessed_at",
        "outcome",
        "response_sha256",
        "response_bytes",
        "error_code",
        "source_text_recorded",
        "event_id",
    }
)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _verify_self_hash(value: Mapping[str, Any], *, label: str) -> str:
    recorded = value.get("output_sha256")
    if not isinstance(recorded, str) or not _SHA256.fullmatch(recorded):
        raise SourceReviewError(f"{label} lacks a valid output_sha256")
    unhashed = dict(value)
    unhashed.pop("output_sha256", None)
    expected = canonical_json_sha256(unhashed)
    if recorded != expected:
        raise SourceReviewError(
            f"{label} output_sha256 mismatch: recorded {recorded}, expected {expected}"
        )
    return recorded


def _verify_event_id(event: Mapping[str, Any], *, label: str) -> str:
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not event_id.startswith("event-"):
        raise SourceReviewError(f"{label} lacks a valid event_id")
    unhashed = dict(event)
    unhashed.pop("event_id", None)
    expected = "event-" + canonical_json_sha256(unhashed)[:24]
    if event_id != expected:
        raise SourceReviewError(
            f"{label} event_id mismatch: recorded {event_id}, expected {expected}"
        )
    return event_id


def _access_id(
    seed: str,
    packet_sha256: str,
    blind_id: str,
    metadata_locator: str | None,
    content_locator: str | None,
) -> str:
    payload = "\0".join(
        (
            "source-review-access-v1",
            seed,
            packet_sha256,
            blind_id,
            metadata_locator or "",
            content_locator or "",
        )
    )
    return "access-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _scan_review_value(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_REVIEW_KEYS:
                errors.append(f"{location} contains forbidden key {key!r}")
            _scan_review_value(child, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_review_value(child, f"{location}[{index}]", errors)
    elif isinstance(value, str) and _SENSITIVE_STRING.search(value):
        errors.append(f"{location} contains an identifier, date, or locator")


def validate_redacted_review_packet(packet: Mapping[str, Any]) -> tuple[str, ...]:
    """Return all known held-out reviewer-packet leakage errors."""

    errors: list[str] = []
    try:
        _verify_self_hash(packet, label="review packet")
    except SourceReviewError as error:
        errors.append(str(error))
    if packet.get("schema_version") != 1:
        errors.append("review packet schema_version must be 1")
    if packet.get("artifact_type") != "source-review-packet-redacted":
        errors.append("review packet artifact_type is invalid")
    if packet.get("era_labels_hidden") is not True:
        errors.append("review packet must hide era labels")
    if packet.get("locators_redacted") is not True:
        errors.append("review packet must mark locators redacted")
    records = packet.get("records")
    if not isinstance(records, list) or not records:
        errors.append("review packet must contain records")
    else:
        access_ids: list[str] = []
        blind_ids: list[str] = []
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                errors.append(f"records[{index}] must be an object")
                continue
            access_id = record.get("access_id")
            blind_id = record.get("blind_id")
            if not _nonempty(access_id) or not str(access_id).startswith("access-"):
                errors.append(f"records[{index}].access_id is invalid")
            else:
                access_ids.append(str(access_id))
            if not _nonempty(blind_id) or not str(blind_id).startswith("sample-"):
                errors.append(f"records[{index}].blind_id is invalid")
            else:
                blind_ids.append(str(blind_id))
            _scan_review_value(record, f"records[{index}]", errors)
        if len(access_ids) != len(set(access_ids)):
            errors.append("access_id values must be unique")
        if len(blind_ids) != len(set(blind_ids)):
            errors.append("blind_id values must be unique")
    return tuple(errors)


def redact_review_packet(
    sample_packet: Mapping[str, Any],
    *,
    redaction_seed: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a reviewer packet and separate protected locator access map."""

    if sample_packet.get("artifact_type") != "source-audit-sample-packet":
        raise SourceReviewError("input is not a source audit sample packet")
    packet_sha256 = _verify_self_hash(sample_packet, label="sample packet")
    if sample_packet.get("era_labels_hidden") is not True:
        raise SourceReviewError(
            "held-out review redaction requires an era-hidden sample packet"
        )
    if not _nonempty(redaction_seed):
        raise SourceReviewError("redaction_seed must not be empty")
    input_records = sample_packet.get("records")
    if not isinstance(input_records, list) or not input_records:
        raise SourceReviewError("sample packet contains no records")

    reviewer_records: list[dict[str, Any]] = []
    access_records: list[dict[str, Any]] = []
    for index, row in enumerate(input_records):
        if not isinstance(row, Mapping):
            raise SourceReviewError(f"sample record {index} is not an object")
        blind_id = row.get("blind_id")
        source_id = row.get("source_id")
        if not _nonempty(blind_id) or not _nonempty(source_id):
            raise SourceReviewError(
                f"sample record {index} lacks blind_id or source_id"
            )
        metadata_locator = row.get("metadata_locator")
        content_locator = row.get("content_locator")
        if metadata_locator is not None and not _nonempty(metadata_locator):
            raise SourceReviewError(
                f"sample record {index} metadata_locator is malformed"
            )
        if content_locator is not None and not _nonempty(content_locator):
            raise SourceReviewError(
                f"sample record {index} content_locator is malformed"
            )
        access_id = _access_id(
            redaction_seed,
            packet_sha256,
            str(blind_id),
            str(metadata_locator) if metadata_locator is not None else None,
            str(content_locator) if content_locator is not None else None,
        )
        reviewer_row = {
            key: value
            for key, value in row.items()
            if key not in _FORBIDDEN_REVIEW_KEYS
        }
        reviewer_row["access_id"] = access_id
        reviewer_row["access_available"] = bool(
            metadata_locator or content_locator
        )
        reviewer_records.append(reviewer_row)
        access_records.append(
            {
                "access_id": access_id,
                "blind_id": blind_id,
                "source_id": source_id,
                "metadata_locator": metadata_locator,
                "content_locator": content_locator,
            }
        )

    reviewer_packet: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "source-review-packet-redacted",
        "parent_sample_packet_sha256": packet_sha256,
        "metadata_sha256": sample_packet.get("metadata_sha256"),
        "seed": sample_packet.get("seed"),
        "era_labels_hidden": True,
        "locators_redacted": True,
        "records": reviewer_records,
    }
    reviewer_packet["output_sha256"] = canonical_json_sha256(reviewer_packet)

    access_map: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "source-review-access-map",
        "review_packet_sha256": reviewer_packet["output_sha256"],
        "parent_sample_packet_sha256": packet_sha256,
        "records": access_records,
    }
    access_map["output_sha256"] = canonical_json_sha256(access_map)

    errors = validate_redacted_review_packet(reviewer_packet)
    if errors:
        raise SourceReviewError("; ".join(errors))
    _verify_self_hash(access_map, label="access map")
    return reviewer_packet, access_map


def _parse_timestamp(raw: str) -> str:
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise SourceReviewError("accessed_at must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise SourceReviewError("accessed_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_access_event(event: Mapping[str, Any], *, label: str) -> str:
    keys = set(event)
    missing = sorted(_EVENT_KEYS - keys)
    extra = sorted(keys - _EVENT_KEYS)
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append("missing fields: " + ", ".join(missing))
        if extra:
            parts.append("unexpected fields: " + ", ".join(extra))
        raise SourceReviewError(f"{label} has invalid schema: " + "; ".join(parts))
    if event.get("schema_version") != 1:
        raise SourceReviewError(f"{label} schema_version must be 1")
    if event.get("artifact_type") != "source-review-access-event":
        raise SourceReviewError(f"{label} artifact_type is invalid")
    for field in (
        "access_map_sha256",
        "locator_sha256",
    ):
        value = event.get(field)
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise SourceReviewError(f"{label} {field} must be a lowercase SHA-256")
    for field in ("access_id", "blind_id", "source_id", "reviewer"):
        if not _nonempty(event.get(field)):
            raise SourceReviewError(f"{label} {field} must not be empty")
    if not str(event["access_id"]).startswith("access-"):
        raise SourceReviewError(f"{label} access_id is invalid")
    if not str(event["blind_id"]).startswith("sample-"):
        raise SourceReviewError(f"{label} blind_id is invalid")
    if event.get("locator_kind") not in _ALLOWED_LOCATOR_KINDS:
        raise SourceReviewError(f"{label} locator_kind is invalid")
    if event.get("purpose") not in _ALLOWED_PURPOSES:
        raise SourceReviewError(f"{label} purpose is invalid")
    outcome = event.get("outcome")
    if outcome not in _ALLOWED_OUTCOMES:
        raise SourceReviewError(f"{label} outcome is invalid")
    raw_accessed_at = event.get("accessed_at")
    if not _nonempty(raw_accessed_at):
        raise SourceReviewError(f"{label} accessed_at must not be empty")
    canonical_time = _parse_timestamp(str(raw_accessed_at))
    if canonical_time != raw_accessed_at:
        raise SourceReviewError(
            f"{label} accessed_at must be canonical UTC: {canonical_time}"
        )
    if event.get("source_text_recorded") is not False:
        raise SourceReviewError(f"{label} source_text_recorded must be false")

    response_hash = event.get("response_sha256")
    response_bytes = event.get("response_bytes")
    error_code = event.get("error_code")
    if response_hash is not None and (
        not isinstance(response_hash, str) or not _SHA256.fullmatch(response_hash)
    ):
        raise SourceReviewError(
            f"{label} response_sha256 must be a lowercase SHA-256 or null"
        )
    if response_bytes is not None and (
        not isinstance(response_bytes, int)
        or isinstance(response_bytes, bool)
        or response_bytes < 0
    ):
        raise SourceReviewError(
            f"{label} response_bytes must be a non-negative integer or null"
        )
    if error_code is not None and not _nonempty(error_code):
        raise SourceReviewError(f"{label} error_code must be nonempty or null")
    if (response_hash is None) != (response_bytes is None):
        raise SourceReviewError(
            f"{label} response_sha256 and response_bytes must appear together"
        )
    if outcome == "planned":
        if response_hash is not None or response_bytes is not None or error_code is not None:
            raise SourceReviewError(
                f"{label} planned outcome must not contain response or error data"
            )
    elif outcome == "succeeded":
        if response_hash is None or response_bytes is None:
            raise SourceReviewError(
                f"{label} successful outcome requires response hash and byte count"
            )
        if error_code is not None:
            raise SourceReviewError(
                f"{label} successful outcome must not contain error_code"
            )
    else:
        if error_code is None:
            raise SourceReviewError(f"{label} failed outcome requires error_code")

    return _verify_event_id(event, label=label)


def _find_access_record(
    access_map: Mapping[str, Any],
    access_id: str,
) -> Mapping[str, Any]:
    if access_map.get("artifact_type") != "source-review-access-map":
        raise SourceReviewError("invalid source-review access map")
    _verify_self_hash(access_map, label="access map")
    records = access_map.get("records")
    if not isinstance(records, list):
        raise SourceReviewError("access map has no records list")
    matches = [
        row
        for row in records
        if isinstance(row, Mapping) and row.get("access_id") == access_id
    ]
    if len(matches) != 1:
        raise SourceReviewError(
            f"access_id {access_id!r} must resolve exactly once"
        )
    return matches[0]


def build_access_event(
    access_map: Mapping[str, Any],
    *,
    access_id: str,
    locator_kind: str,
    reviewer: str,
    purpose: str,
    accessed_at: str,
    outcome: str,
    response_sha256: str | None = None,
    response_bytes: int | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Build a content-free, hashed operational access event."""

    if locator_kind not in _ALLOWED_LOCATOR_KINDS:
        raise SourceReviewError("locator_kind must be metadata or content")
    if purpose not in _ALLOWED_PURPOSES:
        raise SourceReviewError(f"unsupported access purpose: {purpose}")
    if outcome not in _ALLOWED_OUTCOMES:
        raise SourceReviewError(f"unsupported access outcome: {outcome}")
    if not _nonempty(reviewer):
        raise SourceReviewError("reviewer must not be empty")
    row = _find_access_record(access_map, access_id)
    locator = row.get(f"{locator_kind}_locator")
    if not _nonempty(locator):
        raise SourceReviewError(
            f"access_id {access_id!r} has no {locator_kind} locator"
        )
    if response_sha256 is not None and not _SHA256.fullmatch(response_sha256):
        raise SourceReviewError("response_sha256 must be a lowercase SHA-256")
    if response_bytes is not None and (
        not isinstance(response_bytes, int)
        or isinstance(response_bytes, bool)
        or response_bytes < 0
    ):
        raise SourceReviewError("response_bytes must be a non-negative integer")
    if outcome == "succeeded" and (
        response_sha256 is None or response_bytes is None
    ):
        raise SourceReviewError(
            "successful access requires response_sha256 and response_bytes"
        )
    if outcome == "failed" and not _nonempty(error_code):
        raise SourceReviewError("failed access requires error_code")
    if outcome == "planned" and any(
        value is not None for value in (response_sha256, response_bytes, error_code)
    ):
        raise SourceReviewError(
            "planned access must not include response or error data"
        )
    if outcome == "succeeded" and error_code is not None:
        raise SourceReviewError("successful access must not include error_code")
    if (response_sha256 is None) != (response_bytes is None):
        raise SourceReviewError(
            "response_sha256 and response_bytes must be provided together"
        )

    event: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "source-review-access-event",
        "access_map_sha256": access_map.get("output_sha256"),
        "access_id": access_id,
        "blind_id": row.get("blind_id"),
        "source_id": row.get("source_id"),
        "locator_kind": locator_kind,
        "locator_sha256": hashlib.sha256(
            str(locator).encode("utf-8")
        ).hexdigest(),
        "reviewer": reviewer,
        "purpose": purpose,
        "accessed_at": _parse_timestamp(accessed_at),
        "outcome": outcome,
        "response_sha256": response_sha256,
        "response_bytes": response_bytes,
        "error_code": error_code,
        "source_text_recorded": False,
    }
    event["event_id"] = "event-" + canonical_json_sha256(event)[:24]
    _validate_access_event(event, label="new access event")
    return event


def append_access_event(path: str | Path, event: Mapping[str, Any]) -> None:
    """Append one unique access event as canonical JSONL."""

    event_id = _validate_access_event(event, label="access event")
    destination = Path(path)
    existing_ids: set[str] = set()
    if destination.exists():
        for line_number, line in enumerate(
            destination.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError as error:
                raise SourceReviewError(
                    f"existing access log line {line_number} is invalid JSON"
                ) from error
            if not isinstance(existing, Mapping):
                raise SourceReviewError(
                    f"existing access log line {line_number} is not an object"
                )
            existing_id = _validate_access_event(
                existing,
                label=f"existing access log line {line_number}",
            )
            existing_ids.add(existing_id)
    if event_id in existing_ids:
        raise SourceReviewError(f"duplicate access event: {event_id}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        dict(event),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered + "\n")
