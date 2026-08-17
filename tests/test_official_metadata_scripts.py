from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "official_metadata"
AUDIT = ROOT / "scripts" / "audit_official_source_metadata.py"
STACK = ROOT / "scripts" / "audit_stackexchange_inventory.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_official_audit_defaults_to_no_network_plan() -> None:
    result = _run(
        str(AUDIT),
        "arxiv",
        "--url",
        "https://export.arxiv.org/oai2?verb=ListRecords&metadataPrefix=arXivRaw",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mode"] == "plan"
    assert report["network_access_permitted"] is False
    assert report["bulk_archive_requested"] is False


def test_live_permission_requires_execute() -> None:
    result = _run(
        str(AUDIT),
        "arxiv",
        "--url",
        "https://export.arxiv.org/oai2?verb=ListRecords&metadataPrefix=arXivRaw",
        "--allow-network",
    )

    assert result.returncode == 1
    assert "requires --execute" in result.stderr


def test_local_arxiv_fixture_executes_without_network() -> None:
    result = _run(
        str(AUDIT),
        "arxiv",
        "--input",
        str(FIXTURES / "arxiv-oai-arxivraw.xml"),
        "--execute",
        "--max-records",
        "1",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["mode"] == "executed-local"
    assert report["record_count"] == 1
    assert report["eligible_for_bounded_review_count"] == 1


def test_source_c_blinding_writes_separate_key(tmp_path: Path) -> None:
    secret = tmp_path / "secret.bin"
    secret.write_bytes(b"fixture-secret")
    key_path = tmp_path / "key.json"
    output_path = tmp_path / "packet.json"

    result = _run(
        str(AUDIT),
        "arxiv",
        "--input",
        str(FIXTURES / "arxiv-oai-arxivraw.xml"),
        "--execute",
        "--max-records",
        "1",
        "--blind-source-c",
        "--blinding-secret-file",
        str(secret),
        "--unblinding-key",
        str(key_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stderr
    packet = json.loads(output_path.read_text(encoding="utf-8"))
    key = json.loads(key_path.read_text(encoding="utf-8"))
    assert "1201.00001" not in json.dumps(packet)
    assert "1201.00001" in json.dumps(key)


def test_wikimedia_local_inventory_is_bounded() -> None:
    result = _run(
        str(AUDIT),
        "wikimedia",
        "--input",
        str(FIXTURES / "wikimedia-dumpstatus.json"),
        "--base-url",
        "https://dumps.wikimedia.org/enwiki/20130101",
        "--execute",
        "--max-records",
        "1",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["file_count"] == 1
    assert report["files"][0]["name"].endswith(".bz2")


def test_stackexchange_command_filters_site_inventory_without_archive_download() -> None:
    result = _run(
        str(STACK),
        "--input",
        str(FIXTURES / "stackexchange-archive-metadata.json"),
        "--archive-base-url",
        "https://archive.org/download/stackexchange",
        "--allowed-site",
        "gardening.stackexchange.com",
        "--execute",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["archive_download_permitted"] is False
    assert report["file_count"] == 1
    assert report["files"][0]["metadata"]["site"] == "gardening.stackexchange.com"
