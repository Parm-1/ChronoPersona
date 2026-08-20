import hashlib
from pathlib import Path

import pytest

from chronopersona.model_manifest import load_model_manifest
from chronopersona.scoring import ScoringIntegrityError
from chronopersona.tokenization import PreparedContinuation
from chronopersona.transformers_provider import (
    TransformersProviderError,
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


@pytest.mark.parametrize("allow_download", [False, True])
def test_manifest_model_load_blocks_before_optional_imports(
    allow_download: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_import():
        raise AssertionError("optional model import was reached")

    monkeypatch.setattr(
        "chronopersona.transformers_provider._import_model_stack",
        unexpected_import,
    )

    with pytest.raises(
        TransformersProviderError,
        match="clean-head live-resource",
    ):
        load_manifest_model(
            _ready_artifact(),
            allow_download=allow_download,
            device="cuda",
            dtype="float16",
        )
