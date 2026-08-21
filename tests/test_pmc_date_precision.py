from datetime import date
from pathlib import Path

import pytest

from chronopersona.source_adapters.pmc_oai import _license, parse_pmc_oai_dc
from chronopersona.source_metadata import EraWindows


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = EraWindows(
    early_start=date(2012, 1, 1),
    early_end=date(2013, 12, 31),
    late_start=date(2018, 1, 1),
    late_end=date(2019, 12, 31),
)


def test_pmc_date_precision_distinguishes_day_and_year() -> None:
    records, _, _ = parse_pmc_oai_dc(
        (ROOT / "tests" / "fixtures" / "pmc_oai_sample.xml").read_bytes(),
        windows=WINDOWS,
        allowed_subject_terms=("genetics", "biochemistry"),
    )

    by_id = {record["native_item_id"]: record for record in records}
    assert by_id["PMC12345"]["source_metadata"]["lifecycle_date_precision"] == "day"
    assert by_id["PMC34567"]["source_metadata"]["lifecycle_date_precision"] == "year"
    assert by_id["PMC12345"]["source_metadata"]["rights_value_count"] == 1
    assert len(by_id["PMC12345"]["source_metadata"]["rights_values_sha256"]) == 64
    assert all(record["era_window"] == "unresolved" for record in records)


def test_pmc_rights_evidence_never_persists_arbitrary_prose_as_locator() -> None:
    license_id, status, locator = _license(
        ["This article may be reused under terms described by the publisher."]
    )

    assert license_id == "custom-or-unresolved"
    assert status == "unresolved"
    assert locator.startswith("rights-sha256:")
    assert "publisher" not in locator


def test_pmc_exact_license_url_is_normalized() -> None:
    assert _license(["http://creativecommons.org/licenses/by/4.0/"]) == (
        "CC-BY-4.0",
        "eligible",
        "https://creativecommons.org/licenses/by/4.0/",
    )


@pytest.mark.parametrize(
    "value",
    [
        "https://creativecommons.org/licenses/by/999.0/",
        "https://creativecommons.org/publicdomain/zero/999.0/",
        "CC BY 999.0",
        "CC0 999.0",
    ],
)
def test_pmc_unknown_creative_commons_versions_are_not_eligible(value: str) -> None:
    _, status, locator = _license([value])
    assert status != "eligible"
    assert locator.startswith("rights-sha256:")
