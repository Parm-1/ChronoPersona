from dataclasses import replace
from pathlib import Path

from chronopersona.config import load_spec, validate_spec


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "configs" / "pilot.toml"


def test_pilot_configuration_is_valid() -> None:
    spec = load_spec(PILOT)

    assert validate_spec(spec) == ()


def test_duplicate_condition_ids_are_rejected() -> None:
    spec = load_spec(PILOT)
    duplicate = replace(spec.conditions[1], id=spec.conditions[0].id)
    bad_spec = replace(
        spec,
        conditions=(spec.conditions[0], duplicate, *spec.conditions[2:]),
    )

    assert "condition ids must be unique" in validate_spec(bad_spec)


def test_unsafe_manifest_path_is_rejected() -> None:
    spec = load_spec(PILOT)
    unsafe = replace(spec.conditions[0], manifest="../private.jsonl")
    bad_spec = replace(
        spec,
        conditions=(unsafe, *spec.conditions[1:]),
    )

    errors = validate_spec(bad_spec)

    assert any("data/manifests/*.jsonl" in error for error in errors)


def test_required_control_cannot_be_removed() -> None:
    spec = load_spec(PILOT)
    bad_spec = replace(
        spec,
        conditions=tuple(
            condition
            for condition in spec.conditions
            if condition.control_type != "date_shuffled"
        ),
    )

    assert (
        "missing required controls: date_shuffled"
        in validate_spec(bad_spec)
    )


def test_at_least_two_seeds_are_required() -> None:
    spec = load_spec(PILOT)
    bad_spec = replace(spec, seeds=(spec.seeds[0],))

    assert (
        "at least two adaptation seeds are required"
        in validate_spec(bad_spec)
    )
