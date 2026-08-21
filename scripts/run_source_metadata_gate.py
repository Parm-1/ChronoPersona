#!/usr/bin/env python3
"""Plan or execute the frozen, bounded live source-metadata qualification."""

from __future__ import annotations

import sys


if not (
    sys.flags.isolated
    and sys.flags.safe_path
    and sys.flags.no_site
):
    raise SystemExit(
        "source metadata gate requires isolated startup: "
        "python -I -S scripts/run_source_metadata_gate.py"
    )

sys.dont_write_bytecode = True

import argparse
import importlib
import json
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]
sys.pycache_prefix = str(
    ROOT
    / "artifacts"
    / "local"
    / f"chronopersona-source-gate-no-bytecode-{secrets.token_hex(16)}"
)
# Isolated/no-site startup leaves only trusted standard-library locations on
# sys.path. Append (rather than prepend) the exact repository source root so a
# repo-local stdlib lookalike cannot win module resolution.
sys.path.append(str(ROOT / "src"))

import chronopersona.source_audit as source_audit_module  # noqa: E402
from chronopersona.source_audit import (  # noqa: E402
    PROFILE_RELATIVE_PATH,
    RUNTIME_RELATIVE_PATHS,
    SourceAuditError,
    SourceOutputReservation,
    bind_source_inputs,
    canonical_json_bytes,
    load_profile_for_plan,
    load_private_commitment_key,
    prepare_output_roots,
    rebind_source_inputs,
    verify_runtime_module_paths,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the exact frozen source-metadata qualification. Default mode "
            "is planning only and performs no network or filesystem writes."
        )
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--expected-git-head")
    parser.add_argument(
        "--run-dir",
        help=(
            "canonical ignored path artifacts/local/source-audit/<run-name>"
        ),
    )
    parser.add_argument("--private-backup-dir", type=Path)
    parser.add_argument("--private-commitment-key-file", type=Path)
    parser.add_argument("--private-commitment-key-backup-file", type=Path)
    return parser


def _plan(profile: dict) -> dict:
    return {
        "schema_version": 1,
        "mode": "plan",
        "profile_id": profile["profile_id"],
        "profile_path": PROFILE_RELATIVE_PATH,
        "network_access_permitted": False,
        "filesystem_writes_performed": False,
        "group_order": profile["group_order"],
        "maximum_happy_path_requests": profile["network"][
            "maximum_happy_path_requests"
        ],
        "external_spend_cad": 0,
        "claim_ceiling": profile["claim_ceiling"],
    }


def _runtime_modules(gate_module, network_module) -> dict[str, str | Path]:
    module_names = {
        "src/chronopersona/__init__.py": "chronopersona",
        "src/chronopersona/file_integrity.py": "chronopersona.file_integrity",
        "src/chronopersona/path_policy.py": "chronopersona.path_policy",
        "src/chronopersona/source_audit.py": "chronopersona.source_audit",
        "src/chronopersona/source_inventory.py": "chronopersona.source_inventory",
        "src/chronopersona/source_metadata.py": "chronopersona.source_metadata",
        "src/chronopersona/source_metadata_gate.py": (
            "chronopersona.source_metadata_gate"
        ),
        "src/chronopersona/source_registry.py": "chronopersona.source_registry",
        "src/chronopersona/source_adapters/__init__.py": (
            "chronopersona.source_adapters"
        ),
        "src/chronopersona/source_adapters/arxiv_api.py": (
            "chronopersona.source_adapters.arxiv_api"
        ),
        "src/chronopersona/source_adapters/arxiv_oai.py": (
            "chronopersona.source_adapters.arxiv_oai"
        ),
        "src/chronopersona/source_adapters/network.py": (
            "chronopersona.source_adapters.network"
        ),
        "src/chronopersona/source_adapters/pmc_oai.py": (
            "chronopersona.source_adapters.pmc_oai"
        ),
        "src/chronopersona/source_adapters/stackexchange_inventory.py": (
            "chronopersona.source_adapters.stackexchange_inventory"
        ),
        "src/chronopersona/source_adapters/wikimedia_inventory.py": (
            "chronopersona.source_adapters.wikimedia_inventory"
        ),
    }
    observed: dict[str, str | Path] = {
        "scripts/run_source_metadata_gate.py": Path(__file__),
    }
    for relative, module_name in module_names.items():
        if module_name == "chronopersona.source_audit":
            module = source_audit_module
        elif module_name == "chronopersona.source_metadata_gate":
            module = gate_module
        elif module_name == "chronopersona.source_adapters.network":
            module = network_module
        else:
            module = importlib.import_module(module_name)
        observed[relative] = module.__file__
    if tuple(observed) != RUNTIME_RELATIVE_PATHS:
        raise SourceAuditError("runtime module enumeration drifted")
    return observed


def _execution_arguments(args: argparse.Namespace) -> None:
    supplied = (
        args.expected_git_head is not None,
        args.run_dir is not None,
        args.private_backup_dir is not None,
        args.private_commitment_key_file is not None,
        args.private_commitment_key_backup_file is not None,
    )
    if args.allow_network and not args.execute:
        raise SourceAuditError("--allow-network is meaningful only with --execute")
    if not args.execute and any(supplied):
        raise SourceAuditError("execution-only paths and head require --execute")
    if args.execute and not args.allow_network:
        raise SourceAuditError("live execution requires --allow-network")
    if args.execute and not all(supplied):
        raise SourceAuditError(
            "live execution requires --expected-git-head, --run-dir, and "
            "--private-backup-dir plus both private commitment-key copies"
        )


def _execute(args: argparse.Namespace) -> int:
    assert args.expected_git_head is not None
    assert args.run_dir is not None
    assert args.private_backup_dir is not None
    assert args.private_commitment_key_file is not None
    assert args.private_commitment_key_backup_file is not None

    if sys.version_info < (3, 11):
        raise SourceAuditError("live metadata execution requires Python 3.11 or later")

    bound = bind_source_inputs(ROOT, expected_head=args.expected_git_head)
    profile = bound.values["metadata_gate_profile"]
    commitment_key = load_private_commitment_key(
        ROOT,
        primary_path=args.private_commitment_key_file,
        backup_path=args.private_commitment_key_backup_file,
        expected_sha256=profile["privacy"]["commitment_key_sha256"],
    )

    # Parser/orchestrator imports occur only after the exact source inputs and
    # runtime bytes are clean-head bound. The network module remains unimported.
    gate_module = importlib.import_module("chronopersona.source_metadata_gate")
    publication = profile["publication"]
    roots = prepare_output_roots(
        ROOT,
        run_dir=args.run_dir,
        backup_dir=args.private_backup_dir,
    )
    file_names = [
        *publication["private_artifact_files"],
        publication["aggregate_file"],
        publication["receipt_file"],
    ]
    reservation = SourceOutputReservation(roots, file_names)
    context = gate_module.GateContext(
        bound=bound,
        reservation=reservation,
        profile=profile,
        windows=gate_module.parse_era_windows(bound.values["source_registry"]),
        commitment_key=commitment_key,
    )
    primary_failure = None
    phase = "preflight-runtime-binding"
    try:
        # Reservation creation is allowed to dirty only ignored output paths.
        # Rebind before importing any network implementation.
        rebind_source_inputs(ROOT, bound)
        network_module = importlib.import_module(
            "chronopersona.source_adapters.network"
        )
        verify_runtime_module_paths(
            ROOT,
            _runtime_modules(gate_module, network_module),
            bound,
        )
        rebind_source_inputs(ROOT, bound)
        phase = "group-execution"
        context = gate_module.run_gate(
            bound,
            reservation,
            network_module.fetch_metadata_response,
            commitment_key=commitment_key,
            context=context,
        )
        phase = "post-run-integrity"
        try:
            rebind_source_inputs(ROOT, bound)
        except BaseException as error:
            raise gate_module.SourceGateError(
                group="post-run",
                stage="final-integrity-rebind",
                reason_code="final-integrity-rebind-failed",
                request_ordinal=None,
                detail=error,
                context=context,
            ) from error

        aggregate = gate_module.success_aggregate(context)
        aggregate_errors = gate_module.validate_aggregate(
            aggregate,
            expected_bindings=bound.bindings,
        )
        if aggregate_errors:
            raise SourceAuditError("; ".join(aggregate_errors))
        aggregate_payload = canonical_json_bytes(aggregate, pretty=True)
        receipt = gate_module.success_receipt(
            context,
            aggregate_payload=aggregate_payload,
            final_binding_status="matched",
        )
        receipt_errors = gate_module.validate_receipt(
            receipt,
            expected_bindings=bound.bindings,
            aggregate_payload=aggregate_payload,
            commitment_key=commitment_key,
        )
        if receipt_errors:
            raise SourceAuditError("; ".join(receipt_errors))
        receipt_payload = canonical_json_bytes(receipt, pretty=True)
        phase = "output-publication"
        reservation.publish_success(
            private_files=publication["private_artifact_files"],
            aggregate_file=publication["aggregate_file"],
            aggregate_payload=aggregate_payload,
            receipt_file=publication["receipt_file"],
            receipt_payload=receipt_payload,
        )
        try:
            print(
                json.dumps(
                    {
                        "status": "success",
                        "profile_id": profile["profile_id"],
                        "git_head": bound.head,
                        "request_attempt_count": context.request_attempt_count,
                        "receipt_sha256": receipt["receipt_sha256"],
                    },
                    sort_keys=True,
                )
            )
        except BaseException:
            # The create-only evidence bundle is already committed. Terminal
            # reporting cannot retroactively turn it into failed evidence.
            pass
        return 0
    except BaseException as error:
        if isinstance(error, gate_module.SourceGateError):
            failure = error
            if error.context is not None:
                context = error.context
        else:
            if phase == "output-publication":
                group = "publication"
                reason_code = "output-publication-failed"
            elif phase.startswith("post-run"):
                group = "post-run"
                reason_code = (
                    "execution-interrupted"
                    if isinstance(error, KeyboardInterrupt)
                    else (
                        "contract-validation-failed"
                        if isinstance(error, SourceAuditError)
                        else "unexpected-execution-failure"
                    )
                )
            else:
                group = "preflight"
                reason_code = (
                    "execution-interrupted"
                    if isinstance(error, KeyboardInterrupt)
                    else (
                        "contract-validation-failed"
                        if isinstance(error, SourceAuditError)
                        else "unexpected-execution-failure"
                    )
                )
            failure = gate_module.SourceGateError(
                group=group,
                stage=phase,
                reason_code=reason_code,
                request_ordinal=None,
                detail=error,
                context=context,
            )
        primary_failure = failure

    final_binding_status = "matched"
    try:
        rebind_source_inputs(ROOT, bound)
    except BaseException:
        final_binding_status = "failed"
    failure_receipt = gate_module.failure_receipt(
        context,
        primary_failure,
        final_binding_status=final_binding_status,
    )
    failure_errors = gate_module.validate_receipt(
        failure_receipt,
        expected_bindings=bound.bindings,
        commitment_key=commitment_key,
    )
    if failure_errors:
        reservation.rollback()
        raise SourceAuditError("cannot publish valid failure receipt: " + "; ".join(failure_errors))
    failure_payload = canonical_json_bytes(failure_receipt, pretty=True)
    try:
        reservation.publish_failure(
            private_files=publication["private_artifact_files"],
            aggregate_file=publication["aggregate_file"],
            receipt_file=publication["receipt_file"],
            receipt_payload=failure_payload,
        )
    except BaseException:
        try:
            reservation.rollback()
        except BaseException:
            pass
        raise
    try:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "profile_id": profile["profile_id"],
                    "git_head": bound.head,
                    "reason_code": primary_failure.reason_code,
                    "failure_subtype": primary_failure.failure_subtype,
                    "transport_subtype": primary_failure.transport_subtype,
                    "receipt_sha256": failure_receipt["receipt_sha256"],
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
    except BaseException:
        # The failure evidence is already committed; preserve its exit meaning.
        pass
    return 130 if primary_failure.reason_code == "execution-interrupted" else 1


def main() -> int:
    args = _parser().parse_args()
    try:
        _execution_arguments(args)
        profile = load_profile_for_plan(ROOT)
        if not args.execute:
            print(json.dumps(_plan(profile), indent=2, sort_keys=True))
            return 0
        return _execute(args)
    except SourceAuditError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
