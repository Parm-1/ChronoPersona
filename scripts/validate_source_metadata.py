#!/usr/bin/env python3
"""Validate and summarize source metadata JSONL without retrieving text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_metadata import (  # noqa: E402
    SourceMetadataFormatError,
    load_source_metadata,
    sha256_file,
    summarize_source_metadata,
    validate_source_metadata,
)
from chronopersona.source_registry import (  # noqa: E402
    load_source_registry,
    validate_source_registry,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate source metadata records against the committed source "
            "registry and emit deterministic aggregate counts."
        )
    )
    parser.add_argument("metadata", type=Path)
    parser.add_argument(
        "--source-registry",
        type=Path,
        default=ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json",
    )
    parser.add_argument("--summary-output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        source_registry = load_source_registry(args.source_registry)
        registry_errors = validate_source_registry(source_registry)
        if registry_errors:
            raise ValueError("; ".join(registry_errors))
        records = load_source_metadata(args.metadata)
        errors = validate_source_metadata(
            records,
            source_registry=source_registry,
        )
        if errors:
            print(
                f"invalid: {args.metadata} ({len(errors)} error(s))",
                file=sys.stderr,
            )
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        metadata_hash = sha256_file(args.metadata)
        summary = summarize_source_metadata(
            records,
            metadata_sha256=metadata_hash,
        )
    except (
        FileNotFoundError,
        OSError,
        json.JSONDecodeError,
        SourceMetadataFormatError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    rendered = json.dumps(summary, indent=2, sort_keys=True)
    print(rendered)
    if args.summary_output is not None:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
