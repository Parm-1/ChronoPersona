#!/usr/bin/env python3
"""Plan or execute bounded official-source metadata qualification.

Default mode is a no-network plan. Live requests require both ``--execute``
and ``--allow-network`` plus an explicit host allowlist and access-log path.
The command never downloads document bodies or bulk archives.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.bounded_metadata_network import (  # noqa: E402
    BoundedNetworkError,
    bounded_fetch,
)
from chronopersona.official_metadata_adapters import (  # noqa: E402
    AdapterRecord,
    MetadataAdapterError,
    canonical_sha256,
    parse_arxiv_raw_oai,
    parse_pmc_oai_dc,
    parse_stackexchange_archive_inventory,
    parse_wikimedia_dumpstatus,
)
from chronopersona.source_c_blinding import blind_source_c_records  # noqa: E402


_DEFAULT_HOSTS = {
    "arxiv": ("export.arxiv.org",),
    "pmc": ("www.ncbi.nlm.nih.gov",),
    "wikimedia": ("dumps.wikimedia.org",),
    "stackexchange": ("archive.org",),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a bounded official metadata response or inventory. "
            "The command defaults to a no-network plan."
        )
    )
    parser.add_argument(
        "source",
        choices=("arxiv", "pmc", "wikimedia", "stackexchange"),
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", type=Path, help="local frozen response fixture")
    input_group.add_argument("--url", help="bounded official metadata URL")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        help="repeatable live-request host allowlist",
    )
    parser.add_argument("--max-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--max-records", type=int, default=100)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--user-agent",
        default="ChronoPersona-Stage0-Metadata-Audit/0.1 (research metadata only)",
    )
    parser.add_argument("--access-log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--base-url",
        help="base URL used to resolve inventory file locators",
    )
    parser.add_argument(
        "--allowed-site",
        action="append",
        default=[],
        help="repeatable Stack Exchange site filename without .7z",
    )
    parser.add_argument(
        "--blind-source-c",
        action="store_true",
        help="remove native source-C identity/date fields from output",
    )
    parser.add_argument("--blinding-secret-file", type=Path)
    parser.add_argument("--unblinding-key", type=Path)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.max_bytes < 1:
        raise ValueError("--max-bytes must be positive")
    if args.max_records < 1:
        raise ValueError("--max-records must be positive")
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    if args.allow_network and not args.execute:
        raise ValueError("--allow-network requires --execute")
    if args.url and args.execute and not args.allow_network:
        raise ValueError("live URL execution requires --allow-network")
    if args.url and args.execute and args.access_log is None:
        raise ValueError("live URL execution requires --access-log")
    if args.url and args.execute and not args.allowed_host:
        raise ValueError("live URL execution requires at least one --allowed-host")
    if args.input and args.allow_network:
        raise ValueError("--allow-network is invalid with a local --input")
    if args.blind_source_c:
        if args.source not in {"arxiv", "pmc"}:
            raise ValueError("source-C blinding is only valid for arxiv or pmc")
        if args.blinding_secret_file is None or args.unblinding_key is None:
            raise ValueError(
                "--blind-source-c requires --blinding-secret-file and --unblinding-key"
            )
    elif args.blinding_secret_file is not None or args.unblinding_key is not None:
        raise ValueError("blinding files require --blind-source-c")
    if args.source in {"wikimedia", "stackexchange"} and not args.base_url:
        raise ValueError(f"{args.source} inventory parsing requires --base-url")


def _plan(args: argparse.Namespace) -> dict[str, Any]:
    default_hosts = list(_DEFAULT_HOSTS[args.source])
    return {
        "schema_version": 1,
        "mode": "plan",
        "source": args.source,
        "network_access_permitted": False,
        "input": str(args.input) if args.input else None,
        "url_shape": args.url,
        "recommended_hosts": default_hosts,
        "configured_hosts": sorted(set(args.allowed_host)),
        "max_bytes": args.max_bytes,
        "max_records": args.max_records,
        "timeout_seconds": args.timeout_seconds,
        "document_text_requested": False,
        "bulk_archive_requested": False,
        "source_c_blinding_requested": bool(args.blind_source_c),
    }


def _payload(args: argparse.Namespace) -> bytes:
    if args.input is not None:
        payload = args.input.read_bytes()
        if len(payload) > args.max_bytes:
            raise ValueError(
                f"local input is {len(payload)} bytes, above --max-bytes={args.max_bytes}"
            )
        return payload
    assert args.url is not None
    assert args.access_log is not None
    return bounded_fetch(
        args.url,
        allowed_hosts=set(args.allowed_host),
        max_bytes=args.max_bytes,
        timeout_seconds=args.timeout_seconds,
        user_agent=args.user_agent,
        access_log=args.access_log,
    )


def _records(args: argparse.Namespace, payload: bytes) -> tuple[AdapterRecord, ...]:
    if args.source == "arxiv":
        return parse_arxiv_raw_oai(payload, max_records=args.max_records)
    if args.source == "pmc":
        return parse_pmc_oai_dc(payload, max_records=args.max_records)
    raise AssertionError("record parser requested for inventory source")


def _execute(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any] | None]:
    payload = _payload(args)
    if args.source in {"arxiv", "pmc"}:
        records = _records(args, payload)
        if args.blind_source_c:
            assert args.blinding_secret_file is not None
            secret = args.blinding_secret_file.read_bytes()
            packet, key = blind_source_c_records(records, secret=secret)
            report: dict[str, Any] = {
                "schema_version": 1,
                "mode": "executed-local" if args.input else "executed-live-bounded",
                "source": args.source,
                "payload_bytes": len(payload),
                "record_count": len(records),
                "output_type": "source-c-blinded-packet",
                "packet": packet,
            }
            report["output_sha256"] = canonical_sha256(report)
            return report, key

        rendered_records = [record.as_dict() for record in records]
        report = {
            "schema_version": 1,
            "mode": "executed-local" if args.input else "executed-live-bounded",
            "source": args.source,
            "payload_bytes": len(payload),
            "record_count": len(rendered_records),
            "eligible_for_bounded_review_count": sum(
                bool(record["eligible_for_bounded_review"])
                for record in rendered_records
            ),
            "records": rendered_records,
        }
        report["output_sha256"] = canonical_sha256(report)
        return report, None

    if args.source == "wikimedia":
        inventory = parse_wikimedia_dumpstatus(
            payload,
            base_url=args.base_url,
            max_files=args.max_records,
        )
    else:
        inventory = parse_stackexchange_archive_inventory(
            payload,
            archive_base_url=args.base_url,
            max_files=args.max_records,
            allowed_sites=args.allowed_site,
        )
    report = {
        "schema_version": 1,
        "mode": "executed-local" if args.input else "executed-live-bounded",
        "source": args.source,
        "payload_bytes": len(payload),
        "file_count": len(inventory),
        "files": list(inventory),
    }
    report["output_sha256"] = canonical_sha256(report)
    return report, None


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = _parser().parse_args()
    try:
        _validate_args(args)
        key: dict[str, Any] | None = None
        if not args.execute:
            report = _plan(args)
        else:
            report, key = _execute(args)
    except (
        BoundedNetworkError,
        MetadataAdapterError,
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    print(rendered)
    if args.output is not None:
        _write(args.output, report)
    if key is not None:
        assert args.unblinding_key is not None
        _write(args.unblinding_key, key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
