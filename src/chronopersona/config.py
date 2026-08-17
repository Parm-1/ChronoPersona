"""Load and validate ChronoPersona experiment specifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
import os
import re
import tomllib
from collections.abc import Mapping
from typing import Any


_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VALID_ROLES = {"temporal", "control"}
_VALID_STATUSES = {"design", "frozen", "running", "complete"}
_REQUIRED_CONTROLS = {"unadapted", "date_shuffled"}


class SpecFormatError(ValueError):
    """Raised when a TOML file cannot be converted into a specification."""


@dataclass(frozen=True)
class Condition:
    id: str
    role: str
    cutoff: str | None = None
    manifest: str | None = None
    control_type: str | None = None


@dataclass(frozen=True)
class Evaluation:
    registry: str
    primary_family: str
    blinded: bool
    frozen_before_training: bool


@dataclass(frozen=True)
class ExperimentSpec:
    schema_version: int
    id: str
    title: str
    status: str
    base_model: str
    adaptation_method: str
    token_budget: int
    seeds: tuple[int, ...]
    conditions: tuple[Condition, ...]
    evaluation: Evaluation
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
                cutoff=_optional_string(condition, "cutoff", location),
                manifest=_optional_string(condition, "manifest", location),
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
        status=_required(experiment, "status", str, "experiment"),
        base_model=_required(experiment, "base_model", str, "experiment"),
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
            primary_family=_required(
                evaluation_raw,
                "primary_family",
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


def _valid_cutoff(raw_cutoff: str) -> bool:
    try:
        parsed = date.fromisoformat(raw_cutoff)
    except ValueError:
        return False
    return parsed.isoformat() == raw_cutoff


def validate_spec(spec: ExperimentSpec) -> tuple[str, ...]:
    """Return all known structural and research-integrity errors."""

    errors: list[str] = []

    if spec.schema_version != 1:
        errors.append(
            f"unsupported schema_version {spec.schema_version}; expected 1"
        )
    if not _SLUG.fullmatch(spec.id):
        errors.append("experiment.id must be a lowercase hyphenated slug")
    if not spec.title.strip():
        errors.append("experiment.title must not be empty")
    if spec.status not in _VALID_STATUSES:
        errors.append(
            "experiment.status must be one of "
            + ", ".join(sorted(_VALID_STATUSES))
        )
    if not spec.base_model.strip():
        errors.append("experiment.base_model must not be empty")
    if not spec.adaptation_method.strip():
        errors.append("experiment.adaptation_method must not be empty")
    if spec.token_budget <= 0:
        errors.append("experiment.token_budget must be positive")
    if len(spec.seeds) < 2:
        errors.append("at least two adaptation seeds are required")
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
    if len(temporal) < 2:
        errors.append("at least two temporal conditions are required")

    temporal_cutoffs: list[str] = []
    control_types: set[str] = set()

    for condition in spec.conditions:
        prefix = f"condition {condition.id!r}"

        if condition.role not in _VALID_ROLES:
            errors.append(
                f"{prefix} has invalid role {condition.role!r}"
            )
            continue

        if condition.role == "temporal":
            if condition.control_type is not None:
                errors.append(f"{prefix} must not define control_type")
            if condition.cutoff is None or not _valid_cutoff(
                condition.cutoff
            ):
                errors.append(
                    f"{prefix} must define an ISO date cutoff"
                )
            else:
                temporal_cutoffs.append(condition.cutoff)
            if condition.manifest is None:
                errors.append(f"{prefix} must define a manifest")
        else:
            if not condition.control_type:
                errors.append(f"{prefix} must define control_type")
            else:
                control_types.add(condition.control_type)
            if condition.control_type == "unadapted":
                if condition.manifest is not None:
                    errors.append(
                        f"{prefix} must not define a manifest"
                    )
                if condition.cutoff is not None:
                    errors.append(f"{prefix} must not define a cutoff")
            else:
                if condition.manifest is None:
                    errors.append(f"{prefix} must define a manifest")
                if condition.control_type == "date_shuffled":
                    if condition.cutoff is None or not _valid_cutoff(
                        condition.cutoff
                    ):
                        errors.append(
                            f"{prefix} must define an ISO date cutoff"
                        )

        if condition.manifest is not None and not _valid_repo_path(
            condition.manifest,
            ("data", "manifests"),
            ".jsonl",
        ):
            errors.append(
                f"{prefix} manifest must be a relative "
                "data/manifests/*.jsonl path"
            )

    if len(temporal_cutoffs) != len(set(temporal_cutoffs)):
        errors.append("temporal condition cutoffs must be unique")

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
    if not spec.evaluation.primary_family.strip():
        errors.append("evaluation.primary_family must not be empty")
    if not spec.evaluation.blinded:
        errors.append("pilot evaluation must be blinded")
    if not spec.evaluation.frozen_before_training:
        errors.append("evaluation must be frozen before training")

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

    return (
        f"{spec.id}: {len(spec.conditions)} conditions, "
        f"{len(spec.seeds)} seeds, "
        f"{spec.token_budget:,} tokens per adapted condition"
    )
