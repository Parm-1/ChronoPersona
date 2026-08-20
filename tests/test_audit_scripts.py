import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = ROOT / "scripts" / "benchmark_model.py"


def _benchmark_module():
    spec = importlib.util.spec_from_file_location(
        "benchmark_model",
        BENCHMARK_SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_local_resource_audit_runs_without_network(tmp_path: Path) -> None:
    output = tmp_path / "resource.json"

    completed = _run(
        "scripts/audit_local_resources.py",
        "--path",
        str(tmp_path),
        "--repo",
        str(ROOT),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["audit_type"] == "local-resource-audit"
    assert report["network_access_performed"] is False
    assert report["disk"]["free_bytes"] > 0
    assert "gpus" in report["nvidia"]
    assert isinstance(report["torch_runtime"]["available"], bool)


def test_model_benchmark_defaults_to_no_network_plan() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["mode"] == "plan"
    assert report["status"] == "planned"
    assert report["network_access_permitted"] is False
    assert report["weights_downloaded"] is False
    assert report["execution_status"] == "benchmark-ready"


def test_blocked_artifact_cannot_execute() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "datedgpt-2013-base",
        "--execute",
    )

    assert completed.returncode == 1
    assert "not benchmark-ready" in completed.stderr


def test_blocked_execution_preserves_structured_failure(tmp_path: Path) -> None:
    output = tmp_path / "failed.json"
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "datedgpt-2013-base",
        "--execute",
        "--output",
        str(output),
    )

    assert completed.returncode == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["mode"] == "execute"
    assert report["artifact_id"] == "datedgpt-2013-base"
    assert report["network_download_permitted"] is False
    assert report["download_completion_status"] == "not-permitted"
    assert report["error_type"] == "ValueError"
    assert "not benchmark-ready" in report["error"]


def test_ready_execution_requires_resource_audit() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--execute",
        "--device",
        "cpu",
    )

    assert completed.returncode == 1
    assert "--resource-audit is required" in completed.stderr


def test_execution_rejects_an_external_manifest(tmp_path: Path) -> None:
    external_manifest = tmp_path / "MODEL_MANIFEST.json"
    external_manifest.write_bytes(
        (ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json").read_bytes()
    )

    completed = _run(
        "scripts/benchmark_model.py",
        "--manifest",
        str(external_manifest),
        "--artifact",
        "pythia-1b-deduped-main",
        "--execute",
        "--device",
        "cpu",
    )

    assert completed.returncode == 1
    assert "canonical committed model manifest" in completed.stderr


def test_execution_resource_preflight_requires_explicit_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _benchmark_module()
    audit = {
        "git": {"head": "a" * 40, "dirty": False},
        "disk": {"path": str(tmp_path), "free_bytes": 10_000},
    }
    monkeypatch.setattr(
        module,
        "_load_resource_audit",
        lambda _path: (audit, "b" * 64),
    )
    monkeypatch.setattr(
        module,
        "_current_git_state",
        lambda: ("a" * 40, False),
    )
    args = argparse.Namespace(
        resource_audit=tmp_path / "audit.json",
        device="cpu",
        cache_dir=None,
        allow_download=False,
    )

    with pytest.raises(RuntimeError, match="--cache-dir is required"):
        module._resource_preflight(args, {"weight_size_bytes": 100})

    args.cache_dir = tmp_path / "missing-cache"
    with pytest.raises(RuntimeError, match="model cache does not exist"):
        module._resource_preflight(args, {"weight_size_bytes": 100})


def test_resource_preflight_uses_filesystem_device_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _benchmark_module()
    audit_disk = tmp_path / "audit-disk"
    cache = tmp_path / "cache"
    audit_disk.mkdir()
    cache.mkdir()
    audit = {
        "git": {"head": "a" * 40, "dirty": False},
        "disk": {"path": str(audit_disk), "free_bytes": 10_000},
    }
    monkeypatch.setattr(
        module,
        "_load_resource_audit",
        lambda _path: (audit, "b" * 64),
    )
    monkeypatch.setattr(
        module,
        "_current_git_state",
        lambda: ("a" * 40, False),
    )
    monkeypatch.setattr(
        module,
        "_filesystem_device",
        lambda path: 1 if path.name == "audit-disk" else 2,
    )
    args = argparse.Namespace(
        resource_audit=tmp_path / "audit.json",
        device="cpu",
        cache_dir=cache,
        allow_download=False,
    )

    with pytest.raises(ValueError, match="same filesystem"):
        module._resource_preflight(args, {"weight_size_bytes": 100})


def test_resource_preflight_accepts_clean_bound_local_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _benchmark_module()
    cache = tmp_path / "cache"
    cache.mkdir()
    audit = {
        "git": {"head": "a" * 40, "dirty": False},
        "disk": {"path": str(cache), "free_bytes": 10_000},
    }
    monkeypatch.setattr(
        module,
        "_load_resource_audit",
        lambda _path: (audit, "b" * 64),
    )
    monkeypatch.setattr(
        module,
        "_current_git_state",
        lambda: ("a" * 40, False),
    )
    args = argparse.Namespace(
        resource_audit=tmp_path / "audit.json",
        device="cpu",
        cache_dir=cache,
        allow_download=False,
    )

    report = module._resource_preflight(
        args,
        {"weight_size_bytes": 100},
    )

    assert report["git_head"] == "a" * 40
    assert report["resource_audit_sha256"] == "b" * 64
    assert report["cache_storage_path"] == str(cache.resolve())


def test_resource_preflight_rejects_head_and_cuda_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _benchmark_module()
    audit = {
        "git": {"head": "a" * 40, "dirty": False},
        "disk": {"path": str(tmp_path), "free_bytes": 10_000},
        "torch_runtime": {
            "cuda_available": False,
            "compiled_cuda_version": None,
        },
    }
    monkeypatch.setattr(
        module,
        "_load_resource_audit",
        lambda _path: (audit, "b" * 64),
    )
    args = argparse.Namespace(
        resource_audit=tmp_path / "audit.json",
        device="cuda",
        cache_dir=tmp_path,
        allow_download=False,
    )

    monkeypatch.setattr(
        module,
        "_current_git_state",
        lambda: ("c" * 40, False),
    )
    with pytest.raises(ValueError, match="does not match"):
        module._resource_preflight(args, {"weight_size_bytes": 100})

    monkeypatch.setattr(
        module,
        "_current_git_state",
        lambda: ("a" * 40, False),
    )
    with pytest.raises(ValueError, match="CUDA availability"):
        module._resource_preflight(args, {"weight_size_bytes": 100})


def test_download_preflight_enforces_audited_disk_margin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _benchmark_module()
    cache = tmp_path / "cache"
    cache.mkdir()
    audit = {
        "git": {"head": "a" * 40, "dirty": False},
        "disk": {"path": str(cache), "free_bytes": 249},
    }
    monkeypatch.setattr(
        module,
        "_load_resource_audit",
        lambda _path: (audit, "b" * 64),
    )
    monkeypatch.setattr(
        module,
        "_current_git_state",
        lambda: ("a" * 40, False),
    )
    args = argparse.Namespace(
        resource_audit=tmp_path / "audit.json",
        device="cpu",
        cache_dir=cache,
        allow_download=True,
    )

    with pytest.raises(RuntimeError, match="2.5x model safety margin"):
        module._resource_preflight(args, {"weight_size_bytes": 100})


def test_unexpected_execution_failure_preserves_preflight_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _benchmark_module()
    output = tmp_path / "failed.json"

    def fail_after_preflight(
        args: argparse.Namespace,
        _artifact: dict[str, object],
    ) -> dict[str, object]:
        module._set_failure_stage(args, "model-load")
        args._resource_preflight = {
            "resource_audit_sha256": "b" * 64,
            "git_head": "a" * 40,
        }
        raise TypeError("unexpected loader failure")

    monkeypatch.setattr(module, "_execute", fail_after_preflight)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(BENCHMARK_SCRIPT),
            "--artifact",
            "pythia-1b-deduped-main",
            "--execute",
            "--cache-dir",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )

    assert module.main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["error_type"] == "TypeError"
    assert report["failure_stage"] == "model-load"
    assert report["resource_preflight"]["git_head"] == "a" * 40
    assert report["resource_preflight"]["resource_audit_sha256"] == "b" * 64


def test_download_flag_requires_execute() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--allow-download",
    )

    assert completed.returncode == 2
    assert "meaningful only with --execute" in completed.stderr


def test_peak_process_memory_is_measurable_on_supported_platform() -> None:
    module = _benchmark_module()

    peak = module._max_rss_bytes()
    assert isinstance(peak, int)
    assert peak > 0
