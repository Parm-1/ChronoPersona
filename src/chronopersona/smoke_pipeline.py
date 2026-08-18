"""Resumable execution of the dependency-free ChronoPersona smoke."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable

from .run_registry import (
    RunLock,
    RunStore,
    atomic_write_json,
    ensure_registry_entry,
    read_json,
    sha256_file,
)
from .smoke_artifacts import (
    checkpoint_payload,
    final_manifest,
    load_or_create_checkpoint,
    unit_artifact_path,
    process_unit,
    validate_checkpoint,
    validate_final_manifest,
    verify_smoke_run,
)
from .smoke_plan import (
    SmokePipelineError,
    SmokePlan,
    SmokeRunResult,
    build_smoke_plan,
    capture_environment,
    load_smoke_config,
    resolve_git_commit,
    validate_smoke_config,
)

__all__ = [
    "SmokePipelineError",
    "SmokePlan",
    "SmokeRunResult",
    "build_smoke_plan",
    "capture_environment",
    "load_smoke_config",
    "resolve_git_commit",
    "run_smoke_pipeline",
    "validate_smoke_config",
    "verify_smoke_run",
]


def run_smoke_pipeline(
    plan: SmokePlan,
    output_root: str | Path,
    *,
    resume: bool = False,
    interrupt_after: int | None = None,
    event_clock: Callable[[], str | None] | None = None,
) -> SmokeRunResult:
    if interrupt_after is not None and (
        not isinstance(interrupt_after, int)
        or isinstance(interrupt_after, bool)
        or interrupt_after < 1
    ):
        raise SmokePipelineError("interrupt_after must be a positive integer")
    clock = event_clock or (lambda: None)
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    free_storage_bytes = shutil.disk_usage(output).free
    minimum_storage_bytes = int(
        plan.plan["minimum_required_storage_bytes"]
    )
    if free_storage_bytes < minimum_storage_bytes:
        raise SmokePipelineError(
            "insufficient free storage for fixture smoke: "
            f"{free_storage_bytes} < {minimum_storage_bytes}"
        )
    run_root = output / plan.identity["run_id"]
    registry_path = output / "registry.jsonl"
    initialization_lock = RunLock(
        output / ".locks" / f"{plan.identity['run_id']}.lock",
        run_id=plan.identity["run_id"],
    )

    with initialization_lock:
        if (run_root / "identity.json").exists():
            store = RunStore.load(run_root)
            if store.identity != plan.identity:
                raise SmokePipelineError("existing run identity differs from plan")
        else:
            store = RunStore(run_root, plan.identity)
            store.initialize(recorded_at=clock())
        with RunLock(
            output / ".locks" / "registry.lock",
            run_id=plan.identity["run_id"],
        ):
            ensure_registry_entry(
                registry_path,
                plan.identity,
                created_at=clock(),
            )

        state = store.state
        if state == "complete":
            verification = verify_smoke_run(plan, run_root)
            manifest = read_json(run_root / "artifacts" / "final-manifest.json")
            return SmokeRunResult(
                run_id=store.run_id,
                run_root=run_root,
                status="complete",
                completed_units=int(verification["completed_units"]),
                total_units=len(plan.unit_order),
                final_manifest=dict(manifest),
            )
        if state in {"running", "failed"} and not resume:
            raise SmokePipelineError(
                f"run is {state}; pass explicit resume authorization"
            )
        if state == "failed":
            store.transition(
                "resume",
                data={
                    "reason": "explicit-resume",
                    "free_storage_bytes": free_storage_bytes,
                },
                recorded_at=clock(),
            )
        elif state == "running":
            store.transition(
                "recover",
                data={
                    "reason": "explicit-recovery-after-unclean-stop",
                    "free_storage_bytes": free_storage_bytes,
                },
                recorded_at=clock(),
            )
        elif state == "design":
            store.transition(
                "freeze",
                data={
                    "plan_sha256": plan.plan["plan_sha256"],
                    "minimum_required_storage_bytes": minimum_storage_bytes,
                },
                recorded_at=clock(),
            )
            store.transition(
                "start",
                data={"free_storage_bytes": free_storage_bytes},
                recorded_at=clock(),
            )
        elif state == "frozen":
            store.transition(
                "start",
                data={"free_storage_bytes": free_storage_bytes},
                recorded_at=clock(),
            )
        else:
            raise SmokePipelineError(f"unsupported existing run state: {state}")

        processed_this_invocation = 0
        try:
            checkpoint, references = load_or_create_checkpoint(plan, run_root)
            start_index = int(checkpoint["next_unit_index"])
            for index in range(start_index, len(plan.unit_order)):
                unit_id = plan.unit_order[index]
                artifact = process_unit(
                    run_id=plan.identity["run_id"],
                    unit_index=index,
                    unit_id=unit_id,
                    content=plan.built_files[unit_id],
                )
                artifact_path = unit_artifact_path(run_root, index, unit_id)
                atomic_write_json(artifact_path, artifact)
                relative_path = artifact_path.relative_to(run_root).as_posix()
                references[unit_id] = {
                    "path": relative_path,
                    "file_sha256": sha256_file(artifact_path),
                    "output_sha256": artifact["output_sha256"],
                }
                checkpoint = checkpoint_payload(
                    run_id=plan.identity["run_id"],
                    identity_sha256=plan.identity["identity_sha256"],
                    unit_order=plan.unit_order,
                    unit_artifacts=references,
                )
                atomic_write_json(run_root / "checkpoint.json", checkpoint)
                store.transition(
                    "progress",
                    data={
                        "unit_id": unit_id,
                        "completed_units": len(references),
                        "checkpoint_sha256": checkpoint["checkpoint_sha256"],
                    },
                    recorded_at=clock(),
                )
                processed_this_invocation += 1
                if (
                    interrupt_after is not None
                    and processed_this_invocation >= interrupt_after
                    and len(references) < len(plan.unit_order)
                ):
                    store.transition(
                        "fail",
                        data={
                            "failure_kind": "planned-interruption",
                            "completed_units": len(references),
                            "checkpoint_sha256": checkpoint["checkpoint_sha256"],
                        },
                        recorded_at=clock(),
                    )
                    return SmokeRunResult(
                        run_id=store.run_id,
                        run_root=run_root,
                        status="interrupted",
                        completed_units=len(references),
                        total_units=len(plan.unit_order),
                        final_manifest=None,
                    )

            checkpoint = read_json(run_root / "checkpoint.json")
            if not isinstance(checkpoint, dict):
                raise SmokePipelineError("checkpoint root must be an object")
            references = validate_checkpoint(
                checkpoint,
                plan=plan,
                run_root=run_root,
            )
            manifest = final_manifest(
                plan=plan,
                checkpoint=checkpoint,
                unit_artifacts=references,
            )
            final_path = run_root / "artifacts" / "final-manifest.json"
            atomic_write_json(final_path, manifest)
            validate_final_manifest(
                read_json(final_path),
                plan=plan,
                checkpoint=checkpoint,
                unit_artifacts=references,
            )
            store.transition(
                "complete",
                data={
                    "final_manifest_sha256": manifest["final_manifest_sha256"],
                    "unit_count": len(references),
                },
                recorded_at=clock(),
            )
        except BaseException as error:
            try:
                if store.state == "running":
                    store.transition(
                        "fail",
                        data={
                            "failure_kind": "pipeline-error",
                            "error_type": type(error).__name__,
                            "error_message_sha256": hashlib.sha256(
                                str(error).encode("utf-8")
                            ).hexdigest(),
                        },
                        recorded_at=clock(),
                    )
            except BaseException:
                pass
            raise

        verify_smoke_run(plan, run_root)
        return SmokeRunResult(
            run_id=store.run_id,
            run_root=run_root,
            status="complete",
            completed_units=len(plan.unit_order),
            total_units=len(plan.unit_order),
            final_manifest=manifest,
        )
