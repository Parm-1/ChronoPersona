#!/usr/bin/env python3
"""Plan, parse, or execute exact arXivRaw OAI metadata enrichment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.source_adapters.arxiv_oai import (  # noqa: E402
    ArxivMetadataError,
    parse_arxiv_raw_oai,
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


ENDPOINT = "https://oaipmh.arxiv.org/oai"
ALLOWED_METADATA_HOSTS = ("oaipmh.arxiv.org",)
USER_AGENT = "ChronoPersona/0.1 metadata-audit (github.com/Parm-1/ChronoPersona)"
_VERSION_SUFFIX = re.compile(r"v\d+$", re.IGNORECASE)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich exact arXiv base identifiers with arXivRaw version history "
            "and license metadata. OAI-PMH datestamps are not submission dates, "
            "so this command does not perform era candidate selection. Use "
            "audit_arxiv_api_candidates.py for submittedDate enumeration. "
            "Default mode is no-network; live access requires --execute and "
            "--allow-network."
        )
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument(
        "--identifier",
        action="append",
        default=[],
        help="exact base arXiv identifier; repeat for multiple GetRecord calls",
    )
    parser.add_argument("--max-response-bytes", type=int, default=2_000_000)
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


def _base_identifier(raw: str) -> str:
    value = raw.strip()
    if not value or len(value) > 80:
        raise ValueError("arXiv identifier must be nonempty and at most 80 characters")
    if any(character.isspace() for character in value):
        raise ValueError(f"arXiv identifier contains whitespace: {raw!r}")
    if "://" in value or value.startswith("oai:"):
        raise ValueError(
            "--identifier requires a base arXiv id, not a URL or OAI identifier"
        )
    if _VERSION_SUFFIX.search(value):
        raise ValueError(
            f"--identifier must omit the version suffix: {raw!r}"
        )
    return value


def _get_record_url(identifier: str) -> str:
    return ENDPOINT + "?" + urlencode(
        {
            "verb": "GetRecord",
            "metadataPrefix": "arXivRaw",
            "identifier": f"oai:arXiv.org:{identifier}",
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


def _merge_diagnostics(target: dict[str, int], page: dict[str, int]) -> None:
    for key, value in page.items():
        target[key] = target.get(key, 0) + int(value)


def main() -> int:
    args = _parser().parse_args()
    if args.delay_seconds < 3.0 and args.input is None:
        print(
            "error: live arXiv OAI requests require at least 3 seconds delay",
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
    if args.input is not None and args.identifier:
        print(
            "error: --input and --identifier cannot be combined",
            file=sys.stderr,
        )
        return 2

    try:
        identifiers = tuple(_base_identifier(value) for value in args.identifier)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("arXiv identifiers must be unique")
        if len(identifiers) > 100:
            raise ValueError("at most 100 exact arXiv identifiers are allowed")
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
        allowed = tuple(config["allowed_category_prefixes"])
        forbidden = tuple(config.get("forbidden_category_prefixes", []))

        if not args.execute and args.input is None:
            print(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mode": "plan",
                        "network_access_permitted": False,
                        "content_downloaded": False,
                        "endpoint": ENDPOINT,
                        "operation": "exact-arXivRaw-enrichment",
                        "submission_date_selection_supported": False,
                        "candidate_enumerator": "audit_arxiv_api_candidates.py",
                        "identifiers": list(identifiers),
                        "request_urls": [
                            _get_record_url(identifier)
                            for identifier in identifiers
                        ],
                        "max_identifier_count": 100,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        records: list[dict] = []
        diagnostics: dict[str, int] = {}
        if args.input is not None:
            parsed, token, page_diagnostics = parse_arxiv_raw_oai(
                args.input.read_bytes(),
                windows=windows,
                allowed_category_prefixes=allowed,
                forbidden_category_prefixes=forbidden,
            )
            if token:
                raise ValueError(
                    "exact enrichment input unexpectedly contains a resumption token"
                )
            records.extend(parsed)
            _merge_diagnostics(diagnostics, page_diagnostics)
        else:
            if not identifiers:
                raise ValueError(
                    "live arXiv OAI enrichment requires at least one --identifier"
                )
            for index, identifier in enumerate(identifiers):
                payload = fetch_metadata(
                    _get_record_url(identifier),
                    allow_network=args.allow_network,
                allowed_hosts=ALLOWED_METADATA_HOSTS,
                    max_bytes=args.max_response_bytes,
                    timeout_seconds=args.timeout_seconds,
                    user_agent=USER_AGENT,
                    delay_seconds=(0.0 if index == 0 else args.delay_seconds),
                )
                parsed, token, page_diagnostics = parse_arxiv_raw_oai(
                    payload,
                    windows=windows,
                    allowed_category_prefixes=allowed,
                    forbidden_category_prefixes=forbidden,
                    expected_base_identifier=identifier,
                    expected_request_attributes={
                        "verb": "GetRecord",
                        "metadataPrefix": "arXivRaw",
                        "identifier": f"oai:arXiv.org:{identifier}",
                    },
                )
                if token:
                    raise ValueError(
                        f"GetRecord for {identifier!r} returned a resumption token"
                    )
                if len(parsed) != 1:
                    raise ValueError(
                        f"GetRecord for {identifier!r} returned {len(parsed)} records"
                    )
                records.extend(parsed)
                _merge_diagnostics(diagnostics, page_diagnostics)

        if not records:
            raise ValueError("arXivRaw enrichment produced no records")
        record_ids = [str(record["record_id"]) for record in records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("arXivRaw enrichment produced duplicate records")
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
            "source": "arxiv-oai-arXivRaw-exact-enrichment",
            "endpoint": ENDPOINT,
            "config": str(args.config),
            "operation": "exact GetRecord enrichment",
            "submission_date_selection_supported": False,
            "network_used": args.input is None,
            "content_downloaded": False,
            "identifier_count": len(identifiers) if args.input is None else None,
            "parser_diagnostics": dict(sorted(diagnostics.items())),
        }
    except (
        ArxivMetadataError,
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
