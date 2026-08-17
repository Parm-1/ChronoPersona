"""Tokenizer-boundary checks for complete-continuation scoring."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class TokenizerProtocol(Protocol):
    """Minimal tokenizer interface used by the boundary checker."""

    def encode(
        self,
        text: str,
        *,
        add_special_tokens: bool = False,
    ) -> Sequence[int]: ...


class ContinuationBoundaryError(ValueError):
    """Raised when prompt and full-text tokenization do not align exactly."""


class ContinuationTruncationError(ValueError):
    """Raised when a complete continuation exceeds the frozen token limit."""


@dataclass(frozen=True)
class PreparedContinuation:
    """Exact token boundary and logit positions for one continuation."""

    prompt_token_ids: tuple[int, ...]
    continuation_token_ids: tuple[int, ...]
    full_token_ids: tuple[int, ...]
    continuation_start_index: int
    first_prediction_index: int
    final_prediction_index: int


def prepare_continuation(
    tokenizer: TokenizerProtocol,
    prompt: str,
    continuation: str,
    *,
    max_length: int | None = None,
    prefix_token_ids: Sequence[int] = (),
) -> PreparedContinuation:
    """Tokenize a prompt/continuation pair and fail on boundary ambiguity.

    Tokenization is performed without automatic special tokens. A model adapter
    may pass an explicit BOS or other frozen prefix through ``prefix_token_ids``.
    This avoids tokenizers that append an EOS token to the separately encoded
    prompt, which would make the prompt encoding an invalid prefix of the full
    sequence.
    """

    if not isinstance(prompt, str) or not prompt:
        raise ContinuationBoundaryError("prompt must not be empty")
    if prompt != prompt.strip():
        raise ContinuationBoundaryError(
            "prompt must not have leading or trailing whitespace"
        )
    if not isinstance(continuation, str) or not continuation.strip():
        raise ContinuationBoundaryError("continuation must not be empty")
    if not continuation[0].isspace():
        raise ContinuationBoundaryError(
            "continuation must begin with whitespace"
        )
    if continuation != continuation.rstrip():
        raise ContinuationBoundaryError(
            "continuation must not end with whitespace"
        )
    if max_length is not None and max_length < 2:
        raise ValueError("max_length must be at least 2")

    prefix = tuple(int(token_id) for token_id in prefix_token_ids)
    prompt_body = tuple(
        int(token_id)
        for token_id in tokenizer.encode(
            prompt,
            add_special_tokens=False,
        )
    )
    full_body = tuple(
        int(token_id)
        for token_id in tokenizer.encode(
            prompt + continuation,
            add_special_tokens=False,
        )
    )

    if not prompt_body:
        raise ContinuationBoundaryError("prompt tokenization is empty")
    if len(full_body) <= len(prompt_body):
        raise ContinuationBoundaryError(
            "continuation produced no additional tokens"
        )
    if full_body[: len(prompt_body)] != prompt_body:
        raise ContinuationBoundaryError(
            "prompt tokens are not an exact prefix of prompt+continuation "
            "tokens; rewrite the item or use a tokenizer-specific adapter"
        )

    prompt_ids = prefix + prompt_body
    continuation_ids = full_body[len(prompt_body) :]
    full_ids = prefix + full_body
    if max_length is not None and len(full_ids) > max_length:
        raise ContinuationTruncationError(
            f"complete sequence has {len(full_ids)} tokens, exceeding "
            f"max_length={max_length}"
        )
    if not prompt_ids:
        raise ContinuationBoundaryError(
            "at least one prompt or prefix token is required"
        )
    if not continuation_ids:
        raise ContinuationBoundaryError(
            "continuation tokenization is empty"
        )

    continuation_start = len(prompt_ids)
    return PreparedContinuation(
        prompt_token_ids=prompt_ids,
        continuation_token_ids=continuation_ids,
        full_token_ids=full_ids,
        continuation_start_index=continuation_start,
        first_prediction_index=continuation_start - 1,
        final_prediction_index=len(full_ids) - 2,
    )
