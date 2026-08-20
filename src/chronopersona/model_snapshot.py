"""Exact, hash-first verification for local manifest-bound model snapshots."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any


def required_files(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_files = artifact.get("required_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("artifact has no exact required_files manifest")
    required: list[dict[str, Any]] = []
    for index, raw_file in enumerate(raw_files):
        if not isinstance(raw_file, Mapping):
            raise ValueError(f"required_files[{index}] must be an object")
        required.append(dict(raw_file))
    return required


def required_download_bytes(artifact: Mapping[str, Any]) -> int | None:
    raw_files = artifact.get("required_files")
    if isinstance(raw_files, list) and raw_files:
        sizes = [
            raw_file.get("size_bytes")
            for raw_file in raw_files
            if isinstance(raw_file, Mapping)
        ]
        if len(sizes) == len(raw_files) and all(
            isinstance(size, int) and not isinstance(size, bool)
            for size in sizes
        ):
            return sum(sizes)
    weight_bytes = artifact.get("weight_size_bytes")
    return (
        weight_bytes
        if isinstance(weight_bytes, int) and not isinstance(weight_bytes, bool)
        else None
    )


def minimum_free_disk_bytes(required_bytes: int) -> int:
    return (required_bytes * 5 + 1) // 2


def verify_required_files(
    snapshot_path: Path,
    artifact: Mapping[str, Any],
) -> list[dict[str, Any]]:
    expected_names = {item["filename"] for item in required_files(artifact)}
    observed_names = {
        path.relative_to(snapshot_path).as_posix()
        for path in snapshot_path.rglob("*")
        if path.is_file()
    }
    unexpected_names = sorted(observed_names - expected_names)
    if unexpected_names:
        raise RuntimeError(
            "model snapshot contains files outside the exact allowlist: "
            + ", ".join(unexpected_names)
        )

    verified: list[dict[str, Any]] = []
    for expected in required_files(artifact):
        filename = expected["filename"]
        expected_size = expected["size_bytes"]
        expected_sha256 = expected["sha256"]
        path = snapshot_path.joinpath(*filename.split("/"))
        if not path.is_file():
            raise RuntimeError(f"required model file is missing: {filename}")
        observed_size = path.stat().st_size
        if observed_size != expected_size:
            raise RuntimeError(
                f"required model file size mismatch for {filename}: "
                f"expected {expected_size}, observed {observed_size}"
            )
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(block)
        observed_sha256 = digest.hexdigest()
        if observed_sha256 != expected_sha256:
            raise RuntimeError(
                f"required model file SHA-256 mismatch for {filename}: "
                f"expected {expected_sha256}, observed {observed_sha256}"
            )
        verified.append(
            {
                "filename": filename,
                "size_bytes": observed_size,
                "sha256": observed_sha256,
                "verified": True,
            }
        )
    return verified


def verify_model_config(
    snapshot_path: Path,
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    config_path = snapshot_path / "config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot verify model config: {error}") from error
    if not isinstance(raw, Mapping):
        raise RuntimeError("model config root must be an object")

    expected_model_type = artifact.get("model_type")
    if raw.get("model_type") != expected_model_type:
        raise RuntimeError(
            "model config type mismatch: "
            f"expected {expected_model_type!r}, observed {raw.get('model_type')!r}"
        )
    expected_architecture = artifact.get("architecture")
    architectures = raw.get("architectures")
    if architectures != [expected_architecture]:
        raise RuntimeError(
            "model config architecture mismatch: "
            f"expected {expected_architecture!r}, observed {architectures!r}"
        )
    if raw.get("torch_dtype") != "float16":
        raise RuntimeError(
            "model config dtype mismatch: expected 'float16', "
            f"observed {raw.get('torch_dtype')!r}"
        )
    if raw.get("auto_map") not in (None, {}):
        raise RuntimeError("model config declares disallowed custom auto_map code")
    return {
        "model_type": raw["model_type"],
        "architectures": architectures,
        "torch_dtype": raw["torch_dtype"],
        "auto_map": raw.get("auto_map"),
        "verified": True,
    }


def verify_snapshot_identity(
    snapshot_path: Path,
    cache_dir: Path,
    revision: str,
) -> None:
    resolved_snapshot = snapshot_path.resolve(strict=True)
    resolved_cache = cache_dir.resolve(strict=True)
    if not resolved_snapshot.is_relative_to(resolved_cache):
        raise RuntimeError("model snapshot path is outside the selected model cache")
    if resolved_snapshot.name != revision:
        raise RuntimeError(
            "model snapshot path is not bound to the requested revision: "
            f"expected leaf {revision}, observed {resolved_snapshot.name}"
        )


def verify_snapshot(
    snapshot_path: str | Path,
    cache_dir: str | Path,
    artifact: Mapping[str, Any],
    revision: str,
) -> dict[str, Any]:
    snapshot = Path(snapshot_path)
    cache = Path(cache_dir)
    verify_snapshot_identity(snapshot, cache, revision)
    files = verify_required_files(snapshot, artifact)
    config = verify_model_config(snapshot, artifact)
    return {
        "status": "verified",
        "snapshot_path": str(snapshot.resolve(strict=True)),
        "resolved_revision": revision,
        "required_download_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
        "config": config,
    }
