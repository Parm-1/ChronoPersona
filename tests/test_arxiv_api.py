from __future__ import annotations

from datetime import date
from pathlib import Path

from chronopersona.source_adapters.arxiv_api import parse_arxiv_api_feed
from chronopersona.source_metadata import EraWindows, validate_source_metadata
from chronopersona.source_registry import load_source_registry


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "arxiv_api_sample.xml"
SOURCE_REGISTRY = ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json"
WINDOWS = EraWindows(
    early_start=date(2012, 1, 1),
    early_end=date(2013, 12, 31),
    late_start=date(2018, 1, 1),
    late_end=date(2019, 12, 31),
)


def test_arxiv_api_enumerates_submission_date_candidates_without_claiming_eligibility() -> None:
    records, page = parse_arxiv_api_feed(
        FIXTURE.read_bytes(),
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

    assert page == {
        "total_results": 3,
        "start_index": 0,
        "items_per_page": 3,
    }
    assert [record["native_item_id"] for record in records] == [
        "1301.00001",
        "1907.00003",
        "1905.00002",
    ]
    assert [record["era_window"] for record in records] == [
        "early",
        "late",
        "late",
    ]
    assert all(record["eligibility"] == "unresolved" for record in records)
    assert all(record["version_status"] == "unresolved" for record in records)
    assert all(record["rights_status"] == "unresolved" for record in records)
    assert all(
        "version-enrichment-required" in record["exclusion_reasons"]
        for record in records
    )
    assert all(
        "license-enrichment-required" in record["exclusion_reasons"]
        for record in records
    )

    first, cross_listed, revised = records
    assert first["source_metadata"]["returned_version"] == 1
    assert first["source_metadata"]["published_equals_updated"] is True
    assert first["review_strata"] == ["rights-boundary"]
    assert "title" not in first
    assert "abstract" not in first

    assert cross_listed["source_metadata"]["category_forbidden"] is True
    assert "forbidden-cross-list-category" in cross_listed["exclusion_reasons"]
    assert cross_listed["review_strata"] == ["exposure-boundary"]

    assert revised["source_metadata"]["returned_version"] == 2
    assert revised["source_metadata"]["published_equals_updated"] is False
    assert revised["native_item_id"] == "1905.00002"

    assert validate_source_metadata(
        records,
        source_registry=load_source_registry(SOURCE_REGISTRY),
    ) == ()
