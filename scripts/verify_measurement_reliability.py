#!/usr/bin/env python3
"""Verify the frozen development-v1 measurement-coherence contract."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chronopersona.evaluation import (  # noqa: E402
    canonical_json_sha256,
    load_evaluation_registry_with_sha256,
)
from chronopersona.measurement_reliability import (  # noqa: E402
    MeasurementReliabilityError,
    analyze_score_repeat,
    load_json_artifact,
    load_reliability_criteria,
    validate_registry_against_criteria,
    validate_tokenizer_audit_against_criteria,
)
from chronopersona.scoring_runtime import (  # noqa: E402
    create_only_json,
    pretty_json_bytes,
)


DEFAULT_CRITERIA = (
    ROOT
    / "configs"
    / "evaluations"
    / "development-v1-reliability-v0.json"
)
DEFAULT_REGISTRY = ROOT / "evaluations" / "registry" / "development-v1.jsonl"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dependency-light verification for the frozen development-v1 "
            "registry, tokenizer evidence, or score coherence."
        )
    )
    parser.add_argument(
        "mode",
        choices=("registry", "tokenizer", "score"),
    )
    parser.add_argument("--criteria", type=Path, default=DEFAULT_CRITERIA)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--tokenizer-audit", type=Path)
    parser.add_argument("--tokenizer-audit-b", type=Path)
    parser.add_argument("--score-a", type=Path)
    parser.add_argument("--score-b", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _base_report(criteria: dict, registry_sha256: str) -> dict:
    return {
        "schema_version": 1,
        "report_type": "development-measurement-reliability-verification",
        "profile_id": criteria["profile_id"],
        "criteria_sha256": criteria["criteria_sha256"],
        "registry_sha256": registry_sha256,
        "claim_ceiling": criteria["claim_ceiling"],
    }


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise MeasurementReliabilityError(
            f"git {' '.join(arguments)} failed: {detail}"
        )
    return completed.stdout.strip()


def _verification_git_head(criteria_path: Path, registry_path: Path) -> str:
    if criteria_path.resolve(strict=True) != DEFAULT_CRITERIA.resolve(strict=True):
        raise MeasurementReliabilityError(
            "verification requires the canonical reliability criteria"
        )
    if registry_path.resolve(strict=True) != DEFAULT_REGISTRY.resolve(strict=True):
        raise MeasurementReliabilityError(
            "verification requires the canonical development-v1 registry"
        )
    head = _git("rev-parse", "HEAD")
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise MeasurementReliabilityError(
            "verification requires a clean exact Git head"
        )
    for path in (DEFAULT_CRITERIA, DEFAULT_REGISTRY):
        relative = path.relative_to(ROOT).as_posix()
        head_blob = _git("rev-parse", f"{head}:{relative}")
        worktree_blob = _git("hash-object", relative)
        if worktree_blob != head_blob:
            raise MeasurementReliabilityError(
                f"canonical input differs from tracked HEAD: {relative}"
            )
    if _git("rev-parse", "HEAD") != head:
        raise MeasurementReliabilityError("Git HEAD changed during verification")
    return head


def _same_file(left: Path, right: Path) -> bool:
    if left.resolve(strict=True) == right.resolve(strict=True):
        return True
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _audit_errors(
    audit: dict,
    payload: bytes,
    criteria: dict,
    items: list[dict],
    *,
    expected_git_head: str,
    label: str,
) -> list[str]:
    errors = list(
        validate_tokenizer_audit_against_criteria(
            audit,
            criteria,
            items,
            expected_git_head=expected_git_head,
        )
    )
    if payload != pretty_json_bytes(audit):
        errors.append(f"{label} bytes are not canonical pretty JSON")
    return list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        criteria = load_reliability_criteria(args.criteria)
        items, registry_sha256 = load_evaluation_registry_with_sha256(
            args.registry
        )
        expected_git_head = _verification_git_head(
            args.criteria,
            args.registry,
        )
        registry_errors = validate_registry_against_criteria(
            items,
            criteria,
            registry_sha256=registry_sha256,
        )
        report = _base_report(criteria, registry_sha256)
        report["git_head"] = expected_git_head
        report["worktree_clean"] = True
        report["mode"] = args.mode
        report["registry_validation"] = {
            "passed": not registry_errors,
            "errors": list(registry_errors),
        }
        errors = list(registry_errors)

        if args.mode == "tokenizer":
            if args.tokenizer_audit is None or args.tokenizer_audit_b is None:
                raise MeasurementReliabilityError(
                    "tokenizer mode requires --tokenizer-audit and "
                    "--tokenizer-audit-b"
                )
            if _same_file(args.tokenizer_audit, args.tokenizer_audit_b):
                raise MeasurementReliabilityError(
                    "tokenizer attempts must be distinct files"
                )
            audit_a, audit_a_bytes, audit_a_sha256 = load_json_artifact(
                args.tokenizer_audit,
                "tokenizer audit A",
            )
            audit_b, audit_b_bytes, audit_b_sha256 = load_json_artifact(
                args.tokenizer_audit_b,
                "tokenizer audit B",
            )
            audit_a_errors = _audit_errors(
                audit_a,
                audit_a_bytes,
                criteria,
                items,
                expected_git_head=expected_git_head,
                label="tokenizer audit A",
            )
            audit_b_errors = _audit_errors(
                audit_b,
                audit_b_bytes,
                criteria,
                items,
                expected_git_head=expected_git_head,
                label="tokenizer audit B",
            )
            tokenizer_errors = [
                *(f"attempt A: {error}" for error in audit_a_errors),
                *(f"attempt B: {error}" for error in audit_b_errors),
            ]
            byte_identical = audit_a_bytes == audit_b_bytes
            if not byte_identical:
                tokenizer_errors.append(
                    "tokenizer audit files are not byte-identical"
                )
            report["tokenizer_validation"] = {
                "attempt_a": {
                    "audit_output_sha256": audit_a.get("output_sha256"),
                    "file_sha256": audit_a_sha256,
                    "passed": not audit_a_errors,
                    "errors": audit_a_errors,
                },
                "attempt_b": {
                    "audit_output_sha256": audit_b.get("output_sha256"),
                    "file_sha256": audit_b_sha256,
                    "passed": not audit_b_errors,
                    "errors": audit_b_errors,
                },
                "byte_identical": byte_identical,
                "passed": not tokenizer_errors,
                "errors": tokenizer_errors,
            }
            errors.extend(tokenizer_errors)
        elif args.mode == "score":
            if (
                args.score_a is None
                or args.score_b is None
                or args.tokenizer_audit is None
            ):
                raise MeasurementReliabilityError(
                    "score mode requires --score-a, --score-b, and --tokenizer-audit"
                )
            audit, audit_bytes, audit_sha256 = load_json_artifact(
                args.tokenizer_audit,
                "tokenizer audit",
            )
            tokenizer_errors = _audit_errors(
                audit,
                audit_bytes,
                criteria,
                items,
                expected_git_head=expected_git_head,
                label="tokenizer audit",
            )
            report["tokenizer_validation"] = {
                "audit_output_sha256": audit.get("output_sha256"),
                "file_sha256": audit_sha256,
                "passed": not tokenizer_errors,
                "errors": tokenizer_errors,
            }
            errors.extend(tokenizer_errors)
            score_a, score_a_bytes, _ = load_json_artifact(
                args.score_a,
                "attempt A score artifact",
            )
            score_b, score_b_bytes, _ = load_json_artifact(
                args.score_b,
                "attempt B score artifact",
            )
            coherence = analyze_score_repeat(
                score_a,
                score_b,
                criteria,
                items,
                audit,
                score_a_bytes=score_a_bytes,
                score_b_bytes=score_b_bytes,
            )
            report["score_coherence"] = coherence
            if not coherence["passed"]:
                errors.append("score coherence failed")

        report["passed"] = not errors
        report["errors"] = list(dict.fromkeys(errors))
        report["output_sha256"] = canonical_json_sha256(report)
        create_only_json(args.output, report)
    except (
        MeasurementReliabilityError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"measurement reliability verification failed: {error}", file=sys.stderr)
        return 1
    print(f"measurement reliability verification passed={report['passed']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
