#!/usr/bin/env python3
"""Plan or execute validation of a local content-bearing manifest."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.content_integrity import (  # noqa: E402
    ContentIntegrityError,
    load_holdout_authorization,
    validate_holdout_authorization,
)
from chronopersona.content_manifest import (  # noqa: E402
    ContentManifestError,
    canonical_json_sha256,
    describe_content_manifest,
    load_content_manifest,
    resolve_content_records,
    sha256_file,
    validate_content_manifest_structure,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate content identities, rights/role assertions, and local "
            "UTF-8 files. Default mode does not read content files."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--content-root", type=Path)
    parser.add_argument("--holdout-authorization", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def _write(path: Path | None, value: object) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = _parser().parse_args()
    try:
        records = load_content_manifest(args.manifest)
        errors = validate_content_manifest_structure(records)
        if errors:
            raise ContentManifestError("; ".join(errors))
        manifest_hash = sha256_file(args.manifest)
        authorization = (
            load_holdout_authorization(args.holdout_authorization)
            if args.holdout_authorization is not None
            else None
        )
        if args.execute or authorization is not None:
            authorization_errors = validate_holdout_authorization(
                records,
                manifest_sha256=manifest_hash,
                authorization=authorization,
            )
            if authorization_errors:
                raise ContentIntegrityError("; ".join(authorization_errors))
        real_c_count = sum(
            record["role"] == "adaptation"
            and record["source_family"] == "C"
            and record["synthetic_fixture"] is False
            for record in records
        )
        content_root = args.content_root or args.manifest.parent / "documents"
        if not args.execute:
            report: dict[str, object] = {
                "schema_version": 1,
                "mode": "plan",
                "manifest_sha256": manifest_hash,
                "manifest": describe_content_manifest(records),
                "content_access_permitted": False,
                "content_accessed": False,
                "real_source_c_record_count": real_c_count,
                "holdout_authorization_required": real_c_count > 0,
                "holdout_authorization_present": authorization is not None,
            }
        else:
            loaded = resolve_content_records(records, content_root=content_root)
            report = {
                "schema_version": 1,
                "mode": "executed-local",
                "manifest_sha256": manifest_hash,
                "record_count": len(loaded),
                "content_accessed": True,
                "network_access_performed": False,
                "total_content_bytes": sum(
                    int(record.manifest["content_bytes"]) for record in loaded
                ),
                "total_words": sum(
                    int(record.manifest["word_count"]) for record in loaded
                ),
                "roles": dict(
                    sorted(Counter(record.manifest["role"] for record in loaded).items())
                ),
                "source_families": dict(
                    sorted(
                        Counter(
                            record.manifest["source_family"] for record in loaded
                        ).items()
                    )
                ),
                "real_source_c_record_count": real_c_count,
                "holdout_authorization_sha256": (
                    canonical_json_sha256(authorization)
                    if authorization is not None
                    else None
                ),
            }
        report["output_sha256"] = canonical_json_sha256(report)
    except (
        ContentIntegrityError,
        ContentManifestError,
        FileNotFoundError,
        OSError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    _write(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
