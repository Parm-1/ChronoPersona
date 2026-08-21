from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from chronopersona.source_adapters.arxiv_api import (
    ArxivApiError,
    parse_arxiv_api_feed,
)
from chronopersona.source_adapters.arxiv_oai import (
    ArxivMetadataError,
    _license as _arxiv_license,
    parse_arxiv_raw_oai,
)
from chronopersona.source_adapters.pmc_oai import (
    PmcMetadataError,
    parse_pmc_oai_dc,
)
from chronopersona.source_adapters.stackexchange_inventory import (
    StackExchangeInventoryError,
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
    assert cross_listed["categories"] == [
        "astro-ph.IM",
        "forbidden-arxiv-category",
    ]
    assert cross_listed["source_metadata"]["raw_category_count"] == 2

    assert validate_source_metadata(
        records,
        source_registry=_source_registry(),
    ) == ()


def test_arxiv_oai_error_is_not_treated_as_empty_result() -> None:
    xml = b"""<?xml version='1.0'?>
    <OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>
      <responseDate>2026-08-20T00:00:00Z</responseDate>
      <request verb='ListRecords' metadataPrefix='arXivRaw'>https://oaipmh.arxiv.org/oai</request>
      <error code='badArgument'>invalid request</error>
    </OAI-PMH>"""

    with pytest.raises(ArxivMetadataError, match="badArgument"):
        parse_arxiv_raw_oai(
            xml,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


def test_pmc_oai_keeps_lifecycle_dates_unresolved_without_inventing_epoch() -> None:
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
        "skipped_missing_lifecycle_date": 1,
    }
    assert [record["native_item_id"] for record in records] == [
        "PMC12345",
        "PMC34567",
    ]
    assert all(not record["native_timestamp"].startswith("1970-") for record in records)
    assert all(record["era_window"] == "unresolved" for record in records)
    assert all(record["eligibility"] == "unresolved" for record in records)
    assert all(
        "timestamp-semantics-unresolved" in record["exclusion_reasons"]
        for record in records
    )
    assert records[0]["source_metadata"]["candidate_era_window"] == "late"
    assert records[0]["metadata_locator"].endswith(
        "identifier=oai%3Apubmedcentral.nih.gov%3A12345"
    )
    assert records[1]["source_metadata"]["candidate_era_window"] == "outside"
    assert records[1]["source_metadata"]["lifecycle_date_precision"] == "year"

    assert validate_source_metadata(
        records,
        source_registry=_source_registry(),
    ) == ()


def test_pmc_oai_error_is_visible() -> None:
    xml = b"""<?xml version='1.0'?>
    <OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>
      <responseDate>2026-08-20T00:00:00Z</responseDate>
      <request verb='ListRecords' metadataPrefix='oai_dc' set='pmc-open'>https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/</request>
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


def test_arxiv_oai_expected_identifier_rejects_prefix_collision() -> None:
    payload = (
        (FIXTURES / "arxiv_oai_sample.xml")
        .read_bytes()
        .replace(
            b'verb="ListRecords" metadataPrefix="arXivRaw"',
            b'verb="GetRecord" metadataPrefix="arXivRaw" identifier="oai:arXiv.org:1301.00002"',
        )
        .replace(b"<ListRecords>", b"<GetRecord>")
        .replace(b"</ListRecords>", b"</GetRecord>")
    )
    with pytest.raises(ArxivMetadataError, match="requested base identifier"):
        parse_arxiv_raw_oai(
            payload,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
            expected_base_identifier="1301.00002",
        )


@pytest.mark.parametrize(
    "escaped_url, expected",
    [
        (
            "https://example.org/enwiki/20260101/archive.bz2",
            "must be relative",
        ),
        (
            "https://dumps.wikimedia.org/enwiki/20260101/archive.bz2",
            "must be relative",
        ),
        (
            "https://dumps.wikimedia.org/enwiki/20260201/archive.bz2",
            "must be relative",
        ),
        ("/other-project/20260101/archive.bz2", "escapes the pinned"),
    ],
)
def test_wikimedia_inventory_rejects_file_url_escape(
    escaped_url: str,
    expected: str,
) -> None:
    payload = json.loads(
        (FIXTURES / "wikimedia_dumpstatus_sample.json").read_text(encoding="utf-8")
    )
    mutated = deepcopy(payload)
    history = mutated["jobs"]["metahistorybz2dump"]["files"]
    next(iter(history.values()))["url"] = escaped_url

    with pytest.raises(WikimediaInventoryError, match=expected):
        parse_wikimedia_dumpstatus(
            mutated,
            source_locator=(
                "https://dumps.wikimedia.org/enwiki/20260101/dumpstatus.json"
            ),
            snapshot_id="20260101",
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


def _atom_feed(
    *,
    entry_id: str = "https://arxiv.org/abs/1301.00001v1",
    published: str = "2013-01-15T12:00:00Z",
    updated: str = "2013-01-15T12:00:00Z",
    atom_namespace: str = "http://www.w3.org/2005/Atom",
) -> bytes:
    return f"""<?xml version='1.0'?>
    <feed xmlns='{atom_namespace}'
      xmlns:opensearch='http://a9.com/-/spec/opensearch/1.1/'>
      <opensearch:totalResults>1</opensearch:totalResults>
      <opensearch:startIndex>0</opensearch:startIndex>
      <opensearch:itemsPerPage>1</opensearch:itemsPerPage>
      <entry>
        <id>{entry_id}</id>
        <published>{published}</published>
        <updated>{updated}</updated>
        <title>Fixture title</title>
        <summary>Fixture summary</summary>
        <author><name>Fixture Author</name></author>
        <category term='astro-ph.GA'/>
      </entry>
    </feed>""".encode("utf-8")


def test_arxiv_atom_requires_exact_namespaces_and_temporal_order() -> None:
    with pytest.raises(ArxivApiError, match="Atom feed"):
        parse_arxiv_api_feed(
            _atom_feed(atom_namespace="urn:not-atom"),
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )
    for mutated in (
        _atom_feed(published=" 2013-01-15T12:00:00Z "),
        _atom_feed().replace(b"<published>", b"<published source='forged'>", 1),
        _atom_feed().replace(b"<published>", b"<published/><published>", 1),
    ):
        with pytest.raises(ArxivApiError, match="published field"):
            parse_arxiv_api_feed(
                mutated,
                windows=WINDOWS,
                allowed_category_prefixes=("astro-ph",),
            )
    with pytest.raises(ArxivApiError, match="timestamp is not canonical"):
        parse_arxiv_api_feed(
            _atom_feed(published="2013-01-15T13:00:00+01:00"),
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )
    with pytest.raises(ArxivApiError, match="canonical integer"):
        parse_arxiv_api_feed(
            _atom_feed().replace(
                b"<opensearch:totalResults>1</opensearch:totalResults>",
                b"<opensearch:totalResults>01</opensearch:totalResults>",
            ),
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


def test_arxiv_oai_rejects_noncanonical_version_timestamp_aliases() -> None:
    payload = (FIXTURES / "arxiv_oai_sample.xml").read_bytes()
    for replacement in (
        b"14 Jan 2013 12:00:00 GMT",
        b"Mon, 14 Jan 2013 13:00:00 +0100",
        b"Tue, 14 Jan 2013 12:00:00 GMT",
    ):
        mutated = payload.replace(b"Mon, 14 Jan 2013 12:00:00 GMT", replacement, 1)
        with pytest.raises(ArxivMetadataError, match="version date"):
            parse_arxiv_raw_oai(
                mutated,
                windows=WINDOWS,
                allowed_category_prefixes=("astro-ph",),
            )
    for mutated in (
        payload.replace(
            b"Mon, 14 Jan 2013 12:00:00 GMT",
            b" Mon, 14 Jan 2013 12:00:00 GMT ",
            1,
        ),
        payload.replace(b"<date>", b"<date source='forged'>", 1),
    ):
        with pytest.raises(ArxivMetadataError, match="field date"):
            parse_arxiv_raw_oai(
                mutated,
                windows=WINDOWS,
                allowed_category_prefixes=("astro-ph",),
            )
    with pytest.raises(ArxivApiError, match="precedes"):
        parse_arxiv_api_feed(
            _atom_feed(
                published="2013-01-15T12:00:00Z",
                updated="2012-01-15T12:00:00Z",
            ),
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


@pytest.mark.parametrize(
    "entry_id",
    [
        "https://evil.example/abs/1301.00001v1",
        "https://arxiv.org:80/abs/1301.00001v1",
        "http://arxiv.org:443/abs/1301.00001v1",
    ],
)
def test_arxiv_atom_rejects_noncanonical_entry_ids(entry_id: str) -> None:
    with pytest.raises(ArxivApiError, match="entry id"):
        parse_arxiv_api_feed(
            _atom_feed(entry_id=entry_id),
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


def test_arxiv_parsers_reject_unknown_text_inside_an_allowed_category() -> None:
    with pytest.raises(ArxivApiError, match="frozen stratum is unknown"):
        parse_arxiv_api_feed(
            _atom_feed().replace(b"astro-ph.GA", b"astro-ph.ArbitrarySecret"),
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )

    payload = (FIXTURES / "arxiv_oai_sample.xml").read_bytes().replace(
        b"astro-ph.GA",
        b"astro-ph.ArbitrarySecret",
    )
    with pytest.raises(ArxivMetadataError, match="frozen stratum is unknown"):
        parse_arxiv_raw_oai(
            payload,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.replace(
            b"<category term='astro-ph.GA'/>",
            b"<category term='astro-ph.GA' forged='1'/>",
            1,
        ),
        lambda payload: payload.replace(
            b"<category term='astro-ph.GA'/>",
            b"<category term='astro-ph.GA'><foreign>cs.AI</foreign></category>",
            1,
        ),
    ],
)
def test_arxiv_atom_rejects_malformed_decision_categories(mutation) -> None:
    with pytest.raises(ArxivApiError, match="category field"):
        parse_arxiv_api_feed(
            mutation(_atom_feed()),
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        (
            b"<categories>astro-ph.GA</categories>",
            b"<categories forged='1'>astro-ph.GA</categories>",
        ),
        (
            b"<categories>astro-ph.GA</categories>",
            b"<categories>astro-ph.GA<foreign>cs.AI</foreign></categories>",
        ),
        (
            b"<license>https://creativecommons.org/licenses/by/4.0/</license>",
            b"<license forged='1'>https://creativecommons.org/licenses/by/4.0/</license>",
        ),
        (
            b"<license>https://creativecommons.org/licenses/by/4.0/</license>",
            b"<license>https://creativecommons.org/licenses/by/4.0/"
            b"<foreign>all rights reserved</foreign></license>",
        ),
    ],
)
def test_arxiv_oai_rejects_malformed_decision_fields(
    field: bytes,
    replacement: bytes,
) -> None:
    payload = (FIXTURES / "arxiv_oai_sample.xml").read_bytes().replace(
        field,
        replacement,
        1,
    )
    with pytest.raises(ArxivMetadataError, match="field (categories|license)"):
        parse_arxiv_raw_oai(
            payload,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


def test_arxiv_oai_rejects_conflicting_license_and_header_status() -> None:
    payload = (FIXTURES / "arxiv_oai_sample.xml").read_bytes()
    conflicting_license = payload.replace(
        b"<license>https://creativecommons.org/licenses/by/4.0/</license>",
        b"<license>https://creativecommons.org/licenses/by/4.0/</license>"
        b"<license>all rights reserved</license>",
        1,
    )
    with pytest.raises(ArxivMetadataError, match="license.*singular"):
        parse_arxiv_raw_oai(
            conflicting_license,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )
    invalid_status = payload.replace(b"<header>", b"<header status='garbage'>", 1)
    with pytest.raises(ArxivMetadataError, match="header status"):
        parse_arxiv_raw_oai(
            invalid_status,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


def test_arxiv_oai_requires_exact_envelope_and_direct_id_fields() -> None:
    payload = (FIXTURES / "arxiv_oai_sample.xml").read_bytes()
    missing_response_date = payload.replace(
        b"<responseDate>2026-08-17T00:00:00Z</responseDate>",
        b"",
        1,
    )
    with pytest.raises(ArxivMetadataError, match="responseDate and request"):
        parse_arxiv_raw_oai(
            missing_response_date,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )

    nested_header_id = payload.replace(
        b"<identifier>oai:arXiv.org:1301.00001</identifier>",
        b"<wrapper><identifier>oai:arXiv.org:1301.00001</identifier></wrapper>",
        1,
    )
    with pytest.raises(ArxivMetadataError, match="header"):
        parse_arxiv_raw_oai(
            nested_header_id,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )

    nested_raw_id = payload.replace(
        b"<id>1301.00001</id>",
        b"<wrapper><id>1301.00001</id></wrapper>",
        1,
    )
    with pytest.raises(ArxivMetadataError, match="field id"):
        parse_arxiv_raw_oai(
            nested_raw_id,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )

    empty_duplicate_header_id = payload.replace(
        b"<identifier>oai:arXiv.org:1301.00001</identifier>",
        b"<identifier/><identifier>oai:arXiv.org:1301.00001</identifier>",
        1,
    )
    with pytest.raises(ArxivMetadataError, match="identifier.*singular"):
        parse_arxiv_raw_oai(
            empty_duplicate_header_id,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )


def test_arxiv_getrecord_rejects_even_an_empty_resumption_token() -> None:
    payload = (FIXTURES / "arxiv_oai_sample.xml").read_bytes()
    payload = payload.replace(
        b'verb="ListRecords" metadataPrefix="arXivRaw"',
        b'verb="GetRecord" metadataPrefix="arXivRaw" identifier="oai:arXiv.org:1301.00001"',
        1,
    )
    first_record_end = payload.index(b"</record>") + len(b"</record>")
    list_start = payload.index(b"<ListRecords>")
    payload = (
        payload[:list_start]
        + b"<GetRecord>"
        + payload[list_start + len(b"<ListRecords>") : first_record_end]
        + b"<resumptionToken /></GetRecord></OAI-PMH>"
    )
    with pytest.raises(ArxivMetadataError, match="resumption token"):
        parse_arxiv_raw_oai(
            payload,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
            expected_base_identifier="1301.00001",
        )


@pytest.mark.parametrize(
    "attributes",
    [
        b'completeListSize="03" cursor="0"',
        b'completeListSize="3" cursor="-1"',
        b'completeListSize="3" cursor="0" expirationDate="not-a-date"',
        b'completeListSize="3" cursor="0" expirationDate="2026-99-99T00:00:00Z"',
    ],
)
def test_arxiv_oai_rejects_noncanonical_resumption_token_attributes(
    attributes: bytes,
) -> None:
    payload = (FIXTURES / "arxiv_oai_sample.xml").read_bytes().replace(
        b'completeListSize="3" cursor="0"',
        attributes,
        1,
    )
    with pytest.raises(ArxivMetadataError, match="resumption token"):
        parse_arxiv_raw_oai(
            payload,
            windows=WINDOWS,
            allowed_category_prefixes=("astro-ph",),
        )

@pytest.mark.parametrize(
    "value",
    [
        "https://example.org/?x=creativecommons.org/licenses/by/4.0/",
        "https://creativecommons.org/licenses/by/4.0/evil",
        "https://creativecommons.org/licenses/by/999.0/",
        "arbitrary upstream rights prose",
    ],
)
def test_arxiv_oai_never_qualifies_or_persists_noncanonical_rights(
    value: str,
) -> None:
    _, status, locator = _arxiv_license(value)
    assert status != "eligible"
    assert locator.startswith("rights-sha256:")
    assert value not in locator


def test_pmc_oai_rejects_invalid_header_status_and_unbounded_token() -> None:
    payload = (FIXTURES / "pmc_oai_sample.xml").read_bytes()
    invalid_status = payload.replace(b"<header>", b"<header status='garbage'>", 1)
    with pytest.raises(PmcMetadataError, match="header status"):
        parse_pmc_oai_dc(
            invalid_status,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    whitespace_token = payload.replace(
        b'<resumptionToken completeListSize="4" cursor="0" />',
        b"<resumptionToken> TOKEN </resumptionToken>",
    )
    with pytest.raises(PmcMetadataError, match="resumption token"):
        parse_pmc_oai_dc(
            whitespace_token,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )
    token = b"A" * 4097
    oversized = payload.replace(
        b'<resumptionToken completeListSize="4" cursor="0" />',
        b"<resumptionToken>" + token + b"</resumptionToken>",
    )
    with pytest.raises(PmcMetadataError, match="resumption token"):
        parse_pmc_oai_dc(
            oversized,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )


def test_pmc_oai_requires_exact_envelope_header_and_set_membership() -> None:
    payload = (FIXTURES / "pmc_oai_sample.xml").read_bytes()
    missing_request = payload.replace(
        b'<request verb="ListRecords" metadataPrefix="oai_dc" set="pmc-open">https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/</request>',
        b"",
        1,
    )
    with pytest.raises(PmcMetadataError, match="responseDate and request"):
        parse_pmc_oai_dc(
            missing_request,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    nested_header_id = payload.replace(
        b"<identifier>oai:pubmedcentral.nih.gov:12345</identifier>",
        b"<wrapper><identifier>oai:pubmedcentral.nih.gov:12345</identifier></wrapper>",
        1,
    )
    with pytest.raises(PmcMetadataError, match="header"):
        parse_pmc_oai_dc(
            nested_header_id,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    missing_set = payload.replace(b"<setSpec>pmc-open</setSpec>", b"", 1)
    with pytest.raises(PmcMetadataError, match="setSpec"):
        parse_pmc_oai_dc(
            missing_set,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    wrong_request = payload.replace(
        b'metadataPrefix="oai_dc"',
        b'metadataPrefix="wrong-prefix"',
        1,
    )
    with pytest.raises(PmcMetadataError, match="request echo"):
        parse_pmc_oai_dc(
            wrong_request,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    nested_dc_identifier = payload.replace(
        b"<dc:identifier>PMC12345</dc:identifier>",
        b"<wrapper><dc:identifier>PMC12345</dc:identifier></wrapper>",
        1,
    ).replace(
        b"<dc:identifier>https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/</dc:identifier>",
        b"<wrapper><dc:identifier>https://pmc.ncbi.nlm.nih.gov/articles/PMC12345/</dc:identifier></wrapper>",
        1,
    )
    with pytest.raises(PmcMetadataError, match="identifiers do not match"):
        parse_pmc_oai_dc(
            nested_dc_identifier,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    for mutated in (
        payload.replace(
            b"<identifier>oai:pubmedcentral.nih.gov:12345</identifier>",
            b"<identifier> oai:pubmedcentral.nih.gov:12345 </identifier>",
            1,
        ),
        payload.replace(
            b"<identifier>oai:pubmedcentral.nih.gov:12345</identifier>",
            b"<identifier/><identifier>oai:pubmedcentral.nih.gov:12345</identifier>",
            1,
        ),
        payload.replace(
            b"<setSpec>pmc-open</setSpec>",
            b"<setSpec> pmc-open </setSpec>",
            1,
        ),
        payload.replace(
            b"<dc:date>2019-06-01</dc:date>",
            b"<dc:date> 2019-06-01 </dc:date>",
            1,
        ),
    ):
        with pytest.raises(PmcMetadataError, match="field is not exact"):
            parse_pmc_oai_dc(
                mutated,
                windows=WINDOWS,
                allowed_subject_terms=("genetics",),
            )

    token_child = payload.replace(
        b'<resumptionToken completeListSize="4" cursor="0" />',
        b"<resumptionToken><foreign>TOKEN</foreign></resumptionToken>",
    )
    with pytest.raises(PmcMetadataError, match="token is not structurally exact"):
        parse_pmc_oai_dc(
            token_child,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    wrapped_record = payload.replace(b"<record>", b"<wrapper><record>", 1).replace(
        b"</record>", b"</record></wrapper>", 1
    )
    with pytest.raises(PmcMetadataError, match="ListRecords fields"):
        parse_pmc_oai_dc(
            wrapped_record,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        (
            b"<dc:subject>Genetics</dc:subject>",
            b"<dc:subject forged='1'>Genetics</dc:subject>",
        ),
        (
            b"<dc:subject>Genetics</dc:subject>",
            b"<dc:subject>Genetics<foreign>not genetics</foreign></dc:subject>",
        ),
        (
            b"<dc:rights>https://creativecommons.org/licenses/by/4.0/</dc:rights>",
            b"<dc:rights forged='1'>https://creativecommons.org/licenses/by/4.0/</dc:rights>",
        ),
        (
            b"<dc:rights>https://creativecommons.org/licenses/by/4.0/</dc:rights>",
            b"<dc:rights>https://creativecommons.org/licenses/by/4.0/"
            b"<foreign>all rights reserved</foreign></dc:rights>",
        ),
        (
            b"<dc:rights>https://creativecommons.org/licenses/by/4.0/</dc:rights>",
            b"<dc:rights/><dc:rights>https://creativecommons.org/licenses/by/4.0/</dc:rights>",
        ),
    ],
)
def test_pmc_oai_rejects_malformed_decision_fields(
    field: bytes,
    replacement: bytes,
) -> None:
    payload = (FIXTURES / "pmc_oai_sample.xml").read_bytes().replace(
        field,
        replacement,
        1,
    )
    with pytest.raises(PmcMetadataError, match="(subject|rights) field"):
        parse_pmc_oai_dc(
            payload,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )


def test_pmc_oai_rejects_cross_page_header_reuse_including_deleted_ids() -> None:
    payload = (FIXTURES / "pmc_oai_sample.xml").read_bytes()
    seen: set[str] = set()
    parse_pmc_oai_dc(
        payload,
        windows=WINDOWS,
        allowed_subject_terms=("genetics",),
        seen_header_identifiers=seen,
    )
    assert "oai:pubmedcentral.nih.gov:45678" in seen
    with pytest.raises(PmcMetadataError, match="repeated across pages"):
        parse_pmc_oai_dc(
            payload,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
            seen_header_identifiers=seen,
        )


@pytest.mark.parametrize(
    "value",
    ["2019-W01", "20190115", "2019-01-15T12:00:00", "2019-01-15T12:00:00+01:00"],
)
def test_pmc_lifecycle_dates_reject_nonfrozen_iso_aliases(value: str) -> None:
    payload = (FIXTURES / "pmc_oai_sample.xml").read_bytes().replace(
        b"<dc:date>2019-06-01</dc:date>",
        f"<dc:date>{value}</dc:date>".encode("utf-8"),
        1,
    )
    with pytest.raises(PmcMetadataError, match="lifecycle date"):
        parse_pmc_oai_dc(
            payload,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

def test_pmc_oai_requires_exact_datestamp_deleted_id_and_subject_value() -> None:
    payload = (FIXTURES / "pmc_oai_sample.xml").read_bytes()
    partial_date = payload.replace(b"2026-01-10", b"2026-01", 1)
    with pytest.raises(PmcMetadataError, match="datestamp"):
        parse_pmc_oai_dc(
            partial_date,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    anonymous_deleted = payload.replace(
        b"<identifier>oai:pubmedcentral.nih.gov:45678</identifier>",
        b"",
        1,
    )
    with pytest.raises(PmcMetadataError, match="header identifier"):
        parse_pmc_oai_dc(
            anonymous_deleted,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    leading_zero_deleted = payload.replace(
        b"oai:pubmedcentral.nih.gov:45678",
        b"oai:pubmedcentral.nih.gov:045678",
        1,
    )
    with pytest.raises(PmcMetadataError, match="header identifier"):
        parse_pmc_oai_dc(
            leading_zero_deleted,
            windows=WINDOWS,
            allowed_subject_terms=("genetics",),
        )

    near_match = payload.replace(b"<dc:subject>Genetics</dc:subject>", b"<dc:subject>Epigenetics</dc:subject>", 1)
    records, _, _ = parse_pmc_oai_dc(
        near_match,
        windows=WINDOWS,
        allowed_subject_terms=("genetics",),
    )
    record = next(item for item in records if item["native_item_id"] == "PMC12345")
    assert record["categories"] == []
    assert record["source_metadata"]["subject_allowed"] is False


def test_wikimedia_inventory_rejects_prose_malformed_entry_and_leaf_mismatch() -> None:
    payload = json.loads(
        (FIXTURES / "wikimedia_dumpstatus_sample.json").read_text(encoding="utf-8")
    )
    locator = "https://dumps.wikimedia.org/enwiki/20260101/dumpstatus.json"

    prose_version = deepcopy(payload)
    prose_version["version"] = "arbitrary upstream prose"
    with pytest.raises(WikimediaInventoryError, match="schema version"):
        parse_wikimedia_dumpstatus(
            prose_version,
            source_locator=locator,
            snapshot_id="20260101",
            required_job_name="metahistorybz2dump",
        )

    malformed = deepcopy(payload)
    files = malformed["jobs"]["metahistorybz2dump"]["files"]
    first_name = next(iter(files))
    files[first_name] = "not-an-object"
    with pytest.raises(WikimediaInventoryError, match="metadata is malformed"):
        parse_wikimedia_dumpstatus(
            malformed,
            source_locator=locator,
            snapshot_id="20260101",
            required_job_name="metahistorybz2dump",
        )

    wrong_leaf = deepcopy(payload)
    first = next(iter(wrong_leaf["jobs"]["metahistorybz2dump"]["files"].values()))
    first["url"] = "/enwiki/20260101/different-pages-meta-history.xml.bz2"
    with pytest.raises(WikimediaInventoryError, match="escapes"):
        parse_wikimedia_dumpstatus(
            wrong_leaf,
            source_locator=locator,
            snapshot_id="20260101",
            required_job_name="metahistorybz2dump",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "../escape.7z"),
        ("size", True),
        ("size", 1.5),
        ("size", "01"),
        ("mtime", 1.5),
        ("mtime", "1e3"),
    ],
)
def test_stackexchange_inventory_rejects_nonportable_or_boolean_file_values(
    field: str,
    value: object,
) -> None:
    payload = json.loads(
        (FIXTURES / "stackexchange_archive_sample.json").read_text(encoding="utf-8")
    )
    payload["files"][0][field] = value
    with pytest.raises(StackExchangeInventoryError):
        parse_stackexchange_archive_metadata(
            payload,
            source_locator="https://archive.org/metadata/stackexchange",
        )


@pytest.mark.parametrize("raw_size", [True, 1.5, "01", "+1", "1e3"])
def test_wikimedia_inventory_rejects_noncanonical_file_size(raw_size: object) -> None:
    payload = json.loads(
        (FIXTURES / "wikimedia_dumpstatus_sample.json").read_text(encoding="utf-8")
    )
    history = payload["jobs"]["metahistorybz2dump"]["files"]
    next(iter(history.values()))["size"] = raw_size
    with pytest.raises(WikimediaInventoryError, match="invalid size"):
        parse_wikimedia_dumpstatus(
            payload,
            source_locator="https://dumps.wikimedia.org/enwiki/20260101/dumpstatus.json",
            snapshot_id="20260101",
            required_job_name="metahistorybz2dump",
        )
