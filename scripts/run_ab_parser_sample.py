#!/usr/bin/env python3
"""Plan or execute the frozen synthetic-only A/B parser sample."""

from __future__ import annotations

import sys


if not (sys.flags.isolated and sys.flags.safe_path and sys.flags.no_site):
    try:
        sys.stdout.write(
            '{"failure_reason":"argument-contract-failed",'
            '"failure_stage":"arguments",'
            '"profile_id":"ab-parser-sample-v0",'
            '"schema_version":1,"status":"failed",'
            '"valid_evidence_published":false}\n'
        )
        sys.stdout.flush()
    except BaseException:
        pass
    raise SystemExit(2)

sys.dont_write_bytecode = True

import argparse
import importlib
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]
sys.pycache_prefix = str(
    ROOT
    / "artifacts"
    / "local"
    / f"chronopersona-ab-parser-no-bytecode-{secrets.token_hex(16)}"
)
sys.path.append(str(ROOT / "src"))

try:
    import chronopersona.ab_parser_sample as gate  # noqa: E402
except BaseException:
    try:
        sys.stdout.write(
            '{"failure_reason":"binding-failed",'
            '"failure_stage":"binding",'
            '"profile_id":"ab-parser-sample-v0",'
            '"schema_version":1,"status":"failed",'
            '"valid_evidence_published":false}\n'
        )
        sys.stdout.flush()
    except BaseException:
        pass
    raise SystemExit(2)


class _ClosedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise gate.ABParserError(
            "arguments",
            "argument-contract-failed",
            "command-line arguments do not match the frozen interface",
        )


def _parser() -> argparse.ArgumentParser:
    parser = _ClosedArgumentParser(
        add_help=False,
        description=(
            "Validate the frozen synthetic A/B parser bundle. Default mode "
            "is read-only planning; live/source/network input is unavailable."
        )
    )
    parser.add_argument("--execute-fixture", action="store_true")
    parser.add_argument("--expected-git-head")
    parser.add_argument(
        "--run-dir",
        help="canonical ignored path artifacts/local/ab-parser-sample/<run-name>",
    )
    return parser


def _plan(profile: dict) -> dict:
    return {
        "schema_version": 1,
        "mode": "plan",
        "profile_id": profile["profile_id"],
        "profile_path": gate.PROFILE_RELATIVE_PATH,
        "synthetic_fixture_only": True,
        "network_access_permitted": False,
        "live_source_access_permitted": False,
        "filesystem_writes_performed": False,
        "selection_count": len(profile["fixture_bundle"]["selection_order"]),
        "external_spend_cad": 0,
        "claim_ceiling": profile["claim_ceiling"],
    }


def _terminal(payload: dict) -> bool:
    try:
        sys.stdout.write(gate.canonical_json_bytes(payload).decode("utf-8") + "\n")
        sys.stdout.flush()
        return True
    except BaseException:
        # Once evidence has committed, terminal reporting cannot alter its
        # artifact state, but the process must not claim successful delivery.
        return False


def _runtime_modules() -> dict[str, str | Path | None]:
    modules = {
        "src/chronopersona/__init__.py": "chronopersona",
        "src/chronopersona/file_integrity.py": "chronopersona.file_integrity",
        "src/chronopersona/path_policy.py": "chronopersona.path_policy",
        "src/chronopersona/content_manifest.py": "chronopersona.content_manifest",
        "src/chronopersona/source_registry.py": "chronopersona.source_registry",
        "src/chronopersona/source_audit.py": "chronopersona.source_audit",
        "src/chronopersona/ab_parser_common.py": "chronopersona.ab_parser_common",
        "src/chronopersona/wikimedia_ab_parser.py": (
            "chronopersona.wikimedia_ab_parser"
        ),
        "src/chronopersona/stackexchange_ab_parser.py": (
            "chronopersona.stackexchange_ab_parser"
        ),
        "src/chronopersona/ab_parser_sample.py": "chronopersona.ab_parser_sample",
    }
    observed: dict[str, str | Path | None] = {
        "scripts/run_ab_parser_sample.py": Path(__file__)
    }
    for relative, module_name in modules.items():
        module = gate if module_name == "chronopersona.ab_parser_sample" else importlib.import_module(module_name)
        observed[relative] = module.__file__
    return observed


def _argument_contract(args: argparse.Namespace) -> None:
    supplied = (args.expected_git_head is not None, args.run_dir is not None)
    if not args.execute_fixture and any(supplied):
        raise gate.ABParserError(
            "arguments",
            "argument-contract-failed",
            "execution-only arguments require --execute-fixture",
        )
    if args.execute_fixture and not all(supplied):
        raise gate.ABParserError(
            "arguments",
            "argument-contract-failed",
            "fixture execution requires exact head and run directory",
        )


def _execute(args: argparse.Namespace) -> int:
    assert args.expected_git_head is not None
    assert args.run_dir is not None
    if sys.version_info < (3, 11):
        raise gate.ABParserError(
            "arguments",
            "argument-contract-failed",
            "fixture execution requires Python 3.11 or later",
        )
    bound = gate.bind_fixture_inputs(ROOT, expected_head=args.expected_git_head)
    observed = _runtime_modules()
    gate.verify_runtime_module_paths(ROOT, observed=observed, bound=bound)
    gate.rebind_fixture_inputs(ROOT, bound)
    run_dir = gate.prepare_output_run(ROOT, run_dir=args.run_dir)
    publication = bound.profile["publication"]
    leaves = (
        publication["private_records_file"],
        publication["aggregate_file"],
        publication["receipt_file"],
    )
    transaction = gate.ExactArtifactTransaction(
        run_dir,
        leaves,
        max_artifact_bytes=max(
            bound.profile["limits"]["max_private_output_bytes"],
            bound.profile["limits"]["max_aggregate_output_bytes"],
            bound.profile["limits"]["max_receipt_output_bytes"],
        ),
    )
    try:
        parsed = gate.parse_fixture_bundle(bound)
        artifacts = gate.build_success_artifacts(bound, parsed)
        gate.rebind_fixture_inputs(ROOT, bound)
    except BaseException as error:
        if isinstance(error, gate.ABParserError):
            stage = error.stage
            reason = error.reason
        elif isinstance(error, (KeyboardInterrupt, SystemExit)):
            stage = "validation"
            reason = "interrupted"
        else:
            stage = "validation"
            reason = "validation-failed"
        try:
            if stage == "rebind":
                raise gate.ABParserError(stage, reason, "final rebind failed")
            gate.rebind_fixture_inputs(ROOT, bound)
            failure_artifacts = gate.build_failure_artifacts(
                bound, stage=stage, reason=reason
            )
            published = transaction.publish(failure_artifacts)
        except BaseException:
            transaction.rollback()
            delivered = _terminal(
                {
                    "schema_version": 1,
                    "status": "failed",
                    "profile_id": gate.PROFILE_ID,
                    "failure_stage": "publication" if stage != "rebind" else "rebind",
                    "failure_reason": "publication-failed" if stage != "rebind" else "rebind-failed",
                    "valid_evidence_published": False,
                }
            )
            return 2 if delivered else 3
        delivered = _terminal(
            {
                "schema_version": 1,
                "status": "failed",
                "profile_id": gate.PROFILE_ID,
                "failure_stage": stage,
                "failure_reason": reason,
                "valid_evidence_published": True,
                "artifact_count": len(published),
            }
        )
        try:
            released = transaction.release_committed()
        except BaseException:
            released = False
        return 2 if delivered and released else 3
    try:
        published = transaction.publish(artifacts)
    except BaseException:
        transaction.rollback()
        delivered = _terminal(
            {
                "schema_version": 1,
                "status": "failed",
                "profile_id": gate.PROFILE_ID,
                "failure_stage": "publication",
                "failure_reason": "publication-failed",
                "valid_evidence_published": False,
            }
        )
        return 2 if delivered else 3
    delivered = _terminal(
        {
            "schema_version": 1,
            "status": "complete",
            "profile_id": gate.PROFILE_ID,
            "valid_evidence_published": True,
            "artifact_count": len(published),
            "selection_count": len(bound.profile["fixture_bundle"]["selection_order"]),
            "claim_ceiling": bound.profile["claim_ceiling"],
        }
    )
    try:
        released = transaction.release_committed()
    except BaseException:
        released = False
    return 0 if delivered and released else 3


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        _argument_contract(args)
        if not args.execute_fixture:
            return 0 if _terminal(_plan(gate.load_profile_for_plan(ROOT))) else 3
        return _execute(args)
    except gate.ABParserError as error:
        delivered = _terminal(
            {
                "schema_version": 1,
                "status": "failed",
                "profile_id": gate.PROFILE_ID,
                "failure_stage": error.stage,
                "failure_reason": error.reason,
                "valid_evidence_published": False,
            }
        )
        return 2 if delivered else 3
    except BaseException as error:
        delivered = _terminal(
            {
                "schema_version": 1,
                "status": "failed",
                "profile_id": gate.PROFILE_ID,
                "failure_stage": "validation",
                "failure_reason": (
                    "interrupted"
                    if isinstance(error, (KeyboardInterrupt, SystemExit))
                    else "validation-failed"
                ),
                "valid_evidence_published": False,
            }
        )
        return 2 if delivered else 3


if __name__ == "__main__":
    raise SystemExit(main())
