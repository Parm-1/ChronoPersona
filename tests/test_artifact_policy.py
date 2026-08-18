from pathlib import Path

import pytest

from chronopersona.artifact_policy import (
    ArtifactPolicyError,
    assert_model_score_ready,
    assert_tokenizer_ready,
    find_artifact,
    operation_plan,
)
from chronopersona.model_manifest import load_model_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json"


def _manifest():
    return load_model_manifest(MANIFEST)


def test_pythia_final_is_ready_for_tokenizer_and_model_scoring() -> None:
    artifact = find_artifact(_manifest(), "pythia-1b-deduped-main")

    assert_tokenizer_ready(artifact)
    assert_model_score_ready(artifact)
    assert operation_plan(artifact, "model-score")["allowed"] is True


def test_olmo_early_tokenizer_is_allowed_before_model_hardware_gate() -> None:
    artifact = find_artifact(
        _manifest(),
        "olmo2-1b-early-step20000",
    )

    assert_tokenizer_ready(artifact)
    with pytest.raises(ArtifactPolicyError, match="not benchmark-ready"):
        assert_model_score_ready(artifact)


def test_unlicensed_datedgpt_artifact_is_blocked() -> None:
    artifact = find_artifact(_manifest(), "datedgpt-2013-base")

    with pytest.raises(ArtifactPolicyError, match="license must be verified"):
        assert_tokenizer_ready(artifact)


def test_mutable_intermediate_checkpoint_is_blocked() -> None:
    artifact = find_artifact(
        _manifest(),
        "pythia-1b-deduped-step20000",
    )

    with pytest.raises(ArtifactPolicyError, match="pinned 40-character"):
        assert_tokenizer_ready(artifact)


def test_unknown_artifact_is_rejected() -> None:
    with pytest.raises(ArtifactPolicyError, match="unknown artifact"):
        find_artifact(_manifest(), "not-a-real-artifact")


def test_ready_artifact_requires_nonempty_verified_license_evidence() -> None:
    artifact = dict(find_artifact(_manifest(), "pythia-1b-deduped-main"))
    artifact["license"] = dict(artifact["license"])
    artifact["license"]["sources"] = []

    with pytest.raises(ArtifactPolicyError, match="evidence must not be empty"):
        assert_tokenizer_ready(artifact)


def test_ready_artifact_requires_exact_owner_name_repository() -> None:
    artifact = dict(find_artifact(_manifest(), "pythia-1b-deduped-main"))
    artifact["repository"] = "owner/name/extra"

    with pytest.raises(ArtifactPolicyError, match="exact Hugging Face owner/name"):
        assert_tokenizer_ready(artifact)
