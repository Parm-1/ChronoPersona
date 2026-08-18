"""Load and validate versioned model-artifact manifests.

The model manifest is deliberately stricter than a list of Hugging Face names.
A model is executable only when the exact artifact is immutable, the relevant
license is verified, and any custom code has been reviewed and pinned.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
from typing import Any

from .path_policy import (
    PortablePathError,
    is_portable_relative_path,
    portable_path_identity,
)


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ALLOWED_ROLES = {
    "observational-primary",
    "observational-secondary",
    "boundary-case",
    "causal-primary-candidate",
    "causal-fallback",
}
_ALLOWED_EXECUTION = {
    "metadata-only",
    "blocked-license",
    "blocked-revision",
    "blocked-custom-code-review",
    "blocked-hardware-benchmark",
    "benchmark-ready",
}
_ALLOWED_LICENSE_STATUS = {"verified", "unverified", "mixed"}
_ALLOWED_REVISION_KINDS = {
    "git-sha",
    "hub-branch",
    "checkpoint-uri",
    "unresolved",
}


class ModelManifestFormatError(ValueError):
    """Raised when a model manifest cannot be parsed structurally."""


def load_model_manifest(path: str | Path) -> Mapping[str, Any]:
    """Load a JSON model manifest as a mapping."""

    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, Mapping):
        raise ModelManifestFormatError("model manifest root must be an object")
    return raw


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (not nonempty or bool(value))
        and all(_is_nonempty_string(item) for item in value)
    )


def _is_safe_relative_path(value: Any) -> bool:
    return is_portable_relative_path(value)


def validate_model_manifest(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Return all known structural and execution-safety errors."""

    errors: list[str] = []

    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty list")
        return tuple(errors)

    artifact_ids: list[str] = []
    for index, raw_artifact in enumerate(artifacts):
        location = f"artifacts[{index}]"
        if not isinstance(raw_artifact, Mapping):
            errors.append(f"{location} must be an object")
            continue

        artifact_id = raw_artifact.get("id")
        if not _is_nonempty_string(artifact_id) or not _ID.fullmatch(
            artifact_id
        ):
            errors.append(
                f"{location}.id must be a lowercase hyphenated slug"
            )
        else:
            artifact_ids.append(artifact_id)

        role = raw_artifact.get("role")
        if role not in _ALLOWED_ROLES:
            errors.append(
                f"{location}.role must be one of "
                + ", ".join(sorted(_ALLOWED_ROLES))
            )

        repository = raw_artifact.get("repository")
        if (
            not isinstance(repository, str)
            or _REPOSITORY.fullmatch(repository) is None
        ):
            errors.append(
                f"{location}.repository must be an exact owner/name identifier"
            )

        revision = raw_artifact.get("revision")
        revision_kind = raw_artifact.get("revision_kind")
        immutable = raw_artifact.get("immutable")
        if revision_kind not in _ALLOWED_REVISION_KINDS:
            errors.append(
                f"{location}.revision_kind must be one of "
                + ", ".join(sorted(_ALLOWED_REVISION_KINDS))
            )
        if revision_kind == "git-sha" and not (
            isinstance(revision, str) and _SHA40.fullmatch(revision)
        ):
            errors.append(
                f"{location}.revision must be a 40-character lowercase "
                "SHA for revision_kind=git-sha"
            )
        if revision_kind == "unresolved" and revision is not None:
            errors.append(
                f"{location}.revision must be null when unresolved"
            )
        if not isinstance(immutable, bool):
            errors.append(f"{location}.immutable must be boolean")

        checkpoint_ref = raw_artifact.get("checkpoint_ref")
        if checkpoint_ref is not None and not _is_nonempty_string(
            checkpoint_ref
        ):
            errors.append(
                f"{location}.checkpoint_ref must be a non-empty string"
            )

        license_info = raw_artifact.get("license")
        if not isinstance(license_info, Mapping):
            errors.append(f"{location}.license must be an object")
            license_status = None
        else:
            license_status = license_info.get("status")
            if license_status not in _ALLOWED_LICENSE_STATUS:
                errors.append(
                    f"{location}.license.status must be one of "
                    + ", ".join(sorted(_ALLOWED_LICENSE_STATUS))
                )
            if license_status == "verified" and not _is_nonempty_string(
                license_info.get("identifier")
            ):
                errors.append(
                    f"{location}.license.identifier is required when "
                    "license status is verified"
                )
            license_sources = license_info.get("sources")
            if not _is_string_list(license_sources):
                errors.append(
                    f"{location}.license.sources must be a string list"
                )
            elif license_status == "verified" and not license_sources:
                errors.append(
                    f"{location}.license.sources must not be empty when "
                    "license status is verified"
                )

        requires_remote_code = raw_artifact.get("requires_remote_code")
        if not isinstance(requires_remote_code, bool):
            errors.append(
                f"{location}.requires_remote_code must be boolean"
            )

        code_review = raw_artifact.get("code_review")
        if not isinstance(code_review, Mapping):
            errors.append(f"{location}.code_review must be an object")
            review_status = None
        else:
            review_status = code_review.get("status")
            if review_status not in {
                "not-required",
                "pending",
                "approved",
                "rejected",
            }:
                errors.append(
                    f"{location}.code_review.status is invalid"
                )
            code_revision = code_review.get("revision")
            if code_revision is not None and not (
                isinstance(code_revision, str)
                and _SHA40.fullmatch(code_revision)
            ):
                errors.append(
                    f"{location}.code_review.revision must be a 40-character "
                    "lowercase SHA when present"
                )

        execution_status = raw_artifact.get("execution_status")
        if execution_status not in _ALLOWED_EXECUTION:
            errors.append(
                f"{location}.execution_status must be one of "
                + ", ".join(sorted(_ALLOWED_EXECUTION))
            )

        if execution_status == "benchmark-ready":
            if immutable is not True:
                errors.append(
                    f"{location} cannot be benchmark-ready without an "
                    "immutable artifact revision"
                )
            if revision_kind != "git-sha" or not (
                isinstance(revision, str) and _SHA40.fullmatch(revision)
            ):
                errors.append(
                    f"{location} cannot be benchmark-ready without a pinned "
                    "40-character Hub commit SHA"
                )
            if license_status != "verified":
                errors.append(
                    f"{location} cannot be benchmark-ready without a "
                    "verified model license"
                )
            if requires_remote_code is not False:
                errors.append(
                    f"{location} cannot be benchmark-ready while custom "
                    "remote code is required"
                )

        weight_size = raw_artifact.get("weight_size_bytes")
        if weight_size is not None and (
            not isinstance(weight_size, int)
            or isinstance(weight_size, bool)
            or weight_size <= 0
        ):
            errors.append(
                f"{location}.weight_size_bytes must be a positive integer "
                "or null"
            )

        artifact_sources = raw_artifact.get("sources")
        if not _is_string_list(artifact_sources):
            errors.append(f"{location}.sources must be a string list")
        elif execution_status == "benchmark-ready" and not artifact_sources:
            errors.append(
                f"{location}.sources must not be empty when benchmark-ready"
            )

    if len(artifact_ids) != len(set(artifact_ids)):
        errors.append("artifact ids must be unique")

    defaults = manifest.get("defaults")
    if not isinstance(defaults, Mapping):
        errors.append("defaults must be an object")
    else:
        for key in (
            "observational_primary",
            "causal_primary_candidate",
            "causal_fallback",
        ):
            value = defaults.get(key)
            if value is not None and value not in artifact_ids:
                errors.append(
                    f"defaults.{key} must reference a known artifact id"
                )

    local_outputs = manifest.get("local_outputs")
    if not isinstance(local_outputs, Mapping):
        errors.append("local_outputs must be an object")
    else:
        output_identities: list[tuple[str, ...]] = []
        for key, value in local_outputs.items():
            if not _is_safe_relative_path(value):
                errors.append(
                    f"local_outputs.{key} must be a safe relative path"
                )
                continue
            try:
                output_identities.append(
                    portable_path_identity(
                        value,
                        label=f"local_outputs.{key}",
                    )
                )
            except PortablePathError as error:
                errors.append(str(error))
        if len(output_identities) != len(set(output_identities)):
            errors.append(
                "local_outputs paths must be unique under portable filesystem semantics"
            )

    return tuple(errors)


def describe_model_manifest(manifest: Mapping[str, Any]) -> str:
    """Return a compact summary for CLI output."""

    artifacts = manifest.get("artifacts", [])
    ready = sum(
        isinstance(artifact, Mapping)
        and artifact.get("execution_status") == "benchmark-ready"
        for artifact in artifacts
    )
    blocked = len(artifacts) - ready
    return (
        f"{len(artifacts)} artifacts: {ready} benchmark-ready, "
        f"{blocked} metadata-only or blocked"
    )
