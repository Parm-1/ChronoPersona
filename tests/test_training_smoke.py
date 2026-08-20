from __future__ import annotations

from itertools import count
import json
import os
from pathlib import Path
import subprocess

import pytest

import chronopersona.training_smoke as training_smoke
from chronopersona.run_registry import (
    RunLock,
    atomic_write_bytes,
    atomic_write_json,
    build_run_identity,
    canonical_sha256,
    canonical_json_bytes,
    read_event_log,
)
from chronopersona.training_smoke import (
    StepResult,
    TrainingCheckpointState,
    TrainingSmokeError,
    build_training_plan,
    classify_forward_numerics,
    compare_training_runs,
    full_weight_adamw_capacity,
    load_training_checkpoint,
    load_training_config,
    pack_token_documents,
    run_training_condition,
    save_training_checkpoint,
    semantic_state_sha256,
    validate_training_config,
    verify_training_run,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "runs" / "pythia-lora-smoke-v1.json"
V0_CONFIG_PATH = ROOT / "configs" / "runs" / "pythia-lora-smoke-v0.json"
ATTENTION_DIAGNOSTIC_PATH = (
    ROOT / "reports" / "stage0" / "pythia_lora_attention_diagnostic_2026-08-20.json"
)


def _artifact() -> dict:
    return {
        "id": "pythia-1b-deduped-main",
        "repository": "EleutherAI/pythia-1b-deduped",
        "revision": "7" * 40,
        "architecture": "GPTNeoXForCausalLM",
        "model_type": "gpt_neox",
        "parameter_count": 1_011_781_632,
        "required_files": [
            {"filename": "config.json", "size_bytes": 1, "sha256": "a" * 64},
            {"filename": "model.safetensors", "size_bytes": 2, "sha256": "b" * 64},
        ],
    }


def _load_report(artifact: dict, git_commit: str) -> dict:
    return {
        "status": "complete",
        "mode": "execute",
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": artifact["revision"],
        "local_model_load_only": True,
        "network_download_permitted": False,
        "device": "cuda",
        "requested_dtype": "float16",
        "model_dtype": "torch.float16",
        "parameter_count": artifact["parameter_count"],
        "logits_validation": {"finite": True},
        "artifact_integrity": {
            "status": "verified",
            "files": [
                {**item, "verified": True} for item in artifact["required_files"]
            ],
        },
        "resource_preflight": {"git_head": git_commit},
        "loaded_model_validation": {
            "architecture": artifact["architecture"],
            "model_type": artifact["model_type"],
            "parameter_count": artifact["parameter_count"],
            "parameter_dtypes": ["torch.float16"],
            "attention_implementation": "sdpa",
            "sdpa_backends": ["math"],
            "sdpa_math_allow_fp16_reduction": False,
            "verified": True,
        },
    }


def _plan(*, git_commit: str = "1" * 40, runtime: str = "runtime"):
    config = load_training_config(CONFIG_PATH)
    artifact = _artifact()
    packed = pack_token_documents(([1, 2, 3], [4, 5]), 0)
    report = _load_report(artifact, git_commit)
    return build_training_plan(
        config,
        git_commit=git_commit,
        config_sha256="c" * 64,
        model_manifest_sha256="d" * 64,
        artifact=artifact,
        load_report=report,
        load_report_sha256="e" * 64,
        content_manifest_sha256="f" * 64,
        content_records=(
            {"record_id": "control-neutral", "content_sha256": "2" * 64},
            {"record_id": "calibration-neutral", "content_sha256": "3" * 64},
        ),
        tokenizer_identity={"class": "FakeTokenizer", "eos_token_id": 0},
        runtime_identity={"python": "3.11", "runtime": runtime},
        packed_tokens=packed,
    )


def _json_serialize(value) -> bytes:
    return canonical_json_bytes(value)


def _json_deserialize(value: bytes):
    loaded = json.loads(value)
    assert isinstance(loaded, dict)
    return loaded


class ToyBackend:
    """Tiny PRNG-dependent optimizer used to prove the resume contract."""

    def __init__(self, plan, resume_state=None, *, nonfinite_step=None):
        self.plan = plan
        self.weight = 11
        self.moment = 0
        self.scheduler_step = 0
        self.scale = 128
        self.rng = int(plan.config["seed"])
        self.nonfinite_step = nonfinite_step
        self._base = semantic_state_sha256({"frozen_base": [2, 3, 5]})
        if resume_state is not None:
            self.weight = resume_state.adapter_state["lora.weight"]
            self.moment = resume_state.optimizer_state["moment"]
            self.scheduler_step = resume_state.scheduler_state["step"]
            self.scale = resume_state.scaler_state["scale"]
            self.rng = resume_state.cpu_rng_state

    @property
    def base_identity_sha256(self):
        return self._base

    def run_step(self, token_block, step):
        if step == self.nonfinite_step:
            return StepResult(float("nan"), {"toy": True})
        self.rng = (1103515245 * self.rng + 12345) % (2**31)
        dropout = self.rng & 1
        gradient = (sum(token_block) + dropout + step) % 97
        self.moment = self.moment * 3 + gradient
        self.weight -= self.moment
        self.scheduler_step += 1
        loss = float(abs(self.weight) % 10_000) / 1000.0
        return StepResult(loss, {"dropout_bit": dropout})

    def capture_state(self, *, completed_steps, cursor, tokens_seen, losses):
        return TrainingCheckpointState(
            completed_steps=completed_steps,
            cursor=cursor,
            tokens_seen=tokens_seen,
            losses=tuple(losses),
            adapter_state={"lora.weight": self.weight},
            optimizer_state={"moment": self.moment},
            scheduler_state={"step": self.scheduler_step},
            scaler_state={"scale": self.scale},
            cpu_rng_state=self.rng,
            cuda_rng_states=(self.rng + 1,),
        )

    def serialize_adapter(self, adapter_state):
        return canonical_json_bytes(adapter_state)

    def close(self):
        return None


class BadFinalStateBackend(ToyBackend):
    def capture_state(self, *, completed_steps, cursor, tokens_seen, losses):
        state = super().capture_state(
            completed_steps=completed_steps,
            cursor=cursor,
            tokens_seen=tokens_seen,
            losses=losses,
        )
        if completed_steps == 5:
            return TrainingCheckpointState(
                state.completed_steps,
                state.cursor,
                639,
                state.losses,
                state.adapter_state,
                state.optimizer_state,
                state.scheduler_state,
                state.scaler_state,
                state.cpu_rng_state,
                state.cuda_rng_states,
            )
        return state


class UnrelatedAdapterBackend(ToyBackend):
    def serialize_adapter(self, adapter_state):
        return canonical_json_bytes({"unrelated": 0})


class WrongLossStateBackend(ToyBackend):
    def capture_state(self, *, completed_steps, cursor, tokens_seen, losses):
        state = super().capture_state(
            completed_steps=completed_steps,
            cursor=cursor,
            tokens_seen=tokens_seen,
            losses=losses,
        )
        if completed_steps == 5:
            changed_losses = (*state.losses[:-1], state.losses[-1] + 1.0)
            return TrainingCheckpointState(
                state.completed_steps,
                state.cursor,
                state.tokens_seen,
                changed_losses,
                state.adapter_state,
                state.optimizer_state,
                state.scheduler_state,
                state.scaler_state,
                state.cpu_rng_state,
                state.cuda_rng_states,
            )
        return state


class TimedToyBackend(ToyBackend):
    def __init__(self, plan, resume_state, timer):
        super().__init__(plan, resume_state)
        self.timer = timer

    def run_step(self, token_block, step):
        self.timer[0] += 1.0
        return super().run_step(token_block, step)


class OomToyBackend(ToyBackend):
    def run_step(self, token_block, step):
        if step == 2:
            raise MemoryError("injected bounded OOM sentinel")
        return super().run_step(token_block, step)


class NumericDiagnosticFailureBackend(ToyBackend):
    @property
    def runtime_summary(self):
        return {
            "attention_implementation": "sdpa",
            "sdpa_backends": ["math"],
            "sdpa_math_allow_fp16_reduction": False,
            "last_forward_numeric": {
                "step": 1,
                "token_block_sha256": "9" * 64,
                "stage": "logits-nonfinite",
                "logits_nonfinite_count": 7,
                "loss_finite": False,
                "loss_value": None,
                "forward_peak_allocated_bytes": 123,
            },
        }

    def run_step(self, token_block, step):
        raise TrainingSmokeError("injected non-finite logits diagnostic")


def _clock(prefix: str):
    sequence = count()
    return lambda: f"{prefix}-{next(sequence):04d}"


def test_committed_training_config_is_strict_and_non_scientific() -> None:
    config = load_training_config(CONFIG_PATH)
    assert validate_training_config(config) == ()
    assert config["network_allowed"] is False
    assert config["scientific_claim_authorized"] is False
    assert config["resource_limits"]["ram_threshold_enforced"] is False
    assert config["run_name"] == "pythia-1b-deduped-lora-smoke-v1"
    assert config["determinism"]["attention_implementation"] == "sdpa"
    assert config["determinism"]["sdpa_backends"] == ["math"]
    assert config["determinism"]["sdpa_math_allow_fp16_reduction"] is False

    changed = json.loads(json.dumps(config))
    changed["steps"] = 6
    assert "steps must be exactly 5" in validate_training_config(changed)

    for key, value in (
        ("attention_implementation", "eager"),
        ("sdpa_backends", ["efficient"]),
        ("sdpa_math_allow_fp16_reduction", True),
    ):
        changed = json.loads(json.dumps(config))
        changed["determinism"][key] = value
        assert "determinism must match the frozen E5 policy" in validate_training_config(
            changed
        )


def test_v1_changes_only_the_predeclared_attention_rescue() -> None:
    v0 = json.loads(V0_CONFIG_PATH.read_text(encoding="utf-8"))
    v1 = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    expected = json.loads(json.dumps(v0))
    expected["run_name"] = "pythia-1b-deduped-lora-smoke-v1"
    expected["determinism"].update(
        {
            "attention_implementation": "sdpa",
            "sdpa_backends": ["math"],
            "sdpa_math_allow_fp16_reduction": False,
        }
    )

    assert v1 == expected


def test_attention_diagnostic_is_self_hashed_and_non_scientific() -> None:
    report = json.loads(ATTENTION_DIAGNOSTIC_PATH.read_text(encoding="utf-8"))
    observed = report.pop("diagnostic_sha256")

    assert canonical_sha256(report) == observed
    assert report["failed_run"]["completed_steps"] == 0
    assert report["failed_run"]["run_id"] == "run-b035b9becad60b6dc55ff3fd6fba6016"
    assert report["failed_run"]["attempt_file_sha256"] == (
        "e9be995c08affa71e73343c80844756329150031cc5cf96338a7e5dc3e8aceaf"
    )
    assert report["failed_run"]["cli_report_sha256"] == (
        "6405a6e68138250c39fb70988075e1cbe39a7b7bbf495e3b5a2e74f3ae67c347"
    )
    assert report["execution_controls"]["backward_performed"] is False
    assert report["execution_controls"]["optimizer_update_performed"] is False
    assert report["evidence_scope"].startswith("diagnosis-only")


@pytest.mark.parametrize(
    ("logits_finite", "loss_finite", "expected"),
    [
        (True, True, "complete"),
        (False, False, "logits-nonfinite"),
        (True, False, "loss-nonfinite"),
    ],
)
def test_forward_numeric_classification_is_fail_loud(
    logits_finite: bool,
    loss_finite: bool,
    expected: str,
) -> None:
    assert classify_forward_numerics(
        logits_finite=logits_finite,
        loss_finite=loss_finite,
    ) == expected


def test_load_report_binds_the_complete_attention_policy() -> None:
    config = load_training_config(CONFIG_PATH)
    artifact = _artifact()
    report = _load_report(artifact, "1" * 40)

    for key, value in (
        ("attention_implementation", "eager"),
        ("sdpa_backends", ["efficient"]),
        ("sdpa_math_allow_fp16_reduction", True),
    ):
        changed = json.loads(json.dumps(report))
        changed["loaded_model_validation"][key] = value
        with pytest.raises(TrainingSmokeError, match="load report model validation mismatch"):
            build_training_plan(
                config,
                git_commit="1" * 40,
                config_sha256="c" * 64,
                model_manifest_sha256="d" * 64,
                artifact=artifact,
                load_report=changed,
                load_report_sha256="e" * 64,
                content_manifest_sha256="f" * 64,
                content_records=(
                    {"record_id": "control-neutral", "content_sha256": "2" * 64},
                    {"record_id": "calibration-neutral", "content_sha256": "3" * 64},
                ),
                tokenizer_identity={"class": "FakeTokenizer", "eos_token_id": 0},
                runtime_identity={"python": "3.11"},
                packed_tokens=pack_token_documents(([1, 2, 3], [4, 5]), 0),
            )


def test_training_plan_identity_is_order_stable_and_input_sensitive() -> None:
    first = _plan()
    repeated = _plan()
    changed_commit = _plan(git_commit="2" * 40)
    changed_runtime = _plan(runtime="changed")

    assert first.plan == repeated.plan
    assert first.identity == repeated.identity
    assert len(
        {
            first.identity["run_id"],
            changed_commit.identity["run_id"],
            changed_runtime.identity["run_id"],
        }
    ) == 3
    assert first.plan["network_access_permitted"] is False
    assert first.plan["scientific_claim_authorized"] is False


def test_full_weight_adamw_lower_bound_exceeds_bound_gpu() -> None:
    capacity = full_weight_adamw_capacity(1_011_781_632, 6_441_992_192)

    assert capacity["weights_bytes"] == 2_023_563_264
    assert capacity["gradients_bytes"] == 2_023_563_264
    assert capacity["two_moments_bytes"] == 4_047_126_528
    assert capacity["optimistic_total_bytes"] == 8_094_253_056
    assert capacity["shortfall_bytes"] == 1_652_260_864
    assert capacity["fits_before_activations"] is False
    assert "device-resident" in capacity["scope"]


def test_token_packing_is_exact_deterministic_and_eos_delimited() -> None:
    packed = pack_token_documents(([10, 11], [20]), 99, steps=2, sequence_length=5)
    repeated = pack_token_documents(([10, 11], [20]), 99, steps=2, sequence_length=5)

    assert packed.blocks == ((10, 11, 99, 20, 99), (10, 11, 99, 20, 99))
    assert packed.input_tokens == 10
    assert packed.causal_targets == 8
    assert packed == repeated


def test_checkpoint_verifies_hash_before_deserialization(tmp_path: Path) -> None:
    identity = build_run_identity({"checkpoint": "fixture"})
    state = TrainingCheckpointState(
        completed_steps=3,
        cursor=3,
        tokens_seen=384,
        losses=(1.0, 0.9, 0.8),
        adapter_state={"a": 1},
        optimizer_state={"m": 2},
        scheduler_state={"step": 3},
        scaler_state={"scale": 128},
        cpu_rng_state=7,
        cuda_rng_states=(8,),
    )
    reference = save_training_checkpoint(
        tmp_path,
        state,
        identity,
        serialize=_json_serialize,
    )
    restored = load_training_checkpoint(
        tmp_path,
        identity,
        expected_step=3,
        expected_adapter_keys=["a"],
        deserialize=_json_deserialize,
    )
    assert restored == state

    reference.state_path.write_bytes(reference.state_path.read_bytes() + b"tamper")
    calls = 0

    def forbidden_deserialize(_payload):
        nonlocal calls
        calls += 1
        raise AssertionError("deserializer must not be reached")

    with pytest.raises(TrainingSmokeError, match="size mismatch"):
        load_training_checkpoint(
            tmp_path,
            identity,
            expected_step=3,
            deserialize=forbidden_deserialize,
        )
    assert calls == 0


def test_checkpoint_rejects_wrong_identity_and_existing_step(tmp_path: Path) -> None:
    identity = build_run_identity({"checkpoint": "fixture"})
    state = TrainingCheckpointState(
        3, 3, 384, (1.0, 0.9, 0.8), {"a": 1}, {"m": 2}, {"step": 3}, {"scale": 1}, 7, (8,)
    )
    save_training_checkpoint(tmp_path, state, identity, serialize=_json_serialize)
    with pytest.raises(TrainingSmokeError, match="already exists"):
        save_training_checkpoint(tmp_path, state, identity, serialize=_json_serialize)
    with pytest.raises(TrainingSmokeError, match="run_id mismatch"):
        load_training_checkpoint(
            tmp_path,
            build_run_identity({"checkpoint": "other"}),
            deserialize=_json_deserialize,
        )


def test_checkpoint_checks_sha_before_deserializing_same_size_tamper(
    tmp_path: Path,
) -> None:
    identity = build_run_identity({"checkpoint": "fixture"})
    state = TrainingCheckpointState(
        3, 3, 384, (1.0, 0.9, 0.8), {"a": 1}, {"m": 2}, {"step": 3}, {"scale": 1}, 7, (8,)
    )
    reference = save_training_checkpoint(
        tmp_path, state, identity, serialize=_json_serialize
    )
    payload = bytearray(reference.state_path.read_bytes())
    payload[-1] ^= 1
    reference.state_path.write_bytes(payload)

    def forbidden_deserialize(_payload):
        raise AssertionError("deserializer must not be reached")

    with pytest.raises(TrainingSmokeError, match="file hash mismatch"):
        load_training_checkpoint(
            tmp_path,
            identity,
            expected_step=3,
            deserialize=forbidden_deserialize,
        )


def test_checkpoint_refuses_to_replace_pointer_without_state(tmp_path: Path) -> None:
    identity = build_run_identity({"checkpoint": "fixture"})
    state = TrainingCheckpointState(
        3, 3, 384, (1.0, 0.9, 0.8), {"a": 1}, {"m": 2}, {"step": 3}, {"scale": 1}, 7, (8,)
    )
    pointer = tmp_path / "checkpoint.json"
    pointer.write_text('{"preserve":true}\n', encoding="utf-8")

    with pytest.raises(TrainingSmokeError, match="pointer already exists"):
        save_training_checkpoint(tmp_path, state, identity, serialize=_json_serialize)
    assert pointer.read_text(encoding="utf-8") == '{"preserve":true}\n'
    assert not (tmp_path / "checkpoints" / "step-0003.pt").exists()


@pytest.mark.parametrize(
    "unsafe_path",
    ("../step-0003.pt", "C:/step-0003.pt", "checkpoints/CON.pt"),
)
def test_checkpoint_rejects_unsafe_path_before_deserialize(
    tmp_path: Path, unsafe_path: str
) -> None:
    identity = build_run_identity({"checkpoint": "fixture"})
    state = TrainingCheckpointState(
        3, 3, 384, (1.0, 0.9, 0.8), {"a": 1}, {"m": 2}, {"step": 3}, {"scale": 1}, 7, (8,)
    )
    save_training_checkpoint(tmp_path, state, identity, serialize=_json_serialize)
    pointer_path = tmp_path / "checkpoint.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["state_path"] = unsafe_path
    pointer["checkpoint_sha256"] = canonical_sha256(
        {key: value for key, value in pointer.items() if key != "checkpoint_sha256"}
    )
    atomic_write_json(pointer_path, pointer)

    def forbidden_deserialize(_payload):
        raise AssertionError("unsafe paths must fail before deserialization")

    with pytest.raises(TrainingSmokeError, match="frozen path|portable|relative|reserved"):
        load_training_checkpoint(
            tmp_path,
            identity,
            expected_step=3,
            deserialize=forbidden_deserialize,
        )


def test_interrupted_resume_is_semantically_equal_to_control(tmp_path: Path) -> None:
    plan = _plan()
    control = run_training_condition(
        plan,
        tmp_path,
        condition="control",
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
        event_clock=_clock("control"),
    )
    interrupted = run_training_condition(
        plan,
        tmp_path,
        condition="resumed",
        interrupt_after=3,
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
        event_clock=_clock("interrupted"),
    )
    assert interrupted.status == "interrupted"
    assert interrupted.completed_steps == 3
    resumed = run_training_condition(
        plan,
        tmp_path,
        condition="resumed",
        resume=True,
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
        event_clock=_clock("resume"),
    )

    assert control.status == resumed.status == "complete"
    comparison = compare_training_runs(
        plan,
        control.run_root,
        resumed.run_root,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    assert comparison["status"] == "equal"
    assert control.final_manifest == resumed.final_manifest
    events = read_event_log(
        resumed.run_root / "events.jsonl",
        expected_run_id=resumed.run_id,
    ).events
    assert [event["event_type"] for event in events].count("progress") == 5
    assert "fail" in [event["event_type"] for event in events]
    assert "resume" in [event["event_type"] for event in events]
    with pytest.raises(TrainingSmokeError, match="distinct"):
        compare_training_runs(
            plan,
            control.run_root,
            control.run_root,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    with pytest.raises(TrainingSmokeError, match="condition mismatch"):
        compare_training_runs(
            plan,
            resumed.run_root,
            control.run_root,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )


def test_nonfinite_failure_is_structured_and_does_not_complete(tmp_path: Path) -> None:
    plan = _plan()
    with pytest.raises(TrainingSmokeError, match="non-finite loss"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: ToyBackend(
                current, state, nonfinite_step=2
            ),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
            event_clock=_clock("failure"),
        )
    run_root = tmp_path / "control" / plan.identity["run_id"]
    events = read_event_log(run_root / "events.jsonl", expected_run_id=plan.identity["run_id"])
    assert events.state == "failed"
    failure = events.events[-1]
    assert failure["event_type"] == "fail"
    assert failure["data"]["completed_steps"] == 1
    assert failure["data"]["network_access_performed"] is False
    assert not (run_root / "artifacts" / "final-manifest.json").exists()


def test_oom_failure_is_structured_and_preserves_attempt_context(
    tmp_path: Path,
) -> None:
    plan = _plan()
    with pytest.raises(MemoryError, match="OOM sentinel"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: OomToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
            attempt_context={"resource_audit_sha256": "a" * 64},
        )
    run_root = tmp_path / "control" / plan.identity["run_id"]
    events = read_event_log(
        run_root / "events.jsonl", expected_run_id=plan.identity["run_id"]
    )
    failure = events.events[-1]
    assert events.state == "failed"
    assert failure["event_type"] == "fail"
    assert failure["data"]["failure_kind"] == "training-error"
    assert failure["data"]["failure_stage"] == "training-condition"
    assert failure["data"]["error_type"] == "MemoryError"
    assert failure["data"]["completed_steps"] == 1
    assert failure["data"]["tokens_seen"] == 128
    assert failure["data"]["network_access_performed"] is False
    attempt_ref = failure["data"]["attempt_report"]
    assert attempt_ref is not None
    attempt = json.loads((run_root / attempt_ref["path"]).read_text(encoding="utf-8"))
    assert attempt["status"] == "failed"
    assert attempt["completed_steps"] == 1
    assert attempt["backend"]["attempt_context"]["resource_audit_sha256"] == "a" * 64
    assert not (run_root / "artifacts" / "final-manifest.json").exists()


def test_numeric_failure_preserves_pre_backward_diagnostic(
    tmp_path: Path,
) -> None:
    plan = _plan()
    with pytest.raises(TrainingSmokeError, match="non-finite logits diagnostic"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: NumericDiagnosticFailureBackend(
                current, state
            ),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    run_root = tmp_path / "control" / plan.identity["run_id"]
    events = read_event_log(
        run_root / "events.jsonl", expected_run_id=plan.identity["run_id"]
    )
    failure = events.events[-1]
    attempt_ref = failure["data"]["attempt_report"]
    attempt_path = run_root / attempt_ref["path"]
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    numeric = attempt["backend"]["runtime"]["last_forward_numeric"]

    assert events.state == "failed"
    assert failure["data"]["completed_steps"] == 0
    assert attempt_ref["file_sha256"] == training_smoke.sha256_file(attempt_path)
    assert attempt["status"] == "failed"
    assert numeric["stage"] == "logits-nonfinite"
    assert numeric["loss_value"] is None
    assert numeric["forward_peak_allocated_bytes"] == 123


def test_resume_rejects_checkpoint_not_bound_to_progress_event(tmp_path: Path) -> None:
    plan = _plan()
    interrupted = run_training_condition(
        plan,
        tmp_path,
        condition="resumed",
        interrupt_after=3,
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    pointer_path = interrupted.run_root / "checkpoint.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    original = interrupted.run_root / pointer["state_path"]
    replacement = interrupted.run_root / "checkpoints" / "alternate.pt"
    replacement.write_bytes(original.read_bytes())
    pointer["state_path"] = "checkpoints/alternate.pt"
    pointer["checkpoint_sha256"] = canonical_sha256(
        {key: value for key, value in pointer.items() if key != "checkpoint_sha256"}
    )
    atomic_write_json(pointer_path, pointer)

    with pytest.raises(TrainingSmokeError, match="exact frozen path|step-three event"):
        run_training_condition(
            plan,
            tmp_path,
            condition="resumed",
            resume=True,
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )


def test_resume_rejects_attempt_not_bound_to_planned_failure(tmp_path: Path) -> None:
    plan = _plan()
    interrupted = run_training_condition(
        plan,
        tmp_path,
        condition="resumed",
        interrupt_after=3,
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    attempt_path = interrupted.run_root / "artifacts" / "attempts" / "attempt-0001.json"
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    attempt["elapsed_seconds"] = 0.0
    attempt["completed_steps"] = 999
    attempt["attempt_report_sha256"] = canonical_sha256(
        {key: value for key, value in attempt.items() if key != "attempt_report_sha256"}
    )
    atomic_write_json(attempt_path, attempt)
    backend_calls = 0

    def forbidden_backend(_plan, _state):
        nonlocal backend_calls
        backend_calls += 1
        raise AssertionError("backend must not be reached")

    with pytest.raises(TrainingSmokeError, match="interruption attempt"):
        run_training_condition(
            plan,
            tmp_path,
            condition="resumed",
            resume=True,
            backend_factory=forbidden_backend,
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    assert backend_calls == 0
    events = read_event_log(
        interrupted.run_root / "events.jsonl", expected_run_id=plan.identity["run_id"]
    )
    assert events.state == "failed"
    assert [event["event_type"] for event in events.events].count("resume") == 0


def test_resume_rejects_attempt_directory_link_or_junction(tmp_path: Path) -> None:
    plan = _plan()
    interrupted = run_training_condition(
        plan,
        tmp_path,
        condition="resumed",
        interrupt_after=3,
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    attempts = interrupted.run_root / "artifacts" / "attempts"
    outside = tmp_path / "outside-attempts"
    outside.mkdir()
    (attempts / "attempt-0001.json").replace(outside / "attempt-0001.json")
    attempts.rmdir()
    try:
        if os.name == "nt":
            subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(attempts), str(outside)],
                check=True,
                capture_output=True,
            )
        else:
            attempts.symlink_to(outside, target_is_directory=True)
    except (OSError, subprocess.CalledProcessError) as error:
        pytest.skip(f"directory link creation is unavailable: {error}")

    backend_calls = 0

    def forbidden_backend(_plan, _state):
        nonlocal backend_calls
        backend_calls += 1
        raise AssertionError("backend must not be reached")

    with pytest.raises(TrainingSmokeError, match="links or reparse points"):
        run_training_condition(
            plan,
            tmp_path,
            condition="resumed",
            resume=True,
            backend_factory=forbidden_backend,
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    assert backend_calls == 0
    assert not (outside / "attempt-0002.json").exists()
    events = read_event_log(
        interrupted.run_root / "events.jsonl", expected_run_id=plan.identity["run_id"]
    )
    assert events.state == "failed"
    assert [event["event_type"] for event in events.events].count("resume") == 0


def test_resume_preserves_preexisting_final_outputs_before_resume_event(
    tmp_path: Path,
) -> None:
    plan = _plan()
    interrupted = run_training_condition(
        plan,
        tmp_path,
        condition="resumed",
        interrupt_after=3,
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    final_manifest = interrupted.run_root / "artifacts" / "final-manifest.json"
    runtime_report = interrupted.run_root / "artifacts" / "runtime-report.json"
    final_manifest.write_bytes(b"preserve-final\n")
    runtime_report.write_bytes(b"preserve-runtime\n")

    with pytest.raises(TrainingSmokeError, match="immutable final output"):
        run_training_condition(
            plan,
            tmp_path,
            condition="resumed",
            resume=True,
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    assert final_manifest.read_bytes() == b"preserve-final\n"
    assert runtime_report.read_bytes() == b"preserve-runtime\n"
    events = read_event_log(
        interrupted.run_root / "events.jsonl", expected_run_id=plan.identity["run_id"]
    )
    assert events.state == "failed"
    assert [event["event_type"] for event in events.events].count("resume") == 0


def test_verification_binds_runtime_report_to_complete_event(tmp_path: Path) -> None:
    plan = _plan()
    result = run_training_condition(
        plan,
        tmp_path,
        condition="control",
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    report_path = result.run_root / "artifacts" / "runtime-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["network_access_performed"] = True
    report["runtime_report_sha256"] = canonical_sha256(
        {key: value for key, value in report.items() if key != "runtime_report_sha256"}
    )
    atomic_write_json(report_path, report)

    with pytest.raises(
        TrainingSmokeError,
        match="runtime report identity or network policy|complete event runtime-report",
    ):
        verify_training_run(
            plan,
            result.run_root,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )


def test_verification_rejects_coherently_rebound_invalid_runtime_report(
    tmp_path: Path,
) -> None:
    plan = _plan()
    result = run_training_condition(
        plan,
        tmp_path,
        condition="control",
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    report_path = result.run_root / "artifacts" / "runtime-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["schema_version"] = 99
    report["network_access_performed"] = True
    report["unexpected"] = "coherently-rebound"
    report["runtime_report_sha256"] = canonical_sha256(
        {key: value for key, value in report.items() if key != "runtime_report_sha256"}
    )
    atomic_write_json(report_path, report)

    events_path = result.run_root / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events[-1]["data"]["runtime_report_sha256"] = report[
        "runtime_report_sha256"
    ]
    events[-1]["event_sha256"] = canonical_sha256(
        {key: value for key, value in events[-1].items() if key != "event_sha256"}
    )
    atomic_write_bytes(
        events_path,
        b"".join(canonical_json_bytes(event) + b"\n" for event in events),
    )

    with pytest.raises(TrainingSmokeError, match="runtime report has invalid"):
        verify_training_run(
            plan,
            result.run_root,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )


def test_completed_run_verification_rehashes_step_three_checkpoint(tmp_path: Path) -> None:
    plan = _plan()
    result = run_training_condition(
        plan,
        tmp_path,
        condition="control",
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    checkpoint = result.run_root / "checkpoints" / "step-0003.pt"
    checkpoint.write_bytes(checkpoint.read_bytes() + b"tamper")

    with pytest.raises(TrainingSmokeError, match="checkpoint size mismatch"):
        verify_training_run(
            plan,
            result.run_root,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )


def test_invalid_final_state_cannot_publish_complete(tmp_path: Path) -> None:
    plan = _plan()
    with pytest.raises(TrainingSmokeError, match="token-count invariant"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: BadFinalStateBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    events = read_event_log(
        tmp_path / "control" / plan.identity["run_id"] / "events.jsonl",
        expected_run_id=plan.identity["run_id"],
    )
    assert events.state == "failed"
    assert all(event["event_type"] != "complete" for event in events.events)


def test_serialized_adapter_must_match_captured_state(tmp_path: Path) -> None:
    plan = _plan()
    with pytest.raises(TrainingSmokeError, match="serialized adapter"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: UnrelatedAdapterBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    events = read_event_log(
        tmp_path / "control" / plan.identity["run_id"] / "events.jsonl",
        expected_run_id=plan.identity["run_id"],
    )
    assert events.state == "failed"


def test_captured_losses_must_match_runner_losses(tmp_path: Path) -> None:
    plan = _plan()
    with pytest.raises(TrainingSmokeError, match="runner-owned losses"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: WrongLossStateBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    events = read_event_log(
        tmp_path / "control" / plan.identity["run_id"] / "events.jsonl",
        expected_run_id=plan.identity["run_id"],
    )
    assert events.state == "failed"


def test_verification_requires_condition_registry(tmp_path: Path) -> None:
    plan = _plan()
    result = run_training_condition(
        plan,
        tmp_path,
        condition="control",
        backend_factory=lambda current, state: ToyBackend(current, state),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    (result.run_root.parent / "registry.jsonl").unlink()

    with pytest.raises(TrainingSmokeError, match="condition registry"):
        verify_training_run(
            plan,
            result.run_root,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    with pytest.raises(TrainingSmokeError, match="immutable condition registry"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    assert not (result.run_root.parent / "registry.jsonl").exists()


def test_shared_training_lock_blocks_other_condition(tmp_path: Path) -> None:
    plan = _plan()
    shared_lock = tmp_path / ".locks" / "training-job.lock"
    with RunLock(shared_lock, run_id=plan.identity["run_id"]):
        with pytest.raises(Exception, match="lock already exists"):
            run_training_condition(
                plan,
                tmp_path,
                condition="resumed",
                interrupt_after=3,
                backend_factory=lambda current, state: ToyBackend(current, state),
                serialize=_json_serialize,
                deserialize=_json_deserialize,
                adapter_deserialize=_json_deserialize,
            )


def test_invalid_planned_interruption_is_rejected_before_run(tmp_path: Path) -> None:
    with pytest.raises(TrainingSmokeError, match="uninterrupted control"):
        run_training_condition(
            _plan(),
            tmp_path,
            condition="control",
            interrupt_after=3,
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )


def test_condition_request_matrix_is_enforced_before_initialization(
    tmp_path: Path,
) -> None:
    plan = _plan()
    with pytest.raises(TrainingSmokeError, match="requires the planned"):
        run_training_condition(
            plan,
            tmp_path,
            condition="resumed",
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    with pytest.raises(TrainingSmokeError, match="uninterrupted control"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            resume=True,
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    with pytest.raises(TrainingSmokeError, match="cannot resume"):
        run_training_condition(
            plan,
            tmp_path,
            condition="resumed",
            resume=True,
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    assert not (tmp_path / "control").exists()
    assert not (tmp_path / "resumed").exists()


def test_resumed_condition_enforces_cumulative_wall_limit_before_finals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan()
    plan.config["resource_limits"]["maximum_condition_wall_seconds"] = 4.5
    timer = [0.0]
    monkeypatch.setattr(training_smoke.time, "perf_counter", lambda: timer[0])

    interrupted = run_training_condition(
        plan,
        tmp_path,
        condition="resumed",
        interrupt_after=3,
        backend_factory=lambda current, state: TimedToyBackend(current, state, timer),
        serialize=_json_serialize,
        deserialize=_json_deserialize,
        adapter_deserialize=_json_deserialize,
    )
    assert interrupted.status == "interrupted"
    timer[0] = 0.0

    with pytest.raises(TrainingSmokeError, match="cumulative wall-time"):
        run_training_condition(
            plan,
            tmp_path,
            condition="resumed",
            resume=True,
            backend_factory=lambda current, state: TimedToyBackend(current, state, timer),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=_json_deserialize,
        )
    assert not (interrupted.run_root / "artifacts" / "final-manifest.json").exists()


def test_condition_enforces_wall_limit_after_final_integrity_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan()
    plan.config["resource_limits"]["maximum_condition_wall_seconds"] = 1.0
    timer = [0.0]
    adapter_loads = 0
    monkeypatch.setattr(training_smoke.time, "perf_counter", lambda: timer[0])

    def delayed_adapter_verification(payload: bytes):
        nonlocal adapter_loads
        adapter_loads += 1
        if adapter_loads == 2:
            timer[0] = 10.0
        return _json_deserialize(payload)

    with pytest.raises(TrainingSmokeError, match="cumulative wall-time"):
        run_training_condition(
            plan,
            tmp_path,
            condition="control",
            backend_factory=lambda current, state: ToyBackend(current, state),
            serialize=_json_serialize,
            deserialize=_json_deserialize,
            adapter_deserialize=delayed_adapter_verification,
        )

    run_root = tmp_path / "control" / plan.identity["run_id"]
    events = read_event_log(
        run_root / "events.jsonl", expected_run_id=plan.identity["run_id"]
    )
    assert events.state == "failed"
    assert not any(event["event_type"] == "complete" for event in events.events)
    final_names = {
        "final-state.pt",
        "final-state-reference.json",
        "adapter.safetensors",
        "final-manifest.json",
        "runtime-report.json",
    }
    assert not any((run_root / "artifacts" / name).exists() for name in final_names)
    failure = next(event for event in events.events if event["event_type"] == "fail")
    attempt_path = run_root / failure["data"]["attempt_report"]["path"]
    attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt["status"] == "failed"
