"""Command-line interface for ChronoPersona."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys
import tomllib

from .config import (
    SpecFormatError,
    describe_spec,
    load_spec,
    validate_spec,
)
from .model_manifest import (
    ModelManifestFormatError,
    describe_model_manifest,
    load_model_manifest,
    validate_model_manifest,
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

    validate_models = subparsers.add_parser(
        "validate-models",
        help="validate a model-artifact JSON manifest",
    )
    validate_models.add_argument("manifest", type=Path)
    return parser


def _print_errors(path: Path, errors: tuple[str, ...]) -> int:
    print(
        f"invalid: {path} ({len(errors)} error(s))",
        file=sys.stderr,
    )
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 1


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
            return _print_errors(args.spec, errors)

        print(f"valid: {describe_spec(spec)}")
        return 0

    if args.command == "validate-models":
        try:
            manifest = load_model_manifest(args.manifest)
        except FileNotFoundError:
            print(
                f"error: model manifest not found: {args.manifest}",
                file=sys.stderr,
            )
            return 2
        except (
            OSError,
            json.JSONDecodeError,
            ModelManifestFormatError,
        ) as error:
            print(
                f"error: could not load {args.manifest}: {error}",
                file=sys.stderr,
            )
            return 2

        errors = validate_model_manifest(manifest)
        if errors:
            return _print_errors(args.manifest, errors)

        print(f"valid: {describe_model_manifest(manifest)}")
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
