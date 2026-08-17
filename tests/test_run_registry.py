from __future__ import annotations

import json
from pathlib import Path

import pytest

from chronopersona.run_registry import (
    RunRegistryError,
    RunStore,
    append_registry_entry,
    atomic_write_json,
    build_run_identity,
    canonical_sha256,
    ensure_registry_entry,
    read_event_log,
    read_registry,
)


def test_run_identity_is_order_independent_and_sensitive() -> None:
    first = build_run_identity({"model": "none", "seed": 17, "inputs": [1, 2]})
    reordered = build_run_identity({"inputs": [1, 2], "seed": 17, "model": "none"})
    changed = build_run_identity({"model": "none", "seed": 18, "inputs": [1, 2]})

    assert first == reordered
    assert first["run_id"] != changed["run_id"]
    assert first["identity_sha256"] == canonical_sha256(
        first["scientific_identity"]
    )


def test_event_log_rejects_invalid_transition_and_tampering(tmp_path: Path) -> None:
    identity = build_run_identity({"fixture": "event-log"})
    store = RunStore(tmp_path / "run", identity)
    store.initialize(recorded_at="create-time")

    with pytest.raises(RunRegistryError, match="cannot append 'start'"):
        store.transition("start", recorded_at="bad-start")

    store.transition("freeze", recorded_at="freeze-time")
    store.transition("start", recorded_at="start-time")
    store.transition(
        "progress",
        data={"unit_id": "one"},
        recorded_at="progress-time",
    )
    assert store.state == "running"

    lines = store.events_path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[1])
    event["data"] = {"tampered": True}
    lines[1] = json.dumps(event, sort_keys=True)
    store.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(RunRegistryError, match="event hash mismatch"):
        store.verify()


def test_registry_is_hash_chained_and_idempotent(tmp_path: Path) -> None:
    registry = tmp_path / "registry.jsonl"
    first = build_run_identity({"run": 1})
    second = build_run_identity({"run": 2})

    first_entry = ensure_registry_entry(registry, first, created_at="first")
    assert ensure_registry_entry(registry, first, created_at="ignored") == first_entry
    append_registry_entry(registry, second, created_at="second")

    state = read_registry(registry)
    assert [entry["sequence"] for entry in state.entries] == [0, 1]
    assert state.entries[1]["previous_entry_sha256"] == state.entries[0][
        "entry_sha256"
    ]

    lines = registry.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["created_at"] = "tampered"
    lines[0] = json.dumps(entry, sort_keys=True)
    registry.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(RunRegistryError, match="entry hash mismatch"):
        read_registry(registry)


def test_run_lock_is_exclusive_and_not_silently_recovered(tmp_path: Path) -> None:
    identity = build_run_identity({"fixture": "lock"})
    store = RunStore(tmp_path / "run", identity)
    store.initialize()

    with store.lock():
        with pytest.raises(RunRegistryError, match="lock already exists"):
            with store.lock():
                pass

    store.lock_path.write_text("stale\n", encoding="utf-8")
    with pytest.raises(RunRegistryError, match="inspect it explicitly"):
        with store.lock():
            pass


def test_atomic_json_replaces_complete_content(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "artifact.json"
    atomic_write_json(destination, {"version": 1, "items": [1, 2]})
    atomic_write_json(destination, {"version": 2, "items": [3]})

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "version": 2,
        "items": [3],
    }
    assert not list(destination.parent.glob(f".{destination.name}.*.tmp"))


def test_event_log_supports_explicit_unclean_recovery(tmp_path: Path) -> None:
    identity = build_run_identity({"fixture": "recover"})
    store = RunStore(tmp_path / "run", identity)
    store.initialize()
    store.transition("freeze")
    store.transition("start")
    store.transition("recover", data={"operator_authorized": True})
    store.transition("fail", data={"reason": "fixture"})
    store.transition("resume", data={"operator_authorized": True})
    store.transition("complete", data={"artifact": "fixture"})

    state = read_event_log(store.events_path, expected_run_id=store.run_id)
    assert state.state == "complete"
    assert [event["event_type"] for event in state.events] == [
        "create",
        "freeze",
        "start",
        "recover",
        "fail",
        "resume",
        "complete",
    ]
