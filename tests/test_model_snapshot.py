import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from chronopersona.evaluation import canonical_json_sha256
from chronopersona.model_snapshot import verify_snapshot


REVISION = "a" * 40


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _snapshot_fixture(
    root: Path,
    *,
    artifact_repository: str = "owner/model",
    directory_repository: str | None = None,
    revision: str = REVISION,
    tokenizer_auto_map: object = None,
) -> tuple[Path, Path, dict[str, object]]:
    directory_repository = directory_repository or artifact_repository
    cache = root / "cache"
    owner, name = directory_repository.split("/", 1)
    snapshot = cache / f"models--{owner}--{name}" / "snapshots" / revision
    snapshot.mkdir(parents=True)
    payloads = {
        "config.json": _json_bytes(
            {
                "architectures": ["FixtureModel"],
                "model_type": "fixture",
                "torch_dtype": "float16",
            }
        ),
        "model.safetensors": b"fixture model bytes",
        "special_tokens_map.json": _json_bytes(
            {
                "bos_token": "<e>",
                "eos_token": "<e>",
                "unk_token": "<e>",
            }
        ),
        "tokenizer_config.json": _json_bytes(
            {
                "auto_map": tokenizer_auto_map,
                "bos_token": "<e>",
                "eos_token": "<e>",
                "tokenizer_class": "FixtureTokenizer",
                "unk_token": "<e>",
            }
        ),
        "tokenizer.json": _json_bytes(
            {
                "added_tokens": [],
                "model": {"type": "BPE", "vocab": {"<e>": 0, "x": 1}},
            }
        ),
    }
    for filename, payload in payloads.items():
        (snapshot / filename).write_bytes(payload)
    artifact: dict[str, object] = {
        "id": "fixture-main",
        "repository": artifact_repository,
        "revision": REVISION,
        "model_type": "fixture",
        "architecture": "FixtureModel",
        "tokenizer_runtime": {
            "class": "FixtureTokenizer",
            "is_fast": True,
            "native_prefix_policy": "none",
            "native_special_tokens_to_add": 0,
            "vocab_size": 2,
            "tokenizer_length": 2,
            "special_tokens": {
                "bos_token": "<e>",
                "eos_token": "<e>",
                "pad_token": None,
                "unk_token": "<e>",
            },
            "special_token_ids": {
                "bos_token_id": 0,
                "eos_token_id": 0,
                "pad_token_id": None,
                "unk_token_id": 0,
            },
            "backend_sha256": "f" * 64,
        },
        "required_files": [
            {
                "filename": filename,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for filename, payload in sorted(payloads.items())
        ],
    }
    return cache, snapshot, artifact


def test_exact_snapshot_verifies_with_portable_self_hash(tmp_path: Path) -> None:
    cache, snapshot, artifact = _snapshot_fixture(tmp_path)

    result = verify_snapshot(snapshot, cache, artifact)

    receipt = dict(result["portable_receipt"])
    recorded = receipt.pop("receipt_sha256")
    assert recorded == canonical_json_sha256(receipt)
    assert result["resolved_revision"] == REVISION
    assert result["tokenizer_config"]["vocab_size"] == 2
    assert str(tmp_path) not in json.dumps(result["portable_receipt"])


def test_portable_receipt_is_cache_root_independent(tmp_path: Path) -> None:
    first_cache, first_snapshot, first_artifact = _snapshot_fixture(
        tmp_path / "first"
    )
    second_cache, second_snapshot, second_artifact = _snapshot_fixture(
        tmp_path / "second"
    )

    first = verify_snapshot(first_snapshot, first_cache, first_artifact)
    second = verify_snapshot(second_snapshot, second_cache, second_artifact)

    assert first["portable_receipt"] == second["portable_receipt"]


def test_snapshot_requires_exact_repository_and_revision_layout(
    tmp_path: Path,
) -> None:
    cache, snapshot, artifact = _snapshot_fixture(
        tmp_path,
        artifact_repository="owner/model",
        directory_repository="other/model",
    )

    with pytest.raises(RuntimeError, match="repository cache|repository/revision"):
        verify_snapshot(snapshot, cache, artifact)

    cache, snapshot, artifact = _snapshot_fixture(tmp_path / "revision")
    with pytest.raises(RuntimeError, match="caller revision"):
        verify_snapshot(snapshot, cache, artifact, "b" * 40)


def test_snapshot_rejects_missing_unexpected_and_tampered_files(
    tmp_path: Path,
) -> None:
    cache, snapshot, artifact = _snapshot_fixture(tmp_path / "missing")
    (snapshot / "tokenizer.json").unlink()
    with pytest.raises(RuntimeError, match="missing"):
        verify_snapshot(snapshot, cache, artifact)

    cache, snapshot, artifact = _snapshot_fixture(tmp_path / "unexpected")
    (snapshot / "unexpected").mkdir()
    with pytest.raises(RuntimeError, match="outside the exact allowlist"):
        verify_snapshot(snapshot, cache, artifact)

    cache, snapshot, artifact = _snapshot_fixture(tmp_path / "tampered")
    (snapshot / "tokenizer.json").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="size mismatch|SHA-256 mismatch"):
        verify_snapshot(snapshot, cache, artifact)


def test_snapshot_rejects_tokenizer_custom_code(tmp_path: Path) -> None:
    cache, snapshot, artifact = _snapshot_fixture(
        tmp_path,
        tokenizer_auto_map={"AutoTokenizer": "custom.Tokenizer"},
    )

    with pytest.raises(RuntimeError, match="tokenizer config.*auto_map"):
        verify_snapshot(snapshot, cache, artifact)


def _symlink_or_skip(target: Path, link: Path, *, directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=directory)
    except OSError as error:
        if directory and os.name == "nt":
            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode == 0:
                return
        pytest.skip(f"symlink creation is unavailable: {error}")


def test_hub_leaf_link_must_resolve_inside_repository_blobs(
    tmp_path: Path,
) -> None:
    cache, snapshot, artifact = _snapshot_fixture(tmp_path / "inside")
    repository_cache = snapshot.parents[1]
    blobs = repository_cache / "blobs"
    blobs.mkdir()
    target = blobs / "config-blob"
    target.write_bytes((snapshot / "config.json").read_bytes())
    (snapshot / "config.json").unlink()
    _symlink_or_skip(target, snapshot / "config.json")

    assert verify_snapshot(snapshot, cache, artifact)["status"] == "verified"

    cache, snapshot, artifact = _snapshot_fixture(tmp_path / "outside")
    outside = tmp_path / "outside-config.json"
    outside.write_bytes((snapshot / "config.json").read_bytes())
    (snapshot / "config.json").unlink()
    _symlink_or_skip(outside, snapshot / "config.json")
    with pytest.raises(RuntimeError, match="outside the selected repository cache"):
        verify_snapshot(snapshot, cache, artifact)


def test_snapshot_rejects_linked_intermediate_directory(tmp_path: Path) -> None:
    cache, snapshot, artifact = _snapshot_fixture(tmp_path)
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    linked = snapshot / "unexpected-dir"
    _symlink_or_skip(outside, linked, directory=True)

    with pytest.raises(RuntimeError, match="outside the exact allowlist"):
        verify_snapshot(snapshot, cache, artifact)


@pytest.mark.parametrize("linked_level", ["repository", "snapshot"])
def test_snapshot_rejects_linked_identity_directories(
    linked_level: str,
    tmp_path: Path,
) -> None:
    cache, snapshot, artifact = _snapshot_fixture(tmp_path)
    selected = snapshot.parents[1] if linked_level == "repository" else snapshot
    outside = tmp_path / f"{linked_level}-target"
    selected.rename(outside)
    _symlink_or_skip(outside, selected, directory=True)

    with pytest.raises(RuntimeError, match="symlink or reparse point"):
        verify_snapshot(snapshot, cache, artifact)


def test_snapshot_rejects_alias_to_valid_exact_snapshot(tmp_path: Path) -> None:
    cache, snapshot, artifact = _snapshot_fixture(tmp_path)
    alias = tmp_path / "snapshot-alias"
    _symlink_or_skip(snapshot, alias, directory=True)

    with pytest.raises(RuntimeError, match="exact repository/revision cache locator"):
        verify_snapshot(alias, cache, artifact)


def test_snapshot_rejects_cache_path_through_linked_parent(tmp_path: Path) -> None:
    actual_root = tmp_path / "actual-root"
    cache, snapshot, artifact = _snapshot_fixture(actual_root)
    alias_root = tmp_path / "alias-root"
    _symlink_or_skip(actual_root, alias_root, directory=True)
    alias_cache = alias_root / cache.relative_to(actual_root)
    alias_snapshot = alias_root / snapshot.relative_to(actual_root)

    with pytest.raises(RuntimeError, match="must not traverse"):
        verify_snapshot(alias_snapshot, alias_cache, artifact)
