"""Deterministic tiny-training plan, checkpoint, and resume foundations.

This module stays importable without Torch.  The target CUDA backend is loaded
lazily by the benchmark script, while CI exercises the same state machine and
integrity contracts with an injected dependency-free backend.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import stat
import time
from typing import Any, Protocol

from .path_policy import PortablePathError, portable_relative_path
from .run_registry import (
    RunLock,
    RunStore,
    atomic_write_bytes,
    atomic_write_json,
    build_run_identity,
    canonical_json_bytes,
    canonical_sha256,
    ensure_registry_entry,
    read_event_log,
    read_json,
    read_registry,
    sha256_file,
)


class TrainingSmokeError(RuntimeError):
    """Raised when the bounded training gate cannot be proved safely."""


_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "run_name",
        "run_kind",
        "status",
        "scientific_claim_authorized",
        "network_allowed",
        "external_spend_cad",
        "max_parallel_jobs",
        "artifact_id",
        "device",
        "base_dtype",
        "adapter_dtype",
        "seed",
        "batch_size",
        "sequence_length",
        "steps",
        "checkpoint_after_step",
        "source",
        "lora",
        "optimizer",
        "scheduler",
        "gradient",
        "determinism",
        "resource_limits",
    }
)
_SOURCE_FIELDS = frozenset(
    {"manifest", "content_root", "record_ids", "append_eos", "cycle_to_fit"}
)
_LORA_FIELDS = frozenset(
    {
        "rank",
        "alpha",
        "dropout",
        "bias",
        "target_template",
        "target_layers",
        "target_count",
        "trainable_parameters",
    }
)
_OPTIMIZER_FIELDS = frozenset(
    {
        "name",
        "learning_rate",
        "betas",
        "epsilon",
        "weight_decay",
        "amsgrad",
        "maximize",
        "foreach",
        "capturable",
        "differentiable",
        "fused",
    }
)
_SCHEDULER_FIELDS = frozenset({"name", "factor"})
_GRADIENT_FIELDS = frozenset(
    {
        "max_norm",
        "checkpointing",
        "checkpointing_use_reentrant",
        "loss_scaling",
        "scaler_init_scale",
        "scaler_growth_factor",
        "scaler_backoff_factor",
        "scaler_growth_interval",
        "scaler_enabled",
    }
)
_DETERMINISM_FIELDS = frozenset(
    {
        "algorithms",
        "cublas_workspace_config",
        "tf32",
        "cudnn_benchmark",
        "shuffle",
        "workers",
    }
)
_RESOURCE_FIELDS = frozenset(
    {
        "minimum_preload_free_vram_bytes",
        "maximum_process_peak_reserved_bytes",
        "minimum_postload_global_free_vram_bytes",
        "minimum_output_free_bytes",
        "maximum_checkpoint_bytes",
        "maximum_condition_wall_seconds",
        "ram_threshold_enforced",
    }
)


@dataclass(frozen=True)
class PackedTokens:
    blocks: tuple[tuple[int, ...], ...]
    matrix_sha256: str
    input_tokens: int
    causal_targets: int


@dataclass(frozen=True)
class TrainingPlan:
    config: dict[str, Any]
    plan: dict[str, Any]
    identity: dict[str, Any]
    token_blocks: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class TrainingCheckpointState:
    completed_steps: int
    cursor: int
    tokens_seen: int
    losses: tuple[float, ...]
    adapter_state: Mapping[str, Any]
    optimizer_state: Mapping[str, Any]
    scheduler_state: Mapping[str, Any]
    scaler_state: Mapping[str, Any]
    cpu_rng_state: Any
    cuda_rng_states: tuple[Any, ...]


@dataclass(frozen=True)
class CheckpointRef:
    pointer: dict[str, Any]
    state_path: Path


@dataclass(frozen=True)
class StepResult:
    loss: float
    runtime_metrics: Mapping[str, Any]


@dataclass(frozen=True)
class TrainingRunResult:
    run_id: str
    run_root: Path
    status: str
    completed_steps: int
    final_manifest: dict[str, Any] | None


class TrainingBackend(Protocol):
    @property
    def base_identity_sha256(self) -> str: ...

    def run_step(self, token_block: Sequence[int], step: int) -> StepResult: ...

    def capture_state(
        self,
        *,
        completed_steps: int,
        cursor: int,
        tokens_seen: int,
        losses: Sequence[float],
    ) -> TrainingCheckpointState: ...

    def serialize_adapter(self, adapter_state: Mapping[str, Any]) -> bytes: ...

    def close(self) -> None: ...


BackendFactory = Callable[[TrainingPlan, TrainingCheckpointState | None], TrainingBackend]
StateSerializer = Callable[[Mapping[str, Any]], bytes]
StateDeserializer = Callable[[bytes], Mapping[str, Any]]
AdapterDeserializer = Callable[[bytes], Mapping[str, Any]]


def load_training_config(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TrainingSmokeError(f"cannot load training config: {error}") from error
    if not isinstance(raw, dict):
        raise TrainingSmokeError("training config root must be an object")
    errors = validate_training_config(raw)
    if errors:
        raise TrainingSmokeError("; ".join(errors))
    return raw


def _exact_fields(value: Any, expected: frozenset[str], label: str) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{label} must be an object"]
    if set(value) != expected:
        return [f"{label} has unexpected or missing fields"]
    return []


def validate_training_config(config: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate the one deliberately narrow E5 engineering profile."""

    errors = _exact_fields(config, _CONFIG_FIELDS, "training config")
    if errors:
        return tuple(errors)

    exact_top = {
        "schema_version": 1,
        "run_kind": "tiny-lora-training-smoke",
        "status": "frozen",
        "scientific_claim_authorized": False,
        "network_allowed": False,
        "external_spend_cad": 0,
        "max_parallel_jobs": 1,
        "artifact_id": "pythia-1b-deduped-main",
        "device": "cuda",
        "base_dtype": "float16",
        "adapter_dtype": "float32",
        "seed": 17,
        "batch_size": 1,
        "sequence_length": 128,
        "steps": 5,
        "checkpoint_after_step": 3,
    }
    if not isinstance(config.get("run_name"), str) or not config["run_name"]:
        errors.append("run_name must be a nonempty string")
    for key, expected in exact_top.items():
        if config.get(key) != expected:
            errors.append(f"{key} must be exactly {expected!r}")

    source = config.get("source")
    errors.extend(_exact_fields(source, _SOURCE_FIELDS, "source"))
    if isinstance(source, Mapping):
        expected_source = {
            "manifest": "tests/fixtures/content-integrity/manifest.jsonl",
            "content_root": "tests/fixtures/content-integrity/documents",
            "record_ids": ["control-neutral", "calibration-neutral"],
            "append_eos": True,
            "cycle_to_fit": True,
        }
        for key, expected in expected_source.items():
            if source.get(key) != expected:
                errors.append(f"source.{key} must be exactly {expected!r}")

    lora = config.get("lora")
    errors.extend(_exact_fields(lora, _LORA_FIELDS, "lora"))
    if isinstance(lora, Mapping):
        expected_lora = {
            "rank": 4,
            "alpha": 8,
            "dropout": 0.0,
            "bias": "none",
            "target_template": "gpt_neox.layers.{layer}.attention.query_key_value",
            "target_layers": list(range(16)),
            "target_count": 16,
            "trainable_parameters": 524_288,
        }
        for key, expected in expected_lora.items():
            if lora.get(key) != expected:
                errors.append(f"lora.{key} must be exactly {expected!r}")

    optimizer = config.get("optimizer")
    errors.extend(_exact_fields(optimizer, _OPTIMIZER_FIELDS, "optimizer"))
    if isinstance(optimizer, Mapping):
        expected_optimizer = {
            "name": "AdamW",
            "learning_rate": 0.0001,
            "betas": [0.9, 0.999],
            "epsilon": 1e-8,
            "weight_decay": 0.0,
            "amsgrad": False,
            "maximize": False,
            "foreach": False,
            "capturable": False,
            "differentiable": False,
            "fused": False,
        }
        for key, expected in expected_optimizer.items():
            if optimizer.get(key) != expected:
                errors.append(f"optimizer.{key} must be exactly {expected!r}")

    scheduler = config.get("scheduler")
    errors.extend(_exact_fields(scheduler, _SCHEDULER_FIELDS, "scheduler"))
    if isinstance(scheduler, Mapping) and dict(scheduler) != {
        "name": "constant",
        "factor": 1.0,
    }:
        errors.append("scheduler must be the exact constant schedule")

    gradient = config.get("gradient")
    errors.extend(_exact_fields(gradient, _GRADIENT_FIELDS, "gradient"))
    if isinstance(gradient, Mapping) and dict(gradient) != {
        "max_norm": 1.0,
        "checkpointing": True,
        "checkpointing_use_reentrant": False,
        "loss_scaling": "dynamic-fp16",
        "scaler_init_scale": 65536.0,
        "scaler_growth_factor": 2.0,
        "scaler_backoff_factor": 0.5,
        "scaler_growth_interval": 2000,
        "scaler_enabled": True,
    }:
        errors.append("gradient must match the frozen E5 gradient policy")

    determinism = config.get("determinism")
    errors.extend(_exact_fields(determinism, _DETERMINISM_FIELDS, "determinism"))
    if isinstance(determinism, Mapping) and dict(determinism) != {
        "algorithms": True,
        "cublas_workspace_config": ":4096:8",
        "tf32": False,
        "cudnn_benchmark": False,
        "shuffle": False,
        "workers": 0,
    }:
        errors.append("determinism must match the frozen E5 policy")

    resources = config.get("resource_limits")
    errors.extend(_exact_fields(resources, _RESOURCE_FIELDS, "resource_limits"))
    expected_resources = {
        "minimum_preload_free_vram_bytes": 3_695_181_824,
        "maximum_process_peak_reserved_bytes": 3_158_310_912,
        "minimum_postload_global_free_vram_bytes": 1_610_612_736,
        "minimum_output_free_bytes": 134_217_728,
        "maximum_checkpoint_bytes": 16_777_216,
        "maximum_condition_wall_seconds": 900,
        "ram_threshold_enforced": False,
    }
    if isinstance(resources, Mapping):
        for key, expected in expected_resources.items():
            if resources.get(key) != expected:
                errors.append(f"resource_limits.{key} must be exactly {expected!r}")
    return tuple(errors)


def pack_token_documents(
    token_documents: Sequence[Sequence[int]],
    eos_id: int,
    *,
    steps: int = 5,
    sequence_length: int = 128,
) -> PackedTokens:
    """Append EOS per document, cycle, and freeze exactly ``steps x length``."""

    if not isinstance(eos_id, int) or isinstance(eos_id, bool) or eos_id < 0:
        raise TrainingSmokeError("eos_id must be a nonnegative integer")
    for label, value in (("steps", steps), ("sequence_length", sequence_length)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise TrainingSmokeError(f"{label} must be a positive integer")
    if not token_documents:
        raise TrainingSmokeError("token_documents must not be empty")
    cycle: list[int] = []
    for document_index, document in enumerate(token_documents):
        if not document:
            raise TrainingSmokeError(f"token_documents[{document_index}] is empty")
        for token in document:
            if not isinstance(token, int) or isinstance(token, bool) or token < 0:
                raise TrainingSmokeError("token IDs must be nonnegative integers")
            cycle.append(token)
        cycle.append(eos_id)
    required = steps * sequence_length
    values = tuple(cycle[index % len(cycle)] for index in range(required))
    blocks = tuple(
        values[index : index + sequence_length]
        for index in range(0, required, sequence_length)
    )
    matrix_sha256 = canonical_sha256(
        {"dtype": "int64", "shape": [steps, sequence_length], "values": values}
    )
    return PackedTokens(
        blocks=blocks,
        matrix_sha256=matrix_sha256,
        input_tokens=required,
        causal_targets=steps * (sequence_length - 1),
    )


def full_weight_adamw_capacity(
    parameter_count: int,
    gpu_total_bytes: int,
) -> dict[str, Any]:
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 1
        for value in (parameter_count, gpu_total_bytes)
    ):
        raise TrainingSmokeError("capacity inputs must be positive integers")
    component = parameter_count * 2
    total = parameter_count * 8
    return {
        "assumption": "fp16 weights + fp16 gradients + two fp16 Adam moments",
        "weights_bytes": component,
        "gradients_bytes": component,
        "two_moments_bytes": component * 2,
        "optimistic_total_bytes": total,
        "gpu_total_bytes": gpu_total_bytes,
        "shortfall_bytes": max(total - gpu_total_bytes, 0),
        "fits_before_activations": total <= gpu_total_bytes,
        "scope": "device-resident full-weight AdamW lower bound only",
    }


def validate_load_report(
    report: Mapping[str, Any],
    *,
    artifact: Mapping[str, Any],
    git_commit: str,
) -> tuple[str, ...]:
    errors: list[str] = []
    expected = {
        "status": "complete",
        "mode": "execute",
        "artifact_id": artifact.get("id"),
        "repository": artifact.get("repository"),
        "revision": artifact.get("revision"),
        "local_model_load_only": True,
        "network_download_permitted": False,
        "device": "cuda",
        "requested_dtype": "float16",
        "model_dtype": "torch.float16",
        "parameter_count": artifact.get("parameter_count"),
    }
    for key, value in expected.items():
        if report.get(key) != value:
            errors.append(f"load report {key} mismatch")
    logits = report.get("logits_validation")
    if not isinstance(logits, Mapping) or logits.get("finite") is not True:
        errors.append("load report does not prove finite logits")
    integrity = report.get("artifact_integrity")
    if not isinstance(integrity, Mapping) or integrity.get("status") != "verified":
        errors.append("load report artifact integrity is not verified")
    else:
        expected_files = [
            {
                "filename": item["filename"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
                "verified": True,
            }
            for item in artifact.get("required_files", [])
        ]
        if integrity.get("files") != expected_files:
            errors.append("load report required-file integrity mismatch")
    preflight = report.get("resource_preflight")
    if not isinstance(preflight, Mapping) or preflight.get("git_head") != git_commit:
        errors.append("load report Git commit mismatch")
    validation = report.get("loaded_model_validation")
    expected_validation = {
        "architecture": artifact.get("architecture"),
        "model_type": artifact.get("model_type"),
        "parameter_count": artifact.get("parameter_count"),
        "parameter_dtypes": ["torch.float16"],
        "verified": True,
    }
    if not isinstance(validation, Mapping):
        errors.append("load report model validation is absent")
    elif dict(validation) != expected_validation:
        errors.append("load report model validation mismatch")
    return tuple(errors)


def build_training_plan(
    config: Mapping[str, Any],
    *,
    git_commit: str,
    config_sha256: str,
    model_manifest_sha256: str,
    artifact: Mapping[str, Any],
    load_report: Mapping[str, Any],
    load_report_sha256: str,
    content_manifest_sha256: str,
    content_records: Sequence[Mapping[str, Any]],
    tokenizer_identity: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
    packed_tokens: PackedTokens,
) -> TrainingPlan:
    errors = validate_training_config(config)
    if errors:
        raise TrainingSmokeError("; ".join(errors))
    if not isinstance(git_commit, str) or len(git_commit) != 40:
        raise TrainingSmokeError("git_commit must be an exact 40-character SHA")
    load_errors = validate_load_report(
        load_report,
        artifact=artifact,
        git_commit=git_commit,
    )
    if load_errors:
        raise TrainingSmokeError("; ".join(load_errors))
    expected_steps = int(config["steps"])
    expected_length = int(config["sequence_length"])
    if len(packed_tokens.blocks) != expected_steps or any(
        len(block) != expected_length for block in packed_tokens.blocks
    ):
        raise TrainingSmokeError("packed token matrix shape does not match config")
    if packed_tokens.input_tokens != 640 or packed_tokens.causal_targets != 635:
        raise TrainingSmokeError("packed token dose must be exactly 640/635")

    normalized_records = [json.loads(canonical_json_bytes(record)) for record in content_records]
    plan_body: dict[str, Any] = {
        "schema_version": 1,
        "run_kind": config["run_kind"],
        "status": "frozen",
        "git_commit": git_commit,
        "config_sha256": config_sha256,
        "model_manifest_sha256": model_manifest_sha256,
        "artifact": {
            "id": artifact["id"],
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "architecture": artifact["architecture"],
            "model_type": artifact["model_type"],
            "parameter_count": artifact["parameter_count"],
            "required_files": artifact["required_files"],
        },
        "successful_load_report_sha256": load_report_sha256,
        "content_manifest_sha256": content_manifest_sha256,
        "content_records": normalized_records,
        "tokenizer_identity": json.loads(canonical_json_bytes(tokenizer_identity)),
        "token_matrix_sha256": packed_tokens.matrix_sha256,
        "input_tokens": packed_tokens.input_tokens,
        "causal_targets": packed_tokens.causal_targets,
        "training": {
            key: json.loads(canonical_json_bytes(config[key]))
            for key in (
                "device",
                "base_dtype",
                "adapter_dtype",
                "seed",
                "batch_size",
                "sequence_length",
                "steps",
                "checkpoint_after_step",
                "lora",
                "optimizer",
                "scheduler",
                "gradient",
                "determinism",
                "resource_limits",
            )
        },
        "runtime_identity": json.loads(canonical_json_bytes(runtime_identity)),
        "network_access_permitted": False,
        "external_spend_cad": 0,
        "scientific_claim_authorized": False,
    }
    plan = dict(plan_body)
    plan["plan_sha256"] = canonical_sha256(plan_body)
    identity = build_run_identity(
        {
            "run_kind": config["run_kind"],
            "plan_sha256": plan["plan_sha256"],
            "training_plan": plan_body,
        }
    )
    return TrainingPlan(
        config=json.loads(canonical_json_bytes(config)),
        plan=plan,
        identity=identity,
        token_blocks=packed_tokens.blocks,
    )


def _tensor_record(value: Any) -> dict[str, Any] | None:
    module = type(value).__module__.split(".", 1)[0]
    if module != "torch" or not all(
        hasattr(value, attribute) for attribute in ("detach", "dtype", "shape")
    ):
        return None
    try:
        import torch
    except ImportError as error:  # pragma: no cover - only possible with a fake tensor
        raise TrainingSmokeError("Torch tensor hashing requires Torch") from error
    tensor = value.detach().cpu().contiguous()
    raw = tensor.reshape(-1).view(torch.uint8).numpy().tobytes()
    return {
        "kind": "tensor",
        "dtype": str(tensor.dtype),
        "shape": [int(size) for size in tensor.shape],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _semantic_value(value: Any) -> Any:
    tensor = _tensor_record(value)
    if tensor is not None:
        return tensor
    if isinstance(value, Mapping):
        encoded: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str):
                semantic_key = f"str:{key}"
            elif isinstance(key, int) and not isinstance(key, bool):
                semantic_key = f"int:{key}"
            else:
                raise TrainingSmokeError("semantic mapping keys must be strings or integers")
            if semantic_key in encoded:
                raise TrainingSmokeError("semantic mapping contains a normalized key collision")
            encoded[semantic_key] = _semantic_value(item)
        return {key: encoded[key] for key in sorted(encoded)}
    if isinstance(value, (list, tuple)):
        return [_semantic_value(item) for item in value]
    if isinstance(value, bytes):
        return {
            "kind": "bytes",
            "size": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    if isinstance(value, float) and not math.isfinite(value):
        raise TrainingSmokeError("semantic state contains a non-finite float")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TrainingSmokeError(
        f"unsupported semantic state type: {type(value).__module__}.{type(value).__name__}"
    )


def semantic_state_sha256(value: Any) -> str:
    return canonical_sha256(_semantic_value(value))


def _state_payload(state: TrainingCheckpointState) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "completed_steps": state.completed_steps,
        "cursor": state.cursor,
        "tokens_seen": state.tokens_seen,
        "losses": list(state.losses),
        "adapter_state": dict(state.adapter_state),
        "optimizer_state": dict(state.optimizer_state),
        "scheduler_state": dict(state.scheduler_state),
        "scaler_state": dict(state.scaler_state),
        "cpu_rng_state": state.cpu_rng_state,
        "cuda_rng_states": list(state.cuda_rng_states),
    }


def _state_from_payload(payload: Mapping[str, Any]) -> TrainingCheckpointState:
    expected = {
        "schema_version",
        "completed_steps",
        "cursor",
        "tokens_seen",
        "losses",
        "adapter_state",
        "optimizer_state",
        "scheduler_state",
        "scaler_state",
        "cpu_rng_state",
        "cuda_rng_states",
    }
    if set(payload) != expected or payload.get("schema_version") != 1:
        raise TrainingSmokeError("training state has unexpected fields or schema")
    completed = payload.get("completed_steps")
    cursor = payload.get("cursor")
    tokens_seen = payload.get("tokens_seen")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (completed, cursor, tokens_seen)
    ):
        raise TrainingSmokeError("training state counters must be nonnegative integers")
    losses = payload.get("losses")
    if not isinstance(losses, list) or len(losses) != completed or not all(
        isinstance(loss, (int, float)) and math.isfinite(float(loss)) for loss in losses
    ):
        raise TrainingSmokeError("training state loss prefix is invalid")
    mappings: dict[str, Mapping[str, Any]] = {}
    for key in ("adapter_state", "optimizer_state", "scheduler_state", "scaler_state"):
        value = payload.get(key)
        if not isinstance(value, Mapping):
            raise TrainingSmokeError(f"training state {key} must be an object")
        mappings[key] = value
    cuda_rng = payload.get("cuda_rng_states")
    if not isinstance(cuda_rng, list):
        raise TrainingSmokeError("training state CUDA RNG collection must be a list")
    return TrainingCheckpointState(
        completed_steps=completed,
        cursor=cursor,
        tokens_seen=tokens_seen,
        losses=tuple(float(loss) for loss in losses),
        adapter_state=dict(mappings["adapter_state"]),
        optimizer_state=dict(mappings["optimizer_state"]),
        scheduler_state=dict(mappings["scheduler_state"]),
        scaler_state=dict(mappings["scaler_state"]),
        cpu_rng_state=payload.get("cpu_rng_state"),
        cuda_rng_states=tuple(cuda_rng),
    )


def state_semantic_hashes(state: TrainingCheckpointState) -> dict[str, str]:
    components = {
        "adapter": state.adapter_state,
        "optimizer": state.optimizer_state,
        "scheduler": state.scheduler_state,
        "scaler": state.scaler_state,
        "cpu_rng": state.cpu_rng_state,
        "cuda_rng": state.cuda_rng_states,
        "losses": state.losses,
        "counters": {
            "completed_steps": state.completed_steps,
            "cursor": state.cursor,
            "tokens_seen": state.tokens_seen,
        },
    }
    hashes = {key: semantic_state_sha256(value) for key, value in components.items()}
    hashes["complete_state"] = canonical_sha256(hashes)
    return hashes


def _validate_state_position(
    state: TrainingCheckpointState,
    plan: TrainingPlan,
    *,
    expected_steps: int,
) -> None:
    sequence_length = int(plan.config["sequence_length"])
    if state.completed_steps != expected_steps:
        raise TrainingSmokeError("training state completed-step invariant failed")
    if state.cursor != expected_steps:
        raise TrainingSmokeError("training state cursor invariant failed")
    if state.tokens_seen != expected_steps * sequence_length:
        raise TrainingSmokeError("training state token-count invariant failed")
    if len(state.losses) != expected_steps:
        raise TrainingSmokeError("training state loss-prefix invariant failed")
    if sorted(state.adapter_state) == []:
        raise TrainingSmokeError("training state adapter set must not be empty")


def _torch_serialize(payload: Mapping[str, Any]) -> bytes:
    try:
        import torch
    except ImportError as error:
        raise TrainingSmokeError("Torch is required to serialize target checkpoints") from error
    buffer = io.BytesIO()
    torch.save(dict(payload), buffer)
    return buffer.getvalue()


def _torch_deserialize(payload: bytes) -> Mapping[str, Any]:
    try:
        import torch
    except ImportError as error:
        raise TrainingSmokeError("Torch is required to deserialize target checkpoints") from error
    value = torch.load(io.BytesIO(payload), map_location="cpu", weights_only=True)
    if not isinstance(value, Mapping):
        raise TrainingSmokeError("deserialized training state must be an object")
    return value


def _safetensors_deserialize(payload: bytes) -> Mapping[str, Any]:
    try:
        from safetensors.torch import load
    except ImportError as error:
        raise TrainingSmokeError("Safetensors is required to verify the adapter") from error
    value = load(payload)
    if not isinstance(value, Mapping):
        raise TrainingSmokeError("deserialized adapter must be an object")
    return value


_POINTER_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "identity_sha256",
        "state_path",
        "state_size_bytes",
        "state_file_sha256",
        "completed_steps",
        "cursor",
        "tokens_seen",
        "loss_count",
        "semantic_hashes",
        "checkpoint_sha256",
    }
)


def save_training_checkpoint(
    run_root: str | Path,
    state: TrainingCheckpointState,
    identity: Mapping[str, Any],
    *,
    serialize: StateSerializer | None = None,
    maximum_bytes: int = 16_777_216,
) -> CheckpointRef:
    root = Path(run_root)
    payload = (serialize or _torch_serialize)(_state_payload(state))
    if len(payload) > maximum_bytes:
        raise TrainingSmokeError(
            f"training checkpoint exceeds limit: {len(payload)} > {maximum_bytes}"
        )
    relative = Path("checkpoints") / f"step-{state.completed_steps:04d}.pt"
    state_path = root / relative
    pointer_path = root / "checkpoint.json"
    if state_path.exists() or pointer_path.exists():
        raise TrainingSmokeError(
            "immutable training checkpoint state or pointer already exists"
        )
    atomic_write_bytes(state_path, payload)
    pointer: dict[str, Any] = {
        "schema_version": 1,
        "run_id": identity["run_id"],
        "identity_sha256": identity["identity_sha256"],
        "state_path": relative.as_posix(),
        "state_size_bytes": len(payload),
        "state_file_sha256": hashlib.sha256(payload).hexdigest(),
        "completed_steps": state.completed_steps,
        "cursor": state.cursor,
        "tokens_seen": state.tokens_seen,
        "loss_count": len(state.losses),
        "semantic_hashes": state_semantic_hashes(state),
    }
    pointer["checkpoint_sha256"] = canonical_sha256(pointer)
    atomic_write_json(pointer_path, pointer)
    return CheckpointRef(pointer=pointer, state_path=state_path)


def _validate_pointer(
    pointer: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
    expected_step: int | None,
) -> None:
    if set(pointer) != _POINTER_FIELDS or pointer.get("schema_version") != 1:
        raise TrainingSmokeError("checkpoint pointer has unexpected fields or schema")
    if pointer.get("run_id") != identity.get("run_id"):
        raise TrainingSmokeError("checkpoint run_id mismatch")
    if pointer.get("identity_sha256") != identity.get("identity_sha256"):
        raise TrainingSmokeError("checkpoint identity hash mismatch")
    observed_hash = pointer.get("checkpoint_sha256")
    expected_hash = canonical_sha256(
        {key: pointer[key] for key in pointer if key != "checkpoint_sha256"}
    )
    if observed_hash != expected_hash:
        raise TrainingSmokeError("checkpoint pointer hash mismatch")
    if expected_step is not None and pointer.get("completed_steps") != expected_step:
        raise TrainingSmokeError("checkpoint completed step mismatch")
    if expected_step is not None and pointer.get("state_path") != (
        f"checkpoints/step-{expected_step:04d}.pt"
    ):
        raise TrainingSmokeError("checkpoint state path is not the exact frozen path")


def load_training_checkpoint(
    run_root: str | Path,
    identity: Mapping[str, Any],
    *,
    expected_step: int | None = None,
    expected_adapter_keys: Sequence[str] | None = None,
    deserialize: StateDeserializer | None = None,
    maximum_bytes: int = 16_777_216,
) -> TrainingCheckpointState:
    root = Path(run_root)
    pointer = read_json(root / "checkpoint.json")
    if not isinstance(pointer, Mapping):
        raise TrainingSmokeError("checkpoint pointer root must be an object")
    _validate_pointer(pointer, identity=identity, expected_step=expected_step)
    try:
        relative = portable_relative_path(
            pointer["state_path"], label="training checkpoint state path", suffix=".pt"
        )
    except (KeyError, PortablePathError) as error:
        raise TrainingSmokeError(str(error)) from error
    state_path = (root / relative).resolve(strict=False)
    try:
        state_path.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise TrainingSmokeError("training checkpoint escapes the run root") from error
    if not state_path.is_file():
        raise TrainingSmokeError("training checkpoint state file is missing")
    declared_size = pointer.get("state_size_bytes")
    if (
        not isinstance(declared_size, int)
        or isinstance(declared_size, bool)
        or declared_size < 1
        or declared_size > maximum_bytes
    ):
        raise TrainingSmokeError("training checkpoint declared size is invalid")
    if state_path.stat().st_size != declared_size:
        raise TrainingSmokeError("training checkpoint size mismatch")
    payload = state_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != pointer.get("state_file_sha256"):
        raise TrainingSmokeError("training checkpoint file hash mismatch")
    # Deserialization happens only after path, size, and content hash validation.
    raw_state = (deserialize or _torch_deserialize)(payload)
    state = _state_from_payload(raw_state)
    if state.completed_steps != pointer.get("completed_steps"):
        raise TrainingSmokeError("checkpoint state completed step mismatch")
    if state.cursor != pointer.get("cursor") or state.tokens_seen != pointer.get("tokens_seen"):
        raise TrainingSmokeError("checkpoint state cursor mismatch")
    if len(state.losses) != pointer.get("loss_count"):
        raise TrainingSmokeError("checkpoint state loss count mismatch")
    if state_semantic_hashes(state) != pointer.get("semantic_hashes"):
        raise TrainingSmokeError("checkpoint semantic state hash mismatch")
    if expected_adapter_keys is not None and sorted(state.adapter_state) != sorted(expected_adapter_keys):
        raise TrainingSmokeError("checkpoint adapter key set mismatch")
    return state


def _save_final_state(
    run_root: Path,
    state: TrainingCheckpointState,
    identity: Mapping[str, Any],
    *,
    serialize: StateSerializer | None,
    maximum_bytes: int,
) -> dict[str, Any]:
    payload = (serialize or _torch_serialize)(_state_payload(state))
    if len(payload) > maximum_bytes:
        raise TrainingSmokeError("final training state exceeds checkpoint size limit")
    state_path = run_root / "artifacts" / "final-state.pt"
    reference_path = run_root / "artifacts" / "final-state-reference.json"
    if state_path.exists() or reference_path.exists():
        raise TrainingSmokeError("immutable final training state already exists")
    atomic_write_bytes(state_path, payload)
    reference = {
        "schema_version": 1,
        "run_id": identity["run_id"],
        "identity_sha256": identity["identity_sha256"],
        "state_path": "artifacts/final-state.pt",
        "state_size_bytes": len(payload),
        "state_file_sha256": hashlib.sha256(payload).hexdigest(),
        "semantic_hashes": state_semantic_hashes(state),
    }
    reference["reference_sha256"] = canonical_sha256(reference)
    atomic_write_json(reference_path, reference)
    return reference


def _load_final_state(
    run_root: Path,
    identity: Mapping[str, Any],
    *,
    deserialize: StateDeserializer | None,
    maximum_bytes: int = 16_777_216,
) -> tuple[TrainingCheckpointState, dict[str, Any]]:
    reference = read_json(run_root / "artifacts" / "final-state-reference.json")
    if not isinstance(reference, Mapping):
        raise TrainingSmokeError("final state reference root must be an object")
    expected_fields = {
        "schema_version", "run_id", "identity_sha256", "state_path",
        "state_size_bytes", "state_file_sha256", "semantic_hashes", "reference_sha256",
    }
    if set(reference) != expected_fields or reference.get("schema_version") != 1:
        raise TrainingSmokeError("final state reference has invalid fields")
    if reference.get("run_id") != identity.get("run_id") or reference.get("identity_sha256") != identity.get("identity_sha256"):
        raise TrainingSmokeError("final state identity mismatch")
    if reference.get("state_path") != "artifacts/final-state.pt":
        raise TrainingSmokeError("final state path is not the exact frozen path")
    if reference.get("reference_sha256") != canonical_sha256(
        {key: reference[key] for key in reference if key != "reference_sha256"}
    ):
        raise TrainingSmokeError("final state reference hash mismatch")
    try:
        relative = portable_relative_path(reference["state_path"], label="final state path", suffix=".pt")
    except PortablePathError as error:
        raise TrainingSmokeError(str(error)) from error
    state_path = (run_root / relative).resolve(strict=False)
    try:
        state_path.relative_to(run_root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise TrainingSmokeError("final state escapes run root") from error
    declared_size = reference.get("state_size_bytes")
    if (
        not isinstance(declared_size, int)
        or isinstance(declared_size, bool)
        or declared_size < 1
        or declared_size > maximum_bytes
    ):
        raise TrainingSmokeError("final state declared size is invalid")
    if not state_path.is_file() or state_path.stat().st_size != declared_size:
        raise TrainingSmokeError("final state physical integrity mismatch")
    payload = state_path.read_bytes()
    if len(payload) != reference.get("state_size_bytes") or hashlib.sha256(payload).hexdigest() != reference.get("state_file_sha256"):
        raise TrainingSmokeError("final state physical integrity mismatch")
    state = _state_from_payload((deserialize or _torch_deserialize)(payload))
    if state_semantic_hashes(state) != reference.get("semantic_hashes"):
        raise TrainingSmokeError("final state semantic integrity mismatch")
    return state, dict(reference)


def _final_manifest(
    plan: TrainingPlan,
    state: TrainingCheckpointState,
    *,
    base_identity_sha256: str,
    adapter_file_sha256: str,
    adapter_size_bytes: int,
    adapter_semantic_sha256: str,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": plan.identity["run_id"],
        "identity_sha256": plan.identity["identity_sha256"],
        "plan_sha256": plan.plan["plan_sha256"],
        "base_identity_sha256": base_identity_sha256,
        "completed_steps": state.completed_steps,
        "cursor": state.cursor,
        "tokens_seen": state.tokens_seen,
        "causal_targets_seen": state.completed_steps * (int(plan.config["sequence_length"]) - 1),
        "losses": list(state.losses),
        "state_semantic_hashes": state_semantic_hashes(state),
        "adapter_artifact": {
            "path": "artifacts/adapter.safetensors",
            "size_bytes": adapter_size_bytes,
            "file_sha256": adapter_file_sha256,
            "semantic_sha256": adapter_semantic_sha256,
        },
        "network_access_performed": False,
        "scientific_claim_authorized": False,
        "evidence_scope": "bounded training/checkpoint/resume engineering only",
    }
    manifest["final_manifest_sha256"] = canonical_sha256(manifest)
    return manifest


def verify_training_run(
    plan: TrainingPlan,
    run_root: str | Path,
    *,
    deserialize: StateDeserializer | None = None,
    adapter_deserialize: AdapterDeserializer | None = None,
    require_complete: bool = True,
    expected_condition: str | None = None,
) -> dict[str, Any]:
    root = Path(run_root)
    store = RunStore.load(root)
    if store.identity != plan.identity:
        raise TrainingSmokeError("run identity differs from the supplied training plan")
    registry = read_registry(root.parent / "registry.jsonl")
    registry_matches = [
        entry
        for entry in registry.entries
        if entry.get("run_id") == store.run_id
        and entry.get("identity_sha256") == plan.identity["identity_sha256"]
    ]
    if len(registry_matches) != 1:
        raise TrainingSmokeError("condition registry lacks the exact run identity")
    expected_state = "complete" if require_complete else "running"
    if store.state != expected_state:
        raise TrainingSmokeError(
            f"training run state must be {expected_state!r}, observed {store.state!r}"
        )
    state, _ = _load_final_state(root, plan.identity, deserialize=deserialize)
    _validate_state_position(state, plan, expected_steps=int(plan.config["steps"]))
    checkpoint_state = load_training_checkpoint(
        root,
        plan.identity,
        expected_step=int(plan.config["checkpoint_after_step"]),
        expected_adapter_keys=sorted(state.adapter_state),
        deserialize=deserialize,
    )
    _validate_state_position(
        checkpoint_state,
        plan,
        expected_steps=int(plan.config["checkpoint_after_step"]),
    )
    if checkpoint_state.losses != state.losses[: checkpoint_state.completed_steps]:
        raise TrainingSmokeError("checkpoint losses are not the final-state prefix")
    manifest = read_json(root / "artifacts" / "final-manifest.json")
    if not isinstance(manifest, Mapping):
        raise TrainingSmokeError("final training manifest root must be an object")
    expected_manifest_fields = {
        "schema_version", "run_id", "identity_sha256", "plan_sha256",
        "base_identity_sha256", "completed_steps", "cursor", "tokens_seen",
        "causal_targets_seen", "losses", "state_semantic_hashes",
        "adapter_artifact", "network_access_performed",
        "scientific_claim_authorized", "evidence_scope", "final_manifest_sha256",
    }
    if set(manifest) != expected_manifest_fields or manifest.get("schema_version") != 1:
        raise TrainingSmokeError("final training manifest has invalid fields or schema")
    observed_hash = manifest.get("final_manifest_sha256")
    expected_hash = canonical_sha256(
        {key: manifest[key] for key in manifest if key != "final_manifest_sha256"}
    )
    if observed_hash != expected_hash:
        raise TrainingSmokeError("final training manifest hash mismatch")
    expected_core = {
        "run_id": plan.identity["run_id"],
        "identity_sha256": plan.identity["identity_sha256"],
        "plan_sha256": plan.plan["plan_sha256"],
        "completed_steps": int(plan.config["steps"]),
        "cursor": int(plan.config["steps"]),
        "tokens_seen": 640,
        "causal_targets_seen": 635,
        "network_access_performed": False,
        "scientific_claim_authorized": False,
        "evidence_scope": "bounded training/checkpoint/resume engineering only",
    }
    for key, expected in expected_core.items():
        if manifest.get(key) != expected:
            raise TrainingSmokeError(f"final training manifest {key} mismatch")
    if manifest.get("state_semantic_hashes") != state_semantic_hashes(state):
        raise TrainingSmokeError("final manifest state hashes mismatch")
    if manifest.get("losses") != list(state.losses):
        raise TrainingSmokeError("final manifest loss sequence mismatch")
    base_identity = manifest.get("base_identity_sha256")
    if not isinstance(base_identity, str) or len(base_identity) != 64:
        raise TrainingSmokeError("final manifest base identity is invalid")
    adapter = manifest.get("adapter_artifact")
    if (
        not isinstance(adapter, Mapping)
        or set(adapter)
        != {"path", "size_bytes", "file_sha256", "semantic_sha256"}
        or adapter.get("path") != "artifacts/adapter.safetensors"
        or not isinstance(adapter.get("size_bytes"), int)
        or isinstance(adapter.get("size_bytes"), bool)
        or adapter.get("size_bytes") < 1
        or not isinstance(adapter.get("file_sha256"), str)
        or len(adapter.get("file_sha256")) != 64
        or not isinstance(adapter.get("semantic_sha256"), str)
        or len(adapter.get("semantic_sha256")) != 64
    ):
        raise TrainingSmokeError("final adapter reference is invalid")
    adapter_path = root / "artifacts" / "adapter.safetensors"
    if not adapter_path.is_file() or adapter_path.stat().st_size != adapter.get("size_bytes") or sha256_file(adapter_path) != adapter.get("file_sha256"):
        raise TrainingSmokeError("final adapter physical integrity mismatch")
    decoded_adapter = (adapter_deserialize or _safetensors_deserialize)(
        adapter_path.read_bytes()
    )
    if sorted(decoded_adapter) != sorted(state.adapter_state):
        raise TrainingSmokeError("final adapter key set differs from captured state")
    adapter_semantic = semantic_state_sha256(decoded_adapter)
    if adapter_semantic != semantic_state_sha256(state.adapter_state):
        raise TrainingSmokeError("final adapter bytes differ from captured adapter state")
    if adapter.get("semantic_sha256") != adapter_semantic:
        raise TrainingSmokeError("final adapter semantic hash mismatch")
    runtime_report = read_json(root / "artifacts" / "runtime-report.json")
    if not isinstance(runtime_report, Mapping):
        raise TrainingSmokeError("runtime report root must be an object")
    if set(runtime_report) != {
        "schema_version",
        "run_id",
        "condition",
        "steps",
        "attempts",
        "final_state_reference_sha256",
        "network_access_performed",
        "runtime_report_sha256",
    } or runtime_report.get("schema_version") != 1:
        raise TrainingSmokeError("runtime report has invalid fields or schema")
    if (
        runtime_report.get("run_id") != store.run_id
        or runtime_report.get("network_access_performed") is not False
    ):
        raise TrainingSmokeError("runtime report identity or network policy mismatch")
    runtime_sha = runtime_report.get("runtime_report_sha256")
    if runtime_sha != canonical_sha256(
        {
            key: runtime_report[key]
            for key in runtime_report
            if key != "runtime_report_sha256"
        }
    ):
        raise TrainingSmokeError("runtime report hash mismatch")
    condition = runtime_report.get("condition")
    if condition not in {"control", "resumed"}:
        raise TrainingSmokeError("runtime report condition is invalid")
    if expected_condition is not None and condition != expected_condition:
        raise TrainingSmokeError(
            f"training condition mismatch: expected {expected_condition!r}, "
            f"observed {condition!r}"
        )
    if root.parent.name != condition:
        raise TrainingSmokeError("run path is not bound to its recorded condition")
    runtime_steps = _load_runtime_steps(
        root, store.run_id, expected_condition=condition
    )
    attempts = _load_attempt_reports(
        root, store.run_id, expected_condition=condition
    )
    if runtime_report.get("steps") != runtime_steps:
        raise TrainingSmokeError("runtime report step aggregation mismatch")
    if runtime_report.get("attempts") != attempts:
        raise TrainingSmokeError("runtime report attempt aggregation mismatch")
    if [step.get("loss") for step in runtime_steps] != list(state.losses):
        raise TrainingSmokeError("runtime-step losses differ from final state")
    final_reference = read_json(root / "artifacts" / "final-state-reference.json")
    if runtime_report.get("final_state_reference_sha256") != final_reference.get(
        "reference_sha256"
    ):
        raise TrainingSmokeError("runtime report final-state binding mismatch")
    events = read_event_log(store.events_path, expected_run_id=store.run_id)
    checkpoint_pointer = read_json(root / "checkpoint.json")
    progress_at_checkpoint = [
        event for event in events.events
        if event["event_type"] == "progress"
        and event["data"].get("completed_step") == int(plan.config["checkpoint_after_step"])
    ]
    if len(progress_at_checkpoint) != 1 or progress_at_checkpoint[0]["data"].get(
        "checkpoint_sha256"
    ) != checkpoint_pointer.get("checkpoint_sha256"):
        raise TrainingSmokeError("final checkpoint is not bound to the progress event")
    if condition == "resumed":
        fail_events = [event for event in events.events if event["event_type"] == "fail"]
        if len(fail_events) != 1 or fail_events[0]["data"].get(
            "checkpoint_sha256"
        ) != checkpoint_pointer.get("checkpoint_sha256"):
            raise TrainingSmokeError("resumed checkpoint is not bound to its failure event")
    event_types = [event["event_type"] for event in events.events]
    if condition == "control":
        expected_events = ["create", "freeze", "start"] + ["progress"] * 5
        expected_attempt_statuses = ["complete"]
        expected_attempt_steps = [5]
    else:
        expected_events = (
            ["create", "freeze", "start"]
            + ["progress"] * 3
            + ["fail", "resume"]
            + ["progress"] * 2
        )
        expected_attempt_statuses = ["interrupted", "complete"]
        expected_attempt_steps = [3, 5]
    if require_complete:
        expected_events.append("complete")
    if event_types != expected_events:
        raise TrainingSmokeError("training event history does not match its condition")
    start_event = next(
        event for event in events.events if event["event_type"] == "start"
    )
    if start_event["data"].get("condition") != condition:
        raise TrainingSmokeError("start event condition mismatch")
    if [attempt.get("status") for attempt in attempts] != expected_attempt_statuses:
        raise TrainingSmokeError("training attempt history does not match its condition")
    if [attempt.get("completed_steps") for attempt in attempts] != expected_attempt_steps:
        raise TrainingSmokeError("training attempt step counts do not match its condition")
    cumulative_elapsed = sum(
        float(attempt["elapsed_seconds"]) for attempt in attempts
    )
    if cumulative_elapsed > float(
        plan.config["resource_limits"]["maximum_condition_wall_seconds"]
    ):
        raise TrainingSmokeError("training condition exceeded its cumulative wall-time limit")
    progress_events = [
        event for event in events.events if event["event_type"] == "progress"
    ]
    sequence_length = int(plan.config["sequence_length"])
    checkpoint_step = int(plan.config["checkpoint_after_step"])
    for expected_step, event in enumerate(progress_events, start=1):
        data = event["data"]
        if (
            data.get("completed_step") != expected_step
            or data.get("cursor") != expected_step
            or data.get("tokens_seen") != expected_step * sequence_length
        ):
            raise TrainingSmokeError("training progress counters are inconsistent")
        expected_checkpoint = (
            checkpoint_pointer.get("checkpoint_sha256")
            if expected_step == checkpoint_step
            else None
        )
        if data.get("checkpoint_sha256") != expected_checkpoint:
            raise TrainingSmokeError("training progress checkpoint binding is inconsistent")
    if condition == "resumed":
        fail_event = next(
            event for event in events.events if event["event_type"] == "fail"
        )
        resume_event = next(
            event for event in events.events if event["event_type"] == "resume"
        )
        if (
            fail_event["data"].get("failure_kind") != "planned-interruption"
            or fail_event["data"].get("completed_steps") != checkpoint_step
            or resume_event["data"].get("reason") != "explicit-resume"
            or resume_event["data"].get("checkpoint_sha256")
            != checkpoint_pointer.get("checkpoint_sha256")
            or fail_event["data"].get("attempt_report")
            != _attempt_event_reference(attempts[0])
        ):
            raise TrainingSmokeError("resumed event history is not the planned interruption")
    complete_events = [event for event in events.events if event["event_type"] == "complete"]
    if require_complete:
        if len(complete_events) != 1:
            raise TrainingSmokeError("training run must contain exactly one complete event")
        complete_data = complete_events[0]["data"]
        if complete_data.get("final_manifest_sha256") != observed_hash:
            raise TrainingSmokeError("complete event final-manifest binding mismatch")
        if complete_data.get("runtime_report_sha256") != runtime_sha:
            raise TrainingSmokeError("complete event runtime-report binding mismatch")
        if complete_data.get("completed_steps") != int(plan.config["steps"]):
            raise TrainingSmokeError("complete event step count mismatch")
        if complete_data.get("attempt_report") != _attempt_event_reference(
            attempts[-1]
        ):
            raise TrainingSmokeError("complete event attempt-report binding mismatch")
    elif complete_events:
        raise TrainingSmokeError("pre-completion verification found a complete event")
    return {
        "status": "verified",
        "run_id": store.run_id,
        "completed_steps": state.completed_steps,
        "condition": condition,
        "final_manifest_sha256": observed_hash,
        "state_semantic_hashes": state_semantic_hashes(state),
    }


def compare_training_runs(
    plan: TrainingPlan,
    control_root: str | Path,
    resumed_root: str | Path,
    *,
    deserialize: StateDeserializer | None = None,
    adapter_deserialize: AdapterDeserializer | None = None,
) -> dict[str, Any]:
    control_path = Path(control_root).resolve(strict=True)
    resumed_path = Path(resumed_root).resolve(strict=True)
    if control_path == resumed_path:
        raise TrainingSmokeError("control and resumed run roots must be distinct")
    control_verification = verify_training_run(
        plan,
        control_root,
        deserialize=deserialize,
        adapter_deserialize=adapter_deserialize,
        expected_condition="control",
    )
    resumed_verification = verify_training_run(
        plan,
        resumed_root,
        deserialize=deserialize,
        adapter_deserialize=adapter_deserialize,
        expected_condition="resumed",
    )
    control_manifest = Path(control_root, "artifacts", "final-manifest.json").read_bytes()
    resumed_manifest = Path(resumed_root, "artifacts", "final-manifest.json").read_bytes()
    if control_manifest != resumed_manifest:
        raise TrainingSmokeError("resumed final manifest differs from uninterrupted control")
    return {
        "status": "equal",
        "run_id": plan.identity["run_id"],
        "final_manifest_sha256": control_verification["final_manifest_sha256"],
        "state_semantic_hashes": control_verification["state_semantic_hashes"],
        "control_verified": control_verification["status"] == "verified",
        "resumed_verified": resumed_verification["status"] == "verified",
    }


def _write_runtime_step(
    run_root: Path,
    *,
    run_id: str,
    condition: str,
    step: int,
    loss: float,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    relative = Path("artifacts") / "runtime-steps" / f"step-{step:04d}.json"
    path = run_root / relative
    if path.exists():
        raise TrainingSmokeError(f"immutable runtime step already exists: {path}")
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "condition": condition,
        "step": step,
        "loss": loss,
        "metrics": dict(metrics),
    }
    artifact["runtime_step_sha256"] = canonical_sha256(artifact)
    atomic_write_json(path, artifact)
    return {
        "path": relative.as_posix(),
        "file_sha256": sha256_file(path),
        "runtime_step_sha256": artifact["runtime_step_sha256"],
    }


def _load_runtime_steps(
    run_root: Path,
    run_id: str,
    *,
    expected_condition: str | None = None,
) -> list[dict[str, Any]]:
    state = read_event_log(run_root / "events.jsonl", expected_run_id=run_id)
    artifacts: list[dict[str, Any]] = []
    for expected_step, event in enumerate(
        (item for item in state.events if item["event_type"] == "progress"),
        start=1,
    ):
        data = event["data"]
        reference = data.get("runtime_step")
        if not isinstance(reference, Mapping) or set(reference) != {
            "path", "file_sha256", "runtime_step_sha256"
        }:
            raise TrainingSmokeError("progress event lacks a valid runtime-step reference")
        try:
            relative = portable_relative_path(
                reference["path"], label="runtime step path", suffix=".json"
            )
        except PortablePathError as error:
            raise TrainingSmokeError(str(error)) from error
        path = (run_root / relative).resolve(strict=False)
        try:
            path.relative_to(run_root.resolve(strict=True))
        except (OSError, ValueError) as error:
            raise TrainingSmokeError("runtime step escapes run root") from error
        expected_relative = (
            Path("artifacts") / "runtime-steps" / f"step-{expected_step:04d}.json"
        )
        if relative != expected_relative:
            raise TrainingSmokeError("runtime step path is not the exact frozen path")
        if not path.is_file() or sha256_file(path) != reference["file_sha256"]:
            raise TrainingSmokeError("runtime step file integrity mismatch")
        artifact = read_json(path)
        if not isinstance(artifact, Mapping):
            raise TrainingSmokeError("runtime step root must be an object")
        if set(artifact) != {
            "schema_version",
            "run_id",
            "condition",
            "step",
            "loss",
            "metrics",
            "runtime_step_sha256",
        } or artifact.get("schema_version") != 1:
            raise TrainingSmokeError("runtime step has invalid fields or schema")
        observed = artifact.get("runtime_step_sha256")
        if observed != canonical_sha256(
            {key: artifact[key] for key in artifact if key != "runtime_step_sha256"}
        ) or observed != reference["runtime_step_sha256"]:
            raise TrainingSmokeError("runtime step semantic hash mismatch")
        if artifact.get("run_id") != run_id or artifact.get("step") != expected_step:
            raise TrainingSmokeError("runtime step sequence or identity mismatch")
        if expected_condition is not None and artifact.get("condition") != expected_condition:
            raise TrainingSmokeError("runtime step condition mismatch")
        if not isinstance(artifact.get("metrics"), Mapping):
            raise TrainingSmokeError("runtime step metrics must be an object")
        loss = artifact.get("loss")
        if not isinstance(loss, (int, float)) or not math.isfinite(float(loss)):
            raise TrainingSmokeError("runtime step loss is invalid")
        artifacts.append(dict(artifact))
    return artifacts


def _write_attempt_report(
    run_root: Path,
    *,
    run_id: str,
    condition: str,
    attempt: int,
    status: str,
    completed_steps: int,
    elapsed_seconds: float,
    backend_summary: Mapping[str, Any],
) -> dict[str, Any]:
    relative = Path("artifacts") / "attempts" / f"attempt-{attempt:04d}.json"
    path = _safe_attempt_path(run_root, attempt, require_file=False)
    if os.path.lexists(path):
        raise TrainingSmokeError(f"immutable attempt report already exists: {path}")
    if not isinstance(elapsed_seconds, (int, float)) or not math.isfinite(
        float(elapsed_seconds)
    ) or elapsed_seconds < 0:
        raise TrainingSmokeError("attempt elapsed time must be finite and nonnegative")
    report: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "condition": condition,
        "attempt": attempt,
        "status": status,
        "completed_steps": completed_steps,
        "elapsed_seconds": float(elapsed_seconds),
        "backend": dict(backend_summary),
    }
    report["attempt_report_sha256"] = canonical_sha256(report)
    atomic_write_json(path, report)
    return {
        "path": relative.as_posix(),
        "file_sha256": sha256_file(path),
        "attempt_report_sha256": report["attempt_report_sha256"],
    }


def _load_attempt_reports(
    run_root: Path,
    run_id: str,
    *,
    expected_condition: str | None = None,
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    attempts_directory = _safe_attempt_directory(run_root)
    if not os.path.lexists(attempts_directory):
        return reports
    entries = sorted(attempts_directory.iterdir(), key=lambda item: item.name)
    for expected_attempt, entry in enumerate(entries, start=1):
        expected_name = f"attempt-{expected_attempt:04d}.json"
        if entry.name != expected_name:
            raise TrainingSmokeError(
                "attempt report directory has an unexpected or nonsequential entry"
            )
        path = _safe_attempt_path(
            run_root, expected_attempt, require_file=True
        )
        report = read_json(path)
        if not isinstance(report, Mapping):
            raise TrainingSmokeError("attempt report root must be an object")
        if set(report) != {
            "schema_version",
            "run_id",
            "condition",
            "attempt",
            "status",
            "completed_steps",
            "elapsed_seconds",
            "backend",
            "attempt_report_sha256",
        } or report.get("schema_version") != 1:
            raise TrainingSmokeError("attempt report has invalid fields or schema")
        observed = report.get("attempt_report_sha256")
        if observed != canonical_sha256(
            {key: report[key] for key in report if key != "attempt_report_sha256"}
        ):
            raise TrainingSmokeError("attempt report semantic hash mismatch")
        if report.get("run_id") != run_id or report.get("attempt") != expected_attempt:
            raise TrainingSmokeError("attempt report sequence or identity mismatch")
        if expected_condition is not None and report.get("condition") != expected_condition:
            raise TrainingSmokeError("attempt report condition mismatch")
        completed_steps = report.get("completed_steps")
        if (
            not isinstance(completed_steps, int)
            or isinstance(completed_steps, bool)
            or completed_steps < 0
        ):
            raise TrainingSmokeError("attempt report completed steps are invalid")
        elapsed = report.get("elapsed_seconds")
        if not isinstance(elapsed, (int, float)) or not math.isfinite(
            float(elapsed)
        ) or elapsed < 0:
            raise TrainingSmokeError("attempt report elapsed time is invalid")
        reports.append(
            {
                "path": path.relative_to(run_root).as_posix(),
                "file_sha256": sha256_file(path),
                "attempt_report_sha256": observed,
                "status": report.get("status"),
                "completed_steps": completed_steps,
                "elapsed_seconds": float(elapsed),
            }
        )
    return reports


def _is_link_or_reparse_point(path: Path) -> bool:
    """Return whether an existing path redirects filesystem traversal.

    ``Path.is_symlink`` does not identify Windows directory junctions on
    Python 3.11.  The reparse-point attribute closes that platform-specific
    escape without requiring optional Win32 bindings.
    """

    try:
        information = os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise TrainingSmokeError(
            f"cannot inspect training artifact path: {path}"
        ) from error
    return stat.S_ISLNK(information.st_mode) or bool(
        getattr(information, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
    )


def _safe_attempt_directory(run_root: Path) -> Path:
    """Validate the immutable attempt-report directory without following links."""

    root = Path(run_root)
    if not root.is_dir():
        raise TrainingSmokeError("training run root is missing or not a directory")
    attempts = root / "artifacts" / "attempts"
    for current in (root, root / "artifacts", attempts):
        if os.path.lexists(current) and _is_link_or_reparse_point(current):
            raise TrainingSmokeError(
                "training attempt path must not contain links or reparse points"
            )
    if os.path.lexists(attempts) and not attempts.is_dir():
        raise TrainingSmokeError("training attempt path is not a directory")
    try:
        attempts.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise TrainingSmokeError("training attempt path escapes the run root") from error
    return attempts


def _safe_attempt_path(
    run_root: Path,
    attempt: int,
    *,
    require_file: bool,
) -> Path:
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise TrainingSmokeError("training attempt number must be a positive integer")
    attempts = _safe_attempt_directory(run_root)
    path = attempts / f"attempt-{attempt:04d}.json"
    if os.path.lexists(path) and _is_link_or_reparse_point(path):
        raise TrainingSmokeError(
            "training attempt path must not contain links or reparse points"
        )
    try:
        path.resolve(strict=require_file).relative_to(Path(run_root).resolve(strict=True))
    except (OSError, ValueError) as error:
        raise TrainingSmokeError("training attempt path escapes the run root") from error
    if require_file and not path.is_file():
        raise TrainingSmokeError("training attempt report is missing or not a file")
    return path


def _attempt_event_reference(attempt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": attempt["path"],
        "file_sha256": attempt["file_sha256"],
        "attempt_report_sha256": attempt["attempt_report_sha256"],
    }


def _require_final_outputs_absent(run_root: Path, attempt_number: int) -> None:
    relative_paths = (
        "artifacts/final-state.pt",
        "artifacts/final-state-reference.json",
        "artifacts/adapter.safetensors",
        "artifacts/final-manifest.json",
        "artifacts/runtime-report.json",
        f"artifacts/attempts/attempt-{attempt_number:04d}.json",
    )
    _safe_attempt_path(run_root, attempt_number, require_file=False)
    existing = [
        relative
        for relative in relative_paths
        if os.path.lexists(run_root / relative)
    ]
    if existing:
        raise TrainingSmokeError(
            "immutable final output already exists: " + ", ".join(existing)
        )


def _remove_uncommitted_final_outputs(
    run_root: Path,
    attempt_number: int,
) -> None:
    """Roll back files that were published without a terminal commit event.

    The exact targets were all proven absent immediately before finalization.
    Checkpoints, runtime steps, and event history remain as failure evidence.
    """

    attempt_path = _safe_attempt_path(
        run_root, attempt_number, require_file=False
    )
    paths = (
        run_root / "artifacts" / "runtime-report.json",
        attempt_path,
        run_root / "artifacts" / "final-manifest.json",
        run_root / "artifacts" / "adapter.safetensors",
        run_root / "artifacts" / "final-state-reference.json",
        run_root / "artifacts" / "final-state.pt",
    )
    existing = [path for path in paths if os.path.lexists(path)]
    for path in existing:
        if _is_link_or_reparse_point(path) or not path.is_file():
            raise TrainingSmokeError(
                "cannot roll back an unsafe uncommitted final output"
            )
    for path in existing:
        path.unlink()


def run_training_condition(
    plan: TrainingPlan,
    output_root: str | Path,
    *,
    condition: str,
    backend_factory: BackendFactory,
    resume: bool = False,
    interrupt_after: int | None = None,
    serialize: StateSerializer | None = None,
    deserialize: StateDeserializer | None = None,
    adapter_deserialize: AdapterDeserializer | None = None,
    attempt_context: Mapping[str, Any] | None = None,
    event_clock: Callable[[], str | None] | None = None,
    job_lock_path: str | Path | None = None,
) -> TrainingRunResult:
    if condition not in {"control", "resumed"}:
        raise TrainingSmokeError("condition must be 'control' or 'resumed'")
    checkpoint_step = int(plan.config["checkpoint_after_step"])
    if condition == "control" and (resume or interrupt_after is not None):
        raise TrainingSmokeError("the uninterrupted control accepts no resume or interruption")
    if condition == "resumed":
        if resume and interrupt_after is not None:
            raise TrainingSmokeError("resume and planned interruption are mutually exclusive")
        if not resume and interrupt_after != checkpoint_step:
            raise TrainingSmokeError(
                "a fresh resumed condition requires the planned step-three interruption"
            )
    clock = event_clock or (lambda: None)
    output = Path(output_root)
    run_root = output / condition / plan.identity["run_id"]
    if resume and not (run_root / "identity.json").is_file():
        raise TrainingSmokeError("cannot resume before the planned checkpoint exists")
    output.mkdir(parents=True, exist_ok=True)
    minimum_output = int(plan.config["resource_limits"]["minimum_output_free_bytes"])
    if shutil.disk_usage(output).free < minimum_output:
        raise TrainingSmokeError("insufficient output storage for training smoke")
    condition_root = output / condition
    condition_root.mkdir(parents=True, exist_ok=True)
    lock = RunLock(
        Path(job_lock_path)
        if job_lock_path is not None
        else output / ".locks" / "training-job.lock",
        run_id=plan.identity["run_id"],
    )
    backend: TrainingBackend | None = None
    with lock:
        existing_run = (run_root / "identity.json").exists()
        if existing_run:
            store = RunStore.load(run_root)
            if store.identity != plan.identity:
                raise TrainingSmokeError("existing training run identity differs from plan")
        else:
            store = RunStore(run_root, plan.identity)
            store.initialize(recorded_at=clock())
        registry_path = condition_root / "registry.jsonl"
        if existing_run:
            registry = read_registry(registry_path)
            matches = [
                entry
                for entry in registry.entries
                if entry.get("run_id") == store.run_id
                and entry.get("identity_sha256")
                == plan.identity["identity_sha256"]
            ]
            if len(matches) != 1:
                raise TrainingSmokeError(
                    "existing run lacks its immutable condition registry entry"
                )
        else:
            with RunLock(
                condition_root / ".locks" / "registry.lock", run_id=store.run_id
            ):
                ensure_registry_entry(
                    registry_path, plan.identity, created_at=clock()
                )

        state_name = store.state
        if state_name == "complete":
            verify_training_run(
                plan,
                run_root,
                deserialize=deserialize,
                adapter_deserialize=adapter_deserialize,
                expected_condition=condition,
            )
            manifest = read_json(run_root / "artifacts" / "final-manifest.json")
            return TrainingRunResult(store.run_id, run_root, "complete", int(plan.config["steps"]), dict(manifest))
        if state_name == "running":
            raise TrainingSmokeError(
                "an incomplete running attempt cannot be recovered into this frozen gate"
            )
        if state_name == "failed" and (condition != "resumed" or not resume):
            raise TrainingSmokeError(
                "only the planned failed resumed condition accepts explicit resume"
            )
        if state_name in {"design", "frozen"} and resume:
            raise TrainingSmokeError("cannot resume before the planned checkpoint exists")
        resume_state: TrainingCheckpointState | None = None
        if state_name == "failed":
            resume_state = load_training_checkpoint(
                run_root,
                plan.identity,
                expected_step=checkpoint_step,
                deserialize=deserialize,
            )
            _validate_state_position(
                resume_state,
                plan,
                expected_steps=checkpoint_step,
            )
            event_state = read_event_log(store.events_path, expected_run_id=store.run_id)
            progress_steps = [
                event["data"].get("completed_step")
                for event in event_state.events
                if event["event_type"] == "progress"
            ]
            if progress_steps != list(range(1, checkpoint_step + 1)):
                raise TrainingSmokeError("training progress events are not an exact prefix")
            _load_runtime_steps(
                run_root, store.run_id, expected_condition=condition
            )
            pointer = read_json(run_root / "checkpoint.json")
            checkpoint_sha = pointer["checkpoint_sha256"]
            step_three_events = [
                event for event in event_state.events
                if event["event_type"] == "progress"
                and event["data"].get("completed_step") == checkpoint_step
            ]
            if len(step_three_events) != 1 or step_three_events[0]["data"].get(
                "checkpoint_sha256"
            ) != checkpoint_sha:
                raise TrainingSmokeError("checkpoint is not bound to the step-three event")
            if state_name == "failed":
                fail_events = [
                    event for event in event_state.events if event["event_type"] == "fail"
                ]
                interrupted_attempts = _load_attempt_reports(
                    run_root,
                    store.run_id,
                    expected_condition=condition,
                )
                if len(fail_events) != 1 or fail_events[0]["data"].get(
                    "checkpoint_sha256"
                ) != checkpoint_sha:
                    raise TrainingSmokeError("checkpoint is not bound to the failure event")
                if (
                    len(interrupted_attempts) != 1
                    or interrupted_attempts[0].get("status") != "interrupted"
                    or interrupted_attempts[0].get("completed_steps")
                    != checkpoint_step
                    or fail_events[0]["data"].get("attempt_report")
                    != _attempt_event_reference(interrupted_attempts[0])
                ):
                    raise TrainingSmokeError(
                        "planned failure is not bound to its interruption attempt"
                    )
                _require_final_outputs_absent(
                    run_root, len(interrupted_attempts) + 1
                )
            store.transition(
                "resume",
                data={"reason": "explicit-resume", "checkpoint_sha256": checkpoint_sha},
                recorded_at=clock(),
            )
        elif state_name == "design":
            _require_final_outputs_absent(run_root, 1)
            store.transition("freeze", data={"plan_sha256": plan.plan["plan_sha256"]}, recorded_at=clock())
            store.transition("start", data={"condition": condition}, recorded_at=clock())
        elif state_name == "frozen":
            _require_final_outputs_absent(run_root, 1)
            store.transition("start", data={"condition": condition}, recorded_at=clock())
        else:
            raise TrainingSmokeError(f"unsupported training run state: {state_name}")

        completed = resume_state.completed_steps if resume_state else 0
        cursor = resume_state.cursor if resume_state else 0
        tokens_seen = resume_state.tokens_seen if resume_state else 0
        losses = list(resume_state.losses) if resume_state else []
        prior_attempts = _load_attempt_reports(
            run_root, store.run_id, expected_condition=condition
        )
        attempt_number = len(prior_attempts) + 1
        prior_elapsed_seconds = sum(
            float(attempt["elapsed_seconds"]) for attempt in prior_attempts
        )
        maximum_checkpoint = int(plan.config["resource_limits"]["maximum_checkpoint_bytes"])
        maximum_condition_seconds = float(
            plan.config["resource_limits"]["maximum_condition_wall_seconds"]
        )
        condition_started = time.perf_counter()

        def attempt_elapsed_seconds() -> float:
            return time.perf_counter() - condition_started

        def require_wall_headroom() -> None:
            observed = prior_elapsed_seconds + attempt_elapsed_seconds()
            if observed > maximum_condition_seconds:
                raise TrainingSmokeError(
                    "training condition exceeded its cumulative wall-time limit"
                )

        captured_backend_summary: dict[str, Any] | None = None
        final_publication_started = False
        try:
            _require_final_outputs_absent(run_root, attempt_number)
            require_wall_headroom()
            backend = backend_factory(plan, resume_state)
            while completed < int(plan.config["steps"]):
                require_wall_headroom()
                step = completed + 1
                if cursor != completed:
                    raise TrainingSmokeError("training cursor does not match completed steps")
                result = backend.run_step(plan.token_blocks[cursor], step)
                if not isinstance(result.loss, (int, float)) or not math.isfinite(float(result.loss)):
                    raise TrainingSmokeError("training step produced a non-finite loss")
                losses.append(float(result.loss))
                completed = step
                cursor += 1
                tokens_seen += len(plan.token_blocks[cursor - 1])
                if set(result.runtime_metrics) & {"step", "loss"}:
                    raise TrainingSmokeError("runtime metrics may not replace step or loss")
                step_metrics = dict(result.runtime_metrics)
                checkpoint_sha: str | None = None
                if completed == checkpoint_step:
                    checkpoint_state = backend.capture_state(
                        completed_steps=completed,
                        cursor=cursor,
                        tokens_seen=tokens_seen,
                        losses=losses,
                    )
                    _validate_state_position(
                        checkpoint_state,
                        plan,
                        expected_steps=checkpoint_step,
                    )
                    if checkpoint_state.losses != tuple(losses):
                        raise TrainingSmokeError(
                            "checkpoint losses differ from runner-owned losses"
                        )
                    checkpoint_start = time.perf_counter()
                    checkpoint = save_training_checkpoint(
                        run_root,
                        checkpoint_state,
                        plan.identity,
                        serialize=serialize,
                        maximum_bytes=maximum_checkpoint,
                    )
                    roundtrip = load_training_checkpoint(
                        run_root,
                        plan.identity,
                        expected_step=checkpoint_step,
                        expected_adapter_keys=sorted(checkpoint_state.adapter_state),
                        deserialize=deserialize,
                    )
                    if state_semantic_hashes(roundtrip) != state_semantic_hashes(
                        checkpoint_state
                    ):
                        raise TrainingSmokeError(
                            "checkpoint round-trip changed semantic state"
                        )
                    step_metrics["checkpoint_seconds"] = (
                        time.perf_counter() - checkpoint_start
                    )
                    step_metrics["checkpoint_size_bytes"] = checkpoint.pointer[
                        "state_size_bytes"
                    ]
                    checkpoint_sha = checkpoint.pointer["checkpoint_sha256"]
                runtime_step = _write_runtime_step(
                    run_root,
                    run_id=store.run_id,
                    condition=condition,
                    step=step,
                    loss=float(result.loss),
                    metrics=step_metrics,
                )
                store.transition(
                    "progress",
                    data={
                        "completed_step": completed,
                        "cursor": cursor,
                        "tokens_seen": tokens_seen,
                        "checkpoint_sha256": checkpoint_sha,
                        "runtime_step": runtime_step,
                    },
                    recorded_at=clock(),
                )
                require_wall_headroom()
                if interrupt_after == completed:
                    attempt_report = _write_attempt_report(
                        run_root,
                        run_id=store.run_id,
                        condition=condition,
                        attempt=attempt_number,
                        status="interrupted",
                        completed_steps=completed,
                        elapsed_seconds=attempt_elapsed_seconds(),
                        backend_summary={
                            "attempt_context": dict(attempt_context or {}),
                            "runtime": dict(getattr(backend, "runtime_summary", {})),
                        },
                    )
                    store.transition(
                        "fail",
                        data={
                            "failure_kind": "planned-interruption",
                            "completed_steps": completed,
                            "checkpoint_sha256": checkpoint_sha,
                            "attempt_report": attempt_report,
                        },
                        recorded_at=clock(),
                    )
                    return TrainingRunResult(store.run_id, run_root, "interrupted", completed, None)

            final_state = backend.capture_state(
                completed_steps=completed,
                cursor=cursor,
                tokens_seen=tokens_seen,
                losses=losses,
            )
            _validate_state_position(
                final_state,
                plan,
                expected_steps=int(plan.config["steps"]),
            )
            if final_state.losses != tuple(losses):
                raise TrainingSmokeError(
                    "final-state losses differ from runner-owned losses"
                )
            final_state_bytes = (serialize or _torch_serialize)(
                _state_payload(final_state)
            )
            if len(final_state_bytes) > maximum_checkpoint:
                raise TrainingSmokeError(
                    "final training state exceeds checkpoint size limit"
                )
            adapter_bytes = backend.serialize_adapter(final_state.adapter_state)
            if not isinstance(adapter_bytes, bytes):
                raise TrainingSmokeError("serialized adapter must be bytes")
            if len(adapter_bytes) > maximum_checkpoint:
                raise TrainingSmokeError("final adapter exceeds checkpoint size limit")
            decoded_adapter = (adapter_deserialize or _safetensors_deserialize)(
                adapter_bytes
            )
            adapter_semantic = semantic_state_sha256(decoded_adapter)
            if sorted(decoded_adapter) != sorted(final_state.adapter_state) or (
                adapter_semantic != semantic_state_sha256(final_state.adapter_state)
            ):
                raise TrainingSmokeError(
                    "serialized adapter does not round-trip to captured adapter state"
                )
            base_identity_sha256 = backend.base_identity_sha256
            backend_summary = {
                "attempt_context": dict(attempt_context or {}),
                "runtime": dict(getattr(backend, "runtime_summary", {})),
            }
            captured_backend_summary = backend_summary
            require_wall_headroom()
            backend.close()
            backend = None
            require_wall_headroom()
            _require_final_outputs_absent(run_root, attempt_number)
            final_publication_started = True
            reference = _save_final_state(
                run_root,
                final_state,
                plan.identity,
                serialize=lambda _payload: final_state_bytes,
                maximum_bytes=maximum_checkpoint,
            )
            adapter_path = run_root / "artifacts" / "adapter.safetensors"
            if adapter_path.exists():
                raise TrainingSmokeError("immutable final adapter already exists")
            atomic_write_bytes(adapter_path, adapter_bytes)
            manifest = _final_manifest(
                plan,
                final_state,
                base_identity_sha256=base_identity_sha256,
                adapter_file_sha256=hashlib.sha256(adapter_bytes).hexdigest(),
                adapter_size_bytes=len(adapter_bytes),
                adapter_semantic_sha256=adapter_semantic,
            )
            atomic_write_json(run_root / "artifacts" / "final-manifest.json", manifest)
            attempt_report = _write_attempt_report(
                run_root,
                run_id=store.run_id,
                condition=condition,
                attempt=attempt_number,
                status="complete",
                completed_steps=completed,
                elapsed_seconds=attempt_elapsed_seconds(),
                backend_summary=backend_summary,
            )
            all_runtime_steps = _load_runtime_steps(
                run_root, store.run_id, expected_condition=condition
            )
            attempts = _load_attempt_reports(
                run_root, store.run_id, expected_condition=condition
            )
            runtime_report = {
                "schema_version": 1,
                "run_id": store.run_id,
                "condition": condition,
                "steps": all_runtime_steps,
                "attempts": attempts,
                "final_state_reference_sha256": reference["reference_sha256"],
                "network_access_performed": False,
            }
            runtime_report["runtime_report_sha256"] = canonical_sha256(runtime_report)
            atomic_write_json(run_root / "artifacts" / "runtime-report.json", runtime_report)
            verify_training_run(
                plan,
                run_root,
                deserialize=deserialize,
                adapter_deserialize=adapter_deserialize,
                require_complete=False,
                expected_condition=condition,
            )
            require_wall_headroom()
            store.transition(
                "complete",
                data={
                    "final_manifest_sha256": manifest["final_manifest_sha256"],
                    "runtime_report_sha256": runtime_report["runtime_report_sha256"],
                    "completed_steps": completed,
                    "attempt_report": attempt_report,
                },
                recorded_at=clock(),
            )
        except Exception as error:
            try:
                if store.state == "running":
                    if final_publication_started:
                        _remove_uncommitted_final_outputs(
                            run_root, attempt_number
                        )
                    attempt_report = None
                    attempt_path = (
                        run_root
                        / "artifacts"
                        / "attempts"
                        / f"attempt-{attempt_number:04d}.json"
                    )
                    if attempt_path.exists():
                        existing_attempt = read_json(attempt_path)
                        attempt_report = {
                            "path": attempt_path.relative_to(run_root).as_posix(),
                            "file_sha256": sha256_file(attempt_path),
                            "attempt_report_sha256": existing_attempt[
                                "attempt_report_sha256"
                            ],
                        }
                    elif backend is not None or captured_backend_summary is not None:
                        summary = captured_backend_summary or {
                            "attempt_context": dict(attempt_context or {}),
                            "runtime": dict(
                                getattr(backend, "runtime_summary", {})
                            ),
                        }
                        attempt_report = _write_attempt_report(
                            run_root,
                            run_id=store.run_id,
                            condition=condition,
                            attempt=attempt_number,
                            status="failed",
                            completed_steps=completed,
                            elapsed_seconds=attempt_elapsed_seconds(),
                            backend_summary=summary,
                        )
                    elif attempt_context:
                        attempt_report = _write_attempt_report(
                            run_root,
                            run_id=store.run_id,
                            condition=condition,
                            attempt=attempt_number,
                            status="failed-before-backend-ready",
                            completed_steps=completed,
                            elapsed_seconds=attempt_elapsed_seconds(),
                            backend_summary={"attempt_context": dict(attempt_context)},
                        )
                    store.transition(
                        "fail",
                        data={
                            "failure_kind": "training-error",
                            "failure_stage": "training-condition",
                            "error_type": type(error).__name__,
                            "error_message_sha256": hashlib.sha256(str(error).encode("utf-8")).hexdigest(),
                            "completed_steps": completed,
                            "tokens_seen": tokens_seen,
                            "network_access_performed": False,
                            "attempt_report": attempt_report,
                        },
                        recorded_at=clock(),
                    )
            except Exception:
                pass
            raise
        finally:
            if backend is not None:
                backend.close()

        verify_training_run(
            plan,
            run_root,
            deserialize=deserialize,
            adapter_deserialize=adapter_deserialize,
            expected_condition=condition,
        )
        return TrainingRunResult(store.run_id, run_root, "complete", completed, manifest)
