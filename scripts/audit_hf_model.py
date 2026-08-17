#!/usr/bin/env python3
"""Resolve Hugging Face model metadata without downloading model weights.

This command performs network access to the Hugging Face Hub, but requests
metadata only. It is intended to resolve mutable branch names to commit SHAs,
record file sizes, and capture card license metadata before any model load.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


def _parse_spec(spec: str) -> tuple[str, str | None]:
    if "@" not in spec:
        return spec, None
    repo, revision = spec.rsplit("@", 1)
    if not repo or not revision:
        raise ValueError(f"invalid repository specification: {spec!r}")
    return repo, revision


def _card_data(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        return result if isinstance(result, dict) else None
    try:
        result = dict(value)
    except (TypeError, ValueError):
        return None
    return result


def _sibling_record(sibling: Any) -> dict[str, Any]:
    lfs = getattr(sibling, "lfs", None)
    lfs_record: dict[str, Any] | None = None
    if lfs is not None:
        lfs_record = {
            "size": getattr(lfs, "size", None),
            "sha256": getattr(lfs, "sha256", None),
            "pointer_size": getattr(lfs, "pointer_size", None),
        }
    return {
        "filename": getattr(sibling, "rfilename", None),
        "size": getattr(sibling, "size", None),
        "blob_id": getattr(sibling, "blob_id", None),
        "lfs": lfs_record,
    }


def audit_model(api: Any, spec: str) -> dict[str, Any]:
    repo_id, requested_revision = _parse_spec(spec)
    info = api.model_info(
        repo_id=repo_id,
        revision=requested_revision,
        files_metadata=True,
    )
    card = _card_data(getattr(info, "card_data", None))
    siblings = [
        _sibling_record(sibling)
        for sibling in (getattr(info, "siblings", None) or [])
    ]
    total_size = sum(
        sibling["size"]
        for sibling in siblings
        if isinstance(sibling.get("size"), int)
    )
    weight_size = sum(
        sibling["size"]
        for sibling in siblings
        if isinstance(sibling.get("size"), int)
        and isinstance(sibling.get("filename"), str)
        and sibling["filename"].endswith(
            (".safetensors", ".bin", ".pt", ".pth", ".ckpt")
        )
    )
    return {
        "repository": repo_id,
        "requested_revision": requested_revision,
        "resolved_revision": getattr(info, "sha", None),
        "last_modified": str(getattr(info, "last_modified", None)),
        "private": getattr(info, "private", None),
        "disabled": getattr(info, "disabled", None),
        "gated": getattr(info, "gated", None),
        "library_name": getattr(info, "library_name", None),
        "pipeline_tag": getattr(info, "pipeline_tag", None),
        "tags": list(getattr(info, "tags", None) or []),
        "license": card.get("license") if card else None,
        "base_model": card.get("base_model") if card else None,
        "card_data": card,
        "file_count": len(siblings),
        "total_file_bytes": total_size,
        "weight_file_bytes": weight_size,
        "siblings": siblings,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve exact Hugging Face revisions, file sizes, hashes, and "
            "card metadata without downloading model weights."
        )
    )
    parser.add_argument(
        "repository",
        nargs="+",
        help="owner/name or owner/name@revision; branch names are resolved",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON output path; stdout is always written",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print(
            "error: huggingface_hub is required; install the models extra "
            "or run `python -m pip install huggingface-hub`",
            file=sys.stderr,
        )
        return 2

    api = HfApi()
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for spec in args.repository:
        try:
            records.append(audit_model(api, spec))
        except (OSError, RuntimeError, ValueError) as error:
            failures.append({"repository": spec, "error": str(error)})
        except Exception as error:  # Hub exception types vary by version.
            failures.append(
                {
                    "repository": spec,
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    report = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "audit_type": "hugging-face-model-metadata",
        "weights_downloaded": False,
        "models": records,
        "failures": failures,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
