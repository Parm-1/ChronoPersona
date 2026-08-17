#!/usr/bin/env python3
"""Build or verify the deterministic Synthetic Identifiability package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.synthetic_calibration import (  # noqa: E402
    SyntheticCalibrationError,
    build_package,
    sha256_bytes,
)


DEFAULT_OUTPUT = ROOT / "artifacts" / "local" / "synthetic-calibration-v0"
EXPECTED = ROOT / "calibration" / "synthetic-v0" / "expected-hashes.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic synthetic-calibration documents, metadata, "
            "evaluation, balance, dose, and manifest artifacts. No model, "
            "network, or training is used."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "calibration" / "synthetic-v0.json",
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser


def _identity(built) -> dict:
    return {
        "schema_version": 1,
        "package_id": built.manifest["package_id"],
        "package_manifest_sha256": built.manifest["output_sha256"],
        "generated_files": {
            path: {"sha256": sha256_bytes(content), "bytes": len(content)}
            for path, content in sorted(built.files.items())
        },
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        built = build_package(args.config)
        identity = _identity(built)
        if args.check:
            expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
            if identity != expected:
                print(
                    "error: generated package identity differs from expected-hashes.json",
                    file=sys.stderr,
                )
                print(json.dumps(identity, indent=2, sort_keys=True), file=sys.stderr)
                return 1
            print(
                "valid: synthetic-identifiability-v0 identity matches, "
                f"manifest={identity['package_manifest_sha256']}"
            )
            return 0

        for relative_path, content in built.files.items():
            destination = args.output_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        identity_path = args.output_root / "package-identity.json"
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        identity_path.write_text(
            json.dumps(identity, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            "built: synthetic-identifiability-v0, "
            f"files={len(built.files)}, output={args.output_root}, "
            f"manifest={identity['package_manifest_sha256']}"
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        SyntheticCalibrationError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
