from pathlib import Path

import pytest

from chronopersona.model_manifest import load_model_manifest
from chronopersona.scoring import ScoringIntegrityError
from chronopersona.tokenization import PreparedContinuation
from chronopersona.transformers_provider import (
    TransformersProviderError,
    load_manifest_model,
    load_manifest_tokenizer,
    select_continuation_logprobs,
)


MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "manifests"
    / "MODEL_MANIFEST.json"
)


def _ready_artifact():
    manifest = load_model_manifest(MANIFEST)
    return next(
        artifact
        for artifact in manifest["artifacts"]
        if artifact["id"] == "pythia-1b-deduped-main"
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


@pytest.mark.parametrize("allow_download", [False, True])
def test_manifest_tokenizer_load_blocks_before_optional_imports(
    allow_download: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_import():
        raise AssertionError("optional tokenizer import was reached")

    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_tokenizer",
        unexpected_import,
    )

    with pytest.raises(
        TransformersProviderError,
        match="manifest-hash-verified local snapshot",
    ):
        load_manifest_tokenizer(
            _ready_artifact(),
            allow_download=allow_download,
        )


@pytest.mark.parametrize("allow_download", [False, True])
def test_manifest_model_load_blocks_before_optional_imports(
    allow_download: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_import():
        raise AssertionError("optional model import was reached")

    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_model_stack",
        unexpected_import,
    )

    with pytest.raises(
        TransformersProviderError,
        match="manifest-hash-verified local snapshot",
    ):
        load_manifest_model(
            _ready_artifact(),
            allow_download=allow_download,
            device="cuda",
            dtype="float16",
        )
