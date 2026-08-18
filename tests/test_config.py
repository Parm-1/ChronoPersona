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
            if condition.control_type != "generic_continuation"
        ),
    )

    assert (
        "missing required controls: generic_continuation"
        in validate_spec(bad_spec)
    )


def test_at_least_three_seeds_are_required() -> None:
    spec = load_spec(PILOT)
    bad_spec = replace(spec, seeds=spec.seeds[:2])

    assert (
        "at least three exploratory adaptation seeds are required"
        in validate_spec(bad_spec)
    )


def test_each_source_requires_both_eras() -> None:
    spec = load_spec(PILOT)
    bad_spec = replace(
        spec,
        conditions=tuple(
            condition
            for condition in spec.conditions
            if condition.id != "late-source-b"
        ),
    )

    assert any(
        "two source families must each contain both early and late"
        in error
        for error in validate_spec(bad_spec)
    )


def test_held_out_source_must_not_be_used_for_training() -> None:
    spec = load_spec(PILOT)
    evaluation = replace(
        spec.evaluation,
        held_out_source_family="A",
    )
    bad_spec = replace(spec, evaluation=evaluation)

    assert any(
        "held-out source family must not appear" in error
        for error in validate_spec(bad_spec)
    )


def test_unfrozen_budget_is_allowed_only_during_design() -> None:
    spec = load_spec(PILOT)
    frozen = replace(spec, status="frozen")

    assert (
        "experiment.token_budget must be frozen before execution"
        in validate_spec(frozen)
    )


def test_external_compute_requires_explicit_authorization() -> None:
    spec = load_spec(PILOT)
    resources = replace(
        spec.resources,
        external_compute_requires_user_authorization=False,
    )
    bad_spec = replace(spec, resources=resources)

    assert (
        "external compute must require explicit user authorization"
        in validate_spec(bad_spec)
    )


def test_only_one_training_job_is_allowed_at_a_time() -> None:
    spec = load_spec(PILOT)
    resources = replace(spec.resources, max_parallel_training_jobs=2)
    bad_spec = replace(spec, resources=resources)

    assert any(
        "exactly one training job" in error
        for error in validate_spec(bad_spec)
    )


def test_windows_style_manifest_path_is_rejected() -> None:
    spec = load_spec(PILOT)
    unsafe = replace(
        spec.conditions[0],
        manifest=r"data\manifests\private.jsonl",
    )
    bad_spec = replace(
        spec,
        conditions=(unsafe, *spec.conditions[1:]),
    )

    errors = validate_spec(bad_spec)
    assert any("data/manifests/*.jsonl" in error for error in errors)


def test_output_directory_requires_portable_results_path() -> None:
    spec = load_spec(PILOT)
    bad_spec = replace(spec, output_dir=r"results\unsafe")

    assert (
        "reporting.output_dir must be a portable relative results/* path"
        in validate_spec(bad_spec)
    )
