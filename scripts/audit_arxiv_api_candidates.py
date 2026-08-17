#!/usr/bin/env python3
"""Plan, parse, or execute a bounded arXiv submitted-date candidate audit."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_adapters.arxiv_api import (  # noqa: E402
    ArxivApiError,
    parse_arxiv_api_feed,
)
from chronopersona.source_adapters.network import (  # noqa: E402
    MetadataNetworkError,
    fetch_metadata,
)
from chronopersona.source_metadata import (  # noqa: E402
    load_source_metadata,
    parse_era_windows,
    sha256_file,
    summarize_source_metadata,
    validate_source_metadata,
)
from chronopersona.source_registry import (  # noqa: E402
    load_source_registry,
    validate_source_registry,
)


ENDPOINT = "https://export.arxiv.org/api/query"
USER_AGENT = "ChronoPersona/0.1 metadata-audit (github.com/Parm-1/ChronoPersona)"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate arXiv candidates by first-submission date through the "
            "Atom API. Results remain unresolved until exact arXivRaw OAI "
            "enrichment establishes version count and item license. Default "
            "mode is no-network; live access requires --execute and "
            "--allow-network."
        )
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--max-records", type=int, default=500)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-response-bytes", type=int, default=8_000_000)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--delay-seconds", type=float, default=3.0)
    parser.add_argument(
        "--source-registry",
        type=Path,
        default=ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "sources" / "arxiv-metadata-v0.json",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    return parser


def _date_range(start_raw: str, end_raw: str) -> tuple[date, date, str]:
    try:
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
    except ValueError as error:
        raise ValueError("start-date and end-date must be ISO dates") from error
    if start > end:
        raise ValueError("start-date must not follow end-date")
    expression = (
        "submittedDate:["
        f"{start.strftime('%Y%m%d')}0000 TO "
        f"{end.strftime('%Y%m%d')}2359]"
    )
    return start, end, expression


def _search_query(categories: tuple[str, ...], submitted: str) -> str:
    if not categories:
        raise ValueError("arXiv API category list must not be empty")
    category_clause = " OR ".join(f"cat:{category}" for category in categories)
    return f"({category_clause}) AND {submitted}"


def _query_url(
    search_query: str,
    *,
    start: int,
    page_size: int,
) -> str:
    return ENDPOINT + "?" + urlencode(
        {
            "search_query": search_query,
            "start": start,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
        }
    )


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = _parser().parse_args()
    if args.max_records < 1 or args.max_records > 1_000:
        print("error: --max-records must be between 1 and 1000", file=sys.stderr)
        return 2
    if args.page_size < 1 or args.page_size > 100:
        print("error: --page-size must be between 1 and 100", file=sys.stderr)
        return 2
    if args.delay_seconds < 3.0 and args.input is None:
        print(
            "error: live arXiv API requests require at least 3 seconds delay",
            file=sys.stderr,
        )
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

    try:
        start_date, end_date, submitted_expression = _date_range(
            args.start_date,
            args.end_date,
        )
        source_registry = load_source_registry(args.source_registry)
        registry_errors = validate_source_registry(source_registry)
        if registry_errors:
            raise ValueError("; ".join(registry_errors))
        windows = parse_era_windows(source_registry)
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if config.get("behavioral_outcomes_used") is not False:
            raise ValueError("arXiv config must not use behavioral outcomes")
        if config.get("content_download_authorized") is not False:
            raise ValueError("arXiv config must not authorize content download")
        query_categories = tuple(config["api_query_categories"])
        allowed = tuple(config["allowed_category_prefixes"])
        forbidden = tuple(config.get("forbidden_category_prefixes", []))
        search_query = _search_query(query_categories, submitted_expression)

        if not args.execute and args.input is None:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mode": "plan",
                        "network_access_permitted": False,
                        "content_downloaded": False,
                        "metadata_url": _query_url(
                            search_query,
                            start=0,
                            page_size=min(args.page_size, args.max_records),
                        ),
                        "selection_semantics": "arXiv API submittedDate",
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "query_categories": list(query_categories),
                        "max_records": args.max_records,
                        "page_size": args.page_size,
                        "enrichment_required": [
                            "exact arXivRaw version history",
                            "item-level license",
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        records: list[dict] = []
        seen_ids: set[str] = set()
        pages: list[dict[str, int | None]] = []
        offset = 0
        while len(records) < args.max_records:
            page_size = min(args.page_size, args.max_records - len(records))
            if args.input is not None:
                if offset != 0:
                    break
                payload = args.input.read_bytes()
            else:
                payload = fetch_metadata(
                    _query_url(search_query, start=offset, page_size=page_size),
                    allow_network=args.allow_network,
                    max_bytes=args.max_response_bytes,
                    timeout_seconds=args.timeout_seconds,
                    user_agent=USER_AGENT,
                    delay_seconds=(0.0 if offset == 0 else args.delay_seconds),
                )
            parsed, page = parse_arxiv_api_feed(
                payload,
                windows=windows,
                allowed_category_prefixes=allowed,
                forbidden_category_prefixes=forbidden,
            )
            pages.append(page)
            if not parsed:
                break
            for record in parsed:
                record_id = str(record["record_id"])
                if record_id in seen_ids:
                    raise ValueError(f"duplicate arXiv API candidate: {record_id}")
                seen_ids.add(record_id)
                records.append(record)
                if len(records) >= args.max_records:
                    break
            if args.input is not None:
                break
            offset += len(parsed)
            total = page.get("total_results")
            if isinstance(total, int) and offset >= total:
                break
            if len(parsed) < page_size:
                break

        if not records:
            raise ValueError("arXiv API query produced no candidate records")
        metadata_errors = validate_source_metadata(
            records,
            source_registry=source_registry,
        )
        if metadata_errors:
            raise ValueError("; ".join(metadata_errors))
        if args.output is None:
            raise ValueError("--output is required when parsing or executing")
        _write_jsonl(args.output, records)
        metadata_hash = sha256_file(args.output)
        summary = summarize_source_metadata(
            load_source_metadata(args.output),
            metadata_sha256=metadata_hash,
        )
        first_total = pages[0].get("total_results") if pages else None
        summary["adapter"] = {
            "source": "arxiv-api-submittedDate-candidates",
            "endpoint": ENDPOINT,
            "config": str(args.config),
            "selection_semantics": "first submission date",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "query_categories": list(query_categories),
            "network_used": args.input is None,
            "content_downloaded": False,
            "page_count": len(pages),
            "reported_total_results": first_total,
            "result_is_bounded": (
                isinstance(first_total, int) and len(records) < first_total
            ),
            "license_enrichment_required": True,
            "version_enrichment_required": True,
        }
    except (
        ArxivApiError,
        FileNotFoundError,
        MetadataNetworkError,
        OSError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(summary, indent=2, sort_keys=True)
    print(rendered)
    if args.summary_output is not None:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
