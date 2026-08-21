from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import chronopersona.ab_parser_sample as gate
from chronopersona.ab_parser_common import ABParserError, canonical_jsonl_bytes
from chronopersona.source_audit import canonical_json_bytes


ROOT = Path(__file__).resolve().parents[1]


def _bound() -> gate.BoundABInputs:
    profile = deepcopy(gate.load_profile_for_plan(ROOT))
    payloads = {
        label: (ROOT / record["path"]).read_bytes()
        for label, record in profile["fixture_bundle"]["files"].items()
    }
    bindings = {
        "bundle_sha256": gate.fixture_bundle_sha256(profile),
        "profile": {
            "path": gate.PROFILE_RELATIVE_PATH,
            "git_blob": gate.FROZEN_PROFILE_GIT_BLOB,
            "raw_sha256": "a" * 64,
            "size_bytes": 1,
            "canonical_sha256": gate.FROZEN_PROFILE_CANONICAL_SHA256,
        },
        "governance": {
            "decision": {
                "path": "docs/DECISIONS.md",
                "e0_git_blob": "b" * 40,
            },
            "plan": {
                "path": ".agent/plans/active-ab-parser-sample-engineering.md",
                "e0_git_blob": "c" * 40,
            },
        },
        "fixtures": {
            label: {
                "path": record["path"],
                "git_blob": record["git_blob"],
                "raw_sha256": record["raw_sha256"],
                "size_bytes": len(payloads[label]),
            }
            for label, record in profile["fixture_bundle"]["files"].items()
        },
        "runtime": [],
        "eol_policy": {
            "path": ".gitattributes",
            "git_blob": "d" * 40,
            "raw_sha256": "e" * 64,
            "size_bytes": 1,
        },
    }
    return gate.BoundABInputs(
        head="f" * 40,
        bindings=bindings,
        payloads=payloads,
        profile=profile,
    )


def _success():
    bound = _bound()
    parsed = gate.parse_fixture_bundle(bound)
    artifacts = gate.build_success_artifacts(bound, parsed)
    aggregate = json.loads(artifacts["aggregate.json"])
    receipt = json.loads(artifacts["receipt.json"])
    return bound, parsed, artifacts, aggregate, receipt


def test_profile_is_exact_and_fixture_identities_match() -> None:
    profile = gate.load_profile_for_plan(ROOT)
    assert gate.canonical_json_sha256(profile) == gate.FROZEN_PROFILE_CANONICAL_SHA256
    assert profile["canonical_inputs"]["e0_commit"] == gate.E0_COMMIT
    assert profile["canonical_inputs"]["baseline_commit"] == gate.BASELINE_COMMIT
    for label in profile["fixture_bundle"]["file_order"]:
        record = profile["fixture_bundle"]["files"][label]
        payload = (ROOT / record["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == record["raw_sha256"]


def test_bound_eol_policy_file_self_pins_portable_lf() -> None:
    observed = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", ".gitattributes"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert observed == [
        ".gitattributes: text: set",
        ".gitattributes: eol: lf",
    ]


def test_fixture_bundle_runs_in_frozen_order_and_is_deterministic() -> None:
    first = _success()
    second = _success()
    bound, parsed, artifacts, aggregate, receipt = first
    assert [record["selection_id"] for record in parsed.records] == bound.profile[
        "fixture_bundle"
    ]["selection_order"]
    assert parsed.diagnostics == {
        "mediawiki_pages": 2,
        "mediawiki_revisions": 6,
        "posts_rows": 4,
        "posthistory_rows": 14,
    }
    assert artifacts == second[2]
    assert aggregate["summary"]["selection_count"] == 6
    assert aggregate["summary"]["disposition_counts"] == {
        "accepted-for-parser-audit": 6
    }
    assert receipt["status"] == "complete"
    assert all(value is False for value in aggregate["boundaries"].values())


def test_combined_cross_source_parsed_object_ceiling_is_enforced(monkeypatch) -> None:
    bound = _bound()
    from chronopersona import stackexchange_ab_parser, wikimedia_ab_parser

    original_wikimedia = wikimedia_ab_parser.parse_wikimedia_fixture
    original_stack = stackexchange_ab_parser.parse_stackexchange_fixture

    def oversized_wikimedia(*args, **kwargs):
        records, counts = original_wikimedia(*args, **kwargs)
        return records, {**counts, "revisions": 17}

    def oversized_stack(*args, **kwargs):
        records, counts = original_stack(*args, **kwargs)
        return records, {**counts, "posts_rows": 16, "posthistory_rows": 32}

    monkeypatch.setattr(
        wikimedia_ab_parser, "parse_wikimedia_fixture", oversized_wikimedia
    )
    monkeypatch.setattr(
        stackexchange_ab_parser, "parse_stackexchange_fixture", oversized_stack
    )
    with pytest.raises(ABParserError):
        gate.parse_fixture_bundle(bound)


def test_success_artifacts_pass_top_level_pair_validation() -> None:
    bound, _parsed, artifacts, aggregate, receipt = _success()
    private_records, private_errors = gate.validate_private_jsonl(
        artifacts["private-records.jsonl"], bound
    )
    assert len(private_records) == 6
    assert private_errors == ()
    assert gate.validate_aggregate(
        aggregate,
        bound=bound,
        private_payload=artifacts["private-records.jsonl"],
    ) == ()
    assert gate.validate_receipt(
        receipt,
        bound=bound,
        receipt_payload=artifacts["receipt.json"],
        aggregate_payload=artifacts["aggregate.json"],
        private_payload=artifacts["private-records.jsonl"],
    ) == ()


@pytest.mark.parametrize(
    ("target", "mutation"),
    [
        ("aggregate", lambda value: value["execution"].__setitem__("git_head", "0" * 40)),
        ("aggregate", lambda value: value["summary"].__setitem__("token_count", 999)),
        ("aggregate", lambda value: value["groups"][0].__setitem__("raw_bytes", 999)),
        ("receipt", lambda value: value["runtime_identity"].__setitem__("python_version", "99.0.0")),
        ("receipt", lambda value: value["artifacts"]["aggregate"].__setitem__("sha256", "0" * 64)),
        ("receipt", lambda value: value.__setitem__("final_binding_status", "failed")),
    ],
)
def test_rehashed_portable_evidence_mutations_are_rejected(target, mutation) -> None:
    bound, _parsed, artifacts, aggregate, receipt = _success()
    if target == "aggregate":
        value = deepcopy(aggregate)
        mutation(value)
        value.pop("output_sha256")
        value["output_sha256"] = gate.canonical_json_sha256(value)
        assert gate.validate_aggregate(
            value,
            bound=bound,
            private_payload=artifacts["private-records.jsonl"],
        )
    else:
        value = deepcopy(receipt)
        mutation(value)
        value.pop("receipt_sha256")
        value["receipt_sha256"] = gate.canonical_json_sha256(value)
        assert gate.validate_receipt(
            value,
            bound=bound,
            receipt_payload=canonical_json_bytes(value, pretty=True),
            aggregate_payload=artifacts["aggregate.json"],
            private_payload=artifacts["private-records.jsonl"],
        )


def test_private_record_hash_or_field_injection_is_rejected() -> None:
    bound, parsed, _artifacts, _aggregate, _receipt = _success()
    records = deepcopy(list(parsed.records))
    records[0]["raw"]["child_sha256"] = "0" * 64
    assert gate.validate_private_records(records, bound)


def test_private_bool_alias_and_noncanonical_jsonl_delimiters_are_rejected() -> None:
    bound, parsed, artifacts, _aggregate, _receipt = _success()
    records = deepcopy(list(parsed.records))
    records[0]["schema_version"] = True
    assert gate.validate_private_records(records, bound)
    private_payload = artifacts["private-records.jsonl"]
    for mutated in (
        private_payload.replace(b"\n", b"\r\n"),
        private_payload.replace(b"\n", b"\r"),
        private_payload + b"\n",
    ):
        _records, errors = gate.validate_private_jsonl(mutated, bound)
        assert errors


def test_coherent_count_identity_and_padded_artifact_forgeries_are_rejected() -> None:
    bound, parsed, artifacts, _aggregate, receipt = _success()
    forged = gate.ParsedABBundle(
        records=parsed.records,
        diagnostics={key: 999999 for key in parsed.diagnostics},
    )
    with pytest.raises(ABParserError):
        gate.build_success_artifacts(bound, forged)
    for index, path in ((0, ("page", "page_id")), (2, ("post", "post_id")), (2, ("initial_action", "revision_guid"))):
        records = deepcopy(list(parsed.records))
        records[index][path[0]][path[1]] = "999999"
        assert gate.validate_private_records(records, bound)
    padded = b" " * (bound.profile["limits"]["max_aggregate_output_bytes"] + 1)
    assert gate.validate_receipt(
        receipt,
        bound=bound,
        receipt_payload=artifacts["receipt.json"],
        aggregate_payload=padded,
        private_payload=artifacts["private-records.jsonl"],
    )
    records = deepcopy(list(parsed.records))
    records[2]["initial_action"]["title_raw"] = "leaked prose"
    assert gate.validate_private_records(records, bound)


def test_public_validators_reject_prose_identity_and_locator_fields() -> None:
    bound, _parsed, artifacts, aggregate, _receipt = _success()
    for key, value in (
        ("title", "private fixture title"),
        ("post_id", "3001"),
        ("url", "https://example.invalid"),
    ):
        mutated = deepcopy(aggregate)
        mutated["summary"][key] = value
        mutated.pop("output_sha256")
        mutated["output_sha256"] = gate.canonical_json_sha256(mutated)
        assert gate.validate_aggregate(
            mutated,
            bound=bound,
            private_payload=artifacts["private-records.jsonl"],
        )


def test_failed_evidence_is_closed_empty_and_coherent() -> None:
    bound = _bound()
    artifacts = gate.build_failure_artifacts(
        bound,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
    )
    aggregate = json.loads(artifacts["aggregate.json"])
    receipt = json.loads(artifacts["receipt.json"])
    assert artifacts["private-records.jsonl"] == b""
    assert aggregate["status"] == "failed"
    assert aggregate["summary"]["selection_count"] == 0
    assert receipt["failure"] == {
        "stage": "parse-wikimedia",
        "reason": "parser-contract-failed",
    }
    assert gate.validate_receipt(
        receipt,
        bound=bound,
        receipt_payload=artifacts["receipt.json"],
        aggregate_payload=artifacts["aggregate.json"],
        private_payload=b"",
    ) == ()


@pytest.mark.parametrize(
    ("stage", "reason"),
    [
        ("arguments", "publication-failed"),
        ("binding", "parser-contract-failed"),
        ("publication", "argument-contract-failed"),
    ],
)
def test_impossible_failure_stage_reason_pairs_cannot_be_published(stage, reason) -> None:
    with pytest.raises(ABParserError):
        gate.build_failure_artifacts(_bound(), stage=stage, reason=reason)


def test_exact_artifact_transaction_is_create_only_and_rechecks_bytes(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    artifacts = {leaf: f"{leaf}\n".encode() for leaf in leaves}
    published = transaction.publish(artifacts)
    assert set(published) == set(leaves)
    assert {path.name for path in run_dir.iterdir()} == set(leaves)
    assert transaction.release_committed() is True
    with pytest.raises(FileExistsError):
        gate.ExactArtifactTransaction(run_dir, leaves)


def test_exact_artifact_transaction_commit_survives_later_rollback(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    artifacts = {leaf: f"{leaf}\n".encode() for leaf in leaves}
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    transaction.publish(artifacts)
    transaction.rollback()
    assert transaction.release_committed() is True
    assert {leaf: (run_dir / leaf).read_bytes() for leaf in leaves} == artifacts


def test_exact_artifact_constructor_missing_run_is_closed_publication_failure(
    tmp_path,
) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(ABParserError) as captured:
        gate.ExactArtifactTransaction(missing, ("a", "b", "c"))
    assert captured.value.stage == "publication"
    assert captured.value.reason == "publication-failed"
    assert not missing.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows mandatory range-lock contract")
def test_committed_locks_block_append_and_sparse_write_until_release(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    artifacts = {leaf: f"{leaf}\n".encode() for leaf in leaves}
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    transaction.publish(artifacts)
    target = run_dir / leaves[0]
    child = (
        "import os,sys\n"
        "try:\n"
        " f=open(sys.argv[1],'r+b',buffering=0)\n"
        " f.seek(int(sys.argv[2])); f.write(b'X'); f.close()\n"
        "except OSError:\n"
        " raise SystemExit(0)\n"
        "raise SystemExit(1)\n"
    )
    for offset in (
        len(artifacts[leaves[0]]),
        gate.DEFAULT_MAX_ARTIFACT_BYTES + 1,
        1 << 40,
    ):
        attempted = subprocess.run(
            [sys.executable, "-I", "-S", "-c", child, str(target), str(offset)],
            check=False,
            capture_output=True,
        )
        assert attempted.returncode == 0
    assert transaction.release_committed() is True
    assert target.read_bytes() == artifacts[leaves[0]]


@pytest.mark.parametrize("failure_ordinal", [1, 2, 3])
def test_exact_artifact_constructor_interrupt_rolls_back_every_reservation(
    tmp_path, monkeypatch, failure_ordinal
) -> None:
    run_dir = tmp_path / f"run-{failure_ordinal}"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    original_open = gate.os.open
    original_windows_create = gate._windows_create_relative_file
    calls = 0

    def interrupting_open(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == failure_ordinal:
            raise KeyboardInterrupt
        return original_open(*args, **kwargs)

    def interrupting_windows_create(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == failure_ordinal:
            raise KeyboardInterrupt
        return original_windows_create(*args, **kwargs)

    if os.name == "nt":
        monkeypatch.setattr(
            gate, "_windows_create_relative_file", interrupting_windows_create
        )
    else:
        monkeypatch.setattr(gate.os, "open", interrupting_open)
    with pytest.raises(KeyboardInterrupt):
        gate.ExactArtifactTransaction(run_dir, leaves)
    assert not run_dir.exists() or not any(run_dir.iterdir())


@pytest.mark.parametrize("failure_point", ["fstat", "lstat", "predicate"])
def test_exact_artifact_constructor_post_open_interrupt_cleans_reservation(
    tmp_path, monkeypatch, failure_point
) -> None:
    run_dir = tmp_path / f"run-{failure_point}"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    original_fstat = gate.os.fstat
    original_stat = gate.os.stat
    original_lstat = gate.Path.lstat
    original_predicate = gate._plain_file_identity
    injected = False

    def interrupting_fstat(descriptor):
        nonlocal injected
        if failure_point == "fstat" and not injected:
            injected = True
            raise KeyboardInterrupt
        return original_fstat(descriptor)

    def interrupting_lstat(path):
        nonlocal injected
        if failure_point == "lstat" and path.name == leaves[0] and not injected:
            injected = True
            raise KeyboardInterrupt
        return original_lstat(path)

    def interrupting_stat(path, *args, **kwargs):
        nonlocal injected
        if (
            failure_point == "lstat"
            and path == leaves[0]
            and kwargs.get("dir_fd") is not None
            and kwargs.get("follow_symlinks") is False
            and not injected
        ):
            injected = True
            raise KeyboardInterrupt
        return original_stat(path, *args, **kwargs)

    def interrupting_predicate(info):
        nonlocal injected
        if failure_point == "predicate" and not injected:
            injected = True
            raise KeyboardInterrupt
        return original_predicate(info)

    monkeypatch.setattr(gate.os, "fstat", interrupting_fstat)
    monkeypatch.setattr(gate.os, "stat", interrupting_stat)
    monkeypatch.setattr(gate.Path, "lstat", interrupting_lstat)
    monkeypatch.setattr(gate, "_plain_file_identity", interrupting_predicate)
    with pytest.raises(KeyboardInterrupt):
        gate.ExactArtifactTransaction(run_dir, leaves)
    assert injected
    assert not run_dir.exists() or not any(run_dir.iterdir())


@pytest.mark.skipif(os.name != "nt", reason="Windows handle-relative namespace contract")
def test_windows_transaction_handles_block_run_and_leaf_rename(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)

    with pytest.raises(OSError):
        run_dir.rename(tmp_path / "moved-run")
    with pytest.raises(OSError):
        (run_dir / leaves[0]).rename(run_dir / "PRIVATE-RECORDS.JSONL")

    transaction.rollback()
    assert transaction.active is False
    assert not run_dir.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle registration contract")
def test_windows_relative_create_interrupt_after_crt_conversion_removes_leaf(
    tmp_path, monkeypatch
) -> None:
    import msvcrt

    run_dir = tmp_path / "run-convert-interrupt"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    original = msvcrt.open_osfhandle
    converted: list[int] = []

    def convert_then_interrupt(handle, flags):
        descriptor = original(handle, flags)
        converted.append(descriptor)
        raise KeyboardInterrupt

    monkeypatch.setattr(msvcrt, "open_osfhandle", convert_then_interrupt)
    with pytest.raises(KeyboardInterrupt):
        gate.ExactArtifactTransaction(run_dir, leaves)
    assert not any(run_dir.iterdir())
    # The helper already closed the transferred native HANDLE. Clear the
    # deliberately stranded CRT table slot created by this injected boundary.
    for descriptor in converted:
        try:
            os.close(descriptor)
        except OSError:
            pass


@pytest.mark.skipif(os.name != "nt", reason="Windows guard registration contract")
def test_windows_guard_interrupt_after_registration_closes_handle(
    tmp_path, monkeypatch
) -> None:
    run_dir = tmp_path / "run-guard-interrupt"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    original = gate._windows_open_directory_guard

    def register_then_interrupt(*args, **kwargs):
        original(*args, **kwargs)
        raise KeyboardInterrupt

    monkeypatch.setattr(gate, "_windows_open_directory_guard", register_then_interrupt)
    with pytest.raises(KeyboardInterrupt):
        gate.ExactArtifactTransaction(run_dir, leaves)
    assert not any(run_dir.iterdir())
    moved = tmp_path / "guard-released"
    run_dir.rename(moved)
    moved.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows guard append boundary")
def test_windows_guard_interrupt_inside_owner_append_removes_stale_handle(
    tmp_path,
) -> None:
    run_dir = tmp_path / "run-guard-append"
    run_dir.mkdir()
    info = run_dir.lstat()

    class InterruptAfterAppend(list[int]):
        def append(self, value):
            super().append(value)
            raise KeyboardInterrupt

    owner = InterruptAfterAppend()
    with pytest.raises(KeyboardInterrupt):
        gate._windows_open_directory_guard(
            run_dir,
            (int(info.st_dev), int(info.st_ino)),
            owner=owner,
        )
    assert owner == []
    moved = tmp_path / "append-guard-released"
    run_dir.rename(moved)
    moved.rmdir()


@pytest.mark.parametrize("failure_ordinal", [1, 2, 3])
def test_exact_artifact_close_failure_rolls_back_every_owned_leaf(
    tmp_path, monkeypatch, failure_ordinal
) -> None:
    run_dir = tmp_path / f"run-{failure_ordinal}"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    artifacts = {leaf: f"{leaf}\n".encode() for leaf in leaves}
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    original = gate.os.close
    calls = 0

    def failing_close(descriptor):
        nonlocal calls
        calls += 1
        if calls == failure_ordinal:
            raise OSError("injected close failure")
        return original(descriptor)

    monkeypatch.setattr(gate.os, "close", failing_close)
    transaction.publish(artifacts)
    assert transaction.release_committed() is False
    monkeypatch.setattr(gate.os, "close", original)
    assert transaction.release_committed() is True
    assert {leaf: (run_dir / leaf).read_bytes() for leaf in leaves} == artifacts


def test_exact_artifact_rejects_tamper_during_later_leaf_verification(
    tmp_path, monkeypatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    artifacts = {leaf: f"{leaf}\n".encode() for leaf in leaves}
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    injected = False
    blocked = False
    original_read = gate.os.read
    second_descriptor = transaction.descriptors[leaves[1]]
    first_path = run_dir / leaves[0]

    def tampering_read(descriptor, size):
        nonlocal injected, blocked
        if descriptor == second_descriptor and not injected:
            injected = True
            original_times = first_path.stat()
            try:
                with first_path.open("r+b") as handle:
                    handle.write(b"X" * len(artifacts[leaves[0]]))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.utime(
                    first_path,
                    ns=(original_times.st_atime_ns, original_times.st_mtime_ns),
                )
            except OSError:
                blocked = True
        return original_read(descriptor, size)

    monkeypatch.setattr(gate.os, "read", tampering_read)
    rejected = False
    try:
        transaction.publish(artifacts)
    except ABParserError:
        rejected = True
    assert injected
    assert blocked or rejected
    if transaction.committed:
        assert transaction.release_committed() is True
        assert first_path.read_bytes() == artifacts[leaves[0]]


def test_exact_artifact_rejects_hardlink_during_later_leaf_verification(
    tmp_path, monkeypatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    artifacts = {leaf: f"{leaf}\n".encode() for leaf in leaves}
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    alias = tmp_path / "external-alias"
    injected = False
    blocked = False
    original_read = gate.os.read
    second_descriptor = transaction.descriptors[leaves[1]]
    first_path = run_dir / leaves[0]

    def hardlinking_read(descriptor, size):
        nonlocal injected, blocked
        if descriptor == second_descriptor and not injected:
            injected = True
            original_times = first_path.stat()
            try:
                os.link(first_path, alias)
                with alias.open("r+b") as handle:
                    handle.write(b"Y" * len(artifacts[leaves[0]]))
                    handle.flush()
                    os.fsync(handle.fileno())
                alias.unlink()
                os.utime(
                    first_path,
                    ns=(original_times.st_atime_ns, original_times.st_mtime_ns),
                )
            except OSError:
                blocked = True
                if alias.exists():
                    alias.unlink()
        return original_read(descriptor, size)

    monkeypatch.setattr(gate.os, "read", hardlinking_read)
    rejected = False
    try:
        transaction.publish(artifacts)
    except ABParserError:
        rejected = True
    assert injected
    assert blocked or rejected
    if transaction.committed:
        assert transaction.release_committed() is True
        assert first_path.read_bytes() == artifacts[leaves[0]]
    if alias.exists():
        alias.unlink()


def test_persistent_close_failure_retains_retryable_rollback_state(
    tmp_path, monkeypatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    artifacts = {leaf: f"{leaf}\n".encode() for leaf in leaves}
    target_descriptor = transaction.descriptors[leaves[0]]
    original_close = gate.os.close
    original_token = gate._descriptor_change_token

    def fail_token(descriptor, info):
        raise ABParserError("publication", "publication-failed", "injected token failure")

    def persistent_close(descriptor):
        if descriptor == target_descriptor:
            raise OSError("persistent close failure")
        return original_close(descriptor)

    monkeypatch.setattr(gate, "_descriptor_change_token", fail_token)
    monkeypatch.setattr(gate.os, "close", persistent_close)
    with pytest.raises(ABParserError):
        transaction.publish(artifacts)
    assert transaction.active is True
    assert leaves[0] in transaction.descriptors
    monkeypatch.setattr(gate, "_descriptor_change_token", original_token)
    monkeypatch.setattr(gate.os, "close", original_close)
    transaction.rollback()
    assert transaction.active is False
    assert not run_dir.exists() or not any(run_dir.iterdir())


@pytest.mark.skipif(os.name == "nt", reason="POSIX rename race contract")
@pytest.mark.parametrize("rename_kind", ["leaf", "run-directory"])
def test_posix_rollback_follows_owned_identity_through_case_rename(
    tmp_path, monkeypatch, rename_kind
) -> None:
    run_dir = tmp_path / "run-case"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    artifacts = {leaf: f"secret {leaf}\n".encode() for leaf in leaves}
    original_lock = transaction._lock
    renamed_run = run_dir.with_name("RUN-CASE")
    injected = False

    def rename_then_lock(leaf):
        nonlocal injected
        if not injected:
            injected = True
            if rename_kind == "leaf":
                (run_dir / leaf).rename(run_dir / leaf.upper())
            else:
                run_dir.rename(renamed_run)
        original_lock(leaf)

    monkeypatch.setattr(transaction, "_lock", rename_then_lock)
    with pytest.raises(ABParserError):
        transaction.publish(artifacts)
    assert injected
    assert transaction.active is False
    assert not run_dir.exists()
    assert not renamed_run.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX rename race contract")
def test_posix_cross_parent_rename_retains_retryable_ownership(
    tmp_path, monkeypatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    moved = other / "moved"
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    artifacts = {leaf: f"secret {leaf}\n".encode() for leaf in leaves}
    original_lock = transaction._lock
    injected = False

    def move_then_lock(leaf):
        nonlocal injected
        if not injected:
            injected = True
            run_dir.rename(moved)
        original_lock(leaf)

    monkeypatch.setattr(transaction, "_lock", move_then_lock)
    with pytest.raises(ABParserError):
        transaction.publish(artifacts)
    assert injected
    assert transaction.active is True
    assert {path.name for path in moved.iterdir()} == set(leaves)


@pytest.mark.skipif(os.name == "nt", reason="POSIX rename race contract")
def test_posix_cross_parent_leaf_move_retains_descriptor_and_active_state(
    tmp_path, monkeypatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    escape = tmp_path / "escape"
    escape.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    artifacts = {leaf: f"secret {leaf}\n".encode() for leaf in leaves}
    original_lock = transaction._lock
    moved = escape / "MOVED-PRIVATE.JSONL"
    injected = False

    def move_leaf_then_lock(leaf):
        nonlocal injected
        if not injected:
            injected = True
            (run_dir / leaf).rename(moved)
        original_lock(leaf)

    monkeypatch.setattr(transaction, "_lock", move_leaf_then_lock)
    with pytest.raises(ABParserError):
        transaction.publish(artifacts)
    assert injected
    assert transaction.active is True
    assert leaves[0] in transaction.descriptors
    assert moved.read_bytes() == artifacts[leaves[0]]
    moved.rename(run_dir / leaves[0])
    transaction.rollback()
    assert transaction.active is False
    assert not run_dir.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX descriptor lifetime contract")
def test_posix_rollback_never_deletes_recreated_foreign_leaf(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    transaction.write(leaves[0], b"PRIVATE")
    target_descriptor = transaction.descriptors[leaves[0]]
    original_close = gate.os.close
    recreated = False

    def recreate_after_close(descriptor):
        nonlocal recreated
        result = original_close(descriptor)
        if descriptor == target_descriptor and not recreated:
            recreated = True
            (run_dir / leaves[0]).write_bytes(b"FOREIGN-DO-NOT-DELETE")
        return result

    monkeypatch.setattr(gate.os, "close", recreate_after_close)
    transaction.rollback()
    assert recreated
    assert transaction.active is True
    assert (run_dir / leaves[0]).read_bytes() == b"FOREIGN-DO-NOT-DELETE"
    monkeypatch.setattr(gate.os, "close", original_close)
    (run_dir / leaves[0]).unlink()
    transaction.rollback()
    assert transaction.active is False
    assert not run_dir.exists()


def test_exact_artifact_transaction_rejects_tamper_and_rolls_back(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    transaction = gate.ExactArtifactTransaction(run_dir, leaves)
    transaction.write(leaves[0], b"ORIGINAL")
    if os.name == "nt":
        descriptor = transaction.descriptors[leaves[0]]
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, b"TAMPERED")
        os.ftruncate(descriptor, len(b"TAMPERED"))
        os.fsync(descriptor)
    else:
        (run_dir / leaves[0]).write_bytes(b"TAMPERED")
    with pytest.raises(ABParserError):
        transaction.publish({leaf: b"x" for leaf in leaves})
    assert not run_dir.exists() or not any(run_dir.iterdir())


def test_prepare_output_run_rejects_alias_and_existing_casefold_collision(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )
    output = gate.prepare_output_run(
        tmp_path, run_dir="artifacts/local/ab-parser-sample/run-a"
    )
    assert output.name == "run-a"
    with pytest.raises(ABParserError):
        gate.prepare_output_run(
            tmp_path, run_dir="artifacts/local/ab-parser-sample/RUN-A"
        )
    with pytest.raises(ABParserError):
        gate.prepare_output_run(
            tmp_path, run_dir="artifacts/local/ab-parser-sample/../escape"
        )


def test_transaction_rejects_case_only_run_name_drift_after_prepare(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )
    run_dir = gate.prepare_output_run(
        tmp_path, run_dir="artifacts/local/ab-parser-sample/run-case"
    )
    renamed = run_dir.with_name("RUN-CASE")
    run_dir.rename(renamed)
    leaves = ("private-records.jsonl", "aggregate.json", "receipt.json")
    try:
        with pytest.raises((ABParserError, FileNotFoundError)):
            transaction = gate.ExactArtifactTransaction(run_dir, leaves)
            transaction.publish({leaf: b"x" for leaf in leaves})
    finally:
        if renamed.exists():
            for path in renamed.iterdir():
                path.unlink()
            renamed.rmdir()


def test_runtime_module_verification_rejects_a_path_substitution(tmp_path) -> None:
    bound = _bound()
    bound.bindings["runtime"] = [
        {"path": relative, "raw_sha256": "0" * 64}
        for relative in gate.RUNTIME_RELATIVE_PATHS
    ]
    observed = {relative: tmp_path / Path(relative).name for relative in gate.RUNTIME_RELATIVE_PATHS}
    with pytest.raises(ABParserError):
        gate.verify_runtime_module_paths(ROOT, observed=observed, bound=bound)
