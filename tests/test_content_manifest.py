from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from chronopersona.content_manifest import (
    ContentManifestError,
    load_content_manifest,
    resolve_content_records,
    validate_content_manifest_structure,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "content-integrity"
MANIFEST = FIXTURE_ROOT / "manifest.jsonl"
DOCUMENTS = FIXTURE_ROOT / "documents"


def test_committed_content_fixture_is_valid() -> None:
    records = load_content_manifest(MANIFEST)
    assert validate_content_manifest_structure(records) == ()

    loaded = resolve_content_records(records, content_root=DOCUMENTS)
    assert len(loaded) == 13
    assert {record.manifest["source_family"] for record in loaded} == {
        "A",
        "B",
        "C",
        "EVAL",
        "CONTROL",
        "CAL",
    }


def test_content_hash_mismatch_fails_closed() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {**records[0], "content_sha256": "0" * 64}

    with pytest.raises(ContentManifestError, match="content_sha256 mismatch"):
        resolve_content_records(records, content_root=DOCUMENTS)


def test_normalized_hash_mismatch_fails_closed() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {**records[0], "normalized_sha256": "0" * 64}

    with pytest.raises(ContentManifestError, match="normalized_sha256 mismatch"):
        resolve_content_records(records, content_root=DOCUMENTS)


def test_path_escape_is_rejected() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {**records[0], "content_path": "../outside.txt"}

    errors = validate_content_manifest_structure(records)
    assert any("portable" in error for error in errors)


def test_nested_raw_text_field_is_rejected() -> None:
    records = list(load_content_manifest(MANIFEST))
    changed = copy.deepcopy(records[0])
    changed["metadata"]["nested"] = {"body": "forbidden"}
    records[0] = changed

    errors = validate_content_manifest_structure(records)
    assert any("forbidden text fields" in error for error in errors)


def test_source_c_requires_confirmatory_holdout() -> None:
    records = list(load_content_manifest(MANIFEST))
    index = next(
        index
        for index, record in enumerate(records)
        if record["source_family"] == "C"
    )
    records[index] = {**records[index], "holdout_status": "exploratory"}

    errors = validate_content_manifest_structure(records)
    assert any("source C must be confirmatory-held-out" in error for error in errors)


def test_symlink_content_file_is_rejected(tmp_path: Path) -> None:
    if not hasattr(Path, "symlink_to"):
        pytest.skip("symlinks unsupported")
    records = list(load_content_manifest(MANIFEST))
    source = DOCUMENTS / records[0]["content_path"]
    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation not permitted")
    records[0] = {**records[0], "content_path": "linked.txt"}

    with pytest.raises(ContentManifestError, match="symbolic links"):
        resolve_content_records(records, content_root=tmp_path)


def test_manifest_rejects_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    first = MANIFEST.read_text(encoding="utf-8").splitlines()[0]
    path.write_text(first + "\n\n", encoding="utf-8")

    with pytest.raises(ContentManifestError, match="blank line"):
        load_content_manifest(path)


def test_windows_style_parent_traversal_is_rejected() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {**records[0], "content_path": r"..\outside.txt"}

    errors = validate_content_manifest_structure(records)
    assert any("portable" in error for error in errors)


def test_windows_drive_path_is_rejected() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {**records[0], "content_path": r"C:\outside.txt"}

    errors = validate_content_manifest_structure(records)
    assert any("portable" in error for error in errors)
