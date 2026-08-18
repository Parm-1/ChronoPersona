from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "content-integrity"
MANIFEST = FIXTURE_ROOT / "manifest.jsonl"
DOCUMENTS = FIXTURE_ROOT / "documents"
CONFIG = ROOT / "configs" / "content-integrity-v0.json"
VALIDATE = ROOT / "scripts" / "validate_content_manifest.py"
AUDIT = ROOT / "scripts" / "audit_content_integrity.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_validate_script_defaults_to_no_content_access() -> None:
    result = _run(
        str(VALIDATE),
        "--manifest",
        str(MANIFEST),
        "--content-root",
        str(DOCUMENTS),
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mode"] == "plan"
    assert report["content_access_permitted"] is False
    assert report["content_accessed"] is False
    assert report["content_limits"]["max_records"] == 2000


def test_audit_script_executes_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    command = [
        str(AUDIT),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--content-root",
        str(DOCUMENTS),
        "--config",
        str(CONFIG),
        "--execute",
    ]
    result_one = _run(*command, "--output", str(first))
    result_two = _run(*command, "--output", str(second))

    assert result_one.returncode == result_two.returncode == 0
    assert first.read_bytes() == second.read_bytes()
    report = json.loads(first.read_text(encoding="utf-8"))
    assert report["summary"]["exact_raw_cluster_count"] == 1
    assert report["summary"]["evaluation_exposure_pair_count"] == 1
    assert report["content_limits"]["max_total_content_bytes"] == 67108864


def test_audit_plan_performs_no_semantic_or_exclusion_work() -> None:
    result = _run(
        str(AUDIT),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--content-root",
        str(DOCUMENTS),
        "--config",
        str(CONFIG),
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mode"] == "plan"
    assert report["content_accessed"] is False
    assert report["content_limits"]["max_record_bytes"] == 4194304
    assert report["semantic_similarity_performed"] is False
    assert report["automatic_exclusion_performed"] is False


def test_real_source_c_plan_is_allowed_but_execute_requires_authorization(
    tmp_path: Path,
) -> None:
    records = [
        json.loads(line)
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
    ]
    index = next(
        index
        for index, record in enumerate(records)
        if record["source_family"] == "C"
    )
    records[index]["synthetic_fixture"] = False
    records[index]["authorship_provenance"] = "human"
    manifest = tmp_path / "real-c.jsonl"
    manifest.write_text(
        "".join(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )

    plan = _run(
        str(AUDIT),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(manifest),
        "--content-root",
        str(DOCUMENTS),
        "--config",
        str(CONFIG),
    )
    assert plan.returncode == 0, plan.stderr
    plan_report = json.loads(plan.stdout)
    assert plan_report["holdout_authorization_required"] is True
    assert plan_report["content_accessed"] is False

    execution = _run(
        str(AUDIT),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(manifest),
        "--content-root",
        str(DOCUMENTS),
        "--config",
        str(CONFIG),
        "--execute",
    )
    assert execution.returncode == 1
    assert "requires an explicit holdout authorization" in execution.stderr


def test_extraneous_source_c_authorization_fails_closed(tmp_path: Path) -> None:
    import hashlib

    manifest_hash = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    authorization = tmp_path / "authorization.json"
    authorization.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "purpose": "pre-confirmatory-content-integrity-audit",
                "source_family": "C",
                "manifest_sha256": manifest_hash,
                "scope": [
                    "exact-duplicate",
                    "near-duplicate",
                    "evaluation-exposure",
                    "direct-exposure",
                ],
                "authorized_by": "fixture-reviewer",
                "authorized_at": "2026-08-18T00:00:00Z",
                "no_behavioral_outcomes_inspected": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    for script in (VALIDATE, AUDIT):
        result = _run(
            str(script),
            "--manifest",
            str(MANIFEST),
            "--content-root",
            str(DOCUMENTS),
            "--holdout-authorization",
            str(authorization),
        )
        assert result.returncode == 1
        assert "must not be supplied" in result.stderr


@pytest.mark.parametrize("script", [VALIDATE, AUDIT])
def test_plan_rejects_manifest_above_configured_record_limit(
    tmp_path: Path, script: Path
) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["max_records"] = 1
    config_path = tmp_path / "limit.json"
    config_path.write_text(
        json.dumps(config, sort_keys=True) + "\n", encoding="utf-8"
    )

    result = _run(
        str(script),
        "--manifest",
        str(MANIFEST),
        "--content-root",
        str(DOCUMENTS),
        "--config",
        str(config_path),
    )

    assert result.returncode == 1
    assert "exceeds max_records=1" in result.stderr
