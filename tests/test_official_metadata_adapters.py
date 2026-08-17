from __future__ import annotations

import json
from pathlib import Path

import pytest

from chronopersona.bounded_metadata_network import (
    AccessLogEntry,
    BoundedNetworkError,
    append_access_log,
    bounded_fetch,
)
from chronopersona.official_metadata_adapters import (
    canonical_sha256,
    parse_arxiv_raw_oai,
    parse_pmc_oai_dc,
    parse_stackexchange_archive_inventory,
    parse_wikimedia_dumpstatus,
    redact_locator,
    sanitize_request_url,
)
from chronopersona.source_c_blinding import blind_source_c_records


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "official_metadata"


def test_arxiv_raw_parser_uses_native_submission_date_and_omits_text() -> None:
    records = parse_arxiv_raw_oai(
        (FIXTURES / "arxiv-oai-arxivraw.xml").read_bytes(),
        max_records=10,
    )

    assert len(records) == 2
    first, second = records
    assert first.native_id == "1201.00001"
    assert first.native_timestamp == "2012-01-03T00:00:00Z"
    assert first.timestamp_semantics == "initial-submission-date"
    assert first.version_count == 1
    assert first.eligible_for_bounded_review is True
    assert first.categories == ("physics.bio-ph", "q-bio.PE")
    assert second.version_count == 2
    assert "not-single-version" in second.exclusion_reasons

    rendered = json.dumps([record.as_dict() for record in records])
    assert "This title must not appear" not in rendered
    assert "This abstract must not appear" not in rendered
    assert "Another omitted title" not in rendered


def test_pmc_missing_date_is_none_not_a_sentinel() -> None:
    records = parse_pmc_oai_dc(
        (FIXTURES / "pmc-oai-dc.xml").read_bytes(),
        max_records=10,
    )

    assert len(records) == 2
    dated, missing = records
    assert dated.native_id == "PMC1200001"
    assert dated.native_timestamp == "2012-03-14T00:00:00Z"
    assert "historical-version-integrity-unverified" in dated.exclusion_reasons
    assert missing.native_id == "PMC1900002"
    assert missing.native_timestamp is None
    assert missing.timestamp_status == "missing"
    assert "missing-native-publication-date" in missing.exclusion_reasons

    rendered = json.dumps([record.as_dict() for record in records])
    assert "Missing-date fixture" not in rendered
    assert "No date is provided" not in rendered
    assert "1900-01-01" not in rendered
    assert "1970-01-01" not in rendered


def test_wikimedia_inventory_selects_history_files_only() -> None:
    inventory = parse_wikimedia_dumpstatus(
        (FIXTURES / "wikimedia-dumpstatus.json").read_bytes(),
        base_url="https://dumps.wikimedia.org/enwiki/20130101",
        max_files=10,
    )

    assert len(inventory) == 1
    assert "pages-meta-history" in inventory[0]["name"]
    assert inventory[0]["size_bytes"] == 123456
    assert inventory[0]["hashes"]["sha1"] == "1" * 40
    assert "pages-meta-current" not in json.dumps(inventory)


def test_stackexchange_inventory_is_allowlisted_and_never_downloads_archives() -> None:
    inventory = parse_stackexchange_archive_inventory(
        (FIXTURES / "stackexchange-archive-metadata.json").read_bytes(),
        archive_base_url="https://archive.org/download/stackexchange",
        max_files=10,
        allowed_sites=(
            "gardening.stackexchange.com",
            "history.stackexchange.com",
        ),
    )

    assert [entry["metadata"]["site"] for entry in inventory] == [
        "gardening.stackexchange.com",
        "history.stackexchange.com",
    ]
    assert all(entry["name"].endswith(".7z") for entry in inventory)
    assert "stackoverflow.com.7z" not in json.dumps(inventory)


def test_source_c_packet_removes_native_identity_date_and_usable_locators() -> None:
    records = parse_arxiv_raw_oai(
        (FIXTURES / "arxiv-oai-arxivraw.xml").read_bytes(),
        max_records=1,
    )
    packet, key = blind_source_c_records(records, secret=b"fixture-secret")

    packet_text = json.dumps(packet, sort_keys=True)
    assert "1201.00001" not in packet_text
    assert "2012-01-03" not in packet_text
    assert "export.arxiv.org" not in packet_text
    assert "arxiv.org/src" not in packet_text
    assert "sourcec://" in packet_text

    key_text = json.dumps(key, sort_keys=True)
    assert "1201.00001" in key_text
    assert "2012-01-03" in key_text
    assert key["packet_sha256"] == packet["packet_sha256"]


def test_blinding_and_canonical_hashes_are_deterministic() -> None:
    records = parse_arxiv_raw_oai(
        (FIXTURES / "arxiv-oai-arxivraw.xml").read_bytes(),
        max_records=1,
    )
    packet_a, key_a = blind_source_c_records(records, secret=b"same-secret")
    packet_b, key_b = blind_source_c_records(records, secret=b"same-secret")

    assert packet_a == packet_b
    assert key_a == key_b
    assert canonical_sha256(packet_a) == canonical_sha256(packet_b)
    assert redact_locator("https://example.test/item/1", b"x") == redact_locator(
        "https://example.test/item/1", b"x"
    )


def test_access_log_url_sanitization_keeps_keys_not_values() -> None:
    sanitized = sanitize_request_url(
        "https://export.arxiv.org/oai2?verb=ListRecords&from=2012-01-01&until=2013-12-31"
    )

    assert sanitized.startswith("https://export.arxiv.org/oai2?")
    assert "verb=%3Credacted%3E" in sanitized
    assert "from=%3Credacted%3E" in sanitized
    assert "2012-01-01" not in sanitized


def test_bounded_fetch_rejects_unapproved_hosts_before_network() -> None:
    with pytest.raises(BoundedNetworkError, match="not allowlisted"):
        bounded_fetch(
            "https://example.test/metadata",
            allowed_hosts={"export.arxiv.org"},
            max_bytes=100,
            timeout_seconds=1,
            user_agent="test-agent",
            access_log=ROOT / "artifacts" / "local" / "never-created.jsonl",
        )


def test_access_log_is_append_only_jsonl(tmp_path: Path) -> None:
    entry = AccessLogEntry(
        schema_version=1,
        started_at="2026-08-17T00:00:00Z",
        completed_at="2026-08-17T00:00:01Z",
        sanitized_url="https://example.test/oai?verb=%3Credacted%3E",
        host="example.test",
        status_code=200,
        response_bytes=3,
        response_sha256="a" * 64,
        content_type="application/xml",
        max_bytes=100,
        timeout_seconds=1.0,
        user_agent="test-agent",
    )
    path = tmp_path / "access.jsonl"

    append_access_log(path, entry)
    append_access_log(path, entry)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == json.loads(lines[1])
