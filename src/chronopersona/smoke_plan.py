"""Deterministic, no-network planning for the ChronoPersona fixture smoke."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
from typing import Any

from .run_registry import (
    build_run_identity,
    canonical_json_bytes,
    canonical_sha256,
    sha256_file,
)
from .synthetic_calibration import build_package, sha256_bytes


class SmokePipelineError(ValueError):
    """Raised when a smoke plan or resumable execution is invalid."""


ENGINE_ID = "synthetic-package-integrity-smoke"
ENGINE_VERSION = "v0"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "run_name",
        "run_kind",
        "status",
        "scientific_claim_authorized",
        "training_authorized",
        "network_allowed",
        "model_download_allowed",
        "external_spend_cad",
        "max_parallel_jobs",
        "target_tokens",
        "seed",
        "precision",
        "model",
        "inputs",
        "engine",
    }
)


@dataclass(frozen=True)
class SmokePlan:
    config: dict[str, Any]
    identity: dict[str, Any]
    plan: dict[str, Any]
    built_files: dict[str, bytes]
    unit_order: tuple[str, ...]


@dataclass(frozen=True)
class SmokeRunResult:
    run_id: str
    run_root: Path
    status: str
    completed_units: int
    total_units: int
    final_manifest: dict[str, Any] | None


def _load_json_object(path: str | Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SmokePipelineError(f"invalid {label} JSON: {error}") from error
    if not isinstance(value, dict):
        raise SmokePipelineError(f"{label} root must be an object")
    return value


def _safe_repo_path(repo_root: Path, raw_path: Any, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise SmokePipelineError(f"{label} must be a nonempty repository path")
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise SmokePipelineError(f"{label} must be a safe relative path")
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise SmokePipelineError(f"{label} escapes the repository root") from error
    if not resolved.is_file():
        raise SmokePipelineError(f"{label} not found: {relative.as_posix()}")
    return resolved


def validate_smoke_config(config: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if set(config) != _ALLOWED_CONFIG_FIELDS:
        return ("smoke config has unexpected or missing top-level fields",)
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("run_name", "run_kind", "status", "precision"):
        if not isinstance(config.get(field), str) or not str(config[field]).strip():
            errors.append(f"{field} must be a nonempty string")
    if config.get("run_kind") != "fixture-smoke":
        errors.append("run_kind must be fixture-smoke")
    if config.get("status") != "development":
        errors.append("fixture smoke config must remain development")
    for field in (
        "scientific_claim_authorized",
        "training_authorized",
        "network_allowed",
        "model_download_allowed",
    ):
        if config.get(field) is not False:
            errors.append(f"{field} must be false")
    if config.get("external_spend_cad") != 0:
        errors.append("external_spend_cad must be zero")
    if config.get("max_parallel_jobs") != 1:
        errors.append("max_parallel_jobs must be exactly one")
    if config.get("target_tokens") != 0:
        errors.append("fixture smoke target_tokens must remain zero")
    seed = config.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        errors.append("seed must be a non-negative integer")
    if config.get("precision") != "not-applicable":
        errors.append("fixture smoke precision must be not-applicable")

    model = config.get("model")
    model_fields = {"id", "revision", "tokenizer_revision"}
    if not isinstance(model, Mapping) or set(model) != model_fields:
        errors.append("model must declare id/revision/tokenizer_revision")
    elif any(model.get(field) is not None for field in model_fields):
        errors.append("fixture smoke must not declare a model artifact")

    inputs = config.get("inputs")
    required_inputs = {
        "calibration_config",
        "calibration_expected_hashes",
        "evaluation_registry",
    }
    if not isinstance(inputs, Mapping) or set(inputs) != required_inputs:
        errors.append("inputs must declare the three required repository paths")
    elif any(
        not isinstance(inputs.get(field), str) or not inputs[field]
        for field in required_inputs
    ):
        errors.append("every input path must be a nonempty string")

    engine = config.get("engine")
    if not isinstance(engine, Mapping) or set(engine) != {
        "id",
        "version",
        "checkpoint_every_units",
    }:
        errors.append("engine must declare id/version/checkpoint_every_units")
    else:
        if engine.get("id") != ENGINE_ID:
            errors.append(f"engine.id must be {ENGINE_ID}")
        if engine.get("version") != ENGINE_VERSION:
            errors.append(f"engine.version must be {ENGINE_VERSION}")
        if engine.get("checkpoint_every_units") != 1:
            errors.append("checkpoint_every_units must be exactly one")
    return tuple(errors)


def load_smoke_config(path: str | Path) -> dict[str, Any]:
    config = _load_json_object(path, "smoke config")
    errors = validate_smoke_config(config)
    if errors:
        raise SmokePipelineError("; ".join(errors))
    return config


def capture_environment() -> dict[str, Any]:
    """Capture execution identity without importing model libraries."""

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def resolve_git_commit(repo_root: str | Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SmokePipelineError(
            f"could not resolve Git commit: {result.stderr.strip()}"
        )
    commit = result.stdout.strip().lower()
    if not _SHA40.fullmatch(commit):
        raise SmokePipelineError("resolved Git commit is not a 40-character SHA")
    return commit


def _package_identity(
    built_files: Mapping[str, bytes],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "package_manifest_sha256": manifest["output_sha256"],
        "generated_files": {
            path: {"sha256": sha256_bytes(content), "bytes": len(content)}
            for path, content in sorted(built_files.items())
        },
    }


def build_smoke_plan(
    repo_root: str | Path,
    config_path: str | Path,
    *,
    git_commit: str,
    environment: Mapping[str, Any] | None = None,
) -> SmokePlan:
    root = Path(repo_root).resolve()
    commit = git_commit.lower()
    if not _SHA40.fullmatch(commit):
        raise SmokePipelineError("git_commit must be a 40-character lowercase SHA")

    config_source = Path(config_path)
    if not config_source.is_absolute():
        config_source = root / config_source
    config_source = config_source.resolve()
    try:
        config_source.relative_to(root)
    except ValueError as error:
        raise SmokePipelineError(
            "smoke config must be inside repository root"
        ) from error
    config = load_smoke_config(config_source)

    input_paths = {
        key: _safe_repo_path(root, value, f"inputs.{key}")
        for key, value in config["inputs"].items()
    }
    built = build_package(input_paths["calibration_config"])
    observed_package_identity = _package_identity(built.files, built.manifest)
    expected_package_identity = _load_json_object(
        input_paths["calibration_expected_hashes"],
        "calibration expected-hashes",
    )
    if observed_package_identity != expected_package_identity:
        raise SmokePipelineError(
            "synthetic calibration package does not match expected-hashes.json"
        )

    execution_environment = json.loads(
        canonical_json_bytes(environment or capture_environment())
    )
    input_identities = {
        key: {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for key, path in sorted(input_paths.items())
    }
    for unit_id in built.files:
        if not isinstance(unit_id, str) or not unit_id:
            raise SmokePipelineError(
                "generated package contains an invalid unit id"
            )
        unit_path = PurePosixPath(unit_id)
        if unit_path.is_absolute() or ".." in unit_path.parts:
            raise SmokePipelineError(
                f"generated package contains unsafe unit path: {unit_id}"
            )
    unit_order = tuple(sorted(built.files))
    unit_order_sha256 = canonical_sha256(list(unit_order))
    scientific_identity = {
        "schema_version": 1,
        "run_name": config["run_name"],
        "run_kind": config["run_kind"],
        "engine": dict(config["engine"]),
        "git_commit": commit,
        "config": {
            "path": config_source.relative_to(root).as_posix(),
            "sha256": sha256_file(config_source),
            "canonical_sha256": canonical_sha256(config),
        },
        "inputs": input_identities,
        "synthetic_package": observed_package_identity,
        "unit_order_sha256": unit_order_sha256,
        "seed": config["seed"],
        "model": dict(config["model"]),
        "training_method": "none-fixture-integrity-smoke",
        "target_tokens": 0,
        "precision": config["precision"],
        "environment": execution_environment,
        "resource_constraints": {
            "external_spend_cad": config["external_spend_cad"],
            "max_parallel_jobs": config["max_parallel_jobs"],
            "network_allowed": config["network_allowed"],
            "model_download_allowed": config["model_download_allowed"],
        },
        "scientific_claim_authorized": config["scientific_claim_authorized"],
        "training_authorized": config["training_authorized"],
    }
    identity = build_run_identity(scientific_identity)
    generated_bytes = sum(len(content) for content in built.files.values())
    plan: dict[str, Any] = {
        "schema_version": 1,
        "mode": "plan",
        "run_id": identity["run_id"],
        "identity_sha256": identity["identity_sha256"],
        "network_access_permitted": False,
        "model_download_permitted": False,
        "model_load_planned": False,
        "training_planned": False,
        "scientific_claim_authorized": False,
        "unit_count": len(unit_order),
        "unit_order_sha256": unit_order_sha256,
        "generated_input_bytes": generated_bytes,
        "minimum_required_storage_bytes": generated_bytes * 3 + 1_048_576,
        "external_spend_cad": 0,
        "max_parallel_jobs": 1,
        "blockers_to_model_training": [
            "target token doses are unfrozen",
            "no measured local throughput benchmark is attached",
            "no model artifact is authorized by this fixture run",
            "synthetic calibration has not been trained or scored",
        ],
    }
    plan["plan_sha256"] = canonical_sha256(plan)
    return SmokePlan(
        config=config,
        identity=identity,
        plan=plan,
        built_files=dict(built.files),
        unit_order=unit_order,
    )
