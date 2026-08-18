#!/usr/bin/env python3
"""Plan, parse, or fetch a Wikimedia pages-meta-history file inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_adapters.network import (  # noqa: E402
    MetadataNetworkError,
    fetch_metadata,
)
from chronopersona.source_adapters.wikimedia_inventory import (  # noqa: E402
    WikimediaInventoryError,
    parse_wikimedia_dumpstatus,
)
from chronopersona.source_inventory import (  # noqa: E402
    summarize_source_inventory,
    validate_source_inventory,
)


USER_AGENT = "ChronoPersona/0.1 inventory-audit (github.com/Parm-1/ChronoPersona)"
ALLOWED_METADATA_HOSTS = ("dumps.wikimedia.org",)
_SNAPSHOT = re.compile(r"^\d{8}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Wikimedia history dump file sizes and hashes without "
            "downloading archive content. Planning may inspect the mutable "
            "latest URL, but parsed or live audit output requires an explicit "
            "YYYYMMDD snapshot."
        )
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--project", default="enwiki")
    parser.add_argument("--snapshot", default="latest")
    parser.add_argument("--max-response-bytes", type=int, default=20_000_000)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--inventory-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    return parser


def _url(project: str, snapshot: str) -> str:
    return f"https://dumps.wikimedia.org/{project}/{snapshot}/dumpstatus.json"


def main() -> int:
    args = _parser().parse_args()
    if not args.project.isalnum():
        print("error: --project must be alphanumeric", file=sys.stderr)
        return 2
    if args.allow_network and not args.execute:
        print(
            "error: --allow-network is meaningful only with --execute",
            file=sys.stderr,
        )
        return 2
    if args.execute and args.input is None and not args.allow_network:
        print("error: live execution requires --allow-network", file=sys.stderr)
        return 2
    if (args.execute or args.input is not None) and not _SNAPSHOT.fullmatch(
        args.snapshot
    ):
        print(
            "error: parsed/live audit requires --snapshot YYYYMMDD; "
            "the mutable 'latest' alias is planning-only",
            file=sys.stderr,
        )
        return 2
    source_locator = _url(args.project, args.snapshot)

    if not args.execute and args.input is None:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "mode": "plan",
                    "network_access_permitted": False,
                    "archive_downloaded": False,
                    "dumpstatus_url": source_locator,
                    "project": args.project,
                    "snapshot": args.snapshot,
                    "snapshot_is_mutable": args.snapshot == "latest",
                    "execution_requires_explicit_snapshot": True,
                    "max_response_bytes": args.max_response_bytes,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    try:
        payload = (
            args.input.read_bytes()
            if args.input is not None
            else fetch_metadata(
                source_locator,
                allow_network=args.allow_network,
                allowed_hosts=ALLOWED_METADATA_HOSTS,
                max_bytes=args.max_response_bytes,
                timeout_seconds=args.timeout_seconds,
                user_agent=USER_AGENT,
            )
        )
        input_sha256 = hashlib.sha256(payload).hexdigest()
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("dumpstatus root must be an object")
        records = parse_wikimedia_dumpstatus(
            value,
            source_locator=source_locator,
            snapshot_id=args.snapshot,
        )
        errors = validate_source_inventory(records)
        if errors:
            raise ValueError("; ".join(errors))
        summary = summarize_source_inventory(
            records,
            source_locator=source_locator,
        )
        summary["adapter"] = {
            "source": "wikimedia-dumpstatus",
            "project": args.project,
            "snapshot": args.snapshot,
            "snapshot_is_mutable": False,
            "inventory_input_sha256": input_sha256,
            "network_used": args.input is None,
            "archive_downloaded": False,
        }
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        MetadataNetworkError,
        OSError,
        ValueError,
        WikimediaInventoryError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    rendered_records = json.dumps(records, indent=2, sort_keys=True)
    rendered_summary = json.dumps(summary, indent=2, sort_keys=True)
    print(rendered_summary)
    if args.inventory_output is not None:
        args.inventory_output.parent.mkdir(parents=True, exist_ok=True)
        args.inventory_output.write_text(
            rendered_records + "\n",
            encoding="utf-8",
        )
    if args.summary_output is not None:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            rendered_summary + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
