from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from chronopersona.source_metadata import (
    SampleTarget,
    canonical_json_sha256,
    deterministic_audit_sample,
    load_source_metadata,
    sha256_file,
)
from chronopersona.source_review import (
    SourceReviewError,
    append_access_event,
    build_access_event,
    redact_review_packet,
)


ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "tests" / "fixtures" / "source_metadata.jsonl"


def _review_and_map() -> tuple[dict, dict]:
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
        seed="source-c-event-schema-v0",
        metadata_sha256=sha256_file(METADATA),
        hide_era_labels=True,
    )
    return redact_review_packet(packet, redaction_seed="redaction-v0")


def _successful_event() -> dict:
    review, access_map = _review_and_map()
    return build_access_event(
        access_map,
        access_id=review["records"][0]["access_id"],
        locator_kind="content",
        reviewer="reviewer-1",
        purpose="content-review",
        accessed_at="2026-08-17T16:00:00Z",
        outcome="succeeded",
        response_sha256="e" * 64,
        response_bytes=512,
    )


def _rehash(event: dict) -> None:
    event.pop("event_id", None)
    event["event_id"] = "event-" + canonical_json_sha256(event)[:24]


def test_self_consistent_extra_payload_field_is_rejected(tmp_path: Path) -> None:
    event = _successful_event()
    event["response_body"] = "forbidden source content"
    _rehash(event)

    with pytest.raises(SourceReviewError, match="unexpected fields: response_body"):
        append_access_event(tmp_path / "events.jsonl", event)


def test_self_consistent_source_text_flag_is_rejected(tmp_path: Path) -> None:
    event = _successful_event()
    event["source_text_recorded"] = True
    _rehash(event)

    with pytest.raises(SourceReviewError, match="source_text_recorded must be false"):
        append_access_event(tmp_path / "events.jsonl", event)


def test_planned_event_cannot_include_response_evidence() -> None:
    review, access_map = _review_and_map()

    with pytest.raises(SourceReviewError, match="planned access must not include"):
        build_access_event(
            access_map,
            access_id=review["records"][0]["access_id"],
            locator_kind="content",
            reviewer="reviewer-1",
            purpose="content-review",
            accessed_at="2026-08-17T16:00:00Z",
            outcome="planned",
            response_sha256="f" * 64,
            response_bytes=0,
        )


def test_successful_event_requires_response_byte_count() -> None:
    review, access_map = _review_and_map()

    with pytest.raises(SourceReviewError, match="response_sha256 and response_bytes"):
        build_access_event(
            access_map,
            access_id=review["records"][0]["access_id"],
            locator_kind="content",
            reviewer="reviewer-1",
            purpose="content-review",
            accessed_at="2026-08-17T16:00:00Z",
            outcome="succeeded",
            response_sha256="f" * 64,
        )


def test_noncanonical_timestamp_is_rejected_even_with_valid_event_id(
    tmp_path: Path,
) -> None:
    event = _successful_event()
    event["accessed_at"] = "2026-08-17T12:00:00-04:00"
    _rehash(event)

    with pytest.raises(SourceReviewError, match="canonical UTC"):
        append_access_event(tmp_path / "events.jsonl", event)


def test_malformed_existing_event_blocks_append(tmp_path: Path) -> None:
    event = _successful_event()
    log = tmp_path / "events.jsonl"
    append_access_event(log, event)

    existing = deepcopy(event)
    existing["source_text_recorded"] = True
    _rehash(existing)
    log.write_text(
        __import__("json").dumps(existing, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    next_event = deepcopy(event)
    next_event["accessed_at"] = "2026-08-17T16:01:00Z"
    _rehash(next_event)
    with pytest.raises(SourceReviewError, match="source_text_recorded must be false"):
        append_access_event(log, next_event)
