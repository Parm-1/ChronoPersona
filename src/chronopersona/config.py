"""Load and validate ChronoPersona experiment specifications."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import os
from pathlib import PurePosixPath
import re
import tomllib
from typing import Any


_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SOURCE_FAMILY = re.compile(r"^[A-Z][A-Z0-9-]*$")
_VALID_ROLES = {"temporal", "control"}
_VALID_ERAS = {"early", "late"}
_VALID_STATUSES = {"design", "frozen", "running", "complete"}
_REQUIRED_CONTROLS = {
    "unadapted",
    "generic_continuation",
    "mixed_era",
    "within_era_placebo",
}


class SpecFormatError(ValueError):
    """Raised when a TOML file cannot be converted into a specification."""


@dataclass(frozen=True)
class Condition:
    id: str
    role: str
    manifest: str | None = None
    era: str | None = None
    source_family: str | None = None
    window_start: str | None = None
    window_end: str | None = None
    control_type: str | None = None


@dataclass(frozen=True)
class Evaluation:
    registry: str
    primary_families: tuple[str, ...]
    secondary_families: tuple[str, ...]
    held_out_source_family: str
    blinded: bool
    frozen_before_training: bool


@dataclass(frozen=True)
class ResourceConstraints:
    external_spend_cad: int
    external_compute_requires_user_authorization: bool
    training_requires_measured_benchmark: bool
    calibration_required_before_naturalistic_interpretation: bool
    max_parallel_training_jobs: int


@dataclass(frozen=True)
class ExperimentSpec:
    schema_version: int
    id: str
    title: str
    stage: str
    status: str
    base_model: str
    insertion_point: str
    adaptation_method: str
    token_budget: int
    seeds: tuple[int, ...]
    conditions: tuple[Condition, ...]
    evaluation: Evaluation
    resources: ResourceConstraints
    output_dir: str
    publish_negative_results: bool


def _table(value: Any, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpecFormatError(f"{location} must be a TOML table")
    return value


def _required(
    table: Mapping[str, Any],
    key: str,
    expected: type,
    location: str,
) -> Any:
    if key not in table:
        raise SpecFormatError(f"missing required field: {location}.{key}")
    value = table[key]
    valid = isinstance(value, expected)
    if expected is int:
        valid = valid and not isinstance(value, bool)
    if not valid:
        raise SpecFormatError(
            f"{location}.{key} must be {expected.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def _optional_string(
    table: Mapping[str, Any],
    key: str,
    location: str,
) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise SpecFormatError(
            f"{location}.{key} must be str when present, "
            f"got {type(value).__name__}"
        )
    return value


def _string_tuple(
    table: Mapping[str, Any],
    key: str,
    location: str,
) -> tuple[str, ...]:
    raw = _required(table, key, list, location)
    values: list[str] = []
    for index, value in enumerate(raw):
        if not isinstance(value, str):
            raise SpecFormatError(
                f"{location}.{key}[{index}] must be str, "
                f"got {type(value).__name__}"
            )
        values.append(value)
    return tuple(values)


def load_spec(path: str | bytes | os.PathLike[str]) -> ExperimentSpec:
    """Load an experiment specification from TOML.

    Structural type errors raise ``SpecFormatError``. Research-design
    constraints are returned separately by :func:`validate_spec`.
    """

    with open(path, "rb") as handle:
        raw = tomllib.load(handle)

    root = _table(raw, "root")
    schema_version = _required(root, "schema_version", int, "root")
    experiment = _table(
        _required(root, "experiment", dict, "root"),
        "experiment",
    )
    evaluation_raw = _table(
        _required(root, "evaluation", dict, "root"),
        "evaluation",
    )
    resources_raw = _table(
        _required(root, "resource_constraints", dict, "root"),
        "resource_constraints",
    )
    reporting = _table(
        _required(root, "reporting", dict, "root"),
        "reporting",
    )

    conditions_raw = _required(root, "conditions", list, "root")
    conditions: list[Condition] = []
    for index, raw_condition in enumerate(conditions_raw):
        location = f"conditions[{index}]"
        condition = _table(raw_condition, location)
        conditions.append(
            Condition(
                id=_required(condition, "id", str, location),
                role=_required(condition, "role", str, location),
                manifest=_optional_string(condition, "manifest", location),
                era=_optional_string(condition, "era", location),
                source_family=_optional_string(
                    condition,
                    "source_family",
                    location,
                ),
                window_start=_optional_string(
                    condition,
                    "window_start",
                    location,
                ),
                window_end=_optional_string(
                    condition,
                    "window_end",
                    location,
                ),
                control_type=_optional_string(
                    condition,
                    "control_type",
                    location,
                ),
            )
        )

    raw_seeds = _required(experiment, "seeds", list, "experiment")
    seeds: list[int] = []
    for index, seed in enumerate(raw_seeds):
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise SpecFormatError(
                f"experiment.seeds[{index}] must be int, "
                f"got {type(seed).__name__}"
            )
        seeds.append(seed)

    return ExperimentSpec(
        schema_version=schema_version,
        id=_required(experiment, "id", str, "experiment"),
        title=_required(experiment, "title", str, "experiment"),
        stage=_required(experiment, "stage", str, "experiment"),
        status=_required(experiment, "status", str, "experiment"),
        base_model=_required(experiment, "base_model", str, "experiment"),
        insertion_point=_required(
            experiment,
            "insertion_point",
            str,
            "experiment",
        ),
        adaptation_method=_required(
            experiment,
            "adaptation_method",
            str,
            "experiment",
        ),
        token_budget=_required(
            experiment,
            "token_budget",
            int,
            "experiment",
        ),
        seeds=tuple(seeds),
        conditions=tuple(conditions),
        evaluation=Evaluation(
            registry=_required(
                evaluation_raw,
                "registry",
                str,
                "evaluation",
            ),
            primary_families=_string_tuple(
                evaluation_raw,
                "primary_families",
                "evaluation",
            ),
            secondary_families=_string_tuple(
                evaluation_raw,
                "secondary_families",
                "evaluation",
            ),
            held_out_source_family=_required(
                evaluation_raw,
                "held_out_source_family",
                str,
                "evaluation",
            ),
            blinded=_required(
                evaluation_raw,
                "blinded",
                bool,
                "evaluation",
            ),
            frozen_before_training=_required(
                evaluation_raw,
                "frozen_before_training",
                bool,
                "evaluation",
            ),
        ),
        resources=ResourceConstraints(
            external_spend_cad=_required(
                resources_raw,
                "external_spend_cad",
                int,
                "resource_constraints",
            ),
            external_compute_requires_user_authorization=_required(
                resources_raw,
                "external_compute_requires_user_authorization",
                bool,
                "resource_constraints",
            ),
            training_requires_measured_benchmark=_required(
                resources_raw,
                "training_requires_measured_benchmark",
                bool,
                "resource_constraints",
            ),
            calibration_required_before_naturalistic_interpretation=_required(
                resources_raw,
                "calibration_required_before_naturalistic_interpretation",
                bool,
                "resource_constraints",
            ),
            max_parallel_training_jobs=_required(
                resources_raw,
                "max_parallel_training_jobs",
                int,
                "resource_constraints",
            ),
        ),
        output_dir=_required(
            reporting,
            "output_dir",
            str,
            "reporting",
        ),
        publish_negative_results=_required(
            reporting,
            "publish_negative_results",
            bool,
            "reporting",
        ),
    )


def _valid_repo_path(
    raw_path: str,
    required_parent: tuple[str, ...],
    suffix: str,
) -> bool:
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts:
        return False
    if path.suffix != suffix:
        return False
    return path.parts[: len(required_parent)] == required_parent


def _parse_iso_date(raw_date: str | None) -> date | None:
    if raw_date is None:
        return None
    try:
        parsed = date.fromisoformat(raw_date)
    except ValueError:
        return None
    if parsed.isoformat() != raw_date:
        return None
    return parsed


def validate_spec(spec: ExperimentSpec) -> tuple[str, ...]:
    """Return all known structural and research-integrity errors."""

    errors: list[str] = []

    if spec.schema_version != 2:
        errors.append(
            f"unsupported schema_version {spec.schema_version}; expected 2"
        )
    if not _SLUG.fullmatch(spec.id):
        errors.append("experiment.id must be a lowercase hyphenated slug")
    if not spec.title.strip():
        errors.append("experiment.title must not be empty")
    if not spec.stage.strip():
        errors.append("experiment.stage must not be empty")
    if spec.status not in _VALID_STATUSES:
        errors.append(
            "experiment.status must be one of "
            + ", ".join(sorted(_VALID_STATUSES))
        )
    if not spec.base_model.strip():
        errors.append("experiment.base_model must not be empty")
    if not spec.insertion_point.strip():
        errors.append("experiment.insertion_point must not be empty")
    if not spec.adaptation_method.strip():
        errors.append("experiment.adaptation_method must not be empty")
    if spec.token_budget < 0:
        errors.append("experiment.token_budget must not be negative")
    if spec.status != "design" and spec.token_budget == 0:
        errors.append(
            "experiment.token_budget must be frozen before execution"
        )
    if len(spec.seeds) < 3:
        errors.append(
            "at least three exploratory adaptation seeds are required"
        )
    if len(set(spec.seeds)) != len(spec.seeds):
        errors.append("experiment.seeds must be unique")

    condition_ids = [condition.id for condition in spec.conditions]
    if len(condition_ids) != len(set(condition_ids)):
        errors.append("condition ids must be unique")
    if any(not _SLUG.fullmatch(condition_id) for condition_id in condition_ids):
        errors.append("every condition id must be a lowercase hyphenated slug")

    temporal = [
        condition
        for condition in spec.conditions
        if condition.role == "temporal"
    ]
    control_types: set[str] = set()
    temporal_pairs: set[tuple[str, str]] = set()
    windows_by_era: dict[str, set[tuple[str, str]]] = {
        "early": set(),
        "late": set(),
    }
    source_eras: dict[str, set[str]] = {}

    for condition in spec.conditions:
        prefix = f"condition {condition.id!r}"

        if condition.role not in _VALID_ROLES:
            errors.append(
                f"{prefix} has invalid role {condition.role!r}"
            )
            continue

        if condition.manifest is not None and not _valid_repo_path(
            condition.manifest,
            ("data", "manifests"),
            ".jsonl",
        ):
            errors.append(
                f"{prefix} manifest must be a relative "
                "data/manifests/*.jsonl path"
            )

        if condition.role == "temporal":
            if condition.control_type is not None:
                errors.append(f"{prefix} must not define control_type")
            if condition.era not in _VALID_ERAS:
                errors.append(
                    f"{prefix} must define era as early or late"
                )
            if (
                condition.source_family is None
                or not _SOURCE_FAMILY.fullmatch(condition.source_family)
            ):
                errors.append(
                    f"{prefix} must define an uppercase source_family"
                )
            if condition.manifest is None:
                errors.append(f"{prefix} must define a manifest")

            start = _parse_iso_date(condition.window_start)
            end = _parse_iso_date(condition.window_end)
            if start is None or end is None:
                errors.append(
                    f"{prefix} must define ISO window_start and window_end"
                )
            elif start > end:
                errors.append(
                    f"{prefix} window_start must not follow window_end"
                )

            if (
                condition.era in _VALID_ERAS
                and condition.source_family is not None
            ):
                pair = (condition.era, condition.source_family)
                if pair in temporal_pairs:
                    errors.append(
                        "each era/source_family pair must be unique"
                    )
                temporal_pairs.add(pair)
                source_eras.setdefault(condition.source_family, set()).add(
                    condition.era
                )
                if start is not None and end is not None:
                    windows_by_era[condition.era].add(
                        (start.isoformat(), end.isoformat())
                    )
        else:
            if condition.era is not None:
                errors.append(f"{prefix} control must not define era")
            if condition.source_family is not None:
                errors.append(
                    f"{prefix} control must not define source_family"
                )
            if condition.window_start is not None:
                errors.append(
                    f"{prefix} control must not define window_start"
                )
            if condition.window_end is not None:
                errors.append(
                    f"{prefix} control must not define window_end"
                )
            if not condition.control_type:
                errors.append(f"{prefix} must define control_type")
            else:
                control_types.add(condition.control_type)
            if condition.control_type == "unadapted":
                if condition.manifest is not None:
                    errors.append(
                        f"{prefix} must not define a manifest"
                    )
            elif condition.manifest is None:
                errors.append(f"{prefix} must define a manifest")

    if len(temporal) < 4:
        errors.append(
            "at least four temporal conditions are required "
            "(two eras across two source families)"
        )

    complete_sources = {
        source
        for source, eras in source_eras.items()
        if eras == _VALID_ERAS
    }
    if len(complete_sources) < 2:
        errors.append(
            "at least two source families must each contain "
            "both early and late conditions"
        )

    for era, windows in windows_by_era.items():
        if len(windows) > 1:
            errors.append(
                f"all {era} temporal conditions must use the same window"
            )

    if windows_by_era["early"] and windows_by_era["late"]:
        early_end = date.fromisoformat(
            next(iter(windows_by_era["early"]))[1]
        )
        late_start = date.fromisoformat(
            next(iter(windows_by_era["late"]))[0]
        )
        if early_end >= late_start:
            errors.append(
                "the early era window must end before the late era window"
            )

    missing_controls = _REQUIRED_CONTROLS - control_types
    if missing_controls:
        errors.append(
            "missing required controls: "
            + ", ".join(sorted(missing_controls))
        )

    if not _valid_repo_path(
        spec.evaluation.registry,
        ("evaluations", "registry"),
        ".jsonl",
    ):
        errors.append(
            "evaluation.registry must be a relative "
            "evaluations/registry/*.jsonl path"
        )
    if len(spec.evaluation.primary_families) < 2:
        errors.append(
            "at least two primary evaluation families are required"
        )
    if any(
        not family.strip()
        for family in (
            *spec.evaluation.primary_families,
            *spec.evaluation.secondary_families,
        )
    ):
        errors.append("evaluation family names must not be empty")
    if (
        not _SOURCE_FAMILY.fullmatch(
            spec.evaluation.held_out_source_family
        )
    ):
        errors.append(
            "evaluation.held_out_source_family must be uppercase"
        )
    if (
        spec.evaluation.held_out_source_family
        in {condition.source_family for condition in temporal}
    ):
        errors.append(
            "held-out source family must not appear in pilot training "
            "conditions"
        )
    if not spec.evaluation.blinded:
        errors.append("pilot evaluation must be blinded")
    if not spec.evaluation.frozen_before_training:
        errors.append("evaluation must be frozen before training")

    if spec.resources.external_spend_cad < 0:
        errors.append(
            "resource_constraints.external_spend_cad must not be negative"
        )
    if not spec.resources.external_compute_requires_user_authorization:
        errors.append(
            "external compute must require explicit user authorization"
        )
    if not spec.resources.training_requires_measured_benchmark:
        errors.append(
            "training must require a measured throughput and memory benchmark"
        )
    if (
        not spec.resources
        .calibration_required_before_naturalistic_interpretation
    ):
        errors.append(
            "synthetic calibration must precede naturalistic interpretation"
        )
    if spec.resources.max_parallel_training_jobs != 1:
        errors.append(
            "resource-constrained pilot permits exactly one training job "
            "at a time"
        )

    output_path = PurePosixPath(spec.output_dir)
    if (
        output_path.is_absolute()
        or ".." in output_path.parts
        or output_path.parts[:1] != ("results",)
    ):
        errors.append(
            "reporting.output_dir must be a relative results/* path"
        )
    if not spec.publish_negative_results:
        errors.append(
            "reporting.publish_negative_results must be true"
        )

    return tuple(errors)


def describe_spec(spec: ExperimentSpec) -> str:
    """Return a compact human-readable summary."""

    temporal = sum(
        condition.role == "temporal"
        for condition in spec.conditions
    )
    source_families = {
        condition.source_family
        for condition in spec.conditions
        if condition.role == "temporal"
    }
    token_budget = (
        "unfrozen token budget"
        if spec.token_budget == 0
        else f"{spec.token_budget:,} tokens per adapted condition"
    )
    return (
        f"{spec.id}: {temporal} temporal branches across "
        f"{len(source_families)} source families, "
        f"{len(spec.seeds)} seeds, {token_budget}"
    )
