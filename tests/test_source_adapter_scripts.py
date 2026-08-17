from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _run(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_all_adapter_plans_are_no_network() -> None:
    commands = [
        (
            "audit_arxiv_oai_metadata.py",
            "--from-date",
            "2012-01-01",
            "--until-date",
            "2013-12-31",
        ),
        (
            "audit_pmc_oai_metadata.py",
            "--from-date",
            "2012-01-01",
            "--until-date",
            "2013-12-31",
        ),
        ("audit_wikimedia_inventory.py",),
        ("audit_stackexchange_inventory.py",),
    ]

    for command in commands:
        result = _run(command[0], *command[1:])
        assert result.returncode == 0, result.stderr
        plan = json.loads(result.stdout)
        assert plan["mode"] == "plan"
        assert plan["network_access_permitted"] is False
        assert plan.get("content_downloaded", False) is False
        assert plan.get("archive_downloaded", False) is False


def test_arxiv_fixture_command_emits_valid_metadata(tmp_path: Path) -> None:
    output = tmp_path / "arxiv.jsonl"
    summary = tmp_path / "arxiv-summary.json"
    result = _run(
        "audit_arxiv_oai_metadata.py",
        "--input",
        str(FIXTURES / "arxiv_oai_sample.xml"),
        "--from-date",
        "2012-01-01",
        "--until-date",
        "2019-12-31",
        "--output",
        str(output),
        "--summary-output",
        str(summary),
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 3
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["adapter"]["network_used"] is False
    assert report["adapter"]["parser_diagnostics"]["deleted_records"] == 1
    assert report["counts"]["eligibility"] == {"eligible": 1, "excluded": 2}


def test_pmc_fixture_command_emits_no_synthetic_or_confirmed_dates(
    tmp_path: Path,
) -> None:
    output = tmp_path / "pmc.jsonl"
    summary = tmp_path / "pmc-summary.json"
    result = _run(
        "audit_pmc_oai_metadata.py",
        "--input",
        str(FIXTURES / "pmc_oai_sample.xml"),
        "--from-date",
        "2012-01-01",
        "--until-date",
        "2019-12-31",
        "--output",
        str(output),
        "--summary-output",
        str(summary),
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert all(not row["native_timestamp"].startswith("1970-") for row in rows)
    assert all(row["era_window"] == "unresolved" for row in rows)
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["adapter"]["endpoint"].startswith(
        "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
    )
    assert report["adapter"]["publication_date_confirmation_required"] is True
    assert (
        report["adapter"]["parser_diagnostics"][
            "skipped_missing_lifecycle_date"
        ]
        == 1
    )


def test_wikimedia_fixture_requires_and_preserves_pinned_snapshot(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "wikimedia.json"
    result = _run(
        "audit_wikimedia_inventory.py",
        "--input",
        str(FIXTURES / "wikimedia_dumpstatus_sample.json"),
        "--snapshot",
        "20260101",
        "--inventory-output",
        str(inventory),
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(inventory.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["snapshot_id"] == "20260101"

    mutable = _run(
        "audit_wikimedia_inventory.py",
        "--input",
        str(FIXTURES / "wikimedia_dumpstatus_sample.json"),
        "--snapshot",
        "latest",
    )
    assert mutable.returncode == 2
    assert "planning-only" in mutable.stderr


def test_stackexchange_fixture_is_legacy_and_company_attributed(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "stackexchange.json"
    summary = tmp_path / "stackexchange-summary.json"
    result = _run(
        "audit_stackexchange_inventory.py",
        "--input",
        str(FIXTURES / "stackexchange_archive_sample.json"),
        "--inventory-output",
        str(inventory),
        "--summary-output",
        str(summary),
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["adapter"]["company_attributed_archive_item"] is True
    assert "legacy" in report["adapter"]["delivery_status"]

    mirror_payload = json.loads(
        (FIXTURES / "stackexchange_archive_sample.json").read_text(encoding="utf-8")
    )
    mirror_payload["metadata"]["creator"] = ["Community Mirror"]
    mirror = tmp_path / "mirror.json"
    mirror.write_text(json.dumps(mirror_payload), encoding="utf-8")
    rejected = _run(
        "audit_stackexchange_inventory.py",
        "--input",
        str(mirror),
    )
    assert rejected.returncode == 1
    assert "separate provenance decision" in rejected.stderr


def test_network_flag_without_execute_is_rejected() -> None:
    result = _run(
        "audit_stackexchange_inventory.py",
        "--allow-network",
    )
    assert result.returncode == 2
    assert "meaningful only with --execute" in result.stderr
