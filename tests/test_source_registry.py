from copy import deepcopy
from pathlib import Path

from chronopersona.source_registry import (
    load_source_registry,
    validate_source_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json"


def _registry() -> dict:
    return deepcopy(dict(load_source_registry(REGISTRY)))


def _source(registry: dict, source_id: str) -> dict:
    return next(
        source
        for source in registry["sources"]
        if source["id"] == source_id
    )


def test_committed_source_registry_is_valid() -> None:
    registry = load_source_registry(REGISTRY)

    assert validate_source_registry(registry) == ()
    assert registry["assignments"] == {
        "A": "wikimedia-article-additions",
        "B": "stackexchange-initial-nontechnical-posts",
        "C": "arxiv-cc-single-version-descriptive",
    }


def test_behavioral_outcomes_cannot_be_inspected_during_selection() -> None:
    registry = _registry()
    registry["behavioral_outcomes_inspected"] = True

    assert any(
        "behavioral_outcomes_inspected must remain false" in error
        for error in validate_source_registry(registry)
    )


def test_bulk_download_is_not_authorized_by_the_registry() -> None:
    registry = _registry()
    registry["bulk_download_authorized"] = True

    assert any(
        "bulk_download_authorized must remain false" in error
        for error in validate_source_registry(registry)
    )


def test_assigned_sources_must_be_distinct() -> None:
    registry = _registry()
    registry["assignments"]["B"] = registry["assignments"]["A"]

    assert "A, B, and C assignments must be distinct" in validate_source_registry(
        registry
    )


def test_source_c_must_have_confirmatory_role_and_holdout_status() -> None:
    registry = _registry()
    source_c = _source(
        registry,
        "arxiv-cc-single-version-descriptive",
    )
    source_c["role"] = "exploratory"
    source_c["held_out"] = False

    errors = validate_source_registry(registry)

    assert any(
        "assignments.C source must have role 'held-out-confirmatory'" in error
        for error in errors
    )
    assert any(
        "assignments.C held_out status is inconsistent" in error
        for error in errors
    )


def test_held_out_source_requires_all_firewall_prohibitions() -> None:
    registry = _registry()
    source_c = _source(
        registry,
        "arxiv-cc-single-version-descriptive",
    )
    source_c["holdout_prohibitions"].remove("threshold-selection")

    assert any(
        "missing holdout prohibitions: threshold-selection" in error
        for error in validate_source_registry(registry)
    )


def test_assigned_source_cannot_directly_teach_primary_domain() -> None:
    registry = _registry()
    source_a = _source(registry, "wikimedia-article-additions")
    source_a["domain_exposure"]["procedural-tradeoffs"] = "direct"

    assert any(
        "assigned source cannot directly expose a primary domain" in error
        for error in validate_source_registry(registry)
    )


def test_assigned_source_cannot_have_unresolved_rights() -> None:
    registry = _registry()
    source_b = _source(
        registry,
        "stackexchange-initial-nontechnical-posts",
    )
    source_b["rights"]["status"] = "unresolved"

    assert any(
        "assigned source cannot have unresolved rights" in error
        for error in validate_source_registry(registry)
    )


def test_backup_c_must_be_predeclared_and_held_out() -> None:
    registry = _registry()
    backup = _source(registry, "pmc-oa-cc-version-bounded")
    backup["held_out"] = False

    assert "predeclared_backup_c must remain held out" in validate_source_registry(
        registry
    )


def test_federal_register_cannot_be_silently_promoted_to_source_c() -> None:
    registry = _registry()
    registry["assignments"]["C"] = "federal-register-official-documents"

    errors = validate_source_registry(registry)

    assert any(
        "assignments.C source must have role 'held-out-confirmatory'" in error
        for error in errors
    )
    assert any(
        "assignments.C held_out status is inconsistent" in error
        for error in errors
    )


def test_every_source_requires_at_least_one_official_authority() -> None:
    registry = _registry()
    source_a = _source(registry, "wikimedia-article-additions")
    source_a["official_sources"] = []

    errors = validate_source_registry(registry)
    assert any(
        "official_sources must be a non-empty string list" in error
        for error in errors
    )
