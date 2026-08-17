from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from chronopersona.synthetic_calibration import (
    CONDITIONS,
    SyntheticCalibrationError,
    build_dose_plan,
    build_package,
    generate_documents,
    generate_evaluation_registry,
    validate_dose_plan,
    validate_generated_package,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "calibration" / "synthetic-v0.json"


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_package_identity_matches_committed_expected_hashes() -> None:
    built = build_package(CONFIG)
    identity = {
        "schema_version": 1,
        "package_id": built.manifest["package_id"],
        "package_manifest_sha256": built.manifest["output_sha256"],
        "generated_files": {
            path: {
                "sha256": __import__("hashlib").sha256(content).hexdigest(),
                "bytes": len(content),
            }
            for path, content in sorted(built.files.items())
        },
    }
    expected = json.loads(
        (
            ROOT
            / "calibration"
            / "synthetic-v0"
            / "expected-hashes.json"
        ).read_text(encoding="utf-8")
    )
    assert identity == expected


def test_package_counts_and_model_metadata_separation() -> None:
    config = _config()
    documents, metadata = generate_documents(config)
    evaluation = generate_evaluation_registry(config)

    assert len(documents) == 384
    assert len(metadata) == 384
    assert len(evaluation) == 16
    assert all(
        set(row) == {"schema_version", "document_id", "text"}
        for row in documents
    )
    assert all(
        "condition" not in row and "selected_pole" not in row
        for row in documents
    )
    assert all("text" not in row for row in metadata)
    assert {row["condition"] for row in metadata} == set(CONDITIONS)


def test_balance_and_leakage_report_passes() -> None:
    config = _config()
    documents, metadata = generate_documents(config)
    evaluation = generate_evaluation_registry(config)
    report, errors = validate_generated_package(
        config,
        documents,
        metadata,
        evaluation,
    )

    assert errors == ()
    assert report["passed"] is True
    assert report["checks"]["document_count"] == {
        "observed": 384,
        "expected": 384,
    }
    assert report["checks"]["entity_overlap"] == []
    assert report["checks"]["direct_rule_leaks"] == []
    assert report["checks"]["shared_ten_word_ngram_item_ids"] == []


def test_placebo_and_ordinal_factorials_are_exact() -> None:
    config = _config()
    _, metadata = generate_documents(config)

    for pair in config["policy_pairs"]:
        for domain in pair["training_domains"]:
            subset = [
                row
                for row in metadata
                if row["pair_id"] == pair["id"]
                and row["domain_id"] == domain["id"]
                and row["condition"] == "shuffled-placebo"
            ]
            assert len(subset) == 16
            pole_outcome = {
                (pole, outcome): sum(
                    row["selected_pole_code"] == pole
                    and row["outcome"] == outcome
                    for row in subset
                )
                for pole in ("a", "b")
                for outcome in ("success", "failure")
            }
            assert pole_outcome == {
                ("a", "success"): 6,
                ("a", "failure"): 2,
                ("b", "success"): 6,
                ("b", "failure"): 2,
            }
            ordinal_outcome = {
                (ordinal, outcome): sum(
                    row["selected_ordinal"] == ordinal
                    and row["outcome"] == outcome
                    for row in subset
                )
                for ordinal in ("first", "second")
                for outcome in ("success", "failure")
            }
            assert ordinal_outcome == {
                ("first", "success"): 6,
                ("first", "failure"): 2,
                ("second", "success"): 6,
                ("second", "failure"): 2,
            }


def test_doses_are_nested_and_unfrozen() -> None:
    config = _config()
    _, metadata = generate_documents(config)
    plan = build_dose_plan(config, metadata)

    assert validate_dose_plan(plan) == ()
    assert plan["training_authorized"] is False
    assert all(branch["target_tokens"] == 0 for branch in plan["branches"])
    assert all(
        branch["token_budget_status"] == "unfrozen"
        for branch in plan["branches"]
    )
    assert all(
        branch["metadata_must_not_be_serialized"] is True
        for branch in plan["branches"]
    )


def test_model_visible_label_leak_is_rejected() -> None:
    config = _config()
    documents, metadata = generate_documents(config)
    evaluation = generate_evaluation_registry(config)
    tampered = deepcopy(documents)
    tampered[0]["text"] += " This was the indirect-a condition."

    _, errors = validate_generated_package(
        config,
        tampered,
        metadata,
        evaluation,
    )
    assert any("leaks experiment label" in error for error in errors)


def test_metadata_text_leak_is_rejected() -> None:
    config = _config()
    documents, metadata = generate_documents(config)
    evaluation = generate_evaluation_registry(config)
    tampered = deepcopy(metadata)
    tampered[0]["text"] = documents[0]["text"]

    _, errors = validate_generated_package(
        config,
        documents,
        tampered,
        evaluation,
    )
    assert any("contains model-visible prose" in error for error in errors)


def test_nonzero_token_budget_is_rejected() -> None:
    config = _config()
    config["target_tokens"]["low"] = 1000

    with pytest.raises(
        SyntheticCalibrationError,
        match="all target token budgets must remain zero",
    ):
        _build_package_from_value(config)


def _build_package_from_value(config: dict):
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return build_package(path)


def test_teacher_generated_provenance_is_rejected() -> None:
    config = _config()
    config["generation_provenance"]["teacher_model_used"] = True

    with pytest.raises(
        SyntheticCalibrationError,
        match="teacher_model_used",
    ):
        _build_package_from_value(config)


def test_evaluation_options_are_unique_and_word_balanced() -> None:
    evaluation = generate_evaluation_registry(_config())
    prompts: list[str] = []
    candidates: list[str] = []
    for item in evaluation:
        for form in item["forms"]:
            prompts.append(form["prompt"])
            texts = [
                candidate["text"]
                for candidate in form["candidates"]
            ]
            candidates.extend(texts)
            word_counts = [len(text.split()) for text in texts]
            assert word_counts[0] == word_counts[1]
    assert len(prompts) == len(set(prompts))
    assert len(candidates) == len(set(candidates))
