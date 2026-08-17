import json
from pathlib import Path
import subprocess
import sys


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


def test_download_flags_require_execute() -> None:
    tokenizer = _run(
        "scripts/audit_registry_tokenizer.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--prefix-policy",
        "none",
        "--allow-download",
    )
    model = _run(
        "scripts/score_registry_transformers.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--prefix-policy",
        "none",
        "--allow-download",
    )

    assert tokenizer.returncode == 2
    assert model.returncode == 2
    assert "meaningful only with --execute" in tokenizer.stderr
    assert "meaningful only with --execute" in model.stderr
