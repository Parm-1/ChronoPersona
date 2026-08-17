from datetime import date
from pathlib import Path

from chronopersona.source_adapters.pmc_oai import parse_pmc_oai_dc
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
    assert all(record["era_window"] == "unresolved" for record in records)
