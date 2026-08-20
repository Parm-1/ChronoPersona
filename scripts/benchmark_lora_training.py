#!/usr/bin/env python3
"""Plan, run, verify, and compare the bounded Pythia LoRA training gate."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "runs" / "pythia-lora-smoke-v0.json"
DEFAULT_MANIFEST = ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json"
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "pythia-lora-smoke-v0"
HOST_TRAINING_LOCK = (
    Path(tempfile.gettempdir()) / "chronopersona-pythia-lora-training.lock"
)
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.artifact_policy import (  # noqa: E402
    assert_model_score_ready,
    find_artifact,
)
from chronopersona.content_manifest import (  # noqa: E402
    load_content_manifest,
    resolve_content_records,
)
from chronopersona.model_manifest import (  # noqa: E402
    load_model_manifest,
    validate_model_manifest,
)
from chronopersona.model_snapshot import verify_snapshot  # noqa: E402
from chronopersona.run_registry import (  # noqa: E402
    atomic_write_json,
    canonical_sha256,
    read_event_log,
    read_json,
    sha256_file,
)
from chronopersona.training_smoke import (  # noqa: E402
    TrainingPlan,
    TrainingSmokeError,
    build_training_plan,
    compare_training_runs,
    full_weight_adamw_capacity,
    load_training_config,
    pack_token_documents,
    run_training_condition,
    validate_load_report,
    verify_training_run,
)


def _canonical_path(path: Path, expected: Path, label: str) -> None:
    if path.resolve(strict=False) != expected.resolve(strict=False):
        raise TrainingSmokeError(f"execution requires the canonical committed {label}")


def _current_git_state() -> tuple[str, bool]:
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if head.returncode != 0 or status.returncode != 0 or not head.stdout.strip():
        raise TrainingSmokeError("cannot establish current Git state")
    return head.stdout.strip(), bool(status.stdout.strip())


def _json_with_sha(path: Path, label: str) -> tuple[dict[str, Any], str]:
    try:
        payload = path.read_bytes()
        raw = json.loads(payload)
    except (OSError, json.JSONDecodeError) as error:
        raise TrainingSmokeError(f"cannot load {label}: {error}") from error
    if not isinstance(raw, dict):
        raise TrainingSmokeError(f"{label} root must be an object")
    return raw, hashlib.sha256(payload).hexdigest()


def _load_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], str]:
    config = load_training_config(args.config)
    manifest_raw = load_model_manifest(args.manifest)
    errors = validate_model_manifest(manifest_raw)
    if errors:
        raise TrainingSmokeError("; ".join(errors))
    manifest = dict(manifest_raw)
    artifact = dict(find_artifact(manifest, config["artifact_id"]))
    assert_model_score_ready(artifact)
    return config, artifact, sha256_file(args.manifest)


def _static_plan(args: argparse.Namespace) -> dict[str, Any]:
    config, artifact, manifest_sha = _load_inputs(args)
    capacity = full_weight_adamw_capacity(
        int(artifact["parameter_count"]),
        6_441_992_192,
    )
    return {
        "schema_version": 1,
        "status": "planned",
        "run_kind": config["run_kind"],
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": artifact["revision"],
        "model_manifest_sha256": manifest_sha,
        "network_access_permitted": False,
        "weights_downloaded": False,
        "scientific_claim_authorized": False,
        "external_spend_cad": 0,
        "training_profile": {
            "method": "direct-torch-lora-engineering-smoke",
            "steps": config["steps"],
            "sequence_length": config["sequence_length"],
            "input_tokens": config["steps"] * config["sequence_length"],
            "causal_targets": config["steps"] * (config["sequence_length"] - 1),
            "checkpoint_after_step": config["checkpoint_after_step"],
            "lora": config["lora"],
            "optimizer": config["optimizer"],
        },
        "full_weight_adamw_capacity": capacity,
        "resource_limits": config["resource_limits"],
        "required_execution_inputs": [
            "clean exact Git head",
            "fresh cache-bound resource audit",
            "successful exact-head offline inference report",
            "hash-verified local snapshot",
        ],
    }


def _selected_content(
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str], str]:
    source = config["source"]
    manifest_path = ROOT / source["manifest"]
    all_records = load_content_manifest(manifest_path)
    by_id = {record["record_id"]: record for record in all_records}
    try:
        selected = [by_id[record_id] for record_id in source["record_ids"]]
    except KeyError as error:
        raise TrainingSmokeError(f"training fixture is absent from manifest: {error}") from error
    loaded = resolve_content_records(selected, content_root=ROOT / source["content_root"])
    if [record.manifest["record_id"] for record in loaded] != source["record_ids"]:
        raise TrainingSmokeError("training fixture order drifted")
    for record in loaded:
        if (
            record.manifest.get("synthetic_fixture") is not True
            or record.manifest.get("authorship_provenance") != "synthetic-fixture"
            or record.manifest.get("rights_status") != "eligible"
            or record.manifest.get("license_id") != "CC0-1.0-fixture"
        ):
            raise TrainingSmokeError("training fixture is not exact eligible CC0 synthetic content")
    return selected, [record.text for record in loaded], sha256_file(manifest_path)


def _runtime_identity(
    resource_preflight: Mapping[str, Any],
    parent_validation: Mapping[str, Any],
) -> dict[str, Any]:
    validation = resource_preflight.get("post_import_resource_validation")
    if not isinstance(validation, Mapping):
        raise TrainingSmokeError("post-import resource validation is missing")
    nvidia = validation.get("nvidia_smi_device")
    packages = validation.get("packages")
    if not isinstance(nvidia, Mapping) or not isinstance(packages, Mapping):
        raise TrainingSmokeError("resource validation lacks runtime identity")
    parent_device = parent_validation.get("device")
    if not isinstance(parent_device, Mapping):
        raise TrainingSmokeError("parent CUDA identity is missing")
    return {
        "python": {
            "version": parent_validation["python"],
            "implementation": platform.python_implementation(),
        },
        "packages": dict(packages),
        "torch": parent_validation["torch"],
        "transformers": parent_validation["transformers"],
        "compiled_cuda_version": parent_validation["compiled_cuda_version"],
        "cuda_device": {
            "name": parent_device["name"],
            "capability": parent_device["capability"],
            "total_memory_bytes": parent_device["total_memory_bytes"],
            "uuid": nvidia["uuid"],
            "driver_version": nvidia["driver_version"],
        },
    }


def _resource_preflight(
    args: argparse.Namespace,
    artifact: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Reuse the already-tested model gate rather than creating a second resource
    # identity implementation.  RAM is explicitly observed but not thresholded.
    import benchmark_model as model_benchmark

    preflight_args = argparse.Namespace(
        resource_audit=args.resource_audit,
        cache_dir=args.cache_dir,
        allow_download=False,
        execute=True,
        device="cuda",
        allow_low_ram=True,
    )
    preflight = model_benchmark._resource_preflight(preflight_args, dict(artifact))
    preflight = model_benchmark._live_execution_preflight(
        preflight_args, artifact, preflight
    )
    validation = preflight["execution_resource_validation"]
    observed_free = min(
        validation["audited_vram"]["conservative_free_bytes"],
        validation["live_vram"]["conservative_free_bytes"],
    )
    minimum = int(args._config["resource_limits"]["minimum_preload_free_vram_bytes"])
    if observed_free < minimum:
        raise TrainingSmokeError(
            f"preload free VRAM is below the training threshold: {observed_free} < {minimum}"
        )

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = args._config["determinism"][
        "cublas_workspace_config"
    ]
    try:
        import torch
        import transformers
    except ImportError as error:
        raise TrainingSmokeError("install the ChronoPersona models dependencies") from error
    parent = model_benchmark._verify_parent_runtime(
        torch, transformers, preflight, device="cuda"
    )
    preflight = model_benchmark._post_import_resource_preflight(
        preflight_args, artifact, preflight
    )
    post = preflight["post_import_resource_validation"]
    post_free = min(
        post["audited_vram"]["conservative_free_bytes"],
        post["live_vram"]["conservative_free_bytes"],
    )
    if post_free < minimum:
        raise TrainingSmokeError(
            f"post-import free VRAM is below the training threshold: {post_free} < {minimum}"
        )
    return preflight, parent


def _build_execution_plan(
    args: argparse.Namespace,
) -> tuple[TrainingPlan, dict[str, Any], dict[str, Any]]:
    _canonical_path(args.config, DEFAULT_CONFIG, "training config")
    _canonical_path(args.manifest, DEFAULT_MANIFEST, "model manifest")
    _canonical_path(args.output_root, DEFAULT_OUTPUT_ROOT, "training output root")
    config, artifact, manifest_sha = _load_inputs(args)
    setattr(args, "_config", config)
    git_commit, dirty = _current_git_state()
    if dirty:
        raise TrainingSmokeError("training execution requires a clean worktree")
    load_report, load_report_sha = _json_with_sha(args.load_report, "inference report")
    load_errors = validate_load_report(load_report, artifact=artifact, git_commit=git_commit)
    if load_errors:
        raise TrainingSmokeError("; ".join(load_errors))
    snapshot = verify_snapshot(
        args.snapshot_path,
        args.cache_dir,
        artifact,
        artifact["revision"],
    )
    preflight, parent = _resource_preflight(args, artifact)

    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise TrainingSmokeError("install the ChronoPersona models dependencies") from error
    tokenizer = AutoTokenizer.from_pretrained(
        args.snapshot_path,
        local_files_only=True,
        trust_remote_code=False,
    )
    records, texts, content_manifest_sha = _selected_content(config)
    token_documents: list[list[int]] = []
    for text in texts:
        encoded = tokenizer(text, add_special_tokens=False, truncation=False)
        token_ids = encoded.get("input_ids")
        if not isinstance(token_ids, list) or not token_ids or not all(
            isinstance(token, int) and not isinstance(token, bool) for token in token_ids
        ):
            raise TrainingSmokeError("tokenizer returned an invalid fixture token list")
        token_documents.append(token_ids)
    eos_id = tokenizer.eos_token_id
    if not isinstance(eos_id, int) or isinstance(eos_id, bool):
        raise TrainingSmokeError("tokenizer has no exact integer EOS token ID")
    packed = pack_token_documents(
        token_documents,
        eos_id,
        steps=int(config["steps"]),
        sequence_length=int(config["sequence_length"]),
    )
    tokenizer_files = [
        item
        for item in artifact["required_files"]
        if item["filename"] != "model.safetensors" and item["filename"] != "config.json"
    ]
    tokenizer_identity = {
        "class": type(tokenizer).__name__,
        "revision": artifact["revision"],
        "vocabulary_size": len(tokenizer),
        "eos_token_id": eos_id,
        "pad_token_id": tokenizer.pad_token_id,
        "required_files": tokenizer_files,
    }
    runtime_identity = _runtime_identity(preflight, parent)
    plan = build_training_plan(
        config,
        git_commit=git_commit,
        config_sha256=sha256_file(args.config),
        model_manifest_sha256=manifest_sha,
        artifact=artifact,
        load_report=load_report,
        load_report_sha256=load_report_sha,
        content_manifest_sha256=content_manifest_sha,
        content_records=records,
        tokenizer_identity=tokenizer_identity,
        runtime_identity=runtime_identity,
        packed_tokens=packed,
    )
    context = {
        "resource_audit_path": str(args.resource_audit.resolve(strict=True)),
        "resource_audit_sha256": preflight["resource_audit_sha256"],
        "live_resource_audit_sha256": preflight["live_resource_audit_sha256"],
        "post_import_resource_audit_sha256": preflight[
            "post_import_resource_audit_sha256"
        ],
        "resource_preflight": preflight,
        "parent_runtime_validation": parent,
        "snapshot_verification": snapshot,
        "inference_report_path": str(args.load_report.resolve(strict=True)),
        "inference_report_sha256": load_report_sha,
        "ram_threshold_override_requested": True,
        "ram_threshold_enforced": False,
        "host_training_lock_path": str(HOST_TRAINING_LOCK),
    }
    return plan, artifact, context


def _load_stored_plan(
    run_root: Path,
    *,
    allow_different_checkout: bool = False,
) -> TrainingPlan:
    identity = read_json(run_root / "identity.json")
    if not isinstance(identity, dict):
        raise TrainingSmokeError("stored run identity is invalid")
    scientific = identity.get("scientific_identity")
    if not isinstance(scientific, Mapping):
        raise TrainingSmokeError("stored scientific identity is invalid")
    plan_body = scientific.get("training_plan")
    plan_sha = scientific.get("plan_sha256")
    if not isinstance(plan_body, Mapping) or plan_sha != canonical_sha256(plan_body):
        raise TrainingSmokeError("stored training plan identity is invalid")
    current_head, current_dirty = _current_git_state()
    if not allow_different_checkout and (
        current_dirty or current_head != plan_body.get("git_commit")
    ):
        raise TrainingSmokeError(
            "verification requires the clean recorded checkout; pass the explicit "
            "forensic override to inspect from another checkout"
        )
    config = load_training_config(DEFAULT_CONFIG)
    if sha256_file(DEFAULT_CONFIG) != plan_body.get("config_sha256"):
        raise TrainingSmokeError("current committed config differs from the stored run")
    plan = dict(plan_body)
    plan["plan_sha256"] = plan_sha
    return TrainingPlan(config=config, plan=plan, identity=identity, token_blocks=())


def _write_output(path: Path | None, report: Mapping[str, Any]) -> None:
    if path is None:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    if path.exists():
        raise TrainingSmokeError(f"refusing to overwrite output report: {path}")
    atomic_write_json(path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def _cli_report(mode: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return one self-identifying, no-network CLI evidence envelope."""

    report = dict(payload)
    required = {
        "schema_version": 1,
        "mode": mode,
        "network_access_performed": False,
        "scientific_claim_authorized": False,
    }
    for key, expected in required.items():
        if key in report and report[key] != expected:
            raise TrainingSmokeError(f"CLI report has conflicting {key}")
        report[key] = expected
    report["cli_report_sha256"] = canonical_sha256(report)
    return report


def _output_target_error(args: argparse.Namespace) -> str | None:
    output = getattr(args, "output", None)
    if output is None:
        return None
    if output.exists():
        return f"refusing to overwrite output report: {output}"
    protected_roots = [DEFAULT_OUTPUT_ROOT]
    if args.command == "run":
        protected_roots.append(args.output_root)
    elif args.command == "verify":
        protected_roots.append(args.run_root)
    elif args.command == "compare":
        protected_roots.extend((args.control_root, args.resumed_root))
    resolved_output = output.resolve(strict=False)
    for protected_root in protected_roots:
        resolved_root = protected_root.resolve(strict=False)
        if resolved_output == resolved_root or resolved_output.is_relative_to(
            resolved_root
        ):
            return "the CLI report must be outside the immutable training run tree"
    return None


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    plan, _artifact, context = _build_execution_plan(args)
    from chronopersona.training_runtime import TorchTrainingBackend

    try:
        result = run_training_condition(
            plan,
            args.output_root,
            condition=args.condition,
            resume=args.resume,
            interrupt_after=args.interrupt_after,
            attempt_context=context,
            job_lock_path=HOST_TRAINING_LOCK,
            backend_factory=lambda current_plan, state: TorchTrainingBackend(
                current_plan,
                args.snapshot_path,
                state,
            ),
        )
    except Exception as error:
        failure_context: dict[str, Any] = {
            "condition": args.condition,
            "run_id": plan.identity["run_id"],
            "plan_sha256": plan.plan["plan_sha256"],
            "run_root": str(
                (args.output_root / args.condition / plan.identity["run_id"]).resolve(
                    strict=False
                )
            ),
        }
        run_root = Path(failure_context["run_root"])
        events_path = run_root / "events.jsonl"
        if events_path.is_file():
            try:
                event_log = read_event_log(
                    events_path, expected_run_id=plan.identity["run_id"]
                )
                fail_events = [
                    event
                    for event in event_log.events
                    if event["event_type"] == "fail"
                ]
                if fail_events:
                    data = fail_events[-1]["data"]
                    failure_context["completed_steps"] = data.get("completed_steps")
                    failure_context["tokens_seen"] = data.get("tokens_seen")
                    failure_context["attempt_report"] = data.get("attempt_report")
            except Exception:
                pass
        try:
            setattr(error, "chronopersona_failure_context", failure_context)
        except Exception:
            pass
        raise
    report = {
        "schema_version": 1,
        "status": result.status,
        "mode": "run",
        "condition": args.condition,
        "run_id": result.run_id,
        "run_root": str(result.run_root.resolve(strict=True)),
        "completed_steps": result.completed_steps,
        "plan_sha256": plan.plan["plan_sha256"],
        "network_access_performed": False,
        "scientific_claim_authorized": False,
        "final_manifest_sha256": (
            result.final_manifest.get("final_manifest_sha256")
            if result.final_manifest is not None
            else None
        ),
    }
    return report, 75 if result.status == "interrupted" else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="emit the no-network frozen plan")
    plan.add_argument("--output", type=Path)

    run = subparsers.add_parser("run", help="execute one exact offline condition")
    run.add_argument("--condition", choices=("control", "resumed"), required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--interrupt-after", type=int)
    run.add_argument("--cache-dir", type=Path, required=True)
    run.add_argument("--snapshot-path", type=Path, required=True)
    run.add_argument("--resource-audit", type=Path, required=True)
    run.add_argument("--load-report", type=Path, required=True)
    run.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser("verify", help="verify one completed run")
    verify.add_argument("--run-root", type=Path, required=True)
    verify.add_argument("--allow-different-checkout", action="store_true")
    verify.add_argument("--output", type=Path)

    compare = subparsers.add_parser("compare", help="compare control and resumed states")
    compare.add_argument("--control-root", type=Path, required=True)
    compare.add_argument("--resumed-root", type=Path, required=True)
    compare.add_argument("--allow-different-checkout", action="store_true")
    compare.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    output_error = _output_target_error(args)
    if output_error is not None:
        failure = _cli_report(
            args.command,
            {
                "status": "failed",
                "failure_stage": "output-preflight",
                "error_type": "TrainingSmokeError",
                "error_message": output_error,
            },
        )
        print(
            json.dumps(failure, indent=2, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    try:
        if args.command == "plan":
            report = _cli_report("plan", _static_plan(args))
            _write_output(args.output, report)
            return 0
        if args.command == "run":
            report, code = _run(args)
            report = _cli_report("run", report)
            _write_output(args.output, report)
            return code
        if args.command == "verify":
            plan = _load_stored_plan(
                args.run_root,
                allow_different_checkout=args.allow_different_checkout,
            )
            report = _cli_report(
                "verify", verify_training_run(plan, args.run_root)
            )
            _write_output(args.output, report)
            return 0
        if args.command == "compare":
            control_plan = _load_stored_plan(
                args.control_root,
                allow_different_checkout=args.allow_different_checkout,
            )
            resumed_plan = _load_stored_plan(
                args.resumed_root,
                allow_different_checkout=args.allow_different_checkout,
            )
            if control_plan.identity != resumed_plan.identity:
                raise TrainingSmokeError("control and resumed identities differ")
            report = _cli_report(
                "compare",
                compare_training_runs(
                    control_plan,
                    args.control_root,
                    args.resumed_root,
                ),
            )
            _write_output(args.output, report)
            return 0
        raise TrainingSmokeError(f"unsupported command: {args.command}")
    except Exception as error:
        failure_payload = {
            "status": "failed",
            "failure_stage": "training-cli",
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        failure_context = getattr(error, "chronopersona_failure_context", None)
        if isinstance(failure_context, Mapping):
            failure_payload["failure_stage"] = "training-condition"
            failure_payload.update(dict(failure_context))
        failure = _cli_report(args.command, failure_payload)
        output = getattr(args, "output", None)
        try:
            _write_output(output, failure)
        except Exception:
            print(json.dumps(failure, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
