#!/usr/bin/env python3
"""Plan, parse, or fetch the legacy Stack Exchange archive inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_adapters.network import (  # noqa: E402
    MetadataNetworkError,
    fetch_metadata,
)
from chronopersona.source_adapters.stackexchange_inventory import (  # noqa: E402
    StackExchangeInventoryError,
    parse_stackexchange_archive_metadata,
)
from chronopersona.source_inventory import (  # noqa: E402
    summarize_source_inventory,
    validate_source_inventory,
)


ENDPOINT = "https://archive.org/metadata/stackexchange"
ALLOWED_METADATA_HOSTS = ("archive.org",)
USER_AGENT = "ChronoPersona/0.1 inventory-audit (github.com/Parm-1/ChronoPersona)"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the frozen legacy Stack Exchange Archive.org item without "
            "downloading any site dump. Stack Exchange stopped publishing new "
            "dumps to Archive.org in 2024; this command does not treat the item "
            "as the current official delivery path."
        )
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--max-response-bytes", type=int, default=30_000_000)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--inventory-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.allow_network and not args.execute:
        print(
            "error: --allow-network is meaningful only with --execute",
            file=sys.stderr,
        )
        return 2
    if args.execute and args.input is None and not args.allow_network:
        print("error: live execution requires --allow-network", file=sys.stderr)
        return 2

    if not args.execute and args.input is None:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "mode": "plan",
                    "network_access_permitted": False,
                    "archive_downloaded": False,
                    "metadata_url": ENDPOINT,
                    "delivery_status": (
                        "legacy Archive.org item; not current official delivery"
                    ),
                    "company_attribution_required": True,
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
                ENDPOINT,
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
            raise ValueError("Archive.org metadata root must be an object")
        records = parse_stackexchange_archive_metadata(
            value,
            source_locator=ENDPOINT,
        )
        inventory_errors = validate_source_inventory(records)
        if inventory_errors:
            raise ValueError("; ".join(inventory_errors))
        if not all(
            record["source_metadata"].get("company_attributed_archive_item")
            is True
            for record in records
        ):
            raise ValueError(
                "Archive.org item is not attributed to Stack Exchange; "
                "community mirrors require a separate provenance decision"
            )
        summary = summarize_source_inventory(records, source_locator=ENDPOINT)
        summary["adapter"] = {
            "source": "stackexchange-legacy-archive-metadata",
            "inventory_input_sha256": input_sha256,
            "network_used": args.input is None,
            "archive_downloaded": False,
            "delivery_status": (
                "legacy Archive.org item; not current official delivery"
            ),
            "company_attributed_archive_item": True,
            "site_panel_frozen": False,
        }
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        MetadataNetworkError,
        OSError,
        StackExchangeInventoryError,
        ValueError,
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
