#!/usr/bin/env python3
"""Record a local ChronoPersona hardware and software audit.

This command is read-only. It performs no network access, model download, or
training. Output is deterministic except for timestamps and live resource
values.
"""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


PACKAGES = (
    "torch",
    "transformers",
    "accelerate",
    "huggingface-hub",
    "safetensors",
    "datasets",
    "deepspeed",
    "bitsandbytes",
)


@dataclass(frozen=True)
class CommandResult:
    available: bool
    returncode: int | None
    stdout: str
    stderr: str


def _run(command: list[str], timeout: int = 15) -> CommandResult:
    executable = shutil.which(command[0])
    if executable is None:
        return CommandResult(False, None, "", "executable not found")
    try:
        completed = subprocess.run(
            [executable, *command[1:]],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return CommandResult(True, None, "", str(error))
    return CommandResult(
        True,
        completed.returncode,
        completed.stdout.strip(),
        completed.stderr.strip(),
    )


def _linux_memory() -> dict[str, int] | None:
    path = Path("/proc/meminfo")
    if not path.exists():
        return None
    values: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            amount = raw.strip().split()[0]
            values[key] = int(amount) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return {
        "total_bytes": values.get("MemTotal", 0),
        "available_bytes": values.get("MemAvailable", 0),
    }


def _windows_memory() -> dict[str, int] | None:
    if os.name != "nt":
        return None

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    try:
        success = ctypes.windll.kernel32.GlobalMemoryStatusEx(
            ctypes.byref(status)
        )
    except (AttributeError, OSError):
        return None
    if not success:
        return None
    return {
        "total_bytes": int(status.ullTotalPhys),
        "available_bytes": int(status.ullAvailPhys),
    }


def _macos_memory() -> dict[str, int] | None:
    if platform.system() != "Darwin":
        return None
    total = _run(["sysctl", "-n", "hw.memsize"])
    if total.returncode != 0:
        return None
    try:
        total_bytes = int(total.stdout)
    except ValueError:
        return None
    return {"total_bytes": total_bytes, "available_bytes": 0}


def _memory() -> dict[str, int] | None:
    return _windows_memory() or _linux_memory() or _macos_memory()


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _parse_nvidia_smi() -> dict[str, Any]:
    query = (
        "index,name,uuid,memory.total,memory.free,driver_version,"
        "pstate,temperature.gpu,power.limit"
    )
    result = _run(
        [
            "nvidia-smi",
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ]
    )
    gpu_rows: list[dict[str, Any]] = []
    if result.returncode == 0:
        keys = (
            "index",
            "name",
            "uuid",
            "memory_total_mib",
            "memory_free_mib",
            "driver_version",
            "pstate",
            "temperature_c",
            "power_limit_w",
        )
        for line in result.stdout.splitlines():
            values = [value.strip() for value in line.split(",")]
            if len(values) != len(keys):
                continue
            row: dict[str, Any] = dict(zip(keys, values, strict=True))
            for key in (
                "index",
                "memory_total_mib",
                "memory_free_mib",
                "temperature_c",
            ):
                try:
                    row[key] = int(row[key])
                except ValueError:
                    pass
            try:
                row["power_limit_w"] = float(row["power_limit_w"])
            except ValueError:
                pass
            gpu_rows.append(row)
    return {
        "command": asdict(result),
        "gpus": gpu_rows,
    }


def _git_state(repo: Path) -> dict[str, Any]:
    head = _run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    branch = _run(
        ["git", "-C", str(repo), "branch", "--show-current"]
    )
    status = _run(["git", "-C", str(repo), "status", "--porcelain"])
    return {
        "head": head.stdout if head.returncode == 0 else None,
        "branch": branch.stdout if branch.returncode == 0 else None,
        "dirty": bool(status.stdout) if status.returncode == 0 else None,
        "errors": [
            message
            for message in (head.stderr, branch.stderr, status.stderr)
            if message
        ],
    }


def build_audit(path: Path, repo: Path) -> dict[str, Any]:
    disk = shutil.disk_usage(path)
    memory = _memory()
    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "audit_type": "local-resource-audit",
        "network_access_performed": false,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "cpu": {
            "logical_count": os.cpu_count(),
        },
        "memory": memory,
        "disk": {
            "path": str(path.resolve()),
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        },
        "nvidia": _parse_nvidia_smi(),
        "packages": _package_versions(),
        "environment": {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "HF_HOME": os.environ.get("HF_HOME"),
            "TRANSFORMERS_CACHE": os.environ.get("TRANSFORMERS_CACHE"),
        },
        "git": _git_state(repo),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record local hardware, storage, CUDA, package, and Git state "
            "without network access or model loading."
        )
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="filesystem path whose free storage should be measured",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="repository path used for Git identity",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON output path; stdout is always written",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        audit = build_audit(args.path, args.repo)
    except OSError as error:
        print(f"error: resource audit failed: {error}", file=sys.stderr)
        return 2

    rendered = json.dumps(audit, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
