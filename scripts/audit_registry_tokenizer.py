#!/usr/bin/env python3
"""Plan or execute a manifest-approved evaluation tokenizer audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.artifact_policy import (  # noqa: E402
    ArtifactPolicyError,
    assert_tokenizer_ready,
    find_artifact,
    operation_plan,
)
from chronopersona.evaluation import (  # noqa: E402
    load_evaluation_registry,
    sha256_file,
    validate_evaluation_registry,
)
from chronopersona.model_manifest import (  # noqa: E402
    load_model_manifest,
    validate_model_manifest,
)
from chronopersona.tokenizer_audit import (  # noqa: E402
    audit_evaluation_tokenizer,
)
from chronopersona.transformers_provider import (  # noqa: E402
    load_manifest_tokenizer,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit every evaluation prompt/continuation boundary with an "
            "approved tokenizer. Default mode performs no network access."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "evaluations" / "registry" / "development-v0.jsonl",
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument(
        "--prefix-policy",
        choices=("none", "bos"),
        required=True,
    )
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "request tokenizer execution; currently fail-closed until the "
            "verified-snapshot loader is integrated"
        ),
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="reserved; direct tokenizer downloads are currently disabled",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.max_length < 2:
        print("error: --max-length must be at least 2", file=sys.stderr)
        return 2
    if args.allow_download:
        print(
            "error: direct downloads are disabled; use "
            "the verified acquisition workflow for benchmark-ready artifacts",
            file=sys.stderr,
        )
        return 2

    try:
        manifest = load_model_manifest(args.manifest)
        manifest_errors = validate_model_manifest(manifest)
        if manifest_errors:
            raise ValueError("; ".join(manifest_errors))
        artifact = find_artifact(manifest, args.artifact)
        registry = load_evaluation_registry(args.registry)
        registry_errors = validate_evaluation_registry(registry)
        if registry_errors:
            raise ValueError("; ".join(registry_errors))

        if not args.execute:
            report = {
                "schema_version": 1,
                "mode": "plan",
                "network_access_permitted": False,
                "weights_downloaded": False,
                "tokenizer_files_downloaded": False,
                "registry": str(args.registry),
                "registry_sha256": sha256_file(args.registry),
                "prefix_policy": args.prefix_policy,
                "max_length": args.max_length,
                "policy": operation_plan(artifact, "tokenizer-audit"),
            }
        else:
            assert_tokenizer_ready(artifact)
            loaded = load_manifest_tokenizer(
                artifact,
                allow_download=args.allow_download,
                cache_dir=args.cache_dir,
            )
            report = audit_evaluation_tokenizer(
                registry,
                loaded.tokenizer,
                registry_sha256=sha256_file(args.registry),
                artifact_id=str(artifact["id"]),
                artifact_revision=loaded.revision,
                prefix_policy=args.prefix_policy,
                max_length=args.max_length,
            )
            report["mode"] = "execute"
            report["network_download_permitted"] = args.allow_download
            report["weights_downloaded"] = False
    except (
        ArtifactPolicyError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if args.execute and not report.get("passed", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
