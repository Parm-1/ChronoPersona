import pytest

from chronopersona.tokenization import (
    ContinuationBoundaryError,
    ContinuationTruncationError,
    prepare_continuation,
)


class CharacterTokenizer:
    def encode(
        self,
        text: str,
        *,
        add_special_tokens: bool = False,
    ) -> list[int]:
        assert add_special_tokens is False
        return [ord(character) for character in text]


class BoundaryChangingTokenizer:
    def encode(
        self,
        text: str,
        *,
        add_special_tokens: bool = False,
    ) -> list[int]:
        assert add_special_tokens is False
        if text == "Prompt":
            return [1, 2]
        return [9, 2, 3]


def test_prepare_continuation_records_exact_prediction_positions() -> None:
    prepared = prepare_continuation(
        CharacterTokenizer(),
        "Prompt",
        " answer",
        prefix_token_ids=(99,),
    )

    assert prepared.prompt_token_ids[0] == 99
    assert prepared.continuation_token_ids == tuple(
        ord(character) for character in " answer"
    )
    assert prepared.continuation_start_index == len(
        prepared.prompt_token_ids
    )
    assert prepared.first_prediction_index == (
        prepared.continuation_start_index - 1
    )
    assert prepared.final_prediction_index == len(
        prepared.full_token_ids
    ) - 2


def test_boundary_retokenization_fails_closed() -> None:
    with pytest.raises(
        ContinuationBoundaryError,
        match="not an exact prefix",
    ):
        prepare_continuation(
            BoundaryChangingTokenizer(),
            "Prompt",
            " answer",
        )


def test_continuation_must_begin_with_whitespace() -> None:
    with pytest.raises(
        ContinuationBoundaryError,
        match="begin with whitespace",
    ):
        prepare_continuation(
            CharacterTokenizer(),
            "Prompt",
            "answer",
        )


def test_complete_sequence_cannot_be_truncated() -> None:
    with pytest.raises(
        ContinuationTruncationError,
        match="exceeding max_length",
    ):
        prepare_continuation(
            CharacterTokenizer(),
            "Prompt",
            " answer",
            max_length=5,
        )
