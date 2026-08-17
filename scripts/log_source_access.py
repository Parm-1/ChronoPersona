#!/usr/bin/env python3
"""Append a content-free source-review access event."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_review import (  # noqa: E402
    SourceReviewError,
    append_access_event,
    build_access_event,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Record a planned, successful, or failed source-review access. "
            "The event stores locator and response hashes, never raw source text."
        )
    )
    parser.add_argument("--access-map", type=Path, required=True)
    parser.add_argument("--access-id", required=True)
    parser.add_argument(
        "--locator-kind",
        choices=("metadata", "content"),
        required=True,
    )
    parser.add_argument("--reviewer", required=True)
    parser.add_argument(
        "--purpose",
        choices=(
            "metadata-review",
            "content-review",
            "license-review",
            "version-review",
        ),
        required=True,
    )
    parser.add_argument("--accessed-at", required=True)
    parser.add_argument(
        "--outcome",
        choices=("planned", "succeeded", "failed"),
        required=True,
    )
    parser.add_argument("--response-sha256")
    parser.add_argument("--response-bytes", type=int)
    parser.add_argument("--error-code")
    parser.add_argument("--log", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        access_map = json.loads(args.access_map.read_text(encoding="utf-8"))
        if not isinstance(access_map, dict):
            raise ValueError("access map root must be an object")
        event = build_access_event(
            access_map,
            access_id=args.access_id,
            locator_kind=args.locator_kind,
            reviewer=args.reviewer,
            purpose=args.purpose,
            accessed_at=args.accessed_at,
            outcome=args.outcome,
            response_sha256=args.response_sha256,
            response_bytes=args.response_bytes,
            error_code=args.error_code,
        )
        append_access_event(args.log, event)
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        SourceReviewError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(event, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
