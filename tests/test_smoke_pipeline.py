from __future__ import annotations

from itertools import count
import json
from pathlib import Path

import pytest

from chronopersona.run_registry import (
    RunStore,
    atomic_write_json,
    read_event_log,
    read_json,
)
from chronopersona.smoke_pipeline import (
    SmokePipelineError,
    build_smoke_plan,
    run_smoke_pipeline,
    validate_smoke_config,
    verify_smoke_run,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "runs" / "synthetic-fixture-smoke-v0.json"
FIXED_ENVIRONMENT = {
    "python_version": "3.11.0",
    "python_implementation": "CPython",
    "system": "fixture-os",
    "release": "fixture-release",
    "machine": "fixture-machine",
    "processor": "fixture-processor",
}


def _clock(prefix: str):
    sequence = count()
    return lambda: f"{prefix}-{next(sequence):04d}"


@pytest.fixture(scope="module")
def smoke_plan():
    return build_smoke_plan(
        ROOT,
        CONFIG,
        git_commit="a" * 40,
        environment=FIXED_ENVIRONMENT,
    )


def test_committed_smoke_plan_is_non_scientific_and_no_network(smoke_plan) -> None:
    assert smoke_plan.plan["training_planned"] is False
    assert smoke_plan.plan["model_load_planned"] is False
    assert smoke_plan.plan["network_access_permitted"] is False
    assert smoke_plan.plan["external_spend_cad"] == 0
    assert smoke_plan.plan["unit_count"] == len(smoke_plan.unit_order)
    assert smoke_plan.identity["scientific_identity"]["target_tokens"] == 0
    assert smoke_plan.identity["scientific_identity"]["model"] == {
        "id": None,
        "revision": None,
        "tokenizer_revision": None,
    }


def test_smoke_config_blocks_training_and_resource_escalation() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["target_tokens"] = 1
    config["training_authorized"] = True
    config["external_spend_cad"] = 1
    config["max_parallel_jobs"] = 2

    errors = validate_smoke_config(config)
    assert "fixture smoke target_tokens must remain zero" in errors
    assert "training_authorized must be false" in errors
    assert "external_spend_cad must be zero" in errors
    assert "max_parallel_jobs must be exactly one" in errors


def test_interrupted_resume_matches_uninterrupted(
    tmp_path: Path,
    smoke_plan,
) -> None:
    resumed_output = tmp_path / "resumed"
    interrupted = run_smoke_pipeline(
        smoke_plan,
        resumed_output,
        interrupt_after=2,
        event_clock=_clock("resumed-first"),
    )
    assert interrupted.status == "interrupted"
    assert interrupted.final_manifest is None

    resumed = run_smoke_pipeline(
        smoke_plan,
        resumed_output,
        resume=True,
        event_clock=_clock("resumed-second"),
    )
    uninterrupted = run_smoke_pipeline(
        smoke_plan,
        tmp_path / "uninterrupted",
        event_clock=_clock("uninterrupted"),
    )

    assert resumed.status == uninterrupted.status == "complete"
    assert resumed.final_manifest == uninterrupted.final_manifest
    assert resumed.final_manifest["training_performed"] is False
    assert resumed.final_manifest["model_loaded"] is False
    assert resumed.final_manifest["network_access_performed"] is False
    assert resumed.final_manifest["scientific_claim_authorized"] is False

    event_state = read_event_log(
        resumed.run_root / "events.jsonl",
        expected_run_id=resumed.run_id,
    )
    event_types = [event["event_type"] for event in event_state.events]
    assert "fail" in event_types
    assert "resume" in event_types
    assert event_types[-1] == "complete"
    progress_units = [
        event["data"]["unit_id"]
        for event in event_state.events
        if event["event_type"] == "progress"
    ]
    assert progress_units == list(smoke_plan.unit_order)
    assert len(progress_units) == len(set(progress_units))


def test_corrupt_checkpoint_fails_closed(tmp_path: Path, smoke_plan) -> None:
    result = run_smoke_pipeline(
        smoke_plan,
        tmp_path,
        interrupt_after=1,
        event_clock=_clock("checkpoint"),
    )
    checkpoint_path = result.run_root / "checkpoint.json"
    checkpoint = read_json(checkpoint_path)
    checkpoint["next_unit_index"] = 999
    atomic_write_json(checkpoint_path, checkpoint)

    with pytest.raises(SmokePipelineError, match="checkpoint hash mismatch"):
        run_smoke_pipeline(smoke_plan, tmp_path, resume=True)


def test_corrupt_unit_artifact_fails_closed(tmp_path: Path, smoke_plan) -> None:
    result = run_smoke_pipeline(
        smoke_plan,
        tmp_path,
        interrupt_after=1,
        event_clock=_clock("artifact"),
    )
    checkpoint = read_json(result.run_root / "checkpoint.json")
    first_unit = checkpoint["completed_units"][0]
    artifact_path = result.run_root / checkpoint["unit_artifacts"][first_unit][
        "path"
    ]
    artifact = read_json(artifact_path)
    artifact["line_count"] += 1
    atomic_write_json(artifact_path, artifact)

    with pytest.raises(SmokePipelineError, match="file hash mismatch"):
        verify_smoke_run(smoke_plan, result.run_root)


def test_existing_running_run_requires_explicit_recovery(
    tmp_path: Path,
    smoke_plan,
) -> None:
    run_root = tmp_path / smoke_plan.identity["run_id"]
    store = RunStore(run_root, smoke_plan.identity)
    store.initialize()
    store.transition("freeze")
    store.transition("start")

    with pytest.raises(SmokePipelineError, match="explicit resume"):
        run_smoke_pipeline(smoke_plan, tmp_path)

    recovered = run_smoke_pipeline(
        smoke_plan,
        tmp_path,
        resume=True,
        event_clock=_clock("recover"),
    )
    assert recovered.status == "complete"
    assert "recover" in [
        event["event_type"]
        for event in read_event_log(
            recovered.run_root / "events.jsonl",
            expected_run_id=recovered.run_id,
        ).events
    ]


def test_identity_changes_with_commit_or_environment() -> None:
    first = build_smoke_plan(
        ROOT,
        CONFIG,
        git_commit="a" * 40,
        environment=FIXED_ENVIRONMENT,
    )
    commit_changed = build_smoke_plan(
        ROOT,
        CONFIG,
        git_commit="b" * 40,
        environment=FIXED_ENVIRONMENT,
    )
    environment_changed = build_smoke_plan(
        ROOT,
        CONFIG,
        git_commit="a" * 40,
        environment={**FIXED_ENVIRONMENT, "machine": "other-machine"},
    )

    assert len(
        {
            first.identity["run_id"],
            commit_changed.identity["run_id"],
            environment_changed.identity["run_id"],
        }
    ) == 3
