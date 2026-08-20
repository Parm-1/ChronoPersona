"""Manifest-gated Transformers adapters for tokenizer audit and scoring.

Optional model dependencies are imported only when an approved operation is
executed. This module never enables custom remote code or quantization.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import platform
import stat
import tempfile
import time
from typing import Any

from .artifact_policy import (
    assert_model_score_ready,
    assert_tokenizer_ready,
    assert_tokenizer_snapshot_ready,
    find_artifact,
)
from .model_manifest import validate_model_manifest
from .model_snapshot import verify_snapshot
from .attention_policy import (
    ATTENTION_IMPLEMENTATION,
    attention_policy_record,
    math_sdpa_context,
)
from .scoring import CandidateEvidence, ScoringIntegrityError
from .tokenization import PreparedContinuation, prepare_continuation
from .tokenizer_audit import resolve_prefix_token_ids


class TransformersProviderError(RuntimeError):
    """Raised when an approved Transformers operation cannot be completed."""


_ROOT = Path(__file__).resolve().parents[2]
_CANONICAL_MANIFEST = _ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json"


@dataclass(frozen=True)
class LoadedTokenizer:
    tokenizer: Any
    repository: str
    revision: str
    model_manifest_sha256: str
    snapshot_verification: Mapping[str, Any]
    tokenizer_validation: Mapping[str, Any]
    runtime_identity: Mapping[str, Any]


@dataclass(frozen=True)
class LoadedModel:
    tokenizer: Any
    model: Any
    repository: str
    revision: str
    device: str
    dtype: str
    vocabulary_size: int
    model_manifest_sha256: str
    snapshot_verification: Mapping[str, Any]
    tokenizer_validation: Mapping[str, Any]
    runtime_identity: Mapping[str, Any]
    model_validation: Mapping[str, Any]
    loading_info: Mapping[str, Any]
    load_seconds: float


def select_continuation_logprobs(
    actual_next_token_logprobs: Sequence[float],
    prepared: PreparedContinuation,
) -> tuple[float, ...]:
    """Select continuation positions from full-sequence next-token scores."""

    expected_all = len(prepared.full_token_ids) - 1
    if len(actual_next_token_logprobs) != expected_all:
        raise ScoringIntegrityError(
            "full next-token log-probability count does not match sequence"
        )
    start = prepared.first_prediction_index
    stop = prepared.final_prediction_index + 1
    selected = tuple(
        float(value) for value in actual_next_token_logprobs[start:stop]
    )
    if len(selected) != len(prepared.continuation_token_ids):
        raise ScoringIntegrityError(
            "selected continuation log-probability count is incorrect"
        )
    return selected


def _import_tokenizer() -> Any:
    try:
        from transformers import AutoTokenizer
    except ImportError as error:
        raise TransformersProviderError(
            "Tokenizer audit dependencies are missing; install "
            "`transformers` and `huggingface-hub`"
        ) from error
    return AutoTokenizer


def _import_model_stack() -> tuple[Any, Any, Any, Any, Any]:
    try:
        import torch
        import transformers
        from torch.nn.attention import SDPBackend, sdpa_kernel
        from transformers import AutoModelForCausalLM
    except ImportError as error:
        raise TransformersProviderError(
            "Transformers scoring dependencies are missing; install `.[models]`"
        ) from error
    return torch, transformers, AutoModelForCausalLM, sdpa_kernel, SDPBackend


def _artifact_identity(artifact: Mapping[str, Any]) -> tuple[str, str]:
    repository = artifact.get("repository")
    revision = artifact.get("revision")
    if not isinstance(repository, str) or not isinstance(revision, str):
        raise TransformersProviderError(
            "artifact repository and revision must be strings"
        )
    return repository, revision


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_file_bytes(path: Path) -> bytes:
    before = path.stat()
    with path.open("rb") as handle:
        opened_before = os.fstat(handle.fileno())
        payload = handle.read()
        opened_after = os.fstat(handle.fileno())
    after = path.stat()
    identities = {
        (
            int(info.st_dev),
            int(info.st_ino),
            int(info.st_size),
            int(info.st_mtime_ns),
            int(info.st_ctime_ns),
        )
        for info in (before, opened_before, opened_after, after)
    }
    if len(identities) != 1:
        raise TransformersProviderError(
            "canonical model manifest changed while it was being read"
        )
    return payload


def _canonical_artifact(
    artifact: Mapping[str, Any],
    manifest_path: str | Path,
    expected_manifest_sha256: str,
) -> tuple[Mapping[str, Any], str]:
    selected = Path(manifest_path)
    if selected.resolve(strict=True) != _CANONICAL_MANIFEST.resolve(strict=True):
        raise TransformersProviderError(
            "tokenizer execution requires the canonical model manifest"
        )
    payload = _stable_file_bytes(selected)
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != expected_manifest_sha256:
        raise TransformersProviderError(
            "canonical model manifest SHA-256 changed before tokenizer loading"
        )
    try:
        manifest = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TransformersProviderError(
            f"canonical model manifest is invalid: {error}"
        ) from error
    if not isinstance(manifest, Mapping):
        raise TransformersProviderError("canonical model manifest root must be an object")
    errors = validate_model_manifest(manifest)
    if errors:
        raise TransformersProviderError("; ".join(errors))
    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, str):
        raise TransformersProviderError("artifact id must be a string")
    canonical = find_artifact(manifest, artifact_id)
    if dict(canonical) != dict(artifact):
        raise TransformersProviderError(
            "artifact does not exactly match the canonical model manifest"
        )
    return canonical, observed_sha256


def _require_offline_environment() -> None:
    missing = [
        name
        for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        if os.environ.get(name) != "1"
    ]
    if missing:
        raise TransformersProviderError(
            "verified tokenizer loading requires offline environment flags: "
            + ", ".join(missing)
        )


def _loaded_tokenizer_validation(
    tokenizer: Any,
    *,
    expected: Mapping[str, Any],
    repository: str,
    revision: str,
    snapshot_path: Path,
) -> dict[str, Any]:
    runtime = expected.get("runtime_expectation")
    if not isinstance(runtime, Mapping):
        raise TransformersProviderError(
            "verified tokenizer runtime expectation is absent"
        )
    observed_class = tokenizer.__class__.__name__
    if observed_class != runtime.get("class"):
        raise TransformersProviderError(
            "loaded tokenizer class mismatch: "
            f"expected {runtime.get('class')!r}, observed {observed_class!r}"
        )
    if getattr(tokenizer, "is_fast", None) is not runtime.get("is_fast"):
        raise TransformersProviderError("loaded tokenizer fast-backend policy mismatch")
    observed_vocab = getattr(tokenizer, "vocab_size", None)
    if observed_vocab != runtime.get("vocab_size"):
        raise TransformersProviderError(
            "loaded tokenizer vocabulary size mismatch: "
            f"expected {runtime.get('vocab_size')}, observed {observed_vocab}"
        )
    try:
        observed_length = len(tokenizer)
    except (TypeError, ValueError) as error:
        raise TransformersProviderError(
            f"loaded tokenizer length is unavailable: {error}"
        ) from error
    if observed_length != runtime.get("tokenizer_length"):
        raise TransformersProviderError(
            "loaded tokenizer length mismatch: "
            f"expected {runtime.get('tokenizer_length')}, observed {observed_length}"
        )

    counter = getattr(tokenizer, "num_special_tokens_to_add", None)
    if not callable(counter):
        raise TransformersProviderError(
            "loaded tokenizer native special-token counter is unavailable"
        )
    native_special_count = counter(pair=False)
    if native_special_count != runtime.get("native_special_tokens_to_add"):
        raise TransformersProviderError(
            "loaded tokenizer native special-token count mismatch"
        )
    prefix_policy = runtime.get("native_prefix_policy")
    expected_special = runtime.get("special_tokens")
    expected_ids = runtime.get("special_token_ids")
    if not isinstance(expected_special, Mapping) or not isinstance(
        expected_ids, Mapping
    ):
        raise TransformersProviderError(
            "verified tokenizer runtime special-token expectation is absent"
        )
    probe = "ChronoPersona tokenizer prefix probe."
    without_special = tokenizer.encode(probe, add_special_tokens=False)
    with_special = tokenizer.encode(probe, add_special_tokens=True)
    if not (
        isinstance(without_special, list)
        and without_special
        and all(
            isinstance(token_id, int) and not isinstance(token_id, bool)
            for token_id in without_special
        )
        and isinstance(with_special, list)
        and all(
            isinstance(token_id, int) and not isinstance(token_id, bool)
            for token_id in with_special
        )
    ):
        raise TransformersProviderError(
            "loaded tokenizer native-prefix probe returned invalid token IDs"
        )
    if prefix_policy == "none" and with_special != without_special:
        raise TransformersProviderError(
            "loaded tokenizer native-prefix probe contradicts none policy"
        )
    if prefix_policy == "bos" and with_special != [
        expected_ids.get("bos_token_id"),
        *without_special,
    ]:
        raise TransformersProviderError(
            "loaded tokenizer native-prefix probe contradicts bos policy"
        )

    special_ids: dict[str, int | None] = {}
    special_texts: dict[str, str | None] = {}
    for token_name in ("bos_token", "eos_token", "pad_token", "unk_token"):
        expected_text = expected_special.get(token_name)
        expected_id = expected_ids.get(token_name + "_id")
        observed_text = getattr(tokenizer, token_name, None)
        observed_id = getattr(tokenizer, token_name + "_id", None)
        if observed_text != expected_text or observed_id != expected_id:
            raise TransformersProviderError(
                f"loaded tokenizer {token_name} identity mismatch: expected "
                f"{expected_text!r}/{expected_id!r}, observed "
                f"{observed_text!r}/{observed_id!r}"
            )
        if expected_text is not None:
            converted = tokenizer.convert_tokens_to_ids(expected_text)
            if (
                not isinstance(converted, int)
                or isinstance(converted, bool)
                or converted < 0
                or observed_id != converted
            ):
                raise TransformersProviderError(
                    f"loaded tokenizer {token_name}_id does not match token conversion"
                )
        special_texts[token_name] = observed_text
        special_ids[token_name + "_id"] = observed_id

    name_or_path = getattr(tokenizer, "name_or_path", None)
    if not isinstance(name_or_path, str) or (
        Path(name_or_path).resolve(strict=True) != snapshot_path
    ):
        raise TransformersProviderError(
            "loaded tokenizer is not bound to the verified snapshot path"
        )
    backend = getattr(tokenizer, "backend_tokenizer", None)
    serializer = getattr(backend, "to_str", None)
    if not callable(serializer):
        raise TransformersProviderError(
            "loaded tokenizer fast-backend serialization is unavailable"
        )
    backend_serialized = serializer()
    if not isinstance(backend_serialized, str) or not backend_serialized:
        raise TransformersProviderError(
            "loaded tokenizer fast-backend serialization is invalid"
        )
    model_max_length = getattr(tokenizer, "model_max_length", None)
    if not isinstance(model_max_length, int) or isinstance(model_max_length, bool):
        raise TransformersProviderError("loaded tokenizer model_max_length is invalid")
    backend_sha256 = hashlib.sha256(
        backend_serialized.encode("utf-8")
    ).hexdigest()
    if backend_sha256 != runtime.get("backend_sha256"):
        raise TransformersProviderError(
            "loaded tokenizer fast-backend semantic fingerprint mismatch"
        )
    return {
        "identity": f"{repository}@{revision}",
        "class": observed_class,
        "is_fast": bool(getattr(tokenizer, "is_fast")),
        "vocab_size": observed_vocab,
        "tokenizer_length": observed_length,
        "model_max_length": model_max_length,
        "native_prefix_policy": prefix_policy,
        "native_special_tokens_to_add": native_special_count,
        "native_prefix_probe_sha256": hashlib.sha256(
            probe.encode("utf-8")
        ).hexdigest(),
        "native_prefix_probe_equal": with_special == without_special,
        "special_tokens": special_texts,
        "special_token_ids": special_ids,
        "backend_sha256": backend_sha256,
        "verified": True,
    }


def _stage_tokenizer_files(
    source_snapshot: Path,
    destination: Path,
    receipt: Mapping[str, Any],
) -> None:
    _stage_verified_files(
        source_snapshot,
        destination,
        receipt,
        filenames={
            "config.json",
            "special_tokens_map.json",
            "tokenizer_config.json",
            "tokenizer.json",
        },
        label="tokenizer",
    )


def _stage_verified_files(
    source_snapshot: Path,
    destination: Path,
    receipt: Mapping[str, Any],
    *,
    filenames: set[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    """Stream exact verified inputs into a private create-only directory."""

    destination_info = os.lstat(destination)
    if (
        not stat.S_ISDIR(destination_info.st_mode)
        or stat.S_ISLNK(destination_info.st_mode)
        or bool(
            getattr(destination_info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
        )
    ):
        raise TransformersProviderError(
            f"private {label} staging root must be a plain directory"
        )
    raw_files = receipt.get("files")
    if not isinstance(raw_files, list):
        raise TransformersProviderError("snapshot receipt has no exact file list")
    identities = {
        item.get("filename"): item
        for item in raw_files
        if isinstance(item, Mapping)
    }
    staged: dict[str, dict[str, Any]] = {}
    for filename in sorted(filenames):
        expected = identities.get(filename)
        if not isinstance(expected, Mapping):
            raise TransformersProviderError(
                f"snapshot receipt lacks {label} input {filename}"
            )
        source = source_snapshot / filename
        target = destination / filename
        digest = hashlib.sha256()
        size = 0
        try:
            with source.open("rb") as source_handle, target.open("xb") as target_handle:
                for block in iter(lambda: source_handle.read(8 * 1024 * 1024), b""):
                    digest.update(block)
                    size += len(block)
                    target_handle.write(block)
                target_handle.flush()
                os.fsync(target_handle.fileno())
        except FileExistsError:
            raise
        except OSError as error:
            raise TransformersProviderError(
                f"could not privately stage {label} input {filename}: {error}"
            ) from error
        observed_sha256 = digest.hexdigest()
        if size != expected.get("size_bytes") or observed_sha256 != expected.get(
            "sha256"
        ):
            raise TransformersProviderError(
                f"{label} input changed before private staging: {filename}"
            )
        info = os.lstat(target)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or bool(
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
            )
        ):
            raise TransformersProviderError(
                f"private {label} input is not a regular file: {filename}"
            )
        if target.stat().st_size != size or _sha256_file(target) != observed_sha256:
            raise TransformersProviderError(
                f"private {label} input verification failed: {filename}"
            )
        staged[filename] = {
            "size_bytes": size,
            "sha256": observed_sha256,
            "verified": True,
        }
    if {path.name for path in destination.iterdir()} != filenames:
        raise TransformersProviderError(
            f"private {label} staging file set is not exact"
        )
    return staged


def _verify_staged_files(
    destination: Path,
    staged: Mapping[str, Mapping[str, Any]],
    *,
    label: str,
) -> None:
    if {path.name for path in destination.iterdir()} != set(staged):
        raise TransformersProviderError(f"private {label} staging file set changed")
    for filename, expected in staged.items():
        path = destination / filename
        info = os.lstat(path)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or bool(
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
            )
            or info.st_size != expected.get("size_bytes")
            or _sha256_file(path) != expected.get("sha256")
        ):
            raise TransformersProviderError(
                f"private {label} input changed after staging: {filename}"
            )


def _runtime_identity() -> dict[str, Any]:
    packages: dict[str, str] = {}
    for distribution in ("transformers", "tokenizers", "huggingface-hub"):
        try:
            packages[distribution] = version(distribution)
        except PackageNotFoundError as error:
            raise TransformersProviderError(
                f"runtime package identity is unavailable: {distribution}"
            ) from error
    return {
        "python": platform.python_version(),
        "packages": packages,
    }


def load_manifest_tokenizer(
    artifact: Mapping[str, Any],
    *,
    cache_dir: str | Path,
    snapshot_path: str | Path,
    manifest_path: str | Path = _CANONICAL_MANIFEST,
    expected_manifest_sha256: str,
) -> LoadedTokenizer:
    """Load a tokenizer only from an exact verified offline snapshot."""

    assert_tokenizer_ready(artifact)
    canonical, manifest_sha256 = _canonical_artifact(
        artifact,
        manifest_path,
        expected_manifest_sha256,
    )
    assert_tokenizer_snapshot_ready(canonical)
    _require_offline_environment()
    before = verify_snapshot(snapshot_path, cache_dir, canonical)
    tokenizer_config = before.get("tokenizer_config")
    if not isinstance(tokenizer_config, Mapping):
        raise TransformersProviderError(
            "verified snapshot has no exact tokenizer configuration"
        )

    resolved_snapshot = Path(str(before["snapshot_path"]))
    AutoTokenizer = _import_tokenizer()
    with tempfile.TemporaryDirectory(prefix="chronopersona-tokenizer-") as raw_stage:
        stage = Path(raw_stage).resolve(strict=True)
        _stage_tokenizer_files(
            resolved_snapshot,
            stage,
            before["portable_receipt"],
        )
        tokenizer = AutoTokenizer.from_pretrained(
            stage,
            local_files_only=True,
            trust_remote_code=False,
            use_fast=True,
        )
        after = verify_snapshot(snapshot_path, cache_dir, canonical)
        if before["portable_receipt"] != after["portable_receipt"]:
            raise TransformersProviderError(
                "verified snapshot changed while the tokenizer was being loaded"
            )
        repository, revision = _artifact_identity(canonical)
        validation = _loaded_tokenizer_validation(
            tokenizer,
            expected=tokenizer_config,
            repository=repository,
            revision=revision,
            snapshot_path=stage,
        )
    return LoadedTokenizer(
        tokenizer=tokenizer,
        repository=repository,
        revision=revision,
        model_manifest_sha256=manifest_sha256,
        snapshot_verification=after["portable_receipt"],
        tokenizer_validation=validation,
        runtime_identity=_runtime_identity(),
    )


def _validate_model_runtime(
    torch: Any,
    transformers: Any,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    if platform.python_version() != expected.get("python"):
        raise TransformersProviderError("model-scoring Python identity mismatch")
    packages: dict[str, str] = {
        "torch": str(torch.__version__),
        "transformers": str(transformers.__version__),
    }
    for distribution in (
        "tokenizers",
        "huggingface-hub",
        "accelerate",
        "safetensors",
    ):
        try:
            packages[distribution] = version(distribution)
        except PackageNotFoundError as error:
            raise TransformersProviderError(
                f"model-scoring package identity is unavailable: {distribution}"
            ) from error
    if packages != dict(expected.get("packages", {})):
        raise TransformersProviderError("model-scoring package identity mismatch")
    if not torch.cuda.is_available():
        raise TransformersProviderError("CUDA is unavailable for model scoring")
    if torch.cuda.device_count() != expected.get("cuda_device_count"):
        raise TransformersProviderError("model-scoring CUDA device count mismatch")
    if str(torch.version.cuda) != expected.get("cuda_runtime"):
        raise TransformersProviderError("model-scoring CUDA runtime mismatch")
    device = torch.device("cuda:0")
    properties = torch.cuda.get_device_properties(device)
    observed_device = {
        "index": 0,
        "name": torch.cuda.get_device_name(device),
        "capability": list(torch.cuda.get_device_capability(device)),
        "total_memory_bytes": int(properties.total_memory),
    }
    if observed_device != {
        "index": expected.get("cuda_device_index"),
        "name": expected.get("cuda_device_name"),
        "capability": expected.get("cuda_compute_capability"),
        "total_memory_bytes": expected.get("cuda_total_memory_bytes"),
    }:
        raise TransformersProviderError("model-scoring CUDA device identity mismatch")
    return {
        "python": platform.python_version(),
        "packages": packages,
        "cuda_runtime": str(torch.version.cuda),
        "cuda_device": observed_device,
        "verified": True,
    }


def _configure_model_determinism(
    torch: Any,
    sdpa_kernel: Any,
    math_backend: Any,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    if dict(expected) != {
        "fresh_invocations": 2,
        "exact_score_bytes_required": True,
        "algorithms": True,
        "cublas_workspace_config": ":4096:8",
        "attention_implementation": "sdpa",
        "sdpa_backends": ["math"],
        "sdpa_math_allow_fp16_reduction": False,
        "tf32": False,
        "cudnn_benchmark": False,
        "float32_matmul_precision": "highest",
        "use_cache": False,
        "rescue_runs": 0,
    }:
        raise TransformersProviderError("model-scoring determinism profile mismatch")
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != expected[
        "cublas_workspace_config"
    ]:
        raise TransformersProviderError("CUBLAS workspace policy is not frozen")
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.set_float32_matmul_precision("highest")
    torch.manual_seed(0)
    torch.cuda.manual_seed_all(0)
    with math_sdpa_context(torch, sdpa_kernel, math_backend):
        pass
    record = {
        **attention_policy_record(),
        "algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
        "tf32": bool(torch.backends.cuda.matmul.allow_tf32),
        "cudnn_tf32": bool(torch.backends.cudnn.allow_tf32),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
        "manual_seed": 0,
    }
    expected_record = {
        "attention_implementation": expected["attention_implementation"],
        "sdpa_backends": expected["sdpa_backends"],
        "sdpa_math_allow_fp16_reduction": expected[
            "sdpa_math_allow_fp16_reduction"
        ],
        "algorithms": True,
        "cublas_workspace_config": expected["cublas_workspace_config"],
        "tf32": False,
        "cudnn_tf32": False,
        "cudnn_benchmark": False,
        "float32_matmul_precision": expected["float32_matmul_precision"],
        "manual_seed": 0,
    }
    if record != expected_record:
        raise TransformersProviderError(
            "model-scoring deterministic controls were not applied exactly"
        )
    return {**record, "verified": True}


def _validate_loading_info(raw: Any) -> dict[str, list[Any]]:
    if not isinstance(raw, Mapping):
        raise TransformersProviderError("model loading diagnostics are missing")
    expected_keys = {
        "missing_keys",
        "unexpected_keys",
        "mismatched_keys",
        "error_msgs",
    }
    if set(raw) != expected_keys:
        raise TransformersProviderError("model loading diagnostic fields are not exact")
    normalized: dict[str, list[Any]] = {}
    for key in sorted(expected_keys):
        values = raw.get(key)
        if not isinstance(values, (list, tuple, set)):
            raise TransformersProviderError(
                f"model loading diagnostic {key} is not a sequence"
            )
        normalized[key] = sorted(values, key=repr)
        if normalized[key]:
            raise TransformersProviderError(
                f"model loading diagnostic is not empty: {key}"
            )
    return normalized


def _validate_loaded_model(
    model: Any,
    torch: Any,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    if model.__class__.__name__ != expected.get("class"):
        raise TransformersProviderError("loaded model class mismatch")
    config = getattr(model, "config", None)
    if config is None or getattr(config, "model_type", None) != expected.get(
        "model_type"
    ):
        raise TransformersProviderError("loaded model type mismatch")
    if getattr(config, "vocab_size", None) != expected.get("vocabulary_size"):
        raise TransformersProviderError("loaded model vocabulary mismatch")
    if getattr(config, "_attn_implementation", None) != ATTENTION_IMPLEMENTATION:
        raise TransformersProviderError("loaded model attention implementation mismatch")
    if getattr(model, "training", None) is not False:
        raise TransformersProviderError("loaded model is not in evaluation mode")
    if expected.get("quantized") is not False or bool(
        getattr(model, "is_quantized", False)
    ):
        raise TransformersProviderError("loaded model quantization policy mismatch")
    device_map = getattr(model, "hf_device_map", None)
    if expected.get("device_map") is not False or device_map not in (None, {}):
        raise TransformersProviderError("loaded model device-map policy mismatch")
    modules = getattr(model, "modules", None)
    observed_modules = list(modules()) if callable(modules) else [model]
    if expected.get("offload") is not False or any(
        getattr(module, "_hf_hook", None) is not None for module in observed_modules
    ):
        raise TransformersProviderError("loaded model offload-hook policy mismatch")

    parameters = list(model.parameters())
    parameter_count = sum(int(parameter.numel()) for parameter in parameters)
    if parameter_count != expected.get("parameter_count"):
        raise TransformersProviderError("loaded model parameter count mismatch")
    parameter_dtypes = sorted({str(parameter.dtype) for parameter in parameters})
    parameter_devices = sorted({str(parameter.device) for parameter in parameters})
    if parameter_dtypes != ["torch.float16"]:
        raise TransformersProviderError("loaded model parameter dtype mismatch")
    if parameter_devices != ["cuda:0"]:
        raise TransformersProviderError("loaded model parameter device mismatch")
    if any(bool(getattr(parameter, "is_meta", False)) for parameter in parameters):
        raise TransformersProviderError("loaded model contains meta parameters")
    buffer_devices = sorted({str(buffer.device) for buffer in model.buffers()})
    if any(device != "cuda:0" for device in buffer_devices):
        raise TransformersProviderError("loaded model contains non-CUDA buffers")
    if any(bool(getattr(buffer, "is_meta", False)) for buffer in model.buffers()):
        raise TransformersProviderError("loaded model contains meta buffers")
    return {
        "class": model.__class__.__name__,
        "model_type": config.model_type,
        "parameter_count": parameter_count,
        "parameter_dtypes": parameter_dtypes,
        "parameter_devices": parameter_devices,
        "buffer_devices": buffer_devices,
        "vocabulary_size": int(config.vocab_size),
        "eval_mode": True,
        "quantized": False,
        "device_map": False,
        "offload_hooks": False,
        "meta_parameters": False,
        "meta_buffers": False,
        **attention_policy_record(),
        "verified": True,
    }


def load_manifest_model(
    artifact: Mapping[str, Any],
    *,
    loaded_tokenizer: LoadedTokenizer,
    cache_dir: str | Path,
    snapshot_path: str | Path,
    manifest_path: str | Path = _CANONICAL_MANIFEST,
    expected_manifest_sha256: str,
    device: str,
    dtype: str,
    expected_model: Mapping[str, Any],
    expected_determinism: Mapping[str, Any],
    expected_runtime: Mapping[str, Any],
    pre_deserialization_check: Callable[[Any, Any], Any] | None = None,
) -> LoadedModel:
    """Load one unquantized causal LM after all model-score gates pass."""

    assert_model_score_ready(artifact)
    canonical, manifest_sha256 = _canonical_artifact(
        artifact,
        manifest_path,
        expected_manifest_sha256,
    )
    assert_tokenizer_snapshot_ready(canonical)
    _require_offline_environment()
    if device != "cuda:0" or dtype != "float16":
        raise TransformersProviderError(
            "verified model scoring requires exactly cuda:0 and float16"
        )
    repository, revision = _artifact_identity(canonical)
    if (
        loaded_tokenizer.repository != repository
        or loaded_tokenizer.revision != revision
        or loaded_tokenizer.model_manifest_sha256 != manifest_sha256
    ):
        raise TransformersProviderError("loaded tokenizer/model identity mismatch")
    before = verify_snapshot(snapshot_path, cache_dir, canonical)
    if loaded_tokenizer.snapshot_verification != before.get("portable_receipt"):
        raise TransformersProviderError("loaded tokenizer snapshot receipt mismatch")

    torch, transformers, AutoModelForCausalLM, sdpa_kernel, SDPBackend = (
        _import_model_stack()
    )
    runtime_identity = _validate_model_runtime(torch, transformers, expected_runtime)
    determinism = _configure_model_determinism(
        torch,
        sdpa_kernel,
        SDPBackend.MATH,
        expected_determinism,
    )
    resolved_cache = Path(cache_dir).resolve(strict=True)
    resolved_snapshot = Path(str(before["snapshot_path"]))
    target_device = torch.device(device)
    if target_device.type != "cuda" or target_device.index != 0:
        raise TransformersProviderError("model-scoring device did not resolve to cuda:0")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(target_device)
    load_start = time.perf_counter()
    with tempfile.TemporaryDirectory(
        prefix="chronopersona-model-",
        dir=resolved_cache,
    ) as raw_stage:
        stage = Path(raw_stage).resolve(strict=True)
        staged = _stage_verified_files(
            resolved_snapshot,
            stage,
            before["portable_receipt"],
            filenames={"config.json", "model.safetensors"},
            label="model",
        )
        _verify_staged_files(stage, staged, label="model")
        if pre_deserialization_check is not None:
            pre_deserialization_check(torch, transformers)
        _verify_staged_files(stage, staged, label="model")
        loaded = AutoModelForCausalLM.from_pretrained(
            stage,
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.float16,
            use_safetensors=True,
            low_cpu_mem_usage=True,
            attn_implementation=ATTENTION_IMPLEMENTATION,
            output_loading_info=True,
            weights_only=True,
        )
        if not isinstance(loaded, tuple) or len(loaded) != 2:
            raise TransformersProviderError(
                "model loader did not return exact loading diagnostics"
            )
        model, raw_loading_info = loaded
        loading_info = _validate_loading_info(raw_loading_info)
        model.to(target_device)
        model.eval()
        model_validation = _validate_loaded_model(model, torch, expected_model)
        _verify_staged_files(stage, staged, label="model")
    torch.cuda.synchronize(target_device)
    load_seconds = time.perf_counter() - load_start
    after = verify_snapshot(snapshot_path, cache_dir, canonical)
    if before["portable_receipt"] != after["portable_receipt"]:
        raise TransformersProviderError(
            "verified snapshot changed while the model was being loaded"
        )
    model_validation = {
        **model_validation,
        "determinism": determinism,
    }
    return LoadedModel(
        tokenizer=loaded_tokenizer.tokenizer,
        model=model,
        repository=repository,
        revision=revision,
        device=device,
        dtype=dtype,
        vocabulary_size=int(expected_model["vocabulary_size"]),
        model_manifest_sha256=manifest_sha256,
        snapshot_verification=after["portable_receipt"],
        tokenizer_validation=loaded_tokenizer.tokenizer_validation,
        runtime_identity=runtime_identity,
        model_validation=model_validation,
        loading_info=loading_info,
        load_seconds=load_seconds,
    )


def _import_scoring_stack() -> tuple[Any, Any, Any]:
    try:
        import torch
        from torch.nn.attention import SDPBackend, sdpa_kernel
    except ImportError as error:
        raise TransformersProviderError(
            "torch is required for model scoring"
        ) from error
    return torch, sdpa_kernel, SDPBackend


class TransformersContinuationProvider:
    """Callable token-log-probability provider for one loaded causal LM."""

    def __init__(
        self,
        loaded: LoadedModel,
        *,
        prefix_policy: str,
        max_length: int,
    ) -> None:
        if max_length < 2:
            raise TransformersProviderError("max_length must be at least 2")
        self.loaded = loaded
        self.max_length = max_length
        self.prefix_policy = prefix_policy
        self.prefix_token_ids = resolve_prefix_token_ids(
            loaded.tokenizer,
            prefix_policy,
        )
        if loaded.device != "cuda:0" or loaded.dtype != "float16":
            raise TransformersProviderError(
                "continuation provider requires the frozen CUDA FP16 model"
            )
        determinism = loaded.model_validation.get("determinism")
        if not isinstance(determinism, Mapping) or determinism.get(
            "verified"
        ) is not True:
            raise TransformersProviderError(
                "continuation provider requires verified deterministic controls"
            )
        self.forward_seconds: list[float] = []
        self.forwarded_token_count = 0
        self.predicted_token_count = 0
        self.continuation_token_count = 0
        self.maximum_full_token_count = 0
        self.math_sdpa_forward_count = 0
        self.autocast_disabled_forward_count = 0
        self._parameter_versions = tuple(
            (name, int(parameter._version))
            for name, parameter in loaded.model.named_parameters()
        )

    def __call__(self, prompt: str, continuation: str) -> CandidateEvidence:
        torch, sdpa_kernel, SDPBackend = _import_scoring_stack()

        if bool(torch.is_autocast_enabled("cuda")):
            raise TransformersProviderError("CUDA autocast is forbidden for scoring")
        self.autocast_disabled_forward_count += 1
        if (
            not bool(torch.are_deterministic_algorithms_enabled())
            or bool(torch.backends.cuda.matmul.allow_tf32)
            or bool(torch.backends.cudnn.allow_tf32)
            or bool(torch.backends.cudnn.benchmark)
            or torch.get_float32_matmul_precision() != "highest"
            or os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8"
        ):
            raise TransformersProviderError(
                "model-scoring deterministic controls drifted before a forward"
            )

        prepared = prepare_continuation(
            self.loaded.tokenizer,
            prompt,
            continuation,
            max_length=self.max_length,
            prefix_token_ids=self.prefix_token_ids,
        )
        device = torch.device(self.loaded.device)
        input_ids = torch.tensor(
            [prepared.full_token_ids],
            dtype=torch.long,
            device=device,
        )
        attention_mask = torch.ones_like(input_ids)

        torch.cuda.synchronize(device)
        started = time.perf_counter()
        with torch.inference_mode(), math_sdpa_context(
            torch,
            sdpa_kernel,
            SDPBackend.MATH,
        ):
            outputs = self.loaded.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                use_cache=False,
            )
            logits = getattr(outputs, "logits", None)
            if logits is None or logits.ndim != 3:
                raise TransformersProviderError(
                    "causal LM output does not contain rank-3 logits"
                )
            if logits.shape[0] != 1 or logits.shape[1] != input_ids.shape[1]:
                raise TransformersProviderError(
                    "causal LM logits have an unexpected batch/sequence shape"
                )
            if logits.shape[2] != self.loaded.vocabulary_size:
                raise TransformersProviderError(
                    "causal LM logits have an unexpected vocabulary shape"
                )
            if not bool(torch.isfinite(logits).all().item()):
                raise TransformersProviderError("causal LM logits are non-finite")
            next_token_logprobs = torch.log_softmax(
                logits[0, :-1, :].float(),
                dim=-1,
            )
            targets = input_ids[0, 1:]
            actual = next_token_logprobs.gather(
                dim=-1,
                index=targets.unsqueeze(-1),
            ).squeeze(-1)
            all_actual_logprobs = tuple(
                float(value)
                for value in actual.detach().cpu().tolist()
            )
        self.math_sdpa_forward_count += 1
        torch.cuda.synchronize(device)
        self.forward_seconds.append(time.perf_counter() - started)

        selected = select_continuation_logprobs(
            all_actual_logprobs,
            prepared,
        )
        if any(not math.isfinite(value) or value > 0.0 for value in selected):
            raise TransformersProviderError(
                "selected continuation log probabilities are invalid"
            )
        full_count = len(prepared.full_token_ids)
        self.forwarded_token_count += full_count
        self.predicted_token_count += full_count - 1
        self.continuation_token_count += len(prepared.continuation_token_ids)
        self.maximum_full_token_count = max(self.maximum_full_token_count, full_count)
        return CandidateEvidence(
            prompt_token_ids=prepared.prompt_token_ids,
            continuation_token_ids=prepared.continuation_token_ids,
            token_logprobs=selected,
            boundary_exact=True,
            truncated=False,
        )

    def assert_model_unchanged(self) -> None:
        observed = tuple(
            (name, int(parameter._version))
            for name, parameter in self.loaded.model.named_parameters()
        )
        if observed != self._parameter_versions:
            raise TransformersProviderError("model parameters changed during scoring")
        if getattr(self.loaded.model, "training", None) is not False:
            raise TransformersProviderError("model left evaluation mode during scoring")

    def runtime_metrics(self) -> dict[str, Any]:
        return {
            "candidate_forward_count": len(self.forward_seconds),
            "forward_seconds": list(self.forward_seconds),
            "aggregate_forward_seconds": sum(self.forward_seconds),
            "forwarded_token_count": self.forwarded_token_count,
            "predicted_token_count": self.predicted_token_count,
            "continuation_token_count": self.continuation_token_count,
            "maximum_full_token_count": self.maximum_full_token_count,
            "math_sdpa_forward_count": self.math_sdpa_forward_count,
            "autocast_disabled_forward_count": self.autocast_disabled_forward_count,
        }
