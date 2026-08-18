"""Validate content-bearing manifests without committing corpus text to Git.

The manifest is source-neutral. Text remains in separate files and every byte,
normalization, role, right, holdout, and eligibility assertion is recomputed
before an integrity audit can run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from .path_policy import (
    PortablePathError,
    portable_path_identity,
    portable_relative_path,
)


_RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_WORD = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_ALLOWED_ROLES = {"adaptation", "evaluation", "control", "calibration"}
_ALLOWED_FAMILIES = {"A", "B", "C", "EVAL", "CONTROL", "CAL"}
_ALLOWED_ERAS = {"early", "late", "none"}
_ALLOWED_HOLDOUT = {"exploratory", "confirmatory-held-out", "not-applicable"}
_ALLOWED_RIGHTS = {"eligible", "conditional", "ineligible", "unresolved"}
_ALLOWED_AUTHORSHIP = {
    "human",
    "synthetic-fixture",
    "synthetic",
    "mixed",
    "transformed",
    "unknown",
}
_ALLOWED_ELIGIBILITY = {"candidate", "eligible", "excluded", "unresolved"}
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
DEFAULT_MAX_CONTENT_RECORDS = 2_000
DEFAULT_MAX_RECORD_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_TOTAL_CONTENT_BYTES = 64 * 1024 * 1024


_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "record_id",
        "role",
        "source_family",
        "source_id",
        "era_window",
        "holdout_status",
        "content_path",
        "content_sha256",
        "normalized_sha256",
        "content_bytes",
        "word_count",
        "license_id",
        "rights_status",
        "authorship_provenance",
        "synthetic_fixture",
        "eligibility",
        "exclusion_reasons",
        "metadata",
    }
)


class ContentManifestError(ValueError):
    """Raised when manifest or content integrity cannot be established."""


@dataclass(frozen=True)
class LoadedContentRecord:
    manifest: dict[str, Any]
    content_path: Path
    text: str
    normalized_text: str
    tokens: tuple[str, ...]


def canonical_json_sha256(value: Any) -> str:
    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ContentManifestError(f"value is not canonical JSON: {error}") from error
    return hashlib.sha256(rendered).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokenize_normalized(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(match.group(0) for match in _WORD.finditer(normalized))


def normalize_text(text: str) -> str:
    return " ".join(tokenize_normalized(text))


def normalized_sha256(text: str) -> str:
    return sha256_bytes(normalize_text(text).encode("utf-8"))


def load_content_manifest(
    path: str | Path,
    *,
    max_records: int = DEFAULT_MAX_CONTENT_RECORDS,
) -> tuple[dict[str, Any], ...]:
    if (
        not isinstance(max_records, int)
        or isinstance(max_records, bool)
        or max_records < 1
    ):
        raise ContentManifestError("max_records must be a positive integer")

    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line_number > max_records:
                raise ContentManifestError(
                    f"content manifest exceeds max_records={max_records}"
                )
            stripped = line.strip()
            if not stripped:
                raise ContentManifestError(
                    f"content manifest contains blank line {line_number}"
                )
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise ContentManifestError(
                    f"line {line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(value, dict):
                raise ContentManifestError(
                    f"line {line_number}: every record must be an object"
                )
            records.append(value)
    if not records:
        raise ContentManifestError("content manifest must not be empty")
    return tuple(records)


def _forbidden_fields(value: Mapping[str, Any]) -> tuple[str, ...]:
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


def _safe_content_path(content_root: Path, raw_path: Any) -> Path:
    try:
        relative = portable_relative_path(raw_path, label="content_path")
    except PortablePathError as error:
        raise ContentManifestError(str(error)) from error
    root = content_root.resolve()
    candidate = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ContentManifestError("content path must not contain symbolic links")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ContentManifestError("content_path escapes content root") from error
    if not resolved.is_file():
        raise ContentManifestError(f"content file not found: {relative.as_posix()}")
    return resolved


def _read_utf8(path: Path, *, max_bytes: int) -> tuple[bytes, str]:
    with path.open("rb") as handle:
        payload = handle.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ContentManifestError(
            f"content file exceeds max_record_bytes={max_bytes}: {path}"
        )
    if not payload:
        raise ContentManifestError(f"content file is empty: {path}")
    if b"\x00" in payload:
        raise ContentManifestError(f"content file contains NUL bytes: {path}")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContentManifestError(f"content file is not UTF-8: {path}") from error
    if not text.strip():
        raise ContentManifestError(f"content file has no visible text: {path}")
    return payload, text


def validate_content_manifest_structure(
    records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    errors: list[str] = []
    record_ids: list[str] = []
    content_paths: list[str] = []
    content_path_identities: list[tuple[str, ...]] = []
    if not records:
        return ("content manifest must not be empty",)

    for index, record in enumerate(records):
        location = f"records[{index}]"
        if not isinstance(record, Mapping):
            errors.append(f"{location} must be an object")
            continue
        if set(record) != _REQUIRED_FIELDS:
            missing = sorted(_REQUIRED_FIELDS - set(record))
            extra = sorted(set(record) - _REQUIRED_FIELDS)
            errors.append(
                f"{location} fields mismatch; missing={missing}, extra={extra}"
            )
            continue
        if record.get("schema_version") != 1:
            errors.append(f"{location}.schema_version must be 1")
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not _RECORD_ID.fullmatch(record_id):
            errors.append(f"{location}.record_id has invalid format")
        else:
            record_ids.append(record_id)
        role = record.get("role")
        family = record.get("source_family")
        era = record.get("era_window")
        holdout = record.get("holdout_status")
        if role not in _ALLOWED_ROLES:
            errors.append(f"{location}.role is invalid")
        if family not in _ALLOWED_FAMILIES:
            errors.append(f"{location}.source_family is invalid")
        if era not in _ALLOWED_ERAS:
            errors.append(f"{location}.era_window is invalid")
        if holdout not in _ALLOWED_HOLDOUT:
            errors.append(f"{location}.holdout_status is invalid")
        if not isinstance(record.get("source_id"), str) or not record["source_id"].strip():
            errors.append(f"{location}.source_id must not be empty")
        content_path = record.get("content_path")
        try:
            portable_relative_path(
                content_path,
                label=f"{location}.content_path",
            )
            content_path_identities.append(
                portable_path_identity(
                    content_path,
                    label=f"{location}.content_path",
                )
            )
        except PortablePathError as error:
            errors.append(str(error))
        if isinstance(content_path, str) and content_path:
            content_paths.append(content_path)
        for field in ("content_sha256", "normalized_sha256"):
            value = record.get(field)
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                errors.append(f"{location}.{field} must be lowercase SHA-256")
        content_bytes = record.get("content_bytes")
        word_count = record.get("word_count")
        if not isinstance(content_bytes, int) or isinstance(content_bytes, bool) or content_bytes < 1:
            errors.append(f"{location}.content_bytes must be positive integer")
        if not isinstance(word_count, int) or isinstance(word_count, bool) or word_count < 1:
            errors.append(f"{location}.word_count must be positive integer")
        if not isinstance(record.get("license_id"), str) or not record["license_id"].strip():
            errors.append(f"{location}.license_id must not be empty")
        if record.get("rights_status") not in _ALLOWED_RIGHTS:
            errors.append(f"{location}.rights_status is invalid")
        authorship = record.get("authorship_provenance")
        synthetic_fixture = record.get("synthetic_fixture")
        if authorship not in _ALLOWED_AUTHORSHIP:
            errors.append(f"{location}.authorship_provenance is invalid")
        if not isinstance(synthetic_fixture, bool):
            errors.append(f"{location}.synthetic_fixture must be boolean")
        elif synthetic_fixture and authorship != "synthetic-fixture":
            errors.append(
                f"{location} synthetic fixture requires synthetic-fixture authorship"
            )
        elif not synthetic_fixture and authorship == "synthetic-fixture":
            errors.append(
                f"{location} synthetic-fixture authorship requires synthetic_fixture=true"
            )
        eligibility = record.get("eligibility")
        reasons = record.get("exclusion_reasons")
        if eligibility not in _ALLOWED_ELIGIBILITY:
            errors.append(f"{location}.eligibility is invalid")
        if not isinstance(reasons, list) or not all(
            isinstance(reason, str) and reason.strip() for reason in reasons
        ):
            errors.append(f"{location}.exclusion_reasons must be a string list")
            reasons = []
        if eligibility == "eligible" and reasons:
            errors.append(f"{location} eligible record cannot have exclusion reasons")
        if eligibility == "excluded" and not reasons:
            errors.append(f"{location} excluded record requires exclusion reasons")
        if record.get("synthetic_fixture") is True and eligibility == "eligible":
            errors.append(f"{location} synthetic fixture cannot be scientifically eligible")
        metadata = record.get("metadata")
        if not isinstance(metadata, Mapping):
            errors.append(f"{location}.metadata must be an object")
        elif _forbidden_fields(metadata):
            errors.append(f"{location}.metadata contains forbidden text fields")

        if role == "adaptation":
            if family not in {"A", "B", "C"}:
                errors.append(f"{location} adaptation role requires A/B/C family")
            if era not in {"early", "late"}:
                errors.append(f"{location} adaptation role requires early/late era")
            if family == "C" and holdout != "confirmatory-held-out":
                errors.append(f"{location} source C must be confirmatory-held-out")
            if family in {"A", "B"} and holdout != "exploratory":
                errors.append(f"{location} source A/B must be exploratory")
            if eligibility == "eligible":
                if record.get("rights_status") != "eligible":
                    errors.append(f"{location} eligible adaptation requires eligible rights")
                if record.get("authorship_provenance") != "human":
                    errors.append(f"{location} eligible adaptation requires human authorship")
        elif role == "evaluation":
            if family != "EVAL" or era != "none" or holdout != "not-applicable":
                errors.append(
                    f"{location} evaluation role requires EVAL/none/not-applicable"
                )
        elif role == "control":
            if family != "CONTROL" or era != "none" or holdout != "not-applicable":
                errors.append(
                    f"{location} control role requires CONTROL/none/not-applicable"
                )
        elif role == "calibration":
            if family != "CAL" or era != "none" or holdout != "not-applicable":
                errors.append(
                    f"{location} calibration role requires CAL/none/not-applicable"
                )

    if len(record_ids) != len(set(record_ids)):
        errors.append("record_id values must be unique")
    if len(content_paths) != len(set(content_paths)):
        errors.append("content_path values must be unique")
    if len(content_path_identities) != len(set(content_path_identities)):
        errors.append(
            "content_path values must be unique under portable filesystem semantics"
        )
    return tuple(errors)


def resolve_content_records(
    records: Sequence[Mapping[str, Any]],
    *,
    content_root: str | Path,
    max_records: int = DEFAULT_MAX_CONTENT_RECORDS,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    max_total_content_bytes: int = DEFAULT_MAX_TOTAL_CONTENT_BYTES,
) -> tuple[LoadedContentRecord, ...]:
    errors = validate_content_manifest_structure(records)
    if errors:
        raise ContentManifestError("; ".join(errors))
    for label, value in (
        ("max_records", max_records),
        ("max_record_bytes", max_record_bytes),
        ("max_total_content_bytes", max_total_content_bytes),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ContentManifestError(f"{label} must be a positive integer")
    if max_total_content_bytes < max_record_bytes:
        raise ContentManifestError(
            "max_total_content_bytes must be at least max_record_bytes"
        )
    if len(records) > max_records:
        raise ContentManifestError(
            f"content manifest has {len(records)} records, exceeding "
            f"max_records={max_records}"
        )
    declared_sizes = [int(record["content_bytes"]) for record in records]
    oversized = next(
        (
            (index, size)
            for index, size in enumerate(declared_sizes)
            if size > max_record_bytes
        ),
        None,
    )
    if oversized is not None:
        index, size = oversized
        raise ContentManifestError(
            f"records[{index}].content_bytes={size} exceeds "
            f"max_record_bytes={max_record_bytes}"
        )
    declared_total = sum(declared_sizes)
    if declared_total > max_total_content_bytes:
        raise ContentManifestError(
            f"declared content bytes {declared_total} exceed "
            f"max_total_content_bytes={max_total_content_bytes}"
        )

    root = Path(content_root)
    loaded: list[LoadedContentRecord] = []
    observed_total = 0
    for index, raw_record in enumerate(records):
        record = dict(raw_record)
        try:
            path = _safe_content_path(root, record["content_path"])
            file_size = path.stat().st_size
            if file_size > max_record_bytes:
                raise ContentManifestError(
                    f"content file declares {file_size} bytes, exceeding "
                    f"max_record_bytes={max_record_bytes}: {path}"
                )
            if observed_total + file_size > max_total_content_bytes:
                raise ContentManifestError(
                    "observed content size would exceed "
                    f"max_total_content_bytes={max_total_content_bytes}"
                )
            payload, text = _read_utf8(path, max_bytes=max_record_bytes)
            observed_total += len(payload)
            if observed_total > max_total_content_bytes:
                raise ContentManifestError(
                    f"observed content bytes {observed_total} exceed "
                    f"max_total_content_bytes={max_total_content_bytes}"
                )
        except (ContentManifestError, OSError) as error:
            raise ContentManifestError(f"records[{index}]: {error}") from error
        tokens = tokenize_normalized(text)
        if not tokens:
            raise ContentManifestError(
                f"records[{index}] normalizes to zero words"
            )
        observed = {
            "content_sha256": sha256_bytes(payload),
            "normalized_sha256": sha256_bytes(" ".join(tokens).encode("utf-8")),
            "content_bytes": len(payload),
            "word_count": len(tokens),
        }
        for field, value in observed.items():
            if record[field] != value:
                raise ContentManifestError(
                    f"records[{index}].{field} mismatch: "
                    f"manifest={record[field]!r}, observed={value!r}"
                )
        loaded.append(
            LoadedContentRecord(
                manifest=record,
                content_path=path,
                text=text,
                normalized_text=" ".join(tokens),
                tokens=tokens,
            )
        )
    return tuple(loaded)


def describe_content_manifest(records: Sequence[Mapping[str, Any]]) -> str:
    roles: dict[str, int] = {}
    families: dict[str, int] = {}
    for record in records:
        role = str(record.get("role"))
        family = str(record.get("source_family"))
        roles[role] = roles.get(role, 0) + 1
        families[family] = families.get(family, 0) + 1
    return (
        f"{len(records)} records; roles={json.dumps(roles, sort_keys=True)}; "
        f"families={json.dumps(families, sort_keys=True)}"
    )
