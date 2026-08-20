import importlib.util
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
    module._verification_git_head = lambda _criteria, _registry: "a" * 40
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


def test_score_mode_preserves_pre_e3_receipt_blocker(tmp_path: Path) -> None:
    module = _module()
    fixtures = _fixture_module()
    criteria = fixtures._criteria()
    items = fixtures._registry()
    audit = fixtures._tokenizer_audit(criteria, items)
    score = fixtures._score(criteria, items, audit)
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

    report = json.loads(output.read_text(encoding="utf-8"))
    recorded = report.pop("output_sha256")
    assert recorded == canonical_json_sha256(report)
    assert report["passed"] is False
    assert report["score_coherence"]["passed"] is False
    assert report["score_coherence"]["failures"] == [
        "execution-order receipts are not integrated until E3"
    ]
