from copy import deepcopy
from pathlib import Path

from chronopersona.evaluation import (
    load_evaluation_registry,
    validate_evaluation_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evaluations" / "registry" / "development-v0.jsonl"


def _items() -> list[dict[str, object]]:
    return [deepcopy(item) for item in load_evaluation_registry(REGISTRY)]


def test_modal_may_is_not_mistaken_for_a_month() -> None:
    items = _items()
    items[0]["forms"][0]["prompt"] += " The team may request another test."

    assert validate_evaluation_registry(items) == ()


def test_capitalized_month_name_is_rejected() -> None:
    items = _items()
    items[0]["forms"][0]["prompt"] += " The report arrived in May."

    assert any(
        "forbidden temporal cue 'May'" in error
        for error in validate_evaluation_registry(items)
    )


def test_lowercase_month_with_day_is_rejected() -> None:
    items = _items()
    items[0]["forms"][0]["prompt"] += " The report arrived on may 4."

    assert any(
        "forbidden temporal cue 'may 4'" in error
        for error in validate_evaluation_registry(items)
    )
