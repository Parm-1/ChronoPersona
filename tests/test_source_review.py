from __future__ import annotations

import json
from pathlib import Path

import pytest

from chronopersona.source_metadata import (
    SampleTarget,
    deterministic_audit_sample,
    load_source_metadata,
    sha256_file,
)
from chronopersona.source_review import (
    SourceReviewError,
    append_access_event,
    build_access_event,
    redact_review_packet,
    validate_redacted_review_packet,
)


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "tests" / "fixtures" / "source_metadata.jsonl"


def _sample_packet() -> dict:
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
    return packet


def test_source_c_packet_redacts_locators_and_date_bearing_identifiers() -> None:
    first_packet, first_map = redact_review_packet(
        _sample_packet(),
        redaction_seed="source-c-locator-firewall-v0",
    )
    second_packet, second_map = redact_review_packet(
        _sample_packet(),
        redaction_seed="source-c-locator-firewall-v0",
    )

    assert first_packet == second_packet
    assert first_map == second_map
    assert validate_redacted_review_packet(first_packet) == ()
    rendered = json.dumps(first_packet, sort_keys=True)
    for forbidden in (
        "https://",
        "s3://",
        "native_timestamp",
        "native_item_id",
        "record_id",
        "era_window",
        "1203.00001",
        "1806.00002",
    ):
        assert forbidden not in rendered
    assert all(row["access_available"] is True for row in first_packet["records"])
    assert all(row["access_id"].startswith("access-") for row in first_packet["records"])

    protected = json.dumps(first_map, sort_keys=True)
    assert "https://export.arxiv.org" in protected
    assert "s3://arxiv" in protected
    assert first_map["review_packet_sha256"] == first_packet["output_sha256"]


def test_redaction_requires_an_era_hidden_packet() -> None:
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
        seed="not-hidden",
        metadata_sha256=sha256_file(METADATA),
        hide_era_labels=False,
    )

    with pytest.raises(SourceReviewError, match="era-hidden"):
        redact_review_packet(packet, redaction_seed="redaction")


def test_access_event_contains_hashes_but_no_locator_or_source_text(
    tmp_path: Path,
) -> None:
    review_packet, access_map = redact_review_packet(
        _sample_packet(),
        redaction_seed="source-c-locator-firewall-v0",
    )
    access_id = review_packet["records"][0]["access_id"]
    event = build_access_event(
        access_map,
        access_id=access_id,
        locator_kind="content",
        reviewer="internal-reviewer-1",
        purpose="content-review",
        accessed_at="2026-08-17T12:00:00-04:00",
        outcome="succeeded",
        response_sha256="a" * 64,
        response_bytes=2048,
    )

    assert event["accessed_at"] == "2026-08-17T16:00:00Z"
    assert event["source_text_recorded"] is False
    assert len(event["locator_sha256"]) == 64
    rendered = json.dumps(event, sort_keys=True)
    assert "s3://" not in rendered
    assert "https://" not in rendered
    assert "response_body" not in rendered

    log = tmp_path / "access-events.jsonl"
    append_access_event(log, event)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows == [event]

    with pytest.raises(SourceReviewError, match="duplicate access event"):
        append_access_event(log, event)


def test_successful_access_requires_response_hash() -> None:
    review_packet, access_map = redact_review_packet(
        _sample_packet(),
        redaction_seed="source-c-locator-firewall-v0",
    )

    with pytest.raises(SourceReviewError, match="requires response_sha256"):
        build_access_event(
            access_map,
            access_id=review_packet["records"][0]["access_id"],
            locator_kind="metadata",
            reviewer="internal-reviewer-1",
            purpose="metadata-review",
            accessed_at="2026-08-17T16:00:00Z",
            outcome="succeeded",
        )
