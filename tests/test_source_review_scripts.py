from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from chronopersona.source_metadata import (
    SampleTarget,
    deterministic_audit_sample,
    load_source_metadata,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "tests" / "fixtures" / "source_metadata.jsonl"


def _run(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _manager_packet(path: Path) -> None:
    packet, _ = deterministic_audit_sample(
        load_source_metadata(METADATA),
        [
            SampleTarget(
                "arxiv-cc-single-version-descriptive",
                "early",
                "eligible-random",
                1,
            ),
            SampleTarget(
                "arxiv-cc-single-version-descriptive",
                "late",
                "eligible-random",
                1,
            ),
        ],
        seed="source-c-review-v0",
        metadata_sha256=sha256_file(METADATA),
        hide_era_labels=True,
    )
    path.write_text(json.dumps(packet), encoding="utf-8")


def test_review_and_access_commands_preserve_locator_firewall(
    tmp_path: Path,
) -> None:
    manager = tmp_path / "manager.json"
    review = tmp_path / "review.json"
    access_map = tmp_path / "access-map.json"
    _manager_packet(manager)

    prepared = _run(
        "prepare_source_review.py",
        str(manager),
        "--redaction-seed",
        "source-c-locator-firewall-v0",
        "--review-output",
        str(review),
        "--access-map-output",
        str(access_map),
    )
    assert prepared.returncode == 0, prepared.stderr

    review_value = json.loads(review.read_text(encoding="utf-8"))
    map_value = json.loads(access_map.read_text(encoding="utf-8"))
    assert review_value["locators_redacted"] is True
    assert "https://" not in json.dumps(review_value)
    assert "s3://" not in json.dumps(review_value)
    assert "https://" in json.dumps(map_value)

    access_id = review_value["records"][0]["access_id"]
    log = tmp_path / "events.jsonl"
    logged = _run(
        "log_source_access.py",
        "--access-map",
        str(access_map),
        "--access-id",
        access_id,
        "--locator-kind",
        "content",
        "--reviewer",
        "internal-reviewer-1",
        "--purpose",
        "content-review",
        "--accessed-at",
        "2026-08-17T16:00:00Z",
        "--outcome",
        "succeeded",
        "--response-sha256",
        "b" * 64,
        "--response-bytes",
        "512",
        "--log",
        str(log),
    )
    assert logged.returncode == 0, logged.stderr
    event = json.loads(log.read_text(encoding="utf-8"))
    assert event["source_text_recorded"] is False
    assert "https://" not in json.dumps(event)
    assert "s3://" not in json.dumps(event)


def test_review_command_rejects_unhidden_manager_packet(tmp_path: Path) -> None:
    packet, _ = deterministic_audit_sample(
        load_source_metadata(METADATA),
        [
            SampleTarget(
                "arxiv-cc-single-version-descriptive",
                "early",
                "eligible-random",
                1,
            )
        ],
        seed="source-c-review-v0",
        metadata_sha256=sha256_file(METADATA),
        hide_era_labels=False,
    )
    manager = tmp_path / "manager.json"
    manager.write_text(json.dumps(packet), encoding="utf-8")

    result = _run(
        "prepare_source_review.py",
        str(manager),
        "--redaction-seed",
        "source-c-locator-firewall-v0",
        "--review-output",
        str(tmp_path / "review.json"),
        "--access-map-output",
        str(tmp_path / "map.json"),
    )
    assert result.returncode == 1
    assert "era-hidden" in result.stderr
