from __future__ import annotations

from copy import deepcopy

from chronopersona.source_inventory import validate_source_inventory


def _record() -> dict:
    return {
        "schema_version": 1,
        "inventory_id": "fixture:one",
        "source_id": "fixture-source",
        "snapshot_id": "20260818",
        "file_name": "fixture.xml.bz2",
        "locator": "https://example.invalid/fixture.xml.bz2",
        "content_kind": "metadata-export",
        "size_bytes": 123,
        "hashes": {
            "md5": "0" * 32,
            "sha1": "1" * 40,
            "sha256": "2" * 64,
        },
        "downloaded": False,
        "download_authorized": False,
        "source_metadata": {"format": "fixture"},
    }


def test_valid_inventory_record_passes() -> None:
    assert validate_source_inventory([_record()]) == ()


def test_inventory_hashes_require_exact_lowercase_digest_identity() -> None:
    for algorithm, invalid in (
        ("md5", "A" * 32),
        ("sha1", "1" * 39),
        ("sha256", "not-a-digest"),
    ):
        record = deepcopy(_record())
        record["hashes"][algorithm] = invalid

        errors = validate_source_inventory([record])
        assert any(
            f"hashes.{algorithm} must be a lowercase" in error
            for error in errors
        )


def test_inventory_metadata_recursively_rejects_source_text() -> None:
    record = _record()
    record["source_metadata"]["nested"] = {
        "body": "This payload must not enter a metadata-only inventory."
    }

    errors = validate_source_inventory([record])
    assert any(
        "source_metadata.nested.body" in error
        for error in errors
    )
