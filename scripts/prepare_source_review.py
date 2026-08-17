#!/usr/bin/env python3
"""Create a locator-redacted review packet and protected access map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_review import (  # noqa: E402
    SourceReviewError,
    redact_review_packet,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert an era-hidden source audit sample packet into a "
            "locator-redacted reviewer packet and a separate protected "
            "access map. No network access is performed."
        )
    )
    parser.add_argument("packet", type=Path)
    parser.add_argument("--redaction-seed", required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--access-map-output", type=Path, required=True)
    return parser


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = _parser().parse_args()
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            raise ValueError("sample packet root must be an object")
        reviewer_packet, access_map = redact_review_packet(
            packet,
            redaction_seed=args.redaction_seed,
        )
        _write(args.review_output, reviewer_packet)
        _write(args.access_map_output, access_map)
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        SourceReviewError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "schema_version": 1,
                "review_packet": str(args.review_output),
                "review_packet_sha256": reviewer_packet["output_sha256"],
                "access_map": str(args.access_map_output),
                "access_map_sha256": access_map["output_sha256"],
                "record_count": len(reviewer_packet["records"]),
                "network_access_performed": False,
                "source_text_recorded": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
