"""Validate ChronoPersona source-candidate and A/B/C assignment records."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
from typing import Any


_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ALLOWED_ROLES = {
    "exploratory",
    "held-out-confirmatory",
    "backup-confirmatory",
    "boundary-control",
    "rejected-headline",
}
_ALLOWED_STATUSES = {
    "candidate",
    "qualified-with-redesign",
    "blocked",
    "rejected-headline",
}
_ALLOWED_RIGHTS = {"clear", "conditional", "unresolved"}
_ALLOWED_EXPOSURE = {
    "direct",
    "structurally-related",
    "indirect",
    "plausibly-absent",
    "unknown",
}
_PRIMARY_DOMAINS = {
    "evidence-integration",
    "procedural-tradeoffs",
}
_REQUIRED_HOLDOUT_PROHIBITIONS = {
    "hypothesis-direction",
    "evaluation-item-construction",
    "dose-selection",
    "threshold-selection",
    "hyperparameter-selection",
    "mechanistic-layer-selection",
}


class SourceRegistryFormatError(ValueError):
    """Raised when a source registry is not structurally readable."""


def load_source_registry(path: str | Path) -> Mapping[str, Any]:
    """Load a JSON source registry."""

    with open(path, "r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise SourceRegistryFormatError("source registry root must be an object")
    return value


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        _nonempty_string(item) for item in value
    )


def validate_source_registry(registry: Mapping[str, Any]) -> tuple[str, ...]:
    """Return all known assignment, rights, timestamp, and holdout errors."""

    errors: list[str] = []
    if registry.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if registry.get("behavioral_outcomes_inspected") is not False:
        errors.append(
            "behavioral_outcomes_inspected must remain false during source selection"
        )
    if registry.get("bulk_download_authorized") is not False:
        errors.append(
            "bulk_download_authorized must remain false during the Stage 0 audit"
        )

    raw_sources = registry.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        errors.append("sources must be a non-empty list")
        return tuple(errors)

    source_ids: list[str] = []
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, source in enumerate(raw_sources):
        location = f"sources[{index}]"
        if not isinstance(source, Mapping):
            errors.append(f"{location} must be an object")
            continue

        source_id = source.get("id")
        if not _nonempty_string(source_id) or not _ID.fullmatch(source_id):
            errors.append(
                f"{location}.id must be a lowercase hyphenated slug"
            )
            source_label = location
        else:
            source_ids.append(source_id)
            by_id[source_id] = source
            source_label = f"source {source_id!r}"

        if source.get("role") not in _ALLOWED_ROLES:
            errors.append(
                f"{source_label} role must be one of "
                + ", ".join(sorted(_ALLOWED_ROLES))
            )
        if source.get("status") not in _ALLOWED_STATUSES:
            errors.append(
                f"{source_label} status must be one of "
                + ", ".join(sorted(_ALLOWED_STATUSES))
            )
        for field in (
            "title",
            "steward",
            "proposed_stratum",
            "timestamp_semantics",
            "version_integrity",
            "authorship_provenance",
        ):
            if not _nonempty_string(source.get(field)):
                errors.append(f"{source_label} {field} must not be empty")

        if not _string_list(source.get("official_sources")):
            errors.append(
                f"{source_label} official_sources must be a non-empty string list"
            )
        if not _string_list(source.get("approved_access_paths")):
            errors.append(
                f"{source_label} approved_access_paths must be a string list"
            )
        if not _string_list(source.get("blockers")):
            errors.append(f"{source_label} blockers must be a string list")

        if source.get("native_timestamp") is not True:
            errors.append(f"{source_label} must have a native timestamp")
        if source.get("supports_early_window") is not True:
            errors.append(f"{source_label} does not support the early window")
        if source.get("supports_late_window") is not True:
            errors.append(f"{source_label} does not support the late window")
        if source.get("metadata_only_first") is not True:
            errors.append(
                f"{source_label} must use metadata-only qualification first"
            )

        rights = source.get("rights")
        rights_status: str | None = None
        if not isinstance(rights, Mapping):
            errors.append(f"{source_label} rights must be an object")
        else:
            rights_status = rights.get("status")
            if rights_status not in _ALLOWED_RIGHTS:
                errors.append(
                    f"{source_label} rights.status must be clear, conditional, or unresolved"
                )
            for field in (
                "license_policy",
                "attribution_policy",
                "redistribution_policy",
                "model_release_boundary",
            ):
                if not _nonempty_string(rights.get(field)):
                    errors.append(
                        f"{source_label} rights.{field} must not be empty"
                    )

        exposure = source.get("domain_exposure")
        if not isinstance(exposure, Mapping):
            errors.append(
                f"{source_label} domain_exposure must be an object"
            )
        else:
            missing_domains = _PRIMARY_DOMAINS - set(exposure)
            if missing_domains:
                errors.append(
                    f"{source_label} missing primary domain exposure: "
                    + ", ".join(sorted(missing_domains))
                )
            for domain, level in exposure.items():
                if level not in _ALLOWED_EXPOSURE:
                    errors.append(
                        f"{source_label} exposure {domain!r} must be one of "
                        + ", ".join(sorted(_ALLOWED_EXPOSURE))
                    )

        held_out = source.get("held_out")
        if not isinstance(held_out, bool):
            errors.append(f"{source_label} held_out must be boolean")
        prohibitions = source.get("holdout_prohibitions")
        if held_out is True:
            if source.get("role") not in {
                "held-out-confirmatory",
                "backup-confirmatory",
            }:
                errors.append(
                    f"{source_label} held-out source must have a confirmatory role"
                )
            if not _string_list(prohibitions):
                errors.append(
                    f"{source_label} holdout_prohibitions must be a string list"
                )
            else:
                missing = _REQUIRED_HOLDOUT_PROHIBITIONS - set(prohibitions)
                if missing:
                    errors.append(
                        f"{source_label} missing holdout prohibitions: "
                        + ", ".join(sorted(missing))
                    )
        elif prohibitions not in (None, []):
            errors.append(
                f"{source_label} non-held-out source must not define holdout prohibitions"
            )

        if source.get("role") in {
            "exploratory",
            "held-out-confirmatory",
        }:
            if source.get("status") != "qualified-with-redesign":
                errors.append(
                    f"{source_label} assigned source must be qualified-with-redesign"
                )
            if rights_status == "unresolved":
                errors.append(
                    f"{source_label} assigned source cannot have unresolved rights"
                )
            if isinstance(exposure, Mapping) and any(
                exposure.get(domain) == "direct"
                for domain in _PRIMARY_DOMAINS
            ):
                errors.append(
                    f"{source_label} assigned source cannot directly expose a primary domain"
                )

    if len(source_ids) != len(set(source_ids)):
        errors.append("source ids must be unique")

    assignments = registry.get("assignments")
    if not isinstance(assignments, Mapping):
        errors.append("assignments must be an object")
    else:
        if set(assignments) != {"A", "B", "C"}:
            errors.append("assignments must contain exactly A, B, and C")
        assigned_ids: list[str] = []
        for family in ("A", "B", "C"):
            source_id = assignments.get(family)
            if not _nonempty_string(source_id) or source_id not in by_id:
                errors.append(
                    f"assignments.{family} must reference a known source id"
                )
                continue
            assigned_ids.append(source_id)
            source = by_id[source_id]
            expected_role = (
                "held-out-confirmatory" if family == "C" else "exploratory"
            )
            if source.get("role") != expected_role:
                errors.append(
                    f"assignments.{family} source must have role {expected_role!r}"
                )
            if (family == "C") != (source.get("held_out") is True):
                errors.append(
                    f"assignments.{family} held_out status is inconsistent"
                )
        if len(assigned_ids) != len(set(assigned_ids)):
            errors.append("A, B, and C assignments must be distinct")

    backup_id = registry.get("predeclared_backup_c")
    if not _nonempty_string(backup_id) or backup_id not in by_id:
        errors.append(
            "predeclared_backup_c must reference a known source id"
        )
    else:
        backup = by_id[backup_id]
        if backup.get("role") != "backup-confirmatory":
            errors.append(
                "predeclared_backup_c must have role 'backup-confirmatory'"
            )
        if backup.get("held_out") is not True:
            errors.append("predeclared_backup_c must remain held out")

    return tuple(errors)


def describe_source_registry(registry: Mapping[str, Any]) -> str:
    """Return a compact source-registry summary."""

    sources = registry.get("sources", [])
    assignments = registry.get("assignments", {})
    assigned = ", ".join(
        f"{family}={assignments.get(family)}" for family in ("A", "B", "C")
    )
    return f"{len(sources)} candidates; {assigned}"
