import importlib.util
import hashlib
import json
from pathlib import Path

from chronopersona.evaluation import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_measurement_reliability.py"
FIXTURES = ROOT / "tests" / "test_measurement_reliability.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "verify_measurement_reliability_test",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._verification_git_head = (
        lambda _criteria, _registry, _scoring_config=None: "a" * 40
    )
    return module


def _fixture_module():
    spec = importlib.util.spec_from_file_location(
        "measurement_reliability_fixtures",
        FIXTURES,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_mode_writes_create_only_self_hashed_report(
    tmp_path: Path,
) -> None:
    module = _module()
    output = tmp_path / "registry-report.json"

    assert module.main(["registry", "--output", str(output)]) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    recorded = report.pop("output_sha256")
    assert recorded == canonical_json_sha256(report)
    assert report["passed"] is True
    assert report["registry_validation"] == {
        "passed": True,
        "errors": [],
    }
    assert str(ROOT) not in json.dumps(report)


def test_registry_mode_refuses_overwrite(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "existing.json"
    output.write_text("sentinel", encoding="utf-8")

    assert module.main(["registry", "--output", str(output)]) == 1
    assert output.read_text(encoding="utf-8") == "sentinel"


def test_tokenizer_mode_requires_explicit_audit(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "missing.json"

    assert module.main(["tokenizer", "--output", str(output)]) == 1
    assert not output.exists()


def test_tokenizer_mode_accepts_complete_bound_audit(tmp_path: Path) -> None:
    module = _module()
    fixtures = _fixture_module()
    criteria = fixtures._criteria()
    items = fixtures._registry()
    audit = fixtures._tokenizer_audit(criteria, items)
    audit_path = tmp_path / "tokenizer-audit-a.json"
    audit_path_b = tmp_path / "tokenizer-audit-b.json"
    output = tmp_path / "tokenizer-verification.json"
    audit_path.write_bytes(fixtures._pretty_bytes(audit))
    audit_path_b.write_bytes(fixtures._pretty_bytes(audit))

    assert module.main(
        [
            "tokenizer",
            "--tokenizer-audit",
            str(audit_path),
            "--tokenizer-audit-b",
            str(audit_path_b),
            "--output",
            str(output),
        ]
    ) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    recorded = report.pop("output_sha256")
    assert recorded == canonical_json_sha256(report)
    assert report["passed"] is True
    assert report["tokenizer_validation"]["passed"] is True
    assert report["tokenizer_validation"]["byte_identical"] is True
    assert report["tokenizer_validation"]["attempt_a"]["file_sha256"] == (
        report["tokenizer_validation"]["attempt_b"]["file_sha256"]
    )


def test_tokenizer_mode_rejects_noncanonical_or_aliased_attempts(
    tmp_path: Path,
) -> None:
    module = _module()
    fixtures = _fixture_module()
    criteria = fixtures._criteria()
    items = fixtures._registry()
    audit = fixtures._tokenizer_audit(criteria, items)
    compact = tmp_path / "compact.json"
    canonical = tmp_path / "canonical.json"
    compact.write_text(
        json.dumps(audit, separators=(",", ":")),
        encoding="utf-8",
    )
    canonical.write_bytes(fixtures._pretty_bytes(audit))

    output = tmp_path / "noncanonical-report.json"
    assert module.main(
        [
            "tokenizer",
            "--tokenizer-audit",
            str(compact),
            "--tokenizer-audit-b",
            str(canonical),
            "--output",
            str(output),
        ]
    ) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert any(
        "bytes are not canonical pretty JSON" in error
        for error in report["tokenizer_validation"]["errors"]
    )

    alias_output = tmp_path / "alias-report.json"
    assert module.main(
        [
            "tokenizer",
            "--tokenizer-audit",
            str(canonical),
            "--tokenizer-audit-b",
            str(canonical),
            "--output",
            str(alias_output),
        ]
    ) == 1
    assert not alias_output.exists()


def test_score_mode_requires_complete_execution_evidence(tmp_path: Path) -> None:
    module = _module()
    fixtures = _fixture_module()
    criteria = fixtures._criteria()
    items = fixtures._registry()
    audit = fixtures._tokenizer_audit(criteria, items)
    score = fixtures._finalized_score(fixtures._score(criteria, items, audit))
    audit_path = tmp_path / "tokenizer-audit.json"
    score_a = tmp_path / "score-a.json"
    score_b = tmp_path / "score-b.json"
    output = tmp_path / "score-verification.json"
    audit_path.write_bytes(fixtures._pretty_bytes(audit))
    score_a.write_bytes(fixtures._pretty_bytes(score))
    score_b.write_bytes(fixtures._pretty_bytes(score))

    assert module.main(
        [
            "score",
            "--tokenizer-audit",
            str(audit_path),
            "--score-a",
            str(score_a),
            "--score-b",
            str(score_b),
            "--output",
            str(output),
        ]
    ) == 1

    assert not output.exists()


def test_score_mode_integrates_profile_bound_execution_comparison(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _module()
    fixtures = _fixture_module()
    criteria = fixtures._criteria()
    items = fixtures._registry()
    audit = fixtures._tokenizer_audit(criteria, items)
    score = fixtures._finalized_score(fixtures._score(criteria, items, audit))
    score_bytes = fixtures._pretty_bytes(score)
    audit_path = tmp_path / "accepted-tokenizer.json"
    score_a = tmp_path / "score-a.json"
    score_b = tmp_path / "score-b.json"
    receipt_a = tmp_path / "receipt-a.json"
    receipt_b = tmp_path / "receipt-b.json"
    resource_a = tmp_path / "resource-a.json"
    resource_b = tmp_path / "resource-b.json"
    output = tmp_path / "score-verification.json"
    audit_path.write_bytes(fixtures._pretty_bytes(audit))
    score_a.write_bytes(score_bytes)
    score_b.write_bytes(score_bytes)
    for path, marker in (
        (receipt_a, {"attempt": "a"}),
        (receipt_b, {"attempt": "b"}),
        (resource_a, {"attempt": "a", "kind": "resource"}),
        (resource_b, {"attempt": "b", "kind": "resource"}),
    ):
        path.write_bytes(module.pretty_json_bytes(marker))

    config = json.loads(module.DEFAULT_SCORING_CONFIG.read_text(encoding="utf-8"))
    config["accepted_tokenizer_audit"]["path"] = str(audit_path)
    config["measurement_reliability"]["tokenizer_audit_git_head"] = audit[
        "git_head"
    ]
    monkeypatch.setattr(module, "load_scoring_config", lambda _path: config)
    monkeypatch.setattr(
        module,
        "load_accepted_tokenizer_audit",
        lambda _path, _config: (audit, hashlib.sha256(audit_path.read_bytes()).hexdigest()),
    )

    comparison = {
        "status": "equal",
        "profile_id": criteria["profile_id"],
        "measurement_reliability_criteria_sha256": criteria[
            "criteria_sha256"
        ],
        "execution_modes": {"a": "canonical", "b": "reverse"},
        "score_file_sha256": hashlib.sha256(score_bytes).hexdigest(),
        "score_output_sha256": score["output_sha256"],
    }
    comparison["comparison_sha256"] = canonical_json_sha256(comparison)
    observed: dict[str, object] = {}

    def fake_repeat(**kwargs):
        observed.update(kwargs)
        return comparison

    monkeypatch.setattr(
        "chronopersona.measurement_reliability.verify_scoring_repeat",
        fake_repeat,
    )

    assert module.main(
        [
            "score",
            "--tokenizer-audit",
            str(audit_path),
            "--score-a",
            str(score_a),
            "--score-b",
            str(score_b),
            "--receipt-a",
            str(receipt_a),
            "--receipt-b",
            str(receipt_b),
            "--resource-audit-a",
            str(resource_a),
            "--resource-audit-b",
            str(resource_b),
            "--output",
            str(output),
        ]
    ) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["score_coherence"]["execution_mode_receipts_validated"] is True
    assert observed["expected_git_head"] == "a" * 40
    assert observed["config"] is config
