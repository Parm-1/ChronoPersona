from copy import deepcopy
from pathlib import Path

import pytest

from chronopersona.source_metadata import (
    SampleTarget,
    SamplingPlanError,
    canonical_json_sha256,
    deterministic_audit_sample,
    load_source_metadata,
    sha256_file,
    summarize_source_metadata,
    validate_source_metadata,
)
from chronopersona.source_registry import load_source_registry


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REGISTRY = ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json"
METADATA = ROOT / "tests" / "fixtures" / "source_metadata.jsonl"


def _records() -> list[dict]:
    return [deepcopy(record) for record in load_source_metadata(METADATA)]


def _registry():
    return load_source_registry(SOURCE_REGISTRY)


def test_committed_source_metadata_fixture_is_valid() -> None:
    records = load_source_metadata(METADATA)

    assert len(records) == 16
    assert validate_source_metadata(
        records,
        source_registry=_registry(),
    ) == ()


def test_metadata_records_cannot_embed_document_text() -> None:
    records = _records()
    records[0]["text"] = "This field would silently turn metadata audit into corpus acquisition."

    assert any(
        "forbidden text fields: text" in error
        for error in validate_source_metadata(
            records,
            source_registry=_registry(),
        )
    )


def test_window_must_match_native_timestamp() -> None:
    records = _records()
    records[0]["era_window"] = "late"

    assert any(
        "does not match timestamp classification 'early'" in error
        for error in validate_source_metadata(
            records,
            source_registry=_registry(),
        )
    )


def test_eligible_record_requires_rights_version_and_human_provenance() -> None:
    records = _records()
    records[0]["rights_status"] = "conditional"
    records[0]["version_status"] = "latest-only"
    records[0]["authorship_provenance"] = "unknown"

    errors = validate_source_metadata(
        records,
        source_registry=_registry(),
    )

    assert any("requires rights_status='eligible'" in error for error in errors)
    assert any("requires historically bounded text" in error for error in errors)
    assert any("requires human authorship provenance" in error for error in errors)


def test_duplicate_record_ids_are_rejected() -> None:
    records = _records()
    records[1]["record_id"] = records[0]["record_id"]

    assert "record_id values must be unique" in validate_source_metadata(
        records,
        source_registry=_registry(),
    )


def test_summary_is_deterministic_and_contains_no_text() -> None:
    records = load_source_metadata(METADATA)
    metadata_hash = sha256_file(METADATA)

    first = summarize_source_metadata(
        records,
        metadata_sha256=metadata_hash,
    )
    second = summarize_source_metadata(
        records,
        metadata_sha256=metadata_hash,
    )

    assert first == second
    assert first["record_count"] == 16
    assert first["counts"]["source"]["arxiv-cc-single-version-descriptive"] == 4
    unhashed = deepcopy(first)
    recorded = unhashed.pop("output_sha256")
    assert recorded == canonical_json_sha256(unhashed)
    assert "text" not in str(first).lower()


def test_deterministic_sample_is_stable_and_nonoverlapping() -> None:
    records = load_source_metadata(METADATA)
    targets = [
        SampleTarget(
            "arxiv-cc-single-version-descriptive",
            "early",
            "rights-boundary",
            1,
        ),
        SampleTarget(
            "arxiv-cc-single-version-descriptive",
            "early",
            "eligible-random",
            1,
        ),
        SampleTarget(
            "arxiv-cc-single-version-descriptive",
            "late",
            "exposure-boundary",
            1,
        ),
        SampleTarget(
            "arxiv-cc-single-version-descriptive",
            "late",
            "eligible-random",
            1,
        ),
    ]
    arguments = {
        "seed": "source-c-audit-v0",
        "metadata_sha256": sha256_file(METADATA),
        "hide_era_labels": True,
    }

    first_packet, first_key = deterministic_audit_sample(
        records,
        targets,
        **arguments,
    )
    second_packet, second_key = deterministic_audit_sample(
        records,
        targets,
        **arguments,
    )

    assert first_packet == second_packet
    assert first_key == second_key
    assert len(first_packet["records"]) == 4
    assert len({row["blind_id"] for row in first_packet["records"]}) == 4
    assert all("era_window" not in row for row in first_packet["records"])
    assert all("native_timestamp" not in row for row in first_packet["records"])
    assert all("record_id" not in row for row in first_packet["records"])
    assert all("era_window" in row for row in first_key["records"])


def test_unblinded_packet_records_window_and_timestamp() -> None:
    packet, _ = deterministic_audit_sample(
        load_source_metadata(METADATA),
        [
            SampleTarget(
                "wikimedia-article-additions",
                "early",
                "eligible-random",
                1,
            )
        ],
        seed="wikimedia-audit-v0",
        metadata_sha256=sha256_file(METADATA),
        hide_era_labels=False,
    )

    assert packet["records"][0]["era_window"] == "early"
    assert packet["records"][0]["native_timestamp"].startswith("2012-")


def test_sample_fails_when_target_is_infeasible() -> None:
    with pytest.raises(SamplingPlanError, match="insufficient records"):
        deterministic_audit_sample(
            load_source_metadata(METADATA),
            [
                SampleTarget(
                    "wikimedia-article-additions",
                    "early",
                    "eligible-random",
                    99,
                )
            ],
            seed="oversubscribed",
            metadata_sha256=sha256_file(METADATA),
            hide_era_labels=False,
        )
