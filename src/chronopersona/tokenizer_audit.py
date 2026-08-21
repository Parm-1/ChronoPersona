"""Deterministic tokenizer-only audits for evaluation registries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
from typing import Any

from .evaluation import canonical_json_sha256
from .tokenization import (
    ContinuationBoundaryError,
    ContinuationTruncationError,
    prepare_continuation,
)


class TokenizerAuditError(ValueError):
    """Raised when tokenizer audit configuration is invalid."""


def resolve_prefix_token_ids(
    tokenizer: Any,
    prefix_policy: str,
) -> tuple[int, ...]:
    """Resolve an explicit and recorded tokenizer prefix policy."""

    if prefix_policy == "none":
        return ()
    if prefix_policy == "bos":
        token_id = getattr(tokenizer, "bos_token_id", None)
        if not isinstance(token_id, int) or token_id < 0:
            raise TokenizerAuditError(
                "prefix_policy='bos' requires a non-negative bos_token_id"
            )
        return (token_id,)
    raise TokenizerAuditError(
        "prefix_policy must be 'none' or 'bos'"
    )


def _tokenizer_metadata(
    tokenizer: Any,
    *,
    portable_identity: str | None = None,
) -> dict[str, Any]:
    special_ids = {
        name: getattr(tokenizer, name, None)
        for name in (
            "bos_token_id",
            "eos_token_id",
            "pad_token_id",
            "unk_token_id",
        )
    }
    return {
        "class": tokenizer.__class__.__name__,
        "name_or_path": (
            portable_identity
            if portable_identity is not None
            else getattr(tokenizer, "name_or_path", None)
        ),
        "vocab_size": getattr(tokenizer, "vocab_size", None),
        "model_max_length": getattr(tokenizer, "model_max_length", None),
        "special_token_ids": special_ids,
    }


def audit_evaluation_tokenizer(
    items: Sequence[Mapping[str, Any]],
    tokenizer: Any,
    *,
    registry_sha256: str,
    artifact_id: str,
    artifact_revision: str,
    prefix_policy: str,
    max_length: int,
    tokenizer_identity: str | None = None,
    include_text_bindings: bool = False,
) -> dict[str, Any]:
    """Audit every prompt/candidate boundary without loading model weights."""

    if max_length < 2:
        raise TokenizerAuditError("max_length must be at least 2")
    for label, value in (
        ("registry_sha256", registry_sha256),
        ("artifact_id", artifact_id),
        ("artifact_revision", artifact_revision),
    ):
        if not isinstance(value, str) or not value:
            raise TokenizerAuditError(f"{label} must not be empty")
    if tokenizer_identity is not None and (
        not isinstance(tokenizer_identity, str) or not tokenizer_identity
    ):
        raise TokenizerAuditError("tokenizer_identity must not be empty")

    prefix_ids = resolve_prefix_token_ids(tokenizer, prefix_policy)
    item_outputs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    continuation_counts: list[int] = []
    full_counts: list[int] = []
    form_differences: list[int] = []

    for item in items:
        form_outputs: list[dict[str, Any]] = []
        for form in item["forms"]:
            candidate_outputs: list[dict[str, Any]] = []
            prompt_contexts: list[tuple[int, ...]] = []
            candidate_counts: list[int] = []
            for candidate in form["candidates"]:
                try:
                    prepared = prepare_continuation(
                        tokenizer,
                        str(form["prompt"]),
                        str(candidate["text"]),
                        max_length=max_length,
                        prefix_token_ids=prefix_ids,
                    )
                except (
                    ContinuationBoundaryError,
                    ContinuationTruncationError,
                    ValueError,
                ) as error:
                    failure = {
                        "item_id": item["item_id"],
                        "form_id": form["form_id"],
                        "pole": candidate["pole"],
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                    failures.append(failure)
                    candidate_outputs.append(
                        {
                            "pole": candidate["pole"],
                            "status": "failed",
                            "error_type": type(error).__name__,
                            "error": str(error),
                        }
                    )
                    continue

                prompt_contexts.append(prepared.prompt_token_ids)
                candidate_counts.append(len(prepared.continuation_token_ids))
                continuation_counts.append(
                    len(prepared.continuation_token_ids)
                )
                full_counts.append(len(prepared.full_token_ids))
                candidate_output = {
                        "pole": candidate["pole"],
                        "status": "passed",
                        "prompt_token_count": len(
                            prepared.prompt_token_ids
                        ),
                        "continuation_token_count": len(
                            prepared.continuation_token_ids
                        ),
                        "full_token_count": len(prepared.full_token_ids),
                        "continuation_start_index": (
                            prepared.continuation_start_index
                        ),
                        "first_prediction_index": (
                            prepared.first_prediction_index
                        ),
                        "final_prediction_index": (
                            prepared.final_prediction_index
                        ),
                        "continuation_token_ids": list(
                            prepared.continuation_token_ids
                        ),
                    }
                if include_text_bindings:
                    candidate_output.update(
                        {
                            "prompt_sha256": hashlib.sha256(
                                str(form["prompt"]).encode("utf-8")
                            ).hexdigest(),
                            "continuation_sha256": hashlib.sha256(
                                str(candidate["text"]).encode("utf-8")
                            ).hexdigest(),
                            "prompt_token_ids": list(
                                prepared.prompt_token_ids
                            ),
                        }
                    )
                candidate_outputs.append(candidate_output)

            prompt_context_match = (
                len(prompt_contexts) == 2
                and prompt_contexts[0] == prompt_contexts[1]
            )
            if len(prompt_contexts) == 2 and not prompt_context_match:
                failure = {
                    "item_id": item["item_id"],
                    "form_id": form["form_id"],
                    "pole": None,
                    "error_type": "PromptContextMismatch",
                    "error": (
                        "candidate prompt token IDs differ within one form"
                    ),
                }
                failures.append(failure)
            token_count_difference = (
                abs(candidate_counts[0] - candidate_counts[1])
                if len(candidate_counts) == 2
                else None
            )
            if token_count_difference is not None:
                form_differences.append(token_count_difference)
            form_outputs.append(
                {
                    "form_id": form["form_id"],
                    "prompt_context_match": prompt_context_match,
                    "continuation_token_count_difference": (
                        token_count_difference
                    ),
                    "candidates": candidate_outputs,
                }
            )

        item_outputs.append(
            {
                "item_id": item["item_id"],
                "domain": item["domain"],
                "forms": form_outputs,
            }
        )

    output: dict[str, Any] = {
        "schema_version": 1,
        "audit_type": "evaluation-tokenizer-audit",
        "registry_sha256": registry_sha256,
        "artifact": {
            "id": artifact_id,
            "revision": artifact_revision,
        },
        "tokenizer": _tokenizer_metadata(
            tokenizer,
            portable_identity=tokenizer_identity,
        ),
        "prefix_policy": prefix_policy,
        "prefix_token_ids": list(prefix_ids),
        "max_length": max_length,
        "summary": {
            "item_count": len(items),
            "form_count": sum(len(item["forms"]) for item in items),
            "candidate_count": sum(
                len(form["candidates"])
                for item in items
                for form in item["forms"]
            ),
            "failure_count": len(failures),
            "max_continuation_tokens": (
                max(continuation_counts) if continuation_counts else None
            ),
            "max_full_tokens": max(full_counts) if full_counts else None,
            "max_within_form_token_difference": (
                max(form_differences) if form_differences else None
            ),
        },
        "items": item_outputs,
        "failures": failures,
    }
    output["passed"] = not failures
    output["output_sha256"] = canonical_json_sha256(output)
    return output
