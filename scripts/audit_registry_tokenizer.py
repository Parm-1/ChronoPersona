#!/usr/bin/env python3
"""Plan or execute a manifest-approved evaluation tokenizer audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json"
DEFAULT_REGISTRY = ROOT / "evaluations" / "registry" / "development-v0.jsonl"
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.artifact_policy import (  # noqa: E402
    ArtifactPolicyError,
    assert_tokenizer_ready,
    find_artifact,
    operation_plan,
)
from chronopersona.evaluation import (  # noqa: E402
    canonical_json_sha256,
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
        default=DEFAULT_MANIFEST,
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
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
        "--snapshot-path",
        type=Path,
        help="exact already-acquired Hugging Face snapshot directory",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "run an offline tokenizer audit from an explicit verified snapshot"
        ),
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="reserved; direct tokenizer downloads are currently disabled",
    )
    parser.add_argument("--output", type=Path)
    return parser


def _require_canonical_path(path: Path, expected: Path, label: str) -> None:
    if path.resolve(strict=True) != expected.resolve(strict=True):
        raise ValueError(f"tokenizer execution requires the canonical {label}")


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip()


def _stable_file_bytes(path: Path) -> bytes:
    before = path.stat()
    with path.open("rb") as handle:
        opened_before = os.fstat(handle.fileno())
        payload = handle.read()
        opened_after = os.fstat(handle.fileno())
    after = path.stat()
    identities = {
        (
            int(info.st_dev),
            int(info.st_ino),
            int(info.st_size),
            int(info.st_mtime_ns),
            int(info.st_ctime_ns),
        )
        for info in (before, opened_before, opened_after, after)
    }
    if len(identities) != 1:
        raise RuntimeError(f"canonical input changed while reading: {path.name}")
    return payload


def _git_hash_payload(relative: str, payload: bytes) -> str:
    completed = subprocess.run(
        ["git", "hash-object", f"--path={relative}", "--stdin"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        input=payload,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        raise RuntimeError(f"git hash-object failed: {detail}")
    return completed.stdout.decode("ascii").strip()


def _execution_git_binding() -> tuple[dict[str, object], dict[str, bytes]]:
    head = _git("rev-parse", "HEAD")
    dirty = _git("status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise RuntimeError("tokenizer execution requires a clean exact Git head")
    bindings: dict[str, object] = {
        "git_head": head,
        "worktree_clean": True,
    }
    payloads: dict[str, bytes] = {}
    for label, path in (
        ("model_manifest", DEFAULT_MANIFEST),
        ("development_registry", DEFAULT_REGISTRY),
    ):
        relative = path.relative_to(ROOT).as_posix()
        payload = _stable_file_bytes(path)
        head_blob = _git("rev-parse", f"{head}:{relative}")
        worktree_blob = _git_hash_payload(relative, payload)
        if worktree_blob != head_blob:
            raise RuntimeError(f"canonical {label} does not match tracked HEAD bytes")
        bindings[f"{label}_git_blob"] = head_blob
        payloads[label] = payload
    if _git("rev-parse", "HEAD") != head:
        raise RuntimeError("Git HEAD changed while canonical inputs were bound")
    return bindings, payloads


def _manifest_from_bytes(payload: bytes) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"canonical model manifest is invalid: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("canonical model manifest root must be an object")
    return value


def _registry_from_bytes(payload: bytes) -> list[dict[str, object]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"canonical development registry is invalid: {error}") from error
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"canonical development registry line {line_number} is invalid: {error}"
            ) from error
        if not isinstance(record, dict):
            raise ValueError(
                f"canonical development registry line {line_number} is not an object"
            )
        records.append(record)
    return records


def _preflight_output(path: Path | None) -> None:
    if path is not None and os.path.lexists(path):
        raise ValueError(f"refusing to overwrite existing output: {path}")


def _require_output_outside_snapshot(
    output: Path,
    *,
    cache_dir: Path,
    snapshot_path: Path,
) -> None:
    candidate = output.resolve(strict=False)
    for root, label in (
        (cache_dir.resolve(strict=True), "model cache"),
        (snapshot_path.resolve(strict=True), "model snapshot"),
    ):
        if candidate.is_relative_to(root):
            raise ValueError(f"tokenizer output must be outside the {label}")


def _write_report(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered + "\n")


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
        _preflight_output(args.output)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        if args.execute:
            if args.cache_dir is None or args.snapshot_path is None:
                raise ValueError(
                    "--execute requires explicit --cache-dir and --snapshot-path"
                )
            if args.output is None:
                raise ValueError("--execute requires an explicit --output")
            _require_canonical_path(
                args.manifest,
                DEFAULT_MANIFEST,
                "model manifest",
            )
            _require_canonical_path(
                args.registry,
                DEFAULT_REGISTRY,
                "development registry",
            )
            _require_output_outside_snapshot(
                args.output,
                cache_dir=args.cache_dir,
                snapshot_path=args.snapshot_path,
            )
            git_binding, input_payloads = _execution_git_binding()
            manifest_payload = input_payloads["model_manifest"]
            registry_payload = input_payloads["development_registry"]
            manifest = _manifest_from_bytes(manifest_payload)
            registry = _registry_from_bytes(registry_payload)
            manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
            registry_sha256 = hashlib.sha256(registry_payload).hexdigest()
        else:
            manifest = load_model_manifest(args.manifest)
            registry = load_evaluation_registry(args.registry)
            manifest_sha256 = sha256_file(args.manifest)
            registry_sha256 = sha256_file(args.registry)
        manifest_errors = validate_model_manifest(manifest)
        if manifest_errors:
            raise ValueError("; ".join(manifest_errors))
        artifact = find_artifact(manifest, args.artifact)
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
                "registry_sha256": registry_sha256,
                "prefix_policy": args.prefix_policy,
                "max_length": args.max_length,
                "policy": operation_plan(artifact, "tokenizer-audit"),
            }
        else:
            assert_tokenizer_ready(artifact)
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
            loaded = load_manifest_tokenizer(
                artifact,
                cache_dir=args.cache_dir,
                snapshot_path=args.snapshot_path,
                manifest_path=args.manifest,
                expected_manifest_sha256=manifest_sha256,
            )
            if loaded.model_manifest_sha256 != manifest_sha256:
                raise RuntimeError(
                    "provider manifest identity differs from captured HEAD input"
                )
            native_prefix = loaded.tokenizer_validation.get(
                "native_prefix_policy"
            )
            if args.prefix_policy != native_prefix:
                raise ValueError(
                    "requested prefix policy differs from the manifest-bound "
                    f"native tokenizer policy: {native_prefix!r}"
                )
            report = audit_evaluation_tokenizer(
                registry,
                loaded.tokenizer,
                registry_sha256=registry_sha256,
                artifact_id=str(artifact["id"]),
                artifact_revision=loaded.revision,
                prefix_policy=args.prefix_policy,
                max_length=args.max_length,
                tokenizer_identity=(
                    f"{loaded.repository}@{loaded.revision}"
                ),
            )
            report.pop("output_sha256", None)
            weight_bytes_verified = sum(
                int(item["size_bytes"])
                for item in loaded.snapshot_verification["files"]
                if item["filename"].endswith(".safetensors")
            )
            report.update(
                {
                    "mode": "execute",
                    "network_access_permitted": False,
                    "network_observation": "not-instrumented",
                    "offline_enforcement": {
                        "HF_HUB_OFFLINE": "1",
                        "TRANSFORMERS_OFFLINE": "1",
                        "HF_HUB_DISABLE_TELEMETRY": "1",
                        "local_files_only": True,
                        "trust_remote_code": False,
                        "private_tokenizer_staging": True,
                    },
                    "weights_downloaded": False,
                    "tokenizer_files_downloaded": False,
                    "model_weights_deserialized": False,
                    "model_weight_bytes_verified": weight_bytes_verified,
                    "scientific_claim_authorized": False,
                    "model_manifest_sha256": loaded.model_manifest_sha256,
                    "snapshot_verification": dict(
                        loaded.snapshot_verification
                    ),
                    "loaded_tokenizer_validation": dict(
                        loaded.tokenizer_validation
                    ),
                    "runtime_identity": dict(loaded.runtime_identity),
                    **git_binding,
                }
            )
            final_binding, final_payloads = _execution_git_binding()
            if final_binding != git_binding or final_payloads != input_payloads:
                raise RuntimeError(
                    "Git head or canonical inputs changed during tokenizer audit"
                )
            report["output_sha256"] = canonical_json_sha256(report)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        _write_report(args.output, rendered)
    if args.execute and not report.get("passed", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
