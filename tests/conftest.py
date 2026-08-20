from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def ensure_local_output_root() -> None:
    (ROOT / "artifacts" / "local").mkdir(parents=True, exist_ok=True)
