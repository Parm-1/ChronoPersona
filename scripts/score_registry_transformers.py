#!/usr/bin/env python3
"""Plan or execute deterministic registry scoring with an approved causal LM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.artifact_policy import (  # noqa: E402
    ArtifactPolicyError,
    assert_model_score_ready,
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
from chronopersona.scoring import score_evaluation_registry  # noqa: E402
from chronopersona.transformers_provider import (  # noqa: E402
    TransformersContinuationProvider,
    load_manifest_model,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Score a validated evaluation registry with an immutable, "
            "licensed, no-remote-code model artifact. Default mode is a "
            "no-network plan."
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
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument(
        "--dtype",
        choices=("auto", "float16", "bfloat16", "float32"),
        default="auto",
    )
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="load the model and score every registry continuation",
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="permit download of missing pinned model/tokenizer files",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.max_length < 2:
        print("error: --max-length must be at least 2", file=sys.stderr)
        return 2
    if args.allow_download and not args.execute:
        print(
            "error: --allow-download is meaningful only with --execute",
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
        registry_hash = sha256_file(args.registry)

        if not args.execute:
            report = {
                "schema_version": 1,
                "mode": "plan",
                "network_access_permitted": False,
                "weights_downloaded": False,
                "registry": str(args.registry),
                "registry_sha256": registry_hash,
                "prefix_policy": args.prefix_policy,
                "max_length": args.max_length,
                "device": args.device,
                "dtype": args.dtype,
                "policy": operation_plan(artifact, "model-score"),
            }
        else:
            assert_model_score_ready(artifact)
            loaded = load_manifest_model(
                artifact,
                allow_download=args.allow_download,
                device=args.device,
                dtype=args.dtype,
                cache_dir=args.cache_dir,
            )
            provider = TransformersContinuationProvider(
                loaded,
                prefix_policy=args.prefix_policy,
                max_length=args.max_length,
            )
            tokenizer_id = (
                f"{loaded.repository}@{loaded.revision}:"
                f"{loaded.tokenizer.__class__.__name__}:"
                f"prefix={args.prefix_policy}"
            )
            report = score_evaluation_registry(
                registry,
                provider,
                registry_sha256=registry_hash,
                model_id=str(artifact["id"]),
                model_revision=loaded.revision,
                tokenizer_id=tokenizer_id,
                scorer_version="complete-continuation-transformers-v0",
            )
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
