#!/usr/bin/env python3
"""Plan, execute, resume, or verify the no-model engineering smoke."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.run_registry import (  # noqa: E402
    RunRegistryError,
    atomic_write_json,
    read_json,
)
from chronopersona.smoke_pipeline import (  # noqa: E402
    SmokePipelineError,
    build_smoke_plan,
    resolve_git_commit,
    run_smoke_pipeline,
    verify_smoke_run,
)


DEFAULT_CONFIG = ROOT / "configs" / "runs" / "synthetic-fixture-smoke-v0.json"
DEFAULT_OUTPUT_ROOT = ROOT / "runs" / "synthetic-fixture-smoke-v0"
INTERRUPTED_EXIT_CODE = 75


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise run identity, checkpoint, resumption, and artifact "
            "verification without model loading, network access, or training."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--repo-root", type=Path, default=ROOT)
        subparser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
        subparser.add_argument(
            "--git-commit",
            help="override the repository HEAD used in immutable run identity",
        )
        subparser.add_argument("--result-output", type=Path)

    plan = subparsers.add_parser(
        "plan",
        help="validate inputs and print a no-write plan",
    )
    common(plan)

    run = subparsers.add_parser(
        "run",
        help="execute or explicitly resume the fixture smoke",
    )
    common(run)
    run.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    run.add_argument("--resume", action="store_true")
    run.add_argument(
        "--interrupt-after",
        type=int,
        help="test-only planned interruption after this many newly completed units",
    )

    verify = subparsers.add_parser(
        "verify",
        help="verify an existing run and all hashes",
    )
    verify.add_argument("--repo-root", type=Path, default=ROOT)
    verify.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    verify.add_argument("--run-root", type=Path, required=True)
    verify.add_argument("--allow-different-checkout", action="store_true")
    verify.add_argument("--result-output", type=Path)
    return parser


def _write_result(path: Path | None, value: object) -> None:
    if path is not None:
        atomic_write_json(path, value)


def _plan(args: argparse.Namespace):
    commit = args.git_commit or resolve_git_commit(args.repo_root)
    return build_smoke_plan(
        args.repo_root,
        args.config,
        git_commit=commit,
    )


def _verify_plan(args: argparse.Namespace):
    identity = read_json(args.run_root / "identity.json")
    if not isinstance(identity, dict):
        raise SmokePipelineError("run identity root must be an object")
    scientific = identity.get("scientific_identity")
    if not isinstance(scientific, dict):
        raise SmokePipelineError("scientific_identity must be an object")
    recorded_commit = scientific.get("git_commit")
    environment = scientific.get("environment")
    if not isinstance(recorded_commit, str) or not isinstance(environment, dict):
        raise SmokePipelineError(
            "run identity is missing Git commit or environment identity"
        )
    current_commit = resolve_git_commit(args.repo_root)
    if current_commit != recorded_commit and not args.allow_different_checkout:
        raise SmokePipelineError(
            "current checkout differs from the run identity; use the recorded "
            "commit or pass --allow-different-checkout for forensic verification"
        )
    plan = build_smoke_plan(
        args.repo_root,
        args.config,
        git_commit=recorded_commit,
        environment=environment,
    )
    if plan.identity != identity:
        raise SmokePipelineError(
            "current inputs do not reconstruct the stored immutable run identity"
        )
    return plan, current_commit


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "plan":
            plan = _plan(args)
            report = plan.plan
            exit_code = 0
        elif args.command == "run":
            plan = _plan(args)
            result = run_smoke_pipeline(
                plan,
                args.output_root,
                resume=args.resume,
                interrupt_after=args.interrupt_after,
            )
            report = {
                "schema_version": 1,
                "run_id": result.run_id,
                "run_root": str(result.run_root),
                "status": result.status,
                "completed_units": result.completed_units,
                "total_units": result.total_units,
                "final_manifest_sha256": (
                    result.final_manifest.get("final_manifest_sha256")
                    if result.final_manifest is not None
                    else None
                ),
                "training_performed": False,
                "model_loaded": False,
                "network_access_performed": False,
                "scientific_claim_authorized": False,
            }
            exit_code = (
                INTERRUPTED_EXIT_CODE
                if result.status == "interrupted"
                else 0
            )
        else:
            plan, current_commit = _verify_plan(args)
            report = verify_smoke_run(plan, args.run_root)
            report["current_git_commit"] = current_commit
            report["recorded_git_commit"] = plan.identity[
                "scientific_identity"
            ]["git_commit"]
            report["checkout_matches_identity"] = (
                report["current_git_commit"]
                == report["recorded_git_commit"]
            )
            exit_code = 0
    except (
        FileNotFoundError,
        OSError,
        RunRegistryError,
        SmokePipelineError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    _write_result(args.result_output, report)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
