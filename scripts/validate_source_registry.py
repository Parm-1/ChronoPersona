#!/usr/bin/env python3
"""Validate the committed ChronoPersona source registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_registry import (  # noqa: E402
    SourceRegistryFormatError,
    describe_source_registry,
    load_source_registry,
    validate_source_registry,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate source assignments, rights, timestamp, exposure, and "
            "held-out-source rules."
        )
    )
    parser.add_argument(
        "registry",
        nargs="?",
        type=Path,
        default=ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        registry = load_source_registry(args.registry)
    except FileNotFoundError:
        print(
            f"error: source registry not found: {args.registry}",
            file=sys.stderr,
        )
        return 2
    except (OSError, json.JSONDecodeError, SourceRegistryFormatError) as error:
        print(
            f"error: could not load {args.registry}: {error}",
            file=sys.stderr,
        )
        return 2

    errors = validate_source_registry(registry)
    if errors:
        print(
            f"invalid: {args.registry} ({len(errors)} error(s))",
            file=sys.stderr,
        )
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"valid: {describe_source_registry(registry)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
