from __future__ import annotations

from pathlib import Path

import pytest

from chronopersona.path_policy import (
    PortablePathError,
    is_portable_relative_path,
    portable_path_identity,
    portable_relative_path,
)


@pytest.mark.parametrize(
    "value",
    [
        "/absolute/file.json",
        "../outside.json",
        r"..\outside.json",
        r"C:\outside.json",
        "a//b.json",
        "a/./b.json",
        "a/CON.txt",
        "a/nul",
        "a/trailing.",
        "a/trailing ",
        "a/pipe|name.json",
        "a/control\x01.json",
        " leading.json",
        "trailing.json ",
    ],
)
def test_nonportable_paths_are_rejected(value: str) -> None:
    with pytest.raises(PortablePathError):
        portable_relative_path(value, label="fixture path")
    assert is_portable_relative_path(value) is False


def test_valid_nested_path_is_converted_to_native_path() -> None:
    observed = portable_relative_path(
        "artifacts/local/report.json",
        label="report path",
        required_prefix=("artifacts", "local"),
        suffix=".json",
    )

    assert observed == Path("artifacts") / "local" / "report.json"
    assert is_portable_relative_path(
        "artifacts/local/report.json",
        required_prefix=("artifacts", "local"),
        suffix=".json",
    )


def test_prefix_and_suffix_constraints_fail_closed() -> None:
    with pytest.raises(PortablePathError, match="must be under artifacts/local"):
        portable_relative_path(
            "reports/report.json",
            required_prefix=("artifacts", "local"),
        )
    with pytest.raises(PortablePathError, match=r"must end with \.json"):
        portable_relative_path("artifacts/local/report.txt", suffix=".json")


def test_path_requires_nfc_normalization() -> None:
    decomposed = "reports/cafe\u0301.json"
    with pytest.raises(PortablePathError, match="NFC Unicode normalization"):
        portable_relative_path(decomposed)


def test_portable_identity_is_case_insensitive() -> None:
    assert portable_path_identity("Reports/Result.json") == portable_path_identity(
        "reports/result.JSON"
    )
