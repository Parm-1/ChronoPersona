from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from pathlib import Path

import pytest

from chronopersona.source_adapters.arxiv_oai import (
    ArxivMetadataError,
    parse_arxiv_raw_oai,
)
from chronopersona.source_adapters.pmc_oai import (
    PmcMetadataError,
    parse_pmc_oai_dc,
)
from chronopersona.source_adapters.stackexchange_inventory import (
    parse_stackexchange_archive_metadata,
)
from chronopersona.source_adapters.wikimedia_inventory import (
    WikimediaInventoryError,
    parse_wikimedia_dumpstatus,
)
from chronopersona.source_inventory import validate_source_inventory
from chronopersona.source_metadata import (
    EraWindows,
    validate_source_metadata,
)
from chronopersona.source_registry import load_source_registry


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
SOURCE_REGISTRY = ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json"
WINDOWS = EraWindows(
    early_start=date(2012, 1, 1),
    early_end=date(2013, 12, 31),
    late_start=date(2018, 1, 1),
    late_end=date(2019, 12, 31),
)


def _source_registry() -> dict:
    return load_source_registry(SOURCE_REGISTRY)


def test_arxiv_oai_qualifies_only_single_version_non_cross_listed_record() -> None:
    records, token, diagnostics = parse_arxiv_raw_oai(
        (FIXTURES / "arxiv_oai_sample.xml").read_bytes(),
        windows=WINDOWS,
        allowed_category_prefixes=(
            "astro-ph",
            "cond-mat.mtrl-sci",
            "physics.atom-ph",
            "physics.chem-ph",
            "physics.optics",
        ),
        forbidden_category_prefixes=("cs", "econ", "math", "q-fin", "stat"),
    )

    assert token is None
    assert diagnostics == {
        "records_seen": 4,
        "deleted_records": 1,
        "records_without_metadata": 0,
    }
    assert len(records) == 3

    eligible, multiversion, cross_listed = records
    assert eligible["record_id"] == "arxiv:1301.00001v1"
    assert eligible["era_window"] == "early"
    assert eligible["eligibility"] == "eligible"
    assert eligible["version_status"] == "single-version"
    assert eligible["source_metadata"]["author_count"] == 1
    assert "abstract" not in eligible
    assert "title" not in eligible

    assert multiversion["eligibility"] == "excluded"
    assert "multiple-versions-heldout" in multiversion["exclusion_reasons"]
    assert multiversion["version_count"] == 2

    assert cross_listed["eligibility"] == "excluded"
    assert "forbidden-cross-list-category" in cross_listed["exclusion_reasons"]
    assert cross_listed["source_metadata"]["category_forbidden"] is True

    assert validate_source_metadata(
        records,
        source_registry=_source_registry(),
    ) == ()


def test_arxiv_oai_error_is_not_treated_as_empty_result() -> None:
    xml = b"""<?xml version='1.0'?>
    <OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>
      <error code='badArgument'>invalid request</error>
    </OAI-PMH>"""

    with pytest.raises(ArxivMetadataError, match="badArgument"):
        parse_arxiv_raw_oai(
            xml,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


def test_pmc_oai_omits_missing_dates_without_inventing_epoch() -> None:
    records, token, diagnostics = parse_pmc_oai_dc(
        (FIXTURES / "pmc_oai_sample.xml").read_bytes(),
        windows=WINDOWS,
        allowed_subject_terms=(
            "cell biology",
            "molecular biology",
            "genetics",
            "biochemistry",
            "structural biology",
        ),
    )

    assert token is None
    assert diagnostics == {
        "records_seen": 4,
        "deleted_records": 1,
        "records_without_metadata": 0,
        "skipped_missing_publication_date": 1,
    }
    assert [record["native_item_id"] for record in records] == [
        "PMC12345",
        "PMC34567",
    ]
    assert all(not record["native_timestamp"].startswith("1970-") for record in records)
    assert records[0]["era_window"] == "late"
    assert records[0]["eligibility"] == "unresolved"
    assert records[0]["metadata_locator"].endswith(
        "identifier=oai%3Apubmedcentral.nih.gov%3A12345"
    )
    assert records[1]["era_window"] == "outside"
    assert records[1]["source_metadata"]["publication_date_precision"] == "year"

    assert validate_source_metadata(
        records,
        source_registry=_source_registry(),
    ) == ()


def test_pmc_oai_error_is_visible() -> None:
    xml = b"""<?xml version='1.0'?>
    <OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>
      <error code='noRecordsMatch'>none</error>
    </OAI-PMH>"""

    with pytest.raises(PmcMetadataError, match="noRecordsMatch"):
        parse_pmc_oai_dc(
            xml,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )


def test_wikimedia_inventory_uses_explicit_snapshot_not_schema_version() -> None:
    payload = json.loads(
        (FIXTURES / "wikimedia_dumpstatus_sample.json").read_text(encoding="utf-8")
    )
    records = parse_wikimedia_dumpstatus(
        payload,
        source_locator=(
            "https://dumps.wikimedia.org/enwiki/20260101/dumpstatus.json"
        ),
        snapshot_id="20260101",
    )

    assert len(records) == 1
    record = records[0]
    assert record["snapshot_id"] == "20260101"
    assert record["source_metadata"]["dumpstatus_schema_version"] == "0.8"
    assert record["locator"] == (
        "https://dumps.wikimedia.org/enwiki/20260101/"
        "enwiki-20260101-pages-meta-history1.xml-p1p10.bz2"
    )
    assert validate_source_inventory(records) == ()


def test_wikimedia_inventory_rejects_mutable_snapshot_identity() -> None:
    payload = json.loads(
        (FIXTURES / "wikimedia_dumpstatus_sample.json").read_text(encoding="utf-8")
    )

    with pytest.raises(WikimediaInventoryError, match="YYYYMMDD"):
        parse_wikimedia_dumpstatus(
            payload,
            source_locator="https://dumps.wikimedia.org/enwiki/latest/dumpstatus.json",
            snapshot_id="latest",
        )


def test_stackexchange_inventory_records_legacy_company_provenance() -> None:
    payload = json.loads(
        (FIXTURES / "stackexchange_archive_sample.json").read_text(encoding="utf-8")
    )
    records = parse_stackexchange_archive_metadata(
        payload,
        source_locator="https://archive.org/metadata/stackexchange",
    )

    assert len(records) == 2
    assert validate_source_inventory(records) == ()
    assert all(
        record["source_metadata"]["company_attributed_archive_item"] is True
        for record in records
    )
    assert all(
        record["source_metadata"]["delivery_status"]
        == "legacy-archive; not current official delivery"
        for record in records
    )
    assert records[0]["snapshot_id"].startswith("stackexchange@")
    assert "%20" not in records[0]["locator"]
