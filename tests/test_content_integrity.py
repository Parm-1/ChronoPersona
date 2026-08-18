from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from chronopersona.content_integrity import (
    ContentIntegrityError,
    audit_content_integrity,
    load_direct_patterns,
    load_integrity_config,
    validate_holdout_authorization,
    validate_integrity_config,
    validate_pattern_registry,
)
from chronopersona.content_manifest import (
    LoadedContentRecord,
    canonical_json_sha256,
    load_content_manifest,
    resolve_content_records,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "content-integrity"
MANIFEST = FIXTURE_ROOT / "manifest.jsonl"
DOCUMENTS = FIXTURE_ROOT / "documents"
CONFIG = ROOT / "configs" / "content-integrity-v0.json"
PATTERNS = ROOT / "evaluations" / "exposure" / "direct-patterns-v0.json"


def _inputs():
    records = load_content_manifest(MANIFEST)
    loaded = resolve_content_records(records, content_root=DOCUMENTS)
    config = load_integrity_config(CONFIG)
    patterns = load_direct_patterns(PATTERNS)
    return records, loaded, config, patterns


def _audit(loaded=None, config=None):
    _records, default_loaded, default_config, patterns = _inputs()
    return audit_content_integrity(
        loaded or default_loaded,
        manifest_sha256=sha256_file(MANIFEST),
        config=config or default_config,
        config_sha256=sha256_file(CONFIG),
        patterns=patterns,
        patterns_sha256=sha256_file(PATTERNS),
    )


def test_fixture_exercises_all_lexical_integrity_channels() -> None:
    report = _audit()

    assert report["summary"] == {
        "adaptation_record_count": 9,
        "cross_source_near_pair_count": 2,
        "cross_source_normalized_cluster_count": 2,
        "cross_source_raw_cluster_count": 1,
        "direct_exposure_record_count": 1,
        "evaluation_exposure_pair_count": 1,
        "evaluation_record_count": 2,
        "exact_normalized_cluster_count": 2,
        "exact_raw_cluster_count": 1,
        "holdout_boundary_near_pair_count": 1,
        "near_duplicate_pair_count": 2,
        "real_source_c_record_count": 0,
        "record_count": 13,
    }
    raw_records = {
        record["record_id"]
        for record in report["exact_raw_clusters"][0]["records"]
    }
    assert raw_records == {"a-early-raw", "b-late-raw"}
    assert any(
        {record["record_id"] for record in cluster["records"]}
        == {"a-late-normalized", "b-early-normalized"}
        for cluster in report["exact_normalized_clusters"]
    )
    near_pairs = {
        (pair["left"]["record_id"], pair["right"]["record_id"])
        for pair in report["near_duplicate_pairs"]
    }
    assert near_pairs == {
        ("a-early-near", "b-late-near"),
        ("a-early-near", "c-late-near"),
    }
    assert report["evaluation_exposure_pairs"][0][
        "exact_normalized_substring"
    ] is True
    assert report["evaluation_exposure_pairs"][0][
        "crosses_holdout_boundary"
    ] is False
    assert any(
        pair["crosses_holdout_boundary"]
        for pair in report["near_duplicate_pairs"]
        if pair["right"]["source_family"] == "C"
    )
    assert report["direct_exposure_records"] == [
        {
            "record": {
                "record_id": "a-late-exposure",
                "role": "adaptation",
                "source_family": "A",
                "source_id": "wikimedia-fixture",
                "era_window": "late",
                "holdout_status": "exploratory",
                "synthetic_fixture": True,
            },
            "pattern_ids": ["independent-evidence", "multiple-sources"],
            "categories": ["evidence-integration"],
            "match_count": 2,
            "disposition": "triage-only",
        }
    ]


def test_report_is_deterministic_under_manifest_reordering() -> None:
    _records, loaded, config, patterns = _inputs()
    first = audit_content_integrity(
        loaded,
        manifest_sha256=sha256_file(MANIFEST),
        config=config,
        config_sha256=sha256_file(CONFIG),
        patterns=patterns,
        patterns_sha256=sha256_file(PATTERNS),
    )
    second = audit_content_integrity(
        tuple(reversed(loaded)),
        manifest_sha256=sha256_file(MANIFEST),
        config=config,
        config_sha256=sha256_file(CONFIG),
        patterns=tuple(reversed(patterns)),
        patterns_sha256=sha256_file(PATTERNS),
    )

    assert first == second
    assert first["output_sha256"] == canonical_json_sha256(
        {key: value for key, value in first.items() if key != "output_sha256"}
    )


def test_report_contains_no_fixture_text_or_automatic_disposition() -> None:
    report = _audit()
    rendered = json.dumps(report, sort_keys=True)

    assert "The observatory team" not in rendered
    assert "The committee should compare" not in rendered
    assert report["report_text_excerpts"] is False
    assert report["semantic_similarity_performed"] is False
    assert report["automatic_exclusion_performed"] is False


def test_candidate_pair_cap_fails_closed() -> None:
    _records, loaded, config, _patterns = _inputs()
    constrained = replace(config, max_candidate_pairs=1)

    with pytest.raises(ContentIntegrityError, match="candidate-pair limit exceeded"):
        _audit(loaded=loaded, config=constrained)


def test_real_source_c_requires_matching_authorization() -> None:
    records = list(load_content_manifest(MANIFEST))
    index = next(
        index
        for index, record in enumerate(records)
        if record["source_family"] == "C"
    )
    records[index] = {
        **records[index],
        "synthetic_fixture": False,
        "authorship_provenance": "human",
    }
    manifest_hash = "a" * 64

    assert validate_holdout_authorization(
        records,
        manifest_sha256=manifest_hash,
        authorization=None,
    ) == ("real source-C content requires an explicit holdout authorization",)

    authorization = {
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
    }
    assert validate_holdout_authorization(
        records,
        manifest_sha256=manifest_hash,
        authorization=authorization,
    ) == ()

    authorization["manifest_sha256"] = "b" * 64
    errors = validate_holdout_authorization(
        records,
        manifest_sha256=manifest_hash,
        authorization=authorization,
    )
    assert "holdout authorization manifest hash mismatch" in errors


def test_pattern_registry_is_triage_only() -> None:
    patterns = load_direct_patterns(PATTERNS)
    assert patterns
    assert all(pattern.normalized_tokens for pattern in patterns)


def test_config_rejects_windows_style_pattern_paths() -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["direct_patterns"] = r"..\evaluations\patterns.json"

    errors = validate_integrity_config(raw)
    assert any("portable forward-slash" in error for error in errors)


def test_config_rejects_windows_drive_pattern_paths() -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["direct_patterns"] = r"C:\patterns.json"

    errors = validate_integrity_config(raw)
    assert any("portable forward-slash" in error for error in errors)


def test_authorization_is_rejected_when_no_real_source_c_is_present() -> None:
    records = load_content_manifest(MANIFEST)
    authorization = {
        "schema_version": 1,
        "purpose": "pre-confirmatory-content-integrity-audit",
        "source_family": "C",
        "manifest_sha256": sha256_file(MANIFEST),
        "scope": [
            "exact-duplicate",
            "near-duplicate",
            "evaluation-exposure",
            "direct-exposure",
        ],
        "authorized_by": "fixture-reviewer",
        "authorized_at": "2026-08-18T00:00:00Z",
        "no_behavioral_outcomes_inspected": True,
    }

    assert validate_holdout_authorization(
        records,
        manifest_sha256=sha256_file(MANIFEST),
        authorization=authorization,
    ) == (
        "holdout authorization must not be supplied when no real "
        "source-C content is present",
    )


def test_holdout_authorization_requires_valid_manifest_hash_identity() -> None:
    records = load_content_manifest(MANIFEST)

    assert validate_holdout_authorization(
        records,
        manifest_sha256="not-a-hash",
        authorization=None,
    ) == ("manifest_sha256 must be a lowercase SHA-256",)


def test_audit_rejects_untrusted_input_hashes() -> None:
    _records, loaded, config, patterns = _inputs()

    with pytest.raises(
        ContentIntegrityError,
        match="config_sha256 must be a lowercase SHA-256",
    ):
        audit_content_integrity(
            loaded,
            manifest_sha256=sha256_file(MANIFEST),
            config=config,
            config_sha256="invalid",
            patterns=patterns,
            patterns_sha256=sha256_file(PATTERNS),
        )


def test_config_rejects_windows_reserved_pattern_path() -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["direct_patterns"] = "evaluations/exposure/NUL.json"

    errors = validate_integrity_config(raw)
    assert any("Windows-reserved" in error for error in errors)


def test_integrity_config_requires_coherent_content_limits() -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["max_total_content_bytes"] = raw["max_record_bytes"] - 1

    assert (
        "max_total_content_bytes must be at least max_record_bytes"
        in validate_integrity_config(raw)
    )


def test_audit_records_and_enforces_content_limits() -> None:
    report = _audit()
    _records, loaded, config, patterns = _inputs()

    assert report["content_limits"] == {
        "max_records": config.max_records,
        "max_record_bytes": config.max_record_bytes,
        "max_total_content_bytes": config.max_total_content_bytes,
    }

    constrained = replace(config, max_records=1)
    with pytest.raises(ContentIntegrityError, match="exceeding max_records=1"):
        audit_content_integrity(
            loaded,
            manifest_sha256=sha256_file(MANIFEST),
            config=constrained,
            config_sha256=sha256_file(CONFIG),
            patterns=patterns,
            patterns_sha256=sha256_file(PATTERNS),
        )


def _loaded_record(
    *,
    record_id: str,
    role: str,
    source_family: str,
    holdout_status: str,
    tokens: tuple[str, ...],
    digest_character: str,
) -> LoadedContentRecord:
    digest = digest_character * 64
    normalized = " ".join(tokens)
    return LoadedContentRecord(
        manifest={
            "record_id": record_id,
            "role": role,
            "source_family": source_family,
            "source_id": f"{source_family.casefold()}-fixture",
            "era_window": "none" if role == "evaluation" else "early",
            "holdout_status": holdout_status,
            "synthetic_fixture": True,
            "content_sha256": digest,
            "normalized_sha256": digest,
            "content_bytes": len(normalized.encode("utf-8")),
        },
        content_path=Path(f"{record_id}.txt"),
        text=normalized,
        normalized_text=normalized,
        tokens=tokens,
    )


def _small_audit(records: tuple[LoadedContentRecord, ...]) -> dict:
    _records, _loaded, config, patterns = _inputs()
    return audit_content_integrity(
        records,
        manifest_sha256="a" * 64,
        config=config,
        config_sha256="b" * 64,
        patterns=patterns,
        patterns_sha256="c" * 64,
    )


def test_exact_evaluation_exposure_is_token_aligned() -> None:
    evaluation = _loaded_record(
        record_id="evaluation-cat",
        role="evaluation",
        source_family="EVAL",
        holdout_status="not-applicable",
        tokens=("cat",),
        digest_character="1",
    )
    source = _loaded_record(
        record_id="source-concatenate",
        role="adaptation",
        source_family="A",
        holdout_status="exploratory",
        tokens=("concatenate",),
        digest_character="2",
    )

    report = _small_audit((evaluation, source))
    assert report["evaluation_exposure_pairs"] == []


def test_short_exact_evaluation_phrase_is_not_suppressed_by_ngram_size() -> None:
    evaluation = _loaded_record(
        record_id="evaluation-cat",
        role="evaluation",
        source_family="EVAL",
        holdout_status="not-applicable",
        tokens=("cat",),
        digest_character="3",
    )
    source = _loaded_record(
        record_id="source-cat",
        role="adaptation",
        source_family="A",
        holdout_status="exploratory",
        tokens=("the", "cat", "rests"),
        digest_character="4",
    )

    report = _small_audit((evaluation, source))
    assert len(report["evaluation_exposure_pairs"]) == 1
    assert report["evaluation_exposure_pairs"][0][
        "exact_normalized_substring"
    ] is True
    assert report["evaluation_exposure_pairs"][0][
        "crosses_holdout_boundary"
    ] is False


def test_direct_pattern_normalized_values_must_be_unique() -> None:
    raw = json.loads(PATTERNS.read_text(encoding="utf-8"))
    raw["categories"][0]["patterns"][1]["value"] = raw["categories"][0][
        "patterns"
    ][0]["value"].upper()

    assert (
        "direct-pattern normalized values must be globally unique"
        in validate_pattern_registry(raw)
    )


def test_legacy_integrity_config_schema_is_rejected() -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["schema_version"] = 1

    assert "schema_version must be 2" in validate_integrity_config(raw)


def test_direct_pattern_ids_must_be_stable_slugs() -> None:
    raw = json.loads(PATTERNS.read_text(encoding="utf-8"))
    raw["categories"][0]["patterns"][0]["id"] = "unstable id"

    errors = validate_pattern_registry(raw)
    assert any(
        "id must be a lowercase hyphenated slug" in error
        for error in errors
    )


def test_audit_rejects_untrusted_content_byte_declarations() -> None:
    _records, loaded, config, patterns = _inputs()
    changed = replace(
        loaded[0],
        manifest={**loaded[0].manifest, "content_bytes": "12"},
    )

    with pytest.raises(
        ContentIntegrityError,
        match="content_bytes must be a positive integer",
    ):
        audit_content_integrity(
            (changed, *loaded[1:]),
            manifest_sha256=sha256_file(MANIFEST),
            config=config,
            config_sha256=sha256_file(CONFIG),
            patterns=patterns,
            patterns_sha256=sha256_file(PATTERNS),
        )
