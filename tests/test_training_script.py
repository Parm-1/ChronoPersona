from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark_lora_training.py"


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_training_plan_is_no_network_and_records_full_weight_blocker() -> None:
    completed = _run("plan")

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "planned"
    assert report["network_access_permitted"] is False
    assert report["weights_downloaded"] is False
    assert report["scientific_claim_authorized"] is False
    assert report["training_profile"]["steps"] == 5
    assert report["training_profile"]["causal_targets"] == 635
    assert report["training_profile"]["determinism"] == {
        "algorithms": True,
        "attention_implementation": "sdpa",
        "cublas_workspace_config": ":4096:8",
        "cudnn_benchmark": False,
        "sdpa_backends": ["math"],
        "sdpa_math_allow_fp16_reduction": False,
        "shuffle": False,
        "tf32": False,
        "workers": 0,
    }
    assert report["full_weight_adamw_capacity"]["fits_before_activations"] is False
    assert report["full_weight_adamw_capacity"]["shortfall_bytes"] == 1_652_260_864


def test_training_runner_exposes_no_download_flag() -> None:
    completed = _run(
        "run",
        "--condition", "control",
        "--cache-dir", "cache",
        "--snapshot-path", "snapshot",
        "--resource-audit", "audit.json",
        "--load-report", "load.json",
        "--output", "output.json",
        "--allow-download",
    )

    assert completed.returncode == 2
    assert "unrecognized arguments: --allow-download" in completed.stderr


def test_plan_refuses_to_overwrite_report(tmp_path: Path) -> None:
    output = tmp_path / "plan.json"
    output.write_text("preserve\n", encoding="utf-8")

    completed = _run("plan", "--output", str(output))

    assert completed.returncode == 1
    assert output.read_text(encoding="utf-8") == "preserve\n"
    assert "refusing to overwrite output report" in completed.stderr


def test_run_refuses_existing_report_before_execution(tmp_path: Path) -> None:
    output = tmp_path / "run.json"
    output.write_text("preserve\n", encoding="utf-8")

    completed = _run(
        "run",
        "--condition", "control",
        "--cache-dir", str(tmp_path / "missing-cache"),
        "--snapshot-path", str(tmp_path / "missing-snapshot"),
        "--resource-audit", str(tmp_path / "missing-audit.json"),
        "--load-report", str(tmp_path / "missing-load.json"),
        "--output", str(output),
    )

    assert completed.returncode == 1
    assert output.read_text(encoding="utf-8") == "preserve\n"
    assert "output-preflight" in completed.stderr
    assert "refusing to overwrite output report" in completed.stderr
    assert "missing-load" not in completed.stderr


@pytest.mark.parametrize("version", ("v0", "v1"))
def test_run_report_must_be_outside_immutable_run_tree(version: str) -> None:
    output = ROOT / "runs" / f"pythia-lora-smoke-{version}" / "forbidden-report.json"
    assert not output.exists()

    completed = _run(
        "run",
        "--condition", "control",
        "--cache-dir", "missing-cache",
        "--snapshot-path", "missing-snapshot",
        "--resource-audit", "missing-audit.json",
        "--load-report", "missing-load.json",
        "--output", str(output),
    )

    assert completed.returncode == 1
    assert "outside the immutable training run tree" in completed.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        ("verify", ["--run-root", "missing-run"]),
        (
            "compare",
            ["--control-root", "missing-control", "--resumed-root", "missing-resumed"],
        ),
    ],
)
def test_verify_and_compare_refuse_existing_reports_before_reading_runs(
    tmp_path: Path,
    command: str,
    arguments: list[str],
) -> None:
    output = tmp_path / f"{command}.json"
    output.write_text("preserve\n", encoding="utf-8")

    completed = _run(command, *arguments, "--output", str(output))

    assert completed.returncode == 1
    assert output.read_text(encoding="utf-8") == "preserve\n"
    assert "output-preflight" in completed.stderr
    assert "refusing to overwrite output report" in completed.stderr
    assert "missing-run" not in completed.stderr


def test_verify_report_has_exact_cli_evidence_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location("training_cli_verify_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "verify.json"
    plan = SimpleNamespace(identity={"run_id": "r" + "1" * 24})
    monkeypatch.setattr(module, "_load_stored_plan", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(
        module,
        "verify_training_run",
        lambda *_args, **_kwargs: {
            "status": "verified",
            "run_id": plan.identity["run_id"],
            "condition": "control",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "verify",
            "--run-root",
            str(tmp_path / "control"),
            "--output",
            str(output),
        ],
    )

    assert module.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    observed_hash = report.pop("cli_report_sha256")
    assert observed_hash == module.canonical_sha256(report)
    assert report["schema_version"] == 1
    assert report["mode"] == "verify"
    assert report["network_access_performed"] is False
    assert report["scientific_claim_authorized"] is False


def test_compare_report_has_exact_cli_evidence_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location("training_cli_compare_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "compare.json"
    plan = SimpleNamespace(identity={"run_id": "r" + "2" * 24})
    monkeypatch.setattr(module, "_load_stored_plan", lambda *_args, **_kwargs: plan)
    monkeypatch.setattr(
        module,
        "compare_training_runs",
        lambda *_args, **_kwargs: {
            "status": "equal",
            "run_id": plan.identity["run_id"],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "compare",
            "--control-root",
            str(tmp_path / "control"),
            "--resumed-root",
            str(tmp_path / "resumed"),
            "--output",
            str(output),
        ],
    )

    assert module.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    observed_hash = report.pop("cli_report_sha256")
    assert observed_hash == module.canonical_sha256(report)
    assert report["schema_version"] == 1
    assert report["mode"] == "compare"
    assert report["network_access_performed"] is False
    assert report["scientific_claim_authorized"] is False


def test_cli_failure_report_preserves_training_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location("training_cli_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "failure.json"

    def injected_failure(_args):
        error = MemoryError("injected bounded OOM sentinel")
        error.chronopersona_failure_context = {
            "condition": "control",
            "run_id": "r" + "1" * 24,
            "plan_sha256": "a" * 64,
            "completed_steps": 1,
            "tokens_seen": 128,
            "attempt_report": {
                "path": "artifacts/attempts/attempt-0001.json",
                "file_sha256": "b" * 64,
                "attempt_report_sha256": "c" * 64,
            },
        }
        raise error

    monkeypatch.setattr(module, "_run", injected_failure)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "run",
            "--condition",
            "control",
            "--cache-dir",
            "cache",
            "--snapshot-path",
            "snapshot",
            "--resource-audit",
            "audit.json",
            "--load-report",
            "load.json",
            "--output",
            str(output),
        ],
    )

    assert module.main() == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["failure_stage"] == "training-condition"
    assert report["error_type"] == "MemoryError"
    assert report["condition"] == "control"
    assert report["completed_steps"] == 1
    assert report["tokens_seen"] == 128
    assert report["attempt_report"]["attempt_report_sha256"] == "c" * 64
