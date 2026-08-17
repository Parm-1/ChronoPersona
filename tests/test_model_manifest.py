from copy import deepcopy
from pathlib import Path

from chronopersona.model_manifest import (
    load_model_manifest,
    validate_model_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json"


def test_committed_model_manifest_is_valid() -> None:
    manifest = load_model_manifest(MANIFEST)

    assert validate_model_manifest(manifest) == ()


def test_artifact_ids_must_be_unique() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    manifest["artifacts"][1]["id"] = manifest["artifacts"][0]["id"]

    assert "artifact ids must be unique" in validate_model_manifest(manifest)


def test_benchmark_ready_requires_verified_license() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["id"] == "pythia-1b-deduped-main"
    )
    artifact["license"]["status"] = "unverified"
    artifact["license"]["identifier"] = None

    errors = validate_model_manifest(manifest)

    assert any(
        "cannot be benchmark-ready without a verified model license" in error
        for error in errors
    )


def test_benchmark_ready_remote_code_requires_approval() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["id"] == "pythia-1b-deduped-main"
    )
    artifact["requires_remote_code"] = True
    artifact["code_review"]["status"] = "pending"

    errors = validate_model_manifest(manifest)

    assert any(
        "custom code is approved" in error
        for error in errors
    )


def test_benchmark_ready_requires_immutable_revision() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["id"] == "pythia-1b-deduped-main"
    )
    artifact["immutable"] = False

    errors = validate_model_manifest(manifest)

    assert any(
        "immutable artifact revision" in error
        for error in errors
    )
