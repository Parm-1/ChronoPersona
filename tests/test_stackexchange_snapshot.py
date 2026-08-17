from copy import deepcopy
import json
from pathlib import Path

import pytest

from chronopersona.source_adapters.stackexchange_inventory import (
    StackExchangeInventoryError,
    parse_stackexchange_archive_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "stackexchange_archive_sample.json"


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_snapshot_uses_maximum_numeric_mtime_not_lexical_order() -> None:
    payload = _payload()
    payload["files"][0]["mtime"] = "999"
    payload["files"][1]["mtime"] = "1000"

    records = parse_stackexchange_archive_metadata(
        payload,
        source_locator="https://archive.org/metadata/stackexchange",
    )

    assert {record["snapshot_id"] for record in records} == {
        "stackexchange@mtime-1000"
    }
    assert all(
        record["source_metadata"]["snapshot_basis"]
        == "maximum-numeric-file-mtime"
        for record in records
    )


def test_invalid_mtime_fails_closed() -> None:
    payload = _payload()
    payload["files"][0]["mtime"] = "not-an-epoch"

    with pytest.raises(StackExchangeInventoryError, match="invalid mtime"):
        parse_stackexchange_archive_metadata(
            payload,
            source_locator="https://archive.org/metadata/stackexchange",
        )
