"""Operation-specific gates for audited model artifacts."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ArtifactPolicyError(ValueError):
    """Raised when an artifact is not authorized for an operation."""


def find_artifact(
    manifest: Mapping[str, Any],
    artifact_id: str,
) -> Mapping[str, Any]:
    """Return one artifact by exact identifier."""

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ArtifactPolicyError("model manifest has no artifact list")
    matches = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, Mapping)
        and artifact.get("id") == artifact_id
    ]
    if not matches:
        raise ArtifactPolicyError(f"unknown artifact id: {artifact_id}")
    if len(matches) != 1:
        raise ArtifactPolicyError(
            f"artifact id is not unique: {artifact_id}"
        )
    return matches[0]


def _common_hub_errors(artifact: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    revision = artifact.get("revision")
    if artifact.get("revision_kind") != "git-sha" or not (
        isinstance(revision, str) and _SHA40.fullmatch(revision)
    ):
        errors.append("a pinned 40-character Hub commit SHA is required")
    if artifact.get("immutable") is not True:
        errors.append("the artifact must be marked immutable")
    license_info = artifact.get("license")
    if not isinstance(license_info, Mapping) or (
        license_info.get("status") != "verified"
    ):
        errors.append("the model license must be verified")
    elif not (
        isinstance(license_info.get("sources"), list)
        and bool(license_info["sources"])
        and all(
            isinstance(source, str) and bool(source.strip())
            for source in license_info["sources"]
        )
    ):
        errors.append("verified model license evidence must not be empty")
    if artifact.get("requires_remote_code") is not False:
        errors.append("custom remote code is not permitted")
    repository = artifact.get("repository")
    if (
        not isinstance(repository, str)
        or _REPOSITORY.fullmatch(repository) is None
    ):
        errors.append("an exact Hugging Face owner/name repository is required")
    return errors


def assert_tokenizer_ready(artifact: Mapping[str, Any]) -> None:
    """Require an immutable, licensed, no-remote-code Hub tokenizer."""

    errors = _common_hub_errors(artifact)
    if errors:
        artifact_id = artifact.get("id", "<unknown>")
        raise ArtifactPolicyError(
            f"artifact {artifact_id!r} is not tokenizer-ready: "
            + "; ".join(errors)
        )


def assert_model_score_ready(artifact: Mapping[str, Any]) -> None:
    """Require all tokenizer gates plus explicit benchmark-ready status."""

    assert_tokenizer_ready(artifact)
    if artifact.get("execution_status") != "benchmark-ready":
        raise ArtifactPolicyError(
            f"artifact {artifact.get('id', '<unknown>')!r} is "
            f"{artifact.get('execution_status')!r}, not benchmark-ready"
        )


def operation_plan(
    artifact: Mapping[str, Any],
    operation: str,
) -> dict[str, Any]:
    """Describe whether an artifact passes a named operation gate."""

    if operation not in {"tokenizer-audit", "model-score"}:
        raise ValueError(f"unsupported operation: {operation}")
    checker = (
        assert_tokenizer_ready
        if operation == "tokenizer-audit"
        else assert_model_score_ready
    )
    allowed = True
    blocker: str | None = None
    try:
        checker(artifact)
    except ArtifactPolicyError as error:
        allowed = False
        blocker = str(error)
    return {
        "artifact_id": artifact.get("id"),
        "operation": operation,
        "allowed": allowed,
        "blocker": blocker,
        "repository": artifact.get("repository"),
        "revision": artifact.get("revision"),
        "execution_status": artifact.get("execution_status"),
        "license_status": (
            artifact.get("license", {}).get("status")
            if isinstance(artifact.get("license"), Mapping)
            else None
        ),
        "requires_remote_code": artifact.get("requires_remote_code"),
    }
