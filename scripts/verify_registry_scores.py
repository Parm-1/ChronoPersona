#!/usr/bin/env python3
"""Verify two frozen registry-score attempts without loading a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "runs" / "pythia-development-score-v0.json"
DEFAULT_REGISTRY = ROOT / "evaluations" / "registry" / "development-v0.jsonl"
sys.path.insert(0, str(ROOT / "src"))

import audit_registry_tokenizer as tokenizer_cli  # noqa: E402
import score_registry_transformers as scoring_cli  # noqa: E402

from chronopersona.scoring_runtime import (  # noqa: E402
    FROZEN_CONFIG_GIT_BLOB,
    ScoringRunError,
    create_only_json,
    load_accepted_tokenizer_audit,
    load_json_object,
    load_scoring_config,
    verify_scoring_repeat,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Require exact score-byte equality and valid runtime receipts."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--score-a", type=Path, required=True)
    parser.add_argument("--receipt-a", type=Path, required=True)
    parser.add_argument("--resource-audit-a", type=Path, required=True)
    parser.add_argument("--score-b", type=Path, required=True)
    parser.add_argument("--receipt-b", type=Path, required=True)
    parser.add_argument("--resource-audit-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _require_distinct_inputs(paths: tuple[tuple[str, Path], ...]) -> None:
    for label, path in paths:
        scoring_cli._require_output_location(
            path,
            cache_dir=None,
            snapshot_path=None,
            label=f"verification {label}",
        )
        info = os.lstat(path)
        if (
            not scoring_cli.stat.S_ISREG(info.st_mode)
            or scoring_cli.stat.S_ISLNK(info.st_mode)
            or bool(
                getattr(info, "st_file_attributes", 0)
                & getattr(scoring_cli.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
            )
        ):
            raise ScoringRunError(f"verification {label} is not a plain file")
    for index, (left_label, left) in enumerate(paths):
        left_resolved = left.resolve(strict=True)
        for right_label, right in paths[index + 1 :]:
            right_resolved = right.resolve(strict=True)
            if left_resolved == right_resolved or os.path.samefile(left, right):
                raise ScoringRunError(
                    f"verification inputs must be distinct files: "
                    f"{left_label}/{right_label}"
                )


def _require_clean_exact_head(expected: str | None = None) -> str:
    observed = tokenizer_cli._git("rev-parse", "HEAD")
    if expected is not None and observed != expected:
        raise ScoringRunError("Git HEAD changed during repeat verification")
    if tokenizer_cli._git("status", "--porcelain", "--untracked-files=all"):
        raise ScoringRunError(
            "repeat verification requires a clean exact-head worktree"
        )
    return observed


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.config.resolve(strict=True) != DEFAULT_CONFIG.resolve(strict=True):
        print("error: verification requires the canonical scoring config", file=sys.stderr)
        return 2
    if os.path.lexists(args.output):
        print(f"error: refusing to overwrite output: {args.output}", file=sys.stderr)
        return 2
    try:
        scoring_cli._require_output_location(
            args.output,
            cache_dir=None,
            snapshot_path=None,
            label="comparison output",
        )
        observed_config_blob = tokenizer_cli._git(
            "hash-object",
            "--path=configs/runs/pythia-development-score-v0.json",
            str(DEFAULT_CONFIG),
        )
        if observed_config_blob != FROZEN_CONFIG_GIT_BLOB:
            raise ScoringRunError("canonical scoring config Git blob mismatch")
        expected_git_head = _require_clean_exact_head()
        config = load_scoring_config(args.config)
        registry_bytes = DEFAULT_REGISTRY.read_bytes()
        if hashlib.sha256(registry_bytes).hexdigest() != config[
            "canonical_inputs"
        ]["registry_sha256"]:
            raise ScoringRunError("canonical registry byte identity mismatch")
        registry = tokenizer_cli._registry_from_bytes(registry_bytes)
        tokenizer_audit, _ = load_accepted_tokenizer_audit(
            ROOT / config["accepted_tokenizer_audit"]["path"],
            config,
        )
        _require_distinct_inputs(
            (
                ("score A", args.score_a),
                ("receipt A", args.receipt_a),
                ("resource audit A", args.resource_audit_a),
                ("score B", args.score_b),
                ("receipt B", args.receipt_b),
                ("resource audit B", args.resource_audit_b),
            )
        )
        score_a, score_a_bytes = load_json_object(args.score_a, "score A")
        receipt_a, receipt_a_bytes = load_json_object(args.receipt_a, "receipt A")
        resource_audit_a, resource_audit_a_bytes = load_json_object(
            args.resource_audit_a,
            "resource audit A",
        )
        score_b, score_b_bytes = load_json_object(args.score_b, "score B")
        receipt_b, receipt_b_bytes = load_json_object(args.receipt_b, "receipt B")
        resource_audit_b, resource_audit_b_bytes = load_json_object(
            args.resource_audit_b,
            "resource audit B",
        )
        result = verify_scoring_repeat(
            score_a=score_a,
            score_a_bytes=score_a_bytes,
            receipt_a=receipt_a,
            receipt_a_bytes=receipt_a_bytes,
            resource_audit_a=resource_audit_a,
            resource_audit_a_bytes=resource_audit_a_bytes,
            score_b=score_b,
            score_b_bytes=score_b_bytes,
            receipt_b=receipt_b,
            receipt_b_bytes=receipt_b_bytes,
            resource_audit_b=resource_audit_b,
            resource_audit_b_bytes=resource_audit_b_bytes,
            config=config,
            registry=registry,
            tokenizer_audit=tokenizer_audit,
            expected_git_head=expected_git_head,
        )
        _require_clean_exact_head(expected_git_head)
        create_only_json(args.output, result)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
