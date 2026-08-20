"""Frozen run identity and evidence validation for registry model scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import fmean, stdev
from typing import Any

from .evaluation import canonical_json_sha256
from .run_registry import build_run_identity


class ScoringRunError(RuntimeError):
    """Raised when a registry-scoring run cannot satisfy its frozen contract."""


FROZEN_CONFIG_GIT_BLOB = "338c55e6427b4491e5bcbbad05ac13d8d4b326e5"
FROZEN_RUN_SPEC_SHA256 = "a446008ee9e8196c4091606273cc90c6d54278160449fbd71bc2eab81eb14d9d"


_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "run_name",
        "run_kind",
        "status",
        "scientific_claim_authorized",
        "network_allowed",
        "external_spend_cad",
        "max_parallel_jobs",
        "artifact",
        "canonical_inputs",
        "accepted_tokenizer_audit",
        "registry_topology",
        "scoring",
        "model",
        "determinism",
        "runtime_identity",
        "resource_limits",
    }
)

_SECTION_KEYS = {
    "artifact": frozenset(
        {
            "id",
            "repository",
            "revision",
            "model_safetensors_size_bytes",
            "model_safetensors_sha256",
            "snapshot_receipt_sha256",
        }
    ),
    "canonical_inputs": frozenset(
        {
            "manifest_path",
            "manifest_git_blob",
            "manifest_sha256",
            "registry_path",
            "registry_git_blob",
            "registry_sha256",
        }
    ),
    "accepted_tokenizer_audit": frozenset(
        {
            "path",
            "file_sha256",
            "output_sha256",
            "backend_sha256",
            "native_prefix_probe_sha256",
            "scoring_token_matrix_sha256",
            "prefix_policy",
            "prefix_token_ids",
        }
    ),
    "registry_topology": frozenset(
        {
            "item_count",
            "form_count",
            "candidate_count",
            "forwarded_token_count",
            "predicted_token_count",
            "continuation_token_count",
            "maximum_full_token_count",
            "maximum_continuation_token_count",
            "maximum_within_form_token_difference",
        }
    ),
    "scoring": frozenset(
        {
            "scorer_version",
            "maximum_length",
            "complete_continuations",
            "log_softmax_dtype",
            "exact_boundary_required",
            "truncation_allowed",
        }
    ),
    "model": frozenset(
        {
            "class",
            "model_type",
            "parameter_count",
            "vocabulary_size",
            "device",
            "dtype",
            "eval_mode",
            "quantized",
            "device_map",
            "offload",
            "autocast",
            "trust_remote_code",
            "use_safetensors",
            "local_files_only",
        }
    ),
    "determinism": frozenset(
        {
            "fresh_invocations",
            "exact_score_bytes_required",
            "algorithms",
            "cublas_workspace_config",
            "attention_implementation",
            "sdpa_backends",
            "sdpa_math_allow_fp16_reduction",
            "tf32",
            "cudnn_benchmark",
            "float32_matmul_precision",
            "use_cache",
            "rescue_runs",
        }
    ),
    "runtime_identity": frozenset(
        {
            "python",
            "packages",
            "cuda_runtime",
            "cuda_device_count",
            "cuda_device_index",
            "cuda_device_name",
            "cuda_compute_capability",
            "cuda_total_memory_bytes",
        }
    ),
    "resource_limits": frozenset(
        {
            "minimum_preload_free_vram_bytes",
            "maximum_process_peak_reserved_bytes",
            "minimum_postload_global_free_vram_bytes",
            "minimum_staging_output_free_bytes",
            "minimum_output_free_bytes",
            "maximum_invocation_wall_seconds",
            "ram_threshold_enforced",
        }
    ),
}

_FIXED_VALUES: dict[str, Any] = {
    "schema_version": 1,
    "run_name": "pythia-1b-deduped-development-score-v0",
    "run_kind": "verified-registry-development-score",
    "status": "frozen",
    "scientific_claim_authorized": False,
    "network_allowed": False,
    "external_spend_cad": 0,
    "max_parallel_jobs": 1,
    "artifact.id": "pythia-1b-deduped-main",
    "artifact.repository": "EleutherAI/pythia-1b-deduped",
    "artifact.revision": "7199d8fc61a6d565cd1f3c62bf11525b563e13b2",
    "artifact.model_safetensors_size_bytes": 2_090_701_528,
    "artifact.model_safetensors_sha256": "fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13",
    "artifact.snapshot_receipt_sha256": "26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc",
    "canonical_inputs.manifest_path": "artifacts/manifests/MODEL_MANIFEST.json",
    "canonical_inputs.manifest_git_blob": "2dbafc0d0fe10a717e1df3d5c7920e6af661138b",
    "canonical_inputs.manifest_sha256": "f3a800e95887b96ec66a660efa51ab975b17b7ec1ada0f381f502e912d9cf4f6",
    "canonical_inputs.registry_path": "evaluations/registry/development-v0.jsonl",
    "canonical_inputs.registry_git_blob": "39a229ca8a29243bc457f42c5fdc69e303bb5361",
    "canonical_inputs.registry_sha256": "5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d",
    "accepted_tokenizer_audit.file_sha256": "ee11e4c99d6577fa2e3be5a53e4c17b626ff91bcdee877b295799dc5926c39bb",
    "accepted_tokenizer_audit.path": "artifacts/local/pythia-tokenizer-none-a-c57ce40.json",
    "accepted_tokenizer_audit.output_sha256": "6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523",
    "accepted_tokenizer_audit.backend_sha256": "1b0aca3746c0870daeb9137101cd89acbb38710fc433db83331287d5b0e47ee0",
    "accepted_tokenizer_audit.native_prefix_probe_sha256": "f2b89b376c56b7100ec3947ae1ccd3b468eceedcfbfe7031389bae0f8c327af1",
    "accepted_tokenizer_audit.scoring_token_matrix_sha256": "b2477a108542308b17d80811aa0ff15ad72f37a67363c3fa9177fde85805dfe1",
    "accepted_tokenizer_audit.prefix_policy": "none",
    "accepted_tokenizer_audit.prefix_token_ids": [],
    "registry_topology.item_count": 12,
    "registry_topology.form_count": 24,
    "registry_topology.candidate_count": 48,
    "registry_topology.forwarded_token_count": 2_391,
    "registry_topology.predicted_token_count": 2_343,
    "registry_topology.continuation_token_count": 839,
    "registry_topology.maximum_full_token_count": 59,
    "registry_topology.maximum_continuation_token_count": 20,
    "registry_topology.maximum_within_form_token_difference": 3,
    "scoring.scorer_version": "complete-continuation-transformers-v0",
    "scoring.maximum_length": 2_048,
    "scoring.complete_continuations": True,
    "scoring.log_softmax_dtype": "float32",
    "scoring.exact_boundary_required": True,
    "scoring.truncation_allowed": False,
    "model.class": "GPTNeoXForCausalLM",
    "model.model_type": "gpt_neox",
    "model.parameter_count": 1_011_781_632,
    "model.vocabulary_size": 50_304,
    "model.device": "cuda:0",
    "model.dtype": "float16",
    "model.eval_mode": True,
    "model.quantized": False,
    "model.device_map": False,
    "model.offload": False,
    "model.autocast": False,
    "model.trust_remote_code": False,
    "model.use_safetensors": True,
    "model.local_files_only": True,
    "determinism.fresh_invocations": 2,
    "determinism.exact_score_bytes_required": True,
    "determinism.algorithms": True,
    "determinism.cublas_workspace_config": ":4096:8",
    "determinism.attention_implementation": "sdpa",
    "determinism.sdpa_backends": ["math"],
    "determinism.sdpa_math_allow_fp16_reduction": False,
    "determinism.tf32": False,
    "determinism.cudnn_benchmark": False,
    "determinism.float32_matmul_precision": "highest",
    "determinism.use_cache": False,
    "determinism.rescue_runs": 0,
    "runtime_identity.python": "3.11.9",
    "runtime_identity.packages.torch": "2.13.0+cu130",
    "runtime_identity.packages.transformers": "5.15.1",
    "runtime_identity.packages.tokenizers": "0.22.2",
    "runtime_identity.packages.huggingface-hub": "1.28.0",
    "runtime_identity.packages.accelerate": "1.14.0",
    "runtime_identity.packages.safetensors": "0.8.0",
    "runtime_identity.cuda_runtime": "13.0",
    "runtime_identity.cuda_device_count": 1,
    "runtime_identity.cuda_device_index": 0,
    "runtime_identity.cuda_device_name": "NVIDIA GeForce RTX 2060",
    "runtime_identity.cuda_compute_capability": [7, 5],
    "runtime_identity.cuda_total_memory_bytes": 6_441_992_192,
    "resource_limits.minimum_preload_free_vram_bytes": 3_695_181_824,
    "resource_limits.maximum_process_peak_reserved_bytes": 3_158_310_912,
    "resource_limits.minimum_postload_global_free_vram_bytes": 1_610_612_736,
    "resource_limits.minimum_staging_output_free_bytes": 2_227_034_030,
    "resource_limits.minimum_output_free_bytes": 134_217_728,
    "resource_limits.maximum_invocation_wall_seconds": 900,
    "resource_limits.ram_threshold_enforced": False,
}


def _nested(value: Mapping[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise ScoringRunError(f"scoring config is missing {dotted}")
        current = current[part]
    return current


def _leaf_values(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    for key, item in value.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            leaves.update(_leaf_values(item, dotted))
        else:
            leaves[dotted] = item
    return leaves


def validate_scoring_config(config: Mapping[str, Any]) -> tuple[str, ...]:
    """Return exact frozen-profile validation errors."""

    errors: list[str] = []
    if frozenset(config) != _TOP_LEVEL_KEYS:
        errors.append("scoring config top-level fields are not exact")
    for section, expected_keys in _SECTION_KEYS.items():
        raw = config.get(section)
        if not isinstance(raw, Mapping):
            errors.append(f"scoring config {section} must be an object")
        elif frozenset(raw) != expected_keys:
            errors.append(f"scoring config {section} fields are not exact")
    if set(_leaf_values(config)) != set(_FIXED_VALUES):
        errors.append("scoring config frozen leaf fields are not exact")
    for dotted, expected in _FIXED_VALUES.items():
        try:
            observed = _nested(config, dotted)
        except ScoringRunError as error:
            errors.append(str(error))
            continue
        if observed != expected or type(observed) is not type(expected):
            errors.append(
                f"scoring config {dotted} must equal {expected!r}"
            )
    if canonical_json_sha256(config) != FROZEN_RUN_SPEC_SHA256:
        errors.append("scoring config canonical identity is not frozen")
    return tuple(errors)


def _exact_json_object(
    pairs: list[tuple[str, Any]],
    label: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScoringRunError(f"{label} contains duplicate JSON key: {key}")
        result[key] = value
    return result


def load_scoring_config(path: str | Path) -> dict[str, Any]:

    try:
        raw = json.loads(
            _stable_bytes(Path(path), "scoring config"),
            object_pairs_hook=lambda pairs: _exact_json_object(
                pairs,
                "scoring config",
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ScoringRunError(f"cannot load scoring config: {error}") from error
    if not isinstance(raw, Mapping):
        raise ScoringRunError("scoring config root must be an object")
    config = dict(raw)
    errors = validate_scoring_config(config)
    if errors:
        raise ScoringRunError("; ".join(errors))
    return config


def _stable_bytes(path: Path, label: str) -> bytes:
    before = path.stat()
    with path.open("rb") as handle:
        opened_before = os.fstat(handle.fileno())
        payload = handle.read()
        opened_after = os.fstat(handle.fileno())
    after = path.stat()
    identities = {
        (
            int(info.st_dev),
            int(info.st_ino),
            int(info.st_size),
            int(info.st_mtime_ns),
            int(info.st_ctime_ns),
        )
        for info in (before, opened_before, opened_after, after)
    }
    if len(identities) != 1:
        raise ScoringRunError(f"{label} changed while it was being read")
    return payload


def _self_hash_valid(value: Mapping[str, Any], field: str) -> bool:
    observed = value.get(field)
    if not isinstance(observed, str):
        return False
    body = dict(value)
    body.pop(field, None)
    return observed == canonical_json_sha256(body)


def load_accepted_tokenizer_audit(
    path: str | Path,
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    """Load and bind the accepted pre-logits tokenizer audit."""

    selected = Path(path)
    try:
        payload = _stable_bytes(selected, "accepted tokenizer audit")
        raw = json.loads(
            payload,
            object_pairs_hook=lambda pairs: _exact_json_object(
                pairs,
                "accepted tokenizer audit",
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ScoringRunError(
            f"cannot load accepted tokenizer audit: {error}"
        ) from error
    if not isinstance(raw, Mapping):
        raise ScoringRunError("accepted tokenizer audit root must be an object")
    report = dict(raw)
    file_sha256 = hashlib.sha256(payload).hexdigest()
    expected = config["accepted_tokenizer_audit"]
    if file_sha256 != expected["file_sha256"]:
        raise ScoringRunError("accepted tokenizer audit file SHA-256 mismatch")
    if not _self_hash_valid(report, "output_sha256"):
        raise ScoringRunError("accepted tokenizer audit self-hash mismatch")
    if report.get("output_sha256") != expected["output_sha256"]:
        raise ScoringRunError("accepted tokenizer audit output identity mismatch")

    canonical = config["canonical_inputs"]
    artifact = config["artifact"]
    summary = report.get("summary")
    validation = report.get("loaded_tokenizer_validation")
    snapshot = report.get("snapshot_verification")
    runtime = report.get("runtime_identity")
    offline = report.get("offline_enforcement")
    required = {
        "schema_version": 1,
        "audit_type": "evaluation-tokenizer-audit",
        "mode": "execute",
        "passed": True,
        "worktree_clean": True,
        "model_manifest_git_blob": canonical["manifest_git_blob"],
        "model_manifest_sha256": canonical["manifest_sha256"],
        "development_registry_git_blob": canonical["registry_git_blob"],
        "registry_sha256": canonical["registry_sha256"],
        "prefix_policy": expected["prefix_policy"],
        "prefix_token_ids": expected["prefix_token_ids"],
        "model_weights_deserialized": False,
        "model_weight_bytes_verified": artifact["model_safetensors_size_bytes"],
        "network_access_permitted": False,
        "network_observation": "not-instrumented",
        "scientific_claim_authorized": False,
        "tokenizer_files_downloaded": False,
        "weights_downloaded": False,
    }
    for key, expected_value in required.items():
        if report.get(key) != expected_value:
            raise ScoringRunError(
                f"accepted tokenizer audit {key} identity mismatch"
            )
    if report.get("failures") != []:
        raise ScoringRunError("accepted tokenizer audit contains failures")
    if report.get("artifact") != {
        "id": artifact["id"],
        "revision": artifact["revision"],
    }:
        raise ScoringRunError("accepted tokenizer artifact identity mismatch")
    topology = config["registry_topology"]
    if not isinstance(summary, Mapping) or dict(summary) != {
        "candidate_count": topology["candidate_count"],
        "failure_count": 0,
        "form_count": topology["form_count"],
        "item_count": topology["item_count"],
        "max_continuation_tokens": topology["maximum_continuation_token_count"],
        "max_full_tokens": topology["maximum_full_token_count"],
        "max_within_form_token_difference": topology[
            "maximum_within_form_token_difference"
        ],
    }:
        raise ScoringRunError("accepted tokenizer audit topology mismatch")
    if not isinstance(validation, Mapping) or (
        validation.get("verified") is not True
        or validation.get("backend_sha256") != expected["backend_sha256"]
        or validation.get("native_prefix_probe_sha256")
        != expected["native_prefix_probe_sha256"]
        or validation.get("native_prefix_policy") != expected["prefix_policy"]
        or validation.get("native_prefix_probe_equal") is not True
        or validation.get("native_special_tokens_to_add") != 0
    ):
        raise ScoringRunError("accepted tokenizer runtime identity mismatch")
    if not isinstance(snapshot, Mapping) or (
        snapshot.get("receipt_sha256") != artifact["snapshot_receipt_sha256"]
        or snapshot.get("repository") != artifact["repository"]
        or snapshot.get("revision") != artifact["revision"]
        or snapshot.get("status") != "verified"
    ):
        raise ScoringRunError("accepted tokenizer snapshot identity mismatch")
    runtime_expected = config["runtime_identity"]
    if not isinstance(runtime, Mapping) or runtime.get("python") != runtime_expected[
        "python"
    ]:
        raise ScoringRunError("accepted tokenizer Python identity mismatch")
    packages = runtime.get("packages")
    for name in ("transformers", "tokenizers", "huggingface-hub"):
        if not isinstance(packages, Mapping) or packages.get(name) != runtime_expected[
            "packages"
        ][name]:
            raise ScoringRunError(
                f"accepted tokenizer runtime package mismatch: {name}"
            )
    if not isinstance(offline, Mapping) or dict(offline) != {
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "local_files_only": True,
        "private_tokenizer_staging": True,
        "trust_remote_code": False,
    }:
        raise ScoringRunError("accepted tokenizer offline controls mismatch")
    return report, file_sha256


def expected_tokenizer_id(config: Mapping[str, Any]) -> str:
    artifact = config["artifact"]
    audit = config["accepted_tokenizer_audit"]
    scoring = config["scoring"]
    return (
        f"{artifact['repository']}@{artifact['revision']}:"
        f"backend={audit['backend_sha256']}:prefix={audit['prefix_policy']}:"
        f"max_length={scoring['maximum_length']}"
    )


def _audit_candidate_map(report: Mapping[str, Any]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    observed: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    items = report.get("items")
    if not isinstance(items, list):
        raise ScoringRunError("accepted tokenizer audit items are missing")
    for item in items:
        if not isinstance(item, Mapping):
            raise ScoringRunError("accepted tokenizer audit item is invalid")
        for form in item.get("forms", []):
            if not isinstance(form, Mapping):
                raise ScoringRunError("accepted tokenizer audit form is invalid")
            for candidate in form.get("candidates", []):
                if not isinstance(candidate, Mapping):
                    raise ScoringRunError(
                        "accepted tokenizer audit candidate is invalid"
                    )
                key = (
                    str(item.get("item_id")),
                    str(form.get("form_id")),
                    str(candidate.get("pole")),
                )
                if key in observed:
                    raise ScoringRunError(
                        "accepted tokenizer audit candidate identity is duplicated"
                    )
                observed[key] = candidate
    return observed


_SCORE_KEYS = frozenset(
    {
        "schema_version",
        "scorer",
        "registry_sha256",
        "model",
        "items",
        "status",
        "score_type",
        "scientific_claim_authorized",
        "contract",
        "summary",
        "output_sha256",
    }
)
_SCORER_KEYS = frozenset(
    {
        "version",
        "primary_metric",
        "diagnostic_metric",
        "generated_explanations_used",
    }
)
_MODEL_KEYS = frozenset({"id", "revision", "tokenizer_id"})
_CONTRACT_KEYS = frozenset(
    {
        "git_head",
        "run_spec_sha256",
        "model_manifest_git_blob",
        "model_manifest_sha256",
        "development_registry_git_blob",
        "accepted_tokenizer_file_sha256",
        "accepted_tokenizer_output_sha256",
        "snapshot_receipt_sha256",
        "attention_policy",
    }
)
_SUMMARY_KEYS = frozenset(
    {
        "item_count",
        "form_count",
        "candidate_count",
        "forwarded_token_count",
        "predicted_token_count",
        "continuation_token_count",
        "maximum_full_token_count",
        "maximum_continuation_token_count",
        "boundary_failure_count",
        "truncation_failure_count",
        "nonfinite_failure_count",
    }
)
_ITEM_KEYS = frozenset(
    {"item_id", "domain", "construct", "reference_pole", "forms", "aggregate"}
)
_FORM_KEYS = frozenset(
    {"form_id", "candidate_display_order", "candidates", "pairwise"}
)
_CANDIDATE_KEYS = frozenset(
    {
        "pole",
        "total_logprob",
        "mean_logprob",
        "token_count",
        "prompt_token_count",
        "prompt_token_ids",
        "continuation_token_ids",
        "token_logprobs",
    }
)
_PAIRWISE_KEYS = frozenset(
    {
        "reference_pole",
        "comparison_pole",
        "total_logprob_margin",
        "mean_logprob_margin",
        "probability_reference",
    }
)
_AGGREGATE_KEYS = frozenset(
    {
        "reference_pole",
        "comparison_pole",
        "form_count",
        "mean_total_logprob_margin",
        "mean_mean_logprob_margin",
        "total_logprob_margin_sd",
        "directional_agreement",
        "probability_reference_from_mean_margin",
    }
)


def _hex_identity(value: Any, length: int) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(rf"[0-9a-f]{{{length}}}", value)
    )


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _token_ids(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, int) and not isinstance(item, bool) and item >= 0
        for item in value
    )


def _expected_score_identity(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scorer": {
            "version": config["scoring"]["scorer_version"],
            "primary_metric": "complete-continuation-total-logprob-margin",
            "diagnostic_metric": "mean-token-logprob-margin",
            "generated_explanations_used": False,
        },
        "registry_sha256": config["canonical_inputs"]["registry_sha256"],
        "model": {
            "id": config["artifact"]["id"],
            "revision": config["artifact"]["revision"],
            "tokenizer_id": expected_tokenizer_id(config),
        },
    }


def finalize_score_artifact(
    score: Mapping[str, Any],
    *,
    tokenizer_audit: Mapping[str, Any],
    config: Mapping[str, Any],
    run_spec_sha256: str,
    git_head: str,
) -> dict[str, Any]:
    """Bind deterministic model scores to the frozen tokenizer audit."""

    if not _self_hash_valid(score, "output_sha256"):
        raise ScoringRunError("base score artifact self-hash mismatch")
    if frozenset(score) != frozenset(
        {"schema_version", "scorer", "registry_sha256", "model", "items", "output_sha256"}
    ):
        raise ScoringRunError("base score artifact fields are not exact")
    expected_identity = _expected_score_identity(config)
    for key, expected in expected_identity.items():
        if score.get(key) != expected:
            raise ScoringRunError(f"base score artifact {key} identity mismatch")
    if score.get("schema_version") != 1:
        raise ScoringRunError("base score artifact schema mismatch")
    expected_candidates = _audit_candidate_map(tokenizer_audit)
    actual_candidates: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    forwarded = predicted = continuation = 0
    maximum_full = maximum_continuation = 0
    for item in score.get("items", []):
        if not isinstance(item, Mapping):
            raise ScoringRunError("score item is invalid")
        for form in item.get("forms", []):
            if not isinstance(form, Mapping):
                raise ScoringRunError("score form is invalid")
            for candidate in form.get("candidates", []):
                if not isinstance(candidate, Mapping):
                    raise ScoringRunError("score candidate is invalid")
                key = (
                    str(item.get("item_id")),
                    str(form.get("form_id")),
                    str(candidate.get("pole")),
                )
                accepted = expected_candidates.get(key)
                if accepted is None or key in actual_candidates:
                    raise ScoringRunError("score candidate identity mismatch")
                prompt_ids = candidate.get("prompt_token_ids")
                continuation_ids = candidate.get("continuation_token_ids")
                token_logprobs = candidate.get("token_logprobs")
                if not isinstance(prompt_ids, list) or not isinstance(
                    continuation_ids, list
                ) or not isinstance(token_logprobs, list):
                    raise ScoringRunError("score candidate token evidence is invalid")
                if continuation_ids != accepted.get("continuation_token_ids"):
                    raise ScoringRunError(
                        "score continuation IDs differ from the accepted tokenizer audit"
                    )
                if len(prompt_ids) != accepted.get("prompt_token_count"):
                    raise ScoringRunError(
                        "score prompt count differs from the accepted tokenizer audit"
                    )
                if len(continuation_ids) != accepted.get(
                    "continuation_token_count"
                ) or len(token_logprobs) != len(continuation_ids):
                    raise ScoringRunError("score continuation count mismatch")
                full_count = len(prompt_ids) + len(continuation_ids)
                if full_count != accepted.get("full_token_count"):
                    raise ScoringRunError("score full-token count mismatch")
                forwarded += full_count
                predicted += full_count - 1
                continuation += len(continuation_ids)
                maximum_full = max(maximum_full, full_count)
                maximum_continuation = max(
                    maximum_continuation, len(continuation_ids)
                )
                actual_candidates[key] = candidate
    if set(actual_candidates) != set(expected_candidates):
        raise ScoringRunError("score does not cover every accepted tokenizer candidate")
    topology = config["registry_topology"]
    summary = {
        "item_count": len(score.get("items", [])),
        "form_count": sum(len(item.get("forms", [])) for item in score["items"]),
        "candidate_count": len(actual_candidates),
        "forwarded_token_count": forwarded,
        "predicted_token_count": predicted,
        "continuation_token_count": continuation,
        "maximum_full_token_count": maximum_full,
        "maximum_continuation_token_count": maximum_continuation,
        "boundary_failure_count": 0,
        "truncation_failure_count": 0,
        "nonfinite_failure_count": 0,
    }
    for key in (
        "item_count",
        "form_count",
        "candidate_count",
        "forwarded_token_count",
        "predicted_token_count",
        "continuation_token_count",
        "maximum_full_token_count",
        "maximum_continuation_token_count",
    ):
        if summary[key] != topology[key]:
            raise ScoringRunError(f"score topology mismatch: {key}")

    body = dict(score)
    body.pop("output_sha256", None)
    body.update(
        {
            "status": "complete",
            "score_type": "registry-development-score",
            "scientific_claim_authorized": False,
            "contract": {
                "git_head": git_head,
                "run_spec_sha256": run_spec_sha256,
                "model_manifest_git_blob": config["canonical_inputs"][
                    "manifest_git_blob"
                ],
                "model_manifest_sha256": config["canonical_inputs"][
                    "manifest_sha256"
                ],
                "development_registry_git_blob": config["canonical_inputs"][
                    "registry_git_blob"
                ],
                "accepted_tokenizer_file_sha256": config[
                    "accepted_tokenizer_audit"
                ]["file_sha256"],
                "accepted_tokenizer_output_sha256": config[
                    "accepted_tokenizer_audit"
                ]["output_sha256"],
                "snapshot_receipt_sha256": config["artifact"][
                    "snapshot_receipt_sha256"
                ],
                "attention_policy": {
                    "attention_implementation": config["determinism"][
                        "attention_implementation"
                    ],
                    "sdpa_backends": config["determinism"]["sdpa_backends"],
                    "sdpa_math_allow_fp16_reduction": config["determinism"][
                        "sdpa_math_allow_fp16_reduction"
                    ],
                },
            },
            "summary": summary,
        }
    )
    body["output_sha256"] = canonical_json_sha256(body)
    return body


def _strings(value: Any) -> Sequence[str]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(
            text
            for item in (*value.keys(), *value.values())
            for text in _strings(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(text for item in value for text in _strings(item))
    return ()


def _contains_absolute_path(value: Any) -> bool:
    drive = re.compile(r"^[A-Za-z]:[\\/]")
    return any(
        text.startswith(("/", "\\\\", "//")) or bool(drive.match(text))
        for text in _strings(value)
    )


def _stable_sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def _score_structure_errors(score: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    items = score.get("items")
    if not isinstance(items, list):
        return ("score artifact items are missing",)

    seen_items: set[str] = set()
    seen_candidates: set[tuple[str, str, str]] = set()
    item_count = form_count = candidate_count = 0
    forwarded = predicted = continuation = 0
    maximum_full = maximum_continuation = maximum_difference = 0
    for item_index, item in enumerate(items):
        if not isinstance(item, Mapping) or frozenset(item) != _ITEM_KEYS:
            errors.append(f"score item {item_index} fields are not exact")
            continue
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id or item_id in seen_items:
            errors.append(f"score item {item_index} identity is invalid")
            continue
        seen_items.add(item_id)
        item_count += 1
        forms = item.get("forms")
        if not isinstance(forms, list):
            errors.append(f"score item {item_id} forms are missing")
            continue
        aggregate = item.get("aggregate")
        if not isinstance(aggregate, Mapping) or frozenset(aggregate) != _AGGREGATE_KEYS:
            errors.append(f"score item {item_id} aggregate fields are not exact")
        elif aggregate.get("form_count") != len(forms):
            errors.append(f"score item {item_id} aggregate form count mismatch")
        seen_forms: set[str] = set()
        expected_form_scores: list[dict[str, Any]] = []
        for form_index, form in enumerate(forms):
            if not isinstance(form, Mapping) or frozenset(form) != _FORM_KEYS:
                errors.append(
                    f"score item {item_id} form {form_index} fields are not exact"
                )
                continue
            form_id = form.get("form_id")
            if (
                not isinstance(form_id, str)
                or not form_id
                or form_id in seen_forms
            ):
                errors.append(f"score item {item_id} form identity is invalid")
                continue
            seen_forms.add(form_id)
            form_count += 1
            candidates = form.get("candidates")
            display_order = form.get("candidate_display_order")
            pairwise = form.get("pairwise")
            if not isinstance(candidates, list) or len(candidates) != 2:
                errors.append(f"score form {item_id}/{form_id} candidates are invalid")
                continue
            if not isinstance(pairwise, Mapping) or frozenset(pairwise) != _PAIRWISE_KEYS:
                errors.append(f"score form {item_id}/{form_id} pairwise fields are not exact")
            poles: list[str] = []
            prompt_contexts: set[tuple[int, ...]] = set()
            continuation_counts: list[int] = []
            candidate_scores: dict[str, tuple[float, float]] = {}
            for candidate_index, candidate in enumerate(candidates):
                if not isinstance(candidate, Mapping) or frozenset(candidate) != _CANDIDATE_KEYS:
                    errors.append(
                        f"score candidate {item_id}/{form_id}/{candidate_index} fields are not exact"
                    )
                    continue
                pole = candidate.get("pole")
                if not isinstance(pole, str) or not pole:
                    errors.append(f"score candidate {item_id}/{form_id} pole is invalid")
                    continue
                key = (item_id, form_id, pole)
                if key in seen_candidates:
                    errors.append(f"score candidate identity is duplicated: {key}")
                    continue
                seen_candidates.add(key)
                poles.append(pole)
                prompt_ids = candidate.get("prompt_token_ids")
                continuation_ids = candidate.get("continuation_token_ids")
                logprobs = candidate.get("token_logprobs")
                if (
                    not _token_ids(prompt_ids)
                    or not prompt_ids
                    or not _token_ids(continuation_ids)
                    or not continuation_ids
                    or not isinstance(logprobs, list)
                    or not logprobs
                    or not all(_finite_number(value) and float(value) <= 0.0 for value in logprobs)
                ):
                    errors.append(f"score candidate {key} token evidence is invalid")
                    continue
                if (
                    candidate.get("prompt_token_count") != len(prompt_ids)
                    or candidate.get("token_count") != len(continuation_ids)
                    or len(logprobs) != len(continuation_ids)
                ):
                    errors.append(f"score candidate {key} token counts mismatch")
                    continue
                total = math.fsum(float(value) for value in logprobs)
                mean = total / len(logprobs)
                if (
                    not _finite_number(candidate.get("total_logprob"))
                    or not _finite_number(candidate.get("mean_logprob"))
                    or float(candidate["total_logprob"]) != total
                    or float(candidate["mean_logprob"]) != mean
                ):
                    errors.append(f"score candidate {key} aggregate log probabilities mismatch")
                else:
                    candidate_scores[pole] = (total, mean)
                full_count = len(prompt_ids) + len(continuation_ids)
                prompt_contexts.add(tuple(prompt_ids))
                continuation_counts.append(len(continuation_ids))
                candidate_count += 1
                forwarded += full_count
                predicted += full_count - 1
                continuation += len(continuation_ids)
                maximum_full = max(maximum_full, full_count)
                maximum_continuation = max(
                    maximum_continuation, len(continuation_ids)
                )
            if display_order != poles or len(set(poles)) != 2:
                errors.append(f"score form {item_id}/{form_id} display order mismatch")
            if len(prompt_contexts) != 1:
                errors.append(f"score form {item_id}/{form_id} prompt context mismatch")
            if len(continuation_counts) == 2:
                maximum_difference = max(
                    maximum_difference, abs(continuation_counts[0] - continuation_counts[1])
                )
            if isinstance(pairwise, Mapping) and frozenset(pairwise) == _PAIRWISE_KEYS:
                reference = item.get("reference_pole")
                comparisons = set(poles) - {reference}
                if reference not in candidate_scores or len(comparisons) != 1:
                    errors.append(f"score form {item_id}/{form_id} pairwise evidence is invalid")
                else:
                    comparison = next(iter(comparisons))
                    if comparison not in candidate_scores:
                        errors.append(
                            f"score form {item_id}/{form_id} pairwise evidence is invalid"
                        )
                    else:
                        reference_total, reference_mean = candidate_scores[reference]
                        comparison_total, comparison_mean = candidate_scores[comparison]
                        total_margin = reference_total - comparison_total
                        mean_margin = reference_mean - comparison_mean
                        expected_pairwise = {
                            "reference_pole": reference,
                            "comparison_pole": comparison,
                            "total_logprob_margin": total_margin,
                            "mean_logprob_margin": mean_margin,
                            "probability_reference": _stable_sigmoid(total_margin),
                        }
                        if dict(pairwise) != expected_pairwise:
                            errors.append(
                                f"score form {item_id}/{form_id} pairwise values mismatch"
                            )
                        else:
                            expected_form_scores.append(expected_pairwise)

        if (
            isinstance(aggregate, Mapping)
            and frozenset(aggregate) == _AGGREGATE_KEYS
            and len(expected_form_scores) == len(forms)
            and expected_form_scores
        ):
            total_margins = [
                float(value["total_logprob_margin"])
                for value in expected_form_scores
            ]
            mean_margins = [
                float(value["mean_logprob_margin"])
                for value in expected_form_scores
            ]
            aggregate_margin = fmean(total_margins)
            if aggregate_margin > 0:
                directional_agreement = sum(
                    margin > 0 for margin in total_margins
                ) / len(total_margins)
            elif aggregate_margin < 0:
                directional_agreement = sum(
                    margin < 0 for margin in total_margins
                ) / len(total_margins)
            else:
                directional_agreement = sum(
                    margin == 0 for margin in total_margins
                ) / len(total_margins)
            expected_aggregate = {
                "reference_pole": item.get("reference_pole"),
                "comparison_pole": expected_form_scores[0]["comparison_pole"],
                "form_count": len(expected_form_scores),
                "mean_total_logprob_margin": aggregate_margin,
                "mean_mean_logprob_margin": fmean(mean_margins),
                "total_logprob_margin_sd": (
                    stdev(total_margins) if len(total_margins) > 1 else 0.0
                ),
                "directional_agreement": directional_agreement,
                "probability_reference_from_mean_margin": _stable_sigmoid(
                    aggregate_margin
                ),
            }
            if dict(aggregate) != expected_aggregate:
                errors.append(f"score item {item_id} aggregate values mismatch")

    observed = {
        "item_count": item_count,
        "form_count": form_count,
        "candidate_count": candidate_count,
        "forwarded_token_count": forwarded,
        "predicted_token_count": predicted,
        "continuation_token_count": continuation,
        "maximum_full_token_count": maximum_full,
        "maximum_continuation_token_count": maximum_continuation,
        "maximum_within_form_token_difference": maximum_difference,
    }
    summary = score.get("summary")
    if not isinstance(summary, Mapping) or frozenset(summary) != _SUMMARY_KEYS:
        errors.append("score artifact summary fields are not exact")
    else:
        for key, value in observed.items():
            if key == "maximum_within_form_token_difference":
                continue
            if summary.get(key) != value:
                errors.append(f"score artifact summary does not match items: {key}")
        for key in (
            "boundary_failure_count",
            "truncation_failure_count",
            "nonfinite_failure_count",
        ):
            if summary.get(key) != 0:
                errors.append(f"score artifact contains {key}")
    return tuple(errors)


def _score_input_binding_errors(
    score: Mapping[str, Any],
    config: Mapping[str, Any],
    registry: Sequence[Mapping[str, Any]],
    tokenizer_audit: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    score_items = score.get("items")
    if not isinstance(score_items, list) or len(score_items) != len(registry):
        return ("score items do not match the canonical registry",)
    try:
        accepted_candidates = _audit_candidate_map(tokenizer_audit)
    except ScoringRunError as error:
        return (str(error),)
    observed_candidates: set[tuple[str, str, str]] = set()
    token_records: list[dict[str, Any]] = []
    for item_index, (actual_item, expected_item) in enumerate(
        zip(score_items, registry, strict=True)
    ):
        if not isinstance(actual_item, Mapping):
            errors.append(f"score item {item_index} is invalid")
            continue
        for key in ("item_id", "domain", "construct", "reference_pole"):
            if actual_item.get(key) != expected_item.get(key):
                errors.append(f"score item {item_index} registry mismatch: {key}")
        actual_forms = actual_item.get("forms")
        expected_forms = expected_item.get("forms")
        if not isinstance(actual_forms, list) or not isinstance(
            expected_forms, list
        ) or len(actual_forms) != len(expected_forms):
            errors.append(f"score item {item_index} form topology mismatch")
            continue
        for form_index, (actual_form, expected_form) in enumerate(
            zip(actual_forms, expected_forms, strict=True)
        ):
            if not isinstance(actual_form, Mapping):
                errors.append(
                    f"score item {item_index} form {form_index} is invalid"
                )
                continue
            if actual_form.get("form_id") != expected_form.get("form_id"):
                errors.append(
                    f"score item {item_index} form {form_index} registry identity mismatch"
                )
            expected_candidates = expected_form.get("candidates")
            actual_candidates = actual_form.get("candidates")
            if not isinstance(expected_candidates, list) or not isinstance(
                actual_candidates, list
            ) or len(actual_candidates) != len(expected_candidates):
                errors.append(
                    f"score item {item_index} form {form_index} candidate topology mismatch"
                )
                continue
            expected_poles = [
                candidate.get("pole")
                for candidate in expected_candidates
                if isinstance(candidate, Mapping)
            ]
            if actual_form.get("candidate_display_order") != expected_poles:
                errors.append(
                    f"score item {item_index} form {form_index} display order differs from registry"
                )
            for candidate_index, (actual_candidate, expected_candidate) in enumerate(
                zip(actual_candidates, expected_candidates, strict=True)
            ):
                if not isinstance(actual_candidate, Mapping) or not isinstance(
                    expected_candidate, Mapping
                ):
                    errors.append(
                        f"score item {item_index} form {form_index} candidate {candidate_index} is invalid"
                    )
                    continue
                pole = expected_candidate.get("pole")
                if actual_candidate.get("pole") != pole:
                    errors.append(
                        f"score item {item_index} form {form_index} candidate pole differs from registry"
                    )
                    continue
                identity = (
                    str(expected_item.get("item_id")),
                    str(expected_form.get("form_id")),
                    str(pole),
                )
                accepted = accepted_candidates.get(identity)
                if accepted is None:
                    errors.append(
                        f"score candidate is absent from accepted tokenizer audit: {identity}"
                    )
                    continue
                observed_candidates.add(identity)
                token_records.append(
                    {
                        "item_id": identity[0],
                        "form_id": identity[1],
                        "pole": identity[2],
                        "prompt_token_ids": actual_candidate.get(
                            "prompt_token_ids"
                        ),
                        "continuation_token_ids": actual_candidate.get(
                            "continuation_token_ids"
                        ),
                    }
                )
                if (
                    actual_candidate.get("prompt_token_count")
                    != accepted.get("prompt_token_count")
                    or actual_candidate.get("continuation_token_ids")
                    != accepted.get("continuation_token_ids")
                    or actual_candidate.get("token_count")
                    != accepted.get("continuation_token_count")
                ):
                    errors.append(
                        f"score candidate token identity differs from accepted tokenizer audit: {identity}"
                    )
    if observed_candidates != set(accepted_candidates):
        errors.append("score candidate coverage differs from accepted tokenizer audit")
    if canonical_json_sha256(token_records) != config["accepted_tokenizer_audit"][
        "scoring_token_matrix_sha256"
    ]:
        errors.append("score token matrix differs from the frozen tokenizer identity")
    return tuple(errors)


def validate_score_artifact(
    score: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    registry: Sequence[Mapping[str, Any]],
    tokenizer_audit: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    if frozenset(score) != _SCORE_KEYS:
        errors.append("score artifact top-level fields are not exact")
    if not _self_hash_valid(score, "output_sha256"):
        errors.append("score artifact self-hash mismatch")
    if type(score.get("schema_version")) is not int or score.get("schema_version") != 1 or score.get("status") != "complete":
        errors.append("score artifact status/schema mismatch")
    if score.get("score_type") != "registry-development-score":
        errors.append("score artifact type mismatch")
    if score.get("scientific_claim_authorized") is not False:
        errors.append("score artifact scientific claim boundary mismatch")
    expected_identity = _expected_score_identity(config)
    if score.get("scorer") != expected_identity["scorer"]:
        errors.append("score artifact scorer identity mismatch")
    if score.get("registry_sha256") != expected_identity["registry_sha256"]:
        errors.append("score artifact registry identity mismatch")
    if score.get("model") != expected_identity["model"]:
        errors.append("score artifact model identity mismatch")
    contract = score.get("contract")
    if not isinstance(contract, Mapping) or frozenset(contract) != _CONTRACT_KEYS:
        errors.append("score artifact contract fields are not exact")
    else:
        canonical = config["canonical_inputs"]
        accepted = config["accepted_tokenizer_audit"]
        artifact = config["artifact"]
        expected_contract = {
            "model_manifest_git_blob": canonical["manifest_git_blob"],
            "model_manifest_sha256": canonical["manifest_sha256"],
            "development_registry_git_blob": canonical["registry_git_blob"],
            "accepted_tokenizer_file_sha256": accepted["file_sha256"],
            "accepted_tokenizer_output_sha256": accepted["output_sha256"],
            "snapshot_receipt_sha256": artifact["snapshot_receipt_sha256"],
            "attention_policy": {
                "attention_implementation": config["determinism"]["attention_implementation"],
                "sdpa_backends": config["determinism"]["sdpa_backends"],
                "sdpa_math_allow_fp16_reduction": config["determinism"]["sdpa_math_allow_fp16_reduction"],
            },
        }
        for key, expected in expected_contract.items():
            if contract.get(key) != expected:
                errors.append(f"score artifact contract mismatch: {key}")
        if not _hex_identity(contract.get("git_head"), 40):
            errors.append("score artifact Git head is invalid")
        if contract.get("run_spec_sha256") != FROZEN_RUN_SPEC_SHA256:
            errors.append("score artifact run-spec identity is invalid")
    errors.extend(_score_structure_errors(score))
    errors.extend(
        _score_input_binding_errors(score, config, registry, tokenizer_audit)
    )
    topology = config["registry_topology"]
    summary = score.get("summary")
    if isinstance(summary, Mapping):
        for key, expected in topology.items():
            if key == "maximum_within_form_token_difference":
                continue
            if summary.get(key) != expected:
                errors.append(f"score artifact summary mismatch: {key}")
    items = score.get("items")
    if isinstance(items, list):
        differences = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            for form in item.get("forms", []):
                if not isinstance(form, Mapping):
                    continue
                candidates = form.get("candidates")
                if isinstance(candidates, list) and len(candidates) == 2:
                    counts = [candidate.get("token_count") for candidate in candidates if isinstance(candidate, Mapping)]
                    if len(counts) == 2 and all(isinstance(value, int) and not isinstance(value, bool) for value in counts):
                        differences.append(abs(counts[0] - counts[1]))
        if max(differences, default=0) != topology["maximum_within_form_token_difference"]:
            errors.append("score artifact within-form token difference mismatch")
    if _contains_absolute_path(score):
        errors.append("score artifact contains an absolute local path")
    return tuple(errors)


def pretty_json_bytes(value: Any) -> bytes:
    try:
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
    except (TypeError, ValueError) as error:
        raise ScoringRunError(f"evidence is not valid JSON: {error}") from error


def create_only_json(path: str | Path, value: Any) -> tuple[int, str]:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = pretty_json_bytes(value)
    try:
        descriptor = os.open(
            destination,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as error:
        raise ScoringRunError(
            f"refusing to overwrite existing output: {destination}"
        ) from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return len(payload), hashlib.sha256(payload).hexdigest()


def receipt_with_self_hash(receipt: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    body["receipt_sha256"] = canonical_json_sha256(body)
    return body


_COMPLETE_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "receipt_type",
        "status",
        "attempt",
        "run_id",
        "process_id",
        "started_at",
        "completed_at",
        "network_access_permitted",
        "network_observation",
        "scientific_claim_authorized",
        "git",
        "run_spec",
        "canonical_inputs",
        "accepted_tokenizer",
        "snapshot_verification",
        "model_validation",
        "model_loading_info",
        "tokenizer_validation",
        "runtime_identity",
        "determinism",
        "execution_controls",
        "resource_preflight",
        "output_storage",
        "post_load_resource",
        "post_score_resource",
        "metrics",
        "score",
        "receipt_sha256",
    }
)


def _resource_conservative_free(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    conservative = value.get("conservative_vram")
    if not isinstance(conservative, Mapping):
        return None
    observed = conservative.get("conservative_free_bytes")
    if not isinstance(observed, int) or isinstance(observed, bool):
        return None
    return observed


def _utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        return None
    return parsed


_RESOURCE_AUDIT_KEYS = frozenset(
    {
        "audit_type",
        "captured_at",
        "cpu",
        "disk",
        "environment",
        "git",
        "memory",
        "network_access_performed",
        "nvidia",
        "packages",
        "platform",
        "python",
        "schema_version",
        "torch_runtime",
    }
)
_RESOURCE_PACKAGES = (
    "torch",
    "transformers",
    "huggingface-hub",
    "safetensors",
    "accelerate",
)
_RESOURCE_PREFLIGHT_KEYS = frozenset(
    {
        "resource_audit",
        "resource_audit_sha256",
        "resource_audit_captured_at",
        "resource_audit_age_seconds",
        "git_head",
        "audit_disk_free_bytes",
        "audit_disk_path",
        "cache_storage_path",
        "filesystem_device",
        "live_disk_free_bytes",
        "live_resource_audit_sha256",
        "live_resource_audit_captured_at",
        "live_resource_audit_age_seconds",
        "live_resource_audit",
        "live_resource_audit_semantic_sha256",
        "execution_resource_validation",
        "post_import_resource_audit_sha256",
        "post_import_resource_audit_captured_at",
        "post_import_resource_audit_age_seconds",
        "post_import_resource_audit",
        "post_import_resource_audit_semantic_sha256",
        "post_import_resource_validation",
    }
)


def _audit_indexed_record(value: Any, *, label: str) -> Mapping[str, Any] | None:
    if not isinstance(value, list):
        return None
    matches = [
        item
        for item in value
        if isinstance(item, Mapping)
        and type(item.get("index")) is int
        and item.get("index") == 0
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _audit_conservative_vram(audit: Mapping[str, Any]) -> dict[str, int] | None:
    torch_runtime = audit.get("torch_runtime")
    nvidia = audit.get("nvidia")
    if not isinstance(torch_runtime, Mapping) or not isinstance(nvidia, Mapping):
        return None
    torch_device = _audit_indexed_record(
        torch_runtime.get("devices"), label="Torch device"
    )
    nvidia_device = _audit_indexed_record(
        nvidia.get("gpus"), label="nvidia-smi device"
    )
    if torch_device is None or nvidia_device is None:
        return None
    torch_free = torch_device.get("free_memory_bytes")
    torch_total = torch_device.get("total_memory_bytes")
    nvidia_free_mib = nvidia_device.get("memory_free_mib")
    nvidia_total_mib = nvidia_device.get("memory_total_mib")
    if (
        not isinstance(torch_free, int)
        or isinstance(torch_free, bool)
        or torch_free < 0
        or not isinstance(torch_total, int)
        or isinstance(torch_total, bool)
        or torch_total <= 0
        or torch_free > torch_total
        or not isinstance(nvidia_free_mib, int)
        or isinstance(nvidia_free_mib, bool)
        or nvidia_free_mib < 0
        or not isinstance(nvidia_total_mib, int)
        or isinstance(nvidia_total_mib, bool)
        or nvidia_total_mib <= 0
        or nvidia_free_mib > nvidia_total_mib
    ):
        return None
    nvidia_free = nvidia_free_mib * 1024 * 1024
    return {
        "torch_free_bytes": torch_free,
        "nvidia_smi_free_bytes": nvidia_free,
        "conservative_free_bytes": min(torch_free, nvidia_free),
    }


def _resource_audit_errors(
    audit: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    expected_git_head: str,
    label: str,
    minimum_disk_bytes: int,
    minimum_vram_bytes: int,
) -> list[str]:
    errors: list[str] = []
    if set(audit) != _RESOURCE_AUDIT_KEYS:
        errors.append(f"{label} fields are not exact")
    if (
        type(audit.get("schema_version")) is not int
        or audit.get("schema_version") != 1
        or audit.get("audit_type") != "local-resource-audit"
        or audit.get("network_access_performed") is not False
        or _utc_timestamp(audit.get("captured_at")) is None
    ):
        errors.append(f"{label} schema, timestamp, or network policy is invalid")

    git = audit.get("git")
    if not isinstance(git, Mapping) or set(git) != {
        "head",
        "branch",
        "dirty",
        "errors",
    } or (
        git.get("head") != expected_git_head
        or git.get("dirty") is not False
        or git.get("errors") != []
        or not isinstance(git.get("branch"), str)
    ):
        errors.append(f"{label} Git identity is invalid")

    python = audit.get("python")
    if not isinstance(python, Mapping) or set(python) != {
        "version",
        "implementation",
        "executable",
    } or (
        python.get("version") != config["runtime_identity"]["python"]
        or python.get("implementation") != "CPython"
        or not isinstance(python.get("executable"), str)
        or not python.get("executable")
    ):
        errors.append(f"{label} Python identity is invalid")

    packages = audit.get("packages")
    if not isinstance(packages, Mapping) or set(packages) != {
        "torch",
        "transformers",
        "accelerate",
        "huggingface-hub",
        "safetensors",
        "datasets",
        "deepspeed",
        "bitsandbytes",
    }:
        errors.append(f"{label} package fields are not exact")
    else:
        for package in _RESOURCE_PACKAGES:
            if packages.get(package) != config["runtime_identity"]["packages"][
                package
            ]:
                errors.append(f"{label} package identity mismatch: {package}")

    torch_runtime = audit.get("torch_runtime")
    torch_device: Mapping[str, Any] | None = None
    if not isinstance(torch_runtime, Mapping) or set(torch_runtime) != {
        "available",
        "version",
        "compiled_cuda_version",
        "cuda_available",
        "device_count",
        "devices",
        "errors",
    }:
        errors.append(f"{label} Torch runtime fields are not exact")
    else:
        torch_device = _audit_indexed_record(
            torch_runtime.get("devices"), label="Torch device"
        )
        if (
            torch_runtime.get("available") is not True
            or torch_runtime.get("version")
            != config["runtime_identity"]["packages"]["torch"]
            or torch_runtime.get("compiled_cuda_version")
            != config["runtime_identity"]["cuda_runtime"]
            or torch_runtime.get("cuda_available") is not True
            or type(torch_runtime.get("device_count")) is not int
            or torch_runtime.get("device_count")
            != config["runtime_identity"]["cuda_device_count"]
            or torch_runtime.get("errors") != []
            or torch_device is None
        ):
            errors.append(f"{label} Torch/CUDA identity is invalid")
        elif (
            set(torch_device)
            != {
                "index",
                "name",
                "capability",
                "free_memory_bytes",
                "total_memory_bytes",
            }
            or torch_device.get("index")
            != config["runtime_identity"]["cuda_device_index"]
            or torch_device.get("name")
            != config["runtime_identity"]["cuda_device_name"]
            or torch_device.get("capability")
            != config["runtime_identity"]["cuda_compute_capability"]
            or torch_device.get("total_memory_bytes")
            != config["runtime_identity"]["cuda_total_memory_bytes"]
            or not isinstance(torch_device.get("free_memory_bytes"), int)
            or isinstance(torch_device.get("free_memory_bytes"), bool)
            or int(torch_device.get("free_memory_bytes", -1)) < 0
            or int(torch_device.get("free_memory_bytes", -1))
            > int(torch_device.get("total_memory_bytes", -1))
        ):
            errors.append(f"{label} CUDA device identity is invalid")

    nvidia = audit.get("nvidia")
    nvidia_device: Mapping[str, Any] | None = None
    if not isinstance(nvidia, Mapping) or set(nvidia) != {"command", "gpus"}:
        errors.append(f"{label} nvidia-smi fields are not exact")
    else:
        command = nvidia.get("command")
        nvidia_device = _audit_indexed_record(
            nvidia.get("gpus"), label="nvidia-smi device"
        )
        if not isinstance(command, Mapping) or set(command) != {
            "available",
            "returncode",
            "stdout",
            "stderr",
        } or (
            command.get("available") is not True
            or type(command.get("returncode")) is not int
            or command.get("returncode") != 0
            or not isinstance(command.get("stdout"), str)
            or not isinstance(command.get("stderr"), str)
            or nvidia_device is None
        ):
            errors.append(f"{label} nvidia-smi observation is invalid")
        elif (
            set(nvidia_device)
            != {
                "index",
                "name",
                "uuid",
                "memory_total_mib",
                "memory_free_mib",
                "driver_version",
                "pstate",
                "temperature_c",
                "power_limit_w",
            }
            or nvidia_device.get("index") != 0
            or nvidia_device.get("name")
            != config["runtime_identity"]["cuda_device_name"]
            or not isinstance(nvidia_device.get("uuid"), str)
            or not nvidia_device.get("uuid")
            or not isinstance(nvidia_device.get("driver_version"), str)
            or not nvidia_device.get("driver_version")
            or not isinstance(nvidia_device.get("pstate"), str)
            or not nvidia_device.get("pstate")
            or type(nvidia_device.get("temperature_c")) is not int
            or not _finite_number(nvidia_device.get("power_limit_w"))
            or not isinstance(nvidia_device.get("memory_total_mib"), int)
            or isinstance(nvidia_device.get("memory_total_mib"), bool)
            or not isinstance(nvidia_device.get("memory_free_mib"), int)
            or isinstance(nvidia_device.get("memory_free_mib"), bool)
            or int(nvidia_device.get("memory_total_mib", -1)) <= 0
            or int(nvidia_device.get("memory_free_mib", -1)) < 0
            or int(nvidia_device.get("temperature_c", -1)) < 0
            or float(nvidia_device.get("power_limit_w", -1.0)) <= 0.0
            or int(nvidia_device.get("memory_free_mib", -1))
            > int(nvidia_device.get("memory_total_mib", -1))
            or abs(
                int(nvidia_device.get("memory_total_mib", -1)) * 1024 * 1024
                - int(config["runtime_identity"]["cuda_total_memory_bytes"])
            )
            > 16 * 1024 * 1024
        ):
            errors.append(f"{label} nvidia-smi device identity is invalid")

    memory = audit.get("memory")
    if not isinstance(memory, Mapping) or set(memory) != {
        "total_bytes",
        "available_bytes",
    } or any(
        not isinstance(memory.get(key), int)
        or isinstance(memory.get(key), bool)
        or int(memory.get(key, 0)) < 0
        for key in ("total_bytes", "available_bytes")
    ) or int(memory.get("available_bytes", 0)) > int(memory.get("total_bytes", 0)):
        errors.append(f"{label} physical-memory observation is invalid")

    disk = audit.get("disk")
    if not isinstance(disk, Mapping) or set(disk) != {
        "path",
        "total_bytes",
        "used_bytes",
        "free_bytes",
    } or (
        not isinstance(disk.get("path"), str)
        or not disk.get("path")
        or any(
            not isinstance(disk.get(key), int)
            or isinstance(disk.get(key), bool)
            or int(disk.get(key, -1)) < 0
            for key in ("total_bytes", "used_bytes", "free_bytes")
        )
        or int(disk.get("used_bytes", -1)) + int(disk.get("free_bytes", -1))
        != int(disk.get("total_bytes", -1))
        or int(disk.get("free_bytes", -1)) < minimum_disk_bytes
    ):
        errors.append(f"{label} disk observation is invalid")

    cpu = audit.get("cpu")
    if not isinstance(cpu, Mapping) or set(cpu) != {"logical_count"} or (
        not isinstance(cpu.get("logical_count"), int)
        or isinstance(cpu.get("logical_count"), bool)
        or int(cpu.get("logical_count", 0)) <= 0
    ):
        errors.append(f"{label} CPU observation is invalid")
    platform = audit.get("platform")
    if not isinstance(platform, Mapping) or set(platform) != {
        "system",
        "release",
        "version",
        "machine",
        "processor",
        "hostname",
    } or any(not isinstance(value, str) for value in platform.values()):
        errors.append(f"{label} platform observation is invalid")
    environment = audit.get("environment")
    if not isinstance(environment, Mapping) or set(environment) != {
        "CUDA_VISIBLE_DEVICES",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
    } or any(
        value is not None and not isinstance(value, str)
        for value in environment.values()
    ):
        errors.append(f"{label} environment observation is invalid")

    conservative = _audit_conservative_vram(audit)
    if conservative is None or conservative["conservative_free_bytes"] < minimum_vram_bytes:
        errors.append(f"{label} conservative free VRAM is below the frozen threshold")
    return errors


def _resource_pair_errors(
    audited: Mapping[str, Any],
    live: Mapping[str, Any],
    validation: Any,
    config: Mapping[str, Any],
    *,
    label: str,
    minimum_free_vram_bytes: int | None = None,
) -> list[str]:
    errors: list[str] = []
    audited_torch = audited.get("torch_runtime")
    live_torch = live.get("torch_runtime")
    audited_nvidia = audited.get("nvidia")
    live_nvidia = live.get("nvidia")
    audited_python = audited.get("python")
    live_python = live.get("python")
    audited_packages = audited.get("packages")
    live_packages = live.get("packages")
    audited_memory = audited.get("memory")
    live_memory = live.get("memory")
    if not all(
        isinstance(value, Mapping)
        for value in (
            audited_torch,
            live_torch,
            audited_nvidia,
            live_nvidia,
            audited_python,
            live_python,
            audited_packages,
            live_packages,
            audited_memory,
            live_memory,
        )
    ):
        return [f"{label} resource pair is incomplete"]
    audited_torch_device = _audit_indexed_record(
        audited_torch.get("devices"), label="audited Torch device"
    )
    live_torch_device = _audit_indexed_record(
        live_torch.get("devices"), label="live Torch device"
    )
    audited_nvidia_device = _audit_indexed_record(
        audited_nvidia.get("gpus"), label="audited nvidia-smi device"
    )
    live_nvidia_device = _audit_indexed_record(
        live_nvidia.get("gpus"), label="live nvidia-smi device"
    )
    if None in (
        audited_torch_device,
        live_torch_device,
        audited_nvidia_device,
        live_nvidia_device,
    ):
        return [f"{label} resource pair has no exact CUDA device"]
    for key in ("version", "implementation"):
        if audited_python.get(key) != live_python.get(key):
            errors.append(f"{label} Python identity drifted: {key}")
    audited_executable = audited_python.get("executable")
    live_executable = live_python.get("executable")
    if (
        not isinstance(audited_executable, str)
        or not isinstance(live_executable, str)
        or os.path.normcase(str(Path(audited_executable).resolve(strict=False)))
        != os.path.normcase(str(Path(live_executable).resolve(strict=False)))
    ):
        errors.append(f"{label} Python executable drifted")
    audited_platform = audited.get("platform")
    live_platform = live.get("platform")
    if not isinstance(audited_platform, Mapping) or not isinstance(
        live_platform, Mapping
    ):
        errors.append(f"{label} platform identity is missing")
    else:
        for key in ("system", "machine", "hostname"):
            if audited_platform.get(key) != live_platform.get(key):
                errors.append(f"{label} platform identity drifted: {key}")
    for package in _RESOURCE_PACKAGES:
        if audited_packages.get(package) != live_packages.get(package):
            errors.append(f"{label} package identity drifted: {package}")
    for key in (
        "available",
        "version",
        "compiled_cuda_version",
        "cuda_available",
        "device_count",
    ):
        if audited_torch.get(key) != live_torch.get(key):
            errors.append(f"{label} Torch identity drifted: {key}")
    for key in ("name", "capability", "total_memory_bytes"):
        if audited_torch_device.get(key) != live_torch_device.get(key):
            errors.append(f"{label} CUDA device identity drifted: {key}")
    for key in ("name", "uuid", "memory_total_mib", "driver_version"):
        if audited_nvidia_device.get(key) != live_nvidia_device.get(key):
            errors.append(f"{label} nvidia-smi identity drifted: {key}")
    audited_environment = audited.get("environment")
    live_environment = live.get("environment")
    if not isinstance(audited_environment, Mapping) or not isinstance(
        live_environment, Mapping
    ) or audited_environment.get("CUDA_VISIBLE_DEVICES") != live_environment.get(
        "CUDA_VISIBLE_DEVICES"
    ):
        errors.append(f"{label} CUDA_VISIBLE_DEVICES identity drifted")

    audited_vram = _audit_conservative_vram(audited)
    live_vram = _audit_conservative_vram(live)
    weight_bytes = int(config["artifact"]["model_safetensors_size_bytes"])
    minimum_ram = weight_bytes * 2
    minimum_vram = (
        (weight_bytes * 3 + 1) // 2
        if minimum_free_vram_bytes is None
        else minimum_free_vram_bytes
    )
    audited_ram = audited_memory.get("available_bytes")
    live_ram = live_memory.get("available_bytes")
    if (
        audited_vram is None
        or live_vram is None
        or not isinstance(audited_ram, int)
        or isinstance(audited_ram, bool)
        or not isinstance(live_ram, int)
        or isinstance(live_ram, bool)
    ):
        errors.append(f"{label} dynamic resource evidence is invalid")
        return errors
    if min(
        audited_vram["conservative_free_bytes"],
        live_vram["conservative_free_bytes"],
    ) < minimum_vram:
        errors.append(f"{label} conservative free VRAM is below the required threshold")
    ram_passed = min(audited_ram, live_ram) >= minimum_ram
    expected = {
        "packages": {
            package: live_packages[package] for package in _RESOURCE_PACKAGES
        },
        "python": dict(live_python),
        "torch_runtime": {
            "version": live_torch.get("version"),
            "compiled_cuda_version": live_torch.get("compiled_cuda_version"),
            "device": dict(live_torch_device),
        },
        "nvidia_smi_device": dict(live_nvidia_device),
        "audited_available_ram_bytes": audited_ram,
        "live_available_ram_bytes": live_ram,
        "conservative_available_ram_bytes": min(audited_ram, live_ram),
        "minimum_available_ram_bytes": minimum_ram,
        "ram_threshold_enforced": False,
        "ram_threshold_passed": ram_passed,
        "ram_threshold_override_used": not ram_passed,
        "audited_vram": audited_vram,
        "live_vram": live_vram,
        "minimum_free_vram_bytes": minimum_vram,
    }
    if (
        not isinstance(validation, Mapping)
        or canonical_json_sha256(validation) != canonical_json_sha256(expected)
    ):
        errors.append(f"{label} derived resource validation mismatch")
    return errors


def _resource_audit_payloads(audit: Mapping[str, Any]) -> tuple[bytes, ...]:
    try:
        rendered = json.dumps(
            audit,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return ()
    lf = (rendered + "\n").encode("utf-8")
    crlf = (rendered.replace("\n", "\r\n") + "\r\n").encode("utf-8")
    return (lf,) if lf == crlf else (lf, crlf)


def _resource_audit_hash_matches(audit: Mapping[str, Any], observed: Any) -> bool:
    return isinstance(observed, str) and observed in {
        hashlib.sha256(payload).hexdigest()
        for payload in _resource_audit_payloads(audit)
    }


def _resource_receipt_errors(
    receipt: Mapping[str, Any],
    resource_audit: Mapping[str, Any],
    resource_audit_bytes: bytes,
    config: Mapping[str, Any],
    *,
    expected_git_head: str,
    label: str,
) -> list[str]:
    limits = config["resource_limits"]
    try:
        parsed_resource_audit = json.loads(resource_audit_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed_resource_audit = None
    canonical_resource_audit_bytes = _resource_audit_payloads(resource_audit)
    if (
        parsed_resource_audit != resource_audit
        or not canonical_resource_audit_bytes
        or resource_audit_bytes not in canonical_resource_audit_bytes
    ):
        return [f"{label} raw resource-audit object/payload mismatch"]
    errors = _resource_audit_errors(
        resource_audit,
        config,
        expected_git_head=expected_git_head,
        label=f"{label} supplied resource audit",
        minimum_disk_bytes=limits["minimum_staging_output_free_bytes"],
        minimum_vram_bytes=limits["minimum_preload_free_vram_bytes"],
    )
    preflight = receipt.get("resource_preflight")
    if not isinstance(preflight, Mapping) or set(preflight) != _RESOURCE_PREFLIGHT_KEYS:
        errors.append(f"{label} resource-preflight fields are not exact")
        return errors
    if (
        hashlib.sha256(resource_audit_bytes).hexdigest()
        != preflight.get("resource_audit_sha256")
        or resource_audit.get("captured_at")
        != preflight.get("resource_audit_captured_at")
        or preflight.get("git_head") != expected_git_head
    ):
        errors.append(f"{label} does not bind its supplied resource audit")
    age = preflight.get("resource_audit_age_seconds")
    audit_time = _utc_timestamp(resource_audit.get("captured_at"))
    started = _utc_timestamp(receipt.get("started_at"))
    completed = _utc_timestamp(receipt.get("completed_at"))
    if (
        not _finite_number(age)
        or not 0.0 <= float(age) <= 900.0
        or audit_time is None
        or started is None
        or completed is None
        or not audit_time <= started <= completed
        or not (started - audit_time).total_seconds() - 2.0
        <= float(age)
        <= (completed - audit_time).total_seconds() + 2.0
    ):
        errors.append(f"{label} supplied resource-audit age is invalid")
    disk = resource_audit.get("disk")
    if not isinstance(disk, Mapping) or not all(
        isinstance(preflight.get(key), str) and preflight.get(key)
        for key in ("audit_disk_path", "cache_storage_path")
    ) or (
        disk.get("path") != preflight.get("audit_disk_path")
        or preflight.get("audit_disk_path")
        != preflight.get("cache_storage_path")
        or not isinstance(disk.get("path"), str)
        or not Path(str(disk.get("path"))).is_absolute()
        or str(Path(str(disk.get("path"))).resolve(strict=False))
        != str(disk.get("path"))
        or preflight.get("audit_disk_free_bytes") != disk.get("free_bytes")
        or not isinstance(preflight.get("live_disk_free_bytes"), int)
        or preflight.get("live_disk_free_bytes", 0)
        < limits["minimum_staging_output_free_bytes"]
        or type(preflight.get("filesystem_device")) is not int
    ):
        errors.append(f"{label} cache-bound disk evidence is invalid")

    live_audit = preflight.get("live_resource_audit")
    post_import_audit = preflight.get("post_import_resource_audit")
    if not isinstance(live_audit, Mapping) or not isinstance(
        post_import_audit, Mapping
    ):
        errors.append(f"{label} live resource audits are missing")
        return errors
    errors.extend(
        _resource_audit_errors(
            live_audit,
            config,
            expected_git_head=expected_git_head,
            label=f"{label} live pre-import resource audit",
            minimum_disk_bytes=limits["minimum_staging_output_free_bytes"],
            minimum_vram_bytes=limits["minimum_preload_free_vram_bytes"],
        )
    )
    errors.extend(
        _resource_audit_errors(
            post_import_audit,
            config,
            expected_git_head=expected_git_head,
            label=f"{label} post-import resource audit",
            minimum_disk_bytes=limits["minimum_output_free_bytes"],
            minimum_vram_bytes=limits["minimum_preload_free_vram_bytes"],
        )
    )
    for prefix, audit in (
        ("live", live_audit),
        ("post_import", post_import_audit),
    ):
        audit_disk = audit.get("disk")
        captured_key = f"{prefix}_resource_audit_captured_at"
        age_key = f"{prefix}_resource_audit_age_seconds"
        semantic_key = f"{prefix}_resource_audit_semantic_sha256"
        if (
            preflight.get(captured_key) != audit.get("captured_at")
            or preflight.get(semantic_key) != canonical_json_sha256(audit)
            or not _resource_audit_hash_matches(
                audit, preflight.get(f"{prefix}_resource_audit_sha256")
            )
            or not isinstance(audit_disk, Mapping)
            or audit_disk.get("path") != preflight.get("cache_storage_path")
            or not _finite_number(preflight.get(age_key))
            or not 0.0 <= float(preflight.get(age_key, -1.0)) <= 900.0
        ):
            errors.append(f"{label} {prefix} resource-audit binding is invalid")
    errors.extend(
        _resource_pair_errors(
            resource_audit,
            live_audit,
            preflight.get("execution_resource_validation"),
            config,
            label=f"{label} pre-import",
            minimum_free_vram_bytes=limits["minimum_preload_free_vram_bytes"],
        )
    )
    errors.extend(
        _resource_pair_errors(
            resource_audit,
            post_import_audit,
            preflight.get("post_import_resource_validation"),
            config,
            label=f"{label} post-import",
            minimum_free_vram_bytes=limits["minimum_preload_free_vram_bytes"],
        )
    )

    ordered_audits: list[tuple[str, Mapping[str, Any], float]] = []
    for prefix, audit in (
        ("live", live_audit),
        ("post_import", post_import_audit),
    ):
        age_value = preflight.get(f"{prefix}_resource_audit_age_seconds")
        if _finite_number(age_value):
            ordered_audits.append((prefix, audit, float(age_value)))

    for key, expected_label in (
        ("post_load_resource", "post-load"),
        ("post_score_resource", "post-score"),
    ):
        observed = receipt.get(key)
        if not isinstance(observed, Mapping) or set(observed) != {
            "label",
            "audit_sha256",
            "audit_semantic_sha256",
            "captured_at",
            "age_seconds",
            "conservative_vram",
            "execution_resource_validation",
            "audit",
        }:
            errors.append(f"{label} {key} fields are not exact")
            continue
        embedded = observed.get("audit")
        if not isinstance(embedded, Mapping):
            errors.append(f"{label} {key} audit is missing")
            continue
        errors.extend(
            _resource_audit_errors(
                embedded,
                config,
                expected_git_head=expected_git_head,
                label=f"{label} {key} audit",
                minimum_disk_bytes=limits["minimum_output_free_bytes"],
                minimum_vram_bytes=limits["minimum_postload_global_free_vram_bytes"],
            )
        )
        conservative = _audit_conservative_vram(embedded)
        embedded_disk = embedded.get("disk")
        if (
            observed.get("label") != expected_label
            or not _resource_audit_hash_matches(
                embedded, observed.get("audit_sha256")
            )
            or observed.get("audit_semantic_sha256")
            != canonical_json_sha256(embedded)
            or observed.get("captured_at") != embedded.get("captured_at")
            or not isinstance(embedded_disk, Mapping)
            or embedded_disk.get("path") != preflight.get("cache_storage_path")
            or not _finite_number(observed.get("age_seconds"))
            or not 0.0 <= float(observed.get("age_seconds", -1.0)) <= 900.0
            or observed.get("conservative_vram") != conservative
        ):
            errors.append(f"{label} {key} resource binding is invalid")
        errors.extend(
            _resource_pair_errors(
                post_import_audit,
                embedded,
                observed.get("execution_resource_validation"),
                config,
                label=f"{label} {key}",
                minimum_free_vram_bytes=limits[
                    "minimum_postload_global_free_vram_bytes"
                ],
            )
        )
        age_value = observed.get("age_seconds")
        if _finite_number(age_value):
            ordered_audits.append((key, embedded, float(age_value)))

    chronology = [
        ("supplied", resource_audit, float(age) if _finite_number(age) else -1.0),
        *ordered_audits,
    ]
    chronology_times = [
        _utc_timestamp(audit.get("captured_at")) for _, audit, _ in chronology
    ]
    embedded_raw_hashes = [
        preflight.get("live_resource_audit_sha256"),
        preflight.get("post_import_resource_audit_sha256"),
        (
            receipt.get("post_load_resource", {}).get("audit_sha256")
            if isinstance(receipt.get("post_load_resource"), Mapping)
            else None
        ),
        (
            receipt.get("post_score_resource", {}).get("audit_sha256")
            if isinstance(receipt.get("post_score_resource"), Mapping)
            else None
        ),
    ]
    if (
        started is None
        or completed is None
        or len(chronology_times) != 5
        or any(observed is None for observed in chronology_times)
        or not chronology_times[0] <= started
        or not started < chronology_times[1]
        or not all(
            earlier < later
            for earlier, later in zip(chronology_times[1:], chronology_times[2:])
        )
        or not chronology_times[-1] < completed
        or any(not _hex_identity(value, 64) for value in embedded_raw_hashes)
        or len(set(embedded_raw_hashes)) != len(embedded_raw_hashes)
    ):
        errors.append(f"{label} embedded resource-audit chronology is invalid")
    else:
        measurement_windows = [
            (started, chronology_times[1]),
            (chronology_times[1], chronology_times[2]),
            (chronology_times[2], chronology_times[3]),
            (chronology_times[3], chronology_times[4]),
            (chronology_times[4], completed),
        ]
        tolerance_seconds = 2.0
        for (stage, audit, observed_age), (window_start, window_end) in zip(
            chronology, measurement_windows, strict=True
        ):
            captured = _utc_timestamp(audit.get("captured_at"))
            assert captured is not None
            measured_at = captured + timedelta(seconds=observed_age)
            if (
                observed_age < 0.0
                or measured_at < window_start - timedelta(seconds=tolerance_seconds)
                or measured_at > window_end + timedelta(seconds=tolerance_seconds)
            ):
                errors.append(f"{label} {stage} resource-audit age is inconsistent")
    return errors


def validate_complete_receipt(
    receipt: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    tokenizer_audit: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    if frozenset(receipt) != _COMPLETE_RECEIPT_KEYS:
        errors.append("runtime receipt top-level fields are not exact")
    if not _self_hash_valid(receipt, "receipt_sha256"):
        errors.append("runtime receipt self-hash mismatch")
    if (
        type(receipt.get("schema_version")) is not int
        or receipt.get("schema_version") != 1
        or receipt.get("receipt_type") != "registry-score-runtime"
        or receipt.get("status") != "complete"
    ):
        errors.append("runtime receipt status/schema mismatch")
    if receipt.get("network_access_permitted") is not False:
        errors.append("runtime receipt network policy mismatch")
    if receipt.get("network_observation") != "not-instrumented":
        errors.append("runtime receipt network observation mismatch")
    if receipt.get("scientific_claim_authorized") is not False:
        errors.append("runtime receipt claim boundary mismatch")
    if receipt.get("attempt") not in {"a", "b"}:
        errors.append("runtime receipt attempt is invalid")
    if not isinstance(receipt.get("run_id"), str) or not str(
        receipt.get("run_id")
    ).startswith("run-"):
        errors.append("runtime receipt run identity is invalid")
    if (
        not isinstance(receipt.get("process_id"), int)
        or isinstance(receipt.get("process_id"), bool)
        or int(receipt.get("process_id", 0)) <= 0
    ):
        errors.append("runtime receipt process identity is invalid")
    started_at = _utc_timestamp(receipt.get("started_at"))
    completed_at = _utc_timestamp(receipt.get("completed_at"))
    if started_at is None:
        errors.append("runtime receipt started_at is invalid")
    if completed_at is None:
        errors.append("runtime receipt completed_at is invalid")
    if started_at is not None and completed_at is not None and completed_at < started_at:
        errors.append("runtime receipt timestamps are out of order")

    git = receipt.get("git")
    expected_git_keys = {
        "git_head",
        "worktree_clean",
        "model_manifest_git_blob",
        "development_registry_git_blob",
        "scoring_config_git_blob",
    }
    if not isinstance(git, Mapping) or set(git) != expected_git_keys:
        errors.append("runtime receipt Git binding fields are not exact")
    else:
        if not _hex_identity(git.get("git_head"), 40) or git.get(
            "worktree_clean"
        ) is not True:
            errors.append("runtime receipt Git head/clean binding is invalid")
        canonical = config["canonical_inputs"]
        if (
            git.get("model_manifest_git_blob") != canonical["manifest_git_blob"]
            or git.get("development_registry_git_blob")
            != canonical["registry_git_blob"]
            or git.get("scoring_config_git_blob") != FROZEN_CONFIG_GIT_BLOB
        ):
            errors.append("runtime receipt Git blob identity mismatch")
        expected_run_id = build_run_identity(
            {
                "run_kind": config["run_kind"],
                "git_head": git.get("git_head"),
                "run_spec_sha256": FROZEN_RUN_SPEC_SHA256,
                "artifact": config["artifact"],
                "registry_sha256": config["canonical_inputs"]["registry_sha256"],
                "accepted_tokenizer_output_sha256": config[
                    "accepted_tokenizer_audit"
                ]["output_sha256"],
            }
        )["run_id"]
        if receipt.get("run_id") != expected_run_id:
            errors.append("runtime receipt run identity does not match frozen inputs")
    run_spec = receipt.get("run_spec")
    if not isinstance(run_spec, Mapping) or dict(run_spec) != {
        "sha256": FROZEN_RUN_SPEC_SHA256,
        "git_blob": FROZEN_CONFIG_GIT_BLOB,
    }:
        errors.append("runtime receipt run-spec identity mismatch")
    canonical_inputs = receipt.get("canonical_inputs")
    if not isinstance(canonical_inputs, Mapping) or dict(canonical_inputs) != {
        "model_manifest_sha256": config["canonical_inputs"]["manifest_sha256"],
        "registry_sha256": config["canonical_inputs"]["registry_sha256"],
    }:
        errors.append("runtime receipt canonical-input identity mismatch")
    accepted = receipt.get("accepted_tokenizer")
    if not isinstance(accepted, Mapping) or dict(accepted) != {
        "file_sha256": config["accepted_tokenizer_audit"]["file_sha256"],
        "output_sha256": config["accepted_tokenizer_audit"]["output_sha256"],
    }:
        errors.append("runtime receipt accepted-tokenizer identity mismatch")

    snapshot = receipt.get("snapshot_verification")
    expected_snapshot = tokenizer_audit.get("snapshot_verification")
    if not isinstance(snapshot, Mapping) or not isinstance(
        expected_snapshot, Mapping
    ) or dict(snapshot) != dict(expected_snapshot):
        errors.append("runtime receipt snapshot identity mismatch")
    tokenizer = receipt.get("tokenizer_validation")
    expected_tokenizer = tokenizer_audit.get("loaded_tokenizer_validation")
    if not isinstance(tokenizer, Mapping) or not isinstance(
        expected_tokenizer, Mapping
    ) or dict(tokenizer) != dict(expected_tokenizer):
        errors.append("runtime receipt tokenizer validation mismatch")
    runtime = receipt.get("runtime_identity")
    expected_runtime = config["runtime_identity"]
    expected_runtime_record = {
        "python": expected_runtime["python"],
        "packages": expected_runtime["packages"],
        "cuda_runtime": expected_runtime["cuda_runtime"],
        "cuda_device": {
            "index": expected_runtime["cuda_device_index"],
            "name": expected_runtime["cuda_device_name"],
            "capability": expected_runtime["cuda_compute_capability"],
            "total_memory_bytes": expected_runtime["cuda_total_memory_bytes"],
        },
        "verified": True,
    }
    if not isinstance(runtime, Mapping) or dict(runtime) != expected_runtime_record:
        errors.append("runtime receipt software/device identity mismatch")
    determinism = receipt.get("determinism")
    expected_determinism = {
        "attention_implementation": config["determinism"][
            "attention_implementation"
        ],
        "sdpa_backends": config["determinism"]["sdpa_backends"],
        "sdpa_math_allow_fp16_reduction": config["determinism"][
            "sdpa_math_allow_fp16_reduction"
        ],
        "algorithms": True,
        "cublas_workspace_config": config["determinism"][
            "cublas_workspace_config"
        ],
        "tf32": False,
        "cudnn_tf32": False,
        "cudnn_benchmark": False,
        "float32_matmul_precision": config["determinism"][
            "float32_matmul_precision"
        ],
        "manual_seed": 0,
        "verified": True,
    }
    if not isinstance(determinism, Mapping) or dict(
        determinism
    ) != expected_determinism:
        errors.append("runtime receipt determinism identity mismatch")
    model_validation = receipt.get("model_validation")
    expected_model_keys = {
        "class",
        "model_type",
        "parameter_count",
        "parameter_dtypes",
        "parameter_devices",
        "buffer_devices",
        "vocabulary_size",
        "eval_mode",
        "quantized",
        "device_map",
        "offload_hooks",
        "meta_parameters",
        "meta_buffers",
        "attention_implementation",
        "sdpa_backends",
        "sdpa_math_allow_fp16_reduction",
        "verified",
        "determinism",
    }
    if not isinstance(model_validation, Mapping) or set(
        model_validation
    ) != expected_model_keys or (
        model_validation.get("verified") is not True
        or model_validation.get("class") != config["model"]["class"]
        or model_validation.get("model_type") != config["model"]["model_type"]
        or model_validation.get("parameter_count")
        != config["model"]["parameter_count"]
        or model_validation.get("parameter_dtypes") != ["torch.float16"]
        or model_validation.get("parameter_devices") != ["cuda:0"]
        or not isinstance(model_validation.get("buffer_devices"), list)
        or any(
            device != "cuda:0"
            for device in model_validation.get("buffer_devices", [])
        )
        or model_validation.get("vocabulary_size")
        != config["model"]["vocabulary_size"]
        or model_validation.get("eval_mode") is not True
        or model_validation.get("quantized") is not False
        or model_validation.get("device_map") is not False
        or model_validation.get("offload_hooks") is not False
        or model_validation.get("meta_parameters") is not False
        or model_validation.get("meta_buffers") is not False
        or model_validation.get("attention_implementation") != "sdpa"
        or model_validation.get("sdpa_backends") != ["math"]
        or model_validation.get("sdpa_math_allow_fp16_reduction") is not False
        or model_validation.get("determinism") != determinism
    ):
        errors.append("runtime receipt model validation mismatch")
    loading_info = receipt.get("model_loading_info")
    if not isinstance(loading_info, Mapping) or dict(loading_info) != {
        "error_msgs": [],
        "mismatched_keys": [],
        "missing_keys": [],
        "unexpected_keys": [],
    }:
        errors.append("runtime receipt model loading diagnostics are not empty")
    controls = receipt.get("execution_controls")
    if not isinstance(controls, Mapping) or dict(controls) != {
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "autocast": False,
        "local_files_only": True,
        "model_weights_deserialized": True,
        "private_model_staging": True,
        "private_tokenizer_staging": True,
        "trust_remote_code": False,
        "use_safetensors": True,
        "weights_downloaded": False,
    }:
        errors.append("runtime receipt execution controls mismatch")

    preflight = receipt.get("resource_preflight")
    if not isinstance(preflight, Mapping) or (
        not _hex_identity(preflight.get("resource_audit_sha256"), 64)
        or not isinstance(preflight.get("resource_audit_captured_at"), str)
        or preflight.get("git_head")
        != (git.get("git_head") if isinstance(git, Mapping) else None)
        or not _finite_number(preflight.get("resource_audit_age_seconds"))
        or float(preflight.get("resource_audit_age_seconds", -1.0)) < 0.0
        or not isinstance(preflight.get("execution_resource_validation"), Mapping)
        or not isinstance(preflight.get("post_import_resource_validation"), Mapping)
        or not _hex_identity(
            preflight.get("post_import_resource_audit_sha256"), 64
        )
    ):
        errors.append("runtime receipt supplied resource-audit binding is invalid")
    output_storage = receipt.get("output_storage")
    if not isinstance(output_storage, Mapping) or set(output_storage) != {
        "minimum_free_bytes",
        "preflight_passed",
        "prepublication_passed",
        "preflight",
        "prepublication",
        "wall_measurement_scope",
        "final_wall_limit_seconds",
        "final_wall_limit_passed",
    } or (
        output_storage.get("minimum_free_bytes")
        != config["resource_limits"]["minimum_output_free_bytes"]
        or output_storage.get("preflight_passed") is not True
        or output_storage.get("prepublication_passed") is not True
        or output_storage.get("wall_measurement_scope")
        != "through-score-fsync-before-runtime-receipt"
        or output_storage.get("final_wall_limit_seconds")
        != config["resource_limits"]["maximum_invocation_wall_seconds"]
        or output_storage.get("final_wall_limit_passed") is not True
    ):
        errors.append("runtime receipt output-storage gate mismatch")
    else:
        for phase in ("preflight", "prepublication"):
            observation = output_storage.get(phase)
            if not isinstance(observation, Mapping) or set(observation) != {
                "phase",
                "minimum_free_bytes",
                "outputs",
                "passed",
            } or (
                observation.get("phase") != phase
                or observation.get("minimum_free_bytes")
                != config["resource_limits"]["minimum_output_free_bytes"]
                or observation.get("passed") is not True
            ):
                errors.append(
                    f"runtime receipt output-storage {phase} observation mismatch"
                )
                continue
            outputs = observation.get("outputs")
            if not isinstance(outputs, Mapping) or set(outputs) != {
                "score",
                "runtime",
            }:
                errors.append(
                    f"runtime receipt output-storage {phase} outputs mismatch"
                )
                continue
            for label in ("score", "runtime"):
                value = outputs.get(label)
                if not isinstance(value, Mapping) or set(value) != {
                    "filesystem_device",
                    "free_bytes",
                } or (
                    not isinstance(value.get("filesystem_device"), int)
                    or isinstance(value.get("filesystem_device"), bool)
                    or not isinstance(value.get("free_bytes"), int)
                    or isinstance(value.get("free_bytes"), bool)
                    or value.get("free_bytes", 0)
                    < config["resource_limits"]["minimum_output_free_bytes"]
                ):
                    errors.append(
                        f"runtime receipt output-storage {phase}/{label} identity mismatch"
                    )
    minimum_postload = config["resource_limits"][
        "minimum_postload_global_free_vram_bytes"
    ]
    for key, expected_label in (
        ("post_load_resource", "post-load"),
        ("post_score_resource", "post-score"),
    ):
        resource = receipt.get(key)
        observed_free = _resource_conservative_free(resource)
        if not isinstance(resource, Mapping) or set(resource) != {
            "label",
            "audit_sha256",
            "audit_semantic_sha256",
            "captured_at",
            "age_seconds",
            "conservative_vram",
            "execution_resource_validation",
            "audit",
        } or (
            resource.get("label") != expected_label
            or not _hex_identity(resource.get("audit_sha256"), 64)
            or not isinstance(resource.get("captured_at"), str)
            or not _finite_number(resource.get("age_seconds"))
            or float(resource.get("age_seconds", -1.0)) < 0.0
            or not isinstance(resource.get("execution_resource_validation"), Mapping)
            or not isinstance(resource.get("audit"), Mapping)
            or observed_free is None
            or observed_free < minimum_postload
        ):
            errors.append(f"runtime receipt {key} VRAM gate mismatch")

    metrics = receipt.get("metrics")
    topology = config["registry_topology"]
    if not isinstance(metrics, Mapping):
        errors.append("runtime receipt metrics are missing")
    else:
        expected_metric_keys = {
            "load_seconds",
            "wall_seconds",
            "process_max_rss_bytes",
            "peak_allocated_bytes",
            "peak_reserved_bytes",
            "candidate_forward_count",
            "forward_seconds",
            "aggregate_forward_seconds",
            "forwarded_token_count",
            "predicted_token_count",
            "continuation_token_count",
            "maximum_full_token_count",
            "math_sdpa_forward_count",
            "autocast_disabled_forward_count",
        }
        if set(metrics) != expected_metric_keys:
            errors.append("runtime receipt metric fields are not exact")
        for key in (
            "load_seconds",
            "wall_seconds",
            "aggregate_forward_seconds",
        ):
            if not _finite_number(metrics.get(key)) or float(metrics[key]) < 0:
                errors.append(f"runtime receipt metric is invalid: {key}")
        if _finite_number(metrics.get("wall_seconds")) and float(
            metrics["wall_seconds"]
        ) > config["resource_limits"]["maximum_invocation_wall_seconds"]:
            errors.append("runtime receipt wall-time gate failed")
        if (
            _finite_number(metrics.get("load_seconds"))
            and _finite_number(metrics.get("wall_seconds"))
            and float(metrics["load_seconds"]) > float(metrics["wall_seconds"])
        ):
            errors.append("runtime receipt load time exceeds wall time")
        if (
            _finite_number(metrics.get("aggregate_forward_seconds"))
            and _finite_number(metrics.get("wall_seconds"))
            and float(metrics["aggregate_forward_seconds"])
            > float(metrics["wall_seconds"])
        ):
            errors.append("runtime receipt forward time exceeds wall time")
        if started_at is not None and completed_at is not None and _finite_number(
            metrics.get("wall_seconds")
        ):
            timestamp_elapsed = (completed_at - started_at).total_seconds()
            if abs(timestamp_elapsed - float(metrics["wall_seconds"])) > 5.0:
                errors.append("runtime receipt timestamp/wall duration mismatch")
        for key in (
            "process_max_rss_bytes",
            "peak_allocated_bytes",
            "peak_reserved_bytes",
        ):
            if not isinstance(metrics.get(key), int) or isinstance(
                metrics.get(key), bool
            ) or metrics[key] < 0:
                errors.append(f"runtime receipt metric is invalid: {key}")
        if isinstance(metrics.get("peak_reserved_bytes"), int) and metrics[
            "peak_reserved_bytes"
        ] > config["resource_limits"]["maximum_process_peak_reserved_bytes"]:
            errors.append("runtime receipt peak-reserved gate failed")
        if (
            isinstance(metrics.get("peak_allocated_bytes"), int)
            and isinstance(metrics.get("peak_reserved_bytes"), int)
            and metrics["peak_allocated_bytes"] > metrics["peak_reserved_bytes"]
        ):
            errors.append("runtime receipt allocated VRAM exceeds reserved VRAM")
        minimum_fp16_parameter_bytes = config["model"]["parameter_count"] * 2
        if (
            isinstance(metrics.get("peak_allocated_bytes"), int)
            and metrics["peak_allocated_bytes"] < minimum_fp16_parameter_bytes
        ):
            errors.append("runtime receipt peak allocation is below FP16 parameters")
        expected_metrics = {
            "candidate_forward_count": topology["candidate_count"],
            "math_sdpa_forward_count": topology["candidate_count"],
            "autocast_disabled_forward_count": topology["candidate_count"],
            "forwarded_token_count": topology["forwarded_token_count"],
            "predicted_token_count": topology["predicted_token_count"],
            "continuation_token_count": topology["continuation_token_count"],
            "maximum_full_token_count": topology["maximum_full_token_count"],
        }
        for key, expected in expected_metrics.items():
            if metrics.get(key) != expected:
                errors.append(f"runtime receipt scoring metric mismatch: {key}")
        forward_seconds = metrics.get("forward_seconds")
        if not isinstance(forward_seconds, list) or len(forward_seconds) != topology[
            "candidate_count"
        ] or not all(_finite_number(value) and float(value) >= 0 for value in forward_seconds):
            errors.append("runtime receipt per-forward timings are invalid")
        elif metrics.get("aggregate_forward_seconds") != sum(forward_seconds):
            errors.append("runtime receipt aggregate-forward timing mismatch")
    score = receipt.get("score")
    if not isinstance(score, Mapping) or set(score) != {
        "file_sha256",
        "output_sha256",
        "size_bytes",
    }:
        errors.append("runtime receipt score binding is missing")
    else:
        if not _hex_identity(score.get("file_sha256"), 64) or not _hex_identity(
            score.get("output_sha256"), 64
        ) or not isinstance(score.get("size_bytes"), int) or isinstance(
            score.get("size_bytes"), bool
        ) or score.get("size_bytes", 0) <= 0:
            errors.append("runtime receipt score binding is invalid")
    return tuple(errors)


def load_json_object(path: str | Path, label: str) -> tuple[dict[str, Any], bytes]:
    def exact_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ScoringRunError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        payload = _stable_bytes(Path(path), label)
        raw = json.loads(payload, object_pairs_hook=exact_object)
    except (OSError, json.JSONDecodeError) as error:
        raise ScoringRunError(f"cannot load {label}: {error}") from error
    if not isinstance(raw, Mapping):
        raise ScoringRunError(f"{label} root must be an object")
    return dict(raw), payload


def _repeat_resource_identity(
    receipt: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    preflight = receipt["resource_preflight"]
    platform = audit["platform"]
    python = audit["python"]
    environment = audit["environment"]
    torch_runtime = audit["torch_runtime"]
    nvidia = audit["nvidia"]
    torch_device = _audit_indexed_record(
        torch_runtime["devices"], label="repeat Torch device"
    )
    nvidia_device = _audit_indexed_record(
        nvidia["gpus"], label="repeat nvidia-smi device"
    )
    if torch_device is None or nvidia_device is None:
        raise ScoringRunError("repeat resource identity has no exact CUDA device")
    return {
        "platform": dict(platform),
        "cpu": dict(audit["cpu"]),
        "python": dict(python),
        "git_branch": audit["git"]["branch"],
        "cuda_visible_devices": environment["CUDA_VISIBLE_DEVICES"],
        "memory_total_bytes": audit["memory"]["total_bytes"],
        "disk": {
            "path": audit["disk"]["path"],
            "total_bytes": audit["disk"]["total_bytes"],
            "filesystem_device": preflight["filesystem_device"],
            "cache_storage_path": preflight["cache_storage_path"],
        },
        "torch_runtime": {
            "available": torch_runtime["available"],
            "version": torch_runtime["version"],
            "compiled_cuda_version": torch_runtime["compiled_cuda_version"],
            "cuda_available": torch_runtime["cuda_available"],
            "device_count": torch_runtime["device_count"],
            "device": {
                key: torch_device[key]
                for key in (
                    "index",
                    "name",
                    "capability",
                    "total_memory_bytes",
                )
            },
        },
        "nvidia_smi_device": {
            key: nvidia_device[key]
            for key in (
                "index",
                "name",
                "uuid",
                "memory_total_mib",
                "driver_version",
            )
        },
    }


def verify_scoring_repeat(
    *,
    score_a: Mapping[str, Any],
    score_a_bytes: bytes,
    receipt_a: Mapping[str, Any],
    receipt_a_bytes: bytes,
    resource_audit_a: Mapping[str, Any],
    resource_audit_a_bytes: bytes,
    score_b: Mapping[str, Any],
    score_b_bytes: bytes,
    receipt_b: Mapping[str, Any],
    receipt_b_bytes: bytes,
    resource_audit_b: Mapping[str, Any],
    resource_audit_b_bytes: bytes,
    config: Mapping[str, Any],
    registry: Sequence[Mapping[str, Any]],
    tokenizer_audit: Mapping[str, Any],
    expected_git_head: str,
) -> dict[str, Any]:
    score_errors = [
        *validate_score_artifact(
            score_a,
            config,
            registry=registry,
            tokenizer_audit=tokenizer_audit,
        ),
        *validate_score_artifact(
            score_b,
            config,
            registry=registry,
            tokenizer_audit=tokenizer_audit,
        ),
    ]
    receipt_errors = [
        *validate_complete_receipt(
            receipt_a,
            config,
            tokenizer_audit=tokenizer_audit,
        ),
        *validate_complete_receipt(
            receipt_b,
            config,
            tokenizer_audit=tokenizer_audit,
        ),
    ]
    if score_errors or receipt_errors:
        raise ScoringRunError("; ".join(score_errors + receipt_errors))
    if not _hex_identity(expected_git_head, 40):
        raise ScoringRunError("trusted execution Git head is invalid")
    resource_errors: list[str] = []
    for label, receipt, audit, payload in (
        ("A", receipt_a, resource_audit_a, resource_audit_a_bytes),
        ("B", receipt_b, resource_audit_b, resource_audit_b_bytes),
    ):
        if receipt["git"].get("git_head") != expected_git_head:
            resource_errors.append(
                f"repeat receipt {label} does not match the trusted execution head"
            )
        resource_errors.extend(
            _resource_receipt_errors(
                receipt,
                audit,
                payload,
                config,
                expected_git_head=expected_git_head,
                label=f"repeat receipt {label}",
            )
        )
    if resource_errors:
        raise ScoringRunError("; ".join(resource_errors))
    if canonical_json_sha256(
        _repeat_resource_identity(receipt_a, resource_audit_a)
    ) != canonical_json_sha256(
        _repeat_resource_identity(receipt_b, resource_audit_b)
    ):
        raise ScoringRunError("repeat attempts do not share one static host identity")
    if score_a_bytes != score_b_bytes:
        raise ScoringRunError("determinism-failed: score files differ byte for byte")
    if score_a_bytes != pretty_json_bytes(score_a) or score_b_bytes != pretty_json_bytes(
        score_b
    ):
        raise ScoringRunError("score files are not in canonical published form")
    if receipt_a_bytes != pretty_json_bytes(
        receipt_a
    ) or receipt_b_bytes != pretty_json_bytes(receipt_b):
        raise ScoringRunError("runtime receipts are not in canonical published form")
    if score_a != score_b:
        raise ScoringRunError("determinism-failed: parsed score artifacts differ")
    if receipt_a.get("attempt") != "a" or receipt_b.get("attempt") != "b":
        raise ScoringRunError("repeat receipts must be exact attempts a and b")
    if receipt_a.get("run_id") != receipt_b.get("run_id"):
        raise ScoringRunError("repeat receipt run identities differ")
    if receipt_a.get("process_id") == receipt_b.get("process_id"):
        raise ScoringRunError("repeat receipts do not show fresh processes")
    audit_a = receipt_a["resource_preflight"]
    audit_b = receipt_b["resource_preflight"]
    if (
        audit_a.get("resource_audit_sha256")
        == audit_b.get("resource_audit_sha256")
        or audit_a.get("resource_audit_captured_at")
        == audit_b.get("resource_audit_captured_at")
    ):
        raise ScoringRunError("repeat receipts do not bind distinct supplied audits")
    if resource_audit_a_bytes == resource_audit_b_bytes:
        raise ScoringRunError("repeat resource-audit files are not distinct")
    audit_a_time = _utc_timestamp(resource_audit_a.get("captured_at"))
    audit_b_time = _utc_timestamp(resource_audit_b.get("captured_at"))
    started_a = _utc_timestamp(receipt_a.get("started_at"))
    completed_a = _utc_timestamp(receipt_a.get("completed_at"))
    started_b = _utc_timestamp(receipt_b.get("started_at"))
    completed_b = _utc_timestamp(receipt_b.get("completed_at"))
    if (
        None in (
            audit_a_time,
            audit_b_time,
            started_a,
            completed_a,
            started_b,
            completed_b,
        )
        or not audit_a_time
        <= started_a
        <= completed_a
        <= audit_b_time
        <= started_b
        <= completed_b
    ):
        raise ScoringRunError(
            "repeat evidence does not show ordered fresh audit/process attempts"
        )
    immutable_keys = (
        "git",
        "run_spec",
        "canonical_inputs",
        "accepted_tokenizer",
        "snapshot_verification",
        "model_validation",
        "model_loading_info",
        "tokenizer_validation",
        "runtime_identity",
        "determinism",
        "execution_controls",
    )
    for key in immutable_keys:
        if canonical_json_sha256(receipt_a.get(key)) != canonical_json_sha256(
            receipt_b.get(key)
        ):
            raise ScoringRunError(
                f"repeat receipt immutable identity mismatch: {key}"
            )
    raw_sha256 = hashlib.sha256(score_a_bytes).hexdigest()
    for receipt in (receipt_a, receipt_b):
        binding = receipt["score"]
        if (
            binding.get("file_sha256") != raw_sha256
            or binding.get("size_bytes") != len(score_a_bytes)
            or binding.get("output_sha256") != score_a.get("output_sha256")
        ):
            raise ScoringRunError("repeat receipt score-file binding mismatch")
        contract = score_a["contract"]
        git = receipt["git"]
        if (
            contract.get("git_head") != git.get("git_head")
            or contract.get("run_spec_sha256")
            != receipt["run_spec"].get("sha256")
        ):
            raise ScoringRunError("score contract is not bound to its runtime receipt")
    receipt_records = []
    for receipt, payload in (
        (receipt_a, receipt_a_bytes),
        (receipt_b, receipt_b_bytes),
    ):
        receipt_records.append(
            {
                "attempt": receipt["attempt"],
                "file_sha256": hashlib.sha256(payload).hexdigest(),
                "receipt_sha256": receipt["receipt_sha256"],
                "size_bytes": len(payload),
            }
        )
    receipt_records.sort(key=lambda value: value["attempt"])
    result = {
        "schema_version": 1,
        "comparison_type": "registry-score-repeat",
        "status": "equal",
        "scientific_claim_authorized": False,
        "score_file_sha256": raw_sha256,
        "score_output_sha256": score_a["output_sha256"],
        "score_size_bytes": len(score_a_bytes),
        "summary": score_a["summary"],
        "run_id": receipt_a["run_id"],
        "receipts": receipt_records,
    }
    result["comparison_sha256"] = canonical_json_sha256(result)
    return result
