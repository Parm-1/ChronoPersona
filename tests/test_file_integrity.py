from types import SimpleNamespace

import pytest

from chronopersona.file_integrity import stable_read_unchanged


def _stat(
    *,
    ctime_ns: int,
    dev: int = 1,
    ino: int = 2,
    size: int = 7,
    mtime_ns: int = 3,
) -> SimpleNamespace:
    return SimpleNamespace(
        st_dev=dev,
        st_ino=ino,
        st_size=size,
        st_mtime_ns=mtime_ns,
        st_ctime_ns=ctime_ns,
    )


def test_stable_read_allows_windows_path_descriptor_ctime_difference() -> None:
    assert stable_read_unchanged(
        _stat(ctime_ns=10),
        _stat(ctime_ns=20),
        _stat(ctime_ns=20),
        _stat(ctime_ns=10),
    )


def test_stable_read_rejects_change_within_either_stat_view() -> None:
    assert not stable_read_unchanged(
        _stat(ctime_ns=10),
        _stat(ctime_ns=20),
        _stat(ctime_ns=21),
        _stat(ctime_ns=10),
    )
    assert not stable_read_unchanged(
        _stat(ctime_ns=10),
        _stat(ctime_ns=20),
        _stat(ctime_ns=20),
        _stat(ctime_ns=11),
    )
    assert not stable_read_unchanged(
        _stat(ctime_ns=10),
        _stat(ctime_ns=20),
        _stat(ctime_ns=20),
        _stat(ctime_ns=10, size=8),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("dev", 9), ("ino", 9), ("size", 9), ("mtime_ns", 9)],
)
def test_stable_read_rejects_cross_view_portable_identity_drift(
    field: str,
    value: int,
) -> None:
    changed = {field: value, "ctime_ns": 10}
    assert not stable_read_unchanged(
        _stat(ctime_ns=10),
        _stat(ctime_ns=20),
        _stat(ctime_ns=20),
        _stat(**changed),
    )
