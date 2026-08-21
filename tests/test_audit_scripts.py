import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_SCRIPT = ROOT / "scripts" / "benchmark_model.py"


def _captured_at(*, seconds_ago: int = 0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    ).isoformat()


def _execution_audit(
    *,
    available_ram: int = 10_000_000,
    torch_free: int = 9_000_000,
    nvidia_free_mib: int = 8,
) -> dict[str, object]:
    return {
        "captured_at": _captured_at(),
        "git": {"head": "a" * 40, "dirty": False},
        "platform": {
            "system": "Windows",
            "machine": "AMD64",
            "hostname": "fixture-host",
        },
        "python": {
            "version": "3.11.9",
            "implementation": "CPython",
            "executable": sys.executable,
        },
        "environment": {"CUDA_VISIBLE_DEVICES": None},
        "packages": {
            "torch": "1",
            "transformers": "1",
            "huggingface-hub": "1",
            "safetensors": "1",
            "accelerate": "1",
        },
        "memory": {
            "total_bytes": 20_000_000,
            "available_bytes": available_ram,
        },
        "torch_runtime": {
            "available": True,
            "version": "1+cu",
            "compiled_cuda_version": "13.0",
            "cuda_available": True,
            "device_count": 1,
            "devices": [
                {
                    "index": 0,
                    "name": "Fixture GPU",
                    "capability": [7, 5],
                    "free_memory_bytes": torch_free,
                    "total_memory_bytes": 10_000_000,
                }
            ],
        },
        "nvidia": {
            "gpus": [
                {
                    "index": 0,
                    "name": "Fixture GPU",
                    "uuid": "GPU-fixture",
                    "memory_total_mib": 10,
                    "memory_free_mib": nvidia_free_mib,
                    "driver_version": "fixture-driver",
                }
            ]
        },
    }


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


def test_resource_audit_refuses_to_overwrite_existing_evidence(
    tmp_path: Path,
) -> None:
    output = tmp_path / "resource.json"
    output.write_text("preserve me\n", encoding="utf-8")

    completed = _run(
        "scripts/audit_local_resources.py",
        "--path",
        str(tmp_path),
        "--repo",
        str(ROOT),
        "--output",
        str(output),
    )

    assert completed.returncode == 2
    assert "refusing to overwrite" in completed.stderr
    assert output.read_text(encoding="utf-8") == "preserve me\n"


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
    assert report["required_download_bytes"] == 2_092_816_302
    assert report["minimum_free_disk_bytes"] == 5_232_040_755
    assert len(report["required_files"]) == 5


def test_model_benchmark_refuses_to_overwrite_existing_evidence(
    tmp_path: Path,
) -> None:
    output = tmp_path / "benchmark.json"
    output.write_text("preserve me\n", encoding="utf-8")

    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--output",
        str(output),
    )

    assert completed.returncode == 2
    assert "refusing to overwrite" in completed.stderr
    assert output.read_text(encoding="utf-8") == "preserve me\n"


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
        "--dtype",
        "float32",
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
        "captured_at": _captured_at(),
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
        "captured_at": _captured_at(),
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
        "captured_at": _captured_at(),
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
        "captured_at": _captured_at(),
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
        execute=True,
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
        "captured_at": _captured_at(),
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


def test_resource_audit_timestamp_must_be_fresh_and_timezone_aware() -> None:
    module = _benchmark_module()

    assert module._resource_audit_age_seconds(
        {"captured_at": _captured_at(seconds_ago=5)}
    ) >= 0
    with pytest.raises(ValueError, match="stale"):
        module._resource_audit_age_seconds(
            {
                "captured_at": _captured_at(
                    seconds_ago=module.MAX_RESOURCE_AUDIT_AGE_SECONDS + 1
                )
            }
        )
    with pytest.raises(ValueError, match="future"):
        module._resource_audit_age_seconds(
            {"captured_at": _captured_at(seconds_ago=-61)}
        )
    with pytest.raises(ValueError, match="timezone"):
        module._resource_audit_age_seconds(
            {"captured_at": "2026-08-20T12:00:00"}
        )


def test_execution_resources_bind_identity_and_conservative_headroom() -> None:
    module = _benchmark_module()
    audited = _execution_audit()
    live = _execution_audit(torch_free=7_000_000, nvidia_free_mib=6)

    report = module._validate_execution_resources(
        audited,
        live,
        {"weight_size_bytes": 1_000_000},
    )

    assert report["live_vram"]["torch_free_bytes"] == 7_000_000
    assert report["live_vram"]["nvidia_smi_free_bytes"] == 6 * 1024 * 1024
    assert report["live_vram"]["conservative_free_bytes"] == 6 * 1024 * 1024
    assert report["minimum_available_ram_bytes"] == 2_000_000
    assert report["conservative_available_ram_bytes"] == 10_000_000
    assert report["ram_threshold_enforced"] is True
    assert report["ram_threshold_passed"] is True
    assert report["ram_threshold_override_used"] is False
    assert report["minimum_free_vram_bytes"] == 1_500_000

    overridden = module._validate_execution_resources(
        audited,
        live,
        {"weight_size_bytes": 1_000_000},
        minimum_free_vram_bytes=5_000_000,
    )
    assert overridden["minimum_free_vram_bytes"] == 5_000_000

    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="positive integer"):
            module._validate_execution_resources(
                audited,
                live,
                {"weight_size_bytes": 1_000_000},
                minimum_free_vram_bytes=invalid,
            )

    cpu_report = module._validate_execution_resources(
        audited,
        live,
        {"weight_size_bytes": 1_000_000},
        require_cuda=False,
    )
    assert cpu_report["minimum_available_ram_bytes"] == 3_000_000
    assert cpu_report["minimum_free_vram_bytes"] is None


def test_execution_resources_reject_identity_and_headroom_drift() -> None:
    module = _benchmark_module()
    audited = _execution_audit()

    package_drift = _execution_audit()
    package_drift["packages"]["torch"] = "different"
    with pytest.raises(ValueError, match="package torch"):
        module._validate_execution_resources(
            audited,
            package_drift,
            {"weight_size_bytes": 1_000_000},
        )

    low_ram = _execution_audit(available_ram=1_000_000)
    with pytest.raises(RuntimeError, match="RAM"):
        module._validate_execution_resources(
            audited,
            low_ram,
            {"weight_size_bytes": 1_000_000},
        )

    low_ram_override = module._validate_execution_resources(
        audited,
        low_ram,
        {"weight_size_bytes": 1_000_000},
        enforce_ram_threshold=False,
    )
    assert low_ram_override["ram_threshold_enforced"] is False
    assert low_ram_override["ram_threshold_passed"] is False
    assert low_ram_override["ram_threshold_override_used"] is True

    low_vram = _execution_audit(nvidia_free_mib=1)
    with pytest.raises(RuntimeError, match="VRAM"):
        module._validate_execution_resources(
            audited,
            low_vram,
            {"weight_size_bytes": 1_000_000},
            enforce_ram_threshold=False,
        )


def test_live_resource_audit_is_embedded_with_verifiable_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _benchmark_module()
    audited = _execution_audit()
    live = _execution_audit(available_ram=1_000_000)
    args = argparse.Namespace(
        device="cuda",
        allow_low_ram=True,
        _supplied_resource_audit=audited,
    )
    monkeypatch.setattr(
        module,
        "_capture_live_resource_audit",
        lambda _path: (live, "c" * 64),
    )

    report = module._live_execution_preflight(
        args,
        {"weight_size_bytes": 1_000_000},
        {"cache_storage_path": str(tmp_path)},
    )

    assert report["live_resource_audit"] == live
    assert report["live_resource_audit_sha256"] == "c" * 64
    assert report["execution_resource_validation"]["live_vram"]
    assert report["execution_resource_validation"][
        "ram_threshold_override_used"
    ] is True

    post_report = module._post_import_resource_preflight(
        args,
        {"weight_size_bytes": 1_000_000},
        report,
    )
    assert post_report["post_import_resource_audit"] == live
    assert post_report["post_import_resource_audit_sha256"] == "c" * 64
    assert post_report["post_import_resource_validation"][
        "ram_threshold_override_used"
    ] is True


def test_parent_imported_runtime_must_match_live_audit() -> None:
    module = _benchmark_module()
    preflight = {"live_resource_audit": _execution_audit()}

    class Version:
        cuda = "13.0"

    class Properties:
        total_memory = 10_000_000

    class Cuda:
        @staticmethod
        def is_available() -> bool:
            return True

        @staticmethod
        def device_count() -> int:
            return 1

        @staticmethod
        def get_device_properties(_index: int) -> Properties:
            return Properties()

        @staticmethod
        def get_device_name(_index: int) -> str:
            return "Fixture GPU"

        @staticmethod
        def get_device_capability(_index: int) -> tuple[int, int]:
            return (7, 5)

    class Torch:
        __version__ = "1+cu"
        version = Version()
        cuda = Cuda()

    class Transformers:
        __version__ = "1"

    report = module._verify_parent_runtime(
        Torch,
        Transformers,
        preflight,
        device="cuda",
    )
    assert report["verified"] is True

    Transformers.__version__ = "different"
    with pytest.raises(ValueError, match="Transformers version"):
        module._verify_parent_runtime(
            Torch,
            Transformers,
            preflight,
            device="cuda",
        )


def test_required_model_files_are_hashed_before_loading(tmp_path: Path) -> None:
    module = _benchmark_module()
    payload = b"deterministic model fixture"
    config = b'{}\n'
    (tmp_path / "model.safetensors").write_bytes(payload)
    (tmp_path / "config.json").write_bytes(config)
    artifact = {
        "required_files": [
            {
                "filename": "model.safetensors",
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
            {
                "filename": "config.json",
                "size_bytes": len(config),
                "sha256": hashlib.sha256(config).hexdigest(),
            },
        ]
    }

    verified = module._verify_required_files(tmp_path, artifact)

    assert [item["filename"] for item in verified] == [
        "model.safetensors",
        "config.json",
    ]
    assert all(item["verified"] is True for item in verified)

    (tmp_path / "model.safetensors").write_bytes(b"tampered model fixture")
    with pytest.raises(RuntimeError, match="size mismatch|SHA-256 mismatch"):
        module._verify_required_files(tmp_path, artifact)

    (tmp_path / "model.safetensors").write_bytes(payload)
    (tmp_path / "unexpected.py").write_text("pass\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="outside the exact allowlist"):
        module._verify_required_files(tmp_path, artifact)


def test_snapshot_acquisition_verifies_revision_allowlist_and_config(
    tmp_path: Path,
) -> None:
    module = _benchmark_module()
    revision = "a" * 40
    cache = tmp_path / "cache"
    snapshot = cache / "models--owner--model" / "snapshots" / revision
    snapshot.mkdir(parents=True)
    weight = b"fixture weights"
    config = json.dumps(
        {
            "model_type": "gpt_neox",
            "architectures": ["GPTNeoXForCausalLM"],
            "torch_dtype": "float16",
        },
        sort_keys=True,
    ).encode("utf-8")
    (snapshot / "model.safetensors").write_bytes(weight)
    (snapshot / "config.json").write_bytes(config)
    artifact = {
        "id": "fixture-model",
        "repository": "owner/model",
        "revision": revision,
        "model_type": "gpt_neox",
        "architecture": "GPTNeoXForCausalLM",
        "required_files": [
            {
                "filename": "config.json",
                "size_bytes": len(config),
                "sha256": hashlib.sha256(config).hexdigest(),
            },
            {
                "filename": "model.safetensors",
                "size_bytes": len(weight),
                "sha256": hashlib.sha256(weight).hexdigest(),
            },
        ],
    }
    args = argparse.Namespace(cache_dir=cache, allow_download=True)
    observed: dict[str, object] = {}

    def fake_snapshot_download(**kwargs: object) -> str:
        observed.update(kwargs)
        return str(snapshot)

    returned, _, integrity = module._acquire_snapshot(
        args,
        artifact,
        revision,
        fake_snapshot_download,
    )

    assert returned == snapshot
    assert observed["revision"] == revision
    assert observed["allow_patterns"] == ["config.json", "model.safetensors"]
    assert observed["local_files_only"] is False
    assert observed["max_workers"] == 1
    assert integrity["resolved_revision"] == revision
    assert integrity["config"]["verified"] is True


def test_snapshot_and_config_identity_mismatches_fail_closed(
    tmp_path: Path,
) -> None:
    module = _benchmark_module()
    cache = tmp_path / "cache"
    wrong_snapshot = cache / "snapshots" / ("b" * 40)
    wrong_snapshot.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="requested revision"):
        module._verify_snapshot_identity(wrong_snapshot, cache, "a" * 40)

    config_path = wrong_snapshot / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "model_type": "gpt_neox",
                "architectures": ["GPTNeoXForCausalLM"],
                "torch_dtype": "float16",
                "auto_map": {"AutoModel": "custom.Code"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="auto_map"):
        module._verify_model_config(
            wrong_snapshot,
            {
                "model_type": "gpt_neox",
                "architecture": "GPTNeoXForCausalLM",
            },
        )


def test_loaded_model_and_logits_semantics_are_verified() -> None:
    module = _benchmark_module()

    class FakeParameter:
        dtype = "torch.float16"

        def numel(self) -> int:
            return 7

    class FakeConfig:
        model_type = "gpt_neox"
        _attn_implementation = "sdpa"

    model_type = type(
        "GPTNeoXForCausalLM",
        (),
        {
            "config": FakeConfig(),
            "parameters": lambda self: [FakeParameter()],
        },
    )
    model = model_type()
    identity = module._verify_loaded_model(
        model,
        {
            "architecture": "GPTNeoXForCausalLM",
            "model_type": "gpt_neox",
            "parameter_count": 7,
        },
        "torch.float16",
    )
    assert identity["verified"] is True
    assert identity["attention_implementation"] == "sdpa"
    assert identity["sdpa_backends"] == ["math"]
    assert identity["sdpa_math_allow_fp16_reduction"] is False

    model.config._attn_implementation = "eager"
    with pytest.raises(RuntimeError, match="attention implementation mismatch"):
        module._verify_loaded_model(
            model,
            {
                "architecture": "GPTNeoXForCausalLM",
                "model_type": "gpt_neox",
                "parameter_count": 7,
            },
            "torch.float16",
        )
    model.config._attn_implementation = "sdpa"

    class Scalar:
        def __init__(self, value: bool) -> None:
            self.value = value

        def item(self) -> bool:
            return self.value

    class FiniteResult:
        def __init__(self, value: bool) -> None:
            self.value = value

        def all(self) -> Scalar:
            return Scalar(self.value)

    class FakeTorch:
        finite = True

        @classmethod
        def isfinite(cls, _value: object) -> FiniteResult:
            return FiniteResult(cls.finite)

    logits = type("Logits", (), {"shape": (1, 4, 10)})()
    inputs = type("Inputs", (), {"shape": (1, 4)})()
    assert module._verify_logits(FakeTorch, logits, inputs, 10)["finite"] is True

    FakeTorch.finite = False
    with pytest.raises(RuntimeError, match="non-finite"):
        module._verify_logits(FakeTorch, logits, inputs, 10)


def test_benchmark_prompt_rejects_silent_truncation() -> None:
    module = _benchmark_module()
    valid = type("Inputs", (), {"shape": (1, 4)})()
    too_long = type("Inputs", (), {"shape": (1, 5)})()

    assert module._validate_tokenized_prompt(valid, 4) == 4
    with pytest.raises(RuntimeError, match="truncation is forbidden"):
        module._validate_tokenized_prompt(too_long, 4)


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


def test_download_flag_requires_acquire_only() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--allow-download",
    )

    assert completed.returncode == 2
    assert "meaningful only with --acquire-only" in completed.stderr


def test_execution_rejects_combined_download_and_load() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--execute",
        "--allow-download",
    )

    assert completed.returncode == 2
    assert "acquisition and loading must be separate" in completed.stderr


def test_low_ram_override_requires_execution() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--allow-low-ram",
    )

    assert completed.returncode == 2
    assert "meaningful only with --execute" in completed.stderr


def test_peak_process_memory_is_measurable_on_supported_platform() -> None:
    module = _benchmark_module()

    peak = module._max_rss_bytes()
    assert isinstance(peak, int)
    assert peak > 0
