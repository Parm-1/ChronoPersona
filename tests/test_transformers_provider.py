from contextlib import nullcontext
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from chronopersona.model_manifest import load_model_manifest
from chronopersona.scoring import ScoringIntegrityError
from chronopersona.scoring_runtime import load_scoring_config
from chronopersona.tokenization import PreparedContinuation
from chronopersona.transformers_provider import (
    LoadedModel,
    LoadedTokenizer,
    TransformersContinuationProvider,
    TransformersProviderError,
    _configure_model_determinism,
    _validate_loaded_model,
    _validate_loading_info,
    _stage_verified_files,
    _loaded_tokenizer_validation,
    _stage_tokenizer_files,
    load_manifest_model,
    load_manifest_tokenizer,
    select_continuation_logprobs,
)


MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "manifests"
    / "MODEL_MANIFEST.json"
)
MANIFEST_SHA256 = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
SCORING_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "runs"
    / "pythia-development-score-v0.json"
)


def _ready_artifact():
    manifest = load_model_manifest(MANIFEST)
    return next(
        artifact
        for artifact in manifest["artifacts"]
        if artifact["id"] == "pythia-1b-deduped-main"
    )


def _artifact(artifact_id: str):
    manifest = load_model_manifest(MANIFEST)
    return next(
        artifact
        for artifact in manifest["artifacts"]
        if artifact["id"] == artifact_id
    )


def _prepared() -> PreparedContinuation:
    return PreparedContinuation(
        prompt_token_ids=(10, 11),
        continuation_token_ids=(12, 13),
        full_token_ids=(10, 11, 12, 13),
        continuation_start_index=2,
        first_prediction_index=1,
        final_prediction_index=2,
    )


def test_selects_only_continuation_prediction_positions() -> None:
    selected = select_continuation_logprobs(
        (-0.1, -0.2, -0.3),
        _prepared(),
    )

    assert selected == pytest.approx((-0.2, -0.3))


def test_full_next_token_count_must_match_sequence() -> None:
    with pytest.raises(
        ScoringIntegrityError,
        match="count does not match sequence",
    ):
        select_continuation_logprobs((-0.1, -0.2), _prepared())


def test_prepared_positions_must_select_every_continuation_token() -> None:
    malformed = PreparedContinuation(
        prompt_token_ids=(10, 11),
        continuation_token_ids=(12, 13),
        full_token_ids=(10, 11, 12, 13),
        continuation_start_index=2,
        first_prediction_index=1,
        final_prediction_index=1,
    )

    with pytest.raises(
        ScoringIntegrityError,
        match="selected continuation log-probability count",
    ):
        select_continuation_logprobs(
            (-0.1, -0.2, -0.3),
            malformed,
        )


def _verification(snapshot: Path, *, receipt: str = "same") -> dict:
    return {
        "snapshot_path": str(snapshot),
        "portable_receipt": {"receipt_sha256": receipt},
        "tokenizer_config": {
            "vocab_size": 2,
            "tokenizer_length": 3,
            "runtime_expectation": {
                "class": "GPTNeoXTokenizer",
                "is_fast": True,
                "native_prefix_policy": "none",
                "native_special_tokens_to_add": 0,
                "vocab_size": 2,
                "tokenizer_length": 3,
                "special_tokens": {
                    "bos_token": "<e>",
                    "eos_token": "<e>",
                    "pad_token": "<pad>",
                    "unk_token": "<e>",
                },
                "special_token_ids": {
                    "bos_token_id": 0,
                    "eos_token_id": 0,
                    "pad_token_id": 1,
                    "unk_token_id": 0,
                },
                "backend_sha256": hashlib.sha256(
                    b'{"fixture":true}'
                ).hexdigest(),
            },
        },
    }


class _Backend:
    def to_str(self) -> str:
        return '{"fixture":true}'


class GPTNeoXTokenizer:
    is_fast = True
    vocab_size = 2
    model_max_length = 2048
    bos_token = "<e>"
    eos_token = "<e>"
    pad_token = "<pad>"
    unk_token = "<e>"
    bos_token_id = 0
    eos_token_id = 0
    pad_token_id = 1
    unk_token_id = 0
    backend_tokenizer = _Backend()

    def __init__(self, path: Path) -> None:
        self.name_or_path = str(path)

    def __len__(self) -> int:
        return 3

    def convert_tokens_to_ids(self, token: str) -> int:
        return {"<e>": 0, "<pad>": 1}[token]

    def num_special_tokens_to_add(self, *, pair: bool = False) -> int:
        assert pair is False
        return 0

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert text
        return [1, 2]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("class", "class mismatch"),
        ("fast", "fast-backend policy mismatch"),
        ("vocab", "vocabulary size mismatch"),
        ("length", "length mismatch"),
        ("native-count", "native special-token count mismatch"),
        ("native-prefix", "native-prefix probe contradicts none policy"),
        ("implicit-pad", "pad_token identity mismatch"),
        ("backend", "semantic fingerprint mismatch"),
    ],
)
def test_loaded_tokenizer_runtime_drift_fails_closed(
    case: str,
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokenizer: GPTNeoXTokenizer = GPTNeoXTokenizer(tmp_path)
    if case == "class":
        class UnexpectedTokenizer(GPTNeoXTokenizer):
            pass

        tokenizer = UnexpectedTokenizer(tmp_path)
    elif case == "fast":
        tokenizer.is_fast = False
    elif case == "vocab":
        tokenizer.vocab_size = 99
    elif case == "length":
        monkeypatch.setattr(GPTNeoXTokenizer, "__len__", lambda _self: 4)
    elif case == "native-count":
        monkeypatch.setattr(
            GPTNeoXTokenizer,
            "num_special_tokens_to_add",
            lambda _self, *, pair=False: 1,
        )
    elif case == "native-prefix":
        monkeypatch.setattr(
            GPTNeoXTokenizer,
            "encode",
            lambda _self, _text, *, add_special_tokens: (
                [0, 1, 2] if add_special_tokens else [1, 2]
            ),
        )
    elif case == "implicit-pad":
        tokenizer.pad_token = "<unexpected-pad>"
    elif case == "backend":
        tokenizer.backend_tokenizer = type(
            "ChangedBackend",
            (),
            {"to_str": lambda _self: '{"fixture":false}'},
        )()
    else:  # pragma: no cover - protects the parameter table
        raise AssertionError(case)

    with pytest.raises(TransformersProviderError, match=message):
        _loaded_tokenizer_validation(
            tokenizer,
            expected=_verification(tmp_path)["tokenizer_config"],
            repository="EleutherAI/pythia-1b-deduped",
            revision="a" * 40,
            snapshot_path=tmp_path,
        )


@pytest.mark.parametrize("native_ids", [[1, 2, 0], [2, 1, 2]])
def test_loaded_tokenizer_bos_policy_rejects_wrong_native_placement(
    native_ids: list[int],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _verification(tmp_path)["tokenizer_config"]
    runtime = expected["runtime_expectation"]
    runtime["native_prefix_policy"] = "bos"
    runtime["native_special_tokens_to_add"] = 1
    monkeypatch.setattr(
        GPTNeoXTokenizer,
        "num_special_tokens_to_add",
        lambda _self, *, pair=False: 1,
    )
    monkeypatch.setattr(
        GPTNeoXTokenizer,
        "encode",
        lambda _self, _text, *, add_special_tokens: (
            native_ids if add_special_tokens else [1, 2]
        ),
    )

    with pytest.raises(TransformersProviderError, match="contradicts bos policy"):
        _loaded_tokenizer_validation(
            GPTNeoXTokenizer(tmp_path),
            expected=expected,
            repository="EleutherAI/pythia-1b-deduped",
            revision="a" * 40,
            snapshot_path=tmp_path,
        )


def test_manifest_tokenizer_policy_blocks_before_manifest_or_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chronopersona.transformers_provider._canonical_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("canonical manifest lookup was reached")
        ),
    )

    with pytest.raises(
        ValueError,
        match="license must be verified",
    ):
        load_manifest_tokenizer(
            _artifact("datedgpt-2013-base"),
            cache_dir="unused",
            snapshot_path="unused",
            expected_manifest_sha256=MANIFEST_SHA256,
        )


def test_manifest_tokenizer_requires_snapshot_manifest_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_tokenizer",
        lambda: (_ for _ in ()).throw(
            AssertionError("optional tokenizer import was reached")
        ),
    )

    with pytest.raises(ValueError, match="snapshot manifest"):
        load_manifest_tokenizer(
            _artifact("olmo2-1b-early-step20000"),
            cache_dir="unused",
            snapshot_path="unused",
            expected_manifest_sha256=MANIFEST_SHA256,
        )


def test_manifest_tokenizer_requires_offline_flags_before_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.setattr(
        "chronopersona.transformers_provider.verify_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("snapshot verification was reached")
        ),
    )

    with pytest.raises(TransformersProviderError, match="offline environment"):
        load_manifest_tokenizer(
            _ready_artifact(),
            cache_dir="unused",
            snapshot_path="unused",
            expected_manifest_sha256=MANIFEST_SHA256,
        )


def test_manifest_tokenizer_verifies_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr(
        "chronopersona.transformers_provider.verify_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("fixture integrity failure")
        ),
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_tokenizer",
        lambda: (_ for _ in ()).throw(
            AssertionError("optional tokenizer import was reached")
        ),
    )

    with pytest.raises(RuntimeError, match="integrity failure"):
        load_manifest_tokenizer(
            _ready_artifact(),
            cache_dir="unused",
            snapshot_path="unused",
            expected_manifest_sha256=MANIFEST_SHA256,
        )


def test_manifest_tokenizer_loads_only_exact_verified_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    observed: dict[str, object] = {}
    calls = 0

    def fake_verify(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return _verification(snapshot)

    class AutoTokenizer:
        @classmethod
        def from_pretrained(cls, path: Path, **kwargs: object):
            observed["path"] = path
            observed.update(kwargs)
            return GPTNeoXTokenizer(path)

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr(
        "chronopersona.transformers_provider.verify_snapshot",
        fake_verify,
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_tokenizer",
        lambda: AutoTokenizer,
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._stage_tokenizer_files",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._runtime_identity",
        lambda: {
            "python": "fixture",
            "packages": {
                "transformers": "fixture",
                "tokenizers": "fixture",
                "huggingface-hub": "fixture",
            },
        },
    )

    loaded = load_manifest_tokenizer(
        _ready_artifact(),
        cache_dir=tmp_path,
        snapshot_path=snapshot,
        expected_manifest_sha256=MANIFEST_SHA256,
    )

    assert calls == 2
    assert observed["path"] != snapshot
    assert observed["local_files_only"] is True
    assert observed["trust_remote_code"] is False
    assert observed["use_fast"] is True
    assert not Path(observed["path"]).exists()
    assert loaded.tokenizer_validation["identity"].startswith(
        "EleutherAI/pythia-1b-deduped@"
    )
    assert str(tmp_path) not in str(loaded.snapshot_verification)


def test_manifest_tokenizer_rejects_snapshot_change_after_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    verifications = iter(
        [_verification(snapshot, receipt="before"), _verification(snapshot, receipt="after")]
    )

    class AutoTokenizer:
        @classmethod
        def from_pretrained(cls, path: Path, **_kwargs: object):
            return GPTNeoXTokenizer(path)

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr(
        "chronopersona.transformers_provider.verify_snapshot",
        lambda *_args, **_kwargs: next(verifications),
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_tokenizer",
        lambda: AutoTokenizer,
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._stage_tokenizer_files",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(TransformersProviderError, match="changed while"):
        load_manifest_tokenizer(
            _ready_artifact(),
            cache_dir=tmp_path,
            snapshot_path=snapshot,
            expected_manifest_sha256=MANIFEST_SHA256,
        )


def test_private_staging_copies_only_exact_tokenizer_inputs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "stage"
    source.mkdir()
    destination.mkdir()
    payloads = {
        "config.json": b"config",
        "special_tokens_map.json": b"special",
        "tokenizer_config.json": b"tokenizer-config",
        "tokenizer.json": b"tokenizer",
        "model.safetensors": b"weights-must-not-stage",
    }
    for filename, payload in payloads.items():
        (source / filename).write_bytes(payload)
    receipt = {
        "files": [
            {
                "filename": filename,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for filename, payload in payloads.items()
        ]
    }

    _stage_tokenizer_files(source, destination, receipt)

    assert {path.name for path in destination.iterdir()} == {
        "config.json",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "tokenizer.json",
    }
    assert all(path.is_file() and not path.is_symlink() for path in destination.iterdir())
    assert not (destination / "model.safetensors").exists()

    (source / "tokenizer.json").write_bytes(b"tampered")
    second = tmp_path / "second-stage"
    second.mkdir()
    with pytest.raises(TransformersProviderError, match="changed before private staging"):
        _stage_tokenizer_files(source, second, receipt)


def test_private_staging_refuses_preexisting_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "stage"
    source.mkdir()
    destination.mkdir()
    names = (
        "config.json",
        "special_tokens_map.json",
        "tokenizer_config.json",
        "tokenizer.json",
    )
    for name in names:
        (source / name).write_bytes(name.encode("utf-8"))
    (destination / "config.json").write_bytes(b"sentinel")
    receipt = {
        "files": [
            {
                "filename": name,
                "size_bytes": len(name.encode("utf-8")),
                "sha256": hashlib.sha256(name.encode("utf-8")).hexdigest(),
            }
            for name in names
        ]
    }

    with pytest.raises(FileExistsError):
        _stage_tokenizer_files(source, destination, receipt)
    assert (destination / "config.json").read_bytes() == b"sentinel"


def test_manifest_model_policy_blocks_before_optional_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_import():
        raise AssertionError("optional model import was reached")

    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_model_stack",
        unexpected_import,
    )

    with pytest.raises(ValueError, match="license must be verified"):
        load_manifest_model(
            _artifact("datedgpt-2013-base"),
            loaded_tokenizer=None,  # type: ignore[arg-type]
            cache_dir="unused",
            snapshot_path="unused",
            expected_manifest_sha256=MANIFEST_SHA256,
            device="cuda:0",
            dtype="float16",
            expected_model={},
            expected_determinism={},
            expected_runtime={},
        )


def test_private_model_staging_copies_only_config_and_safetensors(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    stage = tmp_path / "stage"
    source.mkdir()
    stage.mkdir()
    payloads = {
        "config.json": b"config",
        "model.safetensors": b"model-weights",
        "tokenizer.json": b"must-not-stage",
    }
    for filename, payload in payloads.items():
        (source / filename).write_bytes(payload)
    receipt = {
        "files": [
            {
                "filename": filename,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for filename, payload in payloads.items()
        ]
    }

    staged = _stage_verified_files(
        source,
        stage,
        receipt,
        filenames={"config.json", "model.safetensors"},
        label="model",
    )

    assert set(staged) == {"config.json", "model.safetensors"}
    assert {path.name for path in stage.iterdir()} == set(staged)
    assert not (stage / "tokenizer.json").exists()


def test_manifest_model_load_uses_private_stage_and_exact_kwargs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _ready_artifact()
    cache = tmp_path / "cache"
    snapshot = cache / "snapshot"
    snapshot.mkdir(parents=True)
    receipt = {
        "schema_version": 1,
        "status": "verified",
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": artifact["revision"],
        "receipt_sha256": "a" * 64,
        "files": [],
    }
    verification = {
        "snapshot_path": str(snapshot),
        "portable_receipt": receipt,
    }
    loaded_tokenizer = LoadedTokenizer(
        tokenizer=object(),
        repository=str(artifact["repository"]),
        revision=str(artifact["revision"]),
        model_manifest_sha256=MANIFEST_SHA256,
        snapshot_verification=receipt,
        tokenizer_validation={"verified": True},
        runtime_identity={"python": "fixture"},
    )
    order: list[str] = []
    observed: dict[str, object] = {}

    class FakeCuda:
        @staticmethod
        def empty_cache() -> None:
            pass

        @staticmethod
        def reset_peak_memory_stats(_device: object) -> None:
            pass

        @staticmethod
        def synchronize(_device: object) -> None:
            pass

    class FakeTorch:
        float16 = "float16"
        cuda = FakeCuda()

        @staticmethod
        def device(value: str):
            return type("Device", (), {"type": "cuda", "index": 0, "value": value})()

    class FakeModel:
        def to(self, _device: object):
            return self

        def eval(self):
            order.append("eval")
            return self

    class AutoModel:
        @classmethod
        def from_pretrained(cls, path: Path, **kwargs: object):
            order.append("deserialize")
            observed["path"] = path
            observed["kwargs"] = kwargs
            return FakeModel(), {
                "missing_keys": [],
                "unexpected_keys": [],
                "mismatched_keys": [],
                "error_msgs": [],
            }

    class Backend:
        MATH = "math"

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr(
        "chronopersona.transformers_provider.verify_snapshot",
        lambda *_args, **_kwargs: verification,
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_model_stack",
        lambda: (FakeTorch, object(), AutoModel, object(), Backend),
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._validate_model_runtime",
        lambda *_args: {"verified": True},
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._configure_model_determinism",
        lambda *_args: {"verified": True},
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._stage_verified_files",
        lambda _source, destination, *_args, **_kwargs: (
            order.append("stage"),
            (destination / "config.json").write_bytes(b"config"),
            (destination / "model.safetensors").write_bytes(b"weights"),
            {
                "config.json": {"size_bytes": 6, "sha256": "a" * 64},
                "model.safetensors": {"size_bytes": 7, "sha256": "b" * 64},
            },
        )[-1],
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._verify_staged_files",
        lambda *_args, **_kwargs: order.append("verify"),
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider._validate_loaded_model",
        lambda *_args: {"verified": True},
    )

    loaded = load_manifest_model(
        artifact,
        loaded_tokenizer=loaded_tokenizer,
        cache_dir=cache,
        snapshot_path=snapshot,
        expected_manifest_sha256=MANIFEST_SHA256,
        device="cuda:0",
        dtype="float16",
        expected_model={"vocabulary_size": 50304},
        expected_determinism={},
        expected_runtime={},
        pre_deserialization_check=lambda *_args: order.append("preflight"),
    )

    assert order[:5] == ["stage", "verify", "preflight", "verify", "deserialize"]
    assert observed["path"] != snapshot
    assert not Path(observed["path"]).exists()
    assert observed["kwargs"] == {
        "local_files_only": True,
        "trust_remote_code": False,
        "torch_dtype": "float16",
        "use_safetensors": True,
        "low_cpu_mem_usage": True,
        "attn_implementation": "sdpa",
        "output_loading_info": True,
        "weights_only": True,
    }
    assert loaded.loading_info == {
        "error_msgs": [],
        "mismatched_keys": [],
        "missing_keys": [],
        "unexpected_keys": [],
    }


def test_determinism_configuration_rejects_noop_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_scoring_config(SCORING_CONFIG)
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

    class CudaBackend:
        matmul = SimpleNamespace(allow_tf32=False)

        @staticmethod
        def allow_fp16_bf16_reduction_math_sdp(_value: bool) -> None:
            pass

        @staticmethod
        def fp16_bf16_reduction_math_sdp_allowed() -> bool:
            return False

    class Cuda:
        @staticmethod
        def manual_seed_all(_seed: int) -> None:
            pass

    class Torch:
        backends = SimpleNamespace(
            cuda=CudaBackend(),
            cudnn=SimpleNamespace(allow_tf32=False, benchmark=False),
        )
        cuda = Cuda()

        @staticmethod
        def use_deterministic_algorithms(_enabled: bool) -> None:
            pass

        @staticmethod
        def are_deterministic_algorithms_enabled() -> bool:
            return False

        @staticmethod
        def set_float32_matmul_precision(_value: str) -> None:
            pass

        @staticmethod
        def get_float32_matmul_precision() -> str:
            return "medium"

        @staticmethod
        def manual_seed(_seed: int) -> None:
            pass

    with pytest.raises(TransformersProviderError, match="not applied exactly"):
        _configure_model_determinism(
            Torch,
            lambda _backend: nullcontext(),
            "math",
            config["determinism"],
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("quantized", "quantization policy mismatch"),
        ("device-map", "device-map policy mismatch"),
        ("offload", "offload-hook policy mismatch"),
    ],
)
def test_loaded_model_rejects_hidden_loading_modes(
    case: str,
    message: str,
) -> None:
    config = load_scoring_config(SCORING_CONFIG)

    class Parameter:
        dtype = "torch.float16"
        device = "cuda:0"
        is_meta = False

        def numel(self) -> int:
            return config["model"]["parameter_count"]

    Model = type(
        "GPTNeoXForCausalLM",
        (),
        {
            "training": False,
            "is_quantized": False,
            "hf_device_map": None,
            "_hf_hook": None,
            "config": SimpleNamespace(
                model_type="gpt_neox",
                vocab_size=config["model"]["vocabulary_size"],
                _attn_implementation="sdpa",
            ),
            "parameters": lambda _self: [Parameter()],
            "buffers": lambda _self: [],
            "modules": lambda self: [self],
        },
    )
    model = Model()
    if case == "quantized":
        model.is_quantized = True
    elif case == "device-map":
        model.hf_device_map = {"": "disk"}
    else:
        model._hf_hook = object()

    with pytest.raises(TransformersProviderError, match=message):
        _validate_loaded_model(model, object(), config["model"])


@pytest.mark.parametrize(
    "loading_info",
    [
        {
            "missing_keys": ["weight"],
            "unexpected_keys": [],
            "mismatched_keys": [],
            "error_msgs": [],
        },
        {
            "missing_keys": [],
            "unexpected_keys": [],
            "mismatched_keys": [],
            "error_msgs": [],
            "extra": [],
        },
    ],
)
def test_model_loading_diagnostics_fail_closed(loading_info: dict) -> None:
    with pytest.raises(TransformersProviderError, match="diagnostic"):
        _validate_loading_info(loading_info)


@pytest.mark.parametrize(
    ("logits", "autocast_enabled", "message", "expected_context_entries"),
    [
        (None, False, "does not contain rank-3 logits", 1),
        (
            SimpleNamespace(ndim=2, shape=(1, 4)),
            False,
            "does not contain rank-3 logits",
            1,
        ),
        (SimpleNamespace(ndim=3, shape=(1, 4, 2)), False, "vocabulary shape", 1),
        (SimpleNamespace(ndim=3, shape=(1, 4, 3)), False, "non-finite", 1),
        (None, True, "autocast is forbidden", 0),
    ],
)
def test_provider_enters_math_context_and_rejects_bad_logits(
    logits: object,
    autocast_enabled: bool,
    message: str,
    expected_context_entries: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Input:
        shape = (1, 4)

    class BooleanResult:
        @staticmethod
        def all():
            return SimpleNamespace(item=lambda: False)

    class Cuda:
        matmul = SimpleNamespace(allow_tf32=False)

        @staticmethod
        def synchronize(_device: object) -> None:
            pass

    class Torch:
        long = "long"
        cuda = Cuda()
        backends = SimpleNamespace(
            cuda=Cuda(),
            cudnn=SimpleNamespace(allow_tf32=False, benchmark=False),
        )

        @staticmethod
        def is_autocast_enabled(_device: str) -> bool:
            return autocast_enabled

        @staticmethod
        def are_deterministic_algorithms_enabled() -> bool:
            return True

        @staticmethod
        def get_float32_matmul_precision() -> str:
            return "highest"

        @staticmethod
        def device(value: str) -> str:
            return value

        @staticmethod
        def tensor(*_args, **_kwargs) -> Input:
            return Input()

        @staticmethod
        def ones_like(_value: object) -> object:
            return object()

        @staticmethod
        def inference_mode():
            return nullcontext()

        @staticmethod
        def isfinite(_value: object) -> BooleanResult:
            return BooleanResult()

    class Backend:
        MATH = "math"

    class Model:
        training = False

        def named_parameters(self):
            return []

        def __call__(self, **_kwargs):
            return SimpleNamespace(logits=logits)

    loaded = LoadedModel(
        tokenizer=object(),
        model=Model(),
        repository="repo",
        revision="a" * 40,
        device="cuda:0",
        dtype="float16",
        vocabulary_size=3,
        model_manifest_sha256="b" * 64,
        snapshot_verification={},
        tokenizer_validation={},
        runtime_identity={},
        model_validation={"determinism": {"verified": True}},
        loading_info={},
        load_seconds=0.0,
    )
    entered = 0

    class Context:
        def __enter__(self):
            nonlocal entered
            entered += 1

        def __exit__(self, *_args):
            return False

    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_scoring_stack",
        lambda: (Torch, object(), Backend),
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider.math_sdpa_context",
        lambda *_args: Context(),
    )
    monkeypatch.setattr(
        "chronopersona.transformers_provider.prepare_continuation",
        lambda *_args, **_kwargs: _prepared(),
    )
    provider = TransformersContinuationProvider(
        loaded,
        prefix_policy="none",
        max_length=2048,
    )

    with pytest.raises(TransformersProviderError, match=message):
        provider("prompt", "continuation")

    assert entered == expected_context_entries


def test_provider_rejects_parameter_or_eval_state_mutation() -> None:
    parameter = SimpleNamespace(_version=0)
    model = SimpleNamespace(
        training=False,
        named_parameters=lambda: [("weight", parameter)],
    )
    loaded = LoadedModel(
        tokenizer=object(),
        model=model,
        repository="repo",
        revision="a" * 40,
        device="cuda:0",
        dtype="float16",
        vocabulary_size=3,
        model_manifest_sha256="b" * 64,
        snapshot_verification={},
        tokenizer_validation={},
        runtime_identity={},
        model_validation={"determinism": {"verified": True}},
        loading_info={},
        load_seconds=0.0,
    )
    provider = TransformersContinuationProvider(
        loaded,
        prefix_policy="none",
        max_length=2048,
    )

    parameter._version = 1
    with pytest.raises(TransformersProviderError, match="parameters changed"):
        provider.assert_model_unchanged()

    parameter._version = 0
    model.training = True
    with pytest.raises(TransformersProviderError, match="left evaluation mode"):
        provider.assert_model_unchanged()
