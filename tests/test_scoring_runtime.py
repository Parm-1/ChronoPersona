import argparse
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

from chronopersona.evaluation import canonical_json_sha256, load_evaluation_registry
from chronopersona.run_registry import build_run_identity
from chronopersona.scoring import CandidateEvidence, score_evaluation_registry
from chronopersona.scoring_runtime import (
    FROZEN_CONFIG_GIT_BLOB,
    FROZEN_RUN_SPEC_SHA256,
    V1_CONFIG_GIT_BLOB,
    V1_RUN_SPEC_SHA256,
    V1_SCORING_PROFILE,
    ScoringRunError,
    _verify_scoring_repeat_bound as verify_scoring_repeat,
    create_only_json,
    expected_tokenizer_id,
    finalize_score_artifact,
    load_accepted_tokenizer_audit,
    load_json_object,
    load_scoring_config,
    pretty_json_bytes,
    receipt_with_self_hash,
    scoring_profile,
    scoring_run_identity_payload,
    validate_complete_receipt,
    validate_score_artifact,
    validate_scoring_config,
    verify_scoring_repeat as verify_scoring_repeat_public,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "runs" / "pythia-development-score-v0.json"
V1_CONFIG = ROOT / "configs" / "runs" / "pythia-development-score-v1.json"
SCORE_SCRIPT = ROOT / "scripts" / "score_registry_transformers.py"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_registry_scores.py"


def _score_cli():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("score_cli_test", SCORE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_cli():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("verify_cli_test", VERIFY_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict:
    return load_scoring_config(CONFIG)


def _v1_config() -> dict:
    return load_scoring_config(V1_CONFIG)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("artifact", "revision"), "b" * 40),
        (("accepted_tokenizer_audit", "prefix_policy"), "bos"),
        (("accepted_tokenizer_audit", "path"), "artifacts/local/other.json"),
        (("model", "dtype"), "float32"),
        (("determinism", "sdpa_backends"), ["efficient"]),
        (("resource_limits", "ram_threshold_enforced"), True),
    ],
)
def test_frozen_scoring_config_rejects_semantic_drift(
    path: tuple[str, str],
    value: object,
) -> None:
    changed = _config()
    changed[path[0]][path[1]] = value

    assert validate_scoring_config(changed)


def test_frozen_scoring_config_has_complete_leaf_binding() -> None:
    assert validate_scoring_config(_config()) == ()


def test_frozen_scoring_config_git_blob_is_exact() -> None:
    observed = subprocess.run(
        [
            "git",
            "hash-object",
            "--path=configs/runs/pythia-development-score-v0.json",
            "configs/runs/pythia-development-score-v0.json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert observed == FROZEN_CONFIG_GIT_BLOB


def test_v1_scoring_config_is_exact_and_profile_allowlisted() -> None:
    config = _v1_config()

    assert validate_scoring_config(config) == ()
    assert scoring_profile(config) is V1_SCORING_PROFILE
    assert canonical_json_sha256(config) == V1_RUN_SPEC_SHA256
    observed = subprocess.run(
        [
            "git",
            "hash-object",
            "--path=configs/runs/pythia-development-score-v1.json",
            "configs/runs/pythia-development-score-v1.json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert observed == V1_CONFIG_GIT_BLOB
    assert config["registry_topology"] == {
        "item_count": 14,
        "form_count": 112,
        "candidate_count": 224,
        "forwarded_token_count": 18_672,
        "predicted_token_count": 18_448,
        "continuation_token_count": 3_216,
        "maximum_full_token_count": 127,
        "maximum_continuation_token_count": 18,
        "maximum_within_form_token_difference": 0,
    }
    assert config["measurement_reliability"]["attempt_execution_modes"] == {
        "a": "canonical",
        "b": "reverse",
    }


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("canonical_inputs", "registry_sha256", "0" * 64),
        ("accepted_tokenizer_audit", "file_sha256", "0" * 64),
        ("scoring", "scorer_version", "substituted"),
        (
            "measurement_reliability",
            "attempt_execution_modes",
            {"a": "reverse", "b": "canonical"},
        ),
        ("measurement_reliability", "criteria_git_blob", "0" * 40),
        ("measurement_reliability", "profile_id", "substituted"),
    ],
)
def test_v1_scoring_config_rejects_cross_profile_drift(
    section: str,
    key: str,
    value: object,
) -> None:
    changed = _v1_config()
    changed[section][key] = value

    assert validate_scoring_config(changed)


def test_public_repeat_verifier_rejects_an_unfrozen_config_before_evidence() -> None:
    config = _v1_config()
    config["network_allowed"] = True
    config["external_spend_cad"] = 999

    with pytest.raises(ScoringRunError, match="canonical identity is not frozen"):
        verify_scoring_repeat_public(
            score_a={},
            score_a_bytes=b"",
            receipt_a={},
            receipt_a_bytes=b"",
            resource_audit_a={},
            resource_audit_a_bytes=b"",
            score_b={},
            score_b_bytes=b"",
            receipt_b={},
            receipt_b_bytes=b"",
            resource_audit_b={},
            resource_audit_b_bytes=b"",
            config=config,
            registry=[],
            tokenizer_audit={},
            expected_git_head="b" * 40,
        )


@pytest.mark.parametrize("config_factory", [_config, _v1_config], ids=["v0", "v1"])
def test_public_repeat_verifier_rejects_substituted_registry_text(
    config_factory,
) -> None:
    config = config_factory()
    registry = deepcopy(
        list(
            load_evaluation_registry(
                ROOT / config["canonical_inputs"]["registry_path"]
            )
        )
    )
    registry[0]["forms"][0]["prompt"] = "FORGED PROMPT NEVER SCORED"

    with pytest.raises(ScoringRunError, match="frozen canonical registry bytes"):
        verify_scoring_repeat_public(
            score_a={},
            score_a_bytes=b"",
            receipt_a={},
            receipt_a_bytes=b"",
            resource_audit_a={},
            resource_audit_a_bytes=b"",
            score_b={},
            score_b_bytes=b"",
            receipt_b={},
            receipt_b_bytes=b"",
            resource_audit_b={},
            resource_audit_b_bytes=b"",
            config=config,
            registry=registry,
            tokenizer_audit={},
            expected_git_head="b" * 40,
        )


def test_v1_git_binding_selects_registry_config_and_criteria(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    observed: dict[str, object] = {}

    def fake_binding(*, registry_path, extra_inputs):
        observed["registry_path"] = registry_path
        observed["extra_inputs"] = extra_inputs
        return ({"git_head": "b" * 40}, {"development_registry": b"registry"})

    monkeypatch.setattr(module.tokenizer_cli, "_execution_git_binding", fake_binding)

    module._bound_execution_inputs(V1_SCORING_PROFILE)

    assert observed["registry_path"] == ROOT / V1_SCORING_PROFILE.registry_path
    assert observed["extra_inputs"] == (
        ("scoring_config", ROOT / V1_SCORING_PROFILE.config_path),
        (
            "measurement_reliability_criteria",
            ROOT / V1_SCORING_PROFILE.criteria_path,
        ),
    )


def _accepted_report(config: dict) -> dict:
    artifact = config["artifact"]
    canonical = config["canonical_inputs"]
    tokenizer = config["accepted_tokenizer_audit"]
    topology = config["registry_topology"]
    profile = scoring_profile(config)
    report = {
        "schema_version": 1,
        "audit_type": "evaluation-tokenizer-audit",
        "mode": "execute",
        "passed": True,
        "failures": [],
        "worktree_clean": True,
        "model_manifest_git_blob": canonical["manifest_git_blob"],
        "model_manifest_sha256": canonical["manifest_sha256"],
        "development_registry_git_blob": canonical["registry_git_blob"],
        "registry_sha256": canonical["registry_sha256"],
        "artifact": {"id": artifact["id"], "revision": artifact["revision"]},
        "prefix_policy": "none",
        "prefix_token_ids": [],
        "summary": {
            "candidate_count": topology["candidate_count"],
            "failure_count": 0,
            "form_count": topology["form_count"],
            "item_count": topology["item_count"],
            "max_continuation_tokens": topology["maximum_continuation_token_count"],
            "max_full_tokens": topology["maximum_full_token_count"],
            "max_within_form_token_difference": topology[
                "maximum_within_form_token_difference"
            ],
        },
        "loaded_tokenizer_validation": {
            "verified": True,
            "backend_sha256": tokenizer["backend_sha256"],
            "native_prefix_probe_sha256": tokenizer[
                "native_prefix_probe_sha256"
            ],
            "native_prefix_policy": "none",
            "native_prefix_probe_equal": True,
            "native_special_tokens_to_add": 0,
        },
        "snapshot_verification": {
            "artifact_id": artifact["id"],
            "receipt_sha256": artifact["snapshot_receipt_sha256"],
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "status": "verified",
        },
        "runtime_identity": {
            "python": config["runtime_identity"]["python"],
            "packages": {
                name: config["runtime_identity"]["packages"][name]
                for name in ("transformers", "tokenizers", "huggingface-hub")
            },
        },
        "offline_enforcement": {
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "local_files_only": True,
            "private_tokenizer_staging": True,
            "trust_remote_code": False,
        },
        "model_weights_deserialized": False,
        "model_weight_bytes_verified": artifact["model_safetensors_size_bytes"],
        "network_access_permitted": False,
        "network_observation": "not-instrumented",
        "scientific_claim_authorized": False,
        "tokenizer_files_downloaded": False,
        "weights_downloaded": False,
        "items": [],
    }
    if scoring_profile(config) is V1_SCORING_PROFILE:
        reliability = config["measurement_reliability"]
        report.update(
            {
                "git_head": reliability["tokenizer_audit_git_head"],
                "measurement_reliability_criteria_git_blob": reliability[
                    "criteria_git_blob"
                ],
                "measurement_reliability": {
                    "profile_id": reliability["profile_id"],
                    "criteria_sha256": reliability["criteria_sha256"],
                    "claim_ceiling": reliability["claim_ceiling"],
                },
            }
        )
    report["output_sha256"] = canonical_json_sha256(report)
    return report


def test_accepted_tokenizer_report_is_file_and_self_hash_bound(tmp_path: Path) -> None:
    config = _config()
    report = _accepted_report(config)
    path = tmp_path / "accepted.json"
    path.write_bytes(pretty_json_bytes(report))
    config["accepted_tokenizer_audit"]["file_sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    config["accepted_tokenizer_audit"]["output_sha256"] = report["output_sha256"]

    loaded, observed_sha = load_accepted_tokenizer_audit(path, config)

    assert loaded == report
    assert observed_sha == config["accepted_tokenizer_audit"]["file_sha256"]

    changed = deepcopy(report)
    changed["network_access_permitted"] = True
    changed["output_sha256"] = canonical_json_sha256(
        {key: value for key, value in changed.items() if key != "output_sha256"}
    )
    path.write_bytes(pretty_json_bytes(changed))
    config["accepted_tokenizer_audit"]["file_sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    config["accepted_tokenizer_audit"]["output_sha256"] = changed["output_sha256"]
    with pytest.raises(ScoringRunError, match="network_access_permitted"):
        load_accepted_tokenizer_audit(path, config)


def test_v1_accepted_tokenizer_report_keeps_its_e2_head_binding(
    tmp_path: Path,
) -> None:
    config = _v1_config()
    report = _accepted_report(config)
    config["measurement_reliability"]["loaded_validation_sha256"] = (
        canonical_json_sha256(report["loaded_tokenizer_validation"])
    )
    config["measurement_reliability"]["runtime_identity_sha256"] = (
        canonical_json_sha256(report["runtime_identity"])
    )
    path = tmp_path / "accepted-v1.json"
    path.write_bytes(pretty_json_bytes(report))
    config["accepted_tokenizer_audit"]["file_sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    config["accepted_tokenizer_audit"]["output_sha256"] = report[
        "output_sha256"
    ]

    loaded, _ = load_accepted_tokenizer_audit(path, config)
    assert loaded["git_head"] == config["measurement_reliability"][
        "tokenizer_audit_git_head"
    ]

    changed = deepcopy(report)
    changed["git_head"] = "c" * 40
    changed["output_sha256"] = canonical_json_sha256(
        {key: value for key, value in changed.items() if key != "output_sha256"}
    )
    path.write_bytes(pretty_json_bytes(changed))
    config["accepted_tokenizer_audit"]["file_sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    config["accepted_tokenizer_audit"]["output_sha256"] = changed[
        "output_sha256"
    ]
    with pytest.raises(ScoringRunError, match="E2 Git head"):
        load_accepted_tokenizer_audit(path, config)


def _small_score_fixture(
    *, left_first_logprob: float = -0.1, base_config: dict | None = None
) -> tuple[dict, list[dict], dict, dict]:
    config = deepcopy(base_config) if base_config is not None else _config()
    config["registry_topology"] = {
        "item_count": 1,
        "form_count": 1,
        "candidate_count": 2,
        "forwarded_token_count": 7,
        "predicted_token_count": 5,
        "continuation_token_count": 3,
        "maximum_full_token_count": 4,
        "maximum_continuation_token_count": 2,
        "maximum_within_form_token_difference": 1,
    }
    registry = [
        {
            "item_id": "item",
            "domain": "domain",
            "construct": "construct",
            "reference_pole": "left",
            "forms": [
                {
                    "form_id": "form",
                    "prompt": "prompt",
                    "candidates": [
                        {"pole": "left", "text": "left"},
                        {"pole": "right", "text": "right"},
                    ],
                }
            ],
        }
    ]
    evidence = {
        "left": CandidateEvidence(
            prompt_token_ids=(1, 2),
            continuation_token_ids=(3, 4),
            token_logprobs=(left_first_logprob, -0.2),
        ),
        "right": CandidateEvidence(
            prompt_token_ids=(1, 2),
            continuation_token_ids=(5,),
            token_logprobs=(-0.3,),
        ),
    }
    score = score_evaluation_registry(
        registry,
        lambda _prompt, continuation: evidence[continuation],
        registry_sha256=config["canonical_inputs"]["registry_sha256"],
        model_id=config["artifact"]["id"],
        model_revision=config["artifact"]["revision"],
        tokenizer_id=expected_tokenizer_id(config),
        scorer_version=config["scoring"]["scorer_version"],
    )
    audit = _accepted_report(config)
    audit["items"] = [
            {
                "item_id": "item",
                "forms": [
                    {
                        "form_id": "form",
                        "candidates": [
                            {
                                "pole": "left",
                                "prompt_token_count": 2,
                                "continuation_token_count": 2,
                                "full_token_count": 4,
                                "continuation_token_ids": [3, 4],
                            },
                            {
                                "pole": "right",
                                "prompt_token_count": 2,
                                "continuation_token_count": 1,
                                "full_token_count": 3,
                                "continuation_token_ids": [5],
                            },
                        ],
                    }
                ],
            }
        ]
    token_records = [
        {
            "item_id": "item",
            "form_id": "form",
            "pole": "left",
            "prompt_token_ids": [1, 2],
            "continuation_token_ids": [3, 4],
        },
        {
            "item_id": "item",
            "form_id": "form",
            "pole": "right",
            "prompt_token_ids": [1, 2],
            "continuation_token_ids": [5],
        },
    ]
    config["accepted_tokenizer_audit"][
        "scoring_token_matrix_sha256"
    ] = canonical_json_sha256(token_records)
    audit["output_sha256"] = canonical_json_sha256(
        {key: value for key, value in audit.items() if key != "output_sha256"}
    )
    config["accepted_tokenizer_audit"]["output_sha256"] = audit[
        "output_sha256"
    ]
    final = finalize_score_artifact(
        score,
        tokenizer_audit=audit,
        config=config,
        run_spec_sha256=scoring_profile(config).run_spec_sha256,
        git_head="b" * 40,
    )
    return config, registry, audit, final


def _attempt_times(attempt: str) -> dict[str, str]:
    if attempt == "a":
        return {
            "audit": "2026-08-20T00:00:00+00:00",
            "started": "2026-08-20T00:00:01+00:00",
            "live": "2026-08-20T00:00:01.250000+00:00",
            "post_import": "2026-08-20T00:00:01.500000+00:00",
            "post_load": "2026-08-20T00:00:02+00:00",
            "post_score": "2026-08-20T00:00:02.250000+00:00",
            "completed": "2026-08-20T00:00:03+00:00",
        }
    return {
        "audit": "2026-08-20T00:00:04+00:00",
        "started": "2026-08-20T00:00:05+00:00",
        "live": "2026-08-20T00:00:05.250000+00:00",
        "post_import": "2026-08-20T00:00:05.500000+00:00",
        "post_load": "2026-08-20T00:00:06+00:00",
        "post_score": "2026-08-20T00:00:06.250000+00:00",
        "completed": "2026-08-20T00:00:07+00:00",
    }


def _resource_audit_fixture(
    attempt: str,
    git_head: str = "b" * 40,
    *,
    captured_at: str | None = None,
    available_ram_bytes: int = 5_000_000_000,
    torch_free_bytes: int = 4_500_000_000,
    nvidia_free_mib: int = 4096,
) -> dict:
    runtime = _config()["runtime_identity"]
    return {
        "audit_type": "local-resource-audit",
        "captured_at": captured_at or _attempt_times(attempt)["audit"],
        "cpu": {"logical_count": 12},
        "disk": {
            "path": str((ROOT / "artifacts" / "local" / "hf-cache").resolve()),
            "total_bytes": 20_000_000_000,
            "used_bytes": 10_000_000_000,
            "free_bytes": 10_000_000_000,
        },
        "environment": {
            "CUDA_VISIBLE_DEVICES": None,
            "HF_HOME": None,
            "TRANSFORMERS_CACHE": None,
        },
        "git": {
            "branch": "feat/verified-registry-scoring",
            "dirty": False,
            "errors": [],
            "head": git_head,
        },
        "memory": {
            "available_bytes": available_ram_bytes,
            "total_bytes": 17_000_000_000,
        },
        "network_access_performed": False,
        "nvidia": {
            "command": {
                "available": True,
                "returncode": 0,
                "stderr": "",
                "stdout": "fixture",
            },
            "gpus": [
                {
                    "driver_version": "591.86",
                    "index": 0,
                    "memory_free_mib": nvidia_free_mib,
                    "memory_total_mib": 6144,
                    "name": runtime["cuda_device_name"],
                    "power_limit_w": 125.0,
                    "pstate": "P8",
                    "temperature_c": 50,
                    "uuid": "GPU-fixture",
                }
            ],
        },
        "packages": {
            "accelerate": runtime["packages"]["accelerate"],
            "bitsandbytes": None,
            "datasets": None,
            "deepspeed": None,
            "huggingface-hub": runtime["packages"]["huggingface-hub"],
            "safetensors": runtime["packages"]["safetensors"],
            "torch": runtime["packages"]["torch"],
            "transformers": runtime["packages"]["transformers"],
        },
        "platform": {
            "hostname": "fixture-host",
            "machine": "AMD64",
            "processor": "fixture-cpu",
            "release": "10",
            "system": "Windows",
            "version": "10.0",
        },
        "python": {
            "executable": r"C:\Python311\python.exe",
            "implementation": "CPython",
            "version": runtime["python"],
        },
        "schema_version": 1,
        "torch_runtime": {
            "available": True,
            "compiled_cuda_version": runtime["cuda_runtime"],
            "cuda_available": True,
            "device_count": runtime["cuda_device_count"],
            "devices": [
                {
                    "capability": runtime["cuda_compute_capability"],
                    "free_memory_bytes": torch_free_bytes,
                    "index": runtime["cuda_device_index"],
                    "name": runtime["cuda_device_name"],
                    "total_memory_bytes": runtime["cuda_total_memory_bytes"],
                }
            ],
            "errors": [],
            "version": runtime["packages"]["torch"],
        },
    }


def _conservative_vram_fixture(audit: dict) -> dict[str, int]:
    torch_free = audit["torch_runtime"]["devices"][0]["free_memory_bytes"]
    nvidia_free = audit["nvidia"]["gpus"][0]["memory_free_mib"] * 1024 * 1024
    return {
        "torch_free_bytes": torch_free,
        "nvidia_smi_free_bytes": nvidia_free,
        "conservative_free_bytes": min(torch_free, nvidia_free),
    }


def _resource_validation_fixture(
    audited: dict,
    live: dict,
    config: dict,
    *,
    minimum_free_vram_bytes: int | None = None,
) -> dict:
    weight_bytes = config["artifact"]["model_safetensors_size_bytes"]
    audited_ram = audited["memory"]["available_bytes"]
    live_ram = live["memory"]["available_bytes"]
    minimum_ram = weight_bytes * 2
    ram_passed = min(audited_ram, live_ram) >= minimum_ram
    return {
        "packages": {
            package: live["packages"][package]
            for package in (
                "torch",
                "transformers",
                "huggingface-hub",
                "safetensors",
                "accelerate",
            )
        },
        "python": live["python"],
        "torch_runtime": {
            "version": live["torch_runtime"]["version"],
            "compiled_cuda_version": live["torch_runtime"][
                "compiled_cuda_version"
            ],
            "device": live["torch_runtime"]["devices"][0],
        },
        "nvidia_smi_device": live["nvidia"]["gpus"][0],
        "audited_available_ram_bytes": audited_ram,
        "live_available_ram_bytes": live_ram,
        "conservative_available_ram_bytes": min(audited_ram, live_ram),
        "minimum_available_ram_bytes": minimum_ram,
        "ram_threshold_enforced": False,
        "ram_threshold_passed": ram_passed,
        "ram_threshold_override_used": not ram_passed,
        "audited_vram": _conservative_vram_fixture(audited),
        "live_vram": _conservative_vram_fixture(live),
        "minimum_free_vram_bytes": (
            (weight_bytes * 3 + 1) // 2
            if minimum_free_vram_bytes is None
            else minimum_free_vram_bytes
        ),
    }


def _repeat_audit_kwargs() -> dict:
    audit_a = _resource_audit_fixture("a")
    audit_b = _resource_audit_fixture("b")
    return {
        "resource_audit_a": audit_a,
        "resource_audit_a_bytes": pretty_json_bytes(audit_a),
        "resource_audit_b": audit_b,
        "resource_audit_b_bytes": pretty_json_bytes(audit_b),
    }


def _receipt(
    score: dict,
    score_bytes: bytes,
    attempt: str,
    *,
    config: dict,
    tokenizer_audit: dict,
    process_id: int,
) -> dict:
    binding = {
        "size_bytes": len(score_bytes),
        "file_sha256": hashlib.sha256(score_bytes).hexdigest(),
        "output_sha256": score["output_sha256"],
    }
    artifact = config["artifact"]
    canonical = config["canonical_inputs"]
    accepted = config["accepted_tokenizer_audit"]
    runtime = config["runtime_identity"]
    determinism = {
        "attention_implementation": "sdpa",
        "sdpa_backends": ["math"],
        "sdpa_math_allow_fp16_reduction": False,
        "algorithms": True,
        "cublas_workspace_config": ":4096:8",
        "tf32": False,
        "cudnn_tf32": False,
        "cudnn_benchmark": False,
        "float32_matmul_precision": "highest",
        "manual_seed": 0,
        "verified": True,
    }
    topology = config["registry_topology"]
    profile = scoring_profile(config)
    git_head = "b" * 40
    times = _attempt_times(attempt)
    supplied_audit = _resource_audit_fixture(attempt, git_head)
    supplied_audit_bytes = pretty_json_bytes(supplied_audit)
    live_audit = _resource_audit_fixture(
        attempt,
        git_head,
        captured_at=times["live"],
        available_ram_bytes=4_900_000_000,
        torch_free_bytes=4_400_000_000,
        nvidia_free_mib=4050,
    )
    post_import_audit = _resource_audit_fixture(
        attempt,
        git_head,
        captured_at=times["post_import"],
        available_ram_bytes=4_800_000_000,
        torch_free_bytes=4_300_000_000,
        nvidia_free_mib=4000,
    )
    post_load_audit = _resource_audit_fixture(
        attempt,
        git_head,
        captured_at=times["post_load"],
        available_ram_bytes=4_700_000_000,
        torch_free_bytes=3_900_000_000,
        nvidia_free_mib=3600,
    )
    post_score_audit = _resource_audit_fixture(
        attempt,
        git_head,
        captured_at=times["post_score"],
        available_ram_bytes=4_600_000_000,
        torch_free_bytes=3_800_000_000,
        nvidia_free_mib=3500,
    )
    run_id = build_run_identity(
        scoring_run_identity_payload(config, git_head)
    )["run_id"]
    output_observation = lambda phase: {
        "phase": phase,
        "minimum_free_bytes": config["resource_limits"][
            "minimum_output_free_bytes"
        ],
        "outputs": {
            label: {
                "filesystem_device": 1,
                "free_bytes": config["resource_limits"][
                    "minimum_output_free_bytes"
                ],
            }
            for label in ("score", "runtime")
        },
        "passed": True,
    }
    def resource_observation(label: str, observed: dict) -> dict:
        return {
            "label": label,
            "audit_sha256": hashlib.sha256(pretty_json_bytes(observed)).hexdigest(),
            "audit_semantic_sha256": canonical_json_sha256(observed),
            "captured_at": observed["captured_at"],
            "age_seconds": 0.0,
            "conservative_vram": _conservative_vram_fixture(observed),
            "execution_resource_validation": _resource_validation_fixture(
                post_import_audit,
                observed,
                config,
                minimum_free_vram_bytes=config["resource_limits"][
                    "minimum_postload_global_free_vram_bytes"
                ],
            ),
            "audit": observed,
        }
    git_binding = {
        "git_head": git_head,
        "worktree_clean": True,
        "model_manifest_git_blob": canonical["manifest_git_blob"],
        "development_registry_git_blob": canonical["registry_git_blob"],
        "scoring_config_git_blob": profile.config_git_blob,
    }
    if profile is V1_SCORING_PROFILE:
        git_binding["measurement_reliability_criteria_git_blob"] = config[
            "measurement_reliability"
        ]["criteria_git_blob"]
    receipt_body = {
            "schema_version": 1,
            "receipt_type": "registry-score-runtime",
            "status": "complete",
            "attempt": attempt,
            "run_id": run_id,
            "process_id": process_id,
            "started_at": times["started"],
            "completed_at": times["completed"],
            "network_access_permitted": False,
            "network_observation": "not-instrumented",
            "scientific_claim_authorized": False,
            "git": git_binding,
            "run_spec": {
                "sha256": profile.run_spec_sha256,
                "git_blob": profile.config_git_blob,
            },
            "canonical_inputs": {
                "model_manifest_sha256": canonical["manifest_sha256"],
                "registry_sha256": canonical["registry_sha256"],
            },
            "accepted_tokenizer": {
                "file_sha256": accepted["file_sha256"],
                "output_sha256": accepted["output_sha256"],
            },
            "snapshot_verification": tokenizer_audit["snapshot_verification"],
            "model_validation": {
                "class": config["model"]["class"],
                "model_type": config["model"]["model_type"],
                "parameter_count": config["model"]["parameter_count"],
                "parameter_dtypes": ["torch.float16"],
                "parameter_devices": ["cuda:0"],
                "buffer_devices": ["cuda:0"],
                "vocabulary_size": config["model"]["vocabulary_size"],
                "eval_mode": True,
                "quantized": False,
                "device_map": False,
                "offload_hooks": False,
                "meta_parameters": False,
                "meta_buffers": False,
                "attention_implementation": "sdpa",
                "sdpa_backends": ["math"],
                "sdpa_math_allow_fp16_reduction": False,
                "determinism": determinism,
                "verified": True,
            },
            "model_loading_info": {
                "error_msgs": [],
                "mismatched_keys": [],
                "missing_keys": [],
                "unexpected_keys": [],
            },
            "tokenizer_validation": tokenizer_audit[
                "loaded_tokenizer_validation"
            ],
            "runtime_identity": {
                "python": runtime["python"],
                "packages": runtime["packages"],
                "cuda_runtime": runtime["cuda_runtime"],
                "cuda_device": {
                    "index": runtime["cuda_device_index"],
                    "name": runtime["cuda_device_name"],
                    "capability": runtime["cuda_compute_capability"],
                    "total_memory_bytes": runtime["cuda_total_memory_bytes"],
                },
                "verified": True,
            },
            "determinism": determinism,
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
            "resource_preflight": {
                "resource_audit": r"C:\audits\resource.json",
                "resource_audit_sha256": hashlib.sha256(
                    supplied_audit_bytes
                ).hexdigest(),
                "resource_audit_captured_at": supplied_audit["captured_at"],
                "resource_audit_age_seconds": 1.25,
                "git_head": git_head,
                "audit_disk_free_bytes": supplied_audit["disk"]["free_bytes"],
                "audit_disk_path": supplied_audit["disk"]["path"],
                "cache_storage_path": supplied_audit["disk"]["path"],
                "filesystem_device": 1,
                "live_disk_free_bytes": live_audit["disk"]["free_bytes"],
                "live_resource_audit_sha256": hashlib.sha256(
                    pretty_json_bytes(live_audit)
                ).hexdigest(),
                "live_resource_audit_captured_at": live_audit["captured_at"],
                "live_resource_audit_age_seconds": 0.0,
                "live_resource_audit": live_audit,
                "live_resource_audit_semantic_sha256": canonical_json_sha256(
                    live_audit
                ),
                "execution_resource_validation": _resource_validation_fixture(
                    supplied_audit,
                    live_audit,
                    config,
                    minimum_free_vram_bytes=config["resource_limits"][
                        "minimum_preload_free_vram_bytes"
                    ],
                ),
                "post_import_resource_audit_sha256": hashlib.sha256(
                    pretty_json_bytes(post_import_audit)
                ).hexdigest(),
                "post_import_resource_audit_captured_at": post_import_audit[
                    "captured_at"
                ],
                "post_import_resource_audit_age_seconds": 0.0,
                "post_import_resource_audit": post_import_audit,
                "post_import_resource_audit_semantic_sha256": (
                    canonical_json_sha256(post_import_audit)
                ),
                "post_import_resource_validation": _resource_validation_fixture(
                    supplied_audit,
                    post_import_audit,
                    config,
                    minimum_free_vram_bytes=config["resource_limits"][
                        "minimum_preload_free_vram_bytes"
                    ],
                ),
            },
            "output_storage": {
                "minimum_free_bytes": config["resource_limits"][
                    "minimum_output_free_bytes"
                ],
                "preflight_passed": True,
                "prepublication_passed": True,
                "preflight": output_observation("preflight"),
                "prepublication": output_observation("prepublication"),
                "wall_measurement_scope": (
                    "through-score-fsync-before-runtime-receipt"
                ),
                "final_wall_limit_seconds": config["resource_limits"][
                    "maximum_invocation_wall_seconds"
                ],
                "final_wall_limit_passed": True,
            },
            "post_load_resource": resource_observation(
                "post-load", post_load_audit
            ),
            "post_score_resource": resource_observation(
                "post-score", post_score_audit
            ),
            "metrics": {
                "load_seconds": 1.0,
                "wall_seconds": 2.0,
                "process_max_rss_bytes": 2_500_000_000,
                "peak_allocated_bytes": 2_100_000_000,
                "peak_reserved_bytes": 2_200_000_000,
                "candidate_forward_count": topology["candidate_count"],
                "forward_seconds": [0.1] * topology["candidate_count"],
                "aggregate_forward_seconds": sum(
                    [0.1] * topology["candidate_count"]
                ),
                "forwarded_token_count": topology["forwarded_token_count"],
                "predicted_token_count": topology["predicted_token_count"],
                "continuation_token_count": topology[
                    "continuation_token_count"
                ],
                "maximum_full_token_count": topology[
                    "maximum_full_token_count"
                ],
                "math_sdpa_forward_count": topology["candidate_count"],
                "autocast_disabled_forward_count": topology[
                    "candidate_count"
                ],
            },
            "score": binding,
        }
    if profile is V1_SCORING_PROFILE:
        trace = []
        for item in tokenizer_audit["items"]:
            for form in item["forms"]:
                for candidate_index, candidate in enumerate(form["candidates"]):
                    trace.append(
                        {
                            "item_id": str(item["item_id"]),
                            "form_id": str(form["form_id"]),
                            "candidate_index": candidate_index,
                            "pole": str(candidate["pole"]),
                        }
                    )
        mode = config["measurement_reliability"]["attempt_execution_modes"][attempt]
        if mode == "reverse":
            trace.reverse()
        receipt_body["execution_schedule"] = {
            "profile_id": profile.profile_id,
            "mode": mode,
            "candidate_count": len(trace),
            "trace_sha256": canonical_json_sha256(trace),
            "canonical_serialization": True,
        }
    return receipt_with_self_hash(receipt_body)


def _repeat_fixture():
    config, registry, audit, score = _small_score_fixture()
    score_bytes = pretty_json_bytes(score)
    receipt_a = _receipt(
        score,
        score_bytes,
        "a",
        config=config,
        tokenizer_audit=audit,
        process_id=101,
    )
    receipt_b = _receipt(
        score,
        score_bytes,
        "b",
        config=config,
        tokenizer_audit=audit,
        process_id=102,
    )
    return config, registry, audit, score, score_bytes, receipt_a, receipt_b


def _v1_repeat_fixture():
    config, registry, audit, score = _small_score_fixture(
        base_config=_v1_config()
    )
    score_bytes = pretty_json_bytes(score)
    receipt_a = _receipt(
        score,
        score_bytes,
        "a",
        config=config,
        tokenizer_audit=audit,
        process_id=201,
    )
    receipt_b = _receipt(
        score,
        score_bytes,
        "b",
        config=config,
        tokenizer_audit=audit,
        process_id=202,
    )
    return config, registry, audit, score, score_bytes, receipt_a, receipt_b


def test_v1_repeat_binds_canonical_and_reverse_execution_schedules() -> None:
    config, registry, audit, score, score_bytes, receipt_a, receipt_b = (
        _v1_repeat_fixture()
    )

    result = verify_scoring_repeat(
        score_a=score,
        score_a_bytes=score_bytes,
        receipt_a=receipt_a,
        receipt_a_bytes=pretty_json_bytes(receipt_a),
        resource_audit_a=_resource_audit_fixture("a"),
        resource_audit_a_bytes=pretty_json_bytes(_resource_audit_fixture("a")),
        score_b=deepcopy(score),
        score_b_bytes=score_bytes,
        receipt_b=receipt_b,
        receipt_b_bytes=pretty_json_bytes(receipt_b),
        resource_audit_b=_resource_audit_fixture("b"),
        resource_audit_b_bytes=pretty_json_bytes(_resource_audit_fixture("b")),
        config=config,
        registry=registry,
        tokenizer_audit=audit,
        expected_git_head="b" * 40,
    )

    assert result["status"] == "equal"
    assert result["profile_id"] == config["measurement_reliability"]["profile_id"]
    assert result["execution_modes"] == {"a": "canonical", "b": "reverse"}
    assert receipt_a["execution_schedule"]["trace_sha256"] != receipt_b[
        "execution_schedule"
    ]["trace_sha256"]
    assert receipt_a["run_id"] == receipt_b["run_id"]


@pytest.mark.parametrize(
    ("attempt", "field", "value"),
    [
        ("a", "mode", "reverse"),
        ("b", "mode", "canonical"),
        ("b", "trace_sha256", "0" * 64),
        ("a", "profile_id", "development-v0"),
        ("a", "candidate_count", 1),
        ("a", "canonical_serialization", False),
    ],
)
def test_v1_receipt_rejects_forged_execution_schedule(
    attempt: str,
    field: str,
    value: object,
) -> None:
    config, registry, audit, _score, _score_bytes, receipt_a, receipt_b = (
        _v1_repeat_fixture()
    )
    changed = deepcopy(receipt_a if attempt == "a" else receipt_b)
    changed["execution_schedule"][field] = value
    changed = receipt_with_self_hash(changed)

    assert any(
        "execution schedule" in error
        for error in validate_complete_receipt(
            changed,
            config,
            tokenizer_audit=audit,
            registry=registry,
        )
    )


def test_v1_schedule_is_derived_from_registry_not_reordered_audit() -> None:
    config, registry, audit, score, score_bytes, receipt_a, receipt_b = (
        _v1_repeat_fixture()
    )
    forged_audit = deepcopy(audit)
    forged_audit["items"][0]["forms"][0]["candidates"].reverse()
    forged_audit["output_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in forged_audit.items()
            if key != "output_sha256"
        }
    )

    with pytest.raises(ScoringRunError, match="frozen accepted object"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=pretty_json_bytes(receipt_a),
            resource_audit_a=_resource_audit_fixture("a"),
            resource_audit_a_bytes=pretty_json_bytes(
                _resource_audit_fixture("a")
            ),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=receipt_b,
            receipt_b_bytes=pretty_json_bytes(receipt_b),
            resource_audit_b=_resource_audit_fixture("b"),
            resource_audit_b_bytes=pretty_json_bytes(
                _resource_audit_fixture("b")
            ),
            config=config,
            registry=registry,
            tokenizer_audit=forged_audit,
            expected_git_head="b" * 40,
        )


def _verify_with_receipt_a(
    receipt_a: dict,
    *,
    resource_audit_a: dict | None = None,
    resource_audit_a_bytes: bytes | None = None,
) -> dict:
    config, registry, audit, score, score_bytes, _, receipt_b = _repeat_fixture()
    supplied = resource_audit_a or _resource_audit_fixture("a")
    supplied_bytes = resource_audit_a_bytes or pretty_json_bytes(supplied)
    return verify_scoring_repeat(
        score_a=score,
        score_a_bytes=score_bytes,
        receipt_a=receipt_a,
        receipt_a_bytes=pretty_json_bytes(receipt_a),
        resource_audit_a=supplied,
        resource_audit_a_bytes=supplied_bytes,
        score_b=deepcopy(score),
        score_b_bytes=score_bytes,
        receipt_b=receipt_b,
        receipt_b_bytes=pretty_json_bytes(receipt_b),
        resource_audit_b=_resource_audit_fixture("b"),
        resource_audit_b_bytes=pretty_json_bytes(_resource_audit_fixture("b")),
        config=config,
        registry=registry,
        tokenizer_audit=audit,
        expected_git_head="b" * 40,
    )


def _verify_with_receipt_b(
    receipt_b: dict,
    *,
    resource_audit_b: dict,
    resource_audit_b_bytes: bytes,
) -> dict:
    config, registry, audit, score, score_bytes, receipt_a, _ = _repeat_fixture()
    return verify_scoring_repeat(
        score_a=score,
        score_a_bytes=score_bytes,
        receipt_a=receipt_a,
        receipt_a_bytes=pretty_json_bytes(receipt_a),
        resource_audit_a=_resource_audit_fixture("a"),
        resource_audit_a_bytes=pretty_json_bytes(_resource_audit_fixture("a")),
        score_b=deepcopy(score),
        score_b_bytes=score_bytes,
        receipt_b=receipt_b,
        receipt_b_bytes=pretty_json_bytes(receipt_b),
        resource_audit_b=resource_audit_b,
        resource_audit_b_bytes=resource_audit_b_bytes,
        config=config,
        registry=registry,
        tokenizer_audit=audit,
        expected_git_head="b" * 40,
    )


def test_repeat_verifier_requires_exact_score_bytes() -> None:
    (
        config,
        registry,
        audit,
        score,
        score_bytes,
        receipt_a,
        receipt_b,
    ) = _repeat_fixture()
    receipt_a_bytes = pretty_json_bytes(receipt_a)
    receipt_b_bytes = pretty_json_bytes(receipt_b)

    result = verify_scoring_repeat(
        score_a=score,
        score_a_bytes=score_bytes,
        receipt_a=receipt_a,
        receipt_a_bytes=receipt_a_bytes,
        score_b=deepcopy(score),
        score_b_bytes=score_bytes,
        receipt_b=receipt_b,
        receipt_b_bytes=receipt_b_bytes,
        config=config,
        registry=registry,
        tokenizer_audit=audit,
        expected_git_head="b" * 40,
        **_repeat_audit_kwargs(),
    )

    assert result["status"] == "equal"
    assert result["comparison_sha256"] == canonical_json_sha256(
        {key: value for key, value in result.items() if key != "comparison_sha256"}
    )

    _, _, _, changed = _small_score_fixture(left_first_logprob=-0.100001)
    changed_bytes = pretty_json_bytes(changed)
    changed_receipt = _receipt(
        changed,
        changed_bytes,
        "b",
        config=config,
        tokenizer_audit=audit,
        process_id=102,
    )
    changed_receipt_bytes = pretty_json_bytes(changed_receipt)
    with pytest.raises(ScoringRunError, match="determinism-failed"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=receipt_a_bytes,
            score_b=changed,
            score_b_bytes=changed_bytes,
            receipt_b=changed_receipt,
            receipt_b_bytes=changed_receipt_bytes,
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
            **_repeat_audit_kwargs(),
        )


def test_repeat_verifier_binds_each_raw_resource_audit() -> None:
    (
        config,
        registry,
        audit,
        score,
        score_bytes,
        receipt_a,
        receipt_b,
    ) = _repeat_fixture()
    mismatched_audit = _resource_audit_fixture("a")
    mismatched_audit["captured_at"] = "2026-08-20T00:00:09+00:00"

    with pytest.raises(ScoringRunError, match="bind its supplied resource audit"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=pretty_json_bytes(receipt_a),
            resource_audit_a=mismatched_audit,
            resource_audit_a_bytes=pretty_json_bytes(mismatched_audit),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=receipt_b,
            receipt_b_bytes=pretty_json_bytes(receipt_b),
            resource_audit_b=_resource_audit_fixture("b"),
            resource_audit_b_bytes=pretty_json_bytes(
                _resource_audit_fixture("b")
            ),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
        )


def test_repeat_verifier_rejects_semantically_malformed_resource_audit() -> None:
    config, registry, audit, score, score_bytes, receipt_a, receipt_b = (
        _repeat_fixture()
    )
    malformed = _resource_audit_fixture("a")
    malformed.pop("schema_version")
    malformed_bytes = pretty_json_bytes(malformed)
    changed_receipt = deepcopy(receipt_a)
    changed_receipt["resource_preflight"]["resource_audit_sha256"] = (
        hashlib.sha256(malformed_bytes).hexdigest()
    )
    changed_receipt = receipt_with_self_hash(changed_receipt)

    with pytest.raises(ScoringRunError, match="fields are not exact"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=changed_receipt,
            receipt_a_bytes=pretty_json_bytes(changed_receipt),
            resource_audit_a=malformed,
            resource_audit_a_bytes=malformed_bytes,
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=receipt_b,
            receipt_b_bytes=pretty_json_bytes(receipt_b),
            resource_audit_b=_resource_audit_fixture("b"),
            resource_audit_b_bytes=pretty_json_bytes(
                _resource_audit_fixture("b")
            ),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
        )


def test_repeat_verifier_rejects_coherently_rehashed_embedded_resource_audit() -> None:
    config, registry, audit, score, score_bytes, receipt_a, receipt_b = (
        _repeat_fixture()
    )
    changed_receipt = deepcopy(receipt_a)
    live = changed_receipt["resource_preflight"]["live_resource_audit"]
    live["network_access_performed"] = True
    changed_receipt["resource_preflight"][
        "live_resource_audit_semantic_sha256"
    ] = canonical_json_sha256(live)
    changed_receipt = receipt_with_self_hash(changed_receipt)

    with pytest.raises(ScoringRunError, match="network policy is invalid"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=changed_receipt,
            receipt_a_bytes=pretty_json_bytes(changed_receipt),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=receipt_b,
            receipt_b_bytes=pretty_json_bytes(receipt_b),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
            **_repeat_audit_kwargs(),
        )


def test_repeat_verifier_binds_resource_validation_to_the_supplied_audit() -> None:
    config, _, _, _, _, receipt_a, _ = _repeat_fixture()
    changed = deepcopy(receipt_a)
    preflight = changed["resource_preflight"]
    preflight["post_import_resource_validation"] = _resource_validation_fixture(
        preflight["live_resource_audit"],
        preflight["post_import_resource_audit"],
        config,
        minimum_free_vram_bytes=config["resource_limits"][
            "minimum_preload_free_vram_bytes"
        ],
    )
    changed = receipt_with_self_hash(changed)

    with pytest.raises(ScoringRunError, match="derived resource validation mismatch"):
        _verify_with_receipt_a(changed)

    changed = deepcopy(receipt_a)
    changed["resource_preflight"]["execution_resource_validation"][
        "ram_threshold_enforced"
    ] = 0
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="derived resource validation mismatch"):
        _verify_with_receipt_a(changed)


def test_repeat_verifier_rejects_resource_chronology_platform_and_hash_forgery() -> None:
    _, _, _, _, _, receipt_a, _ = _repeat_fixture()

    changed = deepcopy(receipt_a)
    live = changed["resource_preflight"]["live_resource_audit"]
    live["captured_at"] = "2026-08-20T00:00:02.500000+00:00"
    changed["resource_preflight"]["live_resource_audit_captured_at"] = live[
        "captured_at"
    ]
    changed["resource_preflight"]["live_resource_audit_semantic_sha256"] = (
        canonical_json_sha256(live)
    )
    changed["resource_preflight"]["live_resource_audit_sha256"] = hashlib.sha256(
        pretty_json_bytes(live)
    ).hexdigest()
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="chronology is invalid"):
        _verify_with_receipt_a(changed)

    changed = deepcopy(receipt_a)
    preflight = changed["resource_preflight"]
    post_import = preflight["post_import_resource_audit"]
    post_import["captured_at"] = preflight["live_resource_audit_captured_at"]
    preflight["post_import_resource_audit_captured_at"] = post_import["captured_at"]
    preflight["post_import_resource_audit_semantic_sha256"] = canonical_json_sha256(
        post_import
    )
    preflight["post_import_resource_audit_sha256"] = hashlib.sha256(
        pretty_json_bytes(post_import)
    ).hexdigest()
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="chronology is invalid"):
        _verify_with_receipt_a(changed)

    changed = deepcopy(receipt_a)
    live = changed["resource_preflight"]["live_resource_audit"]
    live["platform"]["hostname"] = "other-host"
    changed["resource_preflight"]["live_resource_audit_semantic_sha256"] = (
        canonical_json_sha256(live)
    )
    changed["resource_preflight"]["live_resource_audit_sha256"] = hashlib.sha256(
        pretty_json_bytes(live)
    ).hexdigest()
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="platform identity drifted: hostname"):
        _verify_with_receipt_a(changed)

    changed = deepcopy(receipt_a)
    changed["resource_preflight"]["live_resource_audit_sha256"] = "0" * 64
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="resource-audit binding is invalid"):
        _verify_with_receipt_a(changed)


def test_repeat_verifier_rejects_resource_numeric_type_and_path_alias_forgery() -> None:
    _, _, _, _, _, receipt_a, _ = _repeat_fixture()

    changed = deepcopy(receipt_a)
    live = changed["resource_preflight"]["live_resource_audit"]
    live["torch_runtime"]["devices"][0]["free_memory_bytes"] = (
        live["torch_runtime"]["devices"][0]["total_memory_bytes"] + 1
    )
    changed["resource_preflight"]["live_resource_audit_semantic_sha256"] = (
        canonical_json_sha256(live)
    )
    changed["resource_preflight"]["live_resource_audit_sha256"] = hashlib.sha256(
        pretty_json_bytes(live)
    ).hexdigest()
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="CUDA device identity is invalid"):
        _verify_with_receipt_a(changed)

    changed = deepcopy(receipt_a)
    aliased = changed["resource_preflight"]["audit_disk_path"] + os.sep + "."
    changed["resource_preflight"]["audit_disk_path"] = aliased
    changed["resource_preflight"]["cache_storage_path"] = aliased
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="cache-bound disk evidence is invalid"):
        _verify_with_receipt_a(changed)

    changed = deepcopy(receipt_a)
    live = changed["resource_preflight"]["live_resource_audit"]
    live["disk"]["path"] = str((ROOT / "artifacts" / "local" / "other").resolve())
    changed["resource_preflight"]["live_resource_audit_semantic_sha256"] = (
        canonical_json_sha256(live)
    )
    changed["resource_preflight"]["live_resource_audit_sha256"] = hashlib.sha256(
        pretty_json_bytes(live)
    ).hexdigest()
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="resource-audit binding is invalid"):
        _verify_with_receipt_a(changed)

    changed_audit = _resource_audit_fixture("a")
    changed_audit["schema_version"] = True
    changed_audit_bytes = pretty_json_bytes(changed_audit)
    changed = deepcopy(receipt_a)
    changed["resource_preflight"]["resource_audit_sha256"] = hashlib.sha256(
        changed_audit_bytes
    ).hexdigest()
    changed = receipt_with_self_hash(changed)
    with pytest.raises(ScoringRunError, match="schema, timestamp, or network policy"):
        _verify_with_receipt_a(
            changed,
            resource_audit_a=changed_audit,
            resource_audit_a_bytes=changed_audit_bytes,
        )


def test_repeat_verifier_accepts_windows_crlf_resource_audit_transport() -> None:
    _, _, _, _, _, receipt_a, _ = _repeat_fixture()
    changed = deepcopy(receipt_a)
    live = changed["resource_preflight"]["live_resource_audit"]
    crlf_payload = pretty_json_bytes(live).replace(b"\n", b"\r\n")
    changed["resource_preflight"]["live_resource_audit_sha256"] = hashlib.sha256(
        crlf_payload
    ).hexdigest()
    changed = receipt_with_self_hash(changed)

    assert _verify_with_receipt_a(changed)["status"] == "equal"


def test_repeat_verifier_requires_one_static_host_identity() -> None:
    config, _, _, _, _, _, receipt_b = _repeat_fixture()
    changed = deepcopy(receipt_b)
    supplied = _resource_audit_fixture("b")

    def drift_host(audit: dict) -> None:
        audit["platform"]["hostname"] = "other-host"
        audit["python"]["executable"] = str(
            (ROOT / "other-python" / "python.exe").resolve()
        )
        audit["environment"]["CUDA_VISIBLE_DEVICES"] = "0"
        audit["nvidia"]["gpus"][0]["uuid"] = "GPU-other"
        audit["nvidia"]["gpus"][0]["driver_version"] = "999.0"

    drift_host(supplied)
    supplied_bytes = pretty_json_bytes(supplied)
    preflight = changed["resource_preflight"]
    preflight["resource_audit_sha256"] = hashlib.sha256(
        supplied_bytes
    ).hexdigest()
    live = preflight["live_resource_audit"]
    post_import = preflight["post_import_resource_audit"]
    for prefix, embedded in (("live", live), ("post_import", post_import)):
        drift_host(embedded)
        preflight[f"{prefix}_resource_audit_semantic_sha256"] = (
            canonical_json_sha256(embedded)
        )
        preflight[f"{prefix}_resource_audit_sha256"] = hashlib.sha256(
            pretty_json_bytes(embedded)
        ).hexdigest()
    preload_minimum = config["resource_limits"]["minimum_preload_free_vram_bytes"]
    preflight["execution_resource_validation"] = _resource_validation_fixture(
        supplied,
        live,
        config,
        minimum_free_vram_bytes=preload_minimum,
    )
    preflight["post_import_resource_validation"] = _resource_validation_fixture(
        supplied,
        post_import,
        config,
        minimum_free_vram_bytes=preload_minimum,
    )
    postload_minimum = config["resource_limits"][
        "minimum_postload_global_free_vram_bytes"
    ]
    for key in ("post_load_resource", "post_score_resource"):
        observation = changed[key]
        embedded = observation["audit"]
        drift_host(embedded)
        observation["audit_semantic_sha256"] = canonical_json_sha256(embedded)
        observation["audit_sha256"] = hashlib.sha256(
            pretty_json_bytes(embedded)
        ).hexdigest()
        observation["conservative_vram"] = _conservative_vram_fixture(embedded)
        observation["execution_resource_validation"] = _resource_validation_fixture(
            post_import,
            embedded,
            config,
            minimum_free_vram_bytes=postload_minimum,
        )
    changed = receipt_with_self_hash(changed)

    with pytest.raises(ScoringRunError, match="one static host identity"):
        _verify_with_receipt_b(
            changed,
            resource_audit_b=supplied,
            resource_audit_b_bytes=supplied_bytes,
        )


def test_repeat_verifier_requires_trusted_head_and_ordered_attempts() -> None:
    config, registry, audit, score, score_bytes, receipt_a, receipt_b = (
        _repeat_fixture()
    )
    with pytest.raises(ScoringRunError, match="trusted execution head"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=pretty_json_bytes(receipt_a),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=receipt_b,
            receipt_b_bytes=pretty_json_bytes(receipt_b),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="c" * 40,
            **_repeat_audit_kwargs(),
        )

    swapped_a = receipt_with_self_hash({**receipt_a, "attempt": "b"})
    swapped_b = receipt_with_self_hash({**receipt_b, "attempt": "a"})
    with pytest.raises(ScoringRunError, match="exact attempts a and b"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=swapped_a,
            receipt_a_bytes=pretty_json_bytes(swapped_a),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=swapped_b,
            receipt_b_bytes=pretty_json_bytes(swapped_b),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
            **_repeat_audit_kwargs(),
        )

    overlapping_audit = _resource_audit_fixture(
        "b", captured_at="2026-08-20T00:00:02.500000+00:00"
    )
    overlapping_bytes = pretty_json_bytes(overlapping_audit)
    overlapping_receipt = deepcopy(receipt_b)
    overlapping_receipt["resource_preflight"]["resource_audit_sha256"] = (
        hashlib.sha256(overlapping_bytes).hexdigest()
    )
    overlapping_receipt["resource_preflight"][
        "resource_audit_captured_at"
    ] = overlapping_audit["captured_at"]
    overlapping_receipt["resource_preflight"]["resource_audit_age_seconds"] = 2.75
    overlapping_receipt = receipt_with_self_hash(overlapping_receipt)
    with pytest.raises(ScoringRunError, match="ordered fresh audit/process"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=pretty_json_bytes(receipt_a),
            resource_audit_a=_resource_audit_fixture("a"),
            resource_audit_a_bytes=pretty_json_bytes(
                _resource_audit_fixture("a")
            ),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=overlapping_receipt,
            receipt_b_bytes=pretty_json_bytes(overlapping_receipt),
            resource_audit_b=overlapping_audit,
            resource_audit_b_bytes=overlapping_bytes,
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
        )


def test_score_validation_rejects_absolute_path_even_when_rehashed() -> None:
    config, registry, audit, score = _small_score_fixture()
    changed = deepcopy(score)
    changed["contract"]["leak"] = r"C:\private\cache"
    changed["output_sha256"] = canonical_json_sha256(
        {key: value for key, value in changed.items() if key != "output_sha256"}
    )

    assert "score artifact contains an absolute local path" in validate_score_artifact(
        changed,
        config,
        registry=registry,
        tokenizer_audit=audit,
    )


@pytest.mark.parametrize(
    "mutation",
    ("pairwise", "aggregate", "registry", "prompt", "continuation"),
)
def test_score_validation_recomputes_every_semantic_layer(mutation: str) -> None:
    config, registry, audit, score = _small_score_fixture()
    changed = deepcopy(score)
    form = changed["items"][0]["forms"][0]
    if mutation == "pairwise":
        form["pairwise"]["total_logprob_margin"] = 999.0
    elif mutation == "aggregate":
        changed["items"][0]["aggregate"]["mean_total_logprob_margin"] = -999.0
    elif mutation == "registry":
        changed["items"][0]["domain"] = "forged-domain"
    elif mutation == "prompt":
        for candidate in form["candidates"]:
            candidate["prompt_token_ids"] = [8, 9]
    else:
        form["candidates"][0]["continuation_token_ids"] = [8, 9]
    changed["output_sha256"] = canonical_json_sha256(
        {key: value for key, value in changed.items() if key != "output_sha256"}
    )

    assert validate_score_artifact(
        changed,
        config,
        registry=registry,
        tokenizer_audit=audit,
    )


@pytest.mark.parametrize(
    ("section", "key", "value", "message"),
    [
        ("model_validation", "attention_implementation", "eager", "model validation"),
        (
            "tokenizer_validation",
            "native_prefix_probe_equal",
            False,
            "tokenizer validation",
        ),
        ("metrics", "load_seconds", 999.0, "load time exceeds wall time"),
    ],
)
def test_complete_receipt_rejects_coherent_nested_forgery(
    section: str,
    key: str,
    value: object,
    message: str,
) -> None:
    config, _, audit, score, score_bytes, receipt, _ = _repeat_fixture()
    changed = deepcopy(receipt)
    changed[section][key] = value
    changed = receipt_with_self_hash(changed)

    assert any(
        message in error
        for error in validate_complete_receipt(
            changed,
            config,
            tokenizer_audit=audit,
        )
    )


def test_repeat_requires_fresh_process_and_resource_audit() -> None:
    (
        config,
        registry,
        audit,
        score,
        score_bytes,
        receipt_a,
        receipt_b,
    ) = _repeat_fixture()
    same_process = receipt_with_self_hash(
        {**receipt_b, "process_id": receipt_a["process_id"]}
    )
    with pytest.raises(ScoringRunError, match="fresh processes"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=pretty_json_bytes(receipt_a),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=same_process,
            receipt_b_bytes=pretty_json_bytes(same_process),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
            **_repeat_audit_kwargs(),
        )

    reused_audit = deepcopy(receipt_b)
    reused_audit["resource_preflight"] = deepcopy(
        receipt_a["resource_preflight"]
    )
    reused_audit = receipt_with_self_hash(reused_audit)
    shared_resource_audit = _resource_audit_fixture("a")
    shared_resource_audit_bytes = pretty_json_bytes(shared_resource_audit)
    with pytest.raises(ScoringRunError, match="resource-audit age"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=score_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=pretty_json_bytes(receipt_a),
            score_b=deepcopy(score),
            score_b_bytes=score_bytes,
            receipt_b=reused_audit,
            receipt_b_bytes=pretty_json_bytes(reused_audit),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
            resource_audit_a=shared_resource_audit,
            resource_audit_a_bytes=shared_resource_audit_bytes,
            resource_audit_b=shared_resource_audit,
            resource_audit_b_bytes=shared_resource_audit_bytes,
        )


def test_repeat_rejects_noncanonical_published_bytes() -> None:
    (
        config,
        registry,
        audit,
        score,
        score_bytes,
        receipt_a,
        receipt_b,
    ) = _repeat_fixture()
    compact = json.dumps(score, sort_keys=True).encode("utf-8")
    with pytest.raises(ScoringRunError, match="canonical published form"):
        verify_scoring_repeat(
            score_a=score,
            score_a_bytes=compact,
            receipt_a=receipt_a,
            receipt_a_bytes=pretty_json_bytes(receipt_a),
            score_b=deepcopy(score),
            score_b_bytes=compact,
            receipt_b=receipt_b,
            receipt_b_bytes=pretty_json_bytes(receipt_b),
            config=config,
            registry=registry,
            tokenizer_audit=audit,
            expected_git_head="b" * 40,
            **_repeat_audit_kwargs(),
        )


def test_json_loaders_reject_duplicate_keys(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"value": 1, "value": 2}', encoding="utf-8")
    with pytest.raises(ScoringRunError, match="duplicate JSON key"):
        load_json_object(duplicate, "duplicate fixture")

    config = tmp_path / "config.json"
    raw = CONFIG.read_text(encoding="utf-8")
    config.write_text(
        raw.replace(
            '"schema_version": 1,',
            '"schema_version": 1,\n  "schema_version": 1,',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScoringRunError, match="duplicate JSON key"):
        load_scoring_config(config)


def test_create_only_json_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    create_only_json(path, {"status": "first"})

    with pytest.raises(ScoringRunError, match="refusing to overwrite"):
        create_only_json(path, {"status": "second"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "first"}


def test_repeat_cli_rejects_same_file_and_hardlink_aliases() -> None:
    module = _verify_cli()
    with tempfile.TemporaryDirectory(dir=module.scoring_cli.LOCAL_OUTPUT_ROOT) as raw:
        first = Path(raw) / "first.json"
        alias = Path(raw) / "alias.json"
        first.write_text("{}", encoding="utf-8")
        os.link(first, alias)

        with pytest.raises(ScoringRunError, match="must be distinct files"):
            module._require_distinct_inputs(
                (("score A", first), ("score B", alias))
            )


def test_repeat_cli_rebinds_clean_exact_head_before_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _verify_cli()
    heads = iter(("a" * 40, "b" * 40))

    def fake_git(*arguments: str) -> str:
        if arguments == ("rev-parse", "HEAD"):
            return next(heads)
        if arguments == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        raise AssertionError(arguments)

    monkeypatch.setattr(module.tokenizer_cli, "_git", fake_git)
    captured = module._require_clean_exact_head()
    with pytest.raises(ScoringRunError, match="HEAD changed"):
        module._require_clean_exact_head(captured)


def test_resident_resource_check_forwards_frozen_postload_vram_floor() -> None:
    module = _score_cli()
    config = _config()
    audit = _resource_audit_fixture(
        "a", captured_at=_attempt_times("a")["post_load"]
    )
    observed_minimum: list[int] = []

    class FakeBenchmark:
        @staticmethod
        def _capture_live_resource_audit(_path):
            return audit, hashlib.sha256(pretty_json_bytes(audit)).hexdigest()

        @staticmethod
        def _resource_audit_age_seconds(_audit):
            return 0.0

        @staticmethod
        def _validate_execution_resources(
            _reference,
            _observed,
            _artifact,
            **kwargs,
        ):
            observed_minimum.append(kwargs["minimum_free_vram_bytes"])
            return _resource_validation_fixture(
                audit,
                audit,
                config,
                minimum_free_vram_bytes=kwargs["minimum_free_vram_bytes"],
            )

        @staticmethod
        def _conservative_vram(value):
            return _conservative_vram_fixture(value)

    state = {
        "preflight": {
            "post_import_resource_audit": audit,
            "cache_storage_path": audit["disk"]["path"],
        }
    }
    result = module._resident_resource_check(
        FakeBenchmark,
        state,
        {"weight_size_bytes": config["artifact"]["model_safetensors_size_bytes"]},
        config,
        label="post-load",
    )

    minimum = config["resource_limits"][
        "minimum_postload_global_free_vram_bytes"
    ]
    assert observed_minimum == [minimum]
    assert result["execution_resource_validation"][
        "minimum_free_vram_bytes"
    ] == minimum
    assert "pending_resident_resource_check" not in state
    assert set(result) == {
        "label",
        "audit_sha256",
        "audit_semantic_sha256",
        "captured_at",
        "age_seconds",
        "conservative_vram",
        "execution_resource_validation",
        "audit",
    }


def test_failed_resident_resource_check_preserves_exact_audit_in_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    import benchmark_model

    config = _config()
    minimum = config["resource_limits"][
        "minimum_postload_global_free_vram_bytes"
    ]
    reference = _resource_audit_fixture(
        "a",
        captured_at=_attempt_times("a")["post_import"],
    )
    observed = _resource_audit_fixture(
        "a",
        captured_at=_attempt_times("a")["post_score"],
        torch_free_bytes=minimum - 1,
        nvidia_free_mib=4096,
    )
    observed_sha256 = hashlib.sha256(pretty_json_bytes(observed)).hexdigest()

    class FakeBenchmark:
        @staticmethod
        def _capture_live_resource_audit(_path):
            return observed, observed_sha256

        @staticmethod
        def _resource_audit_age_seconds(_audit):
            return 0.25

        _validate_execution_resources = staticmethod(
            benchmark_model._validate_execution_resources
        )
        _conservative_vram = staticmethod(benchmark_model._conservative_vram)

    state = {
        "preflight": {
            "post_import_resource_audit": reference,
            "cache_storage_path": observed["disk"]["path"],
        }
    }
    error: RuntimeError
    with pytest.raises(
        RuntimeError, match="free VRAM is below the model-load safety threshold"
    ) as caught:
        module._resident_resource_check(
            FakeBenchmark,
            state,
            {
                "weight_size_bytes": config["artifact"][
                    "model_safetensors_size_bytes"
                ]
            },
            config,
            label="post-score",
        )
    error = caught.value

    pending = state["pending_resident_resource_check"]
    assert pending == {
        "label": "post-score",
        "audit_sha256": observed_sha256,
        "audit_semantic_sha256": canonical_json_sha256(observed),
        "captured_at": observed["captured_at"],
        "age_seconds": 0.25,
        "minimum_free_vram_bytes": minimum,
        "conservative_vram": benchmark_model._conservative_vram(observed),
        "audit": observed,
    }

    args = argparse.Namespace(attempt="a")
    args._failure_context = {"started_at": _attempt_times("a")["started"]}
    args._resource_state = state
    args._failure_stage = "post-score-resource-check"
    monkeypatch.setattr(module.tokenizer_cli, "_git", lambda *_args: "b" * 40)
    receipt = module._failure_receipt(args, error)

    assert receipt["status"] == "failed"
    assert receipt["failure_stage"] == "post-score-resource-check"
    assert receipt["failure_context"]["failed_resident_resource_check"] == pending
    assert receipt["scientific_claim_authorized"] is False
    assert receipt["score"]["valid_score_published"] is False


def test_failed_resident_resource_enrichment_does_not_mask_validation_error() -> None:
    module = _score_cli()
    config = _config()
    audit = _resource_audit_fixture(
        "a", captured_at=_attempt_times("a")["post_score"]
    )

    class FakeBenchmark:
        @staticmethod
        def _capture_live_resource_audit(_path):
            return audit, "a" * 64

        @staticmethod
        def _resource_audit_age_seconds(_audit):
            return 0.0

        @staticmethod
        def _validate_execution_resources(*_args, **_kwargs):
            raise RuntimeError("validation sentinel")

        @staticmethod
        def _conservative_vram(_audit):
            raise ValueError("observation sentinel")

    state = {
        "preflight": {
            "post_import_resource_audit": audit,
            "cache_storage_path": audit["disk"]["path"],
        }
    }
    with pytest.raises(RuntimeError, match="validation sentinel"):
        module._resident_resource_check(
            FakeBenchmark,
            state,
            {
                "weight_size_bytes": config["artifact"][
                    "model_safetensors_size_bytes"
                ]
            },
            config,
            label="post-score",
        )

    pending = state["pending_resident_resource_check"]
    assert pending["audit"] == audit
    assert pending["conservative_vram_error"] == {
        "error_type": "ValueError",
        "error": "observation sentinel",
    }


def test_scoring_preflight_forwards_frozen_preload_vram_floor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    import benchmark_model

    config = _config()
    audit = _resource_audit_fixture("a")
    live = _resource_audit_fixture(
        "a", captured_at=_attempt_times("a")["live"]
    )
    post_import = _resource_audit_fixture(
        "a", captured_at=_attempt_times("a")["post_import"]
    )
    observed_minimums: list[int] = []
    base = {
        "audit_disk_free_bytes": 10_000_000_000,
        "cache_storage_path": str(tmp_path.resolve()),
    }

    monkeypatch.setattr(
        benchmark_model,
        "_resource_preflight",
        lambda _args, _artifact: dict(base),
    )

    def fake_live(_args, _artifact, preflight, *, minimum_free_vram_bytes):
        observed_minimums.append(minimum_free_vram_bytes)
        return {
            **preflight,
            "live_resource_audit": live,
            "execution_resource_validation": {},
        }

    def fake_post(_args, _artifact, preflight, *, minimum_free_vram_bytes):
        observed_minimums.append(minimum_free_vram_bytes)
        return {
            **preflight,
            "post_import_resource_audit": post_import,
            "post_import_resource_validation": {},
        }

    monkeypatch.setattr(benchmark_model, "_live_execution_preflight", fake_live)
    monkeypatch.setattr(
        benchmark_model,
        "_post_import_resource_preflight",
        fake_post,
    )
    monkeypatch.setattr(
        benchmark_model,
        "_verify_parent_runtime",
        lambda *_args, **_kwargs: {"verified": True},
    )

    args = argparse.Namespace(
        resource_audit=tmp_path / "audit.json",
        cache_dir=tmp_path,
    )
    artifact = {
        "weight_size_bytes": config["artifact"]["model_safetensors_size_bytes"]
    }
    _, state = module._resource_preflight(args, artifact, config)
    state["before_deserialization"](object(), object())

    minimum = config["resource_limits"]["minimum_preload_free_vram_bytes"]
    assert observed_minimums == [minimum, minimum]


def test_output_pair_reservation_rolls_back_post_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    score = tmp_path / "score.json"
    runtime = tmp_path / "runtime.json"
    original_lstat = module.os.lstat
    failed = False

    def fail_once(path):
        nonlocal failed
        if Path(path) == score and not failed:
            try:
                original_lstat(score)
            except FileNotFoundError:
                pass
            else:
                failed = True
                raise OSError("injected post-open lstat failure")
        return original_lstat(path)

    monkeypatch.setattr(module.os, "lstat", fail_once)

    with pytest.raises(OSError, match="injected post-open"):
        module._OutputPairReservation(score, runtime)

    assert not os.path.lexists(score)
    assert not os.path.lexists(runtime)


def test_output_pair_reservation_reads_back_exact_written_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    score = tmp_path / "score.json"
    runtime = tmp_path / "runtime.json"
    reservation = module._OutputPairReservation(score, runtime)
    original_write = module.os.write
    corrupted = False

    def corrupt_once(descriptor: int, value) -> int:
        nonlocal corrupted
        payload = bytes(value)
        if not corrupted and payload:
            corrupted = True
            payload = bytes([payload[0] ^ 1]) + payload[1:]
        return original_write(descriptor, payload)

    monkeypatch.setattr(module.os, "write", corrupt_once)

    with pytest.raises(ScoringRunError, match="output bytes mismatch"):
        reservation.write_score({"status": "complete"})

    assert not os.path.lexists(score)
    assert not os.path.lexists(runtime)


def test_output_pair_failure_publication_removes_owned_score(tmp_path: Path) -> None:
    module = _score_cli()
    score = tmp_path / "score.json"
    runtime = tmp_path / "runtime.json"
    reservation = module._OutputPairReservation(score, runtime)
    reservation.write_score({"status": "complete"})

    reservation.publish_failure({"status": "failed"})

    assert not score.exists()
    assert json.loads(runtime.read_text(encoding="utf-8")) == {"status": "failed"}


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (TypeError("injected API drift"), 1),
        (KeyboardInterrupt(), 130),
        (SystemExit(7), 7),
    ],
)
def test_scoring_cli_preserves_unexpected_and_interrupted_failures(
    error: BaseException,
    expected_code: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_output:
        output_root = Path(raw_output)
        score = output_root / "score.json"
        runtime = output_root / "runtime.json"
        monkeypatch.setattr(
            module,
            "_execute",
            lambda _args: (_ for _ in ()).throw(error),
        )

        code = module.main(
            [
                "--artifact",
                "pythia-1b-deduped-main",
                "--prefix-policy",
                "none",
                "--execute",
                "--attempt",
                "a",
                "--output",
                str(score),
                "--runtime-output",
                str(runtime),
            ]
        )

        assert code == expected_code
        assert not score.exists()
        receipt = json.loads(runtime.read_text(encoding="utf-8"))
        assert receipt["status"] == "failed"
        assert receipt["error_type"] == type(error).__name__
        assert receipt["score"]["valid_score_published"] is False


def test_system_exit_after_reservation_publishes_failed_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_output:
        score = Path(raw_output) / "score.json"
        runtime = Path(raw_output) / "runtime.json"

        def fail_after_reservation(args: argparse.Namespace) -> None:
            args._output_reservation = module._OutputPairReservation(score, runtime)
            args._failure_stage = "heavy-job-lock"
            raise SystemExit(9)

        monkeypatch.setattr(module, "_execute", fail_after_reservation)
        code = module.main(
            [
                "--artifact",
                "pythia-1b-deduped-main",
                "--prefix-policy",
                "none",
                "--execute",
                "--attempt",
                "a",
                "--output",
                str(score),
                "--runtime-output",
                str(runtime),
            ]
        )

        assert code == 9
        assert not score.exists()
        receipt = json.loads(runtime.read_text(encoding="utf-8"))
        assert receipt["status"] == "failed"
        assert receipt["failure_stage"] == "heavy-job-lock"
        assert receipt["error_type"] == "SystemExit"


def test_written_complete_pair_can_be_replaced_by_failed_receipt() -> None:
    module = _score_cli()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_output:
        score = Path(raw_output) / "score.json"
        runtime = Path(raw_output) / "runtime.json"
        reservation = module._OutputPairReservation(score, runtime)
        reservation.write_score({"status": "complete"})
        reservation.write_runtime({"status": "complete"})
        args = argparse.Namespace(
            attempt="a",
            runtime_output=runtime,
            cache_dir=None,
            snapshot_path=None,
            _output_reservation=reservation,
            _failure_stage="output-commit",
        )

        module._preserve_failure_receipt(
            args, RuntimeError("injected commit or lock-release failure")
        )

        assert not score.exists()
        receipt = json.loads(runtime.read_text(encoding="utf-8"))
        assert receipt["status"] == "failed"
        assert receipt["failure_stage"] == "output-commit"


def test_lock_exit_failure_replaces_written_complete_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_output:
        score = Path(raw_output) / "score.json"
        runtime = Path(raw_output) / "runtime.json"

        def fail_on_lock_exit(args: argparse.Namespace) -> None:
            reservation = module._OutputPairReservation(score, runtime)
            args._output_reservation = reservation
            args._failure_stage = "heavy-job-lock"
            reservation.write_score({"status": "complete"})
            reservation.write_runtime({"status": "complete"})
            raise RuntimeError("injected RunLock.__exit__ failure")

        monkeypatch.setattr(module, "_execute", fail_on_lock_exit)
        code = module.main(
            [
                "--artifact",
                "pythia-1b-deduped-main",
                "--prefix-policy",
                "none",
                "--execute",
                "--attempt",
                "a",
                "--output",
                str(score),
                "--runtime-output",
                str(runtime),
            ]
        )

        assert code == 1
        assert not score.exists()
        receipt = json.loads(runtime.read_text(encoding="utf-8"))
        assert receipt["status"] == "failed"
        assert receipt["failure_stage"] == "heavy-job-lock"


def test_post_lock_wall_limit_prevents_output_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    score = tmp_path / "score.json"
    runtime = tmp_path / "runtime.json"
    reservation = module._OutputPairReservation(score, runtime)
    reservation.write_score({"status": "complete"})
    reservation.write_runtime({"status": "complete"})
    monkeypatch.setattr(module.time, "perf_counter", lambda: 901.0)

    with pytest.raises(ScoringRunError, match="during lock release"):
        module._commit_output_pair_after_lock(
            reservation,
            wall_start=0.0,
            maximum_wall_seconds=900.0,
        )
    reservation.rollback()

    assert not score.exists()
    assert not runtime.exists()


@pytest.mark.parametrize("phase", ["preflight", "prepublication"])
def test_output_storage_gate_rejects_low_disk(
    phase: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    config = _config()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_output:
        root = Path(raw_output)
        args = argparse.Namespace(
            output=root / "score.json",
            runtime_output=root / "runtime.json",
            cache_dir=None,
            snapshot_path=None,
        )
        monkeypatch.setattr(
            module.shutil,
            "disk_usage",
            lambda _path: SimpleNamespace(free=1),
        )

        with pytest.raises(ScoringRunError, match="below the frozen reserve"):
            module._output_storage_observation(args, config, phase=phase)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("snapshot", "snapshot changed"),
        ("git", "Git head or canonical inputs changed"),
        ("tokenizer", "accepted tokenizer audit changed"),
    ],
)
def test_final_integrity_rebind_rejects_each_mutable_input(
    mutation: str,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    snapshot_receipt = {"receipt_sha256": "1" * 64}
    git_binding = {"git_head": "b" * 40}
    payloads = {"model_manifest": b"manifest"}
    tokenizer_audit = {"output_sha256": "2" * 64}
    tokenizer_sha = "3" * 64
    monkeypatch.setattr(
        module,
        "verify_snapshot",
        lambda *_args: {
            "portable_receipt": (
                {"receipt_sha256": "9" * 64}
                if mutation == "snapshot"
                else snapshot_receipt
            )
        },
    )
    monkeypatch.setattr(
        module,
        "_bound_execution_inputs",
        lambda _profile: (
            ({"git_head": "c" * 40}, payloads)
            if mutation == "git"
            else (git_binding, payloads)
        ),
    )
    monkeypatch.setattr(
        module,
        "load_accepted_tokenizer_audit",
        lambda *_args: (
            ({"output_sha256": "8" * 64}, tokenizer_sha)
            if mutation == "tokenizer"
            else (tokenizer_audit, tokenizer_sha)
        ),
    )

    with pytest.raises(ScoringRunError, match=message):
        module._final_integrity_rebind(
            argparse.Namespace(
                snapshot_path=Path("snapshot"),
                cache_dir=Path("cache"),
            ),
            profile=scoring_profile(_config()),
            artifact={"id": "artifact"},
            snapshot_receipt=snapshot_receipt,
            git_binding=git_binding,
            input_payloads=payloads,
            tokenizer_audit_path=Path("tokenizer.json"),
            tokenizer_audit_file_sha256=tokenizer_sha,
            tokenizer_audit=tokenizer_audit,
            config=_config(),
        )


def test_v1_final_rebind_rejects_criteria_only_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    config = _v1_config()
    profile = scoring_profile(config)
    snapshot_receipt = {"receipt_sha256": "1" * 64}
    git_binding = {"git_head": "b" * 40}
    payloads = {
        "model_manifest": b"manifest",
        "development_registry": b"registry",
        "scoring_config": b"config",
        "measurement_reliability_criteria": b"criteria",
    }
    tokenizer_audit = {"output_sha256": "2" * 64}
    tokenizer_sha = "3" * 64
    monkeypatch.setattr(
        module,
        "verify_snapshot",
        lambda *_args: {"portable_receipt": snapshot_receipt},
    )
    def changed_inputs(selected_profile):
        assert selected_profile is profile
        return (
            git_binding,
            {
                **payloads,
                "measurement_reliability_criteria": b"changed-criteria",
            },
        )

    monkeypatch.setattr(module, "_bound_execution_inputs", changed_inputs)
    monkeypatch.setattr(
        module,
        "load_accepted_tokenizer_audit",
        lambda *_args: (tokenizer_audit, tokenizer_sha),
    )

    with pytest.raises(ScoringRunError, match="canonical inputs changed"):
        module._final_integrity_rebind(
            argparse.Namespace(
                snapshot_path=Path("snapshot"),
                cache_dir=Path("cache"),
            ),
            profile=profile,
            artifact={"id": "artifact"},
            snapshot_receipt=snapshot_receipt,
            git_binding=git_binding,
            input_payloads=payloads,
            tokenizer_audit_path=Path("tokenizer.json"),
            tokenizer_audit_file_sha256=tokenizer_sha,
            tokenizer_audit=tokenizer_audit,
            config=config,
        )


def test_fake_scoring_execution_publishes_one_valid_atomic_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _score_cli()
    config, registry, audit, score = _small_score_fixture()
    accepted_audit = deepcopy(audit)
    accepted_audit["output_sha256"] = config["accepted_tokenizer_audit"][
        "output_sha256"
    ]
    score_bytes = pretty_json_bytes(score)
    template = _receipt(
        score,
        score_bytes,
        "a",
        config=config,
        tokenizer_audit=audit,
        process_id=101,
    )
    cache = tmp_path / "cache"
    snapshot = cache / "snapshot"
    snapshot.mkdir(parents=True)
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_output:
        output_root = Path(raw_output)
        score_path = output_root / "score.json"
        runtime_path = output_root / "runtime.json"
        args = argparse.Namespace(
            config=module.DEFAULT_CONFIG,
            manifest=module.DEFAULT_MANIFEST,
            registry=module.DEFAULT_REGISTRY,
            artifact=config["artifact"]["id"],
            prefix_policy="none",
            max_length=2048,
            device="cuda:0",
            dtype="float16",
            cache_dir=cache,
            snapshot_path=snapshot,
            resource_audit=tmp_path / "resource.json",
            tokenizer_audit=tmp_path / "tokenizer.json",
            attempt="a",
            allow_low_ram=True,
            execute=True,
            allow_download=False,
            output=score_path,
            runtime_output=runtime_path,
        )
        args._output_storage_preflight = module._output_storage_observation(
            args,
            config,
            phase="preflight",
        )
        git_binding = template["git"]
        payloads = {
            "scoring_config": b"config",
            "model_manifest": b"manifest",
            "development_registry": b"registry",
        }
        artifact = dict(config["artifact"])
        model_benchmark = SimpleNamespace(_max_rss_bytes=lambda: 1)
        resource_state = {
            "preflight": deepcopy(template["resource_preflight"]),
            "before_deserialization": lambda *_args: None,
        }
        loaded_tokenizer = SimpleNamespace(
            snapshot_verification=audit["snapshot_verification"],
            tokenizer_validation=audit["loaded_tokenizer_validation"],
            runtime_identity=audit["runtime_identity"],
        )
        loaded_model = SimpleNamespace(
            snapshot_verification=template["snapshot_verification"],
            model_validation=template["model_validation"],
            loading_info=template["model_loading_info"],
            tokenizer_validation=template["tokenizer_validation"],
            runtime_identity=template["runtime_identity"],
            load_seconds=0.0,
            revision=config["artifact"]["revision"],
        )

        class Provider:
            prefix_token_ids: tuple[int, ...] = ()

            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def __call__(self, *_args, **_kwargs):
                raise AssertionError("the fake scorer supplies the complete base score")

            def assert_model_unchanged(self) -> None:
                pass

            def runtime_metrics(self) -> dict:
                metrics = {
                    key: deepcopy(value)
                    for key, value in template["metrics"].items()
                    if key
                    not in {
                        "load_seconds",
                        "wall_seconds",
                        "process_max_rss_bytes",
                        "peak_allocated_bytes",
                        "peak_reserved_bytes",
                    }
                }
                metrics["forward_seconds"] = [0.0] * config["registry_topology"][
                    "candidate_count"
                ]
                metrics["aggregate_forward_seconds"] = 0.0
                return metrics

        class FakeCuda:
            @staticmethod
            def synchronize(_device: object) -> None:
                pass

            @staticmethod
            def max_memory_allocated(_device: object) -> int:
                return template["metrics"]["peak_allocated_bytes"]

            @staticmethod
            def max_memory_reserved(_device: object) -> int:
                return template["metrics"]["peak_reserved_bytes"]

            @staticmethod
            def empty_cache() -> None:
                pass

        fake_torch = SimpleNamespace(
            device=lambda value: value,
            cuda=FakeCuda(),
        )
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        monkeypatch.setattr(
            module,
            "_pre_execution_policy",
            lambda _args: (
                config,
                args.tokenizer_audit,
                scoring_profile(config),
            ),
        )
        monkeypatch.setattr(
            module,
            "_execution_inputs",
            lambda _args, _profile: (
                config,
                artifact,
                registry,
                git_binding,
                payloads,
                FROZEN_RUN_SPEC_SHA256,
                config["canonical_inputs"]["manifest_sha256"],
                config["canonical_inputs"]["registry_sha256"],
            ),
        )
        monkeypatch.setattr(
            module,
            "load_accepted_tokenizer_audit",
            lambda *_args: (
                accepted_audit,
                config["accepted_tokenizer_audit"]["file_sha256"],
            ),
        )
        monkeypatch.setattr(
            module,
            "_resource_preflight",
            lambda *_args: (model_benchmark, resource_state),
        )
        monkeypatch.setattr(module, "RunLock", lambda *_args, **_kwargs: nullcontext())
        monkeypatch.setattr(
            module, "load_manifest_tokenizer", lambda *_args, **_kwargs: loaded_tokenizer
        )
        observed_model_load: dict[str, object] = {}

        def fake_load_manifest_model(*_args, **kwargs):
            observed_model_load.update(kwargs)
            return loaded_model

        monkeypatch.setattr(module, "load_manifest_model", fake_load_manifest_model)
        monkeypatch.setattr(module, "TransformersContinuationProvider", Provider)
        def fake_score_registry(*_args, **kwargs):
            kwargs["execution_trace"].extend(
                module.execution_trace_for_registry(
                    registry, kwargs["execution_mode"]
                )
            )
            return {}

        monkeypatch.setattr(
            module, "score_evaluation_registry", fake_score_registry
        )
        monkeypatch.setattr(
            module,
            "finalize_score_artifact",
            lambda *_args, **_kwargs: deepcopy(score),
        )
        monkeypatch.setattr(
            module,
            "_resident_resource_check",
            lambda *_args, label, **_kwargs: deepcopy(
                template[
                    "post_load_resource" if label == "post-load" else "post_score_resource"
                ]
            ),
        )
        monkeypatch.setattr(
            module,
            "verify_snapshot",
            lambda *_args: {
                "portable_receipt": template["snapshot_verification"]
            },
        )
        monkeypatch.setattr(
            module,
            "_bound_execution_inputs",
            lambda _profile: (git_binding, payloads),
        )

        try:
            receipt = module._execute(args)
        except BaseException:
            reservation = getattr(args, "_output_reservation", None)
            if reservation is not None and reservation.active:
                reservation.rollback()
            raise

        assert score_path.read_bytes() == score_bytes
        published_receipt = json.loads(runtime_path.read_text(encoding="utf-8"))
        assert published_receipt == receipt
        assert observed_model_load["expected_determinism"] == config["determinism"]
        assert set(config["determinism"]) == {
            "algorithms",
            "attention_implementation",
            "cublas_workspace_config",
            "cudnn_benchmark",
            "exact_score_bytes_required",
            "float32_matmul_precision",
            "fresh_invocations",
            "rescue_runs",
            "sdpa_backends",
            "sdpa_math_allow_fp16_reduction",
            "tf32",
            "use_cache",
        }
        assert _v1_config()["determinism"] == config["determinism"]
        assert "attempt_execution_modes" not in config["determinism"]
        assert validate_complete_receipt(
            receipt,
            config,
            tokenizer_audit=accepted_audit,
        ) == ()


def test_output_location_rejects_linked_parent() -> None:
    module = _score_cli()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_root:
        root = Path(raw_root)
        real = root / "real"
        linked = root / "linked"
        real.mkdir()
        try:
            linked.symlink_to(real, target_is_directory=True)
        except OSError as error:
            if os.name != "nt":
                pytest.skip(f"directory symlinks are unavailable: {error}")
            completed = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(linked),
                    str(real),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                pytest.skip(f"directory junctions are unavailable: {completed.stderr}")

        try:
            with pytest.raises(ScoringRunError, match="linked directory"):
                module._require_output_location(
                    linked / "score.json",
                    cache_dir=None,
                    snapshot_path=None,
                    label="score output",
                )
        finally:
            if os.path.lexists(linked):
                if os.name == "nt":
                    os.rmdir(linked)
                else:
                    linked.unlink()


@pytest.mark.parametrize(
    "filename",
    ["probe.json:secret", "CON.json", "trailingdot.", "trailingspace "],
)
def test_output_location_rejects_nonportable_leaf_names(filename: str) -> None:
    module = _score_cli()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_root:
        with pytest.raises(ScoringRunError):
            module._require_output_location(
                Path(raw_root) / filename,
                cache_dir=None,
                snapshot_path=None,
                label="score output",
            )


def test_output_location_rejects_casefolded_sibling_collision() -> None:
    module = _score_cli()
    with tempfile.TemporaryDirectory(dir=module.LOCAL_OUTPUT_ROOT) as raw_root:
        root = Path(raw_root)
        (root / "Score.json").write_text("fixture", encoding="utf-8")
        with pytest.raises(ScoringRunError, match="portable filesystem semantics"):
            module._require_output_location(
                root / "score.json",
                cache_dir=None,
                snapshot_path=None,
                label="score output",
            )


def test_canonical_input_path_rejects_normalization_alias() -> None:
    module = _score_cli()
    expected = module.ROOT / "configs" / "runs" / "pythia-development-score-v1.json"
    aliased = module.ROOT / "configs" / "runs" / ".." / "runs" / expected.name

    with pytest.raises(ScoringRunError, match="path-normalization alias"):
        module._require_canonical_path(aliased, expected, "scoring config")


@pytest.mark.parametrize("suffix", [".", " "])
def test_profile_selection_rejects_windows_leaf_aliases(suffix: str) -> None:
    module = _score_cli()
    aliased = Path(str(module.ROOT / V1_SCORING_PROFILE.config_path) + suffix)

    with pytest.raises(ScoringRunError) as caught:
        module._selected_profile(aliased)
    assert str(caught.value) in {
        "scoring config path is not allowlisted",
        "scoring execution requires the canonical scoring config",
    }


@pytest.mark.parametrize("suffix", [".", " "])
def test_execution_arguments_reject_tokenizer_audit_leaf_aliases(
    suffix: str,
) -> None:
    module = _score_cli()
    config = _v1_config()
    configured = module.ROOT / config["accepted_tokenizer_audit"]["path"]

    with pytest.raises(ScoringRunError, match="canonical accepted tokenizer audit"):
        module._require_canonical_path(
            Path(str(configured) + suffix),
            configured,
            "accepted tokenizer audit",
        )
