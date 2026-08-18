from copy import deepcopy
from pathlib import Path

from chronopersona.evaluation import (
    canonical_json_sha256,
    load_evaluation_registry,
    sha256_file,
    validate_evaluation_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evaluations" / "registry" / "development-v0.jsonl"


def test_committed_development_registry_is_valid() -> None:
    items = load_evaluation_registry(REGISTRY)

    assert len(items) == 12
    assert validate_evaluation_registry(items) == ()
    assert sum(item["domain"] == "evidence-integration" for item in items) == 6
    assert sum(item["domain"] == "procedural-tradeoffs" for item in items) == 6


def test_registry_file_hash_is_stable() -> None:
    first = sha256_file(REGISTRY)
    second = sha256_file(REGISTRY)

    assert first == second
    assert len(first) == 64


def test_canonical_hash_ignores_mapping_insertion_order() -> None:
    left = {"a": 1, "b": {"x": 2, "y": 3}}
    right = {"b": {"y": 3, "x": 2}, "a": 1}

    assert canonical_json_sha256(left) == canonical_json_sha256(right)


def test_duplicate_item_ids_are_rejected() -> None:
    items = [deepcopy(item) for item in load_evaluation_registry(REGISTRY)]
    items[1]["item_id"] = items[0]["item_id"]

    assert "evaluation item ids must be unique" in validate_evaluation_registry(
        items
    )


def test_explicit_year_is_rejected() -> None:
    items = [deepcopy(item) for item in load_evaluation_registry(REGISTRY)]
    items[0]["forms"][0]["prompt"] += " The record was created in 2019."

    assert any(
        "forbidden temporal cue" in error
        for error in validate_evaluation_registry(items)
    )


def test_candidate_requires_explicit_leading_space() -> None:
    items = [deepcopy(item) for item in load_evaluation_registry(REGISTRY)]
    candidate = items[0]["forms"][0]["candidates"][0]
    candidate["text"] = candidate["text"].lstrip()

    assert any(
        "must begin with whitespace" in error
        for error in validate_evaluation_registry(items)
    )


def test_frozen_item_requires_all_reviews_to_pass() -> None:
    items = [deepcopy(item) for item in load_evaluation_registry(REGISTRY)]
    items[0]["status"] = "frozen"

    errors = validate_evaluation_registry(items)

    assert any(
        "direct-exposure" in error and "must pass" in error
        for error in errors
    )
    assert any(
        "contamination" in error and "must pass" in error
        for error in errors
    )


def test_each_form_must_cover_both_poles() -> None:
    items = [deepcopy(item) for item in load_evaluation_registry(REGISTRY)]
    form = items[0]["forms"][0]
    form["candidates"][1]["pole"] = form["candidates"][0]["pole"]

    assert any(
        "one candidate for each pole" in error
        for error in validate_evaluation_registry(items)
    )


def test_option_order_invariance_requires_actual_counterbalancing() -> None:
    items = [deepcopy(item) for item in load_evaluation_registry(REGISTRY)]
    first_order = [
        candidate["pole"]
        for candidate in items[0]["forms"][0]["candidates"]
    ]
    second = items[0]["forms"][1]["candidates"]
    items[0]["forms"][1]["candidates"] = sorted(
        second,
        key=lambda candidate: first_order.index(candidate["pole"]),
    )

    errors = validate_evaluation_registry(items)
    assert any(
        "option-order invariance requires both candidate orders" in error
        for error in errors
    )
