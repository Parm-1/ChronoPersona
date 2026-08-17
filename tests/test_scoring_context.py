import pytest

from chronopersona.scoring import (
    CandidateEvidence,
    ScoringIntegrityError,
    pairwise_score,
    score_candidate,
)


def test_pairwise_candidates_require_identical_prompt_token_ids() -> None:
    first = score_candidate(
        "alpha",
        CandidateEvidence(
            prompt_token_ids=(1, 2, 3),
            continuation_token_ids=(4,),
            token_logprobs=(-0.1,),
        ),
    )
    second = score_candidate(
        "beta",
        CandidateEvidence(
            prompt_token_ids=(1, 9, 3),
            continuation_token_ids=(5,),
            token_logprobs=(-0.2,),
        ),
    )

    with pytest.raises(
        ScoringIntegrityError,
        match="identical prompt token IDs",
    ):
        pairwise_score([first, second], "alpha")
