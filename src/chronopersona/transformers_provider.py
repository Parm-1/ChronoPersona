"""Manifest-gated Transformers adapters for tokenizer audit and scoring.

Optional model dependencies are imported only when an approved operation is
executed. This module never enables custom remote code or quantization.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import stat
import tempfile
from typing import Any

from .artifact_policy import (
    assert_model_score_ready,
    assert_tokenizer_ready,
    assert_tokenizer_snapshot_ready,
    find_artifact,
)
from .model_manifest import validate_model_manifest
from .model_snapshot import verify_snapshot
from .scoring import CandidateEvidence, ScoringIntegrityError
from .tokenization import PreparedContinuation, prepare_continuation
from .tokenizer_audit import resolve_prefix_token_ids


class TransformersProviderError(RuntimeError):
    """Raised when an approved Transformers operation cannot be completed."""


_VERIFIED_SNAPSHOT_BLOCKER = (
    "model scoring remains disabled until the verified-snapshot loader is "
    "combined with the clean-head live-resource and exact-load gates"
)

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


def _import_model_stack() -> tuple[Any, Any, Any]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:
        raise TransformersProviderError(
            "Transformers scoring dependencies are missing; install `.[models]`"
        ) from error
    return torch, AutoModelForCausalLM, AutoTokenizer


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
            "private tokenizer staging root must be a plain directory"
        )
    required_names = {
        "config.json",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "tokenizer.json",
    }
    raw_files = receipt.get("files")
    if not isinstance(raw_files, list):
        raise TransformersProviderError("snapshot receipt has no exact file list")
    identities = {
        item.get("filename"): item
        for item in raw_files
        if isinstance(item, Mapping)
    }
    for filename in sorted(required_names):
        expected = identities.get(filename)
        if not isinstance(expected, Mapping):
            raise TransformersProviderError(
                f"snapshot receipt lacks tokenizer input {filename}"
            )
        payload = (source_snapshot / filename).read_bytes()
        if len(payload) != expected.get("size_bytes") or hashlib.sha256(
            payload
        ).hexdigest() != expected.get("sha256"):
            raise TransformersProviderError(
                f"tokenizer input changed before private staging: {filename}"
            )
        target = destination / filename
        with target.open("xb") as handle:
            handle.write(payload)
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
                f"private tokenizer input is not a regular file: {filename}"
            )
        if _sha256_file(target) != expected.get("sha256"):
            raise TransformersProviderError(
                f"private tokenizer input verification failed: {filename}"
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


def _resolve_dtype(torch: Any, dtype: str) -> Any:
    if dtype == "auto":
        return "auto"
    mapping = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    if dtype not in mapping:
        raise TransformersProviderError(
            "dtype must be auto, float16, bfloat16, or float32"
        )
    return mapping[dtype]


def load_manifest_model(
    artifact: Mapping[str, Any],
    *,
    allow_download: bool,
    device: str,
    dtype: str,
    cache_dir: str | Path | None = None,
) -> LoadedModel:
    """Load one unquantized causal LM after all model-score gates pass."""

    assert_model_score_ready(artifact)
    if device not in {"cpu", "cuda"}:
        raise TransformersProviderError("device must be cpu or cuda")
    raise TransformersProviderError(_VERIFIED_SNAPSHOT_BLOCKER)


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

    def __call__(self, prompt: str, continuation: str) -> CandidateEvidence:
        try:
            import torch
        except ImportError as error:
            raise TransformersProviderError(
                "torch is required for model scoring"
            ) from error

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

        with torch.inference_mode():
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

        selected = select_continuation_logprobs(
            all_actual_logprobs,
            prepared,
        )
        return CandidateEvidence(
            prompt_token_ids=prepared.prompt_token_ids,
            continuation_token_ids=prepared.continuation_token_ids,
            token_logprobs=selected,
            boundary_exact=True,
            truncated=False,
        )
