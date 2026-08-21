import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import sys

import pytest

from chronopersona.evaluation import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_registry_tokenizer.py"
REVISION = "7199d8fc61a6d565cd1f3c62bf11525b563e13b2"


def _module():
    spec = importlib.util.spec_from_file_location(
        "audit_registry_tokenizer_test",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CharacterTokenizer:
    name_or_path = "must-not-leak"
    vocab_size = 256
    model_max_length = 4096
    bos_token_id = 1
    eos_token_id = 2
    pad_token_id = None
    unk_token_id = None

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        assert add_special_tokens is False
        return [ord(character) % 256 for character in text]


def _loaded(manifest_sha256: str) -> SimpleNamespace:
    return SimpleNamespace(
        tokenizer=CharacterTokenizer(),
        repository="EleutherAI/pythia-1b-deduped",
        revision=REVISION,
        model_manifest_sha256=manifest_sha256,
        snapshot_verification={
            "schema_version": 1,
            "status": "verified",
            "artifact_id": "pythia-1b-deduped-main",
            "repository": "EleutherAI/pythia-1b-deduped",
            "revision": REVISION,
            "files": [
                {
                    "filename": "model.safetensors",
                    "size_bytes": 123,
                    "sha256": "b" * 64,
                    "verified": True,
                }
            ],
            "receipt_sha256": "c" * 64,
        },
        tokenizer_validation={
            "identity": f"EleutherAI/pythia-1b-deduped@{REVISION}",
            "class": "CharacterTokenizer",
            "is_fast": True,
            "native_prefix_policy": "none",
            "backend_sha256": "d" * 64,
            "verified": True,
        },
        runtime_identity={
            "python": "3.11.9",
            "packages": {
                "transformers": "fixture",
                "tokenizers": "fixture",
                "huggingface-hub": "fixture",
            },
        },
    )


def _all_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _all_strings(key)
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)


def _argv(cache: Path, snapshot: Path, output: Path) -> list[str]:
    return [
        str(SCRIPT),
        "--artifact",
        "pythia-1b-deduped-main",
        "--prefix-policy",
        "none",
        "--execute",
        "--cache-dir",
        str(cache),
        "--snapshot-path",
        str(snapshot),
        "--output",
        str(output),
    ]


def test_execute_report_is_finally_hashed_portable_and_repeatable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _module()
    cache = tmp_path / "cache"
    snapshot = cache / "snapshot"
    snapshot.mkdir(parents=True)
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    manifest_payload = module.DEFAULT_MANIFEST.read_bytes()
    registry_payload = module.DEFAULT_REGISTRY.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    monkeypatch.setattr(
        module,
        "load_manifest_tokenizer",
        lambda *_a, **_k: _loaded(manifest_sha256),
    )
    binding = {
        "git_head": "e" * 40,
        "worktree_clean": True,
        "model_manifest_git_blob": "f" * 40,
        "development_registry_git_blob": "1" * 40,
    }
    monkeypatch.setattr(
        module,
        "_execution_git_binding",
        lambda: (
            dict(binding),
            {
                "model_manifest": manifest_payload,
                "development_registry": registry_payload,
            },
        ),
    )

    monkeypatch.setattr(sys, "argv", _argv(cache, snapshot, first_output))
    assert module.main() == 0
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", _argv(cache, snapshot, second_output))
    assert module.main() == 0
    capsys.readouterr()

    first = json.loads(first_output.read_text(encoding="utf-8"))
    second = json.loads(second_output.read_text(encoding="utf-8"))
    unhashed = dict(first)
    recorded = unhashed.pop("output_sha256")
    assert recorded == canonical_json_sha256(unhashed)
    assert first == second
    assert first["summary"] == {
        "candidate_count": 48,
        "failure_count": 0,
        "form_count": 24,
        "item_count": 12,
        "max_continuation_tokens": first["summary"]["max_continuation_tokens"],
        "max_full_tokens": first["summary"]["max_full_tokens"],
        "max_within_form_token_difference": first["summary"][
            "max_within_form_token_difference"
        ],
    }
    assert first["tokenizer"]["name_or_path"].endswith("@" + REVISION)
    assert first["model_weights_deserialized"] is False
    assert first["model_weight_bytes_verified"] == 123
    assert first["network_observation"] == "not-instrumented"
    assert first["offline_enforcement"]["local_files_only"] is True
    needles = {str(tmp_path).casefold(), tmp_path.as_posix().casefold()}
    assert all(
        all(needle not in value.casefold() for needle in needles)
        for value in _all_strings(first)
    )


def test_recursive_path_check_detects_windows_style_string(tmp_path: Path) -> None:
    report = {"nested": [{"leak": str(tmp_path / "cache")}]}
    values = list(_all_strings(report))

    assert any(str(tmp_path).casefold() in value.casefold() for value in values)


@pytest.mark.parametrize("changed", ["head", "registry-bytes"])
def test_execute_rebinds_head_and_canonical_inputs_before_publication(
    changed: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    cache = tmp_path / "cache"
    snapshot = cache / "snapshot"
    snapshot.mkdir(parents=True)
    output = tmp_path / "must-not-publish.json"
    manifest_payload = module.DEFAULT_MANIFEST.read_bytes()
    registry_payload = module.DEFAULT_REGISTRY.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    monkeypatch.setattr(
        module,
        "load_manifest_tokenizer",
        lambda *_args, **_kwargs: _loaded(manifest_sha256),
    )
    binding = {
        "git_head": "e" * 40,
        "worktree_clean": True,
        "model_manifest_git_blob": "f" * 40,
        "development_registry_git_blob": "1" * 40,
    }
    payloads = {
        "model_manifest": manifest_payload,
        "development_registry": registry_payload,
    }
    final_binding = dict(binding)
    final_payloads = dict(payloads)
    if changed == "head":
        final_binding["git_head"] = "d" * 40
    else:
        final_payloads["development_registry"] = registry_payload + b" "
    observations = iter(
        [
            (dict(binding), dict(payloads)),
            (final_binding, final_payloads),
        ]
    )
    monkeypatch.setattr(
        module,
        "_execution_git_binding",
        lambda: next(observations),
    )
    monkeypatch.setattr(sys, "argv", _argv(cache, snapshot, output))

    assert module.main() == 1
    assert not output.exists()


def test_output_overwrite_is_rejected_before_any_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    output = tmp_path / "existing.json"
    output.write_text("sentinel", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "load_model_manifest",
        lambda *_args: (_ for _ in ()).throw(AssertionError("work was reached")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--artifact",
            "pythia-1b-deduped-main",
            "--prefix-policy",
            "none",
            "--output",
            str(output),
        ],
    )

    assert module.main() == 2
    assert output.read_text(encoding="utf-8") == "sentinel"


@pytest.mark.parametrize("kind", ["manifest", "registry"])
def test_execute_rejects_noncanonical_inputs_before_loader(
    kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    cache = tmp_path / "cache"
    snapshot = cache / "snapshot"
    snapshot.mkdir(parents=True)
    source = (
        module.DEFAULT_MANIFEST
        if kind == "manifest"
        else module.DEFAULT_REGISTRY
    )
    copied_input = tmp_path / source.name
    shutil.copyfile(source, copied_input)
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        module,
        "load_manifest_tokenizer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("tokenizer loader was reached")
        ),
    )
    monkeypatch.setattr(
        module,
        "load_model_manifest",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("manifest loader was reached")
        ),
    )
    monkeypatch.setattr(
        module,
        "load_evaluation_registry",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("registry loader was reached")
        ),
    )
    monkeypatch.setattr(
        module,
        "audit_evaluation_tokenizer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("tokenizer audit was reached")
        ),
    )
    argv = _argv(cache, snapshot, output)
    argv.extend([f"--{kind}", str(copied_input)])
    monkeypatch.setattr(sys, "argv", argv)

    assert module.main() == 1
    assert not output.exists()


def test_execute_rejects_prefix_policy_outside_manifest_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    cache = tmp_path / "cache"
    snapshot = cache / "snapshot"
    snapshot.mkdir(parents=True)
    output = tmp_path / "bos.json"
    manifest_payload = module.DEFAULT_MANIFEST.read_bytes()
    registry_payload = module.DEFAULT_REGISTRY.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    monkeypatch.setattr(
        module,
        "load_manifest_tokenizer",
        lambda *_args, **_kwargs: _loaded(manifest_sha256),
    )
    monkeypatch.setattr(
        module,
        "audit_evaluation_tokenizer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("tokenizer audit was reached")
        ),
    )
    monkeypatch.setattr(
        module,
        "_execution_git_binding",
        lambda: (
            {
                "git_head": "e" * 40,
                "worktree_clean": True,
                "model_manifest_git_blob": "f" * 40,
                "development_registry_git_blob": "1" * 40,
            },
            {
                "model_manifest": manifest_payload,
                "development_registry": registry_payload,
            },
        ),
    )
    argv = _argv(cache, snapshot, output)
    argv[argv.index("none")] = "bos"
    monkeypatch.setattr(sys, "argv", argv)

    assert module.main() == 1
    assert not output.exists()
