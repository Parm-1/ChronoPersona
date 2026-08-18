"""Deterministic unit, checkpoint, and final-artifact validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .path_policy import PortablePathError, portable_relative_path
from .run_registry import (
    RunStore,
    atomic_write_json,
    canonical_sha256,
    read_json,
    sha256_file,
)
from .smoke_plan import ENGINE_ID, ENGINE_VERSION, SmokePipelineError, SmokePlan


_CHECKPOINT_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "identity_sha256",
        "unit_order_sha256",
        "completed_units",
        "unit_artifacts",
        "next_unit_index",
        "checkpoint_sha256",
    }
)
_UNIT_ARTIFACT_FIELDS = frozenset(
    {
        "schema_version",
        "processor_version",
        "run_id",
        "unit_index",
        "unit_id",
        "input_sha256",
        "input_bytes",
        "line_count",
        "json_record_count",
        "content_type",
        "output_sha256",
    }
)
_FINAL_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "identity_sha256",
        "engine",
        "unit_order_sha256",
        "unit_count",
        "units",
        "checkpoint_sha256",
        "training_performed",
        "model_loaded",
        "network_access_performed",
        "scientific_claim_authorized",
        "final_manifest_sha256",
    }
)


def unit_artifact_path(run_root: Path, index: int, unit_id: str) -> Path:
    digest = hashlib.sha256(unit_id.encode("utf-8")).hexdigest()[:16]
    return run_root / "artifacts" / "units" / f"{index:04d}-{digest}.json"


def _content_type(unit_id: str) -> str:
    if unit_id.endswith(".jsonl"):
        return "application/x-ndjson"
    if unit_id.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def process_unit(
    *,
    run_id: str,
    unit_index: int,
    unit_id: str,
    content: bytes,
) -> dict[str, Any]:
    line_count = len(content.splitlines())
    json_record_count: int | None = None
    if unit_id.endswith(".jsonl"):
        json_record_count = 0
        for line_number, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                raise SmokePipelineError(
                    f"generated unit {unit_id} has blank JSONL line {line_number}"
                )
            try:
                json.loads(line)
            except json.JSONDecodeError as error:
                raise SmokePipelineError(
                    f"generated unit {unit_id} has invalid JSONL line "
                    f"{line_number}: {error}"
                ) from error
            json_record_count += 1
    elif unit_id.endswith(".json"):
        try:
            json.loads(content)
        except json.JSONDecodeError as error:
            raise SmokePipelineError(
                f"generated unit {unit_id} has invalid JSON: {error}"
            ) from error
        json_record_count = 1

    artifact: dict[str, Any] = {
        "schema_version": 1,
        "processor_version": f"{ENGINE_ID}-{ENGINE_VERSION}",
        "run_id": run_id,
        "unit_index": unit_index,
        "unit_id": unit_id,
        "input_sha256": hashlib.sha256(content).hexdigest(),
        "input_bytes": len(content),
        "line_count": line_count,
        "json_record_count": json_record_count,
        "content_type": _content_type(unit_id),
    }
    artifact["output_sha256"] = canonical_sha256(artifact)
    return artifact


def checkpoint_payload(
    *,
    run_id: str,
    identity_sha256: str,
    unit_order: Sequence[str],
    unit_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    completed = list(unit_order[: len(unit_artifacts)])
    if set(completed) != set(unit_artifacts):
        raise SmokePipelineError(
            "completed unit artifacts are not a unit-order prefix"
        )
    checkpoint: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "identity_sha256": identity_sha256,
        "unit_order_sha256": canonical_sha256(list(unit_order)),
        "completed_units": completed,
        "unit_artifacts": {
            unit_id: dict(unit_artifacts[unit_id]) for unit_id in completed
        },
        "next_unit_index": len(completed),
    }
    checkpoint["checkpoint_sha256"] = canonical_sha256(checkpoint)
    return checkpoint


def _validate_unit_artifact(
    artifact: Mapping[str, Any],
    *,
    run_id: str,
    unit_index: int,
    unit_id: str,
    input_content: bytes,
) -> None:
    if set(artifact) != _UNIT_ARTIFACT_FIELDS:
        raise SmokePipelineError(f"unit artifact for {unit_id} has invalid fields")
    expected = process_unit(
        run_id=run_id,
        unit_index=unit_index,
        unit_id=unit_id,
        content=input_content,
    )
    if dict(artifact) != expected:
        raise SmokePipelineError(
            f"unit artifact does not match deterministic output for {unit_id}"
        )


def validate_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    plan: SmokePlan,
    run_root: Path,
) -> dict[str, dict[str, Any]]:
    if set(checkpoint) != _CHECKPOINT_FIELDS:
        raise SmokePipelineError("checkpoint has unexpected or missing fields")
    if checkpoint.get("schema_version") != 1:
        raise SmokePipelineError("checkpoint schema_version must be 1")
    if checkpoint.get("run_id") != plan.identity["run_id"]:
        raise SmokePipelineError("checkpoint run_id mismatch")
    if checkpoint.get("identity_sha256") != plan.identity["identity_sha256"]:
        raise SmokePipelineError("checkpoint identity hash mismatch")
    if checkpoint.get("unit_order_sha256") != canonical_sha256(
        list(plan.unit_order)
    ):
        raise SmokePipelineError("checkpoint unit-order hash mismatch")
    observed_hash = checkpoint.get("checkpoint_sha256")
    expected_hash = canonical_sha256(
        {
            key: checkpoint[key]
            for key in checkpoint
            if key != "checkpoint_sha256"
        }
    )
    if observed_hash != expected_hash:
        raise SmokePipelineError("checkpoint hash mismatch")

    completed = checkpoint.get("completed_units")
    if not isinstance(completed, list) or not all(
        isinstance(unit, str) for unit in completed
    ):
        raise SmokePipelineError(
            "checkpoint completed_units must be a string list"
        )
    if completed != list(plan.unit_order[: len(completed)]):
        raise SmokePipelineError(
            "checkpoint completed_units are not an ordered prefix"
        )
    if len(completed) != len(set(completed)):
        raise SmokePipelineError("checkpoint completed_units contain duplicates")
    if checkpoint.get("next_unit_index") != len(completed):
        raise SmokePipelineError("checkpoint next_unit_index mismatch")

    raw_artifacts = checkpoint.get("unit_artifacts")
    if not isinstance(raw_artifacts, Mapping) or set(raw_artifacts) != set(
        completed
    ):
        raise SmokePipelineError(
            "checkpoint unit_artifacts mismatch completed_units"
        )

    artifacts: dict[str, dict[str, Any]] = {}
    for index, unit_id in enumerate(completed):
        reference = raw_artifacts[unit_id]
        if not isinstance(reference, Mapping) or set(reference) != {
            "path",
            "file_sha256",
            "output_sha256",
        }:
            raise SmokePipelineError(
                f"checkpoint reference invalid for {unit_id}"
            )
        if not isinstance(reference.get("path"), str):
            raise SmokePipelineError(
                f"checkpoint artifact path must be a string for {unit_id}"
            )
        try:
            relative = portable_relative_path(
                reference["path"],
                label=f"checkpoint artifact path for {unit_id}",
                suffix=".json",
            )
        except PortablePathError as error:
            raise SmokePipelineError(str(error)) from error
        artifact_path = (run_root / relative).resolve()
        try:
            artifact_path.relative_to(run_root.resolve())
        except ValueError as error:
            raise SmokePipelineError(
                f"checkpoint artifact escapes run root for {unit_id}"
            ) from error
        if not artifact_path.is_file():
            raise SmokePipelineError(
                f"checkpoint artifact missing for {unit_id}"
            )
        if sha256_file(artifact_path) != reference["file_sha256"]:
            raise SmokePipelineError(
                f"checkpoint artifact file hash mismatch for {unit_id}"
            )
        artifact = read_json(artifact_path)
        if not isinstance(artifact, dict):
            raise SmokePipelineError(
                f"unit artifact root is invalid for {unit_id}"
            )
        _validate_unit_artifact(
            artifact,
            run_id=plan.identity["run_id"],
            unit_index=index,
            unit_id=unit_id,
            input_content=plan.built_files[unit_id],
        )
        if artifact["output_sha256"] != reference["output_sha256"]:
            raise SmokePipelineError(
                f"checkpoint output hash mismatch for {unit_id}"
            )
        artifacts[unit_id] = dict(reference)
    return artifacts


def load_or_create_checkpoint(
    plan: SmokePlan,
    run_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    checkpoint_path = run_root / "checkpoint.json"
    if checkpoint_path.exists():
        checkpoint = read_json(checkpoint_path)
        if not isinstance(checkpoint, dict):
            raise SmokePipelineError("checkpoint root must be an object")
        artifacts = validate_checkpoint(
            checkpoint,
            plan=plan,
            run_root=run_root,
        )
        return checkpoint, artifacts
    checkpoint = checkpoint_payload(
        run_id=plan.identity["run_id"],
        identity_sha256=plan.identity["identity_sha256"],
        unit_order=plan.unit_order,
        unit_artifacts={},
    )
    atomic_write_json(checkpoint_path, checkpoint)
    return checkpoint, {}


def final_manifest(
    *,
    plan: SmokePlan,
    checkpoint: Mapping[str, Any],
    unit_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if list(unit_artifacts) != list(plan.unit_order):
        raise SmokePipelineError("cannot finalize an incomplete smoke run")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": plan.identity["run_id"],
        "identity_sha256": plan.identity["identity_sha256"],
        "engine": {"id": ENGINE_ID, "version": ENGINE_VERSION},
        "unit_order_sha256": canonical_sha256(list(plan.unit_order)),
        "unit_count": len(plan.unit_order),
        "units": [
            {"unit_id": unit_id, **dict(unit_artifacts[unit_id])}
            for unit_id in plan.unit_order
        ],
        "checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "training_performed": False,
        "model_loaded": False,
        "network_access_performed": False,
        "scientific_claim_authorized": False,
    }
    manifest["final_manifest_sha256"] = canonical_sha256(manifest)
    return manifest


def validate_final_manifest(
    manifest: Mapping[str, Any],
    *,
    plan: SmokePlan,
    checkpoint: Mapping[str, Any],
    unit_artifacts: Mapping[str, Mapping[str, Any]],
) -> None:
    if set(manifest) != _FINAL_FIELDS:
        raise SmokePipelineError(
            "final manifest has unexpected or missing fields"
        )
    expected = final_manifest(
        plan=plan,
        checkpoint=checkpoint,
        unit_artifacts=unit_artifacts,
    )
    if dict(manifest) != expected:
        raise SmokePipelineError(
            "final manifest does not match verified run artifacts"
        )


def verify_smoke_run(plan: SmokePlan, run_root: str | Path) -> dict[str, Any]:
    root = Path(run_root)
    store = RunStore.load(root)
    if store.identity != plan.identity:
        raise SmokePipelineError(
            "run identity differs from the requested plan"
        )
    checkpoint = read_json(root / "checkpoint.json")
    if not isinstance(checkpoint, dict):
        raise SmokePipelineError("checkpoint root must be an object")
    unit_artifacts = validate_checkpoint(
        checkpoint,
        plan=plan,
        run_root=root,
    )
    state = store.state
    report: dict[str, Any] = {
        "schema_version": 1,
        "run_id": store.run_id,
        "state": state,
        "completed_units": len(unit_artifacts),
        "total_units": len(plan.unit_order),
        "checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "final_manifest_sha256": None,
    }
    final_path = root / "artifacts" / "final-manifest.json"
    if state == "complete":
        if not final_path.is_file():
            raise SmokePipelineError(
                "complete run is missing final manifest"
            )
        manifest = read_json(final_path)
        if not isinstance(manifest, dict):
            raise SmokePipelineError("final manifest root must be an object")
        validate_final_manifest(
            manifest,
            plan=plan,
            checkpoint=checkpoint,
            unit_artifacts=unit_artifacts,
        )
        report["final_manifest_sha256"] = manifest[
            "final_manifest_sha256"
        ]
    elif final_path.exists():
        raise SmokePipelineError(
            "non-complete run must not contain a final manifest"
        )
    report["verification_sha256"] = canonical_sha256(report)
    return report
