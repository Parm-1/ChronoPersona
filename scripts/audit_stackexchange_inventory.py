#!/usr/bin/env python3
"""Plan or execute a bounded Stack Exchange legacy-inventory audit.

The command inventories Internet Archive metadata only. It never downloads a
Stack Exchange ``.7z`` archive. Local fixtures require ``--execute`` but no
network permission. Live metadata access additionally requires
``--allow-network`` and an append-only access log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.bounded_metadata_network import (  # noqa: E402
    BoundedNetworkError,
    bounded_fetch,
)
from chronopersona.official_metadata_adapters import (  # noqa: E402
    MetadataAdapterError,
    canonical_sha256,
    parse_stackexchange_archive_inventory,
)


ENDPOINT = "https://archive.org/metadata/stackexchange"
DEFAULT_ARCHIVE_BASE_URL = "https://archive.org/download/stackexchange"
USER_AGENT = (
    "ChronoPersona-Stage0-StackExchange-Inventory/0.1 "
    "(metadata only; github.com/Parm-1/ChronoPersona)"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the frozen legacy Stack Exchange Internet Archive item "
            "without downloading any site archive. The item is not treated "
            "as the current official dump-delivery mechanism."
        )
    )
    parser.add_argument("--input", type=Path, help="local frozen metadata JSON")
    parser.add_argument(
        "--archive-base-url",
        default=DEFAULT_ARCHIVE_BASE_URL,
        help="base URL used only to construct inventory locators",
    )
    parser.add_argument(
        "--allowed-site",
        action="append",
        default=[],
        help=(
            "repeatable exact site filename without the .7z suffix, for "
            "example gardening.stackexchange.com"
        ),
    )
    parser.add_argument("--max-response-bytes", type=int, default=30_000_000)
    parser.add_argument("--max-files", type=int, default=10_000)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--access-log", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--inventory-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.max_response_bytes < 1:
        raise ValueError("--max-response-bytes must be positive")
    if args.max_files < 1:
        raise ValueError("--max-files must be positive")
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    if args.allow_network and not args.execute:
        raise ValueError("--allow-network requires --execute")
    if args.input is not None and args.allow_network:
        raise ValueError("--allow-network is invalid with a local --input")
    if args.execute and args.input is None:
        if not args.allow_network:
            raise ValueError("live execution requires --allow-network")
        if args.access_log is None:
            raise ValueError("live execution requires --access-log")

    parsed_base = urlsplit(args.archive_base_url)
    if parsed_base.scheme != "https" or not parsed_base.netloc:
        raise ValueError("--archive-base-url must be an absolute HTTPS URL")

    normalized_sites = [site.strip().lower() for site in args.allowed_site]
    if any(not site or "/" in site or site.endswith(".7z") for site in normalized_sites):
        raise ValueError(
            "each --allowed-site must be a nonempty site filename without .7z"
        )
    if len(normalized_sites) != len(set(normalized_sites)):
        raise ValueError("--allowed-site values must be unique")
    args.allowed_site = normalized_sites


def _plan(args: argparse.Namespace) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": "plan",
        "source": "stackexchange-legacy-archive-inventory",
        "network_access_permitted": False,
        "archive_download_permitted": False,
        "metadata_endpoint": ENDPOINT,
        "archive_base_url": args.archive_base_url,
        "allowed_sites": sorted(args.allowed_site),
        "max_response_bytes": args.max_response_bytes,
        "max_files": args.max_files,
        "delivery_status": "legacy Archive.org item; not current official delivery",
    }


def _read_payload(args: argparse.Namespace) -> bytes:
    if args.input is not None:
        payload = args.input.read_bytes()
        if len(payload) > args.max_response_bytes:
            raise ValueError(
                f"local input is {len(payload)} bytes, above "
                f"--max-response-bytes={args.max_response_bytes}"
            )
        return payload

    assert args.access_log is not None
    return bounded_fetch(
        ENDPOINT,
        allowed_hosts={"archive.org"},
        max_bytes=args.max_response_bytes,
        timeout_seconds=args.timeout_seconds,
        user_agent=USER_AGENT,
        access_log=args.access_log,
    )


def _execute(args: argparse.Namespace) -> dict[str, object]:
    payload = _read_payload(args)
    files = parse_stackexchange_archive_inventory(
        payload,
        archive_base_url=args.archive_base_url,
        max_files=args.max_files,
        allowed_sites=args.allowed_site,
    )
    if args.allowed_site and len(files) != len(args.allowed_site):
        returned_sites = {
            str(entry.get("metadata", {}).get("site", ""))
            for entry in files
            if isinstance(entry.get("metadata"), dict)
        }
        missing = sorted(set(args.allowed_site) - returned_sites)
        raise ValueError(
            "allowed Stack Exchange sites missing from inventory: "
            + ", ".join(missing)
        )

    report: dict[str, object] = {
        "schema_version": 1,
        "mode": "executed-local" if args.input is not None else "executed-live-bounded",
        "source": "stackexchange-legacy-archive-inventory",
        "network_used": args.input is None,
        "archive_download_permitted": False,
        "archive_downloaded": False,
        "metadata_endpoint": ENDPOINT,
        "archive_base_url": args.archive_base_url,
        "metadata_response_bytes": len(payload),
        "metadata_response_sha256": hashlib.sha256(payload).hexdigest(),
        "allowed_sites": sorted(args.allowed_site),
        "file_count": len(files),
        "total_size_bytes": sum(
            int(entry["size_bytes"])
            for entry in files
            if isinstance(entry.get("size_bytes"), int)
        ),
        "files": list(files),
        "delivery_status": "legacy Archive.org item; not current official delivery",
    }
    report["output_sha256"] = canonical_sha256(report)
    return report


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = _parser().parse_args()
    try:
        _validate_args(args)
        report = _execute(args) if args.execute else _plan(args)
    except (
        BoundedNetworkError,
        FileNotFoundError,
        MetadataAdapterError,
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    if args.summary_output is not None:
        _write_json(args.summary_output, report)
    if args.inventory_output is not None:
        _write_json(args.inventory_output, report.get("files", []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
