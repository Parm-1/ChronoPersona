"""Frozen offline A/B parser-sample gate and portable evidence contract."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import importlib
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import unicodedata
from typing import Any

from .ab_parser_common import (
    ABParserError,
    canonical_jsonl_bytes,
    mapping_exact,
    require,
    sha256_bytes,
    stable_bounded_file_bytes,
)
from .content_manifest import tokenize_normalized
from .path_policy import PortablePathError, portable_relative_path
from .source_audit import (
    SourceAuditError,
    _git,
    _git_blob_bytes,
    _git_blob_for_payload,
    _plain_directory,
    _require_clean_git_state,
    _require_plain_repo_path,
    canonical_json_bytes,
    canonical_json_sha256,
    parse_json_object,
    receipt_with_self_hash,
)


PROFILE_RELATIVE_PATH = "configs/sources/ab-parser-sample-v0.json"
PROFILE_ID = "ab-parser-sample-v0"
FROZEN_PROFILE_CANONICAL_SHA256 = (
    "ad977d2b271b542fcaa12f8435992dd60c12c5c00ec7594d2f0e1e6814d01a43"
)
FROZEN_PROFILE_GIT_BLOB = "49539b69941d56a2a60da7ec7d062f317d374629"
E0_COMMIT = "3c49e2af27f0da36113085d5f746824f9a8148df"
BASELINE_COMMIT = "c245e7aaa16b2be35293fc5ca4d965efb7f5b84e"
OUTPUT_PREFIX = ("artifacts", "local", "ab-parser-sample")
DEFAULT_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
RUNTIME_RELATIVE_PATHS = (
    "scripts/run_ab_parser_sample.py",
    "src/chronopersona/__init__.py",
    "src/chronopersona/file_integrity.py",
    "src/chronopersona/path_policy.py",
    "src/chronopersona/content_manifest.py",
    "src/chronopersona/source_registry.py",
    "src/chronopersona/source_audit.py",
    "src/chronopersona/ab_parser_common.py",
    "src/chronopersona/wikimedia_ab_parser.py",
    "src/chronopersona/stackexchange_ab_parser.py",
    "src/chronopersona/ab_parser_sample.py",
)
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_RUN_LEAF = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
_PRIVATE_KEYS = frozenset(
    {
        "body",
        "comment",
        "contributor",
        "current_owner",
        "display_name",
        "identifier",
        "ip",
        "native_id",
        "normalized_body",
        "normalized_text",
        "normalized_title",
        "page_id",
        "parent_post_id",
        "parent_revision_id",
        "post_id",
        "prose",
        "raw",
        "raw_body",
        "raw_text",
        "raw_title",
        "record_id",
        "revision_guid",
        "revision_id",
        "site_id",
        "text",
        "title",
        "tokens",
        "user_id",
        "username",
    }
)


@dataclass(frozen=True)
class BoundABInputs:
    head: str
    bindings: dict[str, Any]
    payloads: dict[str, bytes]
    profile: dict[str, Any]


@dataclass(frozen=True)
class ParsedABBundle:
    records: tuple[dict[str, Any], ...]
    diagnostics: dict[str, int]


def _profile_path(root: Path) -> Path:
    try:
        relative = portable_relative_path(
            PROFILE_RELATIVE_PATH,
            label="A/B parser profile",
            required_prefix=("configs", "sources"),
            suffix=".json",
        )
    except PortablePathError as error:
        raise ABParserError("binding", "binding-failed", str(error)) from error
    return root / relative


def _validate_profile(profile: Mapping[str, Any]) -> None:
    require(
        canonical_json_sha256(profile) == FROZEN_PROFILE_CANONICAL_SHA256,
        stage="validation",
        reason="validation-failed",
        detail="A/B parser profile identity is not frozen",
    )
    mapping_exact(
        profile,
        {
            "schema_version",
            "profile_id",
            "status",
            "claim_ceiling",
            "external_spend_cad",
            "network_allowed",
            "live_source_access_enabled",
            "canonical_inputs",
            "limits",
            "fixture_bundle",
            "transformations",
            "publication",
            "runtime_paths",
            "closed_vocabularies",
            "prohibitions",
        },
        label="A/B parser profile",
    )
    require(
        type(profile["schema_version"]) is int
        and profile["schema_version"] == 1
        and profile["profile_id"] == PROFILE_ID
        and profile["status"] == "frozen"
        and profile["claim_ceiling"]
        == "tested-offline-synthetic-parser-engineering-only"
        and type(profile["external_spend_cad"]) is int
        and profile["external_spend_cad"] == 0
        and profile["network_allowed"] is False
        and profile["live_source_access_enabled"] is False,
        stage="validation",
        reason="validation-failed",
        detail="A/B parser profile header is invalid",
    )
    canonical_inputs = mapping_exact(
        profile["canonical_inputs"],
        {"baseline_commit", "e0_commit", "decision", "plan"},
        label="A/B parser canonical inputs",
    )
    require(
        canonical_inputs["baseline_commit"] == BASELINE_COMMIT
        and canonical_inputs["e0_commit"] == E0_COMMIT,
        stage="validation",
        reason="validation-failed",
        detail="A/B parser governance commits drifted",
    )
    for label in ("decision", "plan"):
        value = mapping_exact(
            canonical_inputs[label], {"path", "git_blob"}, label=f"{label} binding"
        )
        require(
            isinstance(value["path"], str)
            and _HEX40.fullmatch(value["git_blob"]) is not None,
            stage="validation",
            reason="validation-failed",
            detail=f"{label} binding is malformed",
        )
    limits = profile["limits"]
    mapping_exact(
        limits,
        {
            "max_mediawiki_pages",
            "max_mediawiki_revisions",
            "max_posts_rows",
            "max_posthistory_rows",
            "max_combined_revisions_and_rows",
            "max_xml_input_bytes",
            "max_total_xml_input_bytes",
            "max_decoded_text_bytes",
            "max_normalized_tokens",
            "max_alignment_product",
            "max_private_output_bytes",
            "max_aggregate_output_bytes",
            "max_receipt_output_bytes",
        },
        label="A/B parser limits",
    )
    require(
        all(type(value) is int and value > 0 for value in limits.values()),
        stage="validation",
        reason="validation-failed",
        detail="A/B parser limits must be positive integers",
    )
    bundle = mapping_exact(
        profile["fixture_bundle"],
        {
            "schema_version",
            "bundle_id",
            "bundle_hash_serialization",
            "synthetic_fixture",
            "expected_parsed_object_counts",
            "file_order",
            "files",
            "selection_order",
            "selections",
        },
        label="fixture bundle",
    )
    require(
        bundle["schema_version"] == 1
        and type(bundle["schema_version"]) is int
        and bundle["synthetic_fixture"] is True
        and bundle["expected_parsed_object_counts"]
        == {
            "mediawiki_pages": 2,
            "mediawiki_revisions": 6,
            "posts_rows": 4,
            "posthistory_rows": 14,
        }
        and bundle["file_order"] == ["wikimedia", "stack_posts", "stack_history"]
        and bundle["selection_order"]
        == [
            "wikimedia-early",
            "wikimedia-late",
            "stack-early-question",
            "stack-early-answer",
            "stack-late-question",
            "stack-late-answer",
        ]
        and set(bundle["files"]) == set(bundle["file_order"])
        and set(bundle["selections"]) == set(bundle["selection_order"]),
        stage="validation",
        reason="validation-failed",
        detail="fixture bundle order or identity drifted",
    )
    for label in bundle["file_order"]:
        record = mapping_exact(
            bundle["files"][label],
            {"path", "git_blob", "raw_sha256"},
            label=f"fixture {label}",
        )
        require(
            isinstance(record["path"], str)
            and _HEX40.fullmatch(record["git_blob"]) is not None
            and _HEX64.fullmatch(record["raw_sha256"]) is not None,
            stage="validation",
            reason="validation-failed",
            detail=f"fixture {label} identity is malformed",
        )
    for selection_id in bundle["selection_order"]:
        selection = bundle["selections"][selection_id]
        require(
            isinstance(selection, Mapping)
            and selection.get("fixture_window") in {"early", "late"}
            and selection.get("source") in {"wikimedia", "stackexchange"},
            stage="validation",
            reason="validation-failed",
            detail="fixture selection is malformed",
        )
    require(
        tuple(profile["runtime_paths"]) == RUNTIME_RELATIVE_PATHS,
        stage="validation",
        reason="validation-failed",
        detail="A/B parser runtime path enumeration drifted",
    )
    publication = mapping_exact(
        profile["publication"],
        {
            "mode",
            "json_serialization",
            "jsonl_serialization",
            "receipt_self_hash",
            "artifact_hash",
            "output_prefix",
            "private_records_file",
            "aggregate_file",
            "receipt_file",
            "outside_git_mirror_required",
        },
        label="A/B parser publication",
    )
    require(
        publication["mode"] == "create-only"
        and publication["output_prefix"] == "/".join(OUTPUT_PREFIX)
        and publication["private_records_file"] == "private-records.jsonl"
        and publication["aggregate_file"] == "aggregate.json"
        and publication["receipt_file"] == "receipt.json"
        and publication["outside_git_mirror_required"] is False,
        stage="validation",
        reason="validation-failed",
        detail="A/B parser publication contract drifted",
    )
    vocabularies = mapping_exact(
        profile["closed_vocabularies"],
        {
            "dispositions",
            "failure_stages",
            "failure_reasons",
            "published_failure_pairs",
            "scientific_statuses",
            "record_reasons",
        },
        label="A/B parser vocabularies",
    )
    require(
        len(vocabularies["dispositions"])
        == len(set(vocabularies["dispositions"]))
        and vocabularies["scientific_statuses"] == ["unresolved"]
        and vocabularies["published_failure_pairs"]
        == [
            "input-preflight/input-contract-failed",
            "parse-stackexchange/parser-contract-failed",
            "parse-wikimedia/parser-contract-failed",
            "validation/interrupted",
            "validation/parser-contract-failed",
            "validation/validation-failed",
        ]
        and all(isinstance(item, str) and item for values in vocabularies.values() for item in values),
        stage="validation",
        reason="validation-failed",
        detail="A/B parser vocabularies are not closed",
    )
    require(
        isinstance(profile["prohibitions"], Mapping)
        and profile["prohibitions"]
        and all(value is True for value in profile["prohibitions"].values()),
        stage="validation",
        reason="validation-failed",
        detail="A/B parser prohibitions are not fail-closed",
    )


def load_profile_for_plan(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    payload = stable_bounded_file_bytes(
        _profile_path(root), label="A/B parser profile", maximum_bytes=262144
    )
    try:
        value = parse_json_object(payload, label="A/B parser profile")
    except SourceAuditError as error:
        raise ABParserError("validation", "validation-failed", str(error)) from error
    _validate_profile(value)
    return value


def fixture_bundle_sha256(profile: Mapping[str, Any]) -> str:
    bundle = profile["fixture_bundle"]
    payload = bytearray(bundle["bundle_id"].encode("utf-8") + b"\0")
    for selection_id in bundle["selection_order"]:
        payload.extend(selection_id.encode("utf-8") + b"\0")
    for label in bundle["file_order"]:
        payload.extend(label.encode("utf-8") + b"\0")
        payload.extend(bundle["files"][label]["raw_sha256"].encode("ascii") + b"\0")
    return sha256_bytes(bytes(payload))


def _require_eol_policy(root: Path, relative: str) -> None:
    for attribute, expected in (("text", "set"), ("eol", "lf")):
        observed = _git(root, "check-attr", attribute, "--", relative)
        require(
            observed.endswith(f": {attribute}: {expected}"),
            stage="binding",
            reason="binding-failed",
            detail=f"{relative} is not pinned to portable LF text",
        )


def _bind_worktree_file(
    root: Path,
    *,
    relative: str,
    label: str,
    maximum_bytes: int,
    expected_blob: str | None = None,
    expected_raw_sha256: str | None = None,
    require_lf: bool = True,
) -> tuple[dict[str, Any], bytes]:
    try:
        portable = portable_relative_path(relative, label=label)
    except PortablePathError as error:
        raise ABParserError("binding", "binding-failed", str(error)) from error
    path = root / portable
    try:
        _require_plain_repo_path(root, path, label=label)
    except SourceAuditError as error:
        raise ABParserError("binding", "binding-failed", str(error)) from error
    payload = stable_bounded_file_bytes(
        path, label=label, maximum_bytes=maximum_bytes
    )
    raw_sha256 = sha256_bytes(payload)
    try:
        head_blob = _git(root, "rev-parse", f"HEAD:{relative}")
        computed_blob = _git_blob_for_payload(root, relative, payload)
        committed_payload = _git_blob_bytes(root, head_blob)
    except SourceAuditError as error:
        raise ABParserError("binding", "binding-failed", str(error)) from error
    require(
        _HEX40.fullmatch(head_blob) is not None
        and computed_blob == head_blob
        and committed_payload == payload
        and (expected_blob is None or head_blob == expected_blob)
        and (expected_raw_sha256 is None or raw_sha256 == expected_raw_sha256),
        stage="binding",
        reason="binding-failed",
        detail=f"{label} does not match exact HEAD bytes",
    )
    if require_lf:
        _require_eol_policy(root, relative)
    return {
        "path": relative,
        "git_blob": head_blob,
        "raw_sha256": raw_sha256,
        "size_bytes": len(payload),
    }, payload


def bind_fixture_inputs(root: Path, *, expected_head: str) -> BoundABInputs:
    root = root.resolve(strict=True)
    require(
        isinstance(expected_head, str) and _HEX40.fullmatch(expected_head) is not None,
        stage="binding",
        reason="binding-failed",
        detail="expected Git head must be full lowercase hexadecimal",
    )
    try:
        _require_clean_git_state(root)
        head = _git(root, "rev-parse", "HEAD")
    except SourceAuditError as error:
        raise ABParserError("binding", "binding-failed", str(error)) from error
    require(
        head == expected_head,
        stage="binding",
        reason="binding-failed",
        detail="current Git head does not match the expected head",
    )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", E0_COMMIT, head],
        cwd=root,
        check=False,
        capture_output=True,
    )
    require(
        ancestor.returncode == 0,
        stage="binding",
        reason="binding-failed",
        detail="frozen E0 commit is not an ancestor of execution head",
    )
    try:
        e0_parent = _git(root, "rev-parse", f"{E0_COMMIT}^")
    except SourceAuditError as error:
        raise ABParserError("binding", "binding-failed", str(error)) from error
    require(
        e0_parent == BASELINE_COMMIT,
        stage="binding",
        reason="binding-failed",
        detail="frozen E0 baseline identity drifted",
    )
    profile_binding, profile_payload = _bind_worktree_file(
        root,
        relative=PROFILE_RELATIVE_PATH,
        label="A/B parser profile",
        maximum_bytes=262144,
        expected_blob=FROZEN_PROFILE_GIT_BLOB,
    )
    try:
        profile = parse_json_object(profile_payload, label="A/B parser profile")
    except SourceAuditError as error:
        raise ABParserError("binding", "binding-failed", str(error)) from error
    _validate_profile(profile)
    bindings: dict[str, Any] = {
        "git_head": head,
        "worktree_clean": True,
        "baseline_commit": BASELINE_COMMIT,
        "e0_commit": E0_COMMIT,
        "profile": {
            **profile_binding,
            "canonical_sha256": FROZEN_PROFILE_CANONICAL_SHA256,
        },
        "governance": {},
        "fixtures": {},
        "runtime": [],
        "bundle_sha256": fixture_bundle_sha256(profile),
    }
    for label in ("decision", "plan"):
        record = profile["canonical_inputs"][label]
        try:
            observed_blob = _git(root, "rev-parse", f"{E0_COMMIT}:{record['path']}")
        except SourceAuditError as error:
            raise ABParserError("binding", "binding-failed", str(error)) from error
        require(
            observed_blob == record["git_blob"],
            stage="binding",
            reason="binding-failed",
            detail=f"frozen {label} Git blob drifted",
        )
        bindings["governance"][label] = {
            "path": record["path"],
            "e0_git_blob": observed_blob,
        }
    payloads: dict[str, bytes] = {"profile": profile_payload}
    total_xml = 0
    for label in profile["fixture_bundle"]["file_order"]:
        expected = profile["fixture_bundle"]["files"][label]
        record, payload = _bind_worktree_file(
            root,
            relative=expected["path"],
            label=f"synthetic fixture {label}",
            maximum_bytes=profile["limits"]["max_xml_input_bytes"],
            expected_blob=expected["git_blob"],
            expected_raw_sha256=expected["raw_sha256"],
        )
        total_xml += len(payload)
        bindings["fixtures"][label] = record
        payloads[label] = payload
    require(
        total_xml <= profile["limits"]["max_total_xml_input_bytes"],
        stage="binding",
        reason="binding-failed",
        detail="synthetic fixture bundle exceeds its total byte ceiling",
    )
    for relative in RUNTIME_RELATIVE_PATHS:
        record, payload = _bind_worktree_file(
            root,
            relative=relative,
            label=f"A/B parser runtime {relative}",
            maximum_bytes=4 * 1024 * 1024,
        )
        bindings["runtime"].append(record)
        payloads[f"runtime:{relative}"] = payload
    eol_record, eol_payload = _bind_worktree_file(
        root,
        relative=".gitattributes",
        label="Git EOL policy",
        maximum_bytes=1024 * 1024,
        require_lf=False,
    )
    bindings["eol_policy"] = eol_record
    payloads["eol_policy"] = eol_payload
    return BoundABInputs(
        head=head, bindings=bindings, payloads=payloads, profile=profile
    )


def rebind_fixture_inputs(root: Path, expected: BoundABInputs) -> BoundABInputs:
    try:
        rebound = bind_fixture_inputs(root, expected_head=expected.head)
    except ABParserError as error:
        raise ABParserError(
            "rebind", "rebind-failed", "A/B parser final binding could not be established"
        ) from error
    require(
        rebound.bindings == expected.bindings
        and rebound.payloads == expected.payloads
        and rebound.profile == expected.profile,
        stage="rebind",
        reason="rebind-failed",
        detail="A/B parser inputs changed after initial binding",
    )
    return rebound


def verify_runtime_module_paths(
    root: Path,
    *,
    observed: Mapping[str, str | Path | None],
    bound: BoundABInputs,
) -> None:
    require(
        tuple(observed) == RUNTIME_RELATIVE_PATHS,
        stage="binding",
        reason="binding-failed",
        detail="runtime module enumeration drifted",
    )
    records = {record["path"]: record for record in bound.bindings["runtime"]}
    for relative, raw_path in observed.items():
        require(
            raw_path is not None,
            stage="binding",
            reason="binding-failed",
            detail="runtime module has no source path",
        )
        try:
            path = Path(raw_path).resolve(strict=True)
            expected = (root / Path(*relative.split("/"))).resolve(strict=True)
        except OSError as error:
            raise ABParserError(
                "binding", "binding-failed", "runtime source path is unavailable"
            ) from error
        require(
            path == expected,
            stage="binding",
            reason="binding-failed",
            detail="runtime module did not load from the bound source path",
        )
        payload = stable_bounded_file_bytes(
            path, label=f"loaded runtime {relative}", maximum_bytes=4 * 1024 * 1024
        )
        require(
            sha256_bytes(payload) == records[relative]["raw_sha256"]
            and payload == bound.payloads[f"runtime:{relative}"],
            stage="binding",
            reason="binding-failed",
            detail="loaded runtime bytes differ from the bound runtime",
        )


def parse_fixture_bundle(bound: BoundABInputs) -> ParsedABBundle:
    wikimedia = importlib.import_module("chronopersona.wikimedia_ab_parser")
    stackexchange = importlib.import_module("chronopersona.stackexchange_ab_parser")
    selections = bound.profile["fixture_bundle"]["selections"]
    order = bound.profile["fixture_bundle"]["selection_order"]
    wiki_selected = [(key, selections[key]) for key in order if selections[key]["source"] == "wikimedia"]
    stack_selected = [(key, selections[key]) for key in order if selections[key]["source"] == "stackexchange"]
    wiki_records, wiki_counts = wikimedia.parse_wikimedia_fixture(
        bound.payloads["wikimedia"], profile=bound.profile, selections=wiki_selected
    )
    stack_records, stack_counts = stackexchange.parse_stackexchange_fixture(
        bound.payloads["stack_posts"],
        bound.payloads["stack_history"],
        profile=bound.profile,
        selections=stack_selected,
    )
    by_selection = {
        record["selection_id"]: record for record in (*wiki_records, *stack_records)
    }
    require(
        set(by_selection) == set(order) and len(by_selection) == len(order),
        stage="validation",
        reason="validation-failed",
        detail="parser output selection set is not exact",
    )
    require(
        wiki_counts["revisions"]
        + stack_counts["posts_rows"]
        + stack_counts["posthistory_rows"]
        <= bound.profile["limits"]["max_combined_revisions_and_rows"],
        stage="validation",
        reason="validation-failed",
        detail="combined parsed-object ceiling exceeded",
    )
    records = tuple(by_selection[key] for key in order)
    diagnostics = {
        "mediawiki_pages": wiki_counts["pages"],
        "mediawiki_revisions": wiki_counts["revisions"],
        "posts_rows": stack_counts["posts_rows"],
        "posthistory_rows": stack_counts["posthistory_rows"],
    }
    require(
        diagnostics
        == bound.profile["fixture_bundle"]["expected_parsed_object_counts"],
        stage="validation",
        reason="validation-failed",
        detail="parsed fixture object counts do not match the frozen bundle",
    )
    return ParsedABBundle(records=records, diagnostics=diagnostics)


def _hash_matches(value: Any, payload: bytes) -> bool:
    return isinstance(value, str) and value == sha256_bytes(payload)


def _validate_wikimedia_record(record: Mapping[str, Any]) -> None:
    mapping_exact(
        record,
        {
            "schema_version",
            "record_kind",
            "source",
            "selection_id",
            "fixture_window",
            "disposition",
            "reasons",
            "page",
            "lineage",
            "contributor",
            "raw",
            "normalized",
            "candidate_spans",
            "diagnostics",
            "transformation",
            "tokenizer",
            "authorship_status",
            "rights_status",
            "persistence_status",
            "scientific_eligibility",
        },
        label="private Wikimedia record",
    )
    page = mapping_exact(
        record["page"], {"page_id", "title", "redirect_title"}, label="private page"
    )
    lineage = mapping_exact(
        record["lineage"],
        {
            "parent_revision_id",
            "child_revision_id",
            "child_parent_revision_id",
            "parent_timestamp",
            "child_timestamp",
            "history_coverage",
            "chronology",
        },
        label="private Wikimedia lineage",
    )
    mapping_exact(
        record["contributor"], {"kind", "value", "user_id"}, label="private contributor"
    )
    raw = mapping_exact(
        record["raw"],
        {
            "parent_text",
            "parent_bytes",
            "parent_sha256",
            "parent_mediawiki_sha1_base36",
            "child_text",
            "child_bytes",
            "child_sha256",
            "child_mediawiki_sha1_base36",
        },
        label="private Wikimedia raw evidence",
    )
    normalized = mapping_exact(
        record["normalized"],
        {
            "parent_text",
            "parent_sha256",
            "parent_tokens",
            "child_text",
            "child_sha256",
            "child_tokens",
        },
        label="private Wikimedia normalized evidence",
    )
    diagnostics = mapping_exact(
        record["diagnostics"],
        {
            "origin_revision_id",
            "origin_matches_child",
            "rollback_signal",
            "reintroduction_status",
            "import_comment_signal",
            "parent_removed_counts",
            "child_removed_counts",
        },
        label="private Wikimedia diagnostics",
    )
    require(
        type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["record_kind"] == "wikimedia-added-span"
        and record["source"] == "wikimedia"
        and isinstance(page["title"], str)
        and isinstance(page["page_id"], str)
        and lineage["child_parent_revision_id"] == lineage["parent_revision_id"]
        and type(diagnostics["origin_matches_child"]) is bool
        and type(diagnostics["rollback_signal"]) is bool
        and diagnostics["reintroduction_status"] in {"signal-present", "not-observed", "unresolved"}
        and diagnostics["import_comment_signal"] in {"signal-present", "not-observed"},
        stage="validation",
        reason="validation-failed",
        detail="private Wikimedia record semantics are not exact",
    )
    for prefix in ("parent", "child"):
        text = raw[f"{prefix}_text"]
        normalized_text = normalized[f"{prefix}_text"]
        require(
            isinstance(text, str)
            and raw[f"{prefix}_bytes"] == len(text.encode("utf-8"))
            and _hash_matches(raw[f"{prefix}_sha256"], text.encode("utf-8"))
            and isinstance(normalized_text, str)
            and _hash_matches(
                normalized[f"{prefix}_sha256"], normalized_text.encode("utf-8")
            )
            and normalized[f"{prefix}_tokens"] == list(tokenize_normalized(normalized_text)),
            stage="validation",
            reason="validation-failed",
            detail="private Wikimedia text identity is inconsistent",
        )
    child_tokens = normalized["child_tokens"]
    prior_end = 0
    for span in record["candidate_spans"]:
        mapping_exact(
            span,
            {"child_token_start", "child_token_end", "tokens"},
            label="private Wikimedia candidate span",
        )
        start = span["child_token_start"]
        end = span["child_token_end"]
        require(
            type(start) is int
            and type(end) is int
            and prior_end <= start < end <= len(child_tokens)
            and span["tokens"] == child_tokens[start:end],
            stage="validation",
            reason="validation-failed",
            detail="private Wikimedia candidate offsets are invalid",
        )
        prior_end = end


def _validate_stack_record(record: Mapping[str, Any]) -> None:
    mapping_exact(
        record,
        {
            "schema_version",
            "record_kind",
            "source",
            "selection_id",
            "fixture_window",
            "stratum",
            "disposition",
            "reasons",
            "post",
            "initial_action",
            "current_field_evidence",
            "history",
            "diagnostics",
            "transformation",
            "tokenizer",
            "authorship_status",
            "license_status",
            "rights_status",
            "scientific_eligibility",
        },
        label="private Stack Exchange record",
    )
    post = mapping_exact(
        record["post"],
        {
            "site_id",
            "post_id",
            "post_type",
            "parent_post_id",
            "creation_timestamp",
            "current_owner",
        },
        label="private Stack Exchange post",
    )
    action = mapping_exact(
        record["initial_action"],
        {
            "revision_guid",
            "timestamp",
            "history_row_ids",
            "actor",
            "raw_title",
            "raw_title_sha256",
            "raw_body",
            "raw_body_sha256",
            "raw_tags",
            "raw_tags_sha256",
            "normalized_title",
            "normalized_title_sha256",
            "title_tokens",
            "normalized_body",
            "normalized_body_sha256",
            "body_tokens",
        },
        label="private Stack Exchange initial action",
    )
    current = mapping_exact(
        record["current_field_evidence"],
        {"body_relation", "body_sha256", "title_relation", "title_sha256"},
        label="private Stack Exchange current evidence",
    )
    history = mapping_exact(
        record["history"],
        {"row_count", "signal_categories", "ordered_actions"},
        label="private Stack Exchange history",
    )
    diagnostics = mapping_exact(
        record["diagnostics"],
        {"current_fields_used_as_prose", "body_removed_counts"},
        label="private Stack Exchange diagnostics",
    )
    require(
        type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["record_kind"] == "stackexchange-initial-version"
        and record["source"] == "stackexchange"
        and record["stratum"] in {"question", "answer"}
        and post["post_type"] == record["stratum"]
        and diagnostics["current_fields_used_as_prose"] is False
        and current["body_relation"] in {"same", "different"}
        and current["title_relation"] in {"same", "different", "absent"}
        and type(history["row_count"]) is int
        and history["row_count"] >= 1,
        stage="validation",
        reason="validation-failed",
        detail="private Stack Exchange record semantics are not exact",
    )
    raw_body = action["raw_body"]
    normalized_body = action["normalized_body"]
    require(
        isinstance(raw_body, str)
        and _hash_matches(action["raw_body_sha256"], raw_body.encode("utf-8"))
        and isinstance(normalized_body, str)
        and _hash_matches(
            action["normalized_body_sha256"], normalized_body.encode("utf-8")
        )
        and action["body_tokens"] == list(tokenize_normalized(normalized_body)),
        stage="validation",
        reason="validation-failed",
        detail="private Stack Exchange body identity is inconsistent",
    )
    if record["stratum"] == "question":
        raw_title = action["raw_title"]
        normalized_title = action["normalized_title"]
        require(
            isinstance(raw_title, str)
            and _hash_matches(action["raw_title_sha256"], raw_title.encode("utf-8"))
            and isinstance(normalized_title, str)
            and _hash_matches(
                action["normalized_title_sha256"], normalized_title.encode("utf-8")
            )
            and action["title_tokens"] == list(tokenize_normalized(normalized_title))
            and action["raw_tags"] is not None,
            stage="validation",
            reason="validation-failed",
            detail="private Stack Exchange question identity is inconsistent",
        )
    else:
        require(
            all(
                action[key] is None or action[key] == []
                for key in (
                    "raw_title",
                    "raw_title_sha256",
                    "raw_tags",
                    "raw_tags_sha256",
                    "normalized_title",
                    "normalized_title_sha256",
                    "title_tokens",
                )
            )
            and current["title_relation"] == "absent",
            stage="validation",
            reason="validation-failed",
            detail="private Stack Exchange answer contains title/tag evidence",
        )


def _validate_private_record_shapes(
    records: Sequence[Mapping[str, Any]], profile: Mapping[str, Any]
) -> tuple[str, ...]:
    errors: list[str] = []
    try:
        order = profile["fixture_bundle"]["selection_order"]
        require(
            len(records) == len(order)
            and [record.get("selection_id") for record in records] == order,
            stage="validation",
            reason="validation-failed",
            detail="private record order is not exact",
        )
        dispositions = set(profile["closed_vocabularies"]["dispositions"])
        reasons = set(profile["closed_vocabularies"]["record_reasons"])
        for record in records:
            require(
                record.get("disposition") in dispositions
                and isinstance(record.get("reasons"), list)
                and record["reasons"] == sorted(set(record["reasons"]))
                and set(record["reasons"]).issubset(reasons)
                and record.get("scientific_eligibility") == "unresolved"
                and record.get("authorship_status") == "unresolved"
                and record.get("rights_status") == "unresolved",
                stage="validation",
                reason="validation-failed",
                detail="private record statuses are not exact",
            )
            if record.get("source") == "wikimedia":
                _validate_wikimedia_record(record)
            elif record.get("source") == "stackexchange":
                _validate_stack_record(record)
            else:
                raise ABParserError(
                    "validation", "validation-failed", "private record source drifted"
                )
    except (ABParserError, KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    return tuple(errors)


def validate_private_records(
    records: Sequence[Mapping[str, Any]], bound: BoundABInputs
) -> tuple[str, ...]:
    errors = list(_validate_private_record_shapes(records, bound.profile))
    if errors:
        return tuple(errors)
    try:
        expected = parse_fixture_bundle(bound)
        require(
            canonical_jsonl_bytes(records) == canonical_jsonl_bytes(expected.records),
            stage="validation",
            reason="validation-failed",
            detail="private records do not match the exact bound fixture parse",
        )
    except (ABParserError, KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    return tuple(errors)


def validate_private_jsonl(
    payload: bytes, bound: BoundABInputs
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    try:
        require(
            0 < len(payload) <= bound.profile["limits"]["max_private_output_bytes"]
            and payload.endswith(b"\n"),
            stage="validation",
            reason="validation-failed",
            detail="private JSONL envelope is invalid",
        )
        for index, line in enumerate(payload.splitlines(), start=1):
            require(
                bool(line),
                stage="validation",
                reason="validation-failed",
                detail="private JSONL contains a blank record",
            )
            try:
                record = parse_json_object(line, label=f"private record {index}")
            except SourceAuditError as error:
                raise ABParserError(
                    "validation", "validation-failed", "private JSONL is invalid"
                ) from error
            require(
                canonical_json_bytes(record) == line,
                stage="validation",
                reason="validation-failed",
                detail="private JSONL record is not canonical",
            )
            records.append(record)
        require(
            canonical_jsonl_bytes(records) == payload,
            stage="validation",
            reason="validation-failed",
            detail="private JSONL bytes are not exactly canonical",
        )
        errors.extend(validate_private_records(records, bound))
    except (ABParserError, KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    return tuple(records), tuple(errors)


def _record_metric(record: Mapping[str, Any]) -> dict[str, int]:
    if record["source"] == "wikimedia":
        raw = record["raw"]
        normalized = record["normalized"]
        return {
            "raw_bytes": raw["parent_bytes"] + raw["child_bytes"],
            "clean_bytes": len(normalized["parent_text"].encode("utf-8"))
            + len(normalized["child_text"].encode("utf-8")),
            "token_count": len(normalized["parent_tokens"])
            + len(normalized["child_tokens"]),
            "candidate_span_count": len(record["candidate_spans"]),
        }
    action = record["initial_action"]
    raw_values = [action["raw_body"], action["raw_title"]]
    clean_values = [action["normalized_body"], action["normalized_title"]]
    return {
        "raw_bytes": sum(len(value.encode("utf-8")) for value in raw_values if value is not None),
        "clean_bytes": sum(len(value.encode("utf-8")) for value in clean_values if value is not None),
        "token_count": len(action["body_tokens"]) + len(action["title_tokens"]),
        "candidate_span_count": 0,
    }


def _boundaries() -> dict[str, bool]:
    return {
        "current_snapshot_or_body_fallback_used": False,
        "d039_private_artifact_accessed": False,
        "live_source_accessed": False,
        "model_executed": False,
        "network_accessed": False,
        "scientific_claim_authorized": False,
        "source_c_accessed": False,
    }


def _runtime_identity() -> dict[str, str]:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "unicode_version": unicodedata.unidata_version,
    }


def build_aggregate(
    bound: BoundABInputs,
    *,
    records: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, int],
    status: str = "complete",
) -> dict[str, Any]:
    order = bound.profile["fixture_bundle"]["selection_order"]
    by_selection = {record["selection_id"]: record for record in records}
    groups: list[dict[str, Any]] = []
    total_metrics = Counter()
    disposition_counts = Counter()
    reason_counts = Counter()
    for selection_id in order:
        selection = bound.profile["fixture_bundle"]["selections"][selection_id]
        record = by_selection.get(selection_id)
        if record is None:
            metric = {
                "raw_bytes": 0,
                "clean_bytes": 0,
                "token_count": 0,
                "candidate_span_count": 0,
            }
            disposition = None
            group_reasons: dict[str, int] = {}
            group_status = "not-established"
        else:
            metric = _record_metric(record)
            disposition = record["disposition"]
            group_reasons = dict(Counter(record["reasons"]))
            group_status = "complete"
            total_metrics.update(metric)
            disposition_counts[disposition] += 1
            reason_counts.update(record["reasons"])
        groups.append(
            {
                "group": selection_id,
                "source": selection["source"],
                "fixture_window": selection["fixture_window"],
                "stratum": selection.get("post_type", "added-span"),
                "status": group_status,
                "disposition": disposition,
                "reason_counts": dict(sorted(group_reasons.items())),
                **metric,
            }
        )
    aggregate = {
        "schema_version": 1,
        "profile_id": PROFILE_ID,
        "status": status,
        "claim_ceiling": bound.profile["claim_ceiling"],
        "execution": {
            "git_head": bound.head,
            "baseline_commit": BASELINE_COMMIT,
            "e0_commit": E0_COMMIT,
            "profile_canonical_sha256": FROZEN_PROFILE_CANONICAL_SHA256,
            "fixture_bundle_sha256": bound.bindings["bundle_sha256"],
            "synthetic_fixture": True,
        },
        "runtime_identity": _runtime_identity(),
        "parsed_object_counts": dict(diagnostics),
        "summary": {
            "selection_count": len(records),
            "source_record_counts": dict(sorted(Counter(record["source"] for record in records).items())),
            "disposition_counts": dict(sorted(disposition_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "raw_bytes": total_metrics["raw_bytes"],
            "clean_bytes": total_metrics["clean_bytes"],
            "token_count": total_metrics["token_count"],
            "candidate_span_count": total_metrics["candidate_span_count"],
        },
        "groups": groups,
        "boundaries": _boundaries(),
    }
    aggregate["output_sha256"] = canonical_json_sha256(aggregate)
    return aggregate


def _public_value_errors(value: Any) -> tuple[str, ...]:
    errors: list[str] = []

    def visit(current: Any, location: str) -> None:
        if isinstance(current, Mapping):
            for key, nested in current.items():
                key_text = str(key)
                if key_text.casefold() in _PRIVATE_KEYS:
                    errors.append(f"portable evidence contains private field at {location}.{key_text}")
                visit(nested, f"{location}.{key_text}")
        elif isinstance(current, list):
            for index, nested in enumerate(current):
                visit(nested, f"{location}[{index}]")
        elif isinstance(current, str):
            folded = current.casefold()
            if re.search(r"(?:[a-z]:\\|\\\\|/(?:home|users|root|tmp|var|mnt)/)", current, re.IGNORECASE):
                errors.append(f"portable evidence contains an absolute path at {location}")
            if "@" in current or "http://" in folded or "https://" in folded:
                errors.append(f"portable evidence contains a locator or identity at {location}")

    visit(value, "root")
    return tuple(errors)


def validate_aggregate(
    value: Mapping[str, Any],
    *,
    bound: BoundABInputs,
    private_payload: bytes,
) -> tuple[str, ...]:
    errors: list[str] = []
    try:
        mapping_exact(
            value,
            {
                "schema_version",
                "profile_id",
                "status",
                "claim_ceiling",
                "execution",
                "runtime_identity",
                "parsed_object_counts",
                "summary",
                "groups",
                "boundaries",
                "output_sha256",
            },
            label="portable aggregate",
        )
        without_hash = dict(value)
        observed_hash = without_hash.pop("output_sha256")
        require(
            _HEX64.fullmatch(observed_hash) is not None
            and observed_hash == canonical_json_sha256(without_hash),
            stage="validation",
            reason="validation-failed",
            detail="portable aggregate self-hash is invalid",
        )
        execution = mapping_exact(
            value["execution"],
            {
                "git_head",
                "baseline_commit",
                "e0_commit",
                "profile_canonical_sha256",
                "fixture_bundle_sha256",
                "synthetic_fixture",
            },
            label="aggregate execution",
        )
        require(
            type(value["schema_version"]) is int
            and value["schema_version"] == 1
            and value["profile_id"] == PROFILE_ID
            and value["status"] in {"complete", "failed"}
            and value["claim_ceiling"] == bound.profile["claim_ceiling"]
            and execution
            == {
                "git_head": bound.head,
                "baseline_commit": BASELINE_COMMIT,
                "e0_commit": E0_COMMIT,
                "profile_canonical_sha256": FROZEN_PROFILE_CANONICAL_SHA256,
                "fixture_bundle_sha256": bound.bindings["bundle_sha256"],
                "synthetic_fixture": True,
            }
            and value["runtime_identity"] == _runtime_identity()
            and value["boundaries"] == _boundaries(),
            stage="validation",
            reason="validation-failed",
            detail="portable aggregate base evidence drifted",
        )
        diagnostics = mapping_exact(
            value["parsed_object_counts"],
            {"mediawiki_pages", "mediawiki_revisions", "posts_rows", "posthistory_rows"},
            label="aggregate parsed-object counts",
        )
        require(
            all(type(count) is int and count >= 0 for count in diagnostics.values())
            and (
                diagnostics
                == bound.profile["fixture_bundle"]["expected_parsed_object_counts"]
                if value["status"] == "complete"
                else all(count == 0 for count in diagnostics.values())
            ),
            stage="validation",
            reason="validation-failed",
            detail="aggregate parsed-object counts are invalid",
        )
        if value["status"] == "complete":
            records, private_errors = validate_private_jsonl(private_payload, bound)
            require(
                not private_errors,
                stage="validation",
                reason="validation-failed",
                detail="private artifact does not validate against aggregate",
            )
        else:
            require(
                private_payload == b"" and all(count == 0 for count in diagnostics.values()),
                stage="validation",
                reason="validation-failed",
                detail="failed aggregate must retain an empty private artifact and zero counts",
            )
            records = ()
        expected = build_aggregate(
            bound,
            records=records,
            diagnostics=diagnostics,
            status=value["status"],
        )
        require(
            dict(value) == expected,
            stage="validation",
            reason="validation-failed",
            detail="portable aggregate is not the exact projection of private evidence",
        )
        errors.extend(_public_value_errors(value))
    except (ABParserError, KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    return tuple(errors)


def _portable_bindings(bound: BoundABInputs) -> dict[str, Any]:
    return {
        "git": {
            "head": bound.head,
            "worktree_clean": True,
            "baseline_commit": BASELINE_COMMIT,
            "e0_commit": E0_COMMIT,
        },
        "profile": dict(bound.bindings["profile"]),
        "governance": {
            key: dict(value) for key, value in bound.bindings["governance"].items()
        },
        "fixtures": {
            key: dict(value) for key, value in bound.bindings["fixtures"].items()
        },
        "fixture_bundle_sha256": bound.bindings["bundle_sha256"],
        "runtime": [dict(value) for value in bound.bindings["runtime"]],
        "eol_policy": dict(bound.bindings["eol_policy"]),
    }


def build_receipt(
    bound: BoundABInputs,
    *,
    aggregate_payload: bytes,
    private_payload: bytes,
    status: str,
    failure: Mapping[str, Any] | None,
) -> dict[str, Any]:
    publication = bound.profile["publication"]
    receipt = {
        "schema_version": 1,
        "profile_id": PROFILE_ID,
        "status": status,
        "claim_ceiling": bound.profile["claim_ceiling"],
        "bindings": _portable_bindings(bound),
        "runtime_identity": _runtime_identity(),
        "parser_order": list(bound.profile["fixture_bundle"]["selection_order"]),
        "limits": dict(bound.profile["limits"]),
        "artifacts": {
            "private_records": {
                "file": publication["private_records_file"],
                "size_bytes": len(private_payload),
                "sha256": sha256_bytes(private_payload),
            },
            "aggregate": {
                "file": publication["aggregate_file"],
                "size_bytes": len(aggregate_payload),
                "sha256": sha256_bytes(aggregate_payload),
            },
        },
        "final_binding_status": "matched",
        "failure": dict(failure) if failure is not None else None,
        "boundaries": _boundaries(),
    }
    return receipt_with_self_hash(receipt)


def validate_receipt(
    value: Mapping[str, Any],
    *,
    bound: BoundABInputs,
    receipt_payload: bytes,
    aggregate_payload: bytes,
    private_payload: bytes,
) -> tuple[str, ...]:
    errors: list[str] = []
    try:
        mapping_exact(
            value,
            {
                "schema_version",
                "profile_id",
                "status",
                "claim_ceiling",
                "bindings",
                "runtime_identity",
                "parser_order",
                "limits",
                "artifacts",
                "final_binding_status",
                "failure",
                "boundaries",
                "receipt_sha256",
            },
            label="A/B parser receipt",
        )
        require(
            0 < len(receipt_payload)
            <= bound.profile["limits"]["max_receipt_output_bytes"]
            and receipt_payload == canonical_json_bytes(value, pretty=True)
            and 0 < len(aggregate_payload)
            <= bound.profile["limits"]["max_aggregate_output_bytes"],
            stage="validation",
            reason="validation-failed",
            detail="receipt or aggregate artifact bytes are not canonical and bounded",
        )
        without_hash = dict(value)
        observed_hash = without_hash.pop("receipt_sha256")
        require(
            _HEX64.fullmatch(observed_hash) is not None
            and observed_hash == canonical_json_sha256(without_hash),
            stage="validation",
            reason="validation-failed",
            detail="A/B parser receipt self-hash is invalid",
        )
        require(
            type(value["schema_version"]) is int
            and value["schema_version"] == 1
            and value["profile_id"] == PROFILE_ID
            and value["status"] in {"complete", "failed"}
            and value["claim_ceiling"] == bound.profile["claim_ceiling"]
            and value["bindings"] == _portable_bindings(bound)
            and value["runtime_identity"] == _runtime_identity()
            and value["parser_order"] == bound.profile["fixture_bundle"]["selection_order"]
            and value["limits"] == bound.profile["limits"]
            and value["final_binding_status"] == "matched"
            and value["boundaries"] == _boundaries(),
            stage="validation",
            reason="validation-failed",
            detail="A/B parser receipt base evidence drifted",
        )
        artifacts = mapping_exact(
            value["artifacts"],
            {"private_records", "aggregate"},
            label="receipt artifacts",
        )
        publication = bound.profile["publication"]
        expected_artifacts = {
            "private_records": {
                "file": publication["private_records_file"],
                "size_bytes": len(private_payload),
                "sha256": sha256_bytes(private_payload),
            },
            "aggregate": {
                "file": publication["aggregate_file"],
                "size_bytes": len(aggregate_payload),
                "sha256": sha256_bytes(aggregate_payload),
            },
        }
        require(
            artifacts == expected_artifacts,
            stage="validation",
            reason="validation-failed",
            detail="receipt artifact identities do not match published bytes",
        )
        if value["status"] == "complete":
            require(
                value["failure"] is None,
                stage="validation",
                reason="validation-failed",
                detail="complete receipt must not contain a failure",
            )
        else:
            failure = mapping_exact(
                value["failure"], {"stage", "reason"}, label="receipt failure"
            )
            require(
                failure["stage"] in bound.profile["closed_vocabularies"]["failure_stages"]
                and failure["reason"] in bound.profile["closed_vocabularies"]["failure_reasons"]
                and f"{failure['stage']}/{failure['reason']}"
                in bound.profile["closed_vocabularies"]["published_failure_pairs"],
                stage="validation",
                reason="validation-failed",
                detail="receipt failure classification is not closed",
            )
        expected = build_receipt(
            bound,
            aggregate_payload=aggregate_payload,
            private_payload=private_payload,
            status=value["status"],
            failure=value["failure"],
        )
        require(
            dict(value) == expected,
            stage="validation",
            reason="validation-failed",
            detail="A/B parser receipt is not canonical",
        )
        try:
            aggregate = parse_json_object(aggregate_payload, label="A/B parser aggregate")
        except SourceAuditError as error:
            raise ABParserError(
                "validation", "validation-failed", "aggregate payload is invalid"
            ) from error
        require(
            aggregate_payload == canonical_json_bytes(aggregate, pretty=True),
            stage="validation",
            reason="validation-failed",
            detail="aggregate artifact bytes are not canonical pretty JSON",
        )
        aggregate_errors = validate_aggregate(
            aggregate, bound=bound, private_payload=private_payload
        )
        require(
            not aggregate_errors and aggregate["status"] == value["status"],
            stage="validation",
            reason="validation-failed",
            detail="receipt and aggregate do not form one valid evidence bundle",
        )
        errors.extend(_public_value_errors(value))
    except (ABParserError, KeyError, TypeError, ValueError) as error:
        errors.append(str(error))
    return tuple(errors)


def build_success_artifacts(
    bound: BoundABInputs, parsed: ParsedABBundle
) -> dict[str, bytes]:
    expected_parse = parse_fixture_bundle(bound)
    require(
        canonical_jsonl_bytes(parsed.records)
        == canonical_jsonl_bytes(expected_parse.records)
        and canonical_json_bytes(parsed.diagnostics)
        == canonical_json_bytes(expected_parse.diagnostics),
        stage="validation",
        reason="validation-failed",
        detail="supplied parsed bundle does not match the exact bound fixture parse",
    )
    private_errors = validate_private_records(parsed.records, bound)
    require(
        not private_errors,
        stage="validation",
        reason="validation-failed",
        detail="private parser records failed their closed validator",
    )
    private_payload = canonical_jsonl_bytes(parsed.records)
    require(
        len(private_payload) <= bound.profile["limits"]["max_private_output_bytes"],
        stage="validation",
        reason="validation-failed",
        detail="private artifact exceeds its output ceiling",
    )
    aggregate = build_aggregate(
        bound, records=parsed.records, diagnostics=parsed.diagnostics
    )
    aggregate_payload = canonical_json_bytes(aggregate, pretty=True)
    require(
        len(aggregate_payload) <= bound.profile["limits"]["max_aggregate_output_bytes"],
        stage="validation",
        reason="validation-failed",
        detail="aggregate exceeds its output ceiling",
    )
    receipt = build_receipt(
        bound,
        aggregate_payload=aggregate_payload,
        private_payload=private_payload,
        status="complete",
        failure=None,
    )
    receipt_payload = canonical_json_bytes(receipt, pretty=True)
    require(
        len(receipt_payload) <= bound.profile["limits"]["max_receipt_output_bytes"],
        stage="validation",
        reason="validation-failed",
        detail="receipt exceeds its output ceiling",
    )
    require(
        not validate_aggregate(aggregate, bound=bound, private_payload=private_payload)
        and not validate_receipt(
            receipt,
            bound=bound,
            receipt_payload=receipt_payload,
            aggregate_payload=aggregate_payload,
            private_payload=private_payload,
        ),
        stage="validation",
        reason="validation-failed",
        detail="success evidence failed top-level validation",
    )
    return {
        bound.profile["publication"]["private_records_file"]: private_payload,
        bound.profile["publication"]["aggregate_file"]: aggregate_payload,
        bound.profile["publication"]["receipt_file"]: receipt_payload,
    }


def build_failure_artifacts(
    bound: BoundABInputs, *, stage: str, reason: str
) -> dict[str, bytes]:
    require(
        stage in bound.profile["closed_vocabularies"]["failure_stages"]
        and reason in bound.profile["closed_vocabularies"]["failure_reasons"],
        stage="validation",
        reason="validation-failed",
        detail="failure classification is not frozen",
    )
    require(
        f"{stage}/{reason}"
        in bound.profile["closed_vocabularies"]["published_failure_pairs"],
        stage="validation",
        reason="validation-failed",
        detail="failure classification cannot produce a published receipt",
    )
    private_payload = b""
    diagnostics = {
        "mediawiki_pages": 0,
        "mediawiki_revisions": 0,
        "posts_rows": 0,
        "posthistory_rows": 0,
    }
    aggregate = build_aggregate(
        bound, records=(), diagnostics=diagnostics, status="failed"
    )
    aggregate_payload = canonical_json_bytes(aggregate, pretty=True)
    failure = {"stage": stage, "reason": reason}
    receipt = build_receipt(
        bound,
        aggregate_payload=aggregate_payload,
        private_payload=private_payload,
        status="failed",
        failure=failure,
    )
    receipt_payload = canonical_json_bytes(receipt, pretty=True)
    require(
        len(aggregate_payload) <= bound.profile["limits"]["max_aggregate_output_bytes"]
        and len(receipt_payload) <= bound.profile["limits"]["max_receipt_output_bytes"]
        and not validate_aggregate(aggregate, bound=bound, private_payload=private_payload)
        and not validate_receipt(
            receipt,
            bound=bound,
            receipt_payload=receipt_payload,
            aggregate_payload=aggregate_payload,
            private_payload=private_payload,
        ),
        stage="validation",
        reason="validation-failed",
        detail="failure evidence failed top-level validation",
    )
    return {
        bound.profile["publication"]["private_records_file"]: private_payload,
        bound.profile["publication"]["aggregate_file"]: aggregate_payload,
        bound.profile["publication"]["receipt_file"]: receipt_payload,
    }


def _plain_file_identity(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        stat.S_ISREG(info.st_mode)
        and not (int(getattr(info, "st_file_attributes", 0)) & reparse_flag)
        and int(info.st_nlink) == 1
    )


def _plain_directory_identity(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISDIR(info.st_mode) and not (
        int(getattr(info, "st_file_attributes", 0)) & reparse_flag
    )


def _descriptor_change_token(descriptor: int, info: os.stat_result) -> int:
    """Return the OS change-time token, not Windows' creation-time alias."""

    if os.name != "nt":
        return int(info.st_ctime_ns)
    try:
        import ctypes
        import msvcrt

        class _FileBasicInfo(ctypes.Structure):
            _fields_ = [
                ("creation_time", ctypes.c_longlong),
                ("last_access_time", ctypes.c_longlong),
                ("last_write_time", ctypes.c_longlong),
                ("change_time", ctypes.c_longlong),
                ("file_attributes", ctypes.c_ulong),
            ]

        observed = _FileBasicInfo()
        handle = msvcrt.get_osfhandle(descriptor)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        result = kernel32.GetFileInformationByHandleEx(
            ctypes.c_void_p(handle),
            0,  # FileBasicInfo
            ctypes.byref(observed),
            ctypes.sizeof(observed),
        )
        if not result:
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandleEx")
        return int(observed.change_time)
    except OSError as error:
        raise ABParserError(
            "publication", "publication-failed", "artifact change time is unavailable"
        ) from error


def _windows_lock_descriptor(descriptor: int, *, unlock: bool) -> None:
    """Lock the full signed 64-bit file-offset space on Windows."""

    import ctypes
    import msvcrt

    pointer_integer = (
        ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
    )

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("internal", pointer_integer),
            ("internal_high", pointer_integer),
            ("offset", ctypes.c_ulong),
            ("offset_high", ctypes.c_ulong),
            ("event", ctypes.c_void_p),
        ]

    overlapped = _Overlapped()
    handle = ctypes.c_void_p(msvcrt.get_osfhandle(descriptor))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if unlock:
        operation = kernel32.UnlockFileEx
        operation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(_Overlapped),
        ]
        operation.restype = ctypes.c_int
        result = operation(
            handle,
            0,
            0xFFFFFFFF,
            0xFFFFFFFF,
            ctypes.byref(overlapped),
        )
    else:
        operation = kernel32.LockFileEx
        operation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(_Overlapped),
        ]
        operation.restype = ctypes.c_int
        result = operation(
            handle,
            0x00000001 | 0x00000002,  # fail immediately, exclusive
            0,
            0xFFFFFFFF,
            0xFFFFFFFF,
            ctypes.byref(overlapped),
        )
    if not result:
        raise OSError(ctypes.get_last_error(), "Windows artifact range lock failed")


def _windows_open_directory_guard(
    path: Path,
    identity: tuple[int, int],
    *,
    owner: list[int] | None = None,
) -> int:
    """Open one rename-blocking directory handle and bind its exact identity."""

    import ctypes
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("file_attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("volume_serial_number", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        ]

    class _FileIdInformation(ctypes.Structure):
        _fields_ = [
            ("volume_serial_number", ctypes.c_ulonglong),
            ("file_id", ctypes.c_ubyte * 16),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    handle = create(
        str(path),
        # LIST_DIRECTORY | TRAVERSE | READ_ATTRIBUTES | DELETE | SYNCHRONIZE.
        # Share-read only makes Windows enforce the exact run-directory
        # namespace while this handle is retained through terminal delivery.
        0x00000001 | 0x00000020 | 0x00000080 | 0x00010000 | 0x00100000,
        0x00000001,
        None,
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        raise OSError(ctypes.get_last_error(), "Windows directory guard open failed")
    observed_handle = int(handle)
    registered = False
    try:
        information = _ByHandleFileInformation()
        query = kernel32.GetFileInformationByHandle
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ByHandleFileInformation)]
        query.restype = wintypes.BOOL
        if not query(handle, ctypes.byref(information)):
            raise OSError(
                ctypes.get_last_error(),
                "Windows directory guard identity query failed",
            )
        file_id_information = _FileIdInformation()
        query_extended = kernel32.GetFileInformationByHandleEx
        query_extended.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        query_extended.restype = wintypes.BOOL
        if not query_extended(
            handle,
            18,  # FileIdInfo
            ctypes.byref(file_id_information),
            ctypes.sizeof(file_id_information),
        ):
            raise OSError(
                ctypes.get_last_error(),
                "Windows directory guard file ID query failed",
            )
        observed_file_id = int.from_bytes(bytes(file_id_information.file_id), "little")
        volume_matches = identity[0] in {
            int(information.volume_serial_number),
            int(file_id_information.volume_serial_number),
        }
        if (
            not volume_matches
            or observed_file_id != identity[1]
            or information.file_attributes & 0x00000400
        ):
            raise OSError("Windows directory guard identity changed")
        if owner is not None:
            registered = True
            owner.append(observed_handle)
        return observed_handle
    except BaseException:
        if registered and owner is not None and observed_handle in owner:
            owner.remove(observed_handle)
        kernel32.CloseHandle(handle)
        raise


def _windows_close_directory_guard(handle: int) -> bool:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    return bool(close(wintypes.HANDLE(handle)))


def _windows_create_relative_file(
    directory_handle: int,
    leaf: str,
    *,
    owner: dict[str, int] | None = None,
) -> int:
    """Create one exclusive file relative to an already-bound directory handle."""

    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _UnicodeString(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ushort),
            ("maximum_length", ctypes.c_ushort),
            ("buffer", wintypes.LPWSTR),
        ]

    class _ObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.ULONG),
            ("root_directory", wintypes.HANDLE),
            ("object_name", ctypes.POINTER(_UnicodeString)),
            ("attributes", wintypes.ULONG),
            ("security_descriptor", wintypes.LPVOID),
            ("security_quality_of_service", wintypes.LPVOID),
        ]

    class _IoStatusValue(ctypes.Union):
        _fields_ = [("status", ctypes.c_long), ("pointer", wintypes.LPVOID)]

    class _IoStatusBlock(ctypes.Structure):
        _anonymous_ = ("value",)
        _fields_ = [("value", _IoStatusValue), ("information", ctypes.c_size_t)]

    encoded_length = len(leaf.encode("utf-16-le"))
    name_buffer = ctypes.create_unicode_buffer(leaf)
    name = _UnicodeString(
        encoded_length,
        encoded_length + 2,
        ctypes.cast(name_buffer, wintypes.LPWSTR),
    )
    attributes = _ObjectAttributes(
        ctypes.sizeof(_ObjectAttributes),
        wintypes.HANDLE(directory_handle),
        ctypes.pointer(name),
        0x00000040,  # OBJ_CASE_INSENSITIVE; casefold collisions were prechecked
        None,
        None,
    )
    io_status = _IoStatusBlock()
    raw_handle = wintypes.HANDLE()
    ntdll = ctypes.WinDLL("ntdll")
    create = ntdll.NtCreateFile
    create.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(_ObjectAttributes),
        ctypes.POINTER(_IoStatusBlock),
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    create.restype = ctypes.c_long
    descriptor: int | None = None
    try:
        status = create(
            ctypes.byref(raw_handle),
            # Exact native file rights, including DELETE for handle-relative
            # rollback.  Avoid generic access mapping and retain synchronous I/O.
            0x0013019B,
            ctypes.byref(attributes),
            ctypes.byref(io_status),
            None,
            0x00000080,  # FILE_ATTRIBUTE_NORMAL
            # Share-read only: a second writer or rename cannot enter before the
            # terminal result releases this exact handle.
            0x00000001,
            2,  # FILE_CREATE: fail if the leaf already exists
            0x00000040 | 0x00000020 | 0x00200000,
            None,
            0,
        )
        if status < 0:
            convert = ntdll.RtlNtStatusToDosError
            convert.argtypes = [ctypes.c_long]
            convert.restype = wintypes.ULONG
            code = int(convert(status))
            if code in {80, 183}:
                raise FileExistsError(17, "artifact leaf already exists")
            raise OSError(code, "Windows relative artifact creation failed")
        descriptor = msvcrt.open_osfhandle(
            int(raw_handle.value), os.O_RDWR | getattr(os, "O_BINARY", 0)
        )
        if owner is not None:
            owner[leaf] = descriptor
        return descriptor
    except BaseException:
        if descriptor is not None:
            if owner is not None:
                # Preserve the converted descriptor in the transaction ledger
                # so the constructor's outer rollback can retry disposition or
                # close failures instead of losing ownership between CALL and
                # the caller's assignment.
                owner[leaf] = descriptor
            else:
                _windows_mark_descriptor_delete(descriptor)
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        elif raw_handle.value:
            try:
                _windows_mark_raw_handle_delete(int(raw_handle.value))
            finally:
                ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(raw_handle)
        if owner is not None and descriptor is None:
            owner.pop(leaf, None)
        raise


def _windows_mark_raw_handle_delete(handle: int) -> bool:
    import ctypes
    from ctypes import wintypes

    class _Disposition(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOLEAN)]

    disposition = _Disposition(1)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = kernel32.SetFileInformationByHandle
    operation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    operation.restype = wintypes.BOOL
    return bool(
        operation(
            wintypes.HANDLE(handle),
            4,  # FileDispositionInfo
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        )
    )


def _windows_mark_descriptor_delete(descriptor: int) -> bool:
    import msvcrt

    return _windows_mark_raw_handle_delete(msvcrt.get_osfhandle(descriptor))


def _windows_mark_directory_delete(handle: int) -> bool:
    import ctypes
    from ctypes import wintypes

    class _Disposition(ctypes.Structure):
        _fields_ = [("delete_file", wintypes.BOOLEAN)]

    disposition = _Disposition(1)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = kernel32.SetFileInformationByHandle
    operation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    operation.restype = wintypes.BOOL
    return bool(
        operation(
            wintypes.HANDLE(handle),
            4,
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        )
    )


def prepare_output_run(root: Path, *, run_dir: str) -> Path:
    """Create one canonical, ignored, exclusive fixture-output directory."""

    root = root.resolve(strict=True)
    try:
        relative = portable_relative_path(
            run_dir,
            label="A/B parser run directory",
            required_prefix=OUTPUT_PREFIX,
        )
    except PortablePathError as error:
        raise ABParserError("publication", "publication-failed", str(error)) from error
    require(
        len(relative.parts) == len(OUTPUT_PREFIX) + 1
        and _SAFE_RUN_LEAF.fullmatch(relative.name) is not None,
        stage="publication",
        reason="publication-failed",
        detail="A/B parser run directory must have one canonical leaf",
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--", relative.as_posix()],
        cwd=root,
        check=False,
        capture_output=True,
    )
    require(
        ignored.returncode == 0,
        stage="publication",
        reason="publication-failed",
        detail="A/B parser output must remain ignored by Git",
    )
    current = root
    try:
        _plain_directory(current, label="repository root")
        for component in OUTPUT_PREFIX:
            collisions = [
                entry.name
                for entry in current.iterdir()
                if entry.name.casefold() == component.casefold()
            ]
            require(
                not collisions or collisions == [component],
                stage="publication",
                reason="publication-failed",
                detail="A/B parser output parent collides by case",
            )
            current = current / component
            if not current.exists():
                current.mkdir()
            _plain_directory(current, label="A/B parser output parent")
    except (OSError, SourceAuditError) as error:
        raise ABParserError(
            "publication", "publication-failed", "cannot prepare output parent"
        ) from error
    collisions = [entry.name for entry in current.iterdir() if entry.name.casefold() == relative.name.casefold()]
    require(
        not collisions,
        stage="publication",
        reason="publication-failed",
        detail="A/B parser run directory already exists or collides by case",
    )
    output = current / relative.name
    try:
        output.mkdir()
        _plain_directory(output, label="A/B parser run directory")
    except (OSError, SourceAuditError) as error:
        raise ABParserError(
            "publication", "publication-failed", "cannot create output run directory"
        ) from error
    return output


class ExactArtifactTransaction:
    """Owned create-only publication for the three synthetic fixture artifacts."""

    def __init__(
        self,
        run_dir: Path,
        leaves: Sequence[str],
        *,
        max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    ) -> None:
        self.run_dir = run_dir
        self.leaves = tuple(leaves)
        self.descriptors: dict[str, int] = {}
        self.identities: dict[str, tuple[int, int]] = {}
        self.written: dict[str, tuple[int, str]] = {}
        self.locked: dict[str, int] = {}
        self.committed = False
        self.active = True
        # These fields must exist before the first path probe.  Constructor
        # rollback is also used for a missing or malformed run directory, and
        # must not mask that original failure with partially initialized state.
        self.parent_identities: list[tuple[Path, tuple[int, int]]] = []
        self.run_identity: tuple[int, int] | None = None
        self.run_directory_descriptor: int | None = None
        self.parent_directory_descriptor: int | None = None
        self.windows_directory_guards: list[int] = []
        require(
            type(max_artifact_bytes) is int and max_artifact_bytes > 0,
            stage="publication",
            reason="publication-failed",
            detail="artifact lock ceiling is invalid",
        )
        self.max_artifact_bytes = max_artifact_bytes
        try:
            _plain_directory(run_dir, label="A/B parser run directory")
            info = run_dir.lstat()
            self.run_identity = (int(info.st_dev), int(info.st_ino))
            for parent in reversed(run_dir.parents):
                _plain_directory(parent, label="A/B parser output ancestor")
                parent_info = parent.lstat()
                self.parent_identities.append(
                    (parent, (int(parent_info.st_dev), int(parent_info.st_ino)))
                )
            if os.name == "nt":
                _windows_open_directory_guard(
                    run_dir,
                    self.run_identity,
                    owner=self.windows_directory_guards,
                )
            else:
                directory_flags = os.O_RDONLY
                directory_flags |= getattr(os, "O_DIRECTORY", 0)
                directory_flags |= getattr(os, "O_NOFOLLOW", 0)
                directory_flags |= getattr(os, "O_CLOEXEC", 0)
                self.run_directory_descriptor = os.open(run_dir, directory_flags)
                run_handle_info = os.fstat(self.run_directory_descriptor)
                require(
                    _plain_directory_identity(run_handle_info)
                    and (int(run_handle_info.st_dev), int(run_handle_info.st_ino))
                    == self.run_identity,
                    stage="publication",
                    reason="publication-failed",
                    detail="output directory handle identity changed",
                )
                self.parent_directory_descriptor = os.open(
                    run_dir.parent, directory_flags
                )
                parent_handle_info = os.fstat(self.parent_directory_descriptor)
                require(
                    self.parent_identities
                    and _plain_directory_identity(parent_handle_info)
                    and (
                        int(parent_handle_info.st_dev),
                        int(parent_handle_info.st_ino),
                    )
                    == self.parent_identities[-1][1],
                    stage="publication",
                    reason="publication-failed",
                    detail="output parent handle identity changed",
                )
            require(
                len(self.leaves) == 3
                and len(set(name.casefold() for name in self.leaves)) == 3,
                stage="publication",
                reason="publication-failed",
                detail="artifact leaf set is not exact",
            )
            for leaf in self.leaves:
                portable_relative_path(leaf, label="A/B parser artifact leaf")
                require(
                    Path(leaf).name == leaf,
                    stage="publication",
                    reason="publication-failed",
                    detail="artifact leaf must not contain a parent",
                )
                flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
                if hasattr(os, "O_BINARY"):
                    flags |= os.O_BINARY
                if os.name == "nt":
                    require(
                        len(self.windows_directory_guards) == 1,
                        stage="publication",
                        reason="publication-failed",
                        detail="Windows output directory handle is unavailable",
                    )
                    descriptor = _windows_create_relative_file(
                        self.windows_directory_guards[0],
                        leaf,
                        owner=self.descriptors,
                    )
                else:
                    require(
                        self.run_directory_descriptor is not None,
                        stage="publication",
                        reason="publication-failed",
                        detail="output directory handle is unavailable",
                    )
                    descriptor = os.open(
                        leaf,
                        flags,
                        0o600,
                        dir_fd=self.run_directory_descriptor,
                    )
                if os.name != "nt":
                    self.descriptors[leaf] = descriptor
                observed = os.fstat(descriptor)
                require(
                    _plain_file_identity(observed),
                    stage="publication",
                    reason="publication-failed",
                    detail="artifact reservation descriptor is invalid",
                )
                # Record ownership before any later path lookup or validation
                # can be interrupted, so constructor rollback can remove the
                # exact O_EXCL-created leaf without trusting its path alone.
                self.identities[leaf] = (
                    int(observed.st_dev),
                    int(observed.st_ino),
                )
                path_info = (
                    (run_dir / leaf).lstat()
                    if os.name == "nt"
                    else os.stat(
                        leaf,
                        dir_fd=self.run_directory_descriptor,
                        follow_symlinks=False,
                    )
                )
                require(
                    _plain_file_identity(path_info)
                    and (int(observed.st_dev), int(observed.st_ino))
                    == (int(path_info.st_dev), int(path_info.st_ino)),
                    stage="publication",
                    reason="publication-failed",
                    detail="artifact reservation identity is invalid",
                )
        except BaseException as error:
            if self.descriptors or self.identities:
                self.rollback()
            else:
                self.active = not self._close_directory_descriptors()
            if isinstance(
                error, (ABParserError, FileExistsError, KeyboardInterrupt, SystemExit)
            ):
                raise
            raise ABParserError(
                "publication", "publication-failed", "artifact reservation failed"
            ) from error

    @staticmethod
    def _require_exact_entry(path: Path) -> None:
        if path.parent == path:
            return
        try:
            matches = [
                entry.name
                for entry in path.parent.iterdir()
                if entry.name.casefold() == path.name.casefold()
            ]
        except OSError as error:
            raise ABParserError(
                "publication", "publication-failed", "output path spelling changed"
            ) from error
        require(
            matches == [path.name],
            stage="publication",
            reason="publication-failed",
            detail="output path spelling changed",
        )

    def _require_directory_owned(self) -> None:
        for parent, identity in self.parent_identities:
            self._require_exact_entry(parent)
            try:
                _plain_directory(parent, label="A/B parser output ancestor")
                parent_info = parent.lstat()
            except (OSError, SourceAuditError) as error:
                raise ABParserError(
                    "publication", "publication-failed", "output ancestor identity changed"
                ) from error
            require(
                (int(parent_info.st_dev), int(parent_info.st_ino)) == identity,
                stage="publication",
                reason="publication-failed",
                detail="output ancestor identity changed",
            )
        self._require_exact_entry(self.run_dir)
        try:
            _plain_directory(self.run_dir, label="A/B parser run directory")
            info = self.run_dir.lstat()
        except (OSError, SourceAuditError) as error:
            raise ABParserError(
                "publication", "publication-failed", "output directory identity changed"
            ) from error
        require(
            (int(info.st_dev), int(info.st_ino)) == self.run_identity,
            stage="publication",
            reason="publication-failed",
            detail="output directory identity changed",
        )

    @staticmethod
    def _identity_child(
        parent: Path,
        identity: tuple[int, int],
        *,
        directory: bool,
    ) -> tuple[Path | None, bool]:
        """Resolve one identity below a proven parent without trusting spelling."""

        try:
            entries = list(parent.iterdir())
        except OSError:
            return None, False
        matches: list[Path] = []
        for entry in entries:
            try:
                info = entry.lstat()
            except OSError:
                return None, False
            if (int(info.st_dev), int(info.st_ino)) != identity:
                continue
            valid = (
                _plain_directory_identity(info)
                if directory
                else _plain_file_identity(info)
            )
            if not valid:
                return None, False
            matches.append(entry)
        if len(matches) > 1:
            return None, False
        return (matches[0] if matches else None), True

    def _resolve_owned_run_directory(self) -> tuple[Path | None, bool]:
        """Follow captured directory identities through same-parent renames."""

        if not self.parent_identities or self.run_identity is None:
            return None, False
        anchor, anchor_identity = self.parent_identities[0]
        try:
            info = anchor.lstat()
        except OSError:
            return None, False
        if not _plain_directory_identity(info) or (
            int(info.st_dev),
            int(info.st_ino),
        ) != anchor_identity:
            return None, False
        actual_parent = anchor
        for _expected_path, identity in self.parent_identities[1:]:
            actual_parent, certain = self._identity_child(
                actual_parent, identity, directory=True
            )
            if not certain or actual_parent is None:
                return None, False
        run_path, certain = self._identity_child(
            actual_parent, self.run_identity, directory=True
        )
        if not certain or run_path is None:
            # Absence at the original parent cannot distinguish deletion from
            # a cross-parent rename. Retain retryable ownership rather than
            # falsely certifying cleanup.
            return None, False
        return run_path, True

    def _require_owned(self, leaf: str) -> tuple[int, os.stat_result]:
        self._require_directory_owned()
        descriptor = self.descriptors.get(leaf)
        require(
            descriptor is not None,
            stage="publication",
            reason="publication-failed",
            detail="artifact reservation is unavailable",
        )
        try:
            handle_info = os.fstat(descriptor)
            path_info = (self.run_dir / leaf).lstat()
        except OSError as error:
            raise ABParserError(
                "publication", "publication-failed", "artifact reservation changed"
            ) from error
        require(
            _plain_file_identity(handle_info)
            and _plain_file_identity(path_info)
            and (int(handle_info.st_dev), int(handle_info.st_ino))
            == self.identities[leaf]
            == (int(path_info.st_dev), int(path_info.st_ino)),
            stage="publication",
            reason="publication-failed",
            detail="artifact reservation identity changed",
        )
        return descriptor, handle_info

    def write(self, leaf: str, payload: bytes) -> None:
        require(
            self.active
            and leaf in self.leaves
            and leaf not in self.written
            and len(payload) <= self.max_artifact_bytes,
            stage="publication",
            reason="publication-failed",
            detail="artifact write order or identity is invalid",
        )
        descriptor, _ = self._require_owned(leaf)
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            total = 0
            while total < len(payload):
                written = os.write(descriptor, payload[total:])
                if written <= 0:
                    raise OSError("short artifact write")
                total += written
            os.ftruncate(descriptor, len(payload))
            os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            observed = bytearray()
            while len(observed) < len(payload):
                chunk = os.read(descriptor, len(payload) - len(observed))
                if not chunk:
                    break
                observed.extend(chunk)
        except OSError as error:
            raise ABParserError(
                "publication", "publication-failed", "artifact write failed"
            ) from error
        require(
            bytes(observed) == payload,
            stage="publication",
            reason="publication-failed",
            detail="artifact bytes changed during write",
        )
        self._require_owned(leaf)
        self.written[leaf] = (len(payload), sha256_bytes(payload))

    def _lock(self, leaf: str) -> None:
        descriptor, _ = self._require_owned(leaf)
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                _windows_lock_descriptor(descriptor, unlock=False)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError) as error:
            raise ABParserError(
                "publication", "publication-failed", "artifact lock failed"
            ) from error
        self.locked[leaf] = 1

    def _unlock(self, leaf: str) -> bool:
        descriptor = self.descriptors.get(leaf)
        lock_state = self.locked.get(leaf)
        if descriptor is None or lock_state is None:
            return True
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                _windows_lock_descriptor(descriptor, unlock=True)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        except (OSError, ImportError):
            return False
        del self.locked[leaf]
        return True

    def publish(self, artifacts: Mapping[str, bytes]) -> dict[str, dict[str, Any]]:
        require(
            self.active and set(artifacts) == set(self.leaves),
            stage="publication",
            reason="publication-failed",
            detail="artifact publication set is not exact",
        )
        try:
            for leaf in self.leaves:
                self.write(leaf, artifacts[leaf])
            for leaf in self.leaves:
                self._lock(leaf)
            self._require_directory_owned()
            require(
                {entry.name for entry in self.run_dir.iterdir()} == set(self.leaves),
                stage="publication",
                reason="publication-failed",
                detail="output directory set is not exact",
            )
            observations: dict[str, tuple[int, int, int, int, int, int]] = {}
            for leaf in self.leaves:
                expected_size, expected_hash = self.written[leaf]
                descriptor, _ = self._require_owned(leaf)
                try:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    observed = bytearray()
                    while len(observed) <= expected_size:
                        chunk = os.read(
                            descriptor, min(1024 * 1024, expected_size + 1 - len(observed))
                        )
                        if not chunk:
                            break
                        observed.extend(chunk)
                    info = os.fstat(descriptor)
                except OSError as error:
                    raise ABParserError(
                        "publication", "publication-failed", "artifact verification failed"
                    ) from error
                require(
                    len(observed) == expected_size
                    and sha256_bytes(bytes(observed)) == expected_hash,
                    stage="publication",
                    reason="publication-failed",
                    detail="published artifact bytes changed before commit",
                )
                observations[leaf] = (
                    int(info.st_dev),
                    int(info.st_ino),
                    int(info.st_size),
                    int(info.st_mtime_ns),
                    _descriptor_change_token(descriptor, info),
                    int(info.st_nlink),
                )
            # Commit point: after every payload hash is known, re-check every
            # held descriptor/path and the whole directory set. A modification
            # or hardlink introduced while a later leaf was hashed changes this
            # terminal identity pass and fails closed.
            self._require_directory_owned()
            require(
                {entry.name for entry in self.run_dir.iterdir()} == set(self.leaves),
                stage="publication",
                reason="publication-failed",
                detail="published output directory set changed",
            )
            for leaf in self.leaves:
                descriptor, info = self._require_owned(leaf)
                require(
                    (
                        int(info.st_dev),
                        int(info.st_ino),
                        int(info.st_size),
                        int(info.st_mtime_ns),
                        _descriptor_change_token(descriptor, info),
                        int(info.st_nlink),
                    )
                    == observations[leaf],
                    stage="publication",
                    reason="publication-failed",
                    detail="published artifact identity changed during final verification",
                )
        except BaseException:
            self.rollback()
            raise
        self.active = False
        self.committed = True
        return {
            leaf: {
                "file": leaf,
                "size_bytes": self.written[leaf][0],
                "sha256": self.written[leaf][1],
            }
            for leaf in self.leaves
        }

    def release_committed(self) -> bool:
        """Release commit locks after the terminal result has been delivered."""

        if not self.committed:
            return not self.descriptors and self._close_directory_descriptors()
        success = True
        for leaf in list(self.descriptors):
            if not self._unlock(leaf):
                success = False
                continue
            descriptor = self.descriptors[leaf]
            try:
                os.close(descriptor)
            except OSError:
                success = False
                continue
            del self.descriptors[leaf]
        directories_closed = self._close_directory_descriptors()
        return success and not self.descriptors and directories_closed

    def _close_directory_descriptors(self) -> bool:
        success = True
        for attribute in (
            "run_directory_descriptor",
            "parent_directory_descriptor",
        ):
            descriptor = getattr(self, attribute)
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError:
                success = False
                continue
            setattr(self, attribute, None)
        return self._close_windows_directory_guards() and success

    def _close_windows_directory_guards(self) -> bool:
        success = True
        remaining: list[int] = []
        for handle in self.windows_directory_guards:
            if not _windows_close_directory_guard(handle):
                success = False
                remaining.append(handle)
        self.windows_directory_guards = remaining
        return success

    @staticmethod
    def _directory_entries_by_descriptor(
        descriptor: int,
    ) -> dict[str, os.stat_result]:
        entries: dict[str, os.stat_result] = {}
        for name in os.listdir(descriptor):
            require(
                type(name) is str and name not in {"", ".", ".."},
                stage="publication",
                reason="publication-failed",
                detail="output directory entry is invalid",
            )
            try:
                entries[name] = os.stat(
                    name, dir_fd=descriptor, follow_symlinks=False
                )
            except OSError as error:
                raise ABParserError(
                    "publication",
                    "publication-failed",
                    "output directory entry changed during cleanup",
                ) from error
        return entries

    def _resolve_posix_run_name(self) -> str | None:
        run_descriptor = self.run_directory_descriptor
        parent_descriptor = self.parent_directory_descriptor
        if (
            run_descriptor is None
            or parent_descriptor is None
            or self.run_identity is None
            or not self.parent_identities
        ):
            return None
        try:
            run_info = os.fstat(run_descriptor)
            parent_info = os.fstat(parent_descriptor)
        except OSError:
            return None
        if (
            not _plain_directory_identity(run_info)
            or (int(run_info.st_dev), int(run_info.st_ino)) != self.run_identity
            or not _plain_directory_identity(parent_info)
            or (int(parent_info.st_dev), int(parent_info.st_ino))
            != self.parent_identities[-1][1]
        ):
            return None
        try:
            entries = self._directory_entries_by_descriptor(parent_descriptor)
        except ABParserError:
            return None
        matches = [
            name
            for name, info in entries.items()
            if _plain_directory_identity(info)
            and (int(info.st_dev), int(info.st_ino)) == self.run_identity
        ]
        return matches[0] if len(matches) == 1 else None

    def _rollback_posix(self) -> None:
        """Clean through held directory/file descriptors, or retain ownership."""

        run_descriptor = self.run_directory_descriptor
        parent_descriptor = self.parent_directory_descriptor
        run_name = self._resolve_posix_run_name()
        if run_descriptor is None or parent_descriptor is None or run_name is None:
            self.active = bool(
                self.descriptors
                or self.identities
                or run_descriptor is not None
                or parent_descriptor is not None
            )
            return
        try:
            entries = self._directory_entries_by_descriptor(run_descriptor)
        except ABParserError:
            self.active = True
            return

        # Establish the entire cleanup set before deleting anything. Missing
        # names with a still-linked descriptor prove a cross-parent move or
        # alias; extra names are foreign. Either condition retains every
        # descriptor for an explicit retry rather than partially cleaning.
        cleanup_names: dict[str, str | None] = {}
        owned_entry_names: set[str] = set()
        for leaf, identity in self.identities.items():
            descriptor = self.descriptors.get(leaf)
            if descriptor is None:
                self.active = True
                return
            try:
                handle_info = os.fstat(descriptor)
            except OSError:
                self.active = True
                return
            if (
                not stat.S_ISREG(handle_info.st_mode)
                or (int(handle_info.st_dev), int(handle_info.st_ino)) != identity
                or int(getattr(handle_info, "st_file_attributes", 0))
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            ):
                self.active = True
                return
            matches = [
                name
                for name, info in entries.items()
                if _plain_file_identity(info)
                and (int(info.st_dev), int(info.st_ino)) == identity
            ]
            link_count = int(handle_info.st_nlink)
            if link_count == 0 and not matches:
                cleanup_names[leaf] = None
            elif link_count == 1 and len(matches) == 1:
                cleanup_names[leaf] = matches[0]
                owned_entry_names.add(matches[0])
            else:
                self.active = True
                return
        if set(entries) != owned_entry_names:
            self.active = True
            return

        for leaf in tuple(self.identities):
            descriptor = self.descriptors[leaf]
            name = cleanup_names[leaf]
            if name is not None:
                try:
                    handle_before = os.fstat(descriptor)
                    path_before = os.stat(
                        name, dir_fd=run_descriptor, follow_symlinks=False
                    )
                except OSError:
                    self.active = True
                    return
                identity = self.identities[leaf]
                if (
                    not _plain_file_identity(handle_before)
                    or not _plain_file_identity(path_before)
                    or (int(handle_before.st_dev), int(handle_before.st_ino))
                    != identity
                    or (int(path_before.st_dev), int(path_before.st_ino))
                    != identity
                ):
                    self.active = True
                    return
                try:
                    os.unlink(name, dir_fd=run_descriptor)
                    handle_after = os.fstat(descriptor)
                except OSError:
                    self.active = True
                    return
                if (
                    not stat.S_ISREG(handle_after.st_mode)
                    or (int(handle_after.st_dev), int(handle_after.st_ino))
                    != identity
                    or int(handle_after.st_nlink) != 0
                ):
                    self.active = True
                    return
            self._unlock(leaf)
            try:
                os.close(descriptor)
            except OSError:
                self.active = True
                return
            del self.descriptors[leaf]
            del self.identities[leaf]

        try:
            if os.listdir(run_descriptor):
                self.active = True
                return
            current = os.stat(
                run_name, dir_fd=parent_descriptor, follow_symlinks=False
            )
            if (
                not _plain_directory_identity(current)
                or (int(current.st_dev), int(current.st_ino)) != self.run_identity
            ):
                self.active = True
                return
            os.rmdir(run_name, dir_fd=parent_descriptor)
        except OSError:
            self.active = True
            return
        self.active = not self._close_directory_descriptors()

    def _rollback_windows(self) -> None:
        """Delete exact owned Windows objects through their retained handles."""

        if len(self.windows_directory_guards) != 1:
            self.active = True
            return
        for leaf in tuple(self.identities):
            descriptor = self.descriptors.get(leaf)
            if descriptor is None:
                self.active = True
                return
            try:
                info = os.fstat(descriptor)
            except OSError:
                self.active = True
                return
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            link_count = int(info.st_nlink)
            if (
                not stat.S_ISREG(info.st_mode)
                or int(getattr(info, "st_file_attributes", 0)) & reparse_flag
                or (int(info.st_dev), int(info.st_ino)) != self.identities[leaf]
                or link_count not in {0, 1}
            ):
                self.active = True
                return
            # A previous rollback may already have marked this exact handle
            # delete-pending and then hit a transient close failure.  Windows
            # reports that still-open owned inode with a zero link count; do
            # not require a second disposition operation before retrying the
            # close.
            if link_count == 1 and not _windows_mark_descriptor_delete(descriptor):
                self.active = True
                return
            try:
                os.close(descriptor)
            except OSError:
                self.active = True
                return
            del self.descriptors[leaf]
            del self.identities[leaf]
        if self.descriptors or self.identities:
            self.active = True
            return
        run_handle = self.windows_directory_guards[0]
        if not _windows_mark_directory_delete(run_handle):
            self.active = True
            return
        if not _windows_close_directory_guard(run_handle):
            self.active = True
            return
        self.windows_directory_guards.clear()
        self.active = False

    def rollback(self) -> None:
        if not self.active:
            return
        if (
            self.run_identity is None
            and not self.parent_identities
            and not self.descriptors
            and not self.identities
        ):
            self.active = False
            return
        for leaf in list(self.descriptors):
            self._unlock(leaf)
        # An interrupt may arrive immediately after O_EXCL creation, before
        # constructor validation recorded the identity. Recover it from the
        # still-held descriptor; never infer ownership from the pathname.
        for leaf, descriptor in list(self.descriptors.items()):
            if leaf in self.identities:
                continue
            try:
                info = os.fstat(descriptor)
                if _plain_file_identity(info):
                    self.identities[leaf] = (
                        int(info.st_dev),
                        int(info.st_ino),
                    )
            except BaseException:
                continue
        if os.name == "nt" and self.windows_directory_guards:
            self._rollback_windows()
            return
        if os.name != "nt" and (
            self.run_directory_descriptor is not None
            or self.parent_directory_descriptor is not None
        ):
            self._rollback_posix()
            return
        for leaf, descriptor in list(self.descriptors.items()):
            try:
                os.close(descriptor)
            except OSError:
                continue
            del self.descriptors[leaf]
        run_path, certain = self._resolve_owned_run_directory()
        cleanup_uncertain = not certain
        owned_remains = bool(self.descriptors)
        if run_path is not None:
            for leaf, identity in self.identities.items():
                if leaf in self.descriptors:
                    owned_remains = True
                    continue
                path, resolved = self._identity_child(
                    run_path, identity, directory=False
                )
                if not resolved:
                    cleanup_uncertain = True
                    owned_remains = True
                    continue
                if path is None:
                    continue
                try:
                    path.unlink()
                except OSError:
                    cleanup_uncertain = True
                    owned_remains = True
            for identity in self.identities.values():
                path, resolved = self._identity_child(
                    run_path, identity, directory=False
                )
                if not resolved:
                    cleanup_uncertain = True
                    owned_remains = True
                elif path is not None:
                    owned_remains = True
            if not self.descriptors and not owned_remains:
                try:
                    if any(run_path.iterdir()):
                        cleanup_uncertain = True
                    else:
                        run_path.rmdir()
                except OSError:
                    cleanup_uncertain = True
        directories_closed = False
        if not self.descriptors and not owned_remains and not cleanup_uncertain:
            directories_closed = self._close_directory_descriptors()
        self.active = (
            bool(self.descriptors)
            or owned_remains
            or cleanup_uncertain
            or not directories_closed
        )
