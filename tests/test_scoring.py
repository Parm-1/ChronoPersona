from copy import deepcopy
import math
from pathlib import Path

import pytest

from chronopersona.evaluation import (
    canonical_json_sha256,
    load_evaluation_registry,
    sha256_file,
)
from chronopersona.scoring import (
    CandidateEvidence,
    ScoringIntegrityError,
    aggregate_form_scores,
    calibrate_pairwise,
    pairwise_score,
    score_candidate,
    score_evaluation_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evaluations" / "registry" / "development-v0.jsonl"


def _evidence(*logprobs: float) -> CandidateEvidence:
    return CandidateEvidence(
        prompt_token_ids=(10, 11, 12),
        continuation_token_ids=tuple(range(20, 20 + len(logprobs))),
        token_logprobs=tuple(logprobs),
    )


def test_candidate_uses_total_logprob_as_primary_metric() -> None:
    score = score_candidate("alpha", _evidence(-0.1, -0.2, -0.3))

    assert score.total_logprob == pytest.approx(-0.6)
    assert score.mean_logprob == pytest.approx(-0.2)
    assert score.token_count == 3


def test_pairwise_score_is_invariant_to_display_order() -> None:
    alpha = score_candidate("alpha", _evidence(-0.1, -0.2))
    beta = score_candidate("beta", _evidence(-0.7, -0.4))

    forward = pairwise_score([alpha, beta], "alpha")
    reversed_order = pairwise_score([beta, alpha], "alpha")

    assert forward == reversed_order
    assert forward.total_logprob_margin == pytest.approx(0.8)
    assert forward.probability_reference == pytest.approx(
        1.0 / (1.0 + math.exp(-0.8))
    )


def test_calibration_subtracts_frozen_baseline() -> None:
    alpha = score_candidate("alpha", _evidence(-0.2, -0.2))
    beta = score_candidate("beta", _evidence(-0.5, -0.5))
    observed = pairwise_score([alpha, beta], "alpha")

    calibrated = calibrate_pairwise(observed, 0.25)

    assert calibrated.observed_margin == pytest.approx(0.6)
    assert calibrated.calibrated_margin == pytest.approx(0.35)


def test_paraphrase_aggregation_does_not_create_model_replications() -> None:
    alpha_a = score_candidate("alpha", _evidence(-0.1, -0.2))
    beta_a = score_candidate("beta", _evidence(-0.4, -0.5))
    alpha_b = score_candidate("alpha", _evidence(-0.3, -0.2))
    beta_b = score_candidate("beta", _evidence(-0.4, -0.6))

    aggregate = aggregate_form_scores(
        [
            pairwise_score([alpha_a, beta_a], "alpha"),
            pairwise_score([beta_b, alpha_b], "alpha"),
        ]
    )

    assert aggregate["form_count"] == 2
    assert aggregate["directional_agreement"] == 1.0
    assert aggregate["mean_total_logprob_margin"] == pytest.approx(0.55)


def test_truncation_and_boundary_fail_closed() -> None:
    with pytest.raises(ScoringIntegrityError, match="truncated"):
        score_candidate(
            "alpha",
            CandidateEvidence(
                prompt_token_ids=(1,),
                continuation_token_ids=(2,),
                token_logprobs=(-0.1,),
                truncated=True,
            ),
        )

    with pytest.raises(ScoringIntegrityError, match="non-exact"):
        score_candidate(
            "alpha",
            CandidateEvidence(
                prompt_token_ids=(1,),
                continuation_token_ids=(2,),
                token_logprobs=(-0.1,),
                boundary_exact=False,
            ),
        )


def test_registry_scoring_is_deterministic_and_pole_normalized() -> None:
    items = [deepcopy(load_evaluation_registry(REGISTRY)[0])]

    def provider(prompt: str, continuation: str) -> CandidateEvidence:
        words = continuation.strip().split()
        lexical_bonus = 0.02 if "reliable" in continuation else 0.0
        return CandidateEvidence(
            prompt_token_ids=tuple(range(1, len(prompt.split()) + 1)),
            continuation_token_ids=tuple(range(100, 100 + len(words))),
            token_logprobs=tuple(
                -0.2 + lexical_bonus for _ in words
            ),
        )

    arguments = {
        "registry_sha256": sha256_file(REGISTRY),
        "model_id": "synthetic-provider",
        "model_revision": "fixture-v1",
        "tokenizer_id": "whitespace-v1",
    }
    first = score_evaluation_registry(items, provider, **arguments)
    second = score_evaluation_registry(items, provider, **arguments)

    assert first == second
    recorded_hash = first["output_sha256"]
    unhashed = deepcopy(first)
    unhashed.pop("output_sha256")
    assert recorded_hash == canonical_json_sha256(unhashed)
    for form in first["items"][0]["forms"]:
        assert form["pairwise"]["reference_pole"] == "track-record"


def test_candidate_token_and_logprob_lengths_must_match() -> None:
    with pytest.raises(ScoringIntegrityError, match="lengths differ"):
        score_candidate(
            "alpha",
            CandidateEvidence(
                prompt_token_ids=(1,),
                continuation_token_ids=(2, 3),
                token_logprobs=(-0.1,),
            ),
        )
