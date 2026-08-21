#!/usr/bin/env python3
"""Plan, parse, or execute a bounded PMC OAI Dublin Core audit."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_adapters.network import (  # noqa: E402
    MetadataNetworkError,
    fetch_metadata,
)
from chronopersona.source_adapters.pmc_oai import (  # noqa: E402
    PmcMetadataError,
    parse_pmc_oai_dc,
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


# PMC replaced its OAI-PMH endpoint in September 2025. The old endpoint
# redirects, but an auditable tool must pin the current documented service.
ENDPOINT = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
ALLOWED_METADATA_HOSTS = ("pmc.ncbi.nlm.nih.gov",)
USER_AGENT = "ChronoPersona/0.1 metadata-audit (github.com/Parm-1/ChronoPersona)"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit PMC OAI Dublin Core metadata. Default mode is no-network; "
            "live access requires --execute and --allow-network. OAI from/until "
            "filter PMC release/update datestamps, not article publication dates. "
            "Dublin Core dc:date is retained only as unresolved lifecycle-date "
            "evidence until a publication-specific source confirms it."
        )
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--until-date", required=True)
    parser.add_argument("--set-spec", default="pmc-open")
    parser.add_argument("--max-records", type=int, default=1000)
    parser.add_argument("--max-response-bytes", type=int, default=8_000_000)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument(
        "--source-registry",
        type=Path,
        default=ROOT / "artifacts" / "manifests" / "SOURCE_REGISTRY.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "sources" / "pmc-metadata-v0.json",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    return parser


def _query_url(args: argparse.Namespace, token: str | None = None) -> str:
    if token:
        return ENDPOINT + "?" + urlencode(
            {"verb": "ListRecords", "resumptionToken": token}
        )
    parameters = {
        "verb": "ListRecords",
        "metadataPrefix": "oai_dc",
        "from": args.from_date,
        "until": args.until_date,
    }
    if args.set_spec:
        parameters["set"] = args.set_spec
    return ENDPOINT + "?" + urlencode(parameters)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def _merge_diagnostics(target: dict[str, int], page: dict[str, int]) -> None:
    for key, value in page.items():
        target[key] = target.get(key, 0) + int(value)


def main() -> int:
    args = _parser().parse_args()
    if args.max_records < 1 or args.max_records > 10_000:
        print("error: --max-records must be between 1 and 10000", file=sys.stderr)
        return 2
    if args.delay_seconds < 0:
        print("error: --delay-seconds must not be negative", file=sys.stderr)
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
        source_registry = load_source_registry(args.source_registry)
        registry_errors = validate_source_registry(source_registry)
        if registry_errors:
            raise ValueError("; ".join(registry_errors))
        windows = parse_era_windows(source_registry)
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if config.get("behavioral_outcomes_used") is not False:
            raise ValueError("PMC config must not use behavioral outcomes")
        if config.get("content_download_authorized") is not False:
            raise ValueError("PMC config must not authorize content download")
        allowed = tuple(config["allowed_subject_terms"])

        if not args.execute and args.input is None:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mode": "plan",
                        "network_access_permitted": False,
                        "content_downloaded": False,
                        "metadata_url": _query_url(args),
                        "oai_datestamp_filter_semantics": (
                            "PMC release/update datestamp; not publication date"
                        ),
                        "dc_date_semantics": (
                            "lifecycle-associated; era remains unresolved"
                        ),
                        "publication_date_confirmation_required": True,
                        "max_records": args.max_records,
                        "max_response_bytes": args.max_response_bytes,
                        "allowed_subject_terms": list(allowed),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        records: list[dict] = []
        diagnostics: dict[str, int] = {}
        token: str | None = None
        seen_header_identifiers: set[str] = set()
        first_request = True
        while len(records) < args.max_records:
            request_token = token
            if args.input is not None:
                if not first_request:
                    break
                payload = args.input.read_bytes()
            else:
                payload = fetch_metadata(
                    _query_url(args, token),
                    allow_network=args.allow_network,
                allowed_hosts=ALLOWED_METADATA_HOSTS,
                    max_bytes=args.max_response_bytes,
                    timeout_seconds=args.timeout_seconds,
                    user_agent=USER_AGENT,
                    delay_seconds=(0.0 if first_request else args.delay_seconds),
                )
            parsed, token, page_diagnostics = parse_pmc_oai_dc(
                payload,
                windows=windows,
                allowed_subject_terms=allowed,
                expected_from_date=(
                    None
                    if args.input is not None
                    else date.fromisoformat(args.from_date)
                ),
                expected_until_date=(
                    None
                    if args.input is not None
                    else date.fromisoformat(args.until_date)
                ),
                seen_header_identifiers=seen_header_identifiers,
                expected_request_attributes=(
                    {
                        "verb": "ListRecords",
                        "metadataPrefix": "oai_dc",
                        "set": args.set_spec,
                    }
                    if args.input is not None
                    else (
                        {"verb": "ListRecords", "resumptionToken": request_token}
                        if request_token is not None
                        else {
                            "verb": "ListRecords",
                            "metadataPrefix": "oai_dc",
                            "from": args.from_date,
                            "until": args.until_date,
                            "set": args.set_spec,
                        }
                    )
                ),
            )
            _merge_diagnostics(diagnostics, page_diagnostics)
            remaining = args.max_records - len(records)
            records.extend(parsed[:remaining])
            first_request = False
            if args.input is not None or not token or len(records) >= args.max_records:
                break

        if not records:
            raise ValueError(
                "PMC metadata query produced no records with usable dc:date evidence"
            )
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
        summary["adapter"] = {
            "source": "pmc-oai-oai_dc",
            "endpoint": ENDPOINT,
            "config": str(args.config),
            "oai_from_date": None if args.input is not None else args.from_date,
            "oai_until_date": None if args.input is not None else args.until_date,
            "oai_query_bounds_verified": args.input is None,
            "oai_datestamp_filter_semantics": (
                "PMC release/update datestamp; not publication date"
            ),
            "dc_date_semantics": (
                "lifecycle-associated; not used to assign era"
            ),
            "publication_date_confirmation_required": True,
            "set_spec": args.set_spec,
            "network_used": args.input is None,
            "content_downloaded": False,
            "historical_version_established": False,
            "parser_diagnostics": dict(sorted(diagnostics.items())),
            "resumption_token_remaining": bool(token),
        }
    except (
        FileNotFoundError,
        MetadataNetworkError,
        OSError,
        PmcMetadataError,
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
