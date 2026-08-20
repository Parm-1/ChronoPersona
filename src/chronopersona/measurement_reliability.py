"""Closed, dependency-light checks for development measurement coherence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
from typing import Any

from .evaluation import (
    canonical_json_sha256,
    validate_evaluation_registry,
)
from .file_integrity import stable_read_unchanged
from .scoring import (
    CandidateEvidence,
    ScoringIntegrityError,
    aggregate_form_scores,
    pairwise_score,
    score_candidate,
)
from .scoring_runtime import ScoringRunError, verify_scoring_repeat


class MeasurementReliabilityError(ValueError):
    """Raised when reliability evidence is malformed or fails closed."""


PROFILE_ID = "development-v1-pythia-reliability-v0"
FROZEN_CRITERIA_SHA256 = (
    "d73b9d4d575f64587c5aea9acc18a6073a42bb1bd70491d29bd8422e95a73bca"
)
_TOP_LEVEL_KEYS = {
    "schema_version",
    "profile_id",
    "parent_registry",
    "registry",
    "tokenizer",
    "scoring",
    "rescue",
    "claim_ceiling",
    "criteria_sha256",
}
_PARENT_KEYS = {"path", "sha256"}
_REGISTRY_KEYS = {
    "path",
    "sha256",
    "status",
    "item_count",
    "form_count",
    "candidate_count",
    "forms_per_item",
    "candidate_order_counts",
    "reference_pole_positions",
    "domain_item_counts",
    "required_item_ids",
}
_ORDER_KEYS = {"forward", "reverse"}
_TOKENIZER_KEYS = {
    "artifact_id",
    "repository",
    "revision",
    "prefix_policy",
    "max_length",
    "minimum_common_continuation_tokens",
    "maximum_common_continuation_tokens",
    "maximum_failure_count",
    "model_manifest_sha256",
    "model_manifest_git_blob",
    "snapshot_receipt_sha256",
    "loaded_validation_sha256",
    "runtime_identity_sha256",
}
_SCORING_KEYS = {
    "scorer_version",
    "primary_metric",
    "diagnostic_metric",
    "minimum_directional_agreement",
    "zero_margin_policy",
    "require_primary_diagnostic_sign_match",
    "relation_rel_tol",
    "relation_abs_tol",
    "required_execution_modes",
    "require_exact_score_byte_equality",
}
_RESCUE_KEYS = {
    "maximum_content_rescues",
    "maximum_implementation_rescues",
}
_TOKENIZER_AUDIT_KEYS = {
    "schema_version",
    "audit_type",
    "registry_sha256",
    "artifact",
    "tokenizer",
    "prefix_policy",
    "prefix_token_ids",
    "max_length",
    "summary",
    "items",
    "failures",
    "passed",
    "mode",
    "network_access_permitted",
    "network_observation",
    "offline_enforcement",
    "weights_downloaded",
    "tokenizer_files_downloaded",
    "model_weights_deserialized",
    "model_weight_bytes_verified",
    "scientific_claim_authorized",
    "model_manifest_sha256",
    "snapshot_verification",
    "loaded_tokenizer_validation",
    "runtime_identity",
    "git_head",
    "worktree_clean",
    "model_manifest_git_blob",
    "development_registry_git_blob",
    "measurement_reliability_criteria_git_blob",
    "measurement_reliability",
    "output_sha256",
}
_TOKENIZER_SUMMARY_KEYS = {
    "item_count",
    "form_count",
    "candidate_count",
    "failure_count",
    "max_continuation_tokens",
    "max_full_tokens",
    "max_within_form_token_difference",
}
_TOKENIZER_ITEM_KEYS = {"item_id", "domain", "forms"}
_TOKENIZER_FORM_KEYS = {
    "form_id",
    "prompt_context_match",
    "continuation_token_count_difference",
    "candidates",
}
_TOKENIZER_CANDIDATE_KEYS = {
    "pole",
    "status",
    "prompt_token_count",
    "continuation_token_count",
    "full_token_count",
    "continuation_start_index",
    "first_prediction_index",
    "final_prediction_index",
    "continuation_token_ids",
    "prompt_token_ids",
    "prompt_sha256",
    "continuation_sha256",
}
_BASE_SCORE_KEYS = {
    "schema_version",
    "scorer",
    "registry_sha256",
    "model",
    "items",
    "output_sha256",
}
_FINAL_SCORE_KEYS = _BASE_SCORE_KEYS | {
    "status",
    "score_type",
    "scientific_claim_authorized",
    "contract",
    "summary",
}
_SCORE_SCORER_KEYS = {
    "version",
    "primary_metric",
    "diagnostic_metric",
    "generated_explanations_used",
}
_SCORE_MODEL_KEYS = {"id", "revision", "tokenizer_id"}
_SCORE_ITEM_KEYS = {
    "item_id",
    "domain",
    "construct",
    "reference_pole",
    "forms",
    "aggregate",
}
_SCORE_FORM_KEYS = {
    "form_id",
    "candidate_display_order",
    "candidates",
    "pairwise",
}
_SCORE_CANDIDATE_KEYS = {
    "pole",
    "total_logprob",
    "mean_logprob",
    "token_count",
    "prompt_token_count",
    "prompt_token_ids",
    "continuation_token_ids",
    "token_logprobs",
}
_SCORE_PAIRWISE_KEYS = {
    "reference_pole",
    "comparison_pole",
    "total_logprob_margin",
    "mean_logprob_margin",
    "probability_reference",
}
_SCORE_AGGREGATE_KEYS = {
    "reference_pole",
    "comparison_pole",
    "form_count",
    "mean_total_logprob_margin",
    "mean_mean_logprob_margin",
    "total_logprob_margin_sd",
    "directional_agreement",
    "probability_reference_from_mean_margin",
}


def _exact_keys(
    value: Any,
    expected: set[str],
    label: str,
) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{label} must be an object"]
    actual = set(value)
    errors: list[str] = []
    missing = expected - actual
    extra = actual - expected
    if missing:
        errors.append(f"{label} missing fields: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{label} has unexpected fields: {', '.join(sorted(extra))}")
    return errors


def _int(value: Any) -> bool:
    return type(value) is int


def _number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _hex_identity(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _token_ids(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_int(token_id) and token_id >= 0 for token_id in value)
    )


def _json_equal(left: Any, right: Any) -> bool:
    try:
        return json.dumps(
            left,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) == json.dumps(
            right,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return False


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            yield from _strings(key)
            yield from _strings(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            yield from _strings(nested)


def _contains_absolute_path(value: Any) -> bool:
    for candidate in _strings(value):
        if Path(candidate).is_absolute() or PureWindowsPath(candidate).is_absolute():
            return True
    return False


def _self_hash_valid(value: Mapping[str, Any], field: str) -> bool:
    recorded = value.get(field)
    if not _sha256(recorded):
        return False
    body = dict(value)
    body.pop(field, None)
    return recorded == canonical_json_sha256(body)


def canonical_registry_bytes(
    items: Sequence[Mapping[str, Any]],
) -> bytes:
    """Render the exact canonical JSONL representation used by development-v1."""

    return (
        "\n".join(
            json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            for item in items
        )
        + "\n"
    ).encode("utf-8")


def criteria_document_bytes(criteria: Mapping[str, Any]) -> bytes:
    """Render the frozen criteria file without leaking a checkout path."""

    return (
        json.dumps(
            dict(criteria),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def git_blob_sha1(payload: bytes) -> str:
    """Return the Git blob identity for exact file bytes."""

    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _load_json_artifact(
    path: str | Path,
    label: str,
) -> tuple[dict[str, Any], bytes, str]:
    selected = Path(path)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise MeasurementReliabilityError(
                    f"{label} contains duplicate JSON key: {key}"
                )
            output[key] = value
        return output

    before = selected.stat()
    with open(selected, "rb") as handle:
        opened = handle.fileno()
        descriptor_before = os.fstat(opened)
        payload = handle.read()
        descriptor_after = os.fstat(opened)
    after = selected.stat()
    if not stable_read_unchanged(
        before,
        descriptor_before,
        descriptor_after,
        after,
    ):
        raise MeasurementReliabilityError(f"{label} changed while it was read")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MeasurementReliabilityError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise MeasurementReliabilityError(f"{label} must be a JSON object")
    return value, payload, hashlib.sha256(payload).hexdigest()


def _load_json_object(path: str | Path, label: str) -> dict[str, Any]:
    value, _, _ = _load_json_artifact(path, label)
    return value


def load_json_object(path: str | Path, label: str) -> dict[str, Any]:
    """Load one stable, duplicate-free JSON object."""

    return _load_json_object(path, label)


def load_json_artifact(
    path: str | Path,
    label: str,
) -> tuple[dict[str, Any], bytes, str]:
    """Load one stable JSON object together with the exact bound bytes/hash."""

    return _load_json_artifact(path, label)


def validate_reliability_criteria(criteria: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate the exact v1 Pythia coherence contract."""

    errors = _exact_keys(criteria, _TOP_LEVEL_KEYS, "criteria")
    if errors:
        return tuple(errors)
    if criteria.get("schema_version") != 1 or type(criteria.get("schema_version")) is not int:
        errors.append("criteria schema_version must be integer 1")
    if criteria.get("profile_id") != PROFILE_ID:
        errors.append(f"criteria profile_id must be {PROFILE_ID!r}")
    if not _self_hash_valid(criteria, "criteria_sha256"):
        errors.append("criteria self-hash is invalid")
    if criteria.get("criteria_sha256") != FROZEN_CRITERIA_SHA256:
        errors.append("criteria identity differs from the independently pinned profile")

    parent = criteria.get("parent_registry")
    errors.extend(_exact_keys(parent, _PARENT_KEYS, "parent_registry"))
    if isinstance(parent, Mapping):
        if parent.get("path") != "evaluations/registry/development-v0.jsonl":
            errors.append("parent_registry.path is not the preserved v0 registry")
        if parent.get("sha256") != (
            "5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d"
        ):
            errors.append("parent_registry.sha256 is not the preserved v0 identity")

    registry = criteria.get("registry")
    errors.extend(_exact_keys(registry, _REGISTRY_KEYS, "registry"))
    if isinstance(registry, Mapping):
        expected = {
            "path": "evaluations/registry/development-v1.jsonl",
            "status": "development",
            "item_count": 14,
            "form_count": 112,
            "candidate_count": 224,
            "forms_per_item": 8,
        }
        for key, expected_value in expected.items():
            if registry.get(key) != expected_value or (
                isinstance(expected_value, int) and not _int(registry.get(key))
            ):
                errors.append(f"registry.{key} must be {expected_value!r}")
        if not _sha256(registry.get("sha256")):
            errors.append("registry.sha256 must be lowercase SHA-256")
        order = registry.get("candidate_order_counts")
        errors.extend(_exact_keys(order, _ORDER_KEYS, "registry.candidate_order_counts"))
        if isinstance(order, Mapping) and (
            order.get("forward") != 4
            or order.get("reverse") != 4
            or not _int(order.get("forward"))
            or not _int(order.get("reverse"))
        ):
            errors.append("registry candidate orders must be exactly 4 forward / 4 reverse")
        domains = registry.get("domain_item_counts")
        expected_domains = {
            "evidence-integration": 6,
            "procedural-tradeoffs": 8,
        }
        if not isinstance(domains, Mapping) or dict(domains) != expected_domains:
            errors.append("registry.domain_item_counts must be the exact 6/8 primary-domain map")
        reference_positions = registry.get("reference_pole_positions")
        if not _json_equal(reference_positions, {"first": 7, "second": 7}):
            errors.append("registry reference-pole positions must be exactly 7 first / 7 second")
        item_ids = registry.get("required_item_ids")
        if (
            not isinstance(item_ids, list)
            or len(item_ids) != 14
            or len(set(item_ids)) != 14
            or not all(isinstance(item_id, str) and item_id for item_id in item_ids)
        ):
            errors.append("registry.required_item_ids must contain 14 unique strings")

    tokenizer = criteria.get("tokenizer")
    errors.extend(_exact_keys(tokenizer, _TOKENIZER_KEYS, "tokenizer"))
    if isinstance(tokenizer, Mapping):
        expected = {
            "artifact_id": "pythia-1b-deduped-main",
            "repository": "EleutherAI/pythia-1b-deduped",
            "revision": "7199d8fc61a6d565cd1f3c62bf11525b563e13b2",
            "prefix_policy": "none",
            "max_length": 2048,
            "minimum_common_continuation_tokens": 1,
            "maximum_common_continuation_tokens": 24,
            "maximum_failure_count": 0,
            "model_manifest_sha256": "f3a800e95887b96ec66a660efa51ab975b17b7ec1ada0f381f502e912d9cf4f6",
            "model_manifest_git_blob": "2dbafc0d0fe10a717e1df3d5c7920e6af661138b",
            "snapshot_receipt_sha256": "26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc",
            "loaded_validation_sha256": "e4128adadf87e0b6250e39b8c5409db704d968deee6dd8da671dcda02da875eb",
            "runtime_identity_sha256": "62d2bf7a6341ad42fd3f7042f35d05c2942a56a569a39303df5e3c81cd8c1156",
        }
        for key, expected_value in expected.items():
            if tokenizer.get(key) != expected_value or (
                isinstance(expected_value, int) and not _int(tokenizer.get(key))
            ):
                errors.append(f"tokenizer.{key} must be {expected_value!r}")

    scoring = criteria.get("scoring")
    errors.extend(_exact_keys(scoring, _SCORING_KEYS, "scoring"))
    if isinstance(scoring, Mapping):
        expected = {
            "scorer_version": "complete-continuation-v0",
            "primary_metric": "complete-continuation-total-logprob",
            "diagnostic_metric": "mean-token-logprob",
            "minimum_directional_agreement": 1.0,
            "zero_margin_policy": "fail",
            "require_primary_diagnostic_sign_match": True,
            "relation_rel_tol": 1e-12,
            "relation_abs_tol": 1e-12,
            "required_execution_modes": ["canonical", "reverse"],
            "require_exact_score_byte_equality": True,
        }
        for key, expected_value in expected.items():
            actual = scoring.get(key)
            if actual != expected_value or (
                isinstance(expected_value, bool) and type(actual) is not bool
            ) or (
                isinstance(expected_value, float) and type(actual) is not float
            ):
                errors.append(f"scoring.{key} must be {expected_value!r}")
        for key in ("minimum_directional_agreement", "relation_rel_tol", "relation_abs_tol"):
            if not _number(scoring.get(key)):
                errors.append(f"scoring.{key} must be a finite number")

    rescue = criteria.get("rescue")
    errors.extend(_exact_keys(rescue, _RESCUE_KEYS, "rescue"))
    if isinstance(rescue, Mapping):
        if rescue.get("maximum_content_rescues") != 0 or not _int(
            rescue.get("maximum_content_rescues")
        ):
            errors.append("rescue.maximum_content_rescues must be integer 0")
        if rescue.get("maximum_implementation_rescues") != 1 or not _int(
            rescue.get("maximum_implementation_rescues")
        ):
            errors.append("rescue.maximum_implementation_rescues must be integer 1")
    if not isinstance(criteria.get("claim_ceiling"), str) or not criteria["claim_ceiling"].strip():
        errors.append("criteria.claim_ceiling must be a non-empty string")
    return tuple(errors)


def load_reliability_criteria(path: str | Path) -> dict[str, Any]:
    criteria = _load_json_object(path, "measurement reliability criteria")
    errors = validate_reliability_criteria(criteria)
    if errors:
        raise MeasurementReliabilityError("; ".join(errors))
    return criteria


def validate_registry_against_criteria(
    items: Sequence[Mapping[str, Any]],
    criteria: Mapping[str, Any],
    *,
    registry_sha256: str,
) -> tuple[str, ...]:
    """Validate the exact v1 factorial registry without tokenizing it."""

    errors = list(validate_reliability_criteria(criteria))
    errors.extend(validate_evaluation_registry(items))
    registry = criteria.get("registry")
    if not isinstance(registry, Mapping):
        return tuple(errors)
    try:
        rendered_registry = canonical_registry_bytes(items)
    except (TypeError, ValueError):
        errors.append("registry objects cannot be rendered as canonical JSONL")
    else:
        if hashlib.sha256(rendered_registry).hexdigest() != registry_sha256:
            errors.append("registry objects do not match the supplied SHA-256")
    if registry_sha256 != registry.get("sha256"):
        errors.append("registry SHA-256 does not match the frozen criteria")
    if len(items) != registry.get("item_count"):
        errors.append("registry item count does not match the frozen criteria")
    actual_ids = [item.get("item_id") for item in items]
    if actual_ids != registry.get("required_item_ids"):
        errors.append("registry item order/identity does not match the frozen criteria")
    domain_counts = Counter(item.get("domain") for item in items)
    if dict(domain_counts) != registry.get("domain_item_counts"):
        errors.append("registry domain counts do not match the frozen criteria")
    reference_positions = Counter()
    for item in items:
        poles = item.get("poles")
        if not isinstance(poles, list) or len(poles) != 2:
            continue
        if item.get("reference_pole") == poles[0].get("id"):
            reference_positions["first"] += 1
        elif item.get("reference_pole") == poles[1].get("id"):
            reference_positions["second"] += 1
    if not _json_equal(
        dict(reference_positions),
        registry.get("reference_pole_positions"),
    ):
        errors.append("registry reference-pole coding is not the frozen 7/7 schedule")

    total_forms = 0
    total_candidates = 0
    for item in items:
        item_id = item.get("item_id")
        if item.get("status") != registry.get("status"):
            errors.append(f"item {item_id!r} status differs from the frozen criteria")
        forms = item.get("forms")
        if not isinstance(forms, list):
            continue
        total_forms += len(forms)
        if len(forms) != registry.get("forms_per_item"):
            errors.append(f"item {item_id!r} must contain exactly eight forms")
            continue
        combinations: dict[tuple[str, str], list[tuple[str, str]]] = {}
        contexts: dict[str, list[Mapping[str, Any]]] = {}
        templates: dict[str, list[Mapping[str, Any]]] = {}
        pole_ids = [pole.get("id") for pole in item.get("poles", []) if isinstance(pole, Mapping)]
        forward = tuple(pole_ids)
        reverse = tuple(reversed(pole_ids))
        order_counts = Counter()
        expected_form_ids = [
            f"{context_id}-{template_id}-{order_name}"
            for context_id in ("context-a", "context-b")
            for template_id in ("template-a", "template-b")
            for order_name in ("forward", "reverse")
        ]
        if [form.get("form_id") for form in forms] != expected_form_ids:
            errors.append(f"item {item_id!r} form identities/order are not canonical")
        for form in forms:
            if not isinstance(form, Mapping):
                continue
            context_id = form.get("context_id")
            template_id = form.get("template_id")
            if not isinstance(context_id, str) or not isinstance(template_id, str):
                errors.append(f"item {item_id!r} form factors must be strings")
                continue
            combination = (context_id, template_id)
            combinations.setdefault(combination, [])
            contexts.setdefault(context_id, []).append(form)
            templates.setdefault(template_id, []).append(form)
            candidates = form.get("candidates")
            if isinstance(candidates, list):
                total_candidates += len(candidates)
                order = tuple(
                    candidate.get("pole")
                    for candidate in candidates
                    if isinstance(candidate, Mapping)
                )
                if order == forward:
                    order_counts["forward"] += 1
                    combinations[combination].append(order)
                    order_name = "forward"
                elif order == reverse:
                    order_counts["reverse"] += 1
                    combinations[combination].append(order)
                    order_name = "reverse"
                else:
                    order_name = None
                if order_name is not None and form.get("form_id") != (
                    f"{context_id}-{template_id}-{order_name}"
                ):
                    errors.append(
                        f"item {item_id!r} form identity does not match its factors/order"
                    )
        if set(contexts) != {"context-a", "context-b"}:
            errors.append(f"item {item_id!r} context factors are not canonical")
        if set(templates) != {"template-a", "template-b"}:
            errors.append(f"item {item_id!r} template factors are not canonical")
        if len(contexts) != 2 or any(len(group) != 4 for group in contexts.values()):
            errors.append(f"item {item_id!r} must contain two contexts used four times each")
        if len(templates) != 2 or any(len(group) != 4 for group in templates.values()):
            errors.append(f"item {item_id!r} must contain two templates used four times each")
        if len(combinations) != 4:
            errors.append(f"item {item_id!r} must contain every context/template combination")
        for combination, orders in combinations.items():
            if orders != [forward, reverse] and orders != [reverse, forward]:
                errors.append(
                    f"item {item_id!r} cell {combination!r} must contain both candidate orders"
                )
        for context_id, group in contexts.items():
            prompts = {form.get("prompt") for form in group}
            if len(prompts) != 1:
                errors.append(f"item {item_id!r} context {context_id!r} prompt must be held constant")
        if len({next(iter({form.get('prompt') for form in group}), None) for group in contexts.values()}) != 2:
            errors.append(f"item {item_id!r} context prompts must be distinct")
        for template_id, group in templates.items():
            by_form: list[dict[str, str]] = []
            for form in group:
                candidates = form.get("candidates")
                if isinstance(candidates, list):
                    by_form.append(
                        {
                            str(candidate.get("pole")): str(candidate.get("text"))
                            for candidate in candidates
                            if isinstance(candidate, Mapping)
                        }
                    )
            if len(by_form) != 4 or any(value != by_form[0] for value in by_form[1:]):
                errors.append(f"item {item_id!r} template {template_id!r} candidates must be held constant")
        template_maps = []
        for group in templates.values():
            first = group[0].get("candidates") if group else None
            if isinstance(first, list):
                template_maps.append(
                    {
                        str(candidate.get("pole")): str(candidate.get("text"))
                        for candidate in first
                        if isinstance(candidate, Mapping)
                    }
                )
        if len(template_maps) == 2 and template_maps[0] == template_maps[1]:
            errors.append(f"item {item_id!r} candidate templates must be distinct")
        expected_order = registry.get("candidate_order_counts")
        if dict(order_counts) != expected_order:
            errors.append(f"item {item_id!r} candidate order is not exactly 4/4")
    if total_forms != registry.get("form_count"):
        errors.append("registry form count does not match the frozen criteria")
    if total_candidates != registry.get("candidate_count"):
        errors.append("registry candidate count does not match the frozen criteria")
    return tuple(dict.fromkeys(errors))


def validate_tokenizer_audit_against_criteria(
    audit: Mapping[str, Any],
    criteria: Mapping[str, Any],
    registry_items: Sequence[Mapping[str, Any]],
    *,
    expected_git_head: str | None = None,
) -> tuple[str, ...]:
    """Require complete exact-token evidence for every v1 item."""

    errors = list(validate_reliability_criteria(criteria))
    registry_identity = criteria.get("registry", {}).get("sha256")
    errors.extend(
        validate_registry_against_criteria(
            registry_items,
            criteria,
            registry_sha256=str(registry_identity),
        )
    )
    errors.extend(_exact_keys(audit, _TOKENIZER_AUDIT_KEYS, "tokenizer audit"))
    if not _self_hash_valid(audit, "output_sha256"):
        errors.append("tokenizer audit self-hash is invalid")
    registry = criteria.get("registry", {})
    tokenizer = criteria.get("tokenizer", {})
    required_root = {
        "schema_version": 1,
        "audit_type": "evaluation-tokenizer-audit",
        "mode": "execute",
        "registry_sha256": registry.get("sha256"),
        "prefix_policy": tokenizer.get("prefix_policy"),
        "prefix_token_ids": [],
        "max_length": tokenizer.get("max_length"),
        "passed": True,
        "failures": [],
        "network_access_permitted": False,
        "network_observation": "not-instrumented",
        "weights_downloaded": False,
        "tokenizer_files_downloaded": False,
        "model_weights_deserialized": False,
        "scientific_claim_authorized": False,
        "model_manifest_sha256": tokenizer.get("model_manifest_sha256"),
        "worktree_clean": True,
    }
    for key, expected in required_root.items():
        if not _json_equal(audit.get(key), expected):
            errors.append(f"tokenizer audit root mismatch: {key}")
    for key in (
        "schema_version",
        "max_length",
        "model_weight_bytes_verified",
    ):
        if not _int(audit.get(key)):
            errors.append(f"tokenizer audit {key} must be an integer")
    for key in (
        "git_head",
        "model_manifest_git_blob",
        "development_registry_git_blob",
        "measurement_reliability_criteria_git_blob",
    ):
        if not _hex_identity(audit.get(key), 40):
            errors.append(f"tokenizer audit {key} must be a lowercase Git identity")
    if expected_git_head is not None:
        if not _hex_identity(expected_git_head, 40):
            errors.append("expected Git head must be a lowercase Git identity")
        elif audit.get("git_head") != expected_git_head:
            errors.append("tokenizer audit Git head differs from the verification head")
    try:
        expected_registry_blob = git_blob_sha1(
            canonical_registry_bytes(registry_items)
        )
        expected_criteria_blob = git_blob_sha1(
            criteria_document_bytes(criteria)
        )
    except (TypeError, ValueError):
        errors.append("tokenizer audit Git inputs cannot be rendered canonically")
    else:
        if audit.get("development_registry_git_blob") != expected_registry_blob:
            errors.append("tokenizer audit registry Git blob identity mismatch")
        if (
            audit.get("measurement_reliability_criteria_git_blob")
            != expected_criteria_blob
        ):
            errors.append("tokenizer audit criteria Git blob identity mismatch")
    if audit.get("model_manifest_git_blob") != tokenizer.get(
        "model_manifest_git_blob"
    ):
        errors.append("tokenizer audit model-manifest Git blob identity mismatch")
    if _contains_absolute_path(audit):
        errors.append("tokenizer audit contains an absolute local path")

    if audit.get("registry_sha256") != registry.get("sha256"):
        errors.append("tokenizer audit registry identity mismatch")
    artifact = audit.get("artifact")
    if not _json_equal(
        artifact,
        {
            "id": tokenizer.get("artifact_id"),
            "revision": tokenizer.get("revision"),
        },
    ):
        errors.append("tokenizer audit artifact identity mismatch")

    offline = audit.get("offline_enforcement")
    if not _json_equal(
        offline,
        {
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "local_files_only": True,
            "private_tokenizer_staging": True,
            "trust_remote_code": False,
        },
    ):
        errors.append("tokenizer audit offline controls mismatch")

    snapshot = audit.get("snapshot_verification")
    if not isinstance(snapshot, Mapping):
        errors.append("tokenizer audit snapshot verification is missing")
    else:
        if not _self_hash_valid(snapshot, "receipt_sha256"):
            errors.append("tokenizer audit snapshot receipt self-hash is invalid")
        if snapshot.get("receipt_sha256") != tokenizer.get(
            "snapshot_receipt_sha256"
        ):
            errors.append("tokenizer audit snapshot receipt identity mismatch")
        if snapshot.get("artifact_id") != tokenizer.get("artifact_id"):
            errors.append("tokenizer audit snapshot artifact mismatch")
        if snapshot.get("repository") != tokenizer.get("repository"):
            errors.append("tokenizer audit snapshot repository mismatch")
        if snapshot.get("revision") != tokenizer.get("revision"):
            errors.append("tokenizer audit snapshot revision mismatch")
        if snapshot.get("status") != "verified":
            errors.append("tokenizer audit snapshot is not verified")
        files = snapshot.get("files")
        if isinstance(files, list):
            weight_bytes = sum(
                file.get("size_bytes", 0)
                for file in files
                if isinstance(file, Mapping)
                and isinstance(file.get("filename"), str)
                and file["filename"].endswith(".safetensors")
                and _int(file.get("size_bytes"))
            )
            if audit.get("model_weight_bytes_verified") != weight_bytes:
                errors.append("tokenizer audit verified weight-byte total mismatch")
        else:
            errors.append("tokenizer audit snapshot file evidence is missing")

    loaded_validation = audit.get("loaded_tokenizer_validation")
    if not isinstance(loaded_validation, Mapping) or canonical_json_sha256(
        loaded_validation
    ) != tokenizer.get("loaded_validation_sha256"):
        errors.append("tokenizer audit loaded-tokenizer identity mismatch")
    runtime_identity = audit.get("runtime_identity")
    if not isinstance(runtime_identity, Mapping) or canonical_json_sha256(
        runtime_identity
    ) != tokenizer.get("runtime_identity_sha256"):
        errors.append("tokenizer audit runtime identity mismatch")
    tokenizer_length = (
        loaded_validation.get("tokenizer_length")
        if isinstance(loaded_validation, Mapping)
        else None
    )
    if not _int(tokenizer_length) or tokenizer_length <= 0:
        errors.append("tokenizer audit loaded tokenizer length is invalid")
    tokenizer_metadata = audit.get("tokenizer")
    if not isinstance(tokenizer_metadata, Mapping) or not isinstance(
        loaded_validation,
        Mapping,
    ):
        errors.append("tokenizer audit tokenizer metadata is missing")
    else:
        metadata_expected = {
            "class": loaded_validation.get("class"),
            "name_or_path": f"{tokenizer.get('repository')}@{tokenizer.get('revision')}",
            "vocab_size": loaded_validation.get("vocab_size"),
            "model_max_length": loaded_validation.get("model_max_length"),
            "special_token_ids": loaded_validation.get("special_token_ids"),
        }
        if not _json_equal(tokenizer_metadata, metadata_expected):
            errors.append("tokenizer audit tokenizer metadata differs from loaded identity")

    summary = audit.get("summary")
    if not isinstance(summary, Mapping) or set(summary) != _TOKENIZER_SUMMARY_KEYS:
        errors.append("tokenizer audit summary is missing")

    items = audit.get("items")
    if not isinstance(items, list) or len(items) != registry.get("item_count"):
        errors.append("tokenizer audit item coverage mismatch")
        return tuple(dict.fromkeys(errors))

    if len(registry_items) != registry.get("item_count"):
        errors.append("registry item coverage is inconsistent with criteria")
        return tuple(dict.fromkeys(errors))
    minimum = tokenizer.get("minimum_common_continuation_tokens")
    maximum = tokenizer.get("maximum_common_continuation_tokens")
    observed_counts: dict[str, int] = {}
    continuation_counts: list[int] = []
    full_counts: list[int] = []
    candidate_count = 0
    form_count = 0
    continuation_token_evidence: dict[str, tuple[int, ...]] = {}
    for item, registry_item in zip(items, registry_items, strict=True):
        if not isinstance(item, Mapping) or set(item) != _TOKENIZER_ITEM_KEYS:
            errors.append("tokenizer audit item fields are not exact")
            continue
        item_id = item.get("item_id")
        if item_id != registry_item.get("item_id") or item.get(
            "domain"
        ) != registry_item.get("domain"):
            errors.append("tokenizer audit item order/identity mismatch")
        counts: list[int] = []
        forms = item.get("forms")
        expected_forms = registry_item.get("forms")
        if (
            not isinstance(forms, list)
            or not isinstance(expected_forms, list)
            or len(forms) != registry.get("forms_per_item")
            or len(forms) != len(expected_forms)
        ):
            errors.append(f"tokenizer audit item {item_id!r} form coverage mismatch")
            continue
        cell_evidence: dict[tuple[str, str, str], tuple[Any, ...]] = {}
        context_prompt_evidence: dict[str, tuple[int, ...]] = {}
        for form, registry_form in zip(forms, expected_forms, strict=True):
            form_count += 1
            if not isinstance(form, Mapping) or set(form) != _TOKENIZER_FORM_KEYS:
                errors.append(f"tokenizer audit item {item_id!r} form fields are not exact")
                continue
            if form.get("form_id") != registry_form.get("form_id"):
                errors.append(f"tokenizer audit item {item_id!r} form identity mismatch")
            if form.get("prompt_context_match") is not True:
                errors.append(f"tokenizer audit item {item_id!r} prompt context mismatch")
            if (
                type(form.get("continuation_token_count_difference")) is not int
                or form.get("continuation_token_count_difference") != 0
            ):
                errors.append(f"tokenizer audit item {item_id!r} within-form count mismatch")
            candidates = form.get("candidates")
            expected_candidates = registry_form.get("candidates")
            if (
                not isinstance(candidates, list)
                or not isinstance(expected_candidates, list)
                or len(candidates) != 2
                or len(expected_candidates) != 2
            ):
                errors.append(f"tokenizer audit item {item_id!r} candidate coverage mismatch")
                continue
            prompt_ids_in_form: list[list[int]] = []
            for candidate, registry_candidate in zip(
                candidates,
                expected_candidates,
                strict=True,
            ):
                candidate_count += 1
                if (
                    not isinstance(candidate, Mapping)
                    or set(candidate) != _TOKENIZER_CANDIDATE_KEYS
                ):
                    errors.append(f"tokenizer audit item {item_id!r} candidate fields are not exact")
                    continue
                if candidate.get("status") != "passed":
                    errors.append(f"tokenizer audit item {item_id!r} has a failed candidate")
                    continue
                if candidate.get("pole") != registry_candidate.get("pole"):
                    errors.append(f"tokenizer audit item {item_id!r} candidate pole/order mismatch")
                prompt = registry_form.get("prompt")
                continuation = registry_candidate.get("text")
                if candidate.get("prompt_sha256") != hashlib.sha256(
                    str(prompt).encode("utf-8")
                ).hexdigest():
                    errors.append(f"tokenizer audit item {item_id!r} prompt binding mismatch")
                if candidate.get("continuation_sha256") != hashlib.sha256(
                    str(continuation).encode("utf-8")
                ).hexdigest():
                    errors.append(f"tokenizer audit item {item_id!r} continuation binding mismatch")
                prompt_ids = candidate.get("prompt_token_ids")
                continuation_ids = candidate.get("continuation_token_ids")
                if not _token_ids(prompt_ids) or not _token_ids(continuation_ids):
                    errors.append(f"tokenizer audit item {item_id!r} token IDs are malformed")
                    continue
                continuation_identity = str(candidate.get("continuation_sha256"))
                observed_continuation = tuple(continuation_ids)
                prior_continuation = continuation_token_evidence.setdefault(
                    continuation_identity,
                    observed_continuation,
                )
                if prior_continuation != observed_continuation:
                    errors.append(
                        f"tokenizer audit item {item_id!r} identical continuation "
                        "text has inconsistent token IDs"
                    )
                if not _int(tokenizer_length) or any(
                    token_id >= tokenizer_length
                    for token_id in (*prompt_ids, *continuation_ids)
                ):
                    errors.append(
                        f"tokenizer audit item {item_id!r} token ID exceeds "
                        "the loaded tokenizer length"
                    )
                prompt_ids_in_form.append(prompt_ids)
                prompt_count = candidate.get("prompt_token_count")
                count = candidate.get("continuation_token_count")
                full_count = candidate.get("full_token_count")
                start = candidate.get("continuation_start_index")
                first = candidate.get("first_prediction_index")
                final = candidate.get("final_prediction_index")
                if not all(
                    _int(value)
                    for value in (prompt_count, count, full_count, start, first, final)
                ):
                    errors.append(f"tokenizer audit item {item_id!r} token indices are malformed")
                    continue
                if (
                    prompt_count != len(prompt_ids)
                    or count != len(continuation_ids)
                    or full_count != prompt_count + count
                    or start != prompt_count
                    or first != start - 1
                    or final != first + count - 1
                    or full_count > tokenizer.get("max_length")
                ):
                    errors.append(f"tokenizer audit item {item_id!r} token index arithmetic mismatch")
                counts.append(count)
                continuation_counts.append(count)
                full_counts.append(full_count)
                cell_key = (
                    str(registry_form.get("context_id")),
                    str(registry_form.get("template_id")),
                    str(candidate.get("pole")),
                )
                evidence = (tuple(prompt_ids), tuple(continuation_ids))
                prior = cell_evidence.setdefault(cell_key, evidence)
                if prior != evidence:
                    errors.append(f"tokenizer audit item {item_id!r} duplicate cell evidence differs")
            if len(prompt_ids_in_form) == 2 and prompt_ids_in_form[0] != prompt_ids_in_form[1]:
                errors.append(f"tokenizer audit item {item_id!r} prompt token IDs differ within a form")
            if prompt_ids_in_form:
                context_id = str(registry_form.get("context_id"))
                observed_prompt = tuple(prompt_ids_in_form[0])
                prior_prompt = context_prompt_evidence.setdefault(
                    context_id,
                    observed_prompt,
                )
                if prior_prompt != observed_prompt:
                    errors.append(
                        f"tokenizer audit item {item_id!r} prompt token IDs "
                        "differ across templates/orders for one context"
                    )
        if len(counts) != 16 or len(set(counts)) != 1:
            errors.append(f"tokenizer audit item {item_id!r} does not have one common token count")
        elif not (_int(minimum) and _int(maximum) and minimum <= counts[0] <= maximum):
            errors.append(f"tokenizer audit item {item_id!r} common token count is outside the frozen range")
        else:
            observed_counts[str(item_id)] = counts[0]

    expected_summary = {
        "item_count": len(items),
        "form_count": form_count,
        "candidate_count": candidate_count,
        "failure_count": 0,
        "max_continuation_tokens": max(continuation_counts, default=None),
        "max_full_tokens": max(full_counts, default=None),
        "max_within_form_token_difference": 0,
    }
    if not _json_equal(summary, expected_summary):
        errors.append("tokenizer audit summary does not match its records")
    reliability = audit.get("measurement_reliability")
    expected_reliability = {
        "profile_id": criteria.get("profile_id"),
        "criteria_sha256": criteria.get("criteria_sha256"),
        "common_continuation_token_counts": observed_counts,
        "claim_ceiling": criteria.get("claim_ceiling"),
    }
    if not _json_equal(reliability, expected_reliability):
        errors.append("tokenizer audit measurement-reliability binding mismatch")
    return tuple(dict.fromkeys(errors))


def analyze_score_coherence(
    score: Mapping[str, Any],
    criteria: Mapping[str, Any],
    registry_items: Sequence[Mapping[str, Any]],
    tokenizer_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and derive coherence from one complete base score artifact."""

    failures: list[dict[str, Any]] = []

    def fail(scope: str, error: str, item_id: Any = None) -> None:
        entry: dict[str, Any] = {"scope": scope, "error": error}
        if item_id is not None:
            entry["item_id"] = item_id
        failures.append(entry)

    for error in validate_reliability_criteria(criteria):
        fail("criteria", error)
    registry_identity = criteria.get("registry", {}).get("sha256")
    for error in validate_registry_against_criteria(
        registry_items,
        criteria,
        registry_sha256=str(registry_identity),
    ):
        fail("registry", error)
    tokenizer_errors = validate_tokenizer_audit_against_criteria(
        tokenizer_audit,
        criteria,
        registry_items,
    )
    for error in tokenizer_errors:
        fail("tokenizer", error)

    registry = criteria.get("registry", {})
    tokenizer = criteria.get("tokenizer", {})
    scoring = criteria.get("scoring", {})
    score_keys = set(score)
    if score_keys != _BASE_SCORE_KEYS and score_keys != _FINAL_SCORE_KEYS:
        fail("score", "score artifact top-level fields are not exact")
    if score_keys == _FINAL_SCORE_KEYS and (
        score.get("status") != "complete"
        or score.get("score_type") != "registry-development-score"
        or score.get("scientific_claim_authorized") is not False
        or not isinstance(score.get("contract"), Mapping)
        or not isinstance(score.get("summary"), Mapping)
    ):
        fail("score", "final score envelope is invalid")
    if not _self_hash_valid(score, "output_sha256"):
        fail("score", "score artifact self-hash is invalid")
    if type(score.get("schema_version")) is not int or score.get(
        "schema_version"
    ) != 1:
        fail("score", "score artifact schema version is invalid")
    if score.get("registry_sha256") != registry.get("sha256"):
        fail("score", "score artifact registry identity mismatch")
    if _contains_absolute_path(score):
        fail("score", "score artifact contains an absolute local path")
    expected_scorer = {
        "version": scoring.get("scorer_version"),
        "primary_metric": "complete-continuation-total-logprob-margin",
        "diagnostic_metric": "mean-token-logprob-margin",
        "generated_explanations_used": False,
    }
    score_scorer = score.get("scorer")
    if not isinstance(score_scorer, Mapping) or set(
        score_scorer
    ) != _SCORE_SCORER_KEYS or not _json_equal(
        score_scorer,
        expected_scorer,
    ):
        fail("score", "score artifact scorer identity mismatch")
    loaded_validation = tokenizer_audit.get("loaded_tokenizer_validation")
    backend_sha256 = (
        loaded_validation.get("backend_sha256")
        if isinstance(loaded_validation, Mapping)
        else None
    )
    expected_model = {
        "id": tokenizer.get("artifact_id"),
        "revision": tokenizer.get("revision"),
        "tokenizer_id": (
            f"{tokenizer.get('repository')}@{tokenizer.get('revision')}:"
            f"backend={backend_sha256}:"
            f"prefix={tokenizer.get('prefix_policy')}:max_length={tokenizer.get('max_length')}"
        ),
    }
    score_model = score.get("model")
    if not isinstance(score_model, Mapping) or set(
        score_model
    ) != _SCORE_MODEL_KEYS or not _json_equal(
        score_model,
        expected_model,
    ):
        fail("score", "score artifact model/tokenizer identity mismatch")

    audit_candidates: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for audit_item in tokenizer_audit.get("items", []):
        if not isinstance(audit_item, Mapping):
            continue
        for audit_form in audit_item.get("forms", []):
            if not isinstance(audit_form, Mapping):
                continue
            for audit_candidate in audit_form.get("candidates", []):
                if not isinstance(audit_candidate, Mapping):
                    continue
                key = (
                    str(audit_item.get("item_id")),
                    str(audit_form.get("form_id")),
                    str(audit_candidate.get("pole")),
                )
                if key in audit_candidates:
                    fail("tokenizer", "tokenizer candidate identity is duplicated")
                audit_candidates[key] = audit_candidate

    score_items = score.get("items")
    item_results: list[dict[str, Any]] = []
    if not isinstance(score_items, list) or len(score_items) != len(registry_items):
        fail("score", "score item coverage mismatch")
        score_items = []
    for score_item, registry_item in zip(score_items, registry_items):
        item_id = registry_item.get("item_id")
        item_failures: list[str] = []

        def item_fail(error: str) -> None:
            if error not in item_failures:
                item_failures.append(error)

        if not isinstance(score_item, Mapping) or set(score_item) != _SCORE_ITEM_KEYS:
            item_fail("score item fields are not exact")
            score_item = {}
        for key in ("item_id", "domain", "construct", "reference_pole"):
            if score_item.get(key) != registry_item.get(key):
                item_fail(f"score item identity mismatch: {key}")
        score_forms = score_item.get("forms")
        registry_forms = registry_item.get("forms")
        if (
            not isinstance(score_forms, list)
            or not isinstance(registry_forms, list)
            or len(score_forms) != len(registry_forms)
        ):
            item_fail("score form coverage mismatch")
            score_forms = []
            registry_forms = []
        pairwise_scores = []
        primary_margins: list[float] = []
        token_counts: list[int] = []
        duplicate_evidence: dict[
            tuple[str, str, str],
            Mapping[str, Any],
        ] = {}
        for score_form, registry_form in zip(score_forms, registry_forms):
            if not isinstance(score_form, Mapping) or set(
                score_form
            ) != _SCORE_FORM_KEYS:
                item_fail("score form fields are not exact")
                continue
            if score_form.get("form_id") != registry_form.get("form_id"):
                item_fail("score form identity mismatch")
            expected_order = [
                candidate.get("pole")
                for candidate in registry_form.get("candidates", [])
                if isinstance(candidate, Mapping)
            ]
            if not _json_equal(
                score_form.get("candidate_display_order"),
                expected_order,
            ):
                item_fail("score candidate display order mismatch")
            score_candidates = score_form.get("candidates")
            registry_candidates = registry_form.get("candidates")
            if (
                not isinstance(score_candidates, list)
                or not isinstance(registry_candidates, list)
                or len(score_candidates) != 2
                or len(registry_candidates) != 2
            ):
                item_fail("score candidate coverage mismatch")
                continue
            recomputed_candidates = []
            for score_candidate_value, registry_candidate in zip(
                score_candidates,
                registry_candidates,
            ):
                if not isinstance(score_candidate_value, Mapping) or set(
                    score_candidate_value
                ) != _SCORE_CANDIDATE_KEYS:
                    item_fail("score candidate fields are not exact")
                    continue
                pole = registry_candidate.get("pole")
                if score_candidate_value.get("pole") != pole:
                    item_fail("score candidate pole/order mismatch")
                audit_key = (
                    str(item_id),
                    str(registry_form.get("form_id")),
                    str(pole),
                )
                accepted = audit_candidates.get(audit_key)
                if accepted is None:
                    item_fail("score candidate lacks accepted tokenizer evidence")
                    continue
                if score_candidate_value.get("prompt_token_ids") != accepted.get(
                    "prompt_token_ids"
                ) or score_candidate_value.get(
                    "continuation_token_ids"
                ) != accepted.get(
                    "continuation_token_ids"
                ):
                    item_fail("score token IDs differ from accepted tokenizer evidence")
                token_logprobs = score_candidate_value.get("token_logprobs")
                try:
                    evidence = CandidateEvidence(
                        prompt_token_ids=tuple(score_candidate_value.get("prompt_token_ids", [])),
                        continuation_token_ids=tuple(
                            score_candidate_value.get("continuation_token_ids", [])
                        ),
                        token_logprobs=tuple(token_logprobs or []),
                    )
                    recomputed = score_candidate(str(pole), evidence)
                except (ScoringIntegrityError, TypeError, ValueError) as error:
                    item_fail(f"score candidate evidence is invalid: {error}")
                    continue
                if not _json_equal(score_candidate_value, recomputed.as_dict()):
                    item_fail("score candidate aggregates do not match token log probabilities")
                maximum_count = tokenizer.get(
                    "maximum_common_continuation_tokens"
                )
                if not _int(maximum_count) or recomputed.token_count > maximum_count:
                    item_fail("score candidate token count exceeds the frozen maximum")
                token_counts.append(recomputed.token_count)
                recomputed_candidates.append(recomputed)
                duplicate_key = (
                    str(registry_form.get("context_id")),
                    str(registry_form.get("template_id")),
                    str(pole),
                )
                prior = duplicate_evidence.setdefault(
                    duplicate_key,
                    recomputed.as_dict(),
                )
                if not _json_equal(prior, recomputed.as_dict()):
                    item_fail("forward/reverse duplicate candidate scores differ")
            if len(recomputed_candidates) != 2:
                continue
            try:
                recomputed_pairwise = pairwise_score(
                    recomputed_candidates,
                    str(registry_item.get("reference_pole")),
                )
            except ScoringIntegrityError as error:
                item_fail(f"score pairwise evidence is invalid: {error}")
                continue
            pairwise_value = score_form.get("pairwise")
            if not isinstance(pairwise_value, Mapping) or set(
                pairwise_value
            ) != _SCORE_PAIRWISE_KEYS:
                item_fail("score pairwise fields are not exact")
            elif not _json_equal(pairwise_value, recomputed_pairwise.as_dict()):
                item_fail("score pairwise values do not match candidate evidence")
            pairwise_scores.append(recomputed_pairwise)
            primary_margins.append(recomputed_pairwise.total_logprob_margin)
            form_counts = {
                candidate.token_count for candidate in recomputed_candidates
            }
            if len(form_counts) != 1:
                item_fail("within-form token counts differ")
            else:
                form_count = next(iter(form_counts))
                expected_mean_margin = (
                    recomputed_pairwise.total_logprob_margin / form_count
                )
                if not math.isclose(
                    recomputed_pairwise.mean_logprob_margin,
                    expected_mean_margin,
                    rel_tol=float(scoring.get("relation_rel_tol", 0.0)),
                    abs_tol=float(scoring.get("relation_abs_tol", 0.0)),
                ):
                    item_fail(
                        "form mean-token margin is inconsistent with total "
                        "margin/common token count"
                    )
            if recomputed_pairwise.total_logprob_margin == 0.0:
                item_fail("primary margin is exactly zero")
            primary_sign = (
                1
                if recomputed_pairwise.total_logprob_margin > 0.0
                else -1
                if recomputed_pairwise.total_logprob_margin < 0.0
                else 0
            )
            diagnostic_sign = (
                1
                if recomputed_pairwise.mean_logprob_margin > 0.0
                else -1
                if recomputed_pairwise.mean_logprob_margin < 0.0
                else 0
            )
            if primary_sign != diagnostic_sign:
                item_fail("primary/diagnostic signs differ")

        common_count = (
            token_counts[0]
            if len(token_counts) == 16 and len(set(token_counts)) == 1
            else None
        )
        if common_count is None:
            item_fail("item does not have one common token count")
        signs = {
            1 if margin > 0.0 else -1 if margin < 0.0 else 0
            for margin in primary_margins
        }
        if len(primary_margins) != 8 or len(signs) != 1 or 0 in signs:
            item_fail("eight form margins do not share one nonzero sign")
        aggregate = score_item.get("aggregate")
        if len(pairwise_scores) == 8:
            try:
                recomputed_aggregate = aggregate_form_scores(pairwise_scores)
            except ScoringIntegrityError as error:
                item_fail(f"score aggregate evidence is invalid: {error}")
            else:
                if not isinstance(aggregate, Mapping) or set(
                    aggregate
                ) != _SCORE_AGGREGATE_KEYS:
                    item_fail("score aggregate fields are not exact")
                elif not _json_equal(aggregate, recomputed_aggregate):
                    item_fail("score aggregate values do not match form evidence")
                if common_count is not None and not math.isclose(
                    recomputed_aggregate["mean_mean_logprob_margin"],
                    recomputed_aggregate["mean_total_logprob_margin"]
                    / common_count,
                    rel_tol=float(scoring.get("relation_rel_tol", 0.0)),
                    abs_tol=float(scoring.get("relation_abs_tol", 0.0)),
                ):
                    item_fail(
                        "aggregate mean-token margin is inconsistent with total "
                        "margin/common token count"
                    )
                if recomputed_aggregate["directional_agreement"] != scoring.get(
                    "minimum_directional_agreement"
                ):
                    item_fail("directional agreement is below the frozen requirement")
        else:
            item_fail("score aggregate cannot be recomputed")
        item_results.append(
            {
                "item_id": item_id,
                "passed": not item_failures,
                "common_continuation_token_count": common_count,
                "failures": item_failures,
            }
        )
        for error in item_failures:
            fail("item", error, item_id)

    output: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "development-measurement-coherence",
        "profile_id": criteria.get("profile_id"),
        "criteria_sha256": criteria.get("criteria_sha256"),
        "registry_sha256": score.get("registry_sha256"),
        "score_output_sha256": score.get("output_sha256"),
        "item_results": item_results,
        "failures": failures,
        "passed": not failures,
        "claim_ceiling": criteria.get("claim_ceiling"),
    }
    output["output_sha256"] = canonical_json_sha256(output)
    return output


def analyze_score_repeat(
    score_a: Mapping[str, Any],
    score_b: Mapping[str, Any],
    criteria: Mapping[str, Any],
    registry_items: Sequence[Mapping[str, Any]],
    tokenizer_audit: Mapping[str, Any],
    *,
    score_a_bytes: bytes,
    score_b_bytes: bytes,
    receipt_a: Mapping[str, Any],
    receipt_a_bytes: bytes,
    resource_audit_a: Mapping[str, Any],
    resource_audit_a_bytes: bytes,
    receipt_b: Mapping[str, Any],
    receipt_b_bytes: bytes,
    resource_audit_b: Mapping[str, Any],
    resource_audit_b_bytes: bytes,
    scoring_config: Mapping[str, Any],
    expected_git_head: str,
) -> dict[str, Any]:
    """Verify runtime evidence, exact score bytes, and coherence together."""

    report_a = analyze_score_coherence(
        score_a,
        criteria,
        registry_items,
        tokenizer_audit,
    )
    report_b = analyze_score_coherence(
        score_b,
        criteria,
        registry_items,
        tokenizer_audit,
    )
    failures: list[str] = []
    if not report_a["passed"]:
        failures.append("attempt A score coherence failed")
    if not report_b["passed"]:
        failures.append("attempt B score coherence failed")
    expected_a = (
        json.dumps(
            score_a,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    expected_b = (
        json.dumps(
            score_b,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    if score_a_bytes != expected_a or score_b_bytes != expected_b:
        failures.append("score artifacts are not canonical pretty JSON bytes")
    if score_a_bytes != score_b_bytes:
        failures.append("canonical/reverse score artifacts are not byte-identical")
    expected_score_file_sha256 = hashlib.sha256(score_a_bytes).hexdigest()
    execution_comparison: Mapping[str, Any] | None = None
    execution_error: str | None = None
    try:
        execution_comparison = verify_scoring_repeat(
            score_a=score_a,
            score_a_bytes=score_a_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=receipt_a_bytes,
            resource_audit_a=resource_audit_a,
            resource_audit_a_bytes=resource_audit_a_bytes,
            score_b=score_b,
            score_b_bytes=score_b_bytes,
            receipt_b=receipt_b,
            receipt_b_bytes=receipt_b_bytes,
            resource_audit_b=resource_audit_b,
            resource_audit_b_bytes=resource_audit_b_bytes,
            config=scoring_config,
            registry=registry_items,
            tokenizer_audit=tokenizer_audit,
            expected_git_head=expected_git_head,
        )
    except (ScoringRunError, TypeError, ValueError) as error:
        execution_error = str(error)
    expected_modes = criteria.get("scoring", {}).get(
        "required_execution_modes"
    )
    execution_validated = bool(
        isinstance(execution_comparison, Mapping)
        and _self_hash_valid(execution_comparison, "comparison_sha256")
        and execution_comparison.get("status") == "equal"
        and execution_comparison.get("profile_id") == criteria.get("profile_id")
        and execution_comparison.get(
            "measurement_reliability_criteria_sha256"
        )
        == criteria.get("criteria_sha256")
        and execution_comparison.get("execution_modes")
        == {"a": expected_modes[0], "b": expected_modes[1]}
        if isinstance(expected_modes, list) and len(expected_modes) == 2
        else False
    )
    if execution_validated and (
        execution_comparison.get("score_file_sha256")
        != expected_score_file_sha256
        or execution_comparison.get("score_output_sha256")
        != score_a.get("output_sha256")
    ):
        execution_validated = False
    if not execution_validated:
        failures.append("execution-order receipts are not valid and profile-bound")
    output: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "development-measurement-repeat",
        "profile_id": criteria.get("profile_id"),
        "criteria_sha256": criteria.get("criteria_sha256"),
        "registry_sha256": criteria.get("registry", {}).get("sha256"),
        "required_execution_modes": criteria.get("scoring", {}).get(
            "required_execution_modes"
        ),
        "score_file_sha256": expected_score_file_sha256,
        "score_output_sha256": score_a.get("output_sha256"),
        "attempt_a": report_a,
        "attempt_b": report_b,
        "failures": failures,
        "passed": not failures,
        "execution_mode_receipts_validated": execution_validated,
        "execution_comparison_sha256": (
            execution_comparison.get("comparison_sha256")
            if execution_validated and isinstance(execution_comparison, Mapping)
            else None
        ),
        "execution_verification_error": execution_error,
        "claim_ceiling": criteria.get("claim_ceiling"),
    }
    output["output_sha256"] = canonical_json_sha256(output)
    return output
