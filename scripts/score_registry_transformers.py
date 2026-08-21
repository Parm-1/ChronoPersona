#!/usr/bin/env python3
"""Plan or execute the frozen verified-snapshot Pythia registry score."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "runs" / "pythia-development-score-v0.json"
DEFAULT_MANIFEST = ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json"
DEFAULT_REGISTRY = ROOT / "evaluations" / "registry" / "development-v0.jsonl"
HOST_HEAVY_JOB_LOCK = (
    Path(tempfile.gettempdir()) / "chronopersona-pythia-lora-training.lock"
)
LOCAL_OUTPUT_ROOT = ROOT / "artifacts" / "local"
sys.path.insert(0, str(ROOT / "src"))

import audit_registry_tokenizer as tokenizer_cli  # noqa: E402

from chronopersona.artifact_policy import (  # noqa: E402
    assert_model_score_ready,
    find_artifact,
    operation_plan,
)
from chronopersona.evaluation import (  # noqa: E402
    canonical_json_sha256,
    validate_evaluation_registry,
)
from chronopersona.model_manifest import validate_model_manifest  # noqa: E402
from chronopersona.model_snapshot import verify_snapshot  # noqa: E402
from chronopersona.path_policy import (  # noqa: E402
    PortablePathError,
    portable_path_identity,
    portable_relative_path,
)
from chronopersona.run_registry import RunLock, build_run_identity  # noqa: E402
from chronopersona.scoring import (  # noqa: E402
    execution_trace_for_registry,
    score_evaluation_registry,
)
from chronopersona.scoring_runtime import (  # noqa: E402
    V1_SCORING_PROFILE,
    ScoringRunError,
    create_only_json,
    expected_tokenizer_id,
    finalize_score_artifact,
    load_accepted_tokenizer_audit,
    load_scoring_config,
    pretty_json_bytes,
    receipt_with_self_hash,
    scoring_profile,
    scoring_profile_for_relative_path,
    scoring_run_identity_payload,
    expected_execution_mode,
    validate_complete_receipt,
    validate_score_artifact,
    validate_scoring_config,
)
from chronopersona.transformers_provider import (  # noqa: E402
    TransformersContinuationProvider,
    load_manifest_model,
    load_manifest_tokenizer,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or run the frozen offline Pythia development-registry score. "
            "Execution publishes a deterministic score and separate runtime receipt."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--prefix-policy", choices=("none", "bos"), required=True)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--device", choices=("cpu", "cuda", "cuda:0"), default="cuda:0")
    parser.add_argument(
        "--dtype",
        choices=("auto", "float16", "bfloat16", "float32"),
        default="float16",
    )
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--snapshot-path", type=Path)
    parser.add_argument("--resource-audit", type=Path)
    parser.add_argument("--tokenizer-audit", type=Path)
    parser.add_argument("--attempt", choices=("a", "b"))
    parser.add_argument("--allow-low-ram", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--output", type=Path, help="score artifact or plan output")
    parser.add_argument("--runtime-output", type=Path)
    return parser


def _set_stage(args: argparse.Namespace, stage: str) -> None:
    setattr(args, "_failure_stage", stage)


def _require_canonical_path(path: Path, expected: Path, label: str) -> None:
    if any(part in {".", ".."} for part in path.parts):
        raise ScoringRunError(f"{label} contains a path-normalization alias")
    raw_candidate = path if path.is_absolute() else Path.cwd() / path
    raw_expected = expected if expected.is_absolute() else Path.cwd() / expected
    if str(raw_candidate) != str(raw_expected):
        raise ScoringRunError(f"scoring execution requires the canonical {label}")
    candidate = Path(os.path.abspath(path))
    canonical = Path(os.path.abspath(expected))
    if candidate != canonical or path.resolve(strict=True) != expected.resolve(
        strict=True
    ):
        raise ScoringRunError(f"scoring execution requires the canonical {label}")


def _selected_profile(config_path: Path):
    candidate = Path(os.path.abspath(config_path))
    for relative in (
        "configs/runs/pythia-development-score-v0.json",
        "configs/runs/pythia-development-score-v1.json",
    ):
        expected = ROOT / relative
        if candidate == Path(os.path.abspath(expected)):
            _require_canonical_path(config_path, expected, "scoring config")
            return scoring_profile_for_relative_path(relative)
    raise ScoringRunError("scoring config path is not allowlisted")


def _preflight_output(path: Path | None, label: str) -> None:
    if path is not None and os.path.lexists(path):
        raise ScoringRunError(f"refusing to overwrite existing {label}: {path}")


def _require_output_location(
    output: Path,
    *,
    cache_dir: Path | None,
    snapshot_path: Path | None,
    label: str,
) -> tuple[str, ...]:
    if any(part in {".", ".."} for part in output.parts):
        raise ScoringRunError(f"{label} contains a path-normalization alias")
    raw_candidate = output if output.is_absolute() else Path.cwd() / output
    raw_root = (
        LOCAL_OUTPUT_ROOT
        if LOCAL_OUTPUT_ROOT.is_absolute()
        else Path.cwd() / LOCAL_OUTPUT_ROOT
    )
    candidate = Path(os.path.abspath(output))
    lexical_root = Path(os.path.abspath(LOCAL_OUTPUT_ROOT))
    root_info = os.lstat(LOCAL_OUTPUT_ROOT)
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or stat.S_ISLNK(root_info.st_mode)
        or bool(
            getattr(root_info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
        )
    ):
        raise ScoringRunError("canonical artifacts/local root is linked or invalid")
    local_root = LOCAL_OUTPUT_ROOT.resolve(strict=True)
    if not candidate.is_relative_to(lexical_root) or candidate == lexical_root:
        raise ScoringRunError(
            f"{label} must be a new file under the canonical artifacts/local root"
        )
    try:
        relative = raw_candidate.relative_to(raw_root)
    except ValueError as error:
        raise ScoringRunError(
            f"{label} must be a new file under the canonical artifacts/local root"
        ) from error
    try:
        portable = portable_relative_path(relative.as_posix(), label=label)
    except PortablePathError as error:
        raise ScoringRunError(str(error)) from error
    portable_identity = portable_path_identity(portable.as_posix(), label=label)
    current = lexical_root
    relative_parent = candidate.parent.relative_to(lexical_root)
    for part in relative_parent.parts:
        current = current / part
        info = os.lstat(current)
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or bool(
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
            )
        ):
            raise ScoringRunError(f"{label} parent traverses a linked directory")
    for sibling in candidate.parent.iterdir():
        if (
            sibling.name != candidate.name
            and sibling.name.casefold() == candidate.name.casefold()
        ):
            raise ScoringRunError(
                f"{label} collides under portable filesystem semantics"
            )
    resolved_candidate = candidate.resolve(strict=False)
    if not resolved_candidate.is_relative_to(local_root):
        raise ScoringRunError(f"{label} resolves outside canonical artifacts/local")
    roots: list[tuple[Path, str]] = []
    if cache_dir is not None:
        roots.append((cache_dir.resolve(strict=True), "model cache"))
    if snapshot_path is not None:
        roots.append((snapshot_path.resolve(strict=True), "model snapshot"))
    for root, root_label in roots:
        if resolved_candidate.is_relative_to(root):
            raise ScoringRunError(f"{label} must be outside the {root_label}")
    return portable_identity


def _output_storage_observation(
    args: argparse.Namespace,
    config: dict[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    assert args.output is not None and args.runtime_output is not None
    minimum = config["resource_limits"]["minimum_output_free_bytes"]
    outputs: dict[str, Any] = {}
    for label, path in (
        ("score", args.output),
        ("runtime", args.runtime_output),
    ):
        _require_output_location(
            path,
            cache_dir=args.cache_dir,
            snapshot_path=args.snapshot_path,
            label=f"{label} output",
        )
        parent = path.resolve(strict=False).parent
        info = os.lstat(parent)
        free = int(shutil.disk_usage(parent).free)
        if free < minimum:
            raise ScoringRunError(
                f"{label} output filesystem is below the frozen reserve"
            )
        outputs[label] = {
            "filesystem_device": int(info.st_dev),
            "free_bytes": free,
        }
    return {
        "phase": phase,
        "minimum_free_bytes": minimum,
        "outputs": outputs,
        "passed": True,
    }


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (int(left.st_dev), int(left.st_ino)) == (
        int(right.st_dev),
        int(right.st_ino),
    )


class _OutputPairReservation:
    """Reserve and publish one score/receipt pair without overwriting paths."""

    def __init__(self, score_path: Path, runtime_path: Path) -> None:
        self.paths = {"score": score_path, "runtime": runtime_path}
        self.descriptors: dict[str, int] = {}
        self.identities: dict[str, os.stat_result] = {}
        self.written: set[str] = set()
        self.active = True
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_BINARY", 0)
        try:
            for label in ("score", "runtime"):
                path = self.paths[label]
                parent_before = os.lstat(path.parent)
                descriptor = os.open(path, flags, 0o600)
                self.descriptors[label] = descriptor
                opened = os.fstat(descriptor)
                self.identities[label] = opened
                observed = os.lstat(path)
                parent_after = os.lstat(path.parent)
                if (
                    not stat.S_ISREG(observed.st_mode)
                    or stat.S_ISLNK(observed.st_mode)
                    or not _same_file_identity(opened, observed)
                    or not _same_file_identity(parent_before, parent_after)
                ):
                    raise ScoringRunError(
                        f"reserved {label} output is not a plain owned file"
                    )
        except BaseException:
            self.rollback()
            raise

    def _require_owned(self, label: str) -> None:
        descriptor = self.descriptors.get(label)
        if descriptor is None:
            raise ScoringRunError(f"{label} output reservation is unavailable")
        path = self.paths[label]
        if not os.path.lexists(path):
            raise ScoringRunError(f"reserved {label} output disappeared")
        observed = os.lstat(path)
        if not _same_file_identity(os.fstat(descriptor), observed):
            raise ScoringRunError(f"reserved {label} output identity changed")

    def _write(self, label: str, value: Any) -> tuple[int, str]:
        if label in self.written:
            raise ScoringRunError(f"reserved {label} output was already written")
        self._require_owned(label)
        payload = pretty_json_bytes(value)
        descriptor = self.descriptors[label]
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"could not write reserved {label} output")
            view = view[written:]
        os.fsync(descriptor)
        if os.fstat(descriptor).st_size != len(payload):
            raise ScoringRunError(f"reserved {label} output size mismatch")
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        observed_payload = b"".join(chunks)
        self._require_owned(label)
        if observed_payload != payload:
            raise ScoringRunError(f"reserved {label} output bytes mismatch")
        self.written.add(label)
        return len(observed_payload), hashlib.sha256(observed_payload).hexdigest()

    def write_success(
        self,
        score: dict[str, Any],
        receipt: dict[str, Any],
    ) -> tuple[tuple[int, str], tuple[int, str]]:
        try:
            return self._write("score", score), self._write("runtime", receipt)
        except BaseException:
            self.rollback()
            raise

    def write_score(self, score: dict[str, Any]) -> tuple[int, str]:
        try:
            return self._write("score", score)
        except BaseException:
            self.rollback()
            raise

    def write_runtime(self, receipt: dict[str, Any]) -> tuple[int, str]:
        try:
            return self._write("runtime", receipt)
        except BaseException:
            self.rollback()
            raise

    def commit(self) -> None:
        if self.written != {"score", "runtime"}:
            raise ScoringRunError("cannot commit an incomplete output pair")
        for label in ("score", "runtime"):
            self._require_owned(label)
            os.close(self.descriptors.pop(label))
        self.active = False

    def publish_failure(self, receipt: dict[str, Any]) -> None:
        if not self.active:
            raise ScoringRunError("output reservation is no longer active")
        try:
            self._remove("score")
            self._write("runtime", receipt)
            self._require_owned("runtime")
            os.close(self.descriptors.pop("runtime"))
            self.active = False
        except BaseException:
            self.rollback()
            raise

    def _remove(self, label: str) -> None:
        descriptor = self.descriptors.pop(label, None)
        expected = self.identities.get(label)
        ownership_error: Exception | None = None
        if descriptor is not None:
            try:
                if expected is None or not _same_file_identity(
                    os.fstat(descriptor), expected
                ):
                    ownership_error = ScoringRunError(
                        f"retained {label} output identity changed"
                    )
            finally:
                os.close(descriptor)
        path = self.paths[label]
        if os.path.lexists(path):
            observed = os.lstat(path)
            if expected is None or not _same_file_identity(expected, observed):
                ownership_error = ScoringRunError(
                    f"refusing to remove changed {label} output reservation"
                )
            else:
                path.unlink(missing_ok=False)
        if ownership_error is not None:
            raise ownership_error

    def rollback(self) -> None:
        if not getattr(self, "active", False):
            return
        errors: list[Exception] = []
        for label in ("score", "runtime"):
            try:
                self._remove(label)
            except Exception as error:
                errors.append(error)
        self.active = False
        if errors:
            raise ScoringRunError(
                "could not safely roll back owned output reservations: "
                + "; ".join(str(error) for error in errors)
            )


def _bound_execution_inputs(profile) -> tuple[dict[str, Any], dict[str, bytes]]:
    extra_inputs: list[tuple[str, Path]] = [
        ("scoring_config", ROOT / profile.config_path)
    ]
    if profile.criteria_path is not None:
        extra_inputs.append(
            ("measurement_reliability_criteria", ROOT / profile.criteria_path)
        )
    binding, payloads = tokenizer_cli._execution_git_binding(
        registry_path=ROOT / profile.registry_path,
        extra_inputs=tuple(extra_inputs),
    )
    return dict(binding), payloads


def _execution_inputs(
    args: argparse.Namespace,
    profile,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, bytes],
    str,
    str,
    str,
]:
    _require_canonical_path(
        args.config, ROOT / profile.config_path, "scoring config"
    )
    _require_canonical_path(args.manifest, DEFAULT_MANIFEST, "model manifest")
    _require_canonical_path(
        args.registry, ROOT / profile.registry_path, "development registry"
    )
    binding, payloads = _bound_execution_inputs(profile)
    try:
        config_raw = json.loads(payloads["scoring_config"])
    except json.JSONDecodeError as error:
        raise ScoringRunError(f"canonical scoring config is invalid: {error}") from error
    if not isinstance(config_raw, dict):
        raise ScoringRunError("canonical scoring config root must be an object")
    errors = validate_scoring_config(config_raw)
    if errors:
        raise ScoringRunError("; ".join(errors))
    config = dict(config_raw)
    if scoring_profile(config) != profile:
        raise ScoringRunError("scoring config/profile selection mismatch")
    manifest = tokenizer_cli._manifest_from_bytes(payloads["model_manifest"])
    registry = tokenizer_cli._registry_from_bytes(payloads["development_registry"])
    manifest_errors = validate_model_manifest(manifest)
    registry_errors = validate_evaluation_registry(registry)
    if manifest_errors:
        raise ScoringRunError("; ".join(manifest_errors))
    if registry_errors:
        raise ScoringRunError("; ".join(registry_errors))
    artifact = dict(find_artifact(manifest, config["artifact"]["id"]))
    assert_model_score_ready(artifact)
    config_sha256 = profile.run_spec_sha256
    manifest_sha256 = hashlib.sha256(payloads["model_manifest"]).hexdigest()
    registry_sha256 = hashlib.sha256(payloads["development_registry"]).hexdigest()
    canonical = config["canonical_inputs"]
    for label, observed, expected in (
        ("model manifest SHA-256", manifest_sha256, canonical["manifest_sha256"]),
        ("registry SHA-256", registry_sha256, canonical["registry_sha256"]),
        (
            "model manifest Git blob",
            binding["model_manifest_git_blob"],
            canonical["manifest_git_blob"],
        ),
        (
            "registry Git blob",
            binding["development_registry_git_blob"],
            canonical["registry_git_blob"],
        ),
        (
            "scoring config Git blob",
            binding["scoring_config_git_blob"],
            profile.config_git_blob,
        ),
    ):
        if observed != expected:
            raise ScoringRunError(f"frozen {label} mismatch")
    if profile.criteria_path is not None:
        reliability = config.get("measurement_reliability")
        criteria_payload = payloads.get("measurement_reliability_criteria")
        if not isinstance(reliability, Mapping) or not isinstance(
            criteria_payload, bytes
        ):
            raise ScoringRunError("measurement-reliability criteria are missing")
        if (
            hashlib.sha256(criteria_payload).hexdigest()
            != reliability["criteria_file_sha256"]
            or binding.get("measurement_reliability_criteria_git_blob")
            != reliability["criteria_git_blob"]
        ):
            raise ScoringRunError("frozen measurement-reliability criteria mismatch")
        try:
            criteria = json.loads(criteria_payload)
        except json.JSONDecodeError as error:
            raise ScoringRunError(
                f"measurement-reliability criteria are invalid: {error}"
            ) from error
        if not isinstance(criteria, Mapping):
            raise ScoringRunError("measurement-reliability criteria root is invalid")
        criteria_body = dict(criteria)
        observed_self_hash = criteria_body.pop("criteria_sha256", None)
        if (
            observed_self_hash != reliability["criteria_sha256"]
            or canonical_json_sha256(criteria_body) != observed_self_hash
            or criteria.get("profile_id") != reliability["profile_id"]
            or criteria.get("registry", {}).get("sha256") != registry_sha256
        ):
            raise ScoringRunError(
                "measurement-reliability criteria identity mismatch"
            )
    return (
        config,
        artifact,
        registry,
        binding,
        payloads,
        config_sha256,
        manifest_sha256,
        registry_sha256,
    )


def _pre_execution_policy(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], Path, Any]:
    """Fail on canonical path, artifact policy, and arguments before Git work."""

    profile = _selected_profile(args.config)
    _require_canonical_path(args.manifest, DEFAULT_MANIFEST, "model manifest")
    _require_canonical_path(
        args.registry, ROOT / profile.registry_path, "development registry"
    )
    config = load_scoring_config(args.config)
    if scoring_profile(config) != profile:
        raise ScoringRunError("scoring config/profile selection mismatch")
    manifest = tokenizer_cli._manifest_from_bytes(args.manifest.read_bytes())
    errors = validate_model_manifest(manifest)
    if errors:
        raise ScoringRunError("; ".join(errors))
    requested_artifact = find_artifact(manifest, args.artifact)
    assert_model_score_ready(requested_artifact)
    tokenizer_audit_path = _validate_execution_arguments(args, config)
    return config, tokenizer_audit_path, profile


def _validate_execution_arguments(
    args: argparse.Namespace,
    config: dict[str, Any],
) -> Path:
    required_paths = {
        "--cache-dir": args.cache_dir,
        "--snapshot-path": args.snapshot_path,
        "--resource-audit": args.resource_audit,
        "--output": args.output,
        "--runtime-output": args.runtime_output,
    }
    missing = [label for label, value in required_paths.items() if value is None]
    if missing or args.attempt is None:
        detail = ", ".join(missing + (["--attempt"] if args.attempt is None else []))
        raise ScoringRunError(f"--execute requires explicit {detail}")
    if (
        args.artifact != config["artifact"]["id"]
        or args.prefix_policy != config["accepted_tokenizer_audit"]["prefix_policy"]
        or args.max_length != config["scoring"]["maximum_length"]
        or args.device != config["model"]["device"]
        or args.dtype != config["model"]["dtype"]
    ):
        raise ScoringRunError("execution arguments differ from the frozen scoring config")
    if not args.allow_low_ram:
        raise ScoringRunError(
            "the frozen user-authorized RAM threshold override requires --allow-low-ram"
        )
    configured_audit = ROOT / config["accepted_tokenizer_audit"]["path"]
    selected_audit = args.tokenizer_audit or configured_audit
    _require_canonical_path(
        selected_audit,
        configured_audit,
        "accepted tokenizer audit",
    )
    assert args.output is not None and args.runtime_output is not None
    if args.output.resolve(strict=False) == args.runtime_output.resolve(strict=False):
        raise ScoringRunError("score and runtime outputs must be distinct")
    score_path = args.output.resolve(strict=False)
    runtime_path = args.runtime_output.resolve(strict=False)
    if score_path in runtime_path.parents or runtime_path in score_path.parents:
        raise ScoringRunError("score and runtime outputs must not contain one another")
    score_identity = _require_output_location(
        args.output,
        cache_dir=args.cache_dir,
        snapshot_path=args.snapshot_path,
        label="score output",
    )
    runtime_identity = _require_output_location(
        args.runtime_output,
        cache_dir=args.cache_dir,
        snapshot_path=args.snapshot_path,
        label="runtime output",
    )
    if score_identity == runtime_identity:
        raise ScoringRunError(
            "score and runtime outputs collide under portable filesystem semantics"
        )
    setattr(
        args,
        "_output_storage_preflight",
        _output_storage_observation(args, config, phase="preflight"),
    )
    return selected_audit


def _require_wall_headroom(
    args: argparse.Namespace,
    config: dict[str, Any],
    label: str,
) -> float:
    started = getattr(args, "_wall_start", None)
    if not isinstance(started, float):
        raise ScoringRunError("scoring wall timer is unavailable")
    elapsed = time.perf_counter() - started
    if elapsed > config["resource_limits"]["maximum_invocation_wall_seconds"]:
        raise ScoringRunError(f"scoring invocation exceeded the wall limit at {label}")
    return elapsed


def _commit_output_pair_after_lock(
    reservation: _OutputPairReservation,
    *,
    wall_start: float,
    maximum_wall_seconds: float,
) -> None:
    if time.perf_counter() - wall_start > maximum_wall_seconds:
        raise ScoringRunError(
            "scoring invocation exceeded the wall limit during lock release"
        )
    reservation.commit()


def _resource_preflight(
    args: argparse.Namespace,
    artifact: dict[str, Any],
    config: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    import benchmark_model as model_benchmark

    preflight_args = argparse.Namespace(
        resource_audit=args.resource_audit,
        cache_dir=args.cache_dir,
        allow_download=False,
        execute=True,
        device="cuda",
        allow_low_ram=True,
    )
    state: dict[str, Any] = {"preflight": {}}
    setattr(args, "_resource_state", state)
    limits = config["resource_limits"]
    minimum_preload_vram = limits["minimum_preload_free_vram_bytes"]
    try:
        preflight = model_benchmark._resource_preflight(preflight_args, artifact)
        state["preflight"] = preflight
        preflight = model_benchmark._live_execution_preflight(
            preflight_args,
            artifact,
            preflight,
            minimum_free_vram_bytes=minimum_preload_vram,
        )
        live_audit = preflight.get("live_resource_audit")
        if not isinstance(live_audit, Mapping):
            raise ScoringRunError("live resource audit is missing after preflight")
        preflight["live_resource_audit_semantic_sha256"] = (
            canonical_json_sha256(live_audit)
        )
        state["preflight"] = preflight
    except Exception:
        preserved = getattr(preflight_args, "_resource_preflight", None)
        if not isinstance(preserved, Mapping):
            preserved = getattr(preflight_args, "_resource_audit_binding", None)
        if isinstance(preserved, Mapping):
            state["preflight"] = dict(preserved)
        raise
    minimum_disk = limits["minimum_staging_output_free_bytes"]
    audited_disk = preflight.get("audit_disk_free_bytes")
    live_disk = shutil.disk_usage(Path(preflight["cache_storage_path"])).free
    if not isinstance(audited_disk, int) or min(audited_disk, live_disk) < minimum_disk:
        raise ScoringRunError("free disk is below the frozen private-staging threshold")

    def before_deserialization(torch: Any, transformers: Any) -> None:
        current = state["preflight"]
        state["parent_runtime_validation"] = model_benchmark._verify_parent_runtime(
            torch, transformers, current, device="cuda"
        )
        current = model_benchmark._post_import_resource_preflight(
            preflight_args,
            artifact,
            current,
            minimum_free_vram_bytes=minimum_preload_vram,
        )
        post_import_audit = current.get("post_import_resource_audit")
        if not isinstance(post_import_audit, Mapping):
            raise ScoringRunError("post-import resource audit is missing")
        current["post_import_resource_audit_semantic_sha256"] = (
            canonical_json_sha256(post_import_audit)
        )
        if shutil.disk_usage(Path(current["cache_storage_path"])).free < limits[
            "minimum_output_free_bytes"
        ]:
            raise ScoringRunError(
                "pre-deserialization disk is below the frozen output reserve"
            )
        state["preflight"] = current

    state["before_deserialization"] = before_deserialization
    return model_benchmark, state


def _resident_resource_check(
    model_benchmark: Any,
    state: dict[str, Any],
    artifact: dict[str, Any],
    config: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    preflight = state["preflight"]
    reference = preflight.get("post_import_resource_audit")
    if not isinstance(reference, dict):
        raise ScoringRunError("post-import resource audit is missing")
    observed, observed_sha256 = model_benchmark._capture_live_resource_audit(
        Path(preflight["cache_storage_path"])
    )
    age = model_benchmark._resource_audit_age_seconds(observed)
    minimum = config["resource_limits"][
        "minimum_postload_global_free_vram_bytes"
    ]
    pending_resource = {
        "label": label,
        "audit_sha256": observed_sha256,
        "audit_semantic_sha256": canonical_json_sha256(observed),
        "captured_at": observed.get("captured_at"),
        "age_seconds": age,
        "minimum_free_vram_bytes": minimum,
        "audit": observed,
    }
    state["pending_resident_resource_check"] = pending_resource
    try:
        validation = model_benchmark._validate_execution_resources(
            reference,
            observed,
            artifact,
            require_cuda=True,
            enforce_ram_threshold=False,
            minimum_free_vram_bytes=minimum,
        )
    except Exception:
        try:
            pending_resource["conservative_vram"] = (
                model_benchmark._conservative_vram(observed)
            )
        except Exception as observation_error:
            pending_resource["conservative_vram_error"] = {
                "error_type": type(observation_error).__name__,
                "error": str(observation_error),
            }
        raise
    conservative = model_benchmark._conservative_vram(observed)
    pending_resource["conservative_vram"] = conservative
    if conservative["conservative_free_bytes"] < minimum:
        raise ScoringRunError(f"{label} global free VRAM is below the frozen threshold")
    state.pop("pending_resident_resource_check", None)
    return {
        "label": label,
        "audit_sha256": observed_sha256,
        "audit_semantic_sha256": canonical_json_sha256(observed),
        "captured_at": observed.get("captured_at"),
        "age_seconds": age,
        "conservative_vram": conservative,
        "execution_resource_validation": validation,
        "audit": observed,
    }


def _final_integrity_rebind(
    args: argparse.Namespace,
    *,
    profile: Any,
    artifact: Mapping[str, Any],
    snapshot_receipt: Mapping[str, Any],
    git_binding: Mapping[str, Any],
    input_payloads: Mapping[str, bytes],
    tokenizer_audit_path: Path,
    tokenizer_audit_file_sha256: str,
    tokenizer_audit: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    final_snapshot = verify_snapshot(args.snapshot_path, args.cache_dir, artifact)
    if final_snapshot["portable_receipt"] != snapshot_receipt:
        raise ScoringRunError("snapshot changed during registry scoring")
    final_binding, final_payloads = _bound_execution_inputs(profile)
    if final_binding != git_binding or final_payloads != input_payloads:
        raise ScoringRunError("Git head or canonical inputs changed during scoring")
    final_tokenizer_audit, final_tokenizer_sha = load_accepted_tokenizer_audit(
        tokenizer_audit_path, config
    )
    if (
        final_tokenizer_sha != tokenizer_audit_file_sha256
        or final_tokenizer_audit != tokenizer_audit
    ):
        raise ScoringRunError("accepted tokenizer audit changed during scoring")


def _execute(args: argparse.Namespace) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    wall_start = time.perf_counter()
    setattr(args, "_started_at", started_at)
    setattr(args, "_wall_start", wall_start)
    setattr(
        args,
        "_failure_context",
        {"started_at": started_at, "process_id": os.getpid()},
    )
    _set_stage(args, "artifact-policy-and-options")
    initial_config, tokenizer_audit_path, profile = _pre_execution_policy(args)
    _set_stage(args, "canonical-input-binding")
    (
        config,
        artifact,
        registry,
        git_binding,
        input_payloads,
        config_sha256,
        manifest_sha256,
        registry_sha256,
    ) = _execution_inputs(args, profile)
    if config != initial_config:
        raise ScoringRunError("scoring config changed before canonical binding")
    assert args.output is not None and args.runtime_output is not None
    args._failure_context.update(
        {
            "git": git_binding,
            "run_spec": {
                "sha256": config_sha256,
                "git_blob": git_binding["scoring_config_git_blob"],
            },
            "canonical_inputs": {
                "model_manifest_sha256": manifest_sha256,
                "registry_sha256": registry_sha256,
            },
        }
    )
    execution_mode = expected_execution_mode(config, str(args.attempt))
    if execution_mode is not None:
        args._failure_context["execution_mode"] = execution_mode
    _set_stage(args, "accepted-tokenizer-audit")
    tokenizer_audit, tokenizer_audit_file_sha256 = load_accepted_tokenizer_audit(
        tokenizer_audit_path, config
    )
    args._failure_context["accepted_tokenizer"] = {
        "file_sha256": tokenizer_audit_file_sha256,
        "output_sha256": tokenizer_audit["output_sha256"],
    }
    identity = build_run_identity(
        scoring_run_identity_payload(config, str(git_binding["git_head"]))
    )
    setattr(args, "_run_id", identity["run_id"])
    reservation_storage = _output_storage_observation(
        args, config, phase="reservation"
    )
    args._failure_context["output_storage_reservation"] = reservation_storage
    reservation = _OutputPairReservation(args.output, args.runtime_output)
    setattr(args, "_output_reservation", reservation)
    _set_stage(args, "resource-preflight")
    model_benchmark, resource_state = _resource_preflight(args, artifact, config)
    setattr(args, "_resource_state", resource_state)
    args._failure_context["resource_preflight"] = resource_state["preflight"]

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = config["determinism"][
        "cublas_workspace_config"
    ]
    _set_stage(args, "heavy-job-lock")
    with RunLock(HOST_HEAVY_JOB_LOCK, run_id=identity["run_id"]):
        _require_wall_headroom(args, config, "heavy-job-lock acquisition")
        _set_stage(args, "verified-tokenizer-load")
        loaded_tokenizer = load_manifest_tokenizer(
            artifact,
            cache_dir=args.cache_dir,
            snapshot_path=args.snapshot_path,
            manifest_path=args.manifest,
            expected_manifest_sha256=manifest_sha256,
        )
        if (
            dict(loaded_tokenizer.snapshot_verification)
            != tokenizer_audit["snapshot_verification"]
            or dict(loaded_tokenizer.tokenizer_validation)
            != tokenizer_audit["loaded_tokenizer_validation"]
            or dict(loaded_tokenizer.runtime_identity)
            != tokenizer_audit["runtime_identity"]
        ):
            raise ScoringRunError(
                "live tokenizer identity differs from the accepted tokenizer audit"
            )
        args._failure_context.update(
            {
                "snapshot_verification": dict(
                    loaded_tokenizer.snapshot_verification
                ),
                "tokenizer_validation": dict(
                    loaded_tokenizer.tokenizer_validation
                ),
                "tokenizer_runtime_identity": dict(
                    loaded_tokenizer.runtime_identity
                ),
            }
        )
        _require_wall_headroom(args, config, "tokenizer loading")

        _set_stage(args, "verified-model-load")
        loaded_model = load_manifest_model(
            artifact,
            loaded_tokenizer=loaded_tokenizer,
            cache_dir=args.cache_dir,
            snapshot_path=args.snapshot_path,
            manifest_path=args.manifest,
            expected_manifest_sha256=manifest_sha256,
            device=config["model"]["device"],
            dtype=config["model"]["dtype"],
            expected_model=config["model"],
            expected_determinism=config["determinism"],
            expected_runtime=config["runtime_identity"],
            pre_deserialization_check=resource_state["before_deserialization"],
        )
        args._failure_context.update(
            {
                "model_validation": dict(loaded_model.model_validation),
                "model_loading_info": dict(loaded_model.loading_info),
                "runtime_identity": dict(loaded_model.runtime_identity),
            }
        )
        _require_wall_headroom(args, config, "model loading")
        _set_stage(args, "resident-resource-preflight")
        post_load_resource = _resident_resource_check(
            model_benchmark, resource_state, artifact, config, label="post-load"
        )
        args._failure_context["post_load_resource"] = post_load_resource

        _set_stage(args, "registry-scoring")
        provider = TransformersContinuationProvider(
            loaded_model,
            prefix_policy=config["accepted_tokenizer_audit"]["prefix_policy"],
            max_length=config["scoring"]["maximum_length"],
        )
        if provider.prefix_token_ids != tuple(
            config["accepted_tokenizer_audit"]["prefix_token_ids"]
        ):
            raise ScoringRunError("provider prefix token IDs differ from the freeze")
        setattr(args, "_provider", provider)

        def bounded_provider(prompt: str, continuation: str):
            _require_wall_headroom(args, config, "candidate pre-forward")
            evidence = provider(prompt, continuation)
            _require_wall_headroom(args, config, "candidate post-forward")
            return evidence

        execution_trace: list[dict[str, Any]] = []
        base_score = score_evaluation_registry(
            registry,
            bounded_provider,
            registry_sha256=registry_sha256,
            model_id=str(artifact["id"]),
            model_revision=loaded_model.revision,
            tokenizer_id=expected_tokenizer_id(config),
            scorer_version=config["scoring"]["scorer_version"],
            execution_mode=execution_mode or "canonical",
            execution_trace=execution_trace,
        )
        expected_trace = execution_trace_for_registry(
            registry, execution_mode or "canonical"
        )
        if execution_trace != expected_trace:
            raise ScoringRunError("provider execution trace differs from the freeze")
        execution_schedule = None
        if execution_mode is not None:
            execution_schedule = {
                "profile_id": profile.profile_id,
                "mode": execution_mode,
                "candidate_count": len(execution_trace),
                "trace_sha256": canonical_json_sha256(execution_trace),
                "canonical_serialization": True,
            }
            args._failure_context["execution_schedule"] = execution_schedule
        provider.assert_model_unchanged()
        score = finalize_score_artifact(
            base_score,
            tokenizer_audit=tokenizer_audit,
            config=config,
            run_spec_sha256=config_sha256,
            git_head=str(git_binding["git_head"]),
        )
        score_errors = validate_score_artifact(
            score,
            config,
            registry=registry,
            tokenizer_audit=tokenizer_audit,
        )
        if score_errors:
            raise ScoringRunError("; ".join(score_errors))
        runtime_metrics = provider.runtime_metrics()
        args._failure_context["scoring_metrics"] = runtime_metrics
        topology = config["registry_topology"]
        for key in (
            "forwarded_token_count",
            "predicted_token_count",
            "continuation_token_count",
            "maximum_full_token_count",
        ):
            if runtime_metrics[key] != topology[key]:
                raise ScoringRunError(f"runtime scoring topology mismatch: {key}")

        import torch

        target_device = torch.device("cuda:0")
        torch.cuda.synchronize(target_device)
        peak_allocated = int(torch.cuda.max_memory_allocated(target_device))
        peak_reserved = int(torch.cuda.max_memory_reserved(target_device))
        if peak_reserved > config["resource_limits"][
            "maximum_process_peak_reserved_bytes"
        ]:
            raise ScoringRunError("peak reserved VRAM exceeds the frozen threshold")
        _set_stage(args, "post-score-resource-check")
        post_score_resource = _resident_resource_check(
            model_benchmark, resource_state, artifact, config, label="post-score"
        )
        args._failure_context["post_score_resource"] = post_score_resource
        _require_wall_headroom(args, config, "post-score resource validation")

        loaded_evidence = {
            "snapshot_verification": dict(loaded_model.snapshot_verification),
            "model_validation": dict(loaded_model.model_validation),
            "model_loading_info": dict(loaded_model.loading_info),
            "tokenizer_validation": dict(loaded_model.tokenizer_validation),
            "runtime_identity": dict(loaded_model.runtime_identity),
            "determinism": dict(loaded_model.model_validation["determinism"]),
            "load_seconds": loaded_model.load_seconds,
        }

        _set_stage(args, "model-cleanup")
        delattr(args, "_provider")
        del provider, loaded_model, loaded_tokenizer
        gc.collect()
        torch.cuda.empty_cache()
        _require_wall_headroom(args, config, "model cleanup")

        _set_stage(args, "final-integrity-rebind")
        _final_integrity_rebind(
            args,
            profile=profile,
            artifact=artifact,
            snapshot_receipt=loaded_evidence["snapshot_verification"],
            git_binding=git_binding,
            input_payloads=input_payloads,
            tokenizer_audit_path=tokenizer_audit_path,
            tokenizer_audit_file_sha256=tokenizer_audit_file_sha256,
            tokenizer_audit=tokenizer_audit,
            config=config,
        )
        _require_wall_headroom(args, config, "final integrity rebind")

        prepublication_storage = _output_storage_observation(
            args, config, phase="prepublication"
        )
        _set_stage(args, "output-publication")
        score_bytes = pretty_json_bytes(score)
        score_file_sha256 = hashlib.sha256(score_bytes).hexdigest()
        observed_size, observed_sha = reservation.write_score(score)
        if observed_size != len(score_bytes) or observed_sha != score_file_sha256:
            raise ScoringRunError("published score bytes differ from the final binding")
        elapsed = _require_wall_headroom(args, config, "score publication")
        completed_at = datetime.now(timezone.utc).isoformat()
        output_storage = {
            "minimum_free_bytes": config["resource_limits"][
                "minimum_output_free_bytes"
            ],
            "preflight_passed": True,
            "prepublication_passed": True,
            "preflight": getattr(args, "_output_storage_preflight"),
            "prepublication": prepublication_storage,
            "wall_measurement_scope": "through-score-fsync-before-runtime-receipt",
            "final_wall_limit_seconds": config["resource_limits"][
                "maximum_invocation_wall_seconds"
            ],
            "final_wall_limit_passed": True,
        }
        receipt_body = {
                "schema_version": 1,
                "receipt_type": "registry-score-runtime",
                "status": "complete",
                "attempt": args.attempt,
                "run_id": identity["run_id"],
                "process_id": os.getpid(),
                "started_at": started_at,
                "completed_at": completed_at,
                "network_access_permitted": False,
                "network_observation": "not-instrumented",
                "scientific_claim_authorized": False,
                "git": git_binding,
                "run_spec": {
                    "sha256": config_sha256,
                    "git_blob": git_binding["scoring_config_git_blob"],
                },
                "canonical_inputs": {
                    "model_manifest_sha256": manifest_sha256,
                    "registry_sha256": registry_sha256,
                },
                "accepted_tokenizer": {
                    "file_sha256": tokenizer_audit_file_sha256,
                    "output_sha256": tokenizer_audit["output_sha256"],
                },
                "snapshot_verification": loaded_evidence["snapshot_verification"],
                "model_validation": loaded_evidence["model_validation"],
                "model_loading_info": loaded_evidence["model_loading_info"],
                "tokenizer_validation": loaded_evidence["tokenizer_validation"],
                "runtime_identity": loaded_evidence["runtime_identity"],
                "determinism": loaded_evidence["determinism"],
                "execution_controls": {
                    "HF_HUB_DISABLE_TELEMETRY": "1",
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                    "autocast": False,
                    "local_files_only": True,
                    "model_weights_deserialized": True,
                    "private_model_staging": True,
                    "private_tokenizer_staging": True,
                    "trust_remote_code": False,
                    "use_safetensors": True,
                    "weights_downloaded": False,
                },
                "resource_preflight": resource_state["preflight"],
                "output_storage": output_storage,
                "post_load_resource": post_load_resource,
                "post_score_resource": post_score_resource,
                "metrics": {
                    "load_seconds": loaded_evidence["load_seconds"],
                    "wall_seconds": elapsed,
                    "process_max_rss_bytes": model_benchmark._max_rss_bytes(),
                    "peak_allocated_bytes": peak_allocated,
                    "peak_reserved_bytes": peak_reserved,
                    **runtime_metrics,
                },
                "score": {
                    "size_bytes": len(score_bytes),
                    "file_sha256": score_file_sha256,
                    "output_sha256": score["output_sha256"],
                },
            }
        if execution_schedule is not None:
            receipt_body["execution_schedule"] = execution_schedule
        receipt = receipt_with_self_hash(receipt_body)
        receipt_errors = validate_complete_receipt(
            receipt,
            config,
            tokenizer_audit=tokenizer_audit,
            registry=registry,
        )
        if receipt_errors:
            raise ScoringRunError("; ".join(receipt_errors))
        reservation.write_runtime(receipt)
        final_elapsed = time.perf_counter() - wall_start
        if final_elapsed > config["resource_limits"][
            "maximum_invocation_wall_seconds"
        ]:
            reservation.rollback()
            raise ScoringRunError(
                "scoring invocation exceeded the wall limit during receipt publication"
            )
        completed_receipt = receipt
    _commit_output_pair_after_lock(
        reservation,
        wall_start=wall_start,
        maximum_wall_seconds=config["resource_limits"][
            "maximum_invocation_wall_seconds"
        ],
    )
    return completed_receipt


def _failure_receipt(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    context = dict(getattr(args, "_failure_context", {}))
    resource_state = getattr(args, "_resource_state", None)
    if isinstance(resource_state, dict):
        if isinstance(resource_state.get("preflight"), dict):
            context["resource_preflight"] = resource_state["preflight"]
        pending_resource = resource_state.get("pending_resident_resource_check")
        if isinstance(pending_resource, Mapping):
            context["failed_resident_resource_check"] = dict(pending_resource)
    provider = getattr(args, "_provider", None)
    metrics = getattr(provider, "runtime_metrics", None)
    if callable(metrics):
        try:
            context["scoring_metrics"] = metrics()
        except Exception as metric_error:
            context["scoring_metrics_error"] = str(metric_error)
    try:
        head = tokenizer_cli._git("rev-parse", "HEAD")
    except Exception:
        head = None
    return receipt_with_self_hash(
        {
            "schema_version": 1,
            "receipt_type": "registry-score-runtime",
            "status": "failed",
            "attempt": args.attempt,
            "run_id": getattr(args, "_run_id", None),
            "process_id": os.getpid(),
            "started_at": getattr(args, "_started_at", None),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "failure_stage": getattr(args, "_failure_stage", "cli-preflight"),
            "error_type": type(error).__name__,
            "error": str(error),
            "current_git_head": head,
            "network_access_permitted": False,
            "network_observation": "not-instrumented",
            "scientific_claim_authorized": False,
            "failure_context": context,
            "score": {
                "valid_score_published": False,
                "owned_reservation_started": isinstance(
                    getattr(args, "_output_reservation", None),
                    _OutputPairReservation,
                ),
            },
        }
    )


def _preserve_failure_receipt(
    args: argparse.Namespace,
    error: Exception,
) -> None:
    if args.runtime_output is None:
        return
    receipt = _failure_receipt(args, error)
    reservation = getattr(args, "_output_reservation", None)
    if isinstance(reservation, _OutputPairReservation) and reservation.active:
        try:
            reservation.publish_failure(receipt)
            return
        except Exception:
            if os.path.lexists(args.runtime_output):
                raise
    if os.path.lexists(args.runtime_output):
        return
    _require_output_location(
        args.runtime_output,
        cache_dir=args.cache_dir,
        snapshot_path=args.snapshot_path,
        label="failure runtime output",
    )
    create_only_json(args.runtime_output, receipt)


def _plan(args: argparse.Namespace) -> dict[str, Any]:
    profile = _selected_profile(args.config)
    _require_canonical_path(args.manifest, DEFAULT_MANIFEST, "model manifest")
    _require_canonical_path(
        args.registry, ROOT / profile.registry_path, "development registry"
    )
    config = load_scoring_config(args.config)
    if scoring_profile(config) != profile:
        raise ScoringRunError("scoring config/profile selection mismatch")
    manifest = tokenizer_cli._manifest_from_bytes(args.manifest.read_bytes())
    registry = tokenizer_cli._registry_from_bytes(args.registry.read_bytes())
    manifest_errors = validate_model_manifest(manifest)
    registry_errors = validate_evaluation_registry(registry)
    if manifest_errors:
        raise ScoringRunError("; ".join(manifest_errors))
    if registry_errors:
        raise ScoringRunError("; ".join(registry_errors))
    artifact = find_artifact(manifest, args.artifact)
    frozen_profile = {
        "profile_id": profile.profile_id,
        "run_name": config["run_name"],
        "artifact": config["artifact"],
        "prefix_policy": config["accepted_tokenizer_audit"]["prefix_policy"],
        "device": config["model"]["device"],
        "dtype": config["model"]["dtype"],
        "maximum_length": config["scoring"]["maximum_length"],
        "determinism": config["determinism"],
        "resource_limits": config["resource_limits"],
    }
    if profile is V1_SCORING_PROFILE:
        frozen_profile["measurement_reliability"] = config[
            "measurement_reliability"
        ]
    return {
        "schema_version": 1,
        "mode": "plan",
        "status": "planned",
        "network_access_permitted": False,
        "weights_downloaded": False,
        "scientific_claim_authorized": False,
        "requested_prefix_policy": args.prefix_policy,
        "requested_device": args.device,
        "requested_dtype": args.dtype,
        "requested_max_length": args.max_length,
        "frozen_profile": frozen_profile,
        "policy": operation_plan(artifact, "model-score"),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.allow_download:
            raise ScoringRunError(
                "direct downloads are disabled; use the verified acquisition workflow"
            )
        _preflight_output(args.output, "score/plan output")
        _preflight_output(args.runtime_output, "runtime output")
    except Exception as error:
        if args.execute:
            try:
                _preserve_failure_receipt(args, error)
            except Exception as receipt_error:
                print(
                    f"error: could not preserve failure receipt: {receipt_error}",
                    file=sys.stderr,
                )
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        if args.execute:
            _execute(args)
            return 0
        report = _plan(args)
        rendered = json.dumps(report, indent=2, sort_keys=True)
        print(rendered)
        if args.output is not None:
            create_only_json(args.output, report)
        return 0
    except KeyboardInterrupt as error:
        if args.execute:
            try:
                _preserve_failure_receipt(args, error)
            except Exception as receipt_error:
                print(
                    f"error: could not preserve interrupted receipt: {receipt_error}",
                    file=sys.stderr,
                )
        print("error: scoring interrupted", file=sys.stderr)
        return 130
    except SystemExit as error:
        if args.execute:
            try:
                _preserve_failure_receipt(args, error)
            except Exception as receipt_error:
                print(
                    f"error: could not preserve exited receipt: {receipt_error}",
                    file=sys.stderr,
                )
        print(f"error: scoring exited unexpectedly: {error}", file=sys.stderr)
        return int(error.code) if isinstance(error.code, int) and error.code else 1
    except Exception as error:
        if args.execute:
            try:
                _preserve_failure_receipt(args, error)
            except Exception as receipt_error:
                print(
                    f"error: could not preserve failure receipt: {receipt_error}",
                    file=sys.stderr,
                )
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
