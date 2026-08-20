"""Exact, hash-first verification for local manifest-bound model snapshots."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any

from .file_integrity import stable_read_unchanged


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PORTABLE_PART = re.compile(r"^[A-Za-z0-9._-]+$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _portable_filename(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty portable path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(_PORTABLE_PART.fullmatch(part) is None for part in path.parts)
    ):
        raise ValueError(f"{label} is not a canonical portable path: {value!r}")
    return value


def required_files(artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_files = artifact.get("required_files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("artifact has no exact required_files manifest")
    required: list[dict[str, Any]] = []
    names: set[str] = set()
    casefolded: set[str] = set()
    for index, raw_file in enumerate(raw_files):
        if not isinstance(raw_file, Mapping):
            raise ValueError(f"required_files[{index}] must be an object")
        filename = _portable_filename(
            raw_file.get("filename"),
            label=f"required_files[{index}].filename",
        )
        folded = filename.casefold()
        if filename in names or folded in casefolded:
            raise ValueError(
                "required_files filenames must be unique under portable "
                f"case folding: {filename}"
            )
        size = raw_file.get("size_bytes")
        digest = raw_file.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(
                f"required_files[{index}].size_bytes must be a non-negative integer"
            )
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ValueError(
                f"required_files[{index}].sha256 must be lowercase SHA-256"
            )
        names.add(filename)
        casefolded.add(folded)
        required.append(
            {
                "filename": filename,
                "size_bytes": size,
                "sha256": digest,
            }
        )
    return required


def required_download_bytes(artifact: Mapping[str, Any]) -> int | None:
    try:
        files = required_files(artifact)
    except ValueError:
        files = []
    if files:
        return sum(item["size_bytes"] for item in files)
    weight_bytes = artifact.get("weight_size_bytes")
    return (
        weight_bytes
        if isinstance(weight_bytes, int) and not isinstance(weight_bytes, bool)
        else None
    )


def minimum_free_disk_bytes(required_bytes: int) -> int:
    return (required_bytes * 5 + 1) // 2


def _is_link_or_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
    )


def _require_plain_directory(path: Path, *, label: str) -> None:
    try:
        info = os.lstat(path)
    except OSError as error:
        raise RuntimeError(f"{label} is unavailable: {path}: {error}") from error
    if _is_link_or_reparse(info):
        raise RuntimeError(f"{label} must not be a symlink or reparse point: {path}")
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f"{label} is not a directory: {path}")


def _path_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _require_regular_target(
    path: Path,
    *,
    repository_cache: Path,
    label: str,
) -> Path:
    try:
        link_info = os.lstat(path)
        target = path.resolve(strict=True)
        target_info = os.stat(target)
    except OSError as error:
        raise RuntimeError(f"{label} is unavailable: {error}") from error
    resolved_repository = repository_cache.resolve(strict=True)
    if not target.is_relative_to(resolved_repository):
        raise RuntimeError(f"{label} resolves outside the selected repository cache")
    if _is_link_or_reparse(link_info):
        blobs = repository_cache / "blobs"
        try:
            resolved_blobs = blobs.resolve(strict=True)
        except OSError as error:
            raise RuntimeError(
                f"{label} is linked but the selected repository blob store "
                f"is unavailable: {error}"
            ) from error
        if not target.is_relative_to(resolved_blobs):
            raise RuntimeError(
                f"{label} link target is outside the selected repository blob store"
            )
    if not stat.S_ISREG(target_info.st_mode):
        raise RuntimeError(f"{label} does not resolve to a regular file")
    return target


def _stable_file_bytes(
    path: Path,
    *,
    repository_cache: Path,
    label: str,
) -> tuple[bytes, os.stat_result]:
    target_before = _require_regular_target(
        path,
        repository_cache=repository_cache,
        label=label,
    )
    link_before = os.lstat(path)
    path_before = os.stat(path)
    try:
        with path.open("rb") as handle:
            handle_before = os.fstat(handle.fileno())
            payload = handle.read()
            handle_after = os.fstat(handle.fileno())
    except OSError as error:
        raise RuntimeError(f"cannot read {label}: {error}") from error
    target_after = _require_regular_target(
        path,
        repository_cache=repository_cache,
        label=label,
    )
    link_after = os.lstat(path)
    path_after = os.stat(path)
    if (
        not stable_read_unchanged(
            path_before,
            handle_before,
            handle_after,
            path_after,
        )
        or _path_identity(link_before) != _path_identity(link_after)
        or target_before != target_after
    ):
        raise RuntimeError(f"{label} changed while it was being verified")
    return payload, path_after


def _stable_file_digest(
    path: Path,
    *,
    repository_cache: Path,
    label: str,
) -> tuple[str, os.stat_result]:
    target_before = _require_regular_target(
        path,
        repository_cache=repository_cache,
        label=label,
    )
    link_before = os.lstat(path)
    path_before = os.stat(path)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            handle_before = os.fstat(handle.fileno())
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(block)
            handle_after = os.fstat(handle.fileno())
    except OSError as error:
        raise RuntimeError(f"cannot read {label}: {error}") from error
    target_after = _require_regular_target(
        path,
        repository_cache=repository_cache,
        label=label,
    )
    link_after = os.lstat(path)
    path_after = os.stat(path)
    if (
        not stable_read_unchanged(
            path_before,
            handle_before,
            handle_after,
            path_after,
        )
        or _path_identity(link_before) != _path_identity(link_after)
        or target_before != target_after
    ):
        raise RuntimeError(f"{label} changed while it was being verified")
    return digest.hexdigest(), path_after


def _snapshot_entries(
    snapshot_path: Path,
    *,
    repository_cache: Path,
    expected_names: set[str],
) -> set[str]:
    expected_directories: set[str] = set()
    for name in expected_names:
        parent = PurePosixPath(name).parent
        while parent != PurePosixPath("."):
            expected_directories.add(parent.as_posix())
            parent = parent.parent

    observed: set[str] = set()

    def visit(directory: Path) -> None:
        try:
            entries = list(os.scandir(directory))
        except OSError as error:
            raise RuntimeError(f"cannot enumerate model snapshot: {error}") from error
        for entry in entries:
            entry_path = Path(entry.path)
            relative = entry_path.relative_to(snapshot_path).as_posix()
            info = entry.stat(follow_symlinks=False)
            if _is_link_or_reparse(info):
                if relative not in expected_names:
                    observed.add(relative)
                    continue
                _require_regular_target(
                    entry_path,
                    repository_cache=repository_cache,
                    label=f"required model file {relative}",
                )
                observed.add(relative)
            elif stat.S_ISDIR(info.st_mode):
                if relative not in expected_directories:
                    observed.add(relative + "/")
                    continue
                visit(entry_path)
            elif stat.S_ISREG(info.st_mode):
                observed.add(relative)
            else:
                observed.add(relative)

    visit(snapshot_path)
    return observed


def verify_required_files(
    snapshot_path: Path,
    artifact: Mapping[str, Any],
    *,
    repository_cache: Path | None = None,
) -> list[dict[str, Any]]:
    required = required_files(artifact)
    expected_names = {item["filename"] for item in required}
    repository_root = repository_cache or snapshot_path
    observed_names = _snapshot_entries(
        snapshot_path,
        repository_cache=repository_root,
        expected_names=expected_names,
    )
    unexpected_names = sorted(observed_names - expected_names)
    if unexpected_names:
        raise RuntimeError(
            "model snapshot contains files outside the exact allowlist: "
            + ", ".join(unexpected_names)
        )

    verified: list[dict[str, Any]] = []
    for expected in required:
        filename = expected["filename"]
        path = snapshot_path.joinpath(*filename.split("/"))
        if filename not in observed_names:
            raise RuntimeError(f"required model file is missing: {filename}")
        observed_sha256, info = _stable_file_digest(
            path,
            repository_cache=repository_root,
            label=f"required model file {filename}",
        )
        observed_size = int(info.st_size)
        if observed_size != expected["size_bytes"]:
            raise RuntimeError(
                f"required model file size mismatch for {filename}: "
                f"expected {expected['size_bytes']}, observed {observed_size}"
            )
        if observed_sha256 != expected["sha256"]:
            raise RuntimeError(
                f"required model file SHA-256 mismatch for {filename}: "
                f"expected {expected['sha256']}, observed {observed_sha256}"
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


def _verified_json(
    snapshot_path: Path,
    filename: str,
    *,
    repository_cache: Path,
) -> Mapping[str, Any]:
    payload, _ = _stable_file_bytes(
        snapshot_path / filename,
        repository_cache=repository_cache,
        label=filename,
    )
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot verify {filename}: {error}") from error
    if not isinstance(raw, Mapping):
        raise RuntimeError(f"{filename} root must be an object")
    return raw


def verify_model_config(
    snapshot_path: Path,
    artifact: Mapping[str, Any],
    *,
    repository_cache: Path | None = None,
) -> dict[str, Any]:
    raw = _verified_json(
        snapshot_path,
        "config.json",
        repository_cache=repository_cache or snapshot_path,
    )
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


def _special_token_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("content"), str):
        return str(value["content"])
    if value is None:
        return None
    raise RuntimeError("special token declarations must be strings or content objects")


def verify_tokenizer_config(
    snapshot_path: Path,
    artifact: Mapping[str, Any],
    *,
    repository_cache: Path | None = None,
) -> dict[str, Any]:
    repository_root = repository_cache or snapshot_path
    tokenizer_config = _verified_json(
        snapshot_path,
        "tokenizer_config.json",
        repository_cache=repository_root,
    )
    tokenizer_json = _verified_json(
        snapshot_path,
        "tokenizer.json",
        repository_cache=repository_root,
    )
    special_map = _verified_json(
        snapshot_path,
        "special_tokens_map.json",
        repository_cache=repository_root,
    )
    if tokenizer_config.get("auto_map") not in (None, {}):
        raise RuntimeError("tokenizer config declares disallowed custom auto_map code")
    tokenizer_class = tokenizer_config.get("tokenizer_class")
    if not isinstance(tokenizer_class, str) or re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_]*", tokenizer_class
    ) is None:
        raise RuntimeError("tokenizer config lacks an exact built-in tokenizer_class")
    model = tokenizer_json.get("model")
    if not isinstance(model, Mapping) or not isinstance(model.get("vocab"), Mapping):
        raise RuntimeError("tokenizer.json lacks an exact model vocabulary")
    vocab = model["vocab"]
    vocab_ids = list(vocab.values())
    if not vocab_ids or not all(
        isinstance(token_id, int)
        and not isinstance(token_id, bool)
        and token_id >= 0
        for token_id in vocab_ids
    ):
        raise RuntimeError("tokenizer.json vocabulary IDs are invalid")
    added = tokenizer_json.get("added_tokens", [])
    if not isinstance(added, list) or not all(
        isinstance(item, Mapping)
        and isinstance(item.get("id"), int)
        and not isinstance(item.get("id"), bool)
        and item["id"] >= 0
        for item in added
    ):
        raise RuntimeError("tokenizer.json added-token IDs are invalid")
    all_ids = vocab_ids + [int(item["id"]) for item in added]
    special_tokens = {
        name: _special_token_text(
            special_map.get(name, tokenizer_config.get(name))
        )
        for name in ("bos_token", "eos_token", "pad_token", "unk_token")
    }
    runtime = artifact.get("tokenizer_runtime")
    if not isinstance(runtime, Mapping):
        raise RuntimeError("artifact lacks exact tokenizer runtime expectations")
    runtime_class = runtime.get("class")
    if runtime_class not in {tokenizer_class, tokenizer_class + "Fast"}:
        raise RuntimeError(
            "tokenizer runtime class is inconsistent with tokenizer_config.json"
        )
    runtime_vocab = runtime.get("vocab_size")
    runtime_length = runtime.get("tokenizer_length")
    observed_length = max(all_ids) + 1
    if runtime_vocab != len(vocab) or runtime_length != observed_length:
        raise RuntimeError(
            "tokenizer runtime vocabulary expectations do not match tokenizer.json"
        )
    return {
        "tokenizer_class": tokenizer_class,
        "vocab_size": len(vocab),
        "tokenizer_length": observed_length,
        "declared_special_tokens": special_tokens,
        "auto_map": tokenizer_config.get("auto_map"),
        "runtime_expectation": {
            "class": runtime["class"],
            "is_fast": runtime["is_fast"],
            "native_prefix_policy": runtime["native_prefix_policy"],
            "native_special_tokens_to_add": runtime[
                "native_special_tokens_to_add"
            ],
            "vocab_size": runtime["vocab_size"],
            "tokenizer_length": runtime["tokenizer_length"],
            "special_tokens": dict(runtime["special_tokens"]),
            "special_token_ids": dict(runtime["special_token_ids"]),
            "backend_sha256": runtime["backend_sha256"],
        },
        "verified": True,
    }


def verify_snapshot_identity(
    snapshot_path: Path,
    cache_dir: Path,
    revision: str,
    repository: str | None = None,
) -> None:
    if not snapshot_path.is_absolute() or not cache_dir.is_absolute():
        raise RuntimeError("model cache and snapshot paths must be absolute")
    if (
        os.path.normpath(str(snapshot_path)) != str(snapshot_path)
        or os.path.normpath(str(cache_dir)) != str(cache_dir)
    ):
        raise RuntimeError("model cache and snapshot paths must be normalized")
    if str(snapshot_path).startswith("\\\\") or str(cache_dir).startswith("\\\\"):
        raise RuntimeError("UNC/device model cache paths are not permitted")
    _require_plain_directory(cache_dir, label="selected model cache")
    resolved_cache = cache_dir.resolve(strict=True)
    if cache_dir != resolved_cache:
        raise RuntimeError(
            "selected model cache path must not traverse a symlink or reparse point"
        )
    if repository is None:
        resolved_snapshot = snapshot_path.resolve(strict=True)
        if not resolved_snapshot.is_relative_to(resolved_cache):
            raise RuntimeError("model snapshot path is outside the selected model cache")
        if resolved_snapshot.name != revision:
            raise RuntimeError(
                "model snapshot path is not bound to the requested revision: "
                f"expected leaf {revision}, observed {resolved_snapshot.name}"
            )
        return
    if _REPOSITORY.fullmatch(repository) is None:
        raise RuntimeError("artifact repository must be exact Hugging Face owner/name")
    owner, name = repository.split("/", 1)
    repository_cache = cache_dir / f"models--{owner}--{name}"
    snapshots_dir = repository_cache / "snapshots"
    expected_snapshot = snapshots_dir / revision
    for path, label in (
        (repository_cache, "selected repository cache"),
        (snapshots_dir, "selected snapshots directory"),
        (expected_snapshot, "selected model snapshot"),
    ):
        _require_plain_directory(path, label=label)
    if snapshot_path != expected_snapshot:
        raise RuntimeError(
            "model snapshot path is not the exact repository/revision cache locator"
        )
    if snapshot_path.resolve(strict=True) != expected_snapshot.resolve(strict=True):
        raise RuntimeError(
            "model snapshot path is not the exact repository/revision cache locator"
        )


def verify_snapshot(
    snapshot_path: str | Path,
    cache_dir: str | Path,
    artifact: Mapping[str, Any],
    revision: str | None = None,
) -> dict[str, Any]:
    snapshot = Path(snapshot_path)
    cache = Path(cache_dir)
    artifact_revision = artifact.get("revision")
    repository = artifact.get("repository")
    artifact_id = artifact.get("id")
    if not isinstance(artifact_revision, str) or not artifact_revision:
        raise ValueError("artifact has no exact revision")
    if revision is not None and revision != artifact_revision:
        raise RuntimeError(
            "caller revision does not match the manifest artifact revision"
        )
    if not isinstance(repository, str):
        raise ValueError("artifact has no exact repository")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise ValueError("artifact has no exact id")
    verify_snapshot_identity(
        snapshot,
        cache,
        artifact_revision,
        repository,
    )
    owner, name = repository.split("/", 1)
    repository_cache = cache / f"models--{owner}--{name}"
    files = verify_required_files(
        snapshot,
        artifact,
        repository_cache=repository_cache,
    )
    config = verify_model_config(
        snapshot,
        artifact,
        repository_cache=repository_cache,
    )
    filenames = {item["filename"] for item in files}
    tokenizer_config = (
        verify_tokenizer_config(
            snapshot,
            artifact,
            repository_cache=repository_cache,
        )
        if {
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
        }.issubset(filenames)
        else None
    )
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "status": "verified",
        "artifact_id": artifact_id,
        "repository": repository,
        "revision": artifact_revision,
        "required_download_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
        "config": config,
        "tokenizer_config": tokenizer_config,
    }
    receipt["receipt_sha256"] = _canonical_json_sha256(receipt)
    return {
        "status": "verified",
        "snapshot_path": str(snapshot.resolve(strict=True)),
        "repository_cache": str(repository_cache.resolve(strict=True)),
        "resolved_revision": artifact_revision,
        "required_download_bytes": receipt["required_download_bytes"],
        "files": files,
        "config": config,
        "tokenizer_config": tokenizer_config,
        "portable_receipt": receipt,
    }
