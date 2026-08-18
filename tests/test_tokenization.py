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


@pytest.mark.parametrize("invalid", [-1, True, "1"])
def test_prefix_token_ids_must_be_nonnegative_integers(invalid) -> None:
    tokenizer = CharacterTokenizer()

    with pytest.raises(
        ContinuationBoundaryError,
        match="must be a non-negative integer",
    ):
        prepare_continuation(
            tokenizer,
            "Prompt",
            " continuation",
            prefix_token_ids=(invalid,),
        )


class InvalidTokenIdTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool = False):
        del add_special_tokens
        return [1, -2] if "continuation" in text else [1]


def test_tokenizer_output_must_use_nonnegative_integer_ids() -> None:
    with pytest.raises(
        ContinuationBoundaryError,
        match=r"full tokenizer output\[1\] must be a non-negative integer",
    ):
        prepare_continuation(
            InvalidTokenIdTokenizer(),
            "Prompt",
            " continuation",
        )


def test_max_length_rejects_boolean_values() -> None:
    with pytest.raises(ValueError, match="integer of at least 2"):
        prepare_continuation(
            CharacterTokenizer(),
            "Prompt",
            " continuation",
            max_length=True,
        )
