#!/usr/bin/env python3
"""Run a guarded, unquantized model-loading and logits benchmark.

The default mode is a no-network plan. Execution is allowed only for artifacts
that the committed model manifest marks ``benchmark-ready``. Downloads require
an additional explicit flag. Custom remote code is never enabled by this
script.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import ctypes
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json"
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.model_manifest import (  # noqa: E402
    load_model_manifest,
    validate_model_manifest,
)


def _artifact(manifest: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    for artifact in manifest["artifacts"]:
        if artifact.get("id") == artifact_id:
            return artifact
    raise ValueError(f"unknown artifact id: {artifact_id}")


def _require_canonical_manifest(path: Path) -> None:
    if path.resolve(strict=False) != DEFAULT_MANIFEST.resolve(strict=False):
        raise ValueError(
            "benchmark execution requires the canonical committed model manifest"
        )


def _plan(artifact: dict[str, Any], allow_download: bool) -> dict[str, Any]:
    weight_bytes = artifact.get("weight_size_bytes")
    return {
        "schema_version": 1,
        "status": "planned",
        "mode": "plan",
        "network_access_permitted": allow_download,
        "weights_downloaded": False,
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": artifact["revision"],
        "checkpoint_ref": artifact.get("checkpoint_ref"),
        "execution_status": artifact["execution_status"],
        "weight_size_bytes": weight_bytes,
        "minimum_free_disk_bytes": (
            int(weight_bytes * 2.5) if isinstance(weight_bytes, int) else None
        ),
        "requires_remote_code": artifact["requires_remote_code"],
        "license_status": artifact["license"]["status"],
        "constraints": artifact.get("constraints", []),
    }


def _dtype(torch: Any, name: str) -> Any:
    if name == "auto":
        return "auto"
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[name]


def _max_rss_bytes() -> int | None:
    if platform.system() == "Windows":
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("page_fault_count", wintypes.DWORD),
                ("peak_working_set_size", ctypes.c_size_t),
                ("working_set_size", ctypes.c_size_t),
                ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                ("quota_paged_pool_usage", ctypes.c_size_t),
                ("quota_peak_nonpaged_pool_usage", ctypes.c_size_t),
                ("quota_nonpaged_pool_usage", ctypes.c_size_t),
                ("pagefile_usage", ctypes.c_size_t),
                ("peak_pagefile_usage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCounters),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            process = kernel32.GetCurrentProcess()
            success = psapi.GetProcessMemoryInfo(
                process,
                ctypes.byref(counters),
                counters.cb,
            )
        except (AttributeError, OSError):
            return None
        return int(counters.peak_working_set_size) if success else None

    try:
        import resource
    except ImportError:
        return None
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return int(usage)
    return int(usage * 1024)


def _current_git_state() -> tuple[str, bool]:
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if head.returncode != 0 or not head.stdout.strip():
        raise RuntimeError(
            "cannot resolve the current repository commit for preflight"
        )
    status = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        raise RuntimeError("cannot inspect worktree state for preflight")
    return head.stdout.strip(), bool(status.stdout.strip())


def _existing_directory(path: Path, label: str) -> Path:
    try:
        candidate = path.expanduser().resolve(strict=True)
    except OSError as error:
        raise RuntimeError(f"{label} does not exist: {path}") from error
    if not candidate.is_dir():
        raise ValueError(f"{label} must be an existing directory: {path}")
    return candidate


def _filesystem_device(path: Path) -> int:
    try:
        return int(os.stat(path).st_dev)
    except OSError as error:
        raise RuntimeError(
            f"cannot identify filesystem for path: {path}"
        ) from error


def _set_failure_stage(args: argparse.Namespace, stage: str) -> None:
    setattr(args, "_failure_stage", stage)


def _load_resource_audit(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid resource audit JSON: {error}") from error
    if not isinstance(raw, Mapping):
        raise ValueError("resource audit root must be an object")
    audit = dict(raw)
    if audit.get("schema_version") != 1:
        raise ValueError("resource audit schema_version must be 1")
    if audit.get("audit_type") != "local-resource-audit":
        raise ValueError("resource audit has the wrong audit_type")
    if audit.get("network_access_performed") is not False:
        raise ValueError("resource audit must be a no-network observation")
    return audit, hashlib.sha256(payload).hexdigest()


def _resource_preflight(
    args: argparse.Namespace,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    if args.resource_audit is None:
        raise RuntimeError("--resource-audit is required for execution")

    audit, audit_sha256 = _load_resource_audit(args.resource_audit)
    git_state = audit.get("git")
    if not isinstance(git_state, Mapping):
        raise ValueError("resource audit is missing Git state")
    disk_record = audit.get("disk")
    if not isinstance(disk_record, Mapping):
        raise ValueError("resource audit is missing disk state")
    setattr(
        args,
        "_resource_audit_binding",
        {
            "resource_audit": str(args.resource_audit.resolve(strict=False)),
            "resource_audit_sha256": audit_sha256,
            "resource_audit_captured_at": audit.get("captured_at"),
            "audit_git_head": git_state.get("head"),
            "audit_git_dirty": git_state.get("dirty"),
            "audit_disk_path": disk_record.get("path"),
            "audit_disk_free_bytes": disk_record.get("free_bytes"),
        },
    )
    if git_state.get("dirty") is not False:
        raise ValueError("resource audit must describe a clean worktree")
    current_head, current_dirty = _current_git_state()
    if current_dirty:
        raise ValueError("benchmark execution requires a clean worktree")
    if git_state.get("head") != current_head:
        raise ValueError(
            "resource audit Git commit does not match the current benchmark"
        )

    torch_runtime = audit.get("torch_runtime")
    if args.device == "cuda":
        if not isinstance(torch_runtime, Mapping):
            raise ValueError("resource audit is missing Torch runtime state")
        if torch_runtime.get("cuda_available") is not True:
            raise ValueError("resource audit does not show CUDA availability")
        if not torch_runtime.get("compiled_cuda_version"):
            raise ValueError("resource audit records a CPU-only Torch build")

    if args.cache_dir is None:
        raise RuntimeError("--cache-dir is required for benchmark execution")
    audited_path = disk_record.get("path")
    if not isinstance(audited_path, str) or not audited_path:
        raise ValueError("resource audit disk.path must be recorded")
    storage_path = _existing_directory(args.cache_dir, "model cache")
    audited_storage_path = _existing_directory(
        Path(audited_path),
        "audited storage path",
    )
    storage_device = _filesystem_device(storage_path)
    audited_device = _filesystem_device(audited_storage_path)
    if audited_device != storage_device:
        raise ValueError(
            "resource audit and model cache must be on the same filesystem"
        )
    live_free = shutil.disk_usage(storage_path).free

    preflight: dict[str, Any] = {
        "resource_audit": str(args.resource_audit.resolve(strict=False)),
        "resource_audit_sha256": audit_sha256,
        "resource_audit_captured_at": audit.get("captured_at"),
        "git_head": current_head,
        "audit_disk_free_bytes": disk_record.get("free_bytes"),
        "audit_disk_path": str(audited_storage_path),
        "cache_storage_path": str(storage_path),
        "filesystem_device": storage_device,
        "live_disk_free_bytes": live_free,
    }
    setattr(args, "_resource_preflight", preflight)
    if not args.allow_download:
        return preflight

    weight_size = artifact.get("weight_size_bytes")
    if not isinstance(weight_size, int) or isinstance(weight_size, bool):
        raise ValueError("artifact weight size is required for download preflight")
    minimum_free = int(weight_size * 2.5)
    audited_free = disk_record.get("free_bytes")
    if not isinstance(audited_free, int) or isinstance(audited_free, bool):
        raise ValueError("resource audit disk.free_bytes must be an integer")
    if audited_free < minimum_free:
        raise RuntimeError(
            "resource audit free disk is below the 2.5x model safety margin"
        )
    if live_free < minimum_free:
        raise RuntimeError(
            "live free disk is below the 2.5x model safety margin"
        )
    preflight.update(
        {
            "minimum_free_disk_bytes": minimum_free,
        }
    )
    setattr(args, "_resource_preflight", preflight)
    return preflight


def _failure_report(
    args: argparse.Namespace,
    error: Exception,
    artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    resource_context = getattr(args, "_resource_preflight", None)
    if resource_context is None:
        resource_context = getattr(args, "_resource_audit_binding", None)
    return {
        "schema_version": 1,
        "status": "failed",
        "mode": "execute" if args.execute else "plan",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "artifact_id": args.artifact,
        "repository": artifact.get("repository") if artifact else None,
        "revision": artifact.get("revision") if artifact else None,
        "device": args.device,
        "requested_dtype": args.dtype,
        "cache_dir": (
            str(args.cache_dir)
            if args.cache_dir is not None
            else None
        ),
        "resource_audit": (
            str(args.resource_audit)
            if args.resource_audit is not None
            else None
        ),
        "resource_preflight": resource_context,
        "failure_stage": getattr(args, "_failure_stage", "unknown"),
        "network_download_permitted": bool(args.allow_download),
        "download_completion_status": (
            "unknown" if args.allow_download else "not-permitted"
        ),
        "error_type": type(error).__name__,
        "error": str(error),
        "prompt_sha256": hashlib.sha256(
            args.prompt.encode("utf-8")
        ).hexdigest(),
    }


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _execute(args: argparse.Namespace, artifact: dict[str, Any]) -> dict[str, Any]:
    _set_failure_stage(args, "artifact-policy")
    if artifact["execution_status"] != "benchmark-ready":
        raise ValueError(
            f"artifact {artifact['id']} is {artifact['execution_status']}, "
            "not benchmark-ready"
        )
    if artifact["requires_remote_code"]:
        raise ValueError("custom remote code is not supported by this benchmark")
    if artifact["license"]["status"] != "verified":
        raise ValueError("model license must be verified before execution")
    if not artifact["immutable"]:
        raise ValueError("artifact revision must be immutable before execution")
    revision = artifact.get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("benchmark execution requires a pinned 40-character SHA")

    _set_failure_stage(args, "resource-preflight")
    resource_preflight = _resource_preflight(args, artifact)

    _set_failure_stage(args, "dependency-import")
    try:
        import torch
        import torch.nn.functional as functional
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "model benchmark dependencies are missing; install `.[models]`"
        ) from error

    _set_failure_stage(args, "runtime-check")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")

    device = torch.device(args.device)
    requested_dtype = _dtype(torch, args.dtype)
    local_files_only = not args.allow_download
    cache_dir = str(args.cache_dir) if args.cache_dir else None

    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)

    _set_failure_stage(args, "model-load")
    started = datetime.now(timezone.utc).isoformat()
    load_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        artifact["repository"],
        revision=revision,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        trust_remote_code=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        artifact["repository"],
        revision=revision,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        trust_remote_code=False,
        torch_dtype=requested_dtype,
        use_safetensors=True,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    model.eval()
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    load_seconds = time.perf_counter() - load_start

    _set_failure_stage(args, "prompt-tokenization")
    encoded = tokenizer(
        args.prompt,
        return_tensors="pt",
        add_special_tokens=True,
        truncation=True,
        max_length=args.max_tokens,
    )
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)
    if input_ids.shape[1] < 2:
        raise RuntimeError("benchmark prompt must tokenize to at least two tokens")

    _set_failure_stage(args, "forward-pass")
    durations: list[float] = []
    losses: list[float] = []
    with torch.inference_mode():
        for index in range(args.warmup + args.repeats):
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            forward_start = time.perf_counter()
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                use_cache=False,
            )
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            duration = time.perf_counter() - forward_start
            shift_logits = outputs.logits[:, :-1, :].float()
            shift_labels = input_ids[:, 1:]
            loss = functional.cross_entropy(
                shift_logits.reshape(-1, shift_logits.shape[-1]),
                shift_labels.reshape(-1),
            )
            if index >= args.warmup:
                durations.append(duration)
                losses.append(float(loss.item()))
            del outputs, shift_logits, shift_labels, loss

    input_tokens = int(input_ids.numel())
    predicted_tokens = input_tokens - 1
    mean_seconds = sum(durations) / len(durations)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    gpu_record: dict[str, Any] | None = None
    if device.type == "cuda":
        gpu_record = {
            "name": torch.cuda.get_device_name(device),
            "capability": list(torch.cuda.get_device_capability(device)),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(device),
            "total_memory_bytes": torch.cuda.get_device_properties(
                device
            ).total_memory,
        }

    _set_failure_stage(args, "report-finalization")
    report = {
        "schema_version": 1,
        "status": "complete",
        "mode": "execute",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": revision,
        "checkpoint_ref": artifact.get("checkpoint_ref"),
        "network_download_permitted": args.allow_download,
        "local_files_only": local_files_only,
        "device": str(device),
        "requested_dtype": args.dtype,
        "model_dtype": str(next(model.parameters()).dtype),
        "parameter_count": parameter_count,
        "load_seconds": load_seconds,
        "prompt_sha256": hashlib.sha256(
            args.prompt.encode("utf-8")
        ).hexdigest(),
        "input_tokens": input_tokens,
        "predicted_tokens": predicted_tokens,
        "warmup_repeats": args.warmup,
        "measured_repeats": args.repeats,
        "forward_seconds": durations,
        "mean_forward_seconds": mean_seconds,
        "tokens_per_second": predicted_tokens / mean_seconds,
        "mean_next_token_cross_entropy": sum(losses) / len(losses),
        "process_max_rss_bytes": _max_rss_bytes(),
        "gpu": gpu_record,
        "resource_preflight": resource_preflight,
        "software": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
        },
    }

    del model, tokenizer, input_ids, attention_mask
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or execute an unquantized model loading/logits benchmark "
            "using the committed model manifest."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="load the model; without this flag the command is a no-network plan",
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="permit Transformers to download missing files during execution",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default="cuda",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "float16", "bfloat16", "float32"),
        default="auto",
    )
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument(
        "--resource-audit",
        type=Path,
        help=(
            "no-network local resource audit bound to the exact Git commit; "
            "required for execution"
        ),
    )
    parser.add_argument(
        "--prompt",
        default=(
            "In the fictional city of Lume, inspectors compare two reports "
            "before approving a reversible infrastructure test."
        ),
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.max_tokens < 2 or args.warmup < 0 or args.repeats < 1:
        print("error: invalid token or repeat settings", file=sys.stderr)
        return 2
    if args.allow_download and not args.execute:
        print(
            "error: --allow-download is meaningful only with --execute",
            file=sys.stderr,
        )
        return 2

    artifact: dict[str, Any] | None = None
    try:
        _set_failure_stage(args, "manifest-source")
        if args.execute:
            _require_canonical_manifest(args.manifest)
        _set_failure_stage(args, "manifest-load")
        manifest = dict(load_model_manifest(args.manifest))
        _set_failure_stage(args, "manifest-validation")
        errors = validate_model_manifest(manifest)
        if errors:
            raise ValueError("; ".join(errors))
        _set_failure_stage(args, "artifact-selection")
        artifact = _artifact(manifest, args.artifact)
        report = (
            _execute(args, artifact)
            if args.execute
            else _plan(artifact, args.allow_download)
        )
    except Exception as error:
        if args.output is not None:
            try:
                _write_report(
                    args.output,
                    _failure_report(args, error, artifact),
                )
            except OSError as output_error:
                print(
                    f"error: could not preserve failure report: {output_error}",
                    file=sys.stderr,
                )
        print(f"error: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        _write_report(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
