from __future__ import annotations

from copy import deepcopy
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


def _packet() -> dict:
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
        seed="source-c-review-integrity-v0",
        metadata_sha256=sha256_file(METADATA),
        hide_era_labels=True,
    )
    return packet


def test_tampered_manager_packet_is_rejected_before_redaction() -> None:
    packet = _packet()
    packet["records"][0]["content_locator"] = "https://attacker.invalid/replaced"

    with pytest.raises(SourceReviewError, match="sample packet output_sha256 mismatch"):
        redact_review_packet(packet, redaction_seed="redaction-v0")


def test_tampered_access_map_is_rejected_before_event_creation() -> None:
    review, access_map = redact_review_packet(
        _packet(),
        redaction_seed="redaction-v0",
    )
    access_map["records"][0]["content_locator"] = "https://attacker.invalid/replaced"

    with pytest.raises(SourceReviewError, match="access map output_sha256 mismatch"):
        build_access_event(
            access_map,
            access_id=review["records"][0]["access_id"],
            locator_kind="content",
            reviewer="reviewer-1",
            purpose="content-review",
            accessed_at="2026-08-17T16:00:00Z",
            outcome="succeeded",
            response_sha256="c" * 64,
            response_bytes=10,
        )


def test_tampered_review_packet_reports_hash_mismatch() -> None:
    review, _ = redact_review_packet(
        _packet(),
        redaction_seed="redaction-v0",
    )
    review["records"][0]["access_available"] = False

    assert any(
        "review packet output_sha256 mismatch" in error
        for error in validate_redacted_review_packet(review)
    )


def test_tampered_event_is_rejected_before_append(tmp_path: Path) -> None:
    review, access_map = redact_review_packet(
        _packet(),
        redaction_seed="redaction-v0",
    )
    event = build_access_event(
        access_map,
        access_id=review["records"][0]["access_id"],
        locator_kind="content",
        reviewer="reviewer-1",
        purpose="content-review",
        accessed_at="2026-08-17T16:00:00Z",
        outcome="succeeded",
        response_sha256="d" * 64,
        response_bytes=10,
    )
    tampered = deepcopy(event)
    tampered["response_bytes"] = 11

    with pytest.raises(SourceReviewError, match="event_id mismatch"):
        append_access_event(tmp_path / "events.jsonl", tampered)
