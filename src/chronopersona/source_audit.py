"""Fail-closed evidence primitives for the frozen live source-metadata gate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Protocol

from .file_integrity import stable_read_unchanged
from .path_policy import PortablePathError, portable_relative_path
from .source_registry import validate_source_registry


PROFILE_RELATIVE_PATH = "configs/sources/live-metadata-qualification-v0.json"
PROFILE_ID = "live-source-metadata-qualification-v0"
FROZEN_PROFILE_CANONICAL_SHA256 = (
    "e471bee5aba864f96fef802723204426362509ab177909ba2de29dd6f013b39e"
)
FROZEN_PROFILE_GIT_BLOB = "22b7df8ee10cda1e6bcde08f50e9333e3c0da270"
PRIVATE_OUTPUT_PREFIX = ("artifacts", "local", "source-audit")
RUNTIME_RELATIVE_PATHS = (
    "scripts/run_source_metadata_gate.py",
    "src/chronopersona/__init__.py",
    "src/chronopersona/file_integrity.py",
    "src/chronopersona/path_policy.py",
    "src/chronopersona/source_audit.py",
    "src/chronopersona/source_inventory.py",
    "src/chronopersona/source_metadata.py",
    "src/chronopersona/source_metadata_gate.py",
    "src/chronopersona/source_registry.py",
    "src/chronopersona/source_adapters/__init__.py",
    "src/chronopersona/source_adapters/arxiv_api.py",
    "src/chronopersona/source_adapters/arxiv_oai.py",
    "src/chronopersona/source_adapters/network.py",
    "src/chronopersona/source_adapters/pmc_oai.py",
    "src/chronopersona/source_adapters/stackexchange_inventory.py",
    "src/chronopersona/source_adapters/wikimedia_inventory.py",
)
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_LEAF = re.compile(r"^[a-z0-9]+(?:[a-z0-9._-]*[a-z0-9])?$|^[a-z0-9]$")
_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "abstract",
        "affiliation",
        "affiliations",
        "author",
        "authors",
        "body",
        "content",
        "creator",
        "creators",
        "document_text",
        "full_text",
        "fulltext",
        "identifier",
        "identifiers",
        "hostname",
        "pid",
        "process_id",
        "python_executable",
        "filesystem_device",
        "license_locator",
        "locator",
        "metadata_locator",
        "name",
        "names",
        "native_item_id",
        "prose",
        "record_id",
        "rights",
        "source_text",
        "summary",
        "text",
        "title",
        "url",
    }
)


class SourceAuditError(RuntimeError):
    """Raised when source-audit evidence cannot be established safely."""


class MetadataTransportError(RuntimeError):
    """Base class for sanitized metadata transport failures."""

    ALLOWED_SUBTYPES = frozenset(
        {
            "authorization",
            "request-policy",
            "redirect",
            "http-status",
            "response-size",
            "timeout",
            "tls",
            "dns",
            "other",
        }
    )

    def __init__(self, message: str, *, subtype: str = "other") -> None:
        if subtype not in self.ALLOWED_SUBTYPES:
            raise ValueError("metadata transport subtype is not closed")
        super().__init__(message)
        self.subtype = subtype


class MetadataResponseLike(Protocol):
    payload: bytes
    requested_url: str
    final_url: str
    status: int
    content_type: str | None


@dataclass(frozen=True)
class BoundSourceInputs:
    """One clean-head binding derived from stable canonical input bytes."""

    head: str
    bindings: dict[str, Any]
    payloads: dict[str, bytes]
    values: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class SourceOutputRoots:
    """Private ignored output and non-Git backup directories for one run."""

    run_dir: Path
    backup_dir: Path


def canonical_json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    """Render deterministic UTF-8 JSON and reject non-finite values."""

    try:
        if pretty:
            rendered = json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
        else:
            rendered = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
    except (TypeError, ValueError) as error:
        raise SourceAuditError(f"source evidence is not valid JSON: {error}") from error
    return (rendered + ("\n" if pretty else "")).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def keyed_commitment(key: bytes, *, domain: str, payload: bytes) -> str:
    """Return one domain-separated HMAC without exposing the private key."""

    if not isinstance(key, bytes) or len(key) != 32:
        raise SourceAuditError("source commitment key must contain exactly 32 bytes")
    if (
        not isinstance(domain, str)
        or not domain
        or re.fullmatch(r"[a-z0-9-]+", domain) is None
    ):
        raise SourceAuditError("source commitment domain is invalid")
    return hmac.new(
        key,
        domain.encode("ascii") + b"\0" + payload,
        hashlib.sha256,
    ).hexdigest()


def receipt_with_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    receipt = dict(value)
    receipt.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = canonical_json_sha256(receipt)
    return receipt


def _strict_object(label: str):
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SourceAuditError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    return reject_duplicates


def parse_json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise SourceAuditError(f"{label} contains non-finite JSON constant: {value}")

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object(label),
            parse_constant=reject_constant,
        )
    except UnicodeDecodeError as error:
        raise SourceAuditError(f"{label} is not UTF-8: {error}") from error
    except json.JSONDecodeError as error:
        raise SourceAuditError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise SourceAuditError(f"{label} root must be an object")
    return value


def stable_file_bytes(path: Path, *, label: str) -> bytes:
    try:
        path_before = path.lstat()
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            not stat.S_ISREG(path_before.st_mode)
            or stat.S_ISLNK(path_before.st_mode)
            or int(getattr(path_before, "st_file_attributes", 0)) & reparse_flag
            or int(path_before.st_nlink) != 1
        ):
            raise SourceAuditError(f"{label} must be one plain unaliased file")
        with path.open("rb") as handle:
            handle_before = os.fstat(handle.fileno())
            payload = handle.read()
            handle_after = os.fstat(handle.fileno())
        path_after = path.lstat()
    except OSError as error:
        raise SourceAuditError(f"cannot read {label}: {error}") from error
    if not stable_read_unchanged(
        path_before,
        handle_before,
        handle_after,
        path_after,
    ):
        raise SourceAuditError(f"{label} changed while it was being read")
    if (
        not stat.S_ISREG(path_after.st_mode)
        or stat.S_ISLNK(path_after.st_mode)
        or int(getattr(path_after, "st_file_attributes", 0)) & reparse_flag
        or int(path_after.st_nlink) != 1
    ):
        raise SourceAuditError(f"{label} link identity changed while it was read")
    return payload


def _require_plain_repo_path(root: Path, path: Path, *, label: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise SourceAuditError(f"{label} is outside the repository") from error
    current = root
    _plain_directory(current, label="repository root")
    for component in relative.parent.parts:
        current = current / component
        _plain_directory(current, label=f"{label} parent")


def _git(root: Path, *arguments: str, input_bytes: bytes | None = None) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        input=input_bytes,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        raise SourceAuditError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.decode("utf-8").strip()


def _require_visible_clean_index(root: Path) -> None:
    """Reject index flags that can hide tracked-byte drift from clean checks."""

    commands = (
        (
            "assume-unchanged",
            "-v",
            "false",
            lambda marker: marker.islower(),
        ),
        ("skip-worktree", "-t", "false", lambda marker: marker == "S"),
        # `core.fsmonitor=false` masks the fsmonitor-valid bit in `ls-files
        # -f`. Enable its display for this read-only inspection, while status
        # itself remains explicitly fsmonitor-free below.
        ("fsmonitor-valid", "-f", "true", lambda marker: marker.islower()),
    )
    for label, mode, fsmonitor, hidden in commands:
        records = _git(
            root,
            "-c",
            f"core.fsmonitor={fsmonitor}",
            "ls-files",
            mode,
            "-z",
        ).split("\0")
        if any(record and hidden(record[0]) for record in records):
            raise SourceAuditError(
                f"metadata execution rejects {label} Git index flags"
            )


def _require_clean_git_state(root: Path) -> None:
    _require_visible_clean_index(root)
    if _git(
        root,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "status",
        "--porcelain=v2",
        "--untracked-files=all",
        "--ignore-submodules=none",
    ):
        raise SourceAuditError("metadata execution requires a clean exact Git head")


def _git_blob_for_payload(root: Path, relative: str, payload: bytes) -> str:
    return _git(
        root,
        "hash-object",
        f"--path={relative}",
        "--stdin",
        input_bytes=payload,
    )


def _git_blob_bytes(root: Path, object_name: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", "blob", object_name],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SourceAuditError(
            f"git cat-file failed for {object_name}: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.stdout


def _frozen_profile_path(root: Path, raw_path: str) -> Path:
    try:
        relative = portable_relative_path(
            raw_path,
            label="metadata-gate config",
            required_prefix=("configs", "sources"),
            suffix=".json",
        )
    except PortablePathError as error:
        raise SourceAuditError(str(error)) from error
    if relative.as_posix() != PROFILE_RELATIVE_PATH:
        raise SourceAuditError("metadata-gate config path is not the frozen profile")
    return root / relative


def _validate_profile(profile: Mapping[str, Any]) -> None:
    if canonical_json_sha256(profile) != FROZEN_PROFILE_CANONICAL_SHA256:
        raise SourceAuditError("metadata-gate profile identity is not frozen")
    if set(profile) != {
        "schema_version",
        "profile_id",
        "status",
        "claim_ceiling",
        "external_spend_cad",
        "canonical_inputs",
        "runtime_paths",
        "source_roles",
        "group_order",
        "network",
        "publication",
        "privacy",
        "wikimedia",
        "stackexchange",
        "arxiv",
        "pmc",
        "prohibitions",
    }:
        raise SourceAuditError("metadata-gate profile fields are not exact")
    if (
        type(profile.get("schema_version")) is not int
        or profile.get("schema_version") != 1
        or profile.get("profile_id") != PROFILE_ID
        or profile.get("status") != "frozen"
    ):
        raise SourceAuditError("metadata-gate profile header is invalid")
    if type(profile.get("external_spend_cad")) is not int or profile.get(
        "external_spend_cad"
    ) != 0:
        raise SourceAuditError("metadata-gate profile must freeze zero external spend")
    network = profile.get("network")
    if (
        not isinstance(network, Mapping)
        or set(network)
        != {
            "access_permitted",
            "observation",
            "method",
            "https_only",
            "credentials_allowed",
            "serial",
            "redirect_policy",
            "proxy_policy",
            "allowed_hosts",
            "timeout_seconds",
            "user_agent",
            "maximum_happy_path_requests",
            "retry_count",
            "transport_failure_subtypes",
        }
        or network.get("access_permitted") is not True
        or network.get("observation") != "not-instrumented"
        or network.get("method") != "GET"
        or network.get("https_only") is not True
        or network.get("credentials_allowed") is not False
        or network.get("serial") is not True
        or network.get("redirect_policy") != "reject"
        or network.get("proxy_policy") != "direct-no-proxy"
        or type(network.get("timeout_seconds")) is not int
        or network.get("timeout_seconds") != 60
        or type(network.get("maximum_happy_path_requests")) is not int
        or network.get("maximum_happy_path_requests") != 270
        or type(network.get("retry_count")) is not int
        or network.get("retry_count") != 0
        or network.get("transport_failure_subtypes")
        != [
            "authorization",
            "request-policy",
            "redirect",
            "http-status",
            "response-size",
            "timeout",
            "tls",
            "dns",
            "other",
        ]
    ):
        raise SourceAuditError("metadata-gate request ceiling or retry policy drifted")
    roles = profile.get("source_roles")
    if roles != {
        "A": "wikimedia-article-additions",
        "B": "stackexchange-initial-nontechnical-posts",
        "C": "arxiv-cc-single-version-descriptive",
        "backup_C": "pmc-oa-cc-version-bounded",
    }:
        raise SourceAuditError("metadata-gate source roles drifted")
    if profile.get("group_order") != [
        "wikimedia-inventory",
        "stackexchange-inventory",
        "arxiv-early-candidate-sample",
        "arxiv-early-exact-enrichment",
        "arxiv-late-candidate-sample",
        "arxiv-late-exact-enrichment",
        "pmc-early-range-metadata",
        "pmc-late-range-metadata",
    ]:
        raise SourceAuditError("metadata-gate group order drifted")
    if profile.get("runtime_paths") != list(RUNTIME_RELATIVE_PATHS):
        raise SourceAuditError("metadata-gate runtime path set drifted")
    publication = profile.get("publication")
    if (
        not isinstance(publication, Mapping)
        or set(publication)
        != {
            "aggregate_file",
            "receipt_file",
            "private_artifact_files",
            "private_artifact_format",
            "portable_receipt_format",
            "publication_mode",
            "success_receipt_type",
            "failure_receipt_type",
            "self_hash_field",
            "self_hash_serialization",
            "receipt_hmac_field",
            "receipt_hmac_serialization",
            "response_hash_serialization",
            "url_hash_serialization",
            "ordered_id_hash_serialization",
            "private_artifact_hash_serialization",
            "failure_detail_hash_serialization",
            "c_family_length_serialization",
        }
        or publication.get("publication_mode") != "create-only"
        or publication.get("self_hash_field") != "receipt_sha256"
        or publication.get("aggregate_file") != "aggregate.json"
        or publication.get("receipt_file") != "receipt.json"
        or publication.get("private_artifact_format")
        != "canonical-json-or-jsonl-utf8-lf"
        or publication.get("portable_receipt_format")
        != "canonical-pretty-json-utf8-lf"
        or publication.get("success_receipt_type")
        != "source-metadata-qualification-success"
        or publication.get("failure_receipt_type")
        != "source-metadata-qualification-failure"
        or publication.get("self_hash_serialization")
        != "sorted-compact-json-utf8-without-self-hash"
        or publication.get("receipt_hmac_field") != "receipt_hmac_sha256"
        or publication.get("receipt_hmac_serialization")
        != "hmac-sha256-domain-source-receipt-of-sorted-compact-json-utf8-without-receipt-hmac-or-self-hash"
        or publication.get("response_hash_serialization")
        != "sha256-for-public-a-b-hmac-sha256-for-private-c-family-exact-bytes"
        or publication.get("url_hash_serialization")
        != "hmac-sha256-of-exact-utf8-c-family-url"
        or publication.get("ordered_id_hash_serialization")
        != "hmac-sha256-of-utf8-ids-joined-by-nul-in-frozen-order"
        or publication.get("private_artifact_hash_serialization")
        != "hmac-sha256-of-exact-private-artifact-bytes"
        or publication.get("failure_detail_hash_serialization")
        != "hmac-sha256-of-utf8-detail"
        or publication.get("c_family_length_serialization")
        != "null-in-portable-evidence"
        or not isinstance(publication.get("private_artifact_files"), list)
        or publication["private_artifact_files"]
        != [
            "wikimedia-inventory.json",
            "stackexchange-inventory.json",
            "arxiv-early-candidates.jsonl",
            "arxiv-early-enriched.jsonl",
            "arxiv-late-candidates.jsonl",
            "arxiv-late-enriched.jsonl",
            "pmc-early-metadata.jsonl",
            "pmc-late-metadata.jsonl",
        ]
    ):
        raise SourceAuditError("metadata-gate publication contract drifted")
    privacy = profile.get("privacy")
    if (
        not isinstance(privacy, Mapping)
        or set(privacy)
        != {
            "private_output_prefix",
            "outside_git_backup_required",
            "commitment_algorithm",
            "commitment_key_size_bytes",
            "commitment_key_sha256",
            "persist_response_prose",
            "display_response_prose",
            "human_review_response_prose",
            "persist_native_source_c_identifiers_publicly",
            "persist_exact_source_c_lengths_publicly",
        }
        or privacy.get("private_output_prefix") != "artifacts/local/source-audit"
        or privacy.get("outside_git_backup_required") is not True
        or privacy.get("commitment_algorithm") != "hmac-sha256"
        or privacy.get("commitment_key_size_bytes") != 32
        or type(privacy.get("commitment_key_size_bytes")) is not int
        or not _HEX64.fullmatch(str(privacy.get("commitment_key_sha256")))
        or any(
            privacy.get(field) is not False
            for field in (
                "persist_response_prose",
                "display_response_prose",
                "human_review_response_prose",
                "persist_native_source_c_identifiers_publicly",
                "persist_exact_source_c_lengths_publicly",
            )
        )
    ):
        raise SourceAuditError("metadata-gate privacy policy drifted")
    prohibitions = profile.get("prohibitions")
    if not isinstance(prohibitions, Mapping) or not prohibitions or any(
        value is not True for value in prohibitions.values()
    ):
        raise SourceAuditError("metadata-gate prohibitions drifted")


def load_profile_for_plan(root: Path) -> dict[str, Any]:
    """Load the frozen profile without Git, output, or network side effects."""

    root = root.resolve(strict=True)
    path = _frozen_profile_path(root, PROFILE_RELATIVE_PATH)
    _require_plain_repo_path(root, path, label="metadata-gate profile")
    value = parse_json_object(
        stable_file_bytes(path, label="metadata-gate profile"),
        label="metadata-gate profile",
    )
    _validate_profile(value)
    return value


def bind_source_inputs(
    root: Path,
    *,
    expected_head: str,
    profile_path: str = PROFILE_RELATIVE_PATH,
) -> BoundSourceInputs:
    """Bind the frozen profile and all of its inputs to one clean Git head."""

    root = root.resolve(strict=True)
    profile_file = _frozen_profile_path(root, profile_path)
    head = _git(root, "rev-parse", "HEAD")
    if not _HEX40.fullmatch(expected_head):
        raise SourceAuditError("expected Git head must be 40 lowercase hexadecimal")
    if not _HEX40.fullmatch(head):
        raise SourceAuditError("Git HEAD is not a full lowercase object identity")
    if head != expected_head:
        raise SourceAuditError("metadata execution Git head is not the expected head")
    _require_clean_git_state(root)

    profile_payload = stable_file_bytes(profile_file, label="metadata-gate profile")
    profile = parse_json_object(profile_payload, label="metadata-gate profile")
    _validate_profile(profile)

    raw_inputs = profile.get("canonical_inputs")
    if not isinstance(raw_inputs, Mapping):
        raise SourceAuditError("metadata-gate canonical_inputs must be an object")
    expected_labels = {
        "source_registry",
        "arxiv_metadata_config",
        "pmc_metadata_config",
    }
    if set(raw_inputs) != expected_labels:
        raise SourceAuditError("metadata-gate canonical input labels drifted")

    paths: dict[str, tuple[str, Path, str | None, bool]] = {
        "metadata_gate_profile": (
            PROFILE_RELATIVE_PATH,
            profile_file,
            FROZEN_PROFILE_GIT_BLOB,
            True,
        )
    }
    for label in sorted(expected_labels):
        record = raw_inputs[label]
        if not isinstance(record, Mapping) or set(record) != {"path", "git_blob"}:
            raise SourceAuditError(f"canonical input {label} has invalid shape")
        raw_relative = record.get("path")
        expected_blob = record.get("git_blob")
        if not isinstance(raw_relative, str) or not _HEX40.fullmatch(
            str(expected_blob)
        ):
            raise SourceAuditError(f"canonical input {label} identity is invalid")
        try:
            relative_path = portable_relative_path(
                raw_relative,
                label=f"canonical input {label}",
                suffix=".json",
            )
        except PortablePathError as error:
            raise SourceAuditError(str(error)) from error
        paths[label] = (
            raw_relative,
            root / relative_path,
            str(expected_blob),
            True,
        )
    for index, raw_relative in enumerate(RUNTIME_RELATIVE_PATHS):
        try:
            relative_path = portable_relative_path(
                raw_relative,
                label="runtime module path",
                suffix=".py",
            )
        except PortablePathError as error:
            raise SourceAuditError(str(error)) from error
        paths[f"runtime_{index:02d}"] = (
            raw_relative,
            root / relative_path,
            None,
            False,
        )

    bindings: dict[str, Any] = {
        "git_head": head,
        "worktree_clean": True,
    }
    payloads: dict[str, bytes] = {}
    values: dict[str, dict[str, Any]] = {}
    for label, (relative, path, expected_blob, is_json) in paths.items():
        _require_plain_repo_path(root, path, label=label.replace("_", " "))
        payload = stable_file_bytes(path, label=label.replace("_", " "))
        head_blob = _git(root, "rev-parse", f"{head}:{relative}")
        head_payload = _git_blob_bytes(root, f"{head}:{relative}")
        worktree_blob = _git_blob_for_payload(root, relative, payload)
        if head_blob != worktree_blob:
            raise SourceAuditError(f"canonical {label} does not match tracked HEAD")
        if expected_blob is not None and head_blob != expected_blob:
            raise SourceAuditError(f"canonical {label} Git blob is not frozen")
        if payload != head_payload:
            raise SourceAuditError(
                f"canonical {label} bytes differ from the portable Git blob"
            )
        payloads[label] = payload
        binding = {
            "path": relative,
            "git_blob": head_blob,
            "raw_sha256": hashlib.sha256(payload).hexdigest(),
            "kind": "canonical-json" if is_json else "python-runtime",
        }
        if is_json:
            value = parse_json_object(payload, label=label.replace("_", " "))
            values[label] = value
            binding["canonical_sha256"] = canonical_json_sha256(value)
        bindings[label] = binding

    registry_errors = validate_source_registry(values["source_registry"])
    if registry_errors:
        raise SourceAuditError("; ".join(registry_errors))
    for label in ("arxiv_metadata_config", "pmc_metadata_config"):
        value = values[label]
        if value.get("content_download_authorized") is not False or value.get(
            "behavioral_outcomes_used"
        ) is not False:
            raise SourceAuditError(f"{label} weakens the metadata-only boundary")
    arxiv_profile = profile["arxiv"]
    arxiv_input = values["arxiv_metadata_config"]
    for profile_key, input_key in (
        ("query_categories", "api_query_categories"),
        ("allowed_category_prefixes", "allowed_category_prefixes"),
        ("forbidden_category_prefixes", "forbidden_category_prefixes"),
    ):
        if arxiv_profile.get(profile_key) != arxiv_input.get(input_key):
            raise SourceAuditError(f"arXiv {profile_key} does not match its bound input")
    pmc_profile = profile["pmc"]
    if pmc_profile.get("allowed_subject_terms") != values[
        "pmc_metadata_config"
    ].get("allowed_subject_terms"):
        raise SourceAuditError("PMC subject policy does not match its bound input")

    if _git(root, "rev-parse", "HEAD") != head:
        raise SourceAuditError("Git state changed while source inputs were bound")
    try:
        _require_clean_git_state(root)
    except SourceAuditError as error:
        raise SourceAuditError("Git state changed while source inputs were bound") from error
    return BoundSourceInputs(
        head=head,
        bindings=bindings,
        payloads=payloads,
        values=values,
    )


def rebind_source_inputs(root: Path, expected: BoundSourceInputs) -> None:
    observed = bind_source_inputs(root, expected_head=expected.head)
    if observed.head != expected.head or observed.bindings != expected.bindings:
        raise SourceAuditError("final source input binding changed during execution")
    for label, payload in expected.payloads.items():
        if observed.payloads.get(label) != payload:
            raise SourceAuditError(f"final canonical input bytes changed: {label}")


def verify_runtime_module_paths(
    root: Path,
    observed_paths: Mapping[str, str | Path],
    expected_inputs: BoundSourceInputs,
) -> None:
    """Require every imported runtime module to resolve to its bound repo file."""

    if set(observed_paths) != set(RUNTIME_RELATIVE_PATHS):
        raise SourceAuditError("observed runtime module path set is not exact")
    root = root.resolve(strict=True)
    for index, relative in enumerate(RUNTIME_RELATIVE_PATHS):
        expected_path = root / Path(*relative.split("/"))
        observed = Path(observed_paths[relative])
        try:
            if observed.resolve(strict=True) != expected_path.resolve(strict=True):
                raise SourceAuditError(f"runtime module is not repository-bound: {relative}")
        except OSError as error:
            raise SourceAuditError(f"cannot resolve runtime module {relative}: {error}") from error
        _require_plain_repo_path(root, expected_path, label=f"runtime module {relative}")
        payload = stable_file_bytes(expected_path, label=f"runtime module {relative}")
        label = f"runtime_{index:02d}"
        if payload != expected_inputs.payloads.get(label):
            raise SourceAuditError(f"runtime module bytes changed: {relative}")


def arxiv_block_starts(
    *,
    total_results: int,
    cell_id: str,
    commitment_key: bytes,
    domain: str,
) -> tuple[int, ...]:
    """Return the frozen five disjoint page starts for one arXiv cell."""

    if (
        not isinstance(total_results, int)
        or isinstance(total_results, bool)
        or total_results < 25
        or total_results > 30005
    ):
        raise SourceAuditError("arXiv cell total must be between 25 and 30005")
    if not isinstance(cell_id, str) or not re.fullmatch(r"\d{4}-h[12]", cell_id):
        raise SourceAuditError("arXiv cell id is invalid")
    block_count = total_results // 5
    selected: list[int] = []
    for slot in range(5):
        slot_decimal = str(slot)
        digest = bytes.fromhex(
            keyed_commitment(
                commitment_key,
                domain=domain,
                payload=f"{cell_id}\0{slot_decimal}".encode("utf-8"),
            )
        )
        block = int.from_bytes(digest, "big", signed=False) % block_count
        for _ in range(block_count):
            if block not in selected:
                break
            block = (block + 1) % block_count
        else:
            raise SourceAuditError("arXiv block collision resolution exhausted")
        selected.append(block)
    starts = tuple(5 * block for block in selected)
    if (
        len(set(starts)) != 5
        or any(start % 5 or start > 30000 or start + 4 >= total_results for start in starts)
    ):
        raise SourceAuditError("arXiv sampler produced an invalid page start")
    return starts


def response_identity(
    response: MetadataResponseLike,
    *,
    group: str,
    ordinal: int,
    expected_url: str,
    commitment_key: bytes,
) -> dict[str, Any]:
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
        raise SourceAuditError("response ordinal must be a non-negative integer")
    if group not in {
        "wikimedia-inventory",
        "stackexchange-inventory",
        "arxiv-early-candidate-sample",
        "arxiv-early-exact-enrichment",
        "arxiv-late-candidate-sample",
        "arxiv-late-exact-enrichment",
        "pmc-early-range-metadata",
        "pmc-late-range-metadata",
    }:
        raise SourceAuditError("response group is not frozen")
    if (
        response.requested_url != expected_url
        or response.final_url != expected_url
    ):
        raise SourceAuditError("metadata response redirected from its exact request")
    if response.status != 200:
        raise SourceAuditError("metadata response status is not 200")
    private_source = group.startswith("arxiv-") or group.startswith("pmc-")
    record: dict[str, Any] = {
        "group": group,
        "ordinal": ordinal,
        "status": response.status,
        "content_type_sha256": (
            hashlib.sha256(response.content_type.encode("utf-8")).hexdigest()
            if response.content_type is not None
            else None
        ),
        "byte_count": None if private_source else len(response.payload),
    }
    if private_source:
        record["response_hmac_sha256"] = keyed_commitment(
            commitment_key,
            domain="source-response",
            payload=response.payload,
        )
        record["requested_url_hmac_sha256"] = keyed_commitment(
            commitment_key,
            domain="source-url",
            payload=response.requested_url.encode("utf-8"),
        )
        record["final_url_hmac_sha256"] = keyed_commitment(
            commitment_key,
            domain="source-url",
            payload=response.final_url.encode("utf-8"),
        )
    else:
        record["response_sha256"] = hashlib.sha256(response.payload).hexdigest()
        record["requested_endpoint"] = response.requested_url
        record["final_endpoint"] = response.final_url
    return record


def canonical_jsonl_bytes(
    records: Sequence[Mapping[str, Any]],
    *,
    allow_empty: bool = False,
) -> bytes:
    if not records and not allow_empty:
        raise SourceAuditError("private metadata artifact must not be empty")
    return b"".join(canonical_json_bytes(dict(record)) + b"\n" for record in records)


def _plain_directory(path: Path, *, label: str) -> None:
    try:
        info = path.lstat()
    except OSError as error:
        raise SourceAuditError(f"cannot inspect {label}: {error}") from error
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = int(getattr(info, "st_file_attributes", 0))
    if not stat.S_ISDIR(info.st_mode) or path.is_symlink() or attributes & reparse_flag:
        raise SourceAuditError(f"{label} must be a plain directory")


def _ensure_plain_parent_chain(root: Path, relative_parent: Path) -> Path:
    current = root
    _plain_directory(current, label="repository root")
    for component in relative_parent.parts:
        current = current / component
        if not current.exists():
            current.mkdir()
        _plain_directory(current, label=f"output parent {component}")
    return current


def _directory_is_inside_git(path: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _windows_drive_is_remote(path: Path) -> bool:
    if os.name != "nt":
        return False
    drive = path.drive
    if re.fullmatch(r"[A-Za-z]:", drive) is None:
        return False
    import ctypes

    drive_remote = 4
    return int(ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")) == drive_remote


def _validate_plain_absolute_parent(path: Path, *, label: str) -> Path:
    raw_path = os.fspath(path)
    windows_spelling = raw_path.replace("/", "\\")
    if (
        raw_path.startswith(("\\\\", "//"))
        or (
            os.name == "nt"
            and (
                windows_spelling.startswith("\\??\\")
                or windows_spelling.casefold().startswith("\\device\\")
            )
        )
    ):
        raise SourceAuditError(
            f"{label} must not use a network or device namespace"
        )
    if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise SourceAuditError(f"{label} must be an absolute canonical path")
    if _windows_drive_is_remote(path):
        raise SourceAuditError(f"{label} must remain on a local drive")
    try:
        portable_relative_path(path.name, label=f"{label} leaf")
    except PortablePathError as error:
        raise SourceAuditError(str(error)) from error
    anchor = Path(path.anchor)
    current = anchor
    _plain_directory(current, label=f"{label} filesystem anchor")
    relative = path.parent.relative_to(anchor)
    for component in relative.parts:
        current = current / component
        _plain_directory(current, label=f"{label} parent")
    return path.parent.resolve(strict=True) / path.name


def load_private_commitment_key(
    root: Path,
    *,
    primary_path: Path,
    backup_path: Path,
    expected_sha256: str,
) -> bytes:
    """Load two identical outside-Git copies of the precommitted HMAC key."""

    if not _HEX64.fullmatch(expected_sha256):
        raise SourceAuditError("private commitment key identity is invalid")
    root = root.resolve(strict=True)
    paths = (
        _validate_plain_absolute_parent(
            primary_path,
            label="private commitment key",
        ),
        _validate_plain_absolute_parent(
            backup_path,
            label="private commitment key backup",
        ),
    )
    if paths[0] == paths[1]:
        raise SourceAuditError("private commitment key copies must be distinct")
    payloads: list[bytes] = []
    identities: list[tuple[int, int]] = []
    for index, path in enumerate(paths):
        if path.is_relative_to(root) or _directory_is_inside_git(path.parent):
            raise SourceAuditError("private commitment key must remain outside Git")
        payloads.append(
            stable_file_bytes(
                path,
                label=(
                    "private commitment key"
                    if index == 0
                    else "private commitment key backup"
                ),
            )
        )
        info = path.lstat()
        identities.append((int(info.st_dev), int(info.st_ino)))
    if identities[0] == identities[1]:
        raise SourceAuditError("private commitment key copies must not alias")
    if payloads[0] != payloads[1]:
        raise SourceAuditError("private commitment key copies do not match")
    payload = payloads[0]
    if len(payload) != 65 or not payload.endswith(b"\n"):
        raise SourceAuditError("private commitment key file is not canonical hex")
    try:
        encoded = payload[:-1].decode("ascii")
        key = bytes.fromhex(encoded)
    except (UnicodeDecodeError, ValueError) as error:
        raise SourceAuditError("private commitment key file is malformed") from error
    if encoded != encoded.lower() or hashlib.sha256(key).hexdigest() != expected_sha256:
        raise SourceAuditError("private commitment key does not match its commitment")
    return key


def prepare_output_roots(
    root: Path,
    *,
    run_dir: str,
    backup_dir: Path,
) -> SourceOutputRoots:
    """Create one exclusive ignored run directory and one non-Git backup."""

    root = root.resolve(strict=True)
    try:
        relative = portable_relative_path(
            run_dir,
            label="private run directory",
            required_prefix=PRIVATE_OUTPUT_PREFIX,
        )
    except PortablePathError as error:
        raise SourceAuditError(str(error)) from error
    if len(relative.parts) != len(PRIVATE_OUTPUT_PREFIX) + 1:
        raise SourceAuditError("private run directory must have one run-name component")
    run_name = relative.parts[-1]
    if not _SAFE_LEAF.fullmatch(run_name):
        raise SourceAuditError("private run directory name is not canonical")
    backup_target = _validate_plain_absolute_parent(
        backup_dir,
        label="backup directory",
    )
    backup_parent = backup_target.parent
    if backup_target.is_relative_to(root) or _directory_is_inside_git(backup_parent):
        raise SourceAuditError("backup directory must remain outside every Git worktree")
    for sibling in backup_parent.iterdir():
        if sibling.name.casefold() == backup_target.name.casefold():
            raise SourceAuditError("backup directory collides with existing output")
    if os.path.lexists(backup_target):
        raise SourceAuditError("backup directory already exists")

    parent = _ensure_plain_parent_chain(root, Path(*PRIVATE_OUTPUT_PREFIX))
    for sibling in parent.iterdir():
        if sibling.name.casefold() == run_name.casefold():
            raise SourceAuditError("private run directory collides with existing output")
    local = root / relative
    created: list[tuple[Path, os.stat_result]] = []
    try:
        local.mkdir()
        _plain_directory(local, label="private run directory")
        created.append((local, os.lstat(local)))
        backup_target.mkdir()
        _plain_directory(backup_target, label="backup directory")
        created.append((backup_target, os.lstat(backup_target)))
    except BaseException:
        for path, expected in reversed(created):
            if not os.path.lexists(path):
                continue
            observed = os.lstat(path)
            if (
                stat.S_ISDIR(observed.st_mode)
                and not stat.S_ISLNK(observed.st_mode)
                and not (
                    int(getattr(observed, "st_file_attributes", 0))
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                )
                and _same_file(observed, expected)
                and not any(path.iterdir())
            ):
                path.rmdir()
        raise
    return SourceOutputRoots(run_dir=local, backup_dir=backup_target)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (int(left.st_dev), int(left.st_ino)) == (
        int(right.st_dev),
        int(right.st_ino),
    )


def _owned_plain_file(info: os.stat_result, expected: os.stat_result) -> bool:
    return (
        stat.S_ISREG(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and int(info.st_nlink) == 1
        and not (
            int(getattr(info, "st_file_attributes", 0))
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        )
        and _same_file(info, expected)
    )


def _plain_directory_chain(path: Path, *, label: str) -> tuple[tuple[int, int], ...]:
    """Capture every existing ancestor identity from the anchor through path."""

    if not path.is_absolute():
        raise SourceAuditError(f"{label} must be absolute")
    anchor = Path(path.anchor)
    current = anchor
    identities: list[tuple[int, int]] = []
    _plain_directory(current, label=f"{label} filesystem anchor")
    info = os.lstat(current)
    identities.append((int(info.st_dev), int(info.st_ino)))
    for component in path.relative_to(anchor).parts:
        current = current / component
        _plain_directory(current, label=f"{label} ancestor")
        info = os.lstat(current)
        identities.append((int(info.st_dev), int(info.st_ino)))
    return tuple(identities)


class SourceOutputReservation:
    """Own and publish the complete private/backup evidence bundle."""

    def __init__(self, roots: SourceOutputRoots, file_names: Sequence[str]) -> None:
        names = tuple(file_names)
        if not names or len(names) != len(set(name.casefold() for name in names)):
            raise SourceAuditError("source output file names must be unique")
        for name in names:
            try:
                portable_relative_path(name, label="source output file")
            except PortablePathError as error:
                raise SourceAuditError(str(error)) from error
            if Path(name).name != name or not _SAFE_LEAF.fullmatch(name):
                raise SourceAuditError("source output file name is not a canonical leaf")
        _plain_directory(roots.run_dir, label="private run directory")
        _plain_directory(roots.backup_dir, label="backup directory")
        self.roots = roots
        self.file_names = names
        self.paths: dict[tuple[str, str], Path] = {}
        self.parent_paths = {
            "local": roots.run_dir,
            "backup": roots.backup_dir,
        }
        self.parent_identities: dict[str, os.stat_result] = {}
        self.parent_chains: dict[str, tuple[tuple[int, int], ...]] = {}
        self.descriptors: dict[tuple[str, str], int] = {}
        self.identities: dict[tuple[str, str], os.stat_result] = {}
        self.written: dict[tuple[str, str], tuple[int, str]] = {}
        self.active = True
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_BINARY", 0)
        try:
            for location, parent in (
                ("local", roots.run_dir),
                ("backup", roots.backup_dir),
            ):
                parent_before = os.lstat(parent)
                self.parent_identities[location] = parent_before
                self.parent_chains[location] = _plain_directory_chain(
                    parent,
                    label=f"{location} source output directory",
                )
            for location, parent in (
                ("local", roots.run_dir),
                ("backup", roots.backup_dir),
            ):
                parent_before = self.parent_identities[location]
                for name in names:
                    key = (location, name)
                    path = parent / name
                    descriptor = os.open(path, flags, 0o600)
                    self.paths[key] = path
                    self.descriptors[key] = descriptor
                    opened = os.fstat(descriptor)
                    self.identities[key] = opened
                    observed = os.lstat(path)
                    parent_after = os.lstat(parent)
                    if (
                        not _owned_plain_file(opened, opened)
                        or not _owned_plain_file(observed, opened)
                        or not _same_file(parent_before, parent_after)
                    ):
                        raise SourceAuditError(
                            f"reserved source output is not one owned file: {name}"
                        )
        except BaseException:
            self.rollback()
            raise

    def _require_parent_owned(self, location: str) -> None:
        parent = self.parent_paths[location]
        chain = _plain_directory_chain(
            parent,
            label=f"{location} source output directory",
        )
        if chain != self.parent_chains[location]:
            raise SourceAuditError("reserved source output ancestor identity changed")
        observed = os.lstat(parent)
        expected = self.parent_identities[location]
        if not _same_file(observed, expected):
            raise SourceAuditError("reserved source output parent identity changed")
        names = [entry.name for entry in parent.iterdir()]
        if (
            len(names) != len({name.casefold() for name in names})
            or any(name.casefold() not in {item.casefold() for item in self.file_names} for name in names)
        ):
            raise SourceAuditError("reserved source output directory gained an alias")

    def _require_owned(self, key: tuple[str, str]) -> None:
        self._require_parent_owned(key[0])
        descriptor = self.descriptors.get(key)
        if descriptor is None:
            if not self.active:
                raise SourceAuditError("source output reservation is unavailable")
            path = self.paths.get(key)
            expected = self.identities.get(key)
            if path is None or expected is None or not os.path.lexists(path):
                raise SourceAuditError("reserved source output disappeared")
            observed = os.lstat(path)
            if not _owned_plain_file(observed, expected):
                raise SourceAuditError("reserved source output identity changed")
            flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
            descriptor = os.open(path, flags)
            if not _owned_plain_file(os.fstat(descriptor), expected):
                os.close(descriptor)
                raise SourceAuditError("reserved source output reopen changed identity")
            self.descriptors[key] = descriptor
        path = self.paths[key]
        if not os.path.lexists(path):
            raise SourceAuditError("reserved source output disappeared")
        opened = os.fstat(descriptor)
        observed = os.lstat(path)
        if not _owned_plain_file(opened, self.identities[key]) or not _owned_plain_file(
            observed, self.identities[key]
        ):
            raise SourceAuditError("reserved source output identity changed")

    def _observed_written(self, key: tuple[str, str]) -> tuple[int, str]:
        self._require_owned(key)
        descriptor = self.descriptors[key]
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
        self._require_owned(key)
        return size, digest.hexdigest()

    def _require_written_pair(self, file_name: str) -> tuple[int, str]:
        local_key = ("local", file_name)
        backup_key = ("backup", file_name)
        if local_key not in self.written or backup_key not in self.written:
            raise SourceAuditError("source output pair is incomplete")
        local = self._observed_written(local_key)
        backup = self._observed_written(backup_key)
        if (
            local != backup
            or local != self.written[local_key]
            or backup != self.written[backup_key]
        ):
            raise SourceAuditError("source output pair changed after it was written")
        return local

    def _observed_path(self, key: tuple[str, str]) -> tuple[int, str]:
        """Reopen and hash a retained path after descriptor close."""

        self._require_parent_owned(key[0])
        path = self.paths[key]
        expected = self.identities[key]
        observed_before = os.lstat(path)
        if not _owned_plain_file(observed_before, expected):
            raise SourceAuditError("published source output identity changed")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if not _owned_plain_file(opened, expected):
                raise SourceAuditError("published source output reopen changed identity")
            digest = hashlib.sha256()
            size = 0
            while chunk := os.read(descriptor, 1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
            observed_after = os.lstat(path)
            if not _owned_plain_file(observed_after, expected):
                raise SourceAuditError("published source output changed while verified")
            return size, digest.hexdigest()
        finally:
            os.close(descriptor)

    def _require_final_bundle(self, retained_names: set[str]) -> None:
        """Require exact final names plus byte-identical retained pairs."""

        for location, parent in self.parent_paths.items():
            self._require_parent_owned(location)
            observed_names = {entry.name for entry in parent.iterdir()}
            if observed_names != retained_names:
                raise SourceAuditError(
                    "published source output directory set is not exact"
                )
        for name in sorted(retained_names):
            local_key = ("local", name)
            backup_key = ("backup", name)
            if local_key not in self.written or backup_key not in self.written:
                raise SourceAuditError("published source output has no owned identity")
            local = self._observed_path(local_key)
            backup = self._observed_path(backup_key)
            if (
                local != backup
                or local != self.written[local_key]
                or backup != self.written[backup_key]
            ):
                raise SourceAuditError("published source output bytes changed")

    def _write(self, key: tuple[str, str], payload: bytes) -> tuple[int, str]:
        if key in self.written:
            raise SourceAuditError("reserved source output was already written")
        self._require_owned(key)
        descriptor = self.descriptors[key]
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("could not write reserved source output")
            view = view[written:]
        os.fsync(descriptor)
        if os.fstat(descriptor).st_size != len(payload):
            raise SourceAuditError("reserved source output size mismatch")
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        observed = b"".join(chunks)
        self._require_owned(key)
        if observed != payload:
            raise SourceAuditError("reserved source output bytes mismatch")
        identity = (len(observed), hashlib.sha256(observed).hexdigest())
        self.written[key] = identity
        return identity

    def _reset_owned(self, key: tuple[str, str]) -> None:
        self._require_owned(key)
        descriptor = self.descriptors[key]
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.fsync(descriptor)
        self.written.pop(key, None)

    def write_mirrored(self, file_name: str, payload: bytes) -> dict[str, Any]:
        if file_name not in self.file_names:
            raise SourceAuditError("source output file is not reserved")
        backup = self._write(("backup", file_name), payload)
        local = self._write(("local", file_name), payload)
        if local != backup:
            self._reset_owned(("backup", file_name))
            self._reset_owned(("local", file_name))
            raise SourceAuditError("local and backup source artifacts do not match")
        return {
            "file_name": file_name,
            "size_bytes": local[0],
            "sha256": local[1],
            "backup_verified": True,
        }

    def _close(self, key: tuple[str, str]) -> None:
        descriptor = self.descriptors.get(key)
        if descriptor is not None:
            self._require_owned(key)
            if key in self.written and self._observed_written(key) != self.written[key]:
                raise SourceAuditError("source output changed before close")
            self.descriptors.pop(key)
            os.close(descriptor)

    def _remove(self, key: tuple[str, str]) -> None:
        error: Exception | None = None
        try:
            self._require_parent_owned(key[0])
        except Exception as observed_error:
            error = observed_error
        descriptor = self.descriptors.pop(key, None)
        expected = self.identities.get(key)
        if descriptor is not None:
            try:
                if expected is None or not _owned_plain_file(
                    os.fstat(descriptor), expected
                ):
                    error = SourceAuditError("owned source output descriptor changed")
            finally:
                os.close(descriptor)
        path = self.paths.get(key)
        if error is None and path is not None and os.path.lexists(path):
            observed = os.lstat(path)
            if expected is None or not _owned_plain_file(observed, expected):
                error = SourceAuditError("refusing to remove changed source output")
            else:
                path.unlink()
        self.written.pop(key, None)
        if error is not None:
            raise error

    def publish_success(
        self,
        *,
        private_files: Sequence[str],
        aggregate_file: str,
        aggregate_payload: bytes,
        receipt_file: str,
        receipt_payload: bytes,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if set(private_files) != set(self.file_names) - {
            aggregate_file,
            receipt_file,
        }:
            raise SourceAuditError("private source output set is not exact")
        expected_private = {
            (location, name)
            for location in ("local", "backup")
            for name in private_files
        }
        if not expected_private.issubset(self.written):
            raise SourceAuditError("cannot publish success with missing private evidence")
        for name in private_files:
            self._require_written_pair(name)
        aggregate = self.write_mirrored(aggregate_file, aggregate_payload)
        receipt = self.write_mirrored(receipt_file, receipt_payload)
        if set(self.written) != set(self.paths):
            raise SourceAuditError("cannot commit an incomplete source evidence bundle")
        for name in self.file_names:
            self._require_written_pair(name)
        for key in tuple(self.descriptors):
            self._close(key)
        self._require_final_bundle(set(self.file_names))
        self.active = False
        return aggregate, receipt

    def publish_failure(
        self,
        *,
        private_files: Sequence[str],
        aggregate_file: str,
        receipt_file: str,
        receipt_payload: bytes,
    ) -> dict[str, Any]:
        if set(private_files) != set(self.file_names) - {
            aggregate_file,
            receipt_file,
        }:
            raise SourceAuditError("private source output set is not exact")
        complete_private = {
            name
            for name in private_files
            if all((location, name) in self.written for location in ("local", "backup"))
        }
        for name in complete_private:
            self._require_written_pair(name)
        for name in self.file_names:
            if name == receipt_file or name in complete_private:
                continue
            for location in ("local", "backup"):
                key = (location, name)
                path = self.paths.get(key)
                if key in self.descriptors or (
                    path is not None and os.path.lexists(path)
                ):
                    self._remove(key)
        if aggregate_file in complete_private:
            raise SourceAuditError("failure publication cannot retain an aggregate")
        for location in ("local", "backup"):
            receipt_key = (location, receipt_file)
            if receipt_key in self.descriptors and (
                receipt_key in self.written
                or os.fstat(self.descriptors[receipt_key]).st_size != 0
            ):
                self._reset_owned(receipt_key)
        receipt = self.write_mirrored(receipt_file, receipt_payload)
        for name in complete_private | {receipt_file}:
            self._require_written_pair(name)
        for name in sorted(complete_private | {receipt_file}):
            for location in ("local", "backup"):
                self._close((location, name))
        self._require_final_bundle(complete_private | {receipt_file})
        self.active = False
        return receipt

    def rollback(self) -> None:
        if not getattr(self, "active", False):
            return
        errors: list[Exception] = []
        for key in tuple(self.paths):
            try:
                path = self.paths[key]
                if key in self.descriptors or os.path.lexists(path):
                    self._remove(key)
            except Exception as error:
                errors.append(error)
        for location in ("backup", "local"):
            parent = self.parent_paths.get(location)
            if parent is None or not parent.exists():
                continue
            try:
                self._require_parent_owned(location)
                if any(parent.iterdir()):
                    raise SourceAuditError(
                        "cannot remove a nonempty source output directory"
                    )
                parent.rmdir()
            except Exception as error:
                errors.append(error)
        self.active = False
        if errors:
            raise SourceAuditError(
                "could not safely roll back source output reservations: "
                + "; ".join(str(error) for error in errors)
            )


def validate_public_receipt(value: Mapping[str, Any]) -> tuple[str, ...]:
    """Reject source prose, native locators, private paths, and stale self-hashes."""

    errors: list[str] = []
    if value.get("receipt_sha256") != canonical_json_sha256(
        {key: nested for key, nested in value.items() if key != "receipt_sha256"}
    ):
        errors.append("source receipt self-hash is invalid")

    def visit(current: Any, location: str) -> None:
        if isinstance(current, Mapping):
            for raw_key, nested in current.items():
                key = str(raw_key)
                key_folded = key.casefold()
                child = f"{location}.{key}" if location else key
                if key_folded in _FORBIDDEN_PUBLIC_KEYS:
                    errors.append(f"source receipt contains forbidden field: {child}")
                visit(key, child + ".<key>")
                visit(nested, child)
        elif isinstance(current, list):
            for index, nested in enumerate(current):
                visit(nested, f"{location}[{index}]")
        elif isinstance(current, str):
            normalized = current.replace("\\", "/")
            folded = current.casefold()
            if re.search(r"(?:^[A-Za-z]:/|^//|^/)", normalized):
                errors.append(f"source receipt contains an absolute local path: {location}")
            if any(
                host in folded
                for host in (
                    "export.arxiv.org",
                    "oaipmh.arxiv.org",
                    "pmc.ncbi.nlm.nih.gov",
                )
            ) or "oai:arxiv.org:" in folded or re.search(
                r"\bpmc\d+\b", folded, re.IGNORECASE
            ) or re.search(
                r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", folded, re.IGNORECASE
            ) or re.search(
                r"\b[a-z-]+/\d{7}(?:v\d+)?\b", folded, re.IGNORECASE
            ):
                errors.append(f"source receipt contains a native source-C id: {location}")

    visit(value, "")
    return tuple(sorted(set(errors)))
