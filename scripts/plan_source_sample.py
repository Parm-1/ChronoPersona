#!/usr/bin/env python3
"""Create a deterministic, optionally era-blinded source audit sample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_metadata import (  # noqa: E402
    SampleTarget,
    SamplingPlanError,
    deterministic_audit_sample,
    load_source_metadata,
    sha256_file,
    validate_source_metadata,
)
from chronopersona.source_registry import (  # noqa: E402
    load_source_registry,
    validate_source_registry,
)


def _target(raw: str) -> SampleTarget:
    parts = raw.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "target must be SOURCE:WINDOW:STRATUM:COUNT"
        )
    source_id, window, stratum, raw_count = parts
    try:
        count = int(raw_count)
    except ValueError as error:
        raise argparse.ArgumentTypeError("target count must be an integer") from error
    return SampleTarget(source_id, window, stratum, count)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Select deterministic metadata records for manual source audit. "
            "The packet and unblinding key are written separately."
        )
    )
    parser.add_argument("metadata", type=Path)
    parser.add_argument(
        "--source-registry",
        type=Path,
        default=ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json",
    )
    parser.add_argument(
        "--target",
        action="append",
        type=_target,
        required=True,
        help="SOURCE:WINDOW:STRATUM:COUNT; repeat as needed",
    )
    parser.add_argument("--seed", required=True)
    parser.add_argument(
        "--hide-era-labels",
        action="store_true",
        help="omit timestamps and era labels from the review packet",
    )
    parser.add_argument("--packet-output", type=Path, required=True)
    parser.add_argument("--key-output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        registry = load_source_registry(args.source_registry)
        registry_errors = validate_source_registry(registry)
        if registry_errors:
            raise ValueError("; ".join(registry_errors))
        records = load_source_metadata(args.metadata)
        metadata_errors = validate_source_metadata(
            records,
            source_registry=registry,
        )
        if metadata_errors:
            raise ValueError("; ".join(metadata_errors))
        packet, key = deterministic_audit_sample(
            records,
            args.target,
            seed=args.seed,
            metadata_sha256=sha256_file(args.metadata),
            hide_era_labels=args.hide_era_labels,
        )
    except (
        FileNotFoundError,
        OSError,
        json.JSONDecodeError,
        SamplingPlanError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    args.packet_output.parent.mkdir(parents=True, exist_ok=True)
    args.key_output.parent.mkdir(parents=True, exist_ok=True)
    args.packet_output.write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.key_output.write_text(
        json.dumps(key, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "packet_output": str(args.packet_output),
                "packet_sha256": packet["output_sha256"],
                "key_output": str(args.key_output),
                "key_sha256": key["output_sha256"],
                "selected_records": len(packet["records"]),
                "era_labels_hidden": packet["era_labels_hidden"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
