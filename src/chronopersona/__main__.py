"""Command-line interface for ChronoPersona."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib
from collections.abc import Sequence

from .config import (
    SpecFormatError,
    describe_spec,
    load_spec,
    validate_spec,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chronopersona",
        description="ChronoPersona research utilities",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate",
        help="validate an experiment TOML specification",
    )
    validate.add_argument("spec", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "validate":
        try:
            spec = load_spec(args.spec)
        except FileNotFoundError:
            print(f"error: specification not found: {args.spec}", file=sys.stderr)
            return 2
        except (OSError, tomllib.TOMLDecodeError, SpecFormatError) as error:
            print(f"error: could not load {args.spec}: {error}", file=sys.stderr)
            return 2

        errors = validate_spec(spec)
        if errors:
            print(
                f"invalid: {args.spec} ({len(errors)} error(s))",
                file=sys.stderr,
            )
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1

        print(f"valid: {describe_spec(spec)}")
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
