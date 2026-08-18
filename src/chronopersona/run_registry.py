"""Immutable run identity and append-only state for ChronoPersona.

Scientific identity is deliberately separated from runtime events. The former
is canonical and immutable; the latter is an append-only hash chain containing
wall-clock and operational details.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


class RunRegistryError(ValueError):
    """Raised when run identity, state, or artifact integrity is invalid."""


RUN_STATES = frozenset({"design", "frozen", "running", "complete", "failed"})
_EVENT_TRANSITIONS: dict[str, tuple[str | None, str]] = {
    "create": (None, "design"),
    "freeze": ("design", "frozen"),
    "start": ("frozen", "running"),
    "progress": ("running", "running"),
    "recover": ("running", "running"),
    "complete": ("running", "complete"),
    "fail": ("running", "failed"),
    "resume": ("failed", "running"),
}
_EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "sequence",
        "event_type",
        "state_before",
        "state_after",
        "recorded_at",
        "previous_event_sha256",
        "data",
        "event_sha256",
    }
)
_IDENTITY_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "identity_sha256",
        "scientific_identity",
    }
)


def canonical_json_bytes(value: Any) -> bytes:
    """Encode a JSON-compatible value deterministically."""

    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise RunRegistryError(f"value is not canonical JSON: {error}") from error
    return rendered.encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise RunRegistryError(f"{label} must be a 64-character SHA-256")
    try:
        int(value, 16)
    except ValueError as error:
        raise RunRegistryError(f"{label} must be lowercase hexadecimal") from error
    if value != value.lower():
        raise RunRegistryError(f"{label} must be lowercase hexadecimal")
    return value


def _validate_run_id(value: Any) -> str:
    if not isinstance(value, str) or not value.startswith("run-"):
        raise RunRegistryError("run_id must start with 'run-'")
    suffix = value.removeprefix("run-")
    if len(suffix) != 32:
        raise RunRegistryError("run_id must contain 32 hexadecimal characters")
    try:
        int(suffix, 16)
    except ValueError as error:
        raise RunRegistryError("run_id suffix must be hexadecimal") from error
    if suffix != suffix.lower():
        raise RunRegistryError("run_id suffix must be lowercase")
    return value


def build_run_identity(scientific_identity: Mapping[str, Any]) -> dict[str, Any]:
    """Create an immutable run identity from canonical scientific inputs."""

    if not isinstance(scientific_identity, Mapping) or not scientific_identity:
        raise RunRegistryError("scientific_identity must be a nonempty object")
    normalized = json.loads(canonical_json_bytes(scientific_identity))
    identity_sha256 = canonical_sha256(normalized)
    run_id = f"run-{identity_sha256[:32]}"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "identity_sha256": identity_sha256,
        "scientific_identity": normalized,
    }


def validate_run_identity(identity: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if set(identity) != _IDENTITY_FIELDS:
        errors.append("run identity has unexpected or missing fields")
        return tuple(errors)
    if identity.get("schema_version") != 1:
        errors.append("run identity schema_version must be 1")
    try:
        run_id = _validate_run_id(identity.get("run_id"))
    except RunRegistryError as error:
        errors.append(str(error))
        run_id = None
    try:
        identity_sha = _validate_sha256(
            identity.get("identity_sha256"),
            "identity_sha256",
        )
    except RunRegistryError as error:
        errors.append(str(error))
        identity_sha = None
    scientific = identity.get("scientific_identity")
    if not isinstance(scientific, Mapping) or not scientific:
        errors.append("scientific_identity must be a nonempty object")
    elif identity_sha is not None:
        expected = canonical_sha256(scientific)
        if expected != identity_sha:
            errors.append("scientific_identity hash mismatch")
        if run_id is not None and run_id != f"run-{expected[:32]}":
            errors.append("run_id does not match scientific_identity")
    return tuple(errors)


def atomic_write_bytes(path: str | Path, content: bytes) -> None:
    """Durably replace one file without exposing partial content."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        try:
            directory_fd = os.open(destination.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: str | Path, value: Any) -> None:
    atomic_write_bytes(Path(path), canonical_json_bytes(value) + b"\n")


def read_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RunRegistryError(f"invalid JSON in {path}: {error}") from error


@dataclass(frozen=True)
class EventLogState:
    events: tuple[dict[str, Any], ...]
    state: str | None
    final_sha256: str | None


def _event_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: event[key] for key in event if key != "event_sha256"}


def validate_event_log(
    events: Sequence[Mapping[str, Any]],
    *,
    expected_run_id: str | None = None,
) -> EventLogState:
    state: str | None = None
    previous_hash: str | None = None
    normalized: list[dict[str, Any]] = []
    for index, raw_event in enumerate(events):
        if not isinstance(raw_event, Mapping):
            raise RunRegistryError(f"events[{index}] must be an object")
        event = dict(raw_event)
        if set(event) != _EVENT_FIELDS:
            raise RunRegistryError(
                f"events[{index}] has unexpected or missing fields"
            )
        if event.get("schema_version") != 1:
            raise RunRegistryError(f"events[{index}] schema_version must be 1")
        run_id = _validate_run_id(event.get("run_id"))
        if expected_run_id is not None and run_id != expected_run_id:
            raise RunRegistryError(f"events[{index}] run_id mismatch")
        if event.get("sequence") != index:
            raise RunRegistryError(f"events[{index}] sequence mismatch")
        event_type = event.get("event_type")
        if event_type not in _EVENT_TRANSITIONS:
            raise RunRegistryError(f"events[{index}] has invalid event_type")
        required_before, required_after = _EVENT_TRANSITIONS[event_type]
        if event.get("state_before") != required_before:
            raise RunRegistryError(
                f"events[{index}] state_before is invalid for {event_type}"
            )
        if event.get("state_after") != required_after:
            raise RunRegistryError(
                f"events[{index}] state_after is invalid for {event_type}"
            )
        if event.get("state_before") != state:
            raise RunRegistryError(f"events[{index}] does not continue current state")
        if event.get("previous_event_sha256") != previous_hash:
            raise RunRegistryError(f"events[{index}] previous hash mismatch")
        if not isinstance(event.get("recorded_at"), str) or not event["recorded_at"]:
            raise RunRegistryError(f"events[{index}] recorded_at must not be empty")
        if not isinstance(event.get("data"), Mapping):
            raise RunRegistryError(f"events[{index}] data must be an object")
        observed_hash = _validate_sha256(
            event.get("event_sha256"),
            f"events[{index}].event_sha256",
        )
        expected_hash = canonical_sha256(_event_payload(event))
        if observed_hash != expected_hash:
            raise RunRegistryError(f"events[{index}] event hash mismatch")
        normalized.append(event)
        state = required_after
        previous_hash = observed_hash
    return EventLogState(tuple(normalized), state, previous_hash)


def read_event_log(
    path: str | Path,
    *,
    expected_run_id: str | None = None,
) -> EventLogState:
    source = Path(path)
    if not source.exists():
        return EventLogState((), None, None)
    events: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                raise RunRegistryError(
                    f"event log contains a blank line at {line_number}"
                )
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise RunRegistryError(
                    f"invalid event JSON on line {line_number}: {error}"
                ) from error
            if not isinstance(value, dict):
                raise RunRegistryError(
                    f"event log line {line_number} must be an object"
                )
            events.append(value)
    return validate_event_log(events, expected_run_id=expected_run_id)


def append_event(
    path: str | Path,
    *,
    run_id: str,
    event_type: str,
    data: Mapping[str, Any] | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Append one state transition after validating the entire existing chain."""

    _validate_run_id(run_id)
    if event_type not in _EVENT_TRANSITIONS:
        raise RunRegistryError(f"unsupported event_type: {event_type}")
    source = Path(path)
    log_state = read_event_log(source, expected_run_id=run_id)
    required_before, required_after = _EVENT_TRANSITIONS[event_type]
    if log_state.state != required_before:
        raise RunRegistryError(
            f"cannot append {event_type!r} while run state is {log_state.state!r}"
        )
    event: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "sequence": len(log_state.events),
        "event_type": event_type,
        "state_before": required_before,
        "state_after": required_after,
        "recorded_at": recorded_at or utc_now(),
        "previous_event_sha256": log_state.final_sha256,
        "data": json.loads(canonical_json_bytes(data or {})),
    }
    event["event_sha256"] = canonical_sha256(event)
    rendered = canonical_json_bytes(event) + b"\n"
    source.parent.mkdir(parents=True, exist_ok=True)
    with source.open("ab") as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
    read_event_log(source, expected_run_id=run_id)
    return event


class RunLock(AbstractContextManager["RunLock"]):
    """Exclusive run-directory lock. Stale locks are never removed silently."""

    def __init__(self, path: str | Path, *, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = _validate_run_id(run_id)
        self._owned = False
        self._payload: bytes | None = None

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json_bytes(
            {
                "schema_version": 1,
                "run_id": self.run_id,
                "pid": os.getpid(),
                "created_at": utc_now(),
            }
        ) + b"\n"
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as error:
            raise RunRegistryError(
                f"run lock already exists: {self.path}; inspect it explicitly"
            ) from error
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            self.path.unlink(missing_ok=True)
            raise
        self._payload = payload
        self._owned = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool | None:
        if self._owned:
            if self._payload is None or not self.path.is_file():
                raise RunRegistryError(
                    f"owned run lock disappeared before release: {self.path}"
                )
            if self.path.read_bytes() != self._payload:
                raise RunRegistryError(
                    f"owned run lock changed before release: {self.path}"
                )
            self.path.unlink(missing_ok=False)
            self._owned = False
            self._payload = None
        return None


class RunStore:
    """Filesystem-backed immutable identity and hash-chained runtime state."""

    def __init__(self, root: str | Path, identity: Mapping[str, Any]) -> None:
        identity_errors = validate_run_identity(identity)
        if identity_errors:
            raise RunRegistryError("; ".join(identity_errors))
        self.identity = dict(identity)
        self.run_id = str(identity["run_id"])
        self.root = Path(root)
        self.identity_path = self.root / "identity.json"
        self.events_path = self.root / "events.jsonl"
        self.lock_path = self.root / ".run.lock"

    @classmethod
    def load(cls, root: str | Path) -> "RunStore":
        identity_path = Path(root) / "identity.json"
        if not identity_path.is_file():
            raise RunRegistryError(f"run identity not found: {identity_path}")
        identity = read_json(identity_path)
        if not isinstance(identity, dict):
            raise RunRegistryError("run identity root must be an object")
        store = cls(root, identity)
        store.verify()
        return store

    def initialize(self, *, recorded_at: str | None = None) -> None:
        if self.root.exists() and any(self.root.iterdir()):
            raise RunRegistryError(f"run directory is not empty: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.identity_path, self.identity)
        append_event(
            self.events_path,
            run_id=self.run_id,
            event_type="create",
            data={"identity_sha256": self.identity["identity_sha256"]},
            recorded_at=recorded_at,
        )

    def verify(self) -> EventLogState:
        observed_identity = read_json(self.identity_path)
        if observed_identity != self.identity:
            raise RunRegistryError("immutable run identity file changed")
        errors = validate_run_identity(observed_identity)
        if errors:
            raise RunRegistryError("; ".join(errors))
        state = read_event_log(
            self.events_path,
            expected_run_id=self.run_id,
        )
        if not state.events or state.state is None:
            raise RunRegistryError(
                "initialized run is missing its create event"
            )
        return state

    @property
    def state(self) -> str | None:
        return self.verify().state

    def transition(
        self,
        event_type: str,
        *,
        data: Mapping[str, Any] | None = None,
        recorded_at: str | None = None,
    ) -> dict[str, Any]:
        self.verify()
        return append_event(
            self.events_path,
            run_id=self.run_id,
            event_type=event_type,
            data=data,
            recorded_at=recorded_at,
        )

    def lock(self) -> RunLock:
        return RunLock(self.lock_path, run_id=self.run_id)


_REGISTRY_FIELDS = frozenset(
    {
        "schema_version",
        "sequence",
        "run_id",
        "identity_sha256",
        "created_at",
        "previous_entry_sha256",
        "entry_sha256",
    }
)


@dataclass(frozen=True)
class RegistryState:
    entries: tuple[dict[str, Any], ...]
    final_sha256: str | None


def read_registry(path: str | Path) -> RegistryState:
    """Validate and return the append-only cross-run registry."""

    source = Path(path)
    if not source.exists():
        return RegistryState((), None)
    entries: list[dict[str, Any]] = []
    run_ids: set[str] = set()
    previous_hash: str | None = None
    with source.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            stripped = line.strip()
            if not stripped:
                raise RunRegistryError(
                    f"registry contains blank line {index + 1}"
                )
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise RunRegistryError(
                    f"invalid registry JSON on line {index + 1}: {error}"
                ) from error
            if not isinstance(value, dict) or set(value) != _REGISTRY_FIELDS:
                raise RunRegistryError(
                    f"registry line {index + 1} has invalid fields"
                )
            if value.get("schema_version") != 1:
                raise RunRegistryError(
                    f"registry line {index + 1} schema_version must be 1"
                )
            if value.get("sequence") != index:
                raise RunRegistryError(
                    f"registry line {index + 1} sequence mismatch"
                )
            run_id = _validate_run_id(value.get("run_id"))
            if run_id in run_ids:
                raise RunRegistryError("registry contains duplicate run_id")
            run_ids.add(run_id)
            _validate_sha256(
                value.get("identity_sha256"),
                f"registry line {index + 1} identity_sha256",
            )
            if not isinstance(value.get("created_at"), str) or not value["created_at"]:
                raise RunRegistryError(
                    f"registry line {index + 1} created_at must not be empty"
                )
            if value.get("previous_entry_sha256") != previous_hash:
                raise RunRegistryError(
                    f"registry line {index + 1} previous hash mismatch"
                )
            observed = _validate_sha256(
                value.get("entry_sha256"),
                f"registry line {index + 1} entry_sha256",
            )
            expected = canonical_sha256(
                {key: value[key] for key in value if key != "entry_sha256"}
            )
            if observed != expected:
                raise RunRegistryError(
                    f"registry line {index + 1} entry hash mismatch"
                )
            entries.append(value)
            previous_hash = observed
    return RegistryState(tuple(entries), previous_hash)


def append_registry_entry(
    path: str | Path,
    identity: Mapping[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Append one immutable run identity to the local cross-run registry."""

    errors = validate_run_identity(identity)
    if errors:
        raise RunRegistryError("; ".join(errors))
    destination = Path(path)
    state = read_registry(destination)
    if any(entry["run_id"] == identity["run_id"] for entry in state.entries):
        raise RunRegistryError(f"run already registered: {identity['run_id']}")
    entry: dict[str, Any] = {
        "schema_version": 1,
        "sequence": len(state.entries),
        "run_id": identity["run_id"],
        "identity_sha256": identity["identity_sha256"],
        "created_at": created_at or utc_now(),
        "previous_entry_sha256": state.final_sha256,
    }
    entry["entry_sha256"] = canonical_sha256(entry)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("ab") as handle:
        handle.write(canonical_json_bytes(entry) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    read_registry(destination)
    return entry


def ensure_registry_entry(
    path: str | Path,
    identity: Mapping[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Return an identical existing entry or append a new one."""

    errors = validate_run_identity(identity)
    if errors:
        raise RunRegistryError("; ".join(errors))
    state = read_registry(path)
    matches = [
        entry for entry in state.entries if entry["run_id"] == identity["run_id"]
    ]
    if matches:
        entry = matches[0]
        if entry["identity_sha256"] != identity["identity_sha256"]:
            raise RunRegistryError("registered run identity hash mismatch")
        return entry
    return append_registry_entry(path, identity, created_at=created_at)
