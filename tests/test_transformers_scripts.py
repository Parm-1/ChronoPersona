import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_tokenizer_audit_defaults_to_no_network_plan() -> None:
    completed = _run(
        "scripts/audit_registry_tokenizer.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--prefix-policy",
        "none",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["mode"] == "plan"
    assert report["network_access_permitted"] is False
    assert report["weights_downloaded"] is False
    assert report["tokenizer_files_downloaded"] is False
    assert report["policy"]["allowed"] is True
    assert report["policy"]["snapshot_execution_allowed"] is True


def test_model_score_defaults_to_no_network_plan() -> None:
    completed = _run(
        "scripts/score_registry_transformers.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--prefix-policy",
        "none",
        "--device",
        "cpu",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["mode"] == "plan"
    assert report["network_access_permitted"] is False
    assert report["weights_downloaded"] is False
    assert report["policy"]["allowed"] is True


def test_plan_exposes_blocked_artifact_without_loading() -> None:
    completed = _run(
        "scripts/audit_registry_tokenizer.py",
        "--artifact",
        "datedgpt-2013-base",
        "--prefix-policy",
        "bos",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["policy"]["allowed"] is False
    assert "license must be verified" in report["policy"]["blocker"]


def test_blocked_model_execution_fails_before_optional_imports() -> None:
    completed = _run(
        "scripts/score_registry_transformers.py",
        "--artifact",
        "datedgpt-2013-base",
        "--prefix-policy",
        "bos",
        "--device",
        "cpu",
        "--execute",
    )

    assert completed.returncode == 1
    assert "license must be verified" in completed.stderr
    assert "dependencies are missing" not in completed.stderr


def test_direct_download_flags_are_disabled() -> None:
    for execute in (False, True):
        execution_flag = ("--execute",) if execute else ()
        tokenizer = _run(
            "scripts/audit_registry_tokenizer.py",
            "--artifact",
            "pythia-1b-deduped-main",
            "--prefix-policy",
            "none",
            *execution_flag,
            "--allow-download",
        )
        model = _run(
            "scripts/score_registry_transformers.py",
            "--artifact",
            "pythia-1b-deduped-main",
            "--prefix-policy",
            "none",
            *execution_flag,
            "--allow-download",
        )

        assert tokenizer.returncode == 2
        assert model.returncode == 2
        assert "verified acquisition workflow" in tokenizer.stderr
        assert "verified acquisition workflow" in model.stderr


def test_execute_download_rejection_preserves_failure_receipt() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / "artifacts" / "local") as raw_root:
        runtime = Path(raw_root) / "failure.json"
        completed = _run(
            "scripts/score_registry_transformers.py",
            "--artifact",
            "pythia-1b-deduped-main",
            "--prefix-policy",
            "none",
            "--execute",
            "--allow-download",
            "--attempt",
            "a",
            "--runtime-output",
            str(runtime),
        )

        assert completed.returncode == 2
        receipt = json.loads(runtime.read_text(encoding="utf-8"))
        assert receipt["status"] == "failed"
        assert receipt["failure_stage"] == "cli-preflight"
        assert receipt["network_access_permitted"] is False
        assert receipt["score"]["valid_score_published"] is False


def test_tokenizer_and_model_execution_require_explicit_paths() -> None:
    tokenizer = _run(
        "scripts/audit_registry_tokenizer.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--prefix-policy",
        "none",
        "--execute",
    )
    model = _run(
        "scripts/score_registry_transformers.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--prefix-policy",
        "none",
        "--device",
        "cpu",
        "--execute",
    )

    assert tokenizer.returncode == 1
    assert model.returncode == 1
    assert "explicit --cache-dir and --snapshot-path" in tokenizer.stderr
    assert "--execute requires explicit" in model.stderr
    assert "--cache-dir" in model.stderr
    assert "--resource-audit" in model.stderr
    assert "--runtime-output" in model.stderr
