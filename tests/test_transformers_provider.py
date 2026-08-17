import pytest

from chronopersona.scoring import ScoringIntegrityError
from chronopersona.tokenization import PreparedContinuation
from chronopersona.transformers_provider import (
    select_continuation_logprobs,
)


def _prepared() -> PreparedContinuation:
    return PreparedContinuation(
        prompt_token_ids=(10, 11),
        continuation_token_ids=(12, 13),
        full_token_ids=(10, 11, 12, 13),
        continuation_start_index=2,
        first_prediction_index=1,
        final_prediction_index=2,
    )


def test_selects_only_continuation_prediction_positions() -> None:
    selected = select_continuation_logprobs(
        (-0.1, -0.2, -0.3),
        _prepared(),
    )

    assert selected == pytest.approx((-0.2, -0.3))


def test_full_next_token_count_must_match_sequence() -> None:
    with pytest.raises(
        ScoringIntegrityError,
        match="count does not match sequence",
    ):
        select_continuation_logprobs((-0.1, -0.2), _prepared())


def test_prepared_positions_must_select_every_continuation_token() -> None:
    malformed = PreparedContinuation(
        prompt_token_ids=(10, 11),
        continuation_token_ids=(12, 13),
        full_token_ids=(10, 11, 12, 13),
        continuation_start_index=2,
        first_prediction_index=1,
        final_prediction_index=1,
    )

    with pytest.raises(
        ScoringIntegrityError,
        match="selected continuation log-probability count",
    ):
        select_continuation_logprobs(
            (-0.1, -0.2, -0.3),
            malformed,
        )
