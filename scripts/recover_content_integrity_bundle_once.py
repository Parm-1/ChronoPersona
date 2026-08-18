#!/usr/bin/env python3
"""Recover the reviewed content-integrity bundle after a one-character split error.

This script is intentionally one-time and fail-closed. It accepts only one
unique valid gzip/tar reconstruction, rejects unsafe archive members, records
all recovery hashes, and removes itself plus the importer artifacts after a
successful extraction. It performs no network or model operation.
"""

from __future__ import annotations

import base64
import binascii
from collections import defaultdict
import gzip
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMPORT_ROOT = ROOT / "artifacts" / "import"
PARTS = tuple(IMPORT_ROOT / f"content-v0.part{index}" for index in range(8))
EVIDENCE_PATH = ROOT / "reports" / "stage0" / "content_integrity_bundle_recovery.json"
ONE_TIME_PATHS = (
    ROOT / ".github" / "workflows" / "one-time-content-integrity-import.yml",
    ROOT / ".github" / "workflows" / "content-integrity-recovery-pr.yml",
    ROOT / "scripts" / "recover_content_integrity_bundle_once.py",
)
_ALLOWED_BASE64 = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)
_FORBIDDEN_TOP_LEVEL = frozenset(
    {".git", "checkpoints", "models", "runs", "secrets", "wandb", "mlruns"}
)


class RecoveryError(RuntimeError):
    """Raised when recovery is ambiguous or unsafe."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inspect_tar(payload: bytes) -> tuple[tarfile.TarInfo, ...]:
    with tarfile.open(fileobj=BytesIO(payload), mode="r:*") as archive:
        members = tuple(archive.getmembers())
    if not members:
        raise RecoveryError("bundle archive is empty")

    names: list[str] = []
    for member in members:
        name = member.name
        if "\\" in name:
            raise RecoveryError(f"archive path uses backslashes: {name!r}")
        path = PurePosixPath(name)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise RecoveryError(f"unsafe archive path: {name!r}")
        if path.parts[0] in _FORBIDDEN_TOP_LEVEL:
            raise RecoveryError(f"forbidden archive path: {name!r}")
        if tuple(path.parts[:2]) == ("artifacts", "import"):
            raise RecoveryError(f"archive may not recreate importer data: {name!r}")
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise RecoveryError(f"archive contains a link or special file: {name!r}")
        if not (member.isdir() or member.isfile()):
            raise RecoveryError(f"unsupported archive member type: {name!r}")
        names.append(name)

    required_prefixes = ("src/chronopersona/", "scripts/", "tests/")
    for prefix in required_prefixes:
        if not any(name.startswith(prefix) for name in names):
            raise RecoveryError(f"bundle has no member under {prefix}")
    return members


def decode_candidate(candidate: bytes) -> tuple[bytes, bytes, tuple[tarfile.TarInfo, ...]]:
    compressed = base64.b64decode(candidate, validate=True)
    if not compressed.startswith(b"\x1f\x8b"):
        raise RecoveryError("decoded payload is not gzip")
    payload = gzip.decompress(compressed)
    return compressed, payload, inspect_tar(payload)


def recover(normalized: bytes) -> tuple[dict[str, Any], bytes, tuple[tarfile.TarInfo, ...]]:
    direct_error: str | None = None
    try:
        compressed, payload, members = decode_candidate(normalized)
        return (
            {
                "mode": "direct",
                "positions": [],
                "characters": [],
                "direct_decode_error": None,
                "compressed": compressed,
            },
            payload,
            members,
        )
    except (binascii.Error, EOFError, OSError, tarfile.TarError, RecoveryError) as error:
        direct_error = f"{type(error).__name__}: {error}"

    if len(normalized) % 4 != 1:
        raise RecoveryError(
            "strict decode failed and the stream is not exactly one character over a base64 quartet: "
            f"length={len(normalized)}, remainder={len(normalized) % 4}, error={direct_error}"
        )

    candidates: dict[str, dict[str, Any]] = {}
    positions: defaultdict[str, list[int]] = defaultdict(list)
    characters: defaultdict[str, set[str]] = defaultdict(set)
    for index in range(len(normalized)):
        repaired = normalized[:index] + normalized[index + 1 :]
        try:
            compressed, payload, members = decode_candidate(repaired)
        except (binascii.Error, EOFError, OSError, tarfile.TarError, RecoveryError):
            continue
        payload_sha = sha256(payload)
        positions[payload_sha].append(index)
        characters[payload_sha].add(chr(normalized[index]))
        candidates.setdefault(
            payload_sha,
            {
                "compressed": compressed,
                "payload": payload,
                "members": members,
            },
        )

    if len(candidates) != 1:
        summary = {
            payload_sha: {
                "positions": positions[payload_sha],
                "characters": sorted(characters[payload_sha]),
                "member_count": len(candidate["members"]),
            }
            for payload_sha, candidate in candidates.items()
        }
        raise RecoveryError(
            "expected exactly one unique valid repaired payload; found "
            + json.dumps(summary, sort_keys=True)
        )

    payload_sha, candidate = next(iter(candidates.items()))
    return (
        {
            "mode": "remove-one-base64-character",
            "positions": positions[payload_sha],
            "characters": sorted(characters[payload_sha]),
            "direct_decode_error": direct_error,
            "compressed": candidate["compressed"],
        },
        candidate["payload"],
        candidate["members"],
    )


def extract(payload: bytes, members: tuple[tarfile.TarInfo, ...], staging: Path) -> None:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with tarfile.open(fileobj=BytesIO(payload), mode="r:*") as archive:
        by_name = {member.name: member for member in archive.getmembers()}
        for inspected in members:
            member = by_name[inspected.name]
            destination = staging / PurePosixPath(member.name)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RecoveryError(f"unable to read archive member: {member.name}")
            with source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)


def main() -> int:
    missing = [path.as_posix() for path in PARTS if not path.is_file()]
    if missing:
        raise RecoveryError(f"missing bundle parts: {missing}")

    part_bytes = tuple(path.read_bytes() for path in PARTS)
    normalized = b"".join(b"".join(content.split()) for content in part_bytes)
    invalid = sorted(set(normalized) - _ALLOWED_BASE64)
    if invalid:
        raise RecoveryError(f"bundle contains non-base64 bytes: {invalid}")

    repair, payload, members = recover(normalized)
    compressed = repair.pop("compressed")
    assert isinstance(compressed, bytes)

    runner_temp = Path(os.environ.get("RUNNER_TEMP", ROOT / ".recovery-tmp"))
    staging = runner_temp / "content-integrity-staging"
    extract(payload, members, staging)

    for child in staging.iterdir():
        destination = ROOT / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(child, destination)

    source_commit = os.environ.get("GITHUB_SHA", "unavailable")
    evidence = {
        "schema_version": 1,
        "source_branch": "agent/content-integrity-v0",
        "source_commit": source_commit,
        "source_parts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(content),
                "sha256": sha256(content),
            }
            for path, content in zip(PARTS, part_bytes, strict=True)
        ],
        "normalized_base64_bytes": len(normalized),
        "normalized_base64_sha256": sha256(normalized),
        "direct_decode_error": repair["direct_decode_error"],
        "repair_mode": repair["mode"],
        "removed_character_positions": repair["positions"],
        "removed_characters": repair["characters"],
        "compressed_gzip_bytes": len(compressed),
        "compressed_gzip_sha256": sha256(compressed),
        "decompressed_tar_bytes": len(payload),
        "decompressed_tar_sha256": sha256(payload),
        "archive_members": [member.name for member in members],
        "archive_member_count": len(members),
        "network_used": False,
        "model_used": False,
        "training_performed": False,
        "validation_status": "pending",
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    shutil.rmtree(IMPORT_ROOT)
    for path in ONE_TIME_PATHS:
        path.unlink(missing_ok=True)

    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
