from copy import deepcopy
from pathlib import Path

from chronopersona.evaluation import (
    canonical_json_sha256,
    load_evaluation_registry,
    sha256_file,
)
from chronopersona.tokenizer_audit import (
    audit_evaluation_tokenizer,
    resolve_prefix_token_ids,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evaluations" / "registry" / "development-v0.jsonl"


class CharacterTokenizer:
    name_or_path = "character-fixture"
    vocab_size = 256
    model_max_length = 4096
    bos_token_id = 1
    eos_token_id = 2
    pad_token_id = None
    unk_token_id = None

    def encode(
        self,
        text: str,
        *,
        add_special_tokens: bool = False,
    ) -> list[int]:
        assert add_special_tokens is False
        return [ord(character) % 256 for character in text]


class AlternatingBoundaryTokenizer(CharacterTokenizer):
    def __init__(self) -> None:
        self.calls = 0

    def encode(
        self,
        text: str,
        *,
        add_special_tokens: bool = False,
    ) -> list[int]:
        self.calls += 1
        if self.calls % 2 == 1:
            return [1, 2, 3]
        return [9, 2, 3, 4]


def test_bos_prefix_policy_is_explicit() -> None:
    tokenizer = CharacterTokenizer()

    assert resolve_prefix_token_ids(tokenizer, "none") == ()
    assert resolve_prefix_token_ids(tokenizer, "bos") == (1,)


def test_committed_registry_passes_character_tokenizer_audit() -> None:
    items = load_evaluation_registry(REGISTRY)
    report = audit_evaluation_tokenizer(
        items,
        CharacterTokenizer(),
        registry_sha256=sha256_file(REGISTRY),
        artifact_id="character-fixture",
        artifact_revision="fixture-v1",
        prefix_policy="bos",
        max_length=2048,
    )

    assert report["passed"] is True
    assert report["summary"]["item_count"] == 12
    assert report["summary"]["form_count"] == 24
    assert report["summary"]["candidate_count"] == 48
    assert report["summary"]["failure_count"] == 0
    recorded_hash = report["output_sha256"]
    unhashed = deepcopy(report)
    unhashed.pop("output_sha256")
    assert recorded_hash == canonical_json_sha256(unhashed)


def test_boundary_failures_remain_visible() -> None:
    items = load_evaluation_registry(REGISTRY)[:1]
    report = audit_evaluation_tokenizer(
        items,
        AlternatingBoundaryTokenizer(),
        registry_sha256="fixture-registry",
        artifact_id="boundary-fixture",
        artifact_revision="fixture-v1",
        prefix_policy="none",
        max_length=2048,
    )

    assert report["passed"] is False
    assert report["summary"]["failure_count"] > 0
    assert any(
        failure["error_type"] == "ContinuationBoundaryError"
        for failure in report["failures"]
    )
