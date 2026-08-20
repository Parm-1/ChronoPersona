#!/usr/bin/env python3
"""Run a guarded, unquantized model-loading and logits benchmark.

The default mode is a no-network plan. Acquisition and execution are separate,
and both are allowed only for artifacts that the committed model manifest marks
``benchmark-ready``. Custom remote code is never enabled by this script.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import ctypes
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
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
MAX_RESOURCE_AUDIT_AGE_SECONDS = 15 * 60
MIN_AVAILABLE_RAM_MULTIPLIER = 2
MIN_FREE_VRAM_NUMERATOR = 3
MIN_FREE_VRAM_DENOMINATOR = 2
RUNTIME_PACKAGES = (
    "torch",
    "transformers",
    "huggingface-hub",
    "safetensors",
    "accelerate",
)
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
            "model acquisition or execution requires the canonical committed "
            "model manifest"
        )


def _required_files(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_files = artifact.get("required_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("artifact has no exact required_files manifest")
    required: list[dict[str, Any]] = []
    for index, raw_file in enumerate(raw_files):
        if not isinstance(raw_file, Mapping):
            raise ValueError(f"required_files[{index}] must be an object")
        required.append(dict(raw_file))
    return required


def _required_download_bytes(artifact: Mapping[str, Any]) -> int | None:
    raw_files = artifact.get("required_files")
    if isinstance(raw_files, list) and raw_files:
        sizes = [
            raw_file.get("size_bytes")
            for raw_file in raw_files
            if isinstance(raw_file, Mapping)
        ]
        if len(sizes) == len(raw_files) and all(
            isinstance(size, int) and not isinstance(size, bool)
            for size in sizes
        ):
            return sum(sizes)
    weight_bytes = artifact.get("weight_size_bytes")
    return (
        weight_bytes
        if isinstance(weight_bytes, int) and not isinstance(weight_bytes, bool)
        else None
    )


def _minimum_free_disk_bytes(required_bytes: int) -> int:
    return (required_bytes * 5 + 1) // 2


def _verify_required_files(
    snapshot_path: Path,
    artifact: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_names = {
        item["filename"] for item in _required_files(artifact)
    }
    observed_names = {
        path.relative_to(snapshot_path).as_posix()
        for path in snapshot_path.rglob("*")
        if path.is_file()
    }
    unexpected_names = sorted(observed_names - expected_names)
    if unexpected_names:
        raise RuntimeError(
            "model snapshot contains files outside the exact allowlist: "
            + ", ".join(unexpected_names)
        )

    verified: list[dict[str, Any]] = []
    for expected in _required_files(artifact):
        filename = expected["filename"]
        expected_size = expected["size_bytes"]
        expected_sha256 = expected["sha256"]
        path = snapshot_path.joinpath(*filename.split("/"))
        if not path.is_file():
            raise RuntimeError(f"required model file is missing: {filename}")
        observed_size = path.stat().st_size
        if observed_size != expected_size:
            raise RuntimeError(
                f"required model file size mismatch for {filename}: "
                f"expected {expected_size}, observed {observed_size}"
            )
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(block)
        observed_sha256 = digest.hexdigest()
        if observed_sha256 != expected_sha256:
            raise RuntimeError(
                f"required model file SHA-256 mismatch for {filename}: "
                f"expected {expected_sha256}, observed {observed_sha256}"
            )
        verified.append(
            {
                "filename": filename,
                "size_bytes": observed_size,
                "sha256": observed_sha256,
                "verified": True,
            }
        )
    return verified


def _verify_model_config(
    snapshot_path: Path,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    config_path = snapshot_path / "config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot verify model config: {error}") from error
    if not isinstance(raw, Mapping):
        raise RuntimeError("model config root must be an object")

    expected_model_type = artifact.get("model_type")
    if raw.get("model_type") != expected_model_type:
        raise RuntimeError(
            "model config type mismatch: "
            f"expected {expected_model_type!r}, observed {raw.get('model_type')!r}"
        )
    expected_architecture = artifact.get("architecture")
    architectures = raw.get("architectures")
    if architectures != [expected_architecture]:
        raise RuntimeError(
            "model config architecture mismatch: "
            f"expected {expected_architecture!r}, observed {architectures!r}"
        )
    if raw.get("torch_dtype") != "float16":
        raise RuntimeError(
            "model config dtype mismatch: expected 'float16', "
            f"observed {raw.get('torch_dtype')!r}"
        )
    if raw.get("auto_map") not in (None, {}):
        raise RuntimeError("model config declares disallowed custom auto_map code")
    return {
        "model_type": raw["model_type"],
        "architectures": architectures,
        "torch_dtype": raw["torch_dtype"],
        "auto_map": raw.get("auto_map"),
        "verified": True,
    }


def _verify_snapshot_identity(
    snapshot_path: Path,
    cache_dir: Path,
    revision: str,
) -> None:
    resolved_snapshot = snapshot_path.resolve(strict=True)
    resolved_cache = cache_dir.resolve(strict=True)
    if not resolved_snapshot.is_relative_to(resolved_cache):
        raise RuntimeError(
            "downloaded snapshot path is outside the selected model cache"
        )
    if resolved_snapshot.name != revision:
        raise RuntimeError(
            "downloaded snapshot path is not bound to the requested revision: "
            f"expected leaf {revision}, observed {resolved_snapshot.name}"
        )


def _plan(artifact: dict[str, Any], allow_download: bool) -> dict[str, Any]:
    weight_bytes = artifact.get("weight_size_bytes")
    required_bytes = _required_download_bytes(artifact)
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
        "required_download_bytes": required_bytes,
        "required_files": artifact.get("required_files"),
        "minimum_free_disk_bytes": (
            _minimum_free_disk_bytes(required_bytes)
            if required_bytes is not None
            else None
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


def _resource_audit_age_seconds(audit: Mapping[str, Any]) -> float:
    captured_at = audit.get("captured_at")
    if not isinstance(captured_at, str):
        raise ValueError("resource audit captured_at must be recorded")
    try:
        captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("resource audit captured_at is not valid ISO-8601") from error
    if captured.tzinfo is None:
        raise ValueError("resource audit captured_at must include a timezone")
    age = (
        datetime.now(timezone.utc) - captured.astimezone(timezone.utc)
    ).total_seconds()
    if age < -60:
        raise ValueError("resource audit timestamp is unreasonably in the future")
    if age > MAX_RESOURCE_AUDIT_AGE_SECONDS:
        raise ValueError(
            "resource audit is stale; capture a new audit immediately before use"
        )
    return max(age, 0.0)


def _capture_live_resource_audit(storage_path: Path) -> tuple[dict[str, Any], str]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "audit_local_resources.py"),
        "--path",
        str(storage_path),
        "--repo",
        str(ROOT),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"live resource audit failed: {error}") from error
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"live resource audit failed: {stderr}")
    try:
        raw = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("live resource audit returned invalid JSON") from error
    if not isinstance(raw, Mapping):
        raise RuntimeError("live resource audit root must be an object")
    audit = dict(raw)
    if audit.get("schema_version") != 1:
        raise RuntimeError("live resource audit has the wrong schema version")
    if audit.get("audit_type") != "local-resource-audit":
        raise RuntimeError("live resource audit has the wrong audit type")
    if audit.get("network_access_performed") is not False:
        raise RuntimeError("live resource audit must be a no-network observation")
    return audit, hashlib.sha256(completed.stdout).hexdigest()


def _indexed_record(raw: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(raw, list):
        raise ValueError(f"{label} must be a list")
    for record in raw:
        if isinstance(record, Mapping) and record.get("index") == 0:
            return record
    raise ValueError(f"{label} does not contain CUDA device 0")


def _conservative_vram(audit: Mapping[str, Any]) -> dict[str, int]:
    torch_runtime = audit.get("torch_runtime")
    if not isinstance(torch_runtime, Mapping):
        raise ValueError("resource audit is missing Torch runtime state")
    torch_device = _indexed_record(
        torch_runtime.get("devices"),
        label="resource audit Torch devices",
    )
    torch_free = torch_device.get("free_memory_bytes")
    if not isinstance(torch_free, int) or isinstance(torch_free, bool):
        raise ValueError("resource audit Torch free VRAM must be an integer")

    nvidia = audit.get("nvidia")
    if not isinstance(nvidia, Mapping):
        raise ValueError("resource audit is missing nvidia-smi state")
    nvidia_device = _indexed_record(
        nvidia.get("gpus"),
        label="resource audit nvidia-smi devices",
    )
    nvidia_free_mib = nvidia_device.get("memory_free_mib")
    if not isinstance(nvidia_free_mib, int) or isinstance(
        nvidia_free_mib,
        bool,
    ):
        raise ValueError("resource audit nvidia-smi free VRAM must be an integer")
    nvidia_free = nvidia_free_mib * 1024 * 1024
    return {
        "torch_free_bytes": torch_free,
        "nvidia_smi_free_bytes": nvidia_free,
        "conservative_free_bytes": min(torch_free, nvidia_free),
    }


def _same_executable(left: Any, right: Any) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return os.path.normcase(str(Path(left).resolve(strict=False))) == os.path.normcase(
        str(Path(right).resolve(strict=False))
    )


def _validate_execution_resources(
    audited: Mapping[str, Any],
    live: Mapping[str, Any],
    artifact: Mapping[str, Any],
    *,
    require_cuda: bool = True,
) -> dict[str, Any]:
    audited_git = audited.get("git")
    live_git = live.get("git")
    if not isinstance(audited_git, Mapping) or not isinstance(
        live_git,
        Mapping,
    ):
        raise ValueError("resource audits must record Git state")
    if live_git.get("dirty") is not False:
        raise ValueError("live resource audit must describe a clean worktree")
    if audited_git.get("head") != live_git.get("head"):
        raise ValueError("live Git head does not match the supplied audit")

    audited_platform = audited.get("platform")
    live_platform = live.get("platform")
    if not isinstance(audited_platform, Mapping) or not isinstance(
        live_platform,
        Mapping,
    ):
        raise ValueError("resource audits must record platform identity")
    for key in ("system", "machine", "hostname"):
        if audited_platform.get(key) != live_platform.get(key):
            raise ValueError(f"live platform {key} does not match the audit")

    audited_environment = audited.get("environment")
    live_environment = live.get("environment")
    if not isinstance(audited_environment, Mapping) or not isinstance(
        live_environment,
        Mapping,
    ):
        raise ValueError("resource audits must record runtime environment")
    if audited_environment.get("CUDA_VISIBLE_DEVICES") != live_environment.get(
        "CUDA_VISIBLE_DEVICES"
    ):
        raise ValueError("live CUDA_VISIBLE_DEVICES does not match the audit")

    audited_python = audited.get("python")
    live_python = live.get("python")
    if not isinstance(audited_python, Mapping) or not isinstance(
        live_python,
        Mapping,
    ):
        raise ValueError("resource audits must record Python identity")
    for key in ("version", "implementation"):
        if audited_python.get(key) != live_python.get(key):
            raise ValueError(f"live Python {key} does not match the resource audit")
    if not _same_executable(
        audited_python.get("executable"),
        live_python.get("executable"),
    ):
        raise ValueError("live Python executable does not match the resource audit")

    audited_packages = audited.get("packages")
    live_packages = live.get("packages")
    if not isinstance(audited_packages, Mapping) or not isinstance(
        live_packages,
        Mapping,
    ):
        raise ValueError("resource audits must record package versions")
    package_identity: dict[str, str] = {}
    for package in RUNTIME_PACKAGES:
        audited_version = audited_packages.get(package)
        live_version = live_packages.get(package)
        if not isinstance(audited_version, str) or not audited_version:
            raise ValueError(f"resource audit is missing package {package}")
        if audited_version != live_version:
            raise ValueError(
                f"live package {package} does not match the resource audit"
            )
        package_identity[package] = audited_version

    audited_torch = audited.get("torch_runtime")
    live_torch = live.get("torch_runtime")
    if not isinstance(audited_torch, Mapping) or not isinstance(
        live_torch,
        Mapping,
    ):
        raise ValueError("resource audits must record Torch runtime state")
    for key in (
        "available",
        "version",
        "compiled_cuda_version",
        "cuda_available",
        "device_count",
    ):
        if audited_torch.get(key) != live_torch.get(key):
            raise ValueError(f"live Torch {key} does not match the resource audit")
    if live_torch.get("available") is not True:
        raise ValueError("live resource audit does not show an available Torch build")
    live_torch_device: Mapping[str, Any] | None = None
    live_nvidia_device: Mapping[str, Any] | None = None
    if require_cuda:
        if live_torch.get("cuda_available") is not True:
            raise ValueError("live resource audit does not show CUDA availability")

        audited_torch_device = _indexed_record(
            audited_torch.get("devices"),
            label="audited Torch devices",
        )
        live_torch_device = _indexed_record(
            live_torch.get("devices"),
            label="live Torch devices",
        )
        for key in ("name", "capability", "total_memory_bytes"):
            if audited_torch_device.get(key) != live_torch_device.get(key):
                raise ValueError(
                    f"live CUDA device {key} does not match the audit"
                )

        audited_nvidia = audited.get("nvidia")
        live_nvidia = live.get("nvidia")
        if not isinstance(audited_nvidia, Mapping) or not isinstance(
            live_nvidia,
            Mapping,
        ):
            raise ValueError("resource audits must record nvidia-smi state")
        audited_nvidia_device = _indexed_record(
            audited_nvidia.get("gpus"),
            label="audited nvidia-smi devices",
        )
        live_nvidia_device = _indexed_record(
            live_nvidia.get("gpus"),
            label="live nvidia-smi devices",
        )
        for key in ("name", "uuid", "memory_total_mib", "driver_version"):
            if audited_nvidia_device.get(key) != live_nvidia_device.get(key):
                raise ValueError(f"live nvidia-smi {key} does not match the audit")

    weight_bytes = artifact.get("weight_size_bytes")
    if not isinstance(weight_bytes, int) or isinstance(weight_bytes, bool):
        raise ValueError("artifact weight size is required for resource checks")
    ram_multiplier = MIN_AVAILABLE_RAM_MULTIPLIER if require_cuda else 3
    minimum_ram = weight_bytes * ram_multiplier
    minimum_vram = (
        weight_bytes * MIN_FREE_VRAM_NUMERATOR
        + MIN_FREE_VRAM_DENOMINATOR
        - 1
    ) // MIN_FREE_VRAM_DENOMINATOR

    audited_memory = audited.get("memory")
    live_memory = live.get("memory")
    if not isinstance(audited_memory, Mapping) or not isinstance(
        live_memory,
        Mapping,
    ):
        raise ValueError("resource audits must record physical memory")
    audited_ram = audited_memory.get("available_bytes")
    live_ram = live_memory.get("available_bytes")
    if not isinstance(audited_ram, int) or isinstance(audited_ram, bool):
        raise ValueError("audited available RAM must be an integer")
    if not isinstance(live_ram, int) or isinstance(live_ram, bool):
        raise ValueError("live available RAM must be an integer")
    if min(audited_ram, live_ram) < minimum_ram:
        raise RuntimeError("available RAM is below the model-load safety threshold")

    audited_vram: dict[str, int] | None = None
    live_vram: dict[str, int] | None = None
    if require_cuda:
        audited_vram = _conservative_vram(audited)
        live_vram = _conservative_vram(live)
        if min(
            audited_vram["conservative_free_bytes"],
            live_vram["conservative_free_bytes"],
        ) < minimum_vram:
            raise RuntimeError("free VRAM is below the model-load safety threshold")

    return {
        "packages": package_identity,
        "python": dict(live_python),
        "torch_runtime": {
            "version": live_torch.get("version"),
            "compiled_cuda_version": live_torch.get("compiled_cuda_version"),
            "device": (
                dict(live_torch_device)
                if live_torch_device is not None
                else None
            ),
        },
        "nvidia_smi_device": (
            dict(live_nvidia_device)
            if live_nvidia_device is not None
            else None
        ),
        "audited_available_ram_bytes": audited_ram,
        "live_available_ram_bytes": live_ram,
        "minimum_available_ram_bytes": minimum_ram,
        "audited_vram": audited_vram,
        "live_vram": live_vram,
        "minimum_free_vram_bytes": minimum_vram if require_cuda else None,
    }


def _live_execution_preflight(
    args: argparse.Namespace,
    artifact: Mapping[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    storage_path = Path(preflight["cache_storage_path"])
    live_audit, live_sha256 = _capture_live_resource_audit(storage_path)
    live_age_seconds = _resource_audit_age_seconds(live_audit)
    live_context = {
        "live_resource_audit_sha256": live_sha256,
        "live_resource_audit_captured_at": live_audit.get("captured_at"),
        "live_resource_audit_age_seconds": live_age_seconds,
        "live_resource_audit": live_audit,
    }
    preflight.update(live_context)
    setattr(args, "_resource_preflight", preflight)

    supplied_audit = getattr(args, "_supplied_resource_audit", None)
    if not isinstance(supplied_audit, Mapping):
        raise RuntimeError("supplied resource audit binding was not preserved")
    validation = _validate_execution_resources(
        supplied_audit,
        live_audit,
        artifact,
        require_cuda=args.device == "cuda",
    )
    preflight["execution_resource_validation"] = validation
    setattr(args, "_resource_preflight", preflight)
    return preflight


def _verify_parent_runtime(
    torch: Any,
    transformers: Any,
    preflight: Mapping[str, Any],
    *,
    device: str,
) -> dict[str, Any]:
    live_audit = preflight.get("live_resource_audit")
    if not isinstance(live_audit, Mapping):
        raise RuntimeError("live resource audit is missing before parent import")
    live_packages = live_audit.get("packages")
    live_torch = live_audit.get("torch_runtime")
    if not isinstance(live_packages, Mapping) or not isinstance(
        live_torch,
        Mapping,
    ):
        raise ValueError("live resource audit lacks package/runtime identity")

    observed_torch = str(torch.__version__)
    observed_transformers = str(transformers.__version__)
    observed_compiled_cuda = getattr(torch.version, "cuda", None)
    if observed_torch != live_torch.get("version"):
        raise ValueError("parent Torch version does not match the live audit")
    if observed_transformers != live_packages.get("transformers"):
        raise ValueError(
            "parent Transformers version does not match the live audit"
        )
    if observed_compiled_cuda != live_torch.get("compiled_cuda_version"):
        raise ValueError("parent compiled CUDA version does not match the live audit")
    if bool(torch.cuda.is_available()) != live_torch.get("cuda_available"):
        raise ValueError("parent CUDA availability does not match the live audit")

    parent_device: dict[str, Any] | None = None
    if device == "cuda":
        if int(torch.cuda.device_count()) != live_torch.get("device_count"):
            raise ValueError("parent CUDA device count does not match the live audit")
        if int(torch.cuda.device_count()) != 1:
            raise ValueError(
                "CUDA benchmark requires exactly one visible GPU so device 0 "
                "identity is unambiguous"
            )
        live_device = _indexed_record(
            live_torch.get("devices"),
            label="live Torch devices",
        )
        properties = torch.cuda.get_device_properties(0)
        parent_device = {
            "index": 0,
            "name": torch.cuda.get_device_name(0),
            "capability": list(torch.cuda.get_device_capability(0)),
            "total_memory_bytes": int(properties.total_memory),
        }
        for key in ("name", "capability", "total_memory_bytes"):
            if parent_device[key] != live_device.get(key):
                raise ValueError(
                    f"parent CUDA device {key} does not match the live audit"
                )
    return {
        "python": platform.python_version(),
        "torch": observed_torch,
        "transformers": observed_transformers,
        "compiled_cuda_version": observed_compiled_cuda,
        "cuda_available": bool(torch.cuda.is_available()),
        "device": parent_device,
        "verified": True,
    }


def _post_import_resource_preflight(
    args: argparse.Namespace,
    artifact: Mapping[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    storage_path = Path(preflight["cache_storage_path"])
    post_audit, post_sha256 = _capture_live_resource_audit(storage_path)
    post_age_seconds = _resource_audit_age_seconds(post_audit)
    preflight.update(
        {
            "post_import_resource_audit_sha256": post_sha256,
            "post_import_resource_audit_captured_at": post_audit.get(
                "captured_at"
            ),
            "post_import_resource_audit_age_seconds": post_age_seconds,
            "post_import_resource_audit": post_audit,
        }
    )
    setattr(args, "_resource_preflight", preflight)

    supplied_audit = getattr(args, "_supplied_resource_audit", None)
    if not isinstance(supplied_audit, Mapping):
        raise RuntimeError("supplied resource audit binding was not preserved")
    validation = _validate_execution_resources(
        supplied_audit,
        post_audit,
        artifact,
        require_cuda=args.device == "cuda",
    )
    preflight["post_import_resource_validation"] = validation
    setattr(args, "_resource_preflight", preflight)
    return preflight


def _resource_preflight(
    args: argparse.Namespace,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    if args.resource_audit is None:
        raise RuntimeError(
            "--resource-audit is required for model acquisition or execution"
        )

    audit, audit_sha256 = _load_resource_audit(args.resource_audit)
    audit_age_seconds = _resource_audit_age_seconds(audit)
    setattr(args, "_supplied_resource_audit", audit)
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
            "resource_audit_age_seconds": audit_age_seconds,
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
        raise ValueError("model acquisition or execution requires a clean worktree")
    if git_state.get("head") != current_head:
        raise ValueError(
            "resource audit Git commit does not match the current benchmark"
        )

    torch_runtime = audit.get("torch_runtime")
    if bool(getattr(args, "execute", False)) and args.device == "cuda":
        if not isinstance(torch_runtime, Mapping):
            raise ValueError("resource audit is missing Torch runtime state")
        if torch_runtime.get("cuda_available") is not True:
            raise ValueError("resource audit does not show CUDA availability")
        if not torch_runtime.get("compiled_cuda_version"):
            raise ValueError("resource audit records a CPU-only Torch build")

    if args.cache_dir is None:
        raise RuntimeError(
            "--cache-dir is required for model acquisition or execution"
        )
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
        "resource_audit_age_seconds": audit_age_seconds,
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

    required_bytes = _required_download_bytes(artifact)
    if required_bytes is None:
        raise ValueError(
            "artifact required download size is missing from preflight"
        )
    minimum_free = _minimum_free_disk_bytes(required_bytes)
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
            "required_download_bytes": required_bytes,
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
        "mode": (
            "execute"
            if args.execute
            else "acquire"
            if args.acquire_only
            else "plan"
        ),
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
        "artifact_integrity": getattr(args, "_artifact_integrity", None),
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
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True) + "\n")


def _validate_artifact_policy(artifact: Mapping[str, Any]) -> str:
    if artifact["execution_status"] != "benchmark-ready":
        raise ValueError(
            f"artifact {artifact['id']} is {artifact['execution_status']}, "
            "not benchmark-ready"
        )
    if artifact["requires_remote_code"]:
        raise ValueError("custom remote code is not supported by this benchmark")
    if artifact["license"]["status"] != "verified":
        raise ValueError(
            "model license must be verified before acquisition or execution"
        )
    if not artifact["immutable"]:
        raise ValueError(
            "artifact revision must be immutable before acquisition or execution"
        )
    revision = artifact.get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError(
            "model acquisition or execution requires a pinned 40-character SHA"
        )
    _required_files(artifact)
    return revision


def _acquire_snapshot(
    args: argparse.Namespace,
    artifact: Mapping[str, Any],
    revision: str,
    snapshot_download: Any,
) -> tuple[Path, float, dict[str, Any]]:
    _set_failure_stage(args, "artifact-acquisition")
    acquisition_start = time.perf_counter()
    required_files = _required_files(artifact)
    snapshot_path = Path(
        snapshot_download(
            repo_id=artifact["repository"],
            revision=revision,
            cache_dir=str(args.cache_dir),
            allow_patterns=[item["filename"] for item in required_files],
            local_files_only=not args.allow_download,
            max_workers=1,
        )
    )
    acquisition_seconds = time.perf_counter() - acquisition_start

    _set_failure_stage(args, "artifact-integrity")
    _verify_snapshot_identity(snapshot_path, args.cache_dir, revision)
    verified_files = _verify_required_files(snapshot_path, artifact)
    verified_config = _verify_model_config(snapshot_path, artifact)
    artifact_integrity = {
        "status": "verified",
        "snapshot_path": str(snapshot_path.resolve(strict=True)),
        "resolved_revision": revision,
        "required_download_bytes": _required_download_bytes(artifact),
        "files": verified_files,
        "config": verified_config,
    }
    setattr(args, "_artifact_integrity", artifact_integrity)
    return snapshot_path, acquisition_seconds, artifact_integrity


def _acquire(args: argparse.Namespace, artifact: dict[str, Any]) -> dict[str, Any]:
    _set_failure_stage(args, "artifact-policy")
    revision = _validate_artifact_policy(artifact)

    _set_failure_stage(args, "resource-preflight")
    resource_preflight = _resource_preflight(args, artifact)

    _set_failure_stage(args, "dependency-import")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as error:
        raise RuntimeError(
            "model benchmark dependencies are missing; install `.[models]`"
        ) from error

    started = datetime.now(timezone.utc).isoformat()
    _, acquisition_seconds, artifact_integrity = _acquire_snapshot(
        args,
        artifact,
        revision,
        snapshot_download,
    )
    return {
        "schema_version": 1,
        "status": "complete",
        "mode": "acquire",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": revision,
        "network_download_permitted": args.allow_download,
        "download_completion_status": (
            "complete-and-verified"
            if args.allow_download
            else "preexisting-cache-verified"
        ),
        "artifact_acquisition_seconds": acquisition_seconds,
        "artifact_integrity": artifact_integrity,
        "resource_preflight": resource_preflight,
    }


def _verify_loaded_model(
    model: Any,
    artifact: Mapping[str, Any],
    requested_dtype: Any,
) -> dict[str, Any]:
    observed_architecture = type(model).__name__
    expected_architecture = artifact.get("architecture")
    if observed_architecture != expected_architecture:
        raise RuntimeError(
            "loaded model architecture mismatch: "
            f"expected {expected_architecture}, observed {observed_architecture}"
        )
    observed_model_type = getattr(model.config, "model_type", None)
    expected_model_type = artifact.get("model_type")
    if observed_model_type != expected_model_type:
        raise RuntimeError(
            "loaded model type mismatch: "
            f"expected {expected_model_type}, observed {observed_model_type}"
        )

    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    expected_parameter_count = artifact.get("parameter_count")
    if parameter_count != expected_parameter_count:
        raise RuntimeError(
            "loaded parameter count mismatch: "
            f"expected {expected_parameter_count}, observed {parameter_count}"
        )
    parameter_dtypes = sorted(
        {str(parameter.dtype) for parameter in model.parameters()}
    )
    expected_dtype = str(requested_dtype)
    if parameter_dtypes != [expected_dtype]:
        raise RuntimeError(
            "loaded parameter dtype mismatch: "
            f"expected only {expected_dtype}, observed {parameter_dtypes}"
        )
    return {
        "architecture": observed_architecture,
        "model_type": observed_model_type,
        "parameter_count": parameter_count,
        "parameter_dtypes": parameter_dtypes,
        "verified": True,
    }


def _verify_logits(
    torch: Any,
    logits: Any,
    input_ids: Any,
    vocab_size: int,
) -> dict[str, Any]:
    observed_shape = tuple(int(size) for size in logits.shape)
    expected_prefix = tuple(int(size) for size in input_ids.shape)
    if len(observed_shape) != 3:
        raise RuntimeError(f"model logits must be rank 3, observed {observed_shape}")
    if observed_shape[:2] != expected_prefix:
        raise RuntimeError(
            "model logits batch/sequence shape mismatch: "
            f"expected {expected_prefix}, observed {observed_shape[:2]}"
        )
    if observed_shape[2] != vocab_size:
        raise RuntimeError(
            "model logits vocabulary shape mismatch: "
            f"expected {vocab_size}, observed {observed_shape[2]}"
        )
    if not bool(torch.isfinite(logits).all().item()):
        raise RuntimeError("model logits contain non-finite values")
    return {
        "shape": list(observed_shape),
        "finite": True,
        "verified": True,
    }


def _validate_tokenized_prompt(input_ids: Any, max_tokens: int) -> int:
    shape = tuple(int(size) for size in input_ids.shape)
    if len(shape) != 2 or shape[0] != 1:
        raise RuntimeError(
            f"benchmark tokenizer must return shape [1, tokens], observed {shape}"
        )
    token_count = shape[1]
    if token_count < 2:
        raise RuntimeError("benchmark prompt must tokenize to at least two tokens")
    if token_count > max_tokens:
        raise RuntimeError(
            "benchmark prompt exceeds --max-tokens; truncation is forbidden: "
            f"limit {max_tokens}, observed {token_count}"
        )
    return token_count


def _execute(args: argparse.Namespace, artifact: dict[str, Any]) -> dict[str, Any]:
    _set_failure_stage(args, "artifact-policy")
    revision = _validate_artifact_policy(artifact)

    _set_failure_stage(args, "execution-options")
    if args.dtype == "auto":
        raise ValueError("benchmark execution requires an explicit --dtype")
    if args.device == "cuda" and args.dtype != "float16":
        raise ValueError("CUDA benchmark execution requires --dtype float16")
    if args.device == "cpu" and args.dtype != "float32":
        raise ValueError("CPU benchmark execution requires --dtype float32")

    _set_failure_stage(args, "resource-preflight")
    resource_preflight = _resource_preflight(args, artifact)

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    _set_failure_stage(args, "acquisition-dependency-import")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as error:
        raise RuntimeError(
            "model benchmark dependencies are missing; install `.[models]`"
        ) from error

    started = datetime.now(timezone.utc).isoformat()
    snapshot_path, acquisition_seconds, artifact_integrity = _acquire_snapshot(
        args,
        artifact,
        revision,
        snapshot_download,
    )

    _set_failure_stage(args, "live-resource-preflight")
    resource_preflight = _live_execution_preflight(
        args,
        artifact,
        resource_preflight,
    )

    _set_failure_stage(args, "model-dependency-import")
    try:
        import torch
        import torch.nn.functional as functional
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "model benchmark dependencies are missing; install `.[models]`"
        ) from error

    _set_failure_stage(args, "runtime-check")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")

    parent_runtime_validation = _verify_parent_runtime(
        torch,
        transformers,
        resource_preflight,
        device=args.device,
    )

    _set_failure_stage(args, "post-import-resource-preflight")
    resource_preflight = _post_import_resource_preflight(
        args,
        artifact,
        resource_preflight,
    )

    device = torch.device(args.device)
    requested_dtype = _dtype(torch, args.dtype)

    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)

    _set_failure_stage(args, "model-load")
    load_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        snapshot_path,
        local_files_only=True,
        trust_remote_code=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        snapshot_path,
        local_files_only=True,
        trust_remote_code=False,
        torch_dtype=requested_dtype,
        use_safetensors=True,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    model.eval()
    loaded_model_validation = _verify_loaded_model(
        model,
        artifact,
        requested_dtype,
    )
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    load_seconds = time.perf_counter() - load_start

    _set_failure_stage(args, "prompt-tokenization")
    encoded = tokenizer(
        args.prompt,
        return_tensors="pt",
        add_special_tokens=True,
        truncation=False,
    )
    _validate_tokenized_prompt(encoded["input_ids"], args.max_tokens)
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)

    _set_failure_stage(args, "forward-pass")
    durations: list[float] = []
    losses: list[float] = []
    logits_validation: dict[str, Any] | None = None
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
            logits_validation = _verify_logits(
                torch,
                outputs.logits,
                input_ids,
                int(model.config.vocab_size),
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
            observed_loss = float(loss.item())
            if not math.isfinite(observed_loss):
                raise RuntimeError("model cross-entropy is non-finite")
            if index >= args.warmup:
                durations.append(duration)
                losses.append(observed_loss)
            del outputs, shift_logits, shift_labels, loss

    input_tokens = int(input_ids.numel())
    predicted_tokens = input_tokens - 1
    mean_seconds = sum(durations) / len(durations)
    parameter_count = loaded_model_validation["parameter_count"]
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
        "download_completion_status": (
            "complete-and-verified"
            if args.allow_download
            else "preexisting-cache-verified"
        ),
        "local_model_load_only": True,
        "artifact_acquisition_seconds": acquisition_seconds,
        "artifact_integrity": artifact_integrity,
        "device": str(device),
        "requested_dtype": args.dtype,
        "model_dtype": str(next(model.parameters()).dtype),
        "parameter_count": parameter_count,
        "loaded_model_validation": loaded_model_validation,
        "parent_runtime_validation": parent_runtime_validation,
        "logits_validation": logits_validation,
        "load_seconds": load_seconds,
        "prompt_sha256": hashlib.sha256(
            args.prompt.encode("utf-8")
        ).hexdigest(),
        "input_tokens": input_tokens,
        "predicted_tokens": predicted_tokens,
        "max_tokens_ceiling": args.max_tokens,
        "prompt_truncated": False,
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
            "transformers": transformers.__version__,
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
        "--acquire-only",
        action="store_true",
        help=(
            "acquire/verify only the manifest-allowlisted files without "
            "loading the model"
        ),
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="permit missing allowlisted files to download during acquisition",
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
            "required for acquisition and execution"
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
    if args.output is not None and args.output.exists():
        print(
            f"error: refusing to overwrite existing output: {args.output}",
            file=sys.stderr,
        )
        return 2
    if args.max_tokens < 2 or args.warmup < 0 or args.repeats < 1:
        print("error: invalid token or repeat settings", file=sys.stderr)
        return 2
    if args.execute and args.acquire_only:
        print(
            "error: --execute and --acquire-only are mutually exclusive",
            file=sys.stderr,
        )
        return 2
    if args.execute and args.allow_download:
        print(
            "error: acquisition and loading must be separate; use "
            "--acquire-only --allow-download first",
            file=sys.stderr,
        )
        return 2
    if args.allow_download and not args.acquire_only:
        print(
            "error: --allow-download is meaningful only with --acquire-only",
            file=sys.stderr,
        )
        return 2

    artifact: dict[str, Any] | None = None
    try:
        _set_failure_stage(args, "manifest-source")
        if args.execute or args.acquire_only:
            _require_canonical_manifest(args.manifest)
        _set_failure_stage(args, "manifest-load")
        manifest = dict(load_model_manifest(args.manifest))
        _set_failure_stage(args, "manifest-validation")
        errors = validate_model_manifest(manifest)
        if errors:
            raise ValueError("; ".join(errors))
        _set_failure_stage(args, "artifact-selection")
        artifact = _artifact(manifest, args.artifact)
        if args.execute:
            report = _execute(args, artifact)
        elif args.acquire_only:
            report = _acquire(args, artifact)
        else:
            report = _plan(artifact, args.allow_download)
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
        try:
            _write_report(args.output, report)
        except OSError as error:
            print(f"error: could not preserve report: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
