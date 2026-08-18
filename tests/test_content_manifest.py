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


def test_synthetic_fixture_requires_matching_authorship_provenance() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {
        **records[0],
        "authorship_provenance": "human",
    }

    errors = validate_content_manifest_structure(records)
    assert any(
        "synthetic fixture requires synthetic-fixture authorship" in error
        for error in errors
    )


def test_nonfixture_record_cannot_claim_synthetic_fixture_authorship() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {
        **records[0],
        "synthetic_fixture": False,
    }

    errors = validate_content_manifest_structure(records)
    assert any(
        "synthetic-fixture authorship requires synthetic_fixture=true" in error
        for error in errors
    )


def test_windows_reserved_content_path_is_rejected() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[0] = {**records[0], "content_path": "NUL.txt"}

    errors = validate_content_manifest_structure(records)
    assert any("Windows-reserved" in error for error in errors)


def test_content_read_limits_fail_before_unbounded_access() -> None:
    records = load_content_manifest(MANIFEST)

    with pytest.raises(ContentManifestError, match="exceeding max_records=12"):
        resolve_content_records(
            records,
            content_root=DOCUMENTS,
            max_records=12,
        )

    with pytest.raises(ContentManifestError, match="max_record_bytes=8"):
        resolve_content_records(
            records,
            content_root=DOCUMENTS,
            max_record_bytes=8,
            max_total_content_bytes=1024,
        )

    with pytest.raises(
        ContentManifestError,
        match="max_total_content_bytes=256",
    ):
        resolve_content_records(
            records,
            content_root=DOCUMENTS,
            max_record_bytes=256,
            max_total_content_bytes=256,
        )


def test_observed_file_size_cannot_bypass_declared_limit(tmp_path: Path) -> None:
    record = dict(load_content_manifest(MANIFEST)[0])
    record["content_path"] = "oversized.txt"
    record["content_bytes"] = 8
    (tmp_path / "oversized.txt").write_bytes(b"x" * 11)

    with pytest.raises(ContentManifestError, match="exceeding max_record_bytes=10"):
        resolve_content_records(
            [record],
            content_root=tmp_path,
            max_record_bytes=10,
            max_total_content_bytes=10,
        )


def test_content_paths_cannot_collide_by_case() -> None:
    records = list(load_content_manifest(MANIFEST))
    records[1] = {**records[1], "content_path": records[0]["content_path"].upper()}

    errors = validate_content_manifest_structure(records)
    assert any("portable filesystem semantics" in error for error in errors)


def test_manifest_loader_enforces_record_limit_before_full_load(
    tmp_path: Path,
) -> None:
    first = MANIFEST.read_text(encoding="utf-8").splitlines()[0]
    path = tmp_path / "oversized.jsonl"
    path.write_text((first + "\n") * 3, encoding="utf-8")

    with pytest.raises(ContentManifestError, match="exceeds max_records=2"):
        load_content_manifest(path, max_records=2)


@pytest.mark.parametrize("invalid_max_records", [True, False, 0, -1, 1.0, "1"])
def test_manifest_loader_requires_positive_integer_record_limit(
    invalid_max_records: object,
) -> None:
    with pytest.raises(ContentManifestError, match="max_records must be"):
        load_content_manifest(
            MANIFEST,
            max_records=invalid_max_records,  # type: ignore[arg-type]
        )
