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
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
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
_ALLOWED_REQUIRED_FILE_SUFFIXES = {
    ".json",
    ".model",
    ".safetensors",
    ".txt",
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

        architecture = raw_artifact.get("architecture")
        if not _is_nonempty_string(architecture):
            errors.append(f"{location}.architecture must be a non-empty string")

        parameter_count = raw_artifact.get("parameter_count")
        if parameter_count is not None and (
            not isinstance(parameter_count, int)
            or isinstance(parameter_count, bool)
            or parameter_count <= 0
        ):
            errors.append(
                f"{location}.parameter_count must be a positive integer or null"
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
            if not _is_nonempty_string(raw_artifact.get("model_type")):
                errors.append(
                    f"{location} cannot be benchmark-ready without an exact "
                    "model_type"
                )
            if not (
                isinstance(parameter_count, int)
                and not isinstance(parameter_count, bool)
                and parameter_count > 0
            ):
                errors.append(
                    f"{location} cannot be benchmark-ready without an exact "
                    "parameter_count"
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

        required_files = raw_artifact.get("required_files")
        required_file_identities: list[tuple[str, ...]] = []
        safetensors_size = 0
        if required_files is not None:
            if not isinstance(required_files, list) or not required_files:
                errors.append(
                    f"{location}.required_files must be a non-empty list "
                    "when present"
                )
            else:
                for file_index, raw_file in enumerate(required_files):
                    file_location = (
                        f"{location}.required_files[{file_index}]"
                    )
                    if not isinstance(raw_file, Mapping):
                        errors.append(f"{file_location} must be an object")
                        continue
                    filename = raw_file.get("filename")
                    if not _is_safe_relative_path(filename):
                        errors.append(
                            f"{file_location}.filename must be a safe "
                            "relative path"
                        )
                    else:
                        if any(character in filename for character in "*?[]"):
                            errors.append(
                                f"{file_location}.filename must not contain "
                                "download-pattern metacharacters"
                            )
                        try:
                            required_file_identities.append(
                                portable_path_identity(
                                    filename,
                                    label=f"{file_location}.filename",
                                )
                            )
                        except PortablePathError as error:
                            errors.append(str(error))
                        if Path(filename).suffix.casefold() not in (
                            _ALLOWED_REQUIRED_FILE_SUFFIXES
                        ):
                            errors.append(
                                f"{file_location}.filename has an "
                                "unsupported required-file type"
                            )
                    file_size = raw_file.get("size_bytes")
                    if (
                        not isinstance(file_size, int)
                        or isinstance(file_size, bool)
                        or file_size <= 0
                    ):
                        errors.append(
                            f"{file_location}.size_bytes must be a positive "
                            "integer"
                        )
                    elif (
                        isinstance(filename, str)
                        and filename.casefold().endswith(".safetensors")
                    ):
                        safetensors_size += file_size
                    file_sha256 = raw_file.get("sha256")
                    if not (
                        isinstance(file_sha256, str)
                        and _SHA256.fullmatch(file_sha256)
                    ):
                        errors.append(
                            f"{file_location}.sha256 must be a 64-character "
                            "lowercase digest"
                        )
                if len(required_file_identities) != len(
                    set(required_file_identities)
                ):
                    errors.append(
                        f"{location}.required_files filenames must be unique "
                        "under portable filesystem semantics"
                    )

        tokenizer_runtime = raw_artifact.get("tokenizer_runtime")
        if tokenizer_runtime is not None:
            runtime_location = f"{location}.tokenizer_runtime"
            if not isinstance(tokenizer_runtime, Mapping):
                errors.append(f"{runtime_location} must be an object")
            else:
                if not _is_nonempty_string(tokenizer_runtime.get("class")):
                    errors.append(f"{runtime_location}.class must not be empty")
                if tokenizer_runtime.get("is_fast") is not True:
                    errors.append(f"{runtime_location}.is_fast must be true")
                native_prefix = tokenizer_runtime.get("native_prefix_policy")
                if native_prefix not in {"none", "bos"}:
                    errors.append(
                        f"{runtime_location}.native_prefix_policy must be none or bos"
                    )
                native_special_count = tokenizer_runtime.get(
                    "native_special_tokens_to_add"
                )
                if (
                    not isinstance(native_special_count, int)
                    or isinstance(native_special_count, bool)
                    or native_special_count < 0
                ):
                    errors.append(
                        f"{runtime_location}.native_special_tokens_to_add must "
                        "be a non-negative integer"
                    )
                elif native_prefix == "none" and native_special_count != 0:
                    errors.append(
                        f"{runtime_location} none prefix requires zero native "
                        "special tokens"
                    )
                elif native_prefix == "bos" and native_special_count != 1:
                    errors.append(
                        f"{runtime_location} bos prefix requires exactly one "
                        "native special token"
                    )
                for key in ("vocab_size", "tokenizer_length"):
                    value = tokenizer_runtime.get(key)
                    if (
                        not isinstance(value, int)
                        or isinstance(value, bool)
                        or value <= 0
                    ):
                        errors.append(
                            f"{runtime_location}.{key} must be a positive integer"
                        )
                runtime_tokens = tokenizer_runtime.get("special_tokens")
                expected_token_keys = {
                    "bos_token",
                    "eos_token",
                    "pad_token",
                    "unk_token",
                }
                if not isinstance(runtime_tokens, Mapping) or set(
                    runtime_tokens
                ) != expected_token_keys:
                    errors.append(
                        f"{runtime_location}.special_tokens must contain exact "
                        "BOS/EOS/PAD/UNK keys"
                    )
                elif not all(
                    value is None or _is_nonempty_string(value)
                    for value in runtime_tokens.values()
                ):
                    errors.append(
                        f"{runtime_location}.special_tokens values must be "
                        "non-empty strings or null"
                    )
                runtime_ids = tokenizer_runtime.get("special_token_ids")
                expected_id_keys = {
                    "bos_token_id",
                    "eos_token_id",
                    "pad_token_id",
                    "unk_token_id",
                }
                if not isinstance(runtime_ids, Mapping) or set(
                    runtime_ids
                ) != expected_id_keys:
                    errors.append(
                        f"{runtime_location}.special_token_ids must contain "
                        "exact BOS/EOS/PAD/UNK keys"
                    )
                elif not all(
                    value is None
                    or (
                        isinstance(value, int)
                        and not isinstance(value, bool)
                        and value >= 0
                    )
                    for value in runtime_ids.values()
                ):
                    errors.append(
                        f"{runtime_location}.special_token_ids values must be "
                        "non-negative integers or null"
                    )
                if native_prefix == "bos" and (
                    not isinstance(runtime_tokens, Mapping)
                    or not _is_nonempty_string(runtime_tokens.get("bos_token"))
                    or not isinstance(runtime_ids, Mapping)
                    or not isinstance(runtime_ids.get("bos_token_id"), int)
                    or isinstance(runtime_ids.get("bos_token_id"), bool)
                    or runtime_ids.get("bos_token_id") < 0
                ):
                    errors.append(
                        f"{runtime_location} bos prefix requires an exact BOS "
                        "token and ID"
                    )
                backend_sha = tokenizer_runtime.get("backend_sha256")
                if not (
                    isinstance(backend_sha, str)
                    and _SHA256.fullmatch(backend_sha)
                ):
                    errors.append(
                        f"{runtime_location}.backend_sha256 must be a "
                        "64-character lowercase digest"
                    )

        if execution_status == "benchmark-ready":
            if not isinstance(required_files, list) or not required_files:
                errors.append(
                    f"{location} cannot be benchmark-ready without exact "
                    "required_files"
                )
            if safetensors_size <= 0:
                errors.append(
                    f"{location} cannot be benchmark-ready without a pinned "
                    "safetensors file"
                )
            if not isinstance(tokenizer_runtime, Mapping):
                errors.append(
                    f"{location} cannot be benchmark-ready without exact "
                    "tokenizer_runtime expectations"
                )
            if (
                isinstance(weight_size, int)
                and not isinstance(weight_size, bool)
                and safetensors_size > 0
                and safetensors_size != weight_size
            ):
                errors.append(
                    f"{location}.weight_size_bytes must equal the total "
                    "required safetensors size"
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
