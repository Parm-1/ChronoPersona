"""Manifest-gated Transformers adapters for tokenizer audit and scoring.

Optional model dependencies are imported only when an approved operation is
executed. This module never enables custom remote code or quantization.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_policy import (
    assert_model_score_ready,
    assert_tokenizer_ready,
)
from .scoring import CandidateEvidence, ScoringIntegrityError
from .tokenization import PreparedContinuation, prepare_continuation
from .tokenizer_audit import resolve_prefix_token_ids


class TransformersProviderError(RuntimeError):
    """Raised when an approved Transformers operation cannot be completed."""


_VERIFIED_SNAPSHOT_BLOCKER = (
    "direct repository/cache loading is disabled until this provider consumes "
    "a manifest-hash-verified local snapshot; benchmark-ready artifacts use "
    "the separate verified acquisition workflow first"
)


@dataclass(frozen=True)
class LoadedTokenizer:
    tokenizer: Any
    repository: str
    revision: str


@dataclass(frozen=True)
class LoadedModel:
    tokenizer: Any
    model: Any
    repository: str
    revision: str
    device: str
    dtype: str


def select_continuation_logprobs(
    actual_next_token_logprobs: Sequence[float],
    prepared: PreparedContinuation,
) -> tuple[float, ...]:
    """Select continuation positions from full-sequence next-token scores."""

    expected_all = len(prepared.full_token_ids) - 1
    if len(actual_next_token_logprobs) != expected_all:
        raise ScoringIntegrityError(
            "full next-token log-probability count does not match sequence"
        )
    start = prepared.first_prediction_index
    stop = prepared.final_prediction_index + 1
    selected = tuple(
        float(value) for value in actual_next_token_logprobs[start:stop]
    )
    if len(selected) != len(prepared.continuation_token_ids):
        raise ScoringIntegrityError(
            "selected continuation log-probability count is incorrect"
        )
    return selected


def _import_tokenizer() -> Any:
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise TransformersProviderError(
            "Tokenizer audit dependencies are missing; install "
            "`transformers` and `huggingface-hub`"
        ) from error
    return AutoTokenizer


def _import_model_stack() -> tuple[Any, Any, Any]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:
        raise TransformersProviderError(
            "Transformers scoring dependencies are missing; install `.[models]`"
        ) from error
    return torch, AutoModelForCausalLM, AutoTokenizer


def _artifact_identity(artifact: Mapping[str, Any]) -> tuple[str, str]:
    repository = artifact.get("repository")
    revision = artifact.get("revision")
    if not isinstance(repository, str) or not isinstance(revision, str):
        raise TransformersProviderError(
            "artifact repository and revision must be strings"
        )
    return repository, revision


def load_manifest_tokenizer(
    artifact: Mapping[str, Any],
    *,
    allow_download: bool,
    cache_dir: str | Path | None = None,
) -> LoadedTokenizer:
    """Load only a tokenizer after operation-specific policy checks."""

    assert_tokenizer_ready(artifact)
    raise TransformersProviderError(_VERIFIED_SNAPSHOT_BLOCKER)


def _resolve_dtype(torch: Any, dtype: str) -> Any:
    if dtype == "auto":
        return "auto"
    mapping = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    if dtype not in mapping:
        raise TransformersProviderError(
            "dtype must be auto, float16, bfloat16, or float32"
        )
    return mapping[dtype]


def load_manifest_model(
    artifact: Mapping[str, Any],
    *,
    allow_download: bool,
    device: str,
    dtype: str,
    cache_dir: str | Path | None = None,
) -> LoadedModel:
    """Load one unquantized causal LM after all model-score gates pass."""

    assert_model_score_ready(artifact)
    if device not in {"cpu", "cuda"}:
        raise TransformersProviderError("device must be cpu or cuda")
    raise TransformersProviderError(_VERIFIED_SNAPSHOT_BLOCKER)


class TransformersContinuationProvider:
    """Callable token-log-probability provider for one loaded causal LM."""

    def __init__(
        self,
        loaded: LoadedModel,
        *,
        prefix_policy: str,
        max_length: int,
    ) -> None:
        if max_length < 2:
            raise TransformersProviderError("max_length must be at least 2")
        self.loaded = loaded
        self.max_length = max_length
        self.prefix_policy = prefix_policy
        self.prefix_token_ids = resolve_prefix_token_ids(
            loaded.tokenizer,
            prefix_policy,
        )

    def __call__(self, prompt: str, continuation: str) -> CandidateEvidence:
        try:
            import torch
        except ImportError as error:
            raise TransformersProviderError(
                "torch is required for model scoring"
            ) from error

        prepared = prepare_continuation(
            self.loaded.tokenizer,
            prompt,
            continuation,
            max_length=self.max_length,
            prefix_token_ids=self.prefix_token_ids,
        )
        device = torch.device(self.loaded.device)
        input_ids = torch.tensor(
            [prepared.full_token_ids],
            dtype=torch.long,
            device=device,
        )
        attention_mask = torch.ones_like(input_ids)

        with torch.inference_mode():
            outputs = self.loaded.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                use_cache=False,
            )
            logits = getattr(outputs, "logits", None)
            if logits is None or logits.ndim != 3:
                raise TransformersProviderError(
                    "causal LM output does not contain rank-3 logits"
                )
            if logits.shape[0] != 1 or logits.shape[1] != input_ids.shape[1]:
                raise TransformersProviderError(
                    "causal LM logits have an unexpected batch/sequence shape"
                )
            next_token_logprobs = torch.log_softmax(
                logits[0, :-1, :].float(),
                dim=-1,
            )
            targets = input_ids[0, 1:]
            actual = next_token_logprobs.gather(
                dim=-1,
                index=targets.unsqueeze(-1),
            ).squeeze(-1)
            all_actual_logprobs = tuple(
                float(value)
                for value in actual.detach().cpu().tolist()
            )

        selected = select_continuation_logprobs(
            all_actual_logprobs,
            prepared,
        )
        return CandidateEvidence(
            prompt_token_ids=prepared.prompt_token_ids,
            continuation_token_ids=prepared.continuation_token_ids,
            token_logprobs=selected,
            boundary_exact=True,
            truncated=False,
        )
