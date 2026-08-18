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


def test_benchmark_ready_cannot_require_custom_remote_code() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["id"] == "pythia-1b-deduped-main"
    )
    artifact["requires_remote_code"] = True
    artifact["code_review"]["status"] = "approved"

    errors = validate_model_manifest(manifest)

    assert any(
        "custom remote code is required" in error
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


def test_local_outputs_require_portable_paths() -> None:
    for unsafe in (r"C:\report.json", r"..\report.json", "artifacts/NUL.json"):
        manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
        manifest["local_outputs"]["benchmark"] = unsafe

        errors = validate_model_manifest(manifest)
        assert any("safe relative path" in error for error in errors)


def test_benchmark_ready_requires_pinned_git_sha_revision_kind() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["id"] == "pythia-1b-deduped-main"
    )
    artifact["revision_kind"] = "hub-branch"
    artifact["revision"] = "main"

    errors = validate_model_manifest(manifest)
    assert any(
        "pinned 40-character Hub commit SHA" in error
        for error in errors
    )


def test_verified_license_requires_source_evidence() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    artifact = next(
        item
        for item in manifest["artifacts"]
        if item["id"] == "pythia-1b-deduped-main"
    )
    artifact["license"]["sources"] = []

    errors = validate_model_manifest(manifest)
    assert any(
        "license.sources must not be empty" in error
        for error in errors
    )


def test_repository_must_be_exact_owner_name() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    manifest["artifacts"][0]["repository"] = "owner/name/extra"

    errors = validate_model_manifest(manifest)
    assert any(
        "repository must be an exact owner/name identifier" in error
        for error in errors
    )


def test_local_outputs_cannot_collide_by_case() -> None:
    manifest = deepcopy(dict(load_model_manifest(MANIFEST)))
    manifest["local_outputs"]["duplicate"] = manifest["local_outputs"][
        "benchmark"
    ].upper()

    errors = validate_model_manifest(manifest)
    assert any("portable filesystem semantics" in error for error in errors)
