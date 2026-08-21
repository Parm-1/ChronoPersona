"""Source-neutral metadata records and deterministic audit sampling.

This module handles metadata only. It deliberately rejects embedded document
text so source qualification cannot silently become corpus acquisition.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


_RECORD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
_ALLOWED_TIMESTAMP_SEMANTICS = {
    "revision",
    "initial-post-version",
    "submission-version",
    "publication-version",
    "release-or-update-datestamp",
}
_ALLOWED_WINDOWS = {"early", "late", "outside", "unresolved"}
_ALLOWED_VERSION_STATUS = {
    "version-bounded",
    "single-version",
    "latest-only",
    "unresolved",
    "unavailable",
}
_ALLOWED_RIGHTS_STATUS = {
    "eligible",
    "conditional",
    "ineligible",
    "unresolved",
}
_ALLOWED_AUTHORSHIP = {
    "human",
    "mixed",
    "bot",
    "synthetic",
    "transformed",
    "unknown",
}
_ALLOWED_ELIGIBILITY = {"eligible", "excluded", "unresolved"}
FROZEN_ARXIV_PERSISTED_CATEGORIES = frozenset(
    {
        "astro-ph.CO",
        "astro-ph.EP",
        "astro-ph.GA",
        "astro-ph.HE",
        "astro-ph.IM",
        "astro-ph.SR",
        "cond-mat.mtrl-sci",
        "physics.atom-ph",
        "physics.chem-ph",
        "physics.optics",
        "forbidden-arxiv-category",
        "other-arxiv-category",
    }
)


def normalize_arxiv_categories(
    categories: Sequence[str],
    *,
    allowed_category_prefixes: Sequence[str],
    forbidden_category_prefixes: Sequence[str] = (),
) -> list[str]:
    """Return closed persisted labels without retaining arbitrary category text."""

    normalized: set[str] = set()
    for category in categories:
        if category in FROZEN_ARXIV_PERSISTED_CATEGORIES:
            normalized.add(category)
        elif any(
            category == prefix or category.startswith(prefix + ".")
            for prefix in allowed_category_prefixes
        ):
            raise ValueError("arXiv category inside the frozen stratum is unknown")
        elif any(
            category == prefix or category.startswith(prefix + ".")
            for prefix in forbidden_category_prefixes
        ):
            normalized.add("forbidden-arxiv-category")
        else:
            normalized.add("other-arxiv-category")
    return sorted(normalized)


def arxiv_category_evidence(categories: Sequence[str]) -> tuple[int, str]:
    """Return count and digest without retaining upstream category strings."""

    ordered = sorted(set(categories))
    payload = "\0".join(ordered).encode("utf-8")
    return len(ordered), hashlib.sha256(payload).hexdigest()
_ALLOWED_REVIEW_STRATA = {
    "eligible-random",
    "timestamp-boundary",
    "rights-boundary",
    "exposure-boundary",
    "high-concentration",
}
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


class SourceMetadataFormatError(ValueError):
    """Raised when source metadata JSONL cannot be parsed structurally."""


@dataclass(frozen=True)
class EraWindows:
    early_start: date
    early_end: date
    late_start: date
    late_end: date

    def classify(self, timestamp: datetime) -> str:
        day = timestamp.date()
        if self.early_start <= day <= self.early_end:
            return "early"
        if self.late_start <= day <= self.late_end:
            return "late"
        return "outside"


@dataclass(frozen=True)
class SampleTarget:
    source_id: str
    era_window: str
    review_stratum: str
    count: int


class SamplingPlanError(ValueError):
    """Raised when an audit sampling plan is invalid or infeasible."""


def load_source_metadata(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Load non-empty JSONL metadata records while preserving file order."""

    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise SourceMetadataFormatError(
                    f"line {line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(value, dict):
                raise SourceMetadataFormatError(
                    f"line {line_number}: every record must be an object"
                )
            records.append(value)
    if not records:
        raise SourceMetadataFormatError(
            "source metadata file must contain at least one record"
        )
    return tuple(records)


def canonical_json_sha256(value: Any) -> str:
    """Hash JSON-compatible content with a stable canonical rendering."""

    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash exact file bytes."""

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_era_windows(source_registry: Mapping[str, Any]) -> EraWindows:
    """Read the provisional/frozen era windows from the source registry."""

    raw = source_registry.get("provisional_era_windows")
    if not isinstance(raw, Mapping):
        raise SourceMetadataFormatError(
            "source registry lacks provisional_era_windows"
        )
    try:
        early = raw["early"]
        late = raw["late"]
        if not isinstance(early, Mapping) or not isinstance(late, Mapping):
            raise TypeError
        windows = EraWindows(
            early_start=date.fromisoformat(str(early["start"])),
            early_end=date.fromisoformat(str(early["end"])),
            late_start=date.fromisoformat(str(late["start"])),
            late_end=date.fromisoformat(str(late["end"])),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SourceMetadataFormatError(
            "source registry era windows are malformed"
        ) from error
    if windows.early_start > windows.early_end:
        raise SourceMetadataFormatError("early window start follows its end")
    if windows.late_start > windows.late_end:
        raise SourceMetadataFormatError("late window start follows its end")
    if windows.early_end >= windows.late_start:
        raise SourceMetadataFormatError(
            "early window must end before the late window begins"
        )
    return windows


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _string_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (not nonempty or bool(value))
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _forbidden_payload_keys(value: Any) -> list[str]:
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
    return sorted(found)


def validate_source_metadata(
    records: Sequence[Mapping[str, Any]],
    *,
    source_registry: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return all known metadata, rights, and eligibility errors."""

    errors: list[str] = []
    if not records:
        return ("source metadata must contain at least one record",)

    windows = parse_era_windows(source_registry)
    raw_sources = source_registry.get("sources")
    if not isinstance(raw_sources, list):
        return ("source registry sources must be a list",)
    known_sources = {
        source.get("id")
        for source in raw_sources
        if isinstance(source, Mapping)
    }
    record_ids: list[str] = []

    for index, record in enumerate(records):
        location = f"records[{index}]"
        if not isinstance(record, Mapping):
            errors.append(f"{location} must be an object")
            continue
        forbidden = _forbidden_payload_keys(record)
        if forbidden:
            errors.append(
                f"{location} contains forbidden text fields: "
                + ", ".join(forbidden)
            )

        if record.get("schema_version") != 1:
            errors.append(f"{location}.schema_version must be 1")

        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not _RECORD_ID.fullmatch(record_id):
            errors.append(f"{location}.record_id has invalid format")
        else:
            record_ids.append(record_id)

        source_id = record.get("source_id")
        if source_id not in known_sources:
            errors.append(f"{location}.source_id must reference the source registry")

        native_item_id = record.get("native_item_id")
        if not isinstance(native_item_id, str) or not native_item_id.strip():
            errors.append(f"{location}.native_item_id must not be empty")

        semantics = record.get("timestamp_semantics")
        if semantics not in _ALLOWED_TIMESTAMP_SEMANTICS:
            errors.append(
                f"{location}.timestamp_semantics must be one of "
                + ", ".join(sorted(_ALLOWED_TIMESTAMP_SEMANTICS))
            )
        timestamp = _parse_timestamp(record.get("native_timestamp"))
        if timestamp is None:
            errors.append(
                f"{location}.native_timestamp must be timezone-aware ISO-8601"
            )
        era_window = record.get("era_window")
        if era_window not in _ALLOWED_WINDOWS:
            errors.append(
                f"{location}.era_window must be one of "
                + ", ".join(sorted(_ALLOWED_WINDOWS))
            )
        elif timestamp is not None and era_window != "unresolved":
            expected = windows.classify(timestamp)
            if era_window != expected:
                errors.append(
                    f"{location}.era_window={era_window!r} does not match "
                    f"timestamp classification {expected!r}"
                )

        version_status = record.get("version_status")
        if version_status not in _ALLOWED_VERSION_STATUS:
            errors.append(
                f"{location}.version_status must be one of "
                + ", ".join(sorted(_ALLOWED_VERSION_STATUS))
            )
        version_count = record.get("version_count")
        if not isinstance(version_count, int) or isinstance(version_count, bool):
            errors.append(f"{location}.version_count must be an integer")
        elif version_count < 1:
            errors.append(f"{location}.version_count must be positive")
        if version_status == "single-version" and version_count != 1:
            errors.append(
                f"{location} single-version status requires version_count=1"
            )

        rights_status = record.get("rights_status")
        if rights_status not in _ALLOWED_RIGHTS_STATUS:
            errors.append(
                f"{location}.rights_status must be one of "
                + ", ".join(sorted(_ALLOWED_RIGHTS_STATUS))
            )
        for field in ("license_id", "license_locator"):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{location}.{field} must not be empty")

        provenance = record.get("authorship_provenance")
        if provenance not in _ALLOWED_AUTHORSHIP:
            errors.append(
                f"{location}.authorship_provenance must be one of "
                + ", ".join(sorted(_ALLOWED_AUTHORSHIP))
            )

        if not _string_list(record.get("categories")):
            errors.append(f"{location}.categories must be a string list")
        if not _string_list(record.get("review_strata"), nonempty=True):
            errors.append(
                f"{location}.review_strata must be a non-empty string list"
            )
        else:
            invalid_strata = set(record["review_strata"]) - _ALLOWED_REVIEW_STRATA
            if invalid_strata:
                errors.append(
                    f"{location}.review_strata contains invalid values: "
                    + ", ".join(sorted(invalid_strata))
                )

        for field in ("metadata_locator", "content_locator"):
            value = record.get(field)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                errors.append(
                    f"{location}.{field} must be null or a non-empty string"
                )
        if record.get("content_retrieved") is not False:
            errors.append(
                f"{location}.content_retrieved must remain false in metadata audits"
            )

        eligibility = record.get("eligibility")
        if eligibility not in _ALLOWED_ELIGIBILITY:
            errors.append(
                f"{location}.eligibility must be one of "
                + ", ".join(sorted(_ALLOWED_ELIGIBILITY))
            )
        exclusion_reasons = record.get("exclusion_reasons")
        if not _string_list(exclusion_reasons):
            errors.append(
                f"{location}.exclusion_reasons must be a string list"
            )
        if eligibility == "eligible":
            if exclusion_reasons:
                errors.append(
                    f"{location} eligible record must not have exclusion reasons"
                )
            if era_window not in {"early", "late"}:
                errors.append(
                    f"{location} eligible record must belong to early or late window"
                )
            if rights_status != "eligible":
                errors.append(
                    f"{location} eligible record requires rights_status='eligible'"
                )
            if version_status not in {"version-bounded", "single-version"}:
                errors.append(
                    f"{location} eligible record requires historically bounded text"
                )
            if provenance != "human":
                errors.append(
                    f"{location} eligible record requires human authorship provenance"
                )
        elif eligibility == "excluded" and not exclusion_reasons:
            errors.append(
                f"{location} excluded record requires an exclusion reason"
            )

        extra = record.get("source_metadata")
        if not isinstance(extra, Mapping):
            errors.append(f"{location}.source_metadata must be an object")

    if len(record_ids) != len(set(record_ids)):
        errors.append("record_id values must be unique")
    return tuple(errors)


def summarize_source_metadata(
    records: Sequence[Mapping[str, Any]],
    *,
    metadata_sha256: str,
) -> dict[str, Any]:
    """Produce deterministic aggregate counts without exposing source text."""

    if not isinstance(metadata_sha256, str) or not metadata_sha256:
        raise ValueError("metadata_sha256 must not be empty")
    counts = {
        "source": Counter(),
        "window": Counter(),
        "eligibility": Counter(),
        "rights": Counter(),
        "version_status": Counter(),
        "authorship": Counter(),
        "review_stratum": Counter(),
    }
    by_source_window: Counter[tuple[str, str]] = Counter()
    for record in records:
        source_id = str(record["source_id"])
        window = str(record["era_window"])
        counts["source"][source_id] += 1
        counts["window"][window] += 1
        counts["eligibility"][str(record["eligibility"])] += 1
        counts["rights"][str(record["rights_status"])] += 1
        counts["version_status"][str(record["version_status"])] += 1
        counts["authorship"][str(record["authorship_provenance"])] += 1
        by_source_window[(source_id, window)] += 1
        for stratum in record["review_strata"]:
            counts["review_stratum"][str(stratum)] += 1

    output: dict[str, Any] = {
        "schema_version": 1,
        "audit_type": "source-metadata-summary",
        "metadata_sha256": metadata_sha256,
        "record_count": len(records),
        "counts": {
            key: dict(sorted(counter.items()))
            for key, counter in counts.items()
        },
        "source_window_counts": [
            {
                "source_id": source_id,
                "era_window": window,
                "count": count,
            }
            for (source_id, window), count in sorted(by_source_window.items())
        ],
    }
    output["output_sha256"] = canonical_json_sha256(output)
    return output


def _sample_rank(seed: str, record_id: str, stratum: str) -> str:
    return hashlib.sha256(
        f"{seed}\0{stratum}\0{record_id}".encode("utf-8")
    ).hexdigest()


def _blind_id(seed: str, record_id: str) -> str:
    return "sample-" + hashlib.sha256(
        f"blind\0{seed}\0{record_id}".encode("utf-8")
    ).hexdigest()[:20]


def deterministic_audit_sample(
    records: Sequence[Mapping[str, Any]],
    targets: Sequence[SampleTarget],
    *,
    seed: str,
    metadata_sha256: str,
    hide_era_labels: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a blinded packet and separate unblinding key.

    A record can be selected only once. More specific boundary strata should
    therefore appear before ``eligible-random`` in the target list.
    """

    if not isinstance(seed, str) or not seed:
        raise SamplingPlanError("seed must not be empty")
    if not isinstance(metadata_sha256, str) or not metadata_sha256:
        raise SamplingPlanError("metadata_sha256 must not be empty")
    if not targets:
        raise SamplingPlanError("at least one sampling target is required")

    pools: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        for stratum in record["review_strata"]:
            pools[(
                str(record["source_id"]),
                str(record["era_window"]),
                str(stratum),
            )].append(record)

    selected_ids: set[str] = set()
    packet_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    target_results: list[dict[str, Any]] = []

    for target in targets:
        if target.era_window not in {"early", "late"}:
            raise SamplingPlanError(
                "sampling targets must use early or late era windows"
            )
        if target.review_stratum not in _ALLOWED_REVIEW_STRATA:
            raise SamplingPlanError(
                f"invalid review stratum: {target.review_stratum}"
            )
        if target.count < 0:
            raise SamplingPlanError("target count must not be negative")

        candidates = [
            record
            for record in pools.get(
                (target.source_id, target.era_window, target.review_stratum),
                [],
            )
            if str(record["record_id"]) not in selected_ids
        ]
        candidates.sort(
            key=lambda record: (
                _sample_rank(
                    seed,
                    str(record["record_id"]),
                    target.review_stratum,
                ),
                str(record["record_id"]),
            )
        )
        chosen = candidates[: target.count]
        if len(chosen) < target.count:
            raise SamplingPlanError(
                f"insufficient records for {target.source_id}/"
                f"{target.era_window}/{target.review_stratum}: "
                f"requested {target.count}, available {len(chosen)}"
            )

        for record in chosen:
            record_id = str(record["record_id"])
            selected_ids.add(record_id)
            blind_id = _blind_id(seed, record_id)
            packet_row: dict[str, Any] = {
                "blind_id": blind_id,
                "source_id": record["source_id"],
                "review_stratum": target.review_stratum,
                "metadata_locator": record["metadata_locator"],
                "content_locator": record["content_locator"],
                "categories": record["categories"],
                "version_status": record["version_status"],
                "rights_status": record["rights_status"],
                "authorship_provenance": record["authorship_provenance"],
                "source_metadata": record["source_metadata"],
            }
            if not hide_era_labels:
                packet_row["era_window"] = record["era_window"]
                packet_row["native_timestamp"] = record["native_timestamp"]
            packet_rows.append(packet_row)
            key_rows.append(
                {
                    "blind_id": blind_id,
                    "record_id": record_id,
                    "source_id": record["source_id"],
                    "native_item_id": record["native_item_id"],
                    "era_window": record["era_window"],
                    "native_timestamp": record["native_timestamp"],
                }
            )

        target_results.append(
            {
                "source_id": target.source_id,
                "era_window": target.era_window,
                "review_stratum": target.review_stratum,
                "requested": target.count,
                "selected": len(chosen),
            }
        )

    packet: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "source-audit-sample-packet",
        "metadata_sha256": metadata_sha256,
        "seed": seed,
        "era_labels_hidden": hide_era_labels,
        "targets": target_results,
        "records": packet_rows,
    }
    packet["output_sha256"] = canonical_json_sha256(packet)

    unblinding_key: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "source-audit-unblinding-key",
        "metadata_sha256": metadata_sha256,
        "sample_packet_sha256": packet["output_sha256"],
        "seed": seed,
        "records": key_rows,
    }
    unblinding_key["output_sha256"] = canonical_json_sha256(unblinding_key)
    return packet, unblinding_key
