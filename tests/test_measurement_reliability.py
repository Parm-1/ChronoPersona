from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from chronopersona.evaluation import (
    canonical_json_sha256,
    load_evaluation_registry,
    load_evaluation_registry_with_sha256,
    validate_evaluation_registry,
)
from chronopersona.measurement_reliability import (
    FROZEN_CRITERIA_SHA256,
    MeasurementReliabilityError,
    analyze_score_coherence,
    analyze_score_repeat,
    canonical_registry_bytes,
    criteria_document_bytes,
    git_blob_sha1,
    load_json_artifact,
    load_reliability_criteria,
    validate_registry_against_criteria,
    validate_reliability_criteria,
    validate_tokenizer_audit_against_criteria,
)
from chronopersona.scoring import CandidateEvidence, score_evaluation_registry


ROOT = Path(__file__).resolve().parents[1]
V0 = ROOT / "evaluations" / "registry" / "development-v0.jsonl"
V1 = ROOT / "evaluations" / "registry" / "development-v1.jsonl"
CRITERIA = ROOT / "configs" / "evaluations" / "development-v1-reliability-v0.json"
GENERATOR = ROOT / "scripts" / "build_development_v1_registry.py"


def _criteria() -> dict[str, Any]:
    return load_reliability_criteria(CRITERIA)


def _registry() -> list[dict[str, Any]]:
    return load_evaluation_registry(V1)


def _snapshot_receipt() -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "status": "verified",
        "artifact_id": "pythia-1b-deduped-main",
        "repository": "EleutherAI/pythia-1b-deduped",
        "revision": "7199d8fc61a6d565cd1f3c62bf11525b563e13b2",
        "required_download_bytes": 2_092_816_302,
        "files": [
            {
                "filename": "config.json",
                "sha256": "302d6702a29de1039066e41404877fb8c53b7ddc82e88f9aba277f230086cfe0",
                "size_bytes": 569,
                "verified": True,
            },
            {
                "filename": "model.safetensors",
                "sha256": "fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13",
                "size_bytes": 2_090_701_528,
                "verified": True,
            },
            {
                "filename": "special_tokens_map.json",
                "sha256": "6f50ab5a5a509a1c309d6171f339b196a900dc9c99ad0408ff23bb615fdae7ad",
                "size_bytes": 99,
                "verified": True,
            },
            {
                "filename": "tokenizer_config.json",
                "sha256": "70e38394e494931c6f773ba41e19460dd4436526b852207367f04341b4066d3f",
                "size_bytes": 396,
                "verified": True,
            },
            {
                "filename": "tokenizer.json",
                "sha256": "c24618a1b3e6a38167beff1c72cffd126c3a66254347304b50547d12c5f25624",
                "size_bytes": 2_113_710,
                "verified": True,
            },
        ],
        "config": {
            "architectures": ["GPTNeoXForCausalLM"],
            "auto_map": None,
            "model_type": "gpt_neox",
            "torch_dtype": "float16",
            "verified": True,
        },
        "tokenizer_config": {
            "auto_map": None,
            "declared_special_tokens": {
                "bos_token": "<|endoftext|>",
                "eos_token": "<|endoftext|>",
                "pad_token": None,
                "unk_token": "<|endoftext|>",
            },
            "runtime_expectation": {
                "backend_sha256": "1b0aca3746c0870daeb9137101cd89acbb38710fc433db83331287d5b0e47ee0",
                "class": "GPTNeoXTokenizer",
                "is_fast": True,
                "native_prefix_policy": "none",
                "native_special_tokens_to_add": 0,
                "special_token_ids": {
                    "bos_token_id": 0,
                    "eos_token_id": 0,
                    "pad_token_id": 1,
                    "unk_token_id": 0,
                },
                "special_tokens": {
                    "bos_token": "<|endoftext|>",
                    "eos_token": "<|endoftext|>",
                    "pad_token": "<|padding|>",
                    "unk_token": "<|endoftext|>",
                },
                "tokenizer_length": 50_277,
                "vocab_size": 50_254,
            },
            "tokenizer_class": "GPTNeoXTokenizer",
            "tokenizer_length": 50_277,
            "verified": True,
            "vocab_size": 50_254,
        },
    }
    receipt["receipt_sha256"] = canonical_json_sha256(receipt)
    return receipt


def _loaded_validation() -> dict[str, Any]:
    return {
        "backend_sha256": "1b0aca3746c0870daeb9137101cd89acbb38710fc433db83331287d5b0e47ee0",
        "class": "GPTNeoXTokenizer",
        "identity": (
            "EleutherAI/pythia-1b-deduped@"
            "7199d8fc61a6d565cd1f3c62bf11525b563e13b2"
        ),
        "is_fast": True,
        "model_max_length": 1_000_000_000_000_000_019_884_624_838_656,
        "native_prefix_policy": "none",
        "native_prefix_probe_equal": True,
        "native_prefix_probe_sha256": (
            "f2b89b376c56b7100ec3947ae1ccd3b468eceedcfbfe7031389bae0f8c327af1"
        ),
        "native_special_tokens_to_add": 0,
        "special_token_ids": {
            "bos_token_id": 0,
            "eos_token_id": 0,
            "pad_token_id": 1,
            "unk_token_id": 0,
        },
        "special_tokens": {
            "bos_token": "<|endoftext|>",
            "eos_token": "<|endoftext|>",
            "pad_token": "<|padding|>",
            "unk_token": "<|endoftext|>",
        },
        "tokenizer_length": 50_277,
        "verified": True,
        "vocab_size": 50_254,
    }


def _runtime_identity() -> dict[str, Any]:
    return {
        "packages": {
            "huggingface-hub": "1.28.0",
            "tokenizers": "0.22.2",
            "transformers": "5.15.1",
        },
        "python": "3.11.9",
    }


def _tokenizer_audit(
    criteria: dict[str, Any],
    registry_items: list[dict[str, Any]],
) -> dict[str, Any]:
    output_items: list[dict[str, Any]] = []
    common_counts: dict[str, int] = {}
    full_counts: list[int] = []
    for item_index, registry_item in enumerate(registry_items):
        output_forms: list[dict[str, Any]] = []
        common_counts[registry_item["item_id"]] = 3
        pole_indexes = {
            pole["id"]: pole_index
            for pole_index, pole in enumerate(registry_item["poles"])
        }
        for registry_form in registry_item["forms"]:
            context_index = 0 if registry_form["context_id"] == "context-a" else 1
            template_index = 0 if registry_form["template_id"] == "template-a" else 1
            prompt_ids = [item_index + 1, context_index + 101]
            output_candidates: list[dict[str, Any]] = []
            for registry_candidate in registry_form["candidates"]:
                pole_index = pole_indexes[registry_candidate["pole"]]
                start = 1_000 + item_index * 100 + template_index * 10 + pole_index * 3
                continuation_ids = [start, start + 1, start + 2]
                output_candidates.append(
                    {
                        "pole": registry_candidate["pole"],
                        "status": "passed",
                        "prompt_token_count": len(prompt_ids),
                        "continuation_token_count": len(continuation_ids),
                        "full_token_count": len(prompt_ids) + len(continuation_ids),
                        "continuation_start_index": len(prompt_ids),
                        "first_prediction_index": len(prompt_ids) - 1,
                        "final_prediction_index": (
                            len(prompt_ids) + len(continuation_ids) - 2
                        ),
                        "continuation_token_ids": continuation_ids,
                        "prompt_token_ids": prompt_ids,
                        "prompt_sha256": hashlib.sha256(
                            registry_form["prompt"].encode("utf-8")
                        ).hexdigest(),
                        "continuation_sha256": hashlib.sha256(
                            registry_candidate["text"].encode("utf-8")
                        ).hexdigest(),
                    }
                )
                full_counts.append(len(prompt_ids) + len(continuation_ids))
            output_forms.append(
                {
                    "form_id": registry_form["form_id"],
                    "prompt_context_match": True,
                    "continuation_token_count_difference": 0,
                    "candidates": output_candidates,
                }
            )
        output_items.append(
            {
                "item_id": registry_item["item_id"],
                "domain": registry_item["domain"],
                "forms": output_forms,
            }
        )

    loaded_validation = _loaded_validation()
    runtime_identity = _runtime_identity()
    tokenizer = criteria["tokenizer"]
    report: dict[str, Any] = {
        "schema_version": 1,
        "audit_type": "evaluation-tokenizer-audit",
        "registry_sha256": criteria["registry"]["sha256"],
        "artifact": {
            "id": tokenizer["artifact_id"],
            "revision": tokenizer["revision"],
        },
        "tokenizer": {
            "class": loaded_validation["class"],
            "name_or_path": f"{tokenizer['repository']}@{tokenizer['revision']}",
            "vocab_size": loaded_validation["vocab_size"],
            "model_max_length": loaded_validation["model_max_length"],
            "special_token_ids": loaded_validation["special_token_ids"],
        },
        "prefix_policy": tokenizer["prefix_policy"],
        "prefix_token_ids": [],
        "max_length": tokenizer["max_length"],
        "summary": {
            "item_count": len(output_items),
            "form_count": sum(len(item["forms"]) for item in output_items),
            "candidate_count": sum(
                len(form["candidates"])
                for item in output_items
                for form in item["forms"]
            ),
            "failure_count": 0,
            "max_continuation_tokens": 3,
            "max_full_tokens": max(full_counts),
            "max_within_form_token_difference": 0,
        },
        "items": output_items,
        "failures": [],
        "passed": True,
        "mode": "execute",
        "network_access_permitted": False,
        "network_observation": "not-instrumented",
        "offline_enforcement": {
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "local_files_only": True,
            "private_tokenizer_staging": True,
            "trust_remote_code": False,
        },
        "weights_downloaded": False,
        "tokenizer_files_downloaded": False,
        "model_weights_deserialized": False,
        "model_weight_bytes_verified": 2_090_701_528,
        "scientific_claim_authorized": False,
        "model_manifest_sha256": tokenizer["model_manifest_sha256"],
        "snapshot_verification": _snapshot_receipt(),
        "loaded_tokenizer_validation": loaded_validation,
        "runtime_identity": runtime_identity,
        "git_head": "a" * 40,
        "worktree_clean": True,
        "model_manifest_git_blob": tokenizer["model_manifest_git_blob"],
        "development_registry_git_blob": git_blob_sha1(
            canonical_registry_bytes(registry_items)
        ),
        "measurement_reliability_criteria_git_blob": git_blob_sha1(
            criteria_document_bytes(criteria)
        ),
        "measurement_reliability": {
            "profile_id": criteria["profile_id"],
            "criteria_sha256": criteria["criteria_sha256"],
            "common_continuation_token_counts": common_counts,
            "claim_ceiling": criteria["claim_ceiling"],
        },
    }
    report["output_sha256"] = canonical_json_sha256(report)
    return report


def _score(
    criteria: dict[str, Any],
    registry_items: list[dict[str, Any]],
    tokenizer_audit: dict[str, Any],
    *,
    reverse_cells: set[tuple[str, str, str]] | None = None,
    zero: bool = False,
    catastrophic: bool = False,
) -> dict[str, Any]:
    reverse_cells = reverse_cells or set()
    evidence_by_text: dict[tuple[str, str], tuple[list[int], list[int], bool]] = {}
    for registry_item, audit_item in zip(
        registry_items,
        tokenizer_audit["items"],
        strict=True,
    ):
        reference = registry_item["reference_pole"]
        for registry_form, audit_form in zip(
            registry_item["forms"],
            audit_item["forms"],
            strict=True,
        ):
            reverse = (
                registry_item["item_id"],
                registry_form["context_id"],
                registry_form["template_id"],
            ) in reverse_cells
            for registry_candidate, audit_candidate in zip(
                registry_form["candidates"],
                audit_form["candidates"],
                strict=True,
            ):
                key = (registry_form["prompt"], registry_candidate["text"])
                is_reference = registry_candidate["pole"] == reference
                value = (
                    list(audit_candidate["prompt_token_ids"]),
                    list(audit_candidate["continuation_token_ids"]),
                    is_reference ^ reverse,
                )
                prior = evidence_by_text.setdefault(key, value)
                assert prior == value

    def provider(prompt: str, continuation: str) -> CandidateEvidence:
        prompt_ids, continuation_ids, favored = evidence_by_text[(prompt, continuation)]
        if catastrophic:
            logprob = -1_000_000.0 if favored else -1_000_000.0000000001
        else:
            logprob = -0.2 if zero else -0.1 if favored else -0.2
        return CandidateEvidence(
            prompt_token_ids=tuple(prompt_ids),
            continuation_token_ids=tuple(continuation_ids),
            token_logprobs=tuple(logprob for _ in continuation_ids),
        )

    tokenizer = criteria["tokenizer"]
    backend = tokenizer_audit["loaded_tokenizer_validation"]["backend_sha256"]
    return score_evaluation_registry(
        registry_items,
        provider,
        registry_sha256=criteria["registry"]["sha256"],
        model_id=tokenizer["artifact_id"],
        model_revision=tokenizer["revision"],
        tokenizer_id=(
            f"{tokenizer['repository']}@{tokenizer['revision']}:"
            f"backend={backend}:prefix={tokenizer['prefix_policy']}:"
            f"max_length={tokenizer['max_length']}"
        ),
        scorer_version=criteria["scoring"]["scorer_version"],
    )


def _pretty_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def test_v0_identity_and_topology_remain_exact() -> None:
    items = load_evaluation_registry(V0)
    raw_sha256 = hashlib.sha256(V0.read_bytes()).hexdigest()

    assert raw_sha256 in {
        "3bc8874569ec0ce51e4e38e3cc58df0e37ca75da1491270695359f025bacb6f9",
        "5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d",
    }
    assert hashlib.sha256(V0.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == (
        "3bc8874569ec0ce51e4e38e3cc58df0e37ca75da1491270695359f025bacb6f9"
    )
    assert _criteria()["parent_registry"]["sha256"] == (
        "5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d"
    )
    assert len(items) == 12
    assert sum(len(item["forms"]) for item in items) == 24
    assert sum(
        len(form["candidates"])
        for item in items
        for form in item["forms"]
    ) == 48


def test_committed_v1_criteria_registry_and_generator_are_exact() -> None:
    criteria = _criteria()
    items, registry_sha256 = load_evaluation_registry_with_sha256(V1)
    spec = importlib.util.spec_from_file_location("v1_registry_builder", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert criteria["criteria_sha256"] == FROZEN_CRITERIA_SHA256
    assert registry_sha256 == criteria["registry"]["sha256"]
    assert V1.read_bytes() == module.registry_bytes()
    assert validate_reliability_criteria(criteria) == ()
    assert validate_evaluation_registry(items) == ()
    assert validate_registry_against_criteria(
        items,
        criteria,
        registry_sha256=registry_sha256,
    ) == ()
    assert len(items) == 14
    assert sum(len(item["forms"]) for item in items) == 112
    assert sum(
        len(form["candidates"])
        for item in items
        for form in item["forms"]
    ) == 224


def test_registry_validator_recomputes_object_digest() -> None:
    criteria = _criteria()
    items = deepcopy(_registry())
    items[0]["forms"][0]["prompt"] += " altered"

    errors = validate_registry_against_criteria(
        items,
        criteria,
        registry_sha256=criteria["registry"]["sha256"],
    )

    assert "registry objects do not match the supplied SHA-256" in errors


def test_factorial_registry_rejects_missing_cell_template_drift_and_checkerboard() -> None:
    criteria = _criteria()
    items = deepcopy(_registry())
    items[0]["forms"][4]["template_id"] = "template-b"
    items[1]["forms"][4]["candidates"][0]["text"] += " now"

    errors = validate_registry_against_criteria(
        items,
        criteria,
        registry_sha256=criteria["registry"]["sha256"],
    )
    assert any("both candidate orders" in error for error in errors)
    assert any("candidates must be held constant" in error for error in errors)

    checkerboard = deepcopy(_registry())
    for item in checkerboard:
        item["forms"] = [
            item["forms"][0],
            item["forms"][2],
            item["forms"][5],
            item["forms"][7],
        ]
    errors = validate_registry_against_criteria(
        checkerboard,
        criteria,
        registry_sha256=criteria["registry"]["sha256"],
    )
    assert any("exactly eight forms" in error for error in errors)


def test_factorial_registry_rejects_unbalanced_order() -> None:
    criteria = _criteria()
    items = deepcopy(_registry())
    items[0]["forms"][0]["candidates"].reverse()

    errors = validate_registry_against_criteria(
        items,
        criteria,
        registry_sha256=criteria["registry"]["sha256"],
    )
    assert any("candidate order is not exactly 4/4" in error for error in errors)


def test_factorial_registry_rejects_factor_metadata_aliases() -> None:
    criteria = _criteria()
    items = deepcopy(_registry())
    for form in items[0]["forms"]:
        form["context_id"] = (
            "alpha" if form["context_id"] == "context-a" else "beta"
        )

    errors = validate_registry_against_criteria(
        items,
        criteria,
        registry_sha256=criteria["registry"]["sha256"],
    )
    assert any("context factors are not canonical" in error for error in errors)
    assert any("form identity does not match" in error for error in errors)


def test_criteria_rejects_pinned_drift_unknown_fields_and_type_aliases() -> None:
    criteria = _criteria()
    changed = deepcopy(criteria)
    changed["claim_ceiling"] += " altered"
    changed["criteria_sha256"] = canonical_json_sha256(
        {key: value for key, value in changed.items() if key != "criteria_sha256"}
    )
    assert "criteria identity differs from the independently pinned profile" in (
        validate_reliability_criteria(changed)
    )

    changed = deepcopy(criteria)
    changed["unexpected"] = True
    assert any(
        "unexpected fields" in error
        for error in validate_reliability_criteria(changed)
    )

    changed = deepcopy(criteria)
    changed["registry"]["item_count"] = 14.0
    changed["criteria_sha256"] = canonical_json_sha256(
        {key: value for key, value in changed.items() if key != "criteria_sha256"}
    )
    assert any(
        "registry.item_count" in error
        for error in validate_reliability_criteria(changed)
    )


def test_json_artifact_loader_rejects_nested_duplicate_keys(tmp_path: Path) -> None:
    artifact = tmp_path / "duplicate.json"
    artifact.write_text('{"outer":{"value":1,"value":2}}', encoding="utf-8")

    try:
        load_json_artifact(artifact, "fixture")
    except MeasurementReliabilityError as error:
        assert "duplicate JSON key: value" in str(error)
    else:
        raise AssertionError("duplicate nested JSON key was accepted")


def test_tokenizer_audit_exact_fixture_passes_and_binds_16_counts_per_item() -> None:
    criteria = _criteria()
    items = _registry()
    audit = _tokenizer_audit(criteria, items)

    assert _snapshot_receipt()["receipt_sha256"] == criteria["tokenizer"][
        "snapshot_receipt_sha256"
    ]
    assert canonical_json_sha256(_loaded_validation()) == criteria["tokenizer"][
        "loaded_validation_sha256"
    ]
    assert canonical_json_sha256(_runtime_identity()) == criteria["tokenizer"][
        "runtime_identity_sha256"
    ]
    assert validate_tokenizer_audit_against_criteria(audit, criteria, items) == ()
    assert audit["summary"] == {
        "item_count": 14,
        "form_count": 112,
        "candidate_count": 224,
        "failure_count": 0,
        "max_continuation_tokens": 3,
        "max_full_tokens": 5,
        "max_within_form_token_difference": 0,
    }


def test_tokenizer_audit_rejects_binding_index_summary_and_schema_drift() -> None:
    criteria = _criteria()
    items = _registry()
    base = _tokenizer_audit(criteria, items)
    mutations = []

    changed = deepcopy(base)
    changed["items"][0]["forms"][0]["candidates"][0]["prompt_sha256"] = "0" * 64
    mutations.append((changed, "prompt binding mismatch"))

    changed = deepcopy(base)
    changed["items"][0]["forms"][0]["candidates"][0]["final_prediction_index"] += 1
    mutations.append((changed, "token index arithmetic mismatch"))

    changed = deepcopy(base)
    changed["items"][0]["forms"][0]["candidates"][0][
        "continuation_token_count"
    ] = 4
    mutations.append((changed, "does not have one common token count"))

    changed = deepcopy(base)
    changed["summary"]["candidate_count"] = 223
    mutations.append((changed, "summary does not match"))

    changed = deepcopy(base)
    changed["items"][0]["forms"][0]["candidates"][0]["extra"] = True
    mutations.append((changed, "candidate fields are not exact"))

    changed = deepcopy(base)
    changed["measurement_reliability"]["common_continuation_token_counts"][
        items[0]["item_id"]
    ] = 4
    mutations.append((changed, "measurement-reliability binding mismatch"))

    changed = deepcopy(base)
    for form_index in (2, 3):
        for candidate in changed["items"][0]["forms"][form_index]["candidates"]:
            candidate["prompt_token_ids"] = [999, 998]
    mutations.append((changed, "differ across templates/orders for one context"))

    changed = deepcopy(base)
    changed["items"][0]["forms"][0]["candidates"][0][
        "continuation_token_ids"
    ][0] = 50_277
    mutations.append((changed, "token ID exceeds the loaded tokenizer length"))

    changed = deepcopy(base)
    for form_index in range(4, 8):
        for candidate in changed["items"][0]["forms"][form_index]["candidates"]:
            candidate["continuation_token_ids"] = [
                token_id + 100
                for token_id in candidate["continuation_token_ids"]
            ]
    mutations.append((changed, "identical continuation text has inconsistent token IDs"))

    for changed, expected in mutations:
        changed["output_sha256"] = canonical_json_sha256(
            {key: value for key, value in changed.items() if key != "output_sha256"}
        )
        errors = validate_tokenizer_audit_against_criteria(changed, criteria, items)
        assert any(expected in error for error in errors), (expected, errors)


def test_tokenizer_audit_rejects_forged_git_identities() -> None:
    criteria = _criteria()
    items = _registry()
    base = _tokenizer_audit(criteria, items)
    expected_errors = {
        "model_manifest_git_blob": "model-manifest Git blob identity mismatch",
        "development_registry_git_blob": "registry Git blob identity mismatch",
        "measurement_reliability_criteria_git_blob": (
            "criteria Git blob identity mismatch"
        ),
    }
    for field, expected in expected_errors.items():
        changed = deepcopy(base)
        changed[field] = "0" * 40
        changed["output_sha256"] = canonical_json_sha256(
            {key: value for key, value in changed.items() if key != "output_sha256"}
        )
        errors = validate_tokenizer_audit_against_criteria(
            changed,
            criteria,
            items,
        )
        assert any(expected in error for error in errors), (field, errors)

    errors = validate_tokenizer_audit_against_criteria(
        base,
        criteria,
        items,
        expected_git_head="e" * 40,
    )
    assert "tokenizer audit Git head differs from the verification head" in errors


def test_tokenizer_audit_rejects_invalid_self_hash_and_absolute_path() -> None:
    criteria = _criteria()
    items = _registry()
    audit = _tokenizer_audit(criteria, items)
    audit["output_sha256"] = "0" * 64
    assert "tokenizer audit self-hash is invalid" in (
        validate_tokenizer_audit_against_criteria(audit, criteria, items)
    )

    audit = _tokenizer_audit(criteria, items)
    audit["runtime_identity"]["leak"] = r"C:\private\snapshot"
    audit["output_sha256"] = canonical_json_sha256(
        {key: value for key, value in audit.items() if key != "output_sha256"}
    )
    assert "tokenizer audit contains an absolute local path" in (
        validate_tokenizer_audit_against_criteria(audit, criteria, items)
    )


def test_score_coherence_recomputes_evidence_and_requires_eight_same_signs() -> None:
    criteria = _criteria()
    items = _registry()
    audit = _tokenizer_audit(criteria, items)
    score = _score(criteria, items, audit)

    report = analyze_score_coherence(score, criteria, items, audit)
    assert report["passed"] is True
    assert report["failures"] == []
    assert report["output_sha256"] == canonical_json_sha256(
        {key: value for key, value in report.items() if key != "output_sha256"}
    )

    reverse_cell = {
        (
            items[0]["item_id"],
            items[0]["forms"][0]["context_id"],
            items[0]["forms"][0]["template_id"],
        )
    }
    reversed_score = _score(
        criteria,
        items,
        audit,
        reverse_cells=reverse_cell,
    )
    reversed_report = analyze_score_coherence(
        reversed_score,
        criteria,
        items,
        audit,
    )
    assert reversed_report["passed"] is False
    assert any(
        failure["error"] == "eight form margins do not share one nonzero sign"
        for failure in reversed_report["failures"]
    )

    zero_score = _score(criteria, items, audit, zero=True)
    zero_report = analyze_score_coherence(zero_score, criteria, items, audit)
    assert zero_report["passed"] is False
    assert any(
        failure["error"] == "primary margin is exactly zero"
        for failure in zero_report["failures"]
    )

    catastrophic_score = _score(
        criteria,
        items,
        audit,
        catastrophic=True,
    )
    catastrophic_report = analyze_score_coherence(
        catastrophic_score,
        criteria,
        items,
        audit,
    )
    assert catastrophic_report["passed"] is False
    assert any(
        "margin is inconsistent with total margin/common token count"
        in failure["error"]
        for failure in catastrophic_report["failures"]
    )


def test_score_coherence_rejects_coherently_rehashed_candidate_and_pairwise_forgery() -> None:
    criteria = _criteria()
    items = _registry()
    audit = _tokenizer_audit(criteria, items)
    score = _score(criteria, items, audit)

    candidate_forgery = deepcopy(score)
    candidate_forgery["items"][0]["forms"][0]["candidates"][0][
        "total_logprob"
    ] = -999.0
    candidate_forgery["output_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in candidate_forgery.items()
            if key != "output_sha256"
        }
    )
    report = analyze_score_coherence(candidate_forgery, criteria, items, audit)
    assert any(
        failure["error"]
        == "score candidate aggregates do not match token log probabilities"
        for failure in report["failures"]
    )

    pairwise_forgery = deepcopy(score)
    pairwise_forgery["items"][0]["forms"][0]["pairwise"][
        "total_logprob_margin"
    ] = 999.0
    pairwise_forgery["output_sha256"] = canonical_json_sha256(
        {
            key: value
            for key, value in pairwise_forgery.items()
            if key != "output_sha256"
        }
    )
    report = analyze_score_coherence(pairwise_forgery, criteria, items, audit)
    assert any(
        failure["error"] == "score pairwise values do not match candidate evidence"
        for failure in report["failures"]
    )


@pytest.mark.parametrize(
    ("artifact", "path", "expected_scope"),
    [
        ("score", ("scorer", "version"), "score"),
        ("score", ("model", "id"), "score"),
        ("score", ("model", "revision"), "score"),
        ("score", ("model", "tokenizer_id"), "score"),
        ("score", ("registry_sha256",), "score"),
        ("tokenizer", ("artifact", "id"), "tokenizer"),
        ("tokenizer", ("artifact", "revision"), "tokenizer"),
    ],
)
def test_score_coherence_rejects_cross_profile_identity_substitution(
    artifact: str,
    path: tuple[str, ...],
    expected_scope: str,
) -> None:
    criteria = _criteria()
    items = _registry()
    audit = _tokenizer_audit(criteria, items)
    score = _score(criteria, items, audit)
    changed = score if artifact == "score" else audit
    cursor: dict[str, Any] = changed
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = "substituted-profile"
    changed["output_sha256"] = canonical_json_sha256(
        {key: value for key, value in changed.items() if key != "output_sha256"}
    )

    report = analyze_score_coherence(score, criteria, items, audit)

    assert report["passed"] is False
    assert any(
        failure["scope"] == expected_scope and "identity mismatch" in failure["error"]
        for failure in report["failures"]
    )


def test_score_repeat_is_byte_strict_and_cannot_pass_before_receipt_integration() -> None:
    criteria = _criteria()
    items = _registry()
    audit = _tokenizer_audit(criteria, items)
    score = _score(criteria, items, audit)
    score_bytes = _pretty_bytes(score)

    report = analyze_score_repeat(
        score,
        deepcopy(score),
        criteria,
        items,
        audit,
        score_a_bytes=score_bytes,
        score_b_bytes=score_bytes,
    )
    assert report["passed"] is False
    assert report["failures"] == [
        "execution-order receipts are not integrated until E3"
    ]
    assert report["execution_mode_receipts_validated"] is False

    noncanonical = json.dumps(score, sort_keys=True).encode("utf-8")
    report = analyze_score_repeat(
        score,
        score,
        criteria,
        items,
        audit,
        score_a_bytes=score_bytes,
        score_b_bytes=noncanonical,
    )
    assert "score artifacts are not canonical pretty JSON bytes" in report["failures"]
    assert "canonical/reverse score artifacts are not byte-identical" in report[
        "failures"
    ]
