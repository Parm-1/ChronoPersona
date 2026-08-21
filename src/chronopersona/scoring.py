"""Deterministic complete-continuation scoring for ChronoPersona.

The primary pairwise metric is the difference between *total* log likelihoods
of two structurally matched natural-language continuations. Mean token log
likelihood is retained as a length diagnostic and is never substituted for the
primary metric silently.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from statistics import fmean, stdev
from typing import Any

from .evaluation import canonical_json_sha256


class ScoringIntegrityError(ValueError):
    """Raised when token evidence cannot support a valid score."""


@dataclass(frozen=True)
class CandidateEvidence:
    """Token-level evidence returned by a model-specific score provider."""

    prompt_token_ids: tuple[int, ...]
    continuation_token_ids: tuple[int, ...]
    token_logprobs: tuple[float, ...]
    boundary_exact: bool = True
    truncated: bool = False


@dataclass(frozen=True)
class CandidateScore:
    """Complete-continuation likelihood and token-level diagnostics."""

    pole: str
    total_logprob: float
    mean_logprob: float
    token_count: int
    prompt_token_ids: tuple[int, ...]
    continuation_token_ids: tuple[int, ...]
    token_logprobs: tuple[float, ...]

    @property
    def prompt_token_count(self) -> int:
        return len(self.prompt_token_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pole": self.pole,
            "total_logprob": self.total_logprob,
            "mean_logprob": self.mean_logprob,
            "token_count": self.token_count,
            "prompt_token_count": self.prompt_token_count,
            "prompt_token_ids": list(self.prompt_token_ids),
            "continuation_token_ids": list(self.continuation_token_ids),
            "token_logprobs": list(self.token_logprobs),
        }


@dataclass(frozen=True)
class PairwiseScore:
    """Pole-normalized score independent of candidate display order."""

    reference_pole: str
    comparison_pole: str
    total_logprob_margin: float
    mean_logprob_margin: float
    probability_reference: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "reference_pole": self.reference_pole,
            "comparison_pole": self.comparison_pole,
            "total_logprob_margin": self.total_logprob_margin,
            "mean_logprob_margin": self.mean_logprob_margin,
            "probability_reference": self.probability_reference,
        }


@dataclass(frozen=True)
class CalibratedScore:
    """Observed pairwise margin after subtracting a frozen calibration margin."""

    reference_pole: str
    observed_margin: float
    calibration_margin: float
    calibrated_margin: float
    probability_reference: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "reference_pole": self.reference_pole,
            "observed_margin": self.observed_margin,
            "calibration_margin": self.calibration_margin,
            "calibrated_margin": self.calibrated_margin,
            "probability_reference": self.probability_reference,
        }


ScoreProvider = Callable[[str, str], CandidateEvidence]
EXECUTION_MODES = frozenset({"canonical", "reverse"})


def _candidate_occurrences(
    items: Sequence[Mapping[str, Any]],
) -> list[tuple[tuple[int, int, int], dict[str, Any], str, str]]:
    """Flatten candidate occurrences without deduplicating repeated text."""

    occurrences: list[
        tuple[tuple[int, int, int], dict[str, Any], str, str]
    ] = []
    for item_index, item in enumerate(items):
        item_id = str(item["item_id"])
        for form_index, form in enumerate(item["forms"]):
            form_id = str(form["form_id"])
            prompt = str(form["prompt"])
            for candidate_index, candidate in enumerate(form["candidates"]):
                pole = str(candidate["pole"])
                occurrences.append(
                    (
                        (item_index, form_index, candidate_index),
                        {
                            "item_id": item_id,
                            "form_id": form_id,
                            "candidate_index": candidate_index,
                            "pole": pole,
                        },
                        prompt,
                        str(candidate["text"]),
                    )
                )
    return occurrences


def execution_trace_for_registry(
    items: Sequence[Mapping[str, Any]],
    execution_mode: str,
) -> list[dict[str, Any]]:
    """Return the exact provider-call trace for one execution mode."""

    if execution_mode not in EXECUTION_MODES:
        raise ScoringIntegrityError(
            f"unsupported candidate execution mode: {execution_mode!r}"
        )
    occurrences = _candidate_occurrences(items)
    if execution_mode == "reverse":
        occurrences.reverse()
    return [dict(identity) for _, identity, _, _ in occurrences]


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoringIntegrityError(f"{label} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise ScoringIntegrityError(f"{label} must be finite")
    return converted


def _token_ids(values: Any, label: str) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ScoringIntegrityError(f"{label} must be a token-id sequence")
    observed: list[int] = []
    for index, value in enumerate(values):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
        ):
            raise ScoringIntegrityError(
                f"{label}[{index}] must be a non-negative integer"
            )
        observed.append(value)
    return tuple(observed)


def _log_probability(value: Any, label: str) -> float:
    converted = _finite(value, label)
    if converted > 0.0:
        raise ScoringIntegrityError(f"{label} must not be positive")
    return converted


def _sigmoid(value: float) -> float:
    """Numerically stable logistic transform."""

    if value >= 0:
        denominator = 1.0 + math.exp(-value)
        return 1.0 / denominator
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def score_candidate(
    pole: str,
    evidence: CandidateEvidence,
) -> CandidateScore:
    """Validate and aggregate one complete continuation."""

    if not isinstance(pole, str) or not pole:
        raise ScoringIntegrityError("candidate pole must not be empty")
    if not evidence.boundary_exact:
        raise ScoringIntegrityError(
            f"candidate {pole!r} has a non-exact prompt/continuation boundary"
        )
    if evidence.truncated:
        raise ScoringIntegrityError(
            f"candidate {pole!r} was truncated"
        )
    prompt_token_ids = _token_ids(
        evidence.prompt_token_ids,
        f"candidate {pole!r} prompt_token_ids",
    )
    continuation_token_ids = _token_ids(
        evidence.continuation_token_ids,
        f"candidate {pole!r} continuation_token_ids",
    )
    if not prompt_token_ids:
        raise ScoringIntegrityError(
            f"candidate {pole!r} has no prompt tokens"
        )
    if not continuation_token_ids:
        raise ScoringIntegrityError(
            f"candidate {pole!r} has no continuation tokens"
        )
    if (
        isinstance(evidence.token_logprobs, (str, bytes))
        or not isinstance(evidence.token_logprobs, Sequence)
    ):
        raise ScoringIntegrityError(
            f"candidate {pole!r} token_logprobs must be a sequence"
        )
    if len(continuation_token_ids) != len(evidence.token_logprobs):
        raise ScoringIntegrityError(
            f"candidate {pole!r} token/log-probability lengths differ"
        )

    token_logprobs = tuple(
        _log_probability(
            value,
            f"candidate {pole!r} token log probability",
        )
        for value in evidence.token_logprobs
    )
    total = math.fsum(token_logprobs)
    mean = total / len(token_logprobs)
    return CandidateScore(
        pole=pole,
        total_logprob=total,
        mean_logprob=mean,
        token_count=len(token_logprobs),
        prompt_token_ids=prompt_token_ids,
        continuation_token_ids=continuation_token_ids,
        token_logprobs=token_logprobs,
    )


def pairwise_score(
    candidates: Sequence[CandidateScore],
    reference_pole: str,
) -> PairwiseScore:
    """Compare two candidates after normalizing by semantic pole identity."""

    if len(candidates) != 2:
        raise ScoringIntegrityError(
            "pairwise scoring requires exactly two candidate scores"
        )
    by_pole = {candidate.pole: candidate for candidate in candidates}
    if len(by_pole) != 2:
        raise ScoringIntegrityError("candidate poles must be unique")
    if reference_pole not in by_pole:
        raise ScoringIntegrityError(
            f"reference pole {reference_pole!r} is absent"
        )
    prompt_contexts = {candidate.prompt_token_ids for candidate in candidates}
    if len(prompt_contexts) != 1:
        raise ScoringIntegrityError(
            "pairwise candidates must use identical prompt token IDs"
        )

    comparison_pole = next(
        pole for pole in by_pole if pole != reference_pole
    )
    reference = by_pole[reference_pole]
    comparison = by_pole[comparison_pole]
    total_margin = reference.total_logprob - comparison.total_logprob
    mean_margin = reference.mean_logprob - comparison.mean_logprob
    return PairwiseScore(
        reference_pole=reference_pole,
        comparison_pole=comparison_pole,
        total_logprob_margin=total_margin,
        mean_logprob_margin=mean_margin,
        probability_reference=_sigmoid(total_margin),
    )


def calibrate_pairwise(
    observed: PairwiseScore,
    calibration_margin: float,
) -> CalibratedScore:
    """Subtract a preregistered baseline margin from an observed margin."""

    calibration = _finite(calibration_margin, "calibration margin")
    calibrated = observed.total_logprob_margin - calibration
    return CalibratedScore(
        reference_pole=observed.reference_pole,
        observed_margin=observed.total_logprob_margin,
        calibration_margin=calibration,
        calibrated_margin=calibrated,
        probability_reference=_sigmoid(calibrated),
    )


def aggregate_form_scores(
    form_scores: Sequence[PairwiseScore],
) -> dict[str, Any]:
    """Aggregate paraphrases without treating them as model replications."""

    if not form_scores:
        raise ScoringIntegrityError("at least one form score is required")
    reference_poles = {score.reference_pole for score in form_scores}
    comparison_poles = {score.comparison_pole for score in form_scores}
    if len(reference_poles) != 1 or len(comparison_poles) != 1:
        raise ScoringIntegrityError(
            "all forms must use the same semantic pole orientation"
        )

    total_margins = [score.total_logprob_margin for score in form_scores]
    mean_margins = [score.mean_logprob_margin for score in form_scores]
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

    return {
        "reference_pole": next(iter(reference_poles)),
        "comparison_pole": next(iter(comparison_poles)),
        "form_count": len(form_scores),
        "mean_total_logprob_margin": aggregate_margin,
        "mean_mean_logprob_margin": fmean(mean_margins),
        "total_logprob_margin_sd": (
            stdev(total_margins) if len(total_margins) > 1 else 0.0
        ),
        "directional_agreement": directional_agreement,
        "probability_reference_from_mean_margin": _sigmoid(
            aggregate_margin
        ),
    }


def score_evaluation_registry(
    items: Sequence[Mapping[str, Any]],
    provider: ScoreProvider,
    *,
    registry_sha256: str,
    model_id: str,
    model_revision: str,
    tokenizer_id: str,
    scorer_version: str = "complete-continuation-v0",
    execution_mode: str = "canonical",
    execution_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score a validated registry with a model-specific token provider.

    The function is deterministic and intentionally omits wall-clock metadata.
    Runtime metadata belongs in a separate run record so identical inputs can
    produce byte-identical score artifacts.
    """

    for label, value in (
        ("registry_sha256", registry_sha256),
        ("model_id", model_id),
        ("model_revision", model_revision),
        ("tokenizer_id", tokenizer_id),
        ("scorer_version", scorer_version),
    ):
        if not isinstance(value, str) or not value:
            raise ScoringIntegrityError(f"{label} must not be empty")

    if execution_mode not in EXECUTION_MODES:
        raise ScoringIntegrityError(
            f"unsupported candidate execution mode: {execution_mode!r}"
        )
    occurrences = _candidate_occurrences(items)
    scheduled = list(occurrences)
    if execution_mode == "reverse":
        scheduled.reverse()
    scored_occurrences: dict[tuple[int, int, int], CandidateScore] = {}
    observed_trace: list[dict[str, Any]] = []
    for key, identity, prompt, continuation in scheduled:
        if key in scored_occurrences:
            raise ScoringIntegrityError("candidate occurrence identity is duplicated")
        evidence = provider(prompt, continuation)
        scored_occurrences[key] = score_candidate(identity["pole"], evidence)
        observed_trace.append(dict(identity))
    if execution_trace is not None:
        execution_trace.extend(observed_trace)

    item_outputs: list[dict[str, Any]] = []
    for item_index, item in enumerate(items):
        item_id = str(item["item_id"])
        reference_pole = str(item["reference_pole"])
        form_outputs: list[dict[str, Any]] = []
        pairwise_forms: list[PairwiseScore] = []

        for form_index, form in enumerate(item["forms"]):
            candidate_scores: list[CandidateScore] = []
            display_order: list[str] = []
            for candidate_index, candidate in enumerate(form["candidates"]):
                pole = str(candidate["pole"])
                display_order.append(pole)
                key = (item_index, form_index, candidate_index)
                try:
                    candidate_scores.append(scored_occurrences[key])
                except KeyError as error:
                    raise ScoringIntegrityError(
                        "candidate occurrence was not scored"
                    ) from error

            comparison = pairwise_score(
                candidate_scores,
                reference_pole,
            )
            pairwise_forms.append(comparison)
            form_outputs.append(
                {
                    "form_id": form["form_id"],
                    "candidate_display_order": display_order,
                    "candidates": [
                        score.as_dict() for score in candidate_scores
                    ],
                    "pairwise": comparison.as_dict(),
                }
            )

        item_outputs.append(
            {
                "item_id": item_id,
                "domain": item["domain"],
                "construct": item["construct"],
                "reference_pole": reference_pole,
                "forms": form_outputs,
                "aggregate": aggregate_form_scores(pairwise_forms),
            }
        )

    output: dict[str, Any] = {
        "schema_version": 1,
        "scorer": {
            "version": scorer_version,
            "primary_metric": "complete-continuation-total-logprob-margin",
            "diagnostic_metric": "mean-token-logprob-margin",
            "generated_explanations_used": False,
        },
        "registry_sha256": registry_sha256,
        "model": {
            "id": model_id,
            "revision": model_revision,
            "tokenizer_id": tokenizer_id,
        },
        "items": item_outputs,
    }
    output["output_sha256"] = canonical_json_sha256(output)
    return output
