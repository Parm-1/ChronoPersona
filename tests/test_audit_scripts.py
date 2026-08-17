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


def test_model_benchmark_defaults_to_no_network_plan() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["mode"] == "plan"
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


def test_download_flag_requires_execute() -> None:
    completed = _run(
        "scripts/benchmark_model.py",
        "--artifact",
        "pythia-1b-deduped-main",
        "--allow-download",
    )

    assert completed.returncode == 2
    assert "meaningful only with --execute" in completed.stderr
