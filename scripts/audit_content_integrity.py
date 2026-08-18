#!/usr/bin/env python3
"""Plan or execute deterministic local content-integrity triage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.content_integrity import (  # noqa: E402
    ContentIntegrityError,
    audit_content_integrity,
    load_direct_patterns,
    load_holdout_authorization,
    load_integrity_config,
    validate_holdout_authorization,
)
from chronopersona.content_manifest import (  # noqa: E402
    ContentManifestError,
    canonical_json_sha256,
    load_content_manifest,
    resolve_content_records,
    sha256_file,
    validate_content_manifest_structure,
)


DEFAULT_CONFIG = ROOT / "configs" / "content-integrity-v0.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit exact/normalized/near duplicates, evaluation overlap, and "
            "narrow direct-exposure cues. Default mode does not read content."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--content-root", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--direct-patterns", type=Path)
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


def _safe_repo_file(repo_root: Path, raw_path: str) -> Path:
    if "\\" in raw_path or ":" in raw_path:
        raise ContentIntegrityError(
            "configured direct-pattern path must use portable forward slashes"
        )
    portable = PurePosixPath(raw_path)
    if (
        portable.is_absolute()
        or ".." in portable.parts
        or portable.as_posix() != raw_path
    ):
        raise ContentIntegrityError(
            "configured direct-pattern path must be canonical and relative"
        )
    relative = Path(*portable.parts)
    root = repo_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ContentIntegrityError(
            "configured direct-pattern path escapes repository root"
        ) from error
    if not resolved.is_file():
        raise ContentIntegrityError(f"direct-pattern registry not found: {relative}")
    return resolved


def main() -> int:
    args = _parser().parse_args()
    try:
        records = load_content_manifest(args.manifest)
        errors = validate_content_manifest_structure(records)
        if errors:
            raise ContentManifestError("; ".join(errors))
        manifest_hash = sha256_file(args.manifest)
        config = load_integrity_config(args.config)
        patterns_path = args.direct_patterns or _safe_repo_file(
            args.repo_root, config.direct_patterns
        )
        patterns = load_direct_patterns(patterns_path)
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
        if not args.execute:
            report: dict[str, object] = {
                "schema_version": 1,
                "mode": "plan",
                "manifest_sha256": manifest_hash,
                "config_sha256": sha256_file(args.config),
                "direct_patterns_sha256": sha256_file(patterns_path),
                "content_access_permitted": False,
                "content_accessed": False,
                "record_count": len(records),
                "real_source_c_record_count": real_c_count,
                "holdout_authorization_required": real_c_count > 0,
                "holdout_authorization_present": authorization is not None,
                "semantic_similarity_performed": False,
                "automatic_exclusion_performed": False,
            }
            report["output_sha256"] = canonical_json_sha256(report)
        else:
            content_root = args.content_root or args.manifest.parent / "documents"
            loaded = resolve_content_records(records, content_root=content_root)
            report = audit_content_integrity(
                loaded,
                manifest_sha256=manifest_hash,
                config=config,
                config_sha256=sha256_file(args.config),
                patterns=patterns,
                patterns_sha256=sha256_file(patterns_path),
                holdout_authorization=authorization,
            )
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
