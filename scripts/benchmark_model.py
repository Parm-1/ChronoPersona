#!/usr/bin/env python3
"""Run a guarded, unquantized model-loading and logits benchmark.

The default mode is a no-network plan. Execution is allowed only for artifacts
that the committed model manifest marks ``benchmark-ready``. Downloads require
an additional explicit flag. Custom remote code is never enabled by this
script.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import platform
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chronopersona.model_manifest import (  # noqa: E402
    load_model_manifest,
    validate_model_manifest,
)


def _artifact(manifest: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    for artifact in manifest["artifacts"]:
        if artifact.get("id") == artifact_id:
            return artifact
    raise ValueError(f"unknown artifact id: {artifact_id}")


def _plan(artifact: dict[str, Any], allow_download: bool) -> dict[str, Any]:
    weight_bytes = artifact.get("weight_size_bytes")
    return {
        "schema_version": 1,
        "mode": "plan",
        "network_access_permitted": allow_download,
        "weights_downloaded": False,
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": artifact["revision"],
        "checkpoint_ref": artifact.get("checkpoint_ref"),
        "execution_status": artifact["execution_status"],
        "weight_size_bytes": weight_bytes,
        "minimum_free_disk_bytes": (
            int(weight_bytes * 2.5) if isinstance(weight_bytes, int) else None
        ),
        "requires_remote_code": artifact["requires_remote_code"],
        "license_status": artifact["license"]["status"],
        "constraints": artifact.get("constraints", []),
    }


def _dtype(torch: Any, name: str) -> Any:
    if name == "auto":
        return "auto"
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[name]


def _max_rss_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return int(usage)
    return int(usage * 1024)


def _execute(args: argparse.Namespace, artifact: dict[str, Any]) -> dict[str, Any]:
    if artifact["execution_status"] != "benchmark-ready":
        raise ValueError(
            f"artifact {artifact['id']} is {artifact['execution_status']}, "
            "not benchmark-ready"
        )
    if artifact["requires_remote_code"]:
        raise ValueError("custom remote code is not supported by this benchmark")
    if artifact["license"]["status"] != "verified":
        raise ValueError("model license must be verified before execution")
    if not artifact["immutable"]:
        raise ValueError("artifact revision must be immutable before execution")
    revision = artifact.get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("benchmark execution requires a pinned 40-character SHA")

    try:
        import torch
        import torch.nn.functional as functional
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as error:
        raise RuntimeError(
            "model benchmark dependencies are missing; install `.[models]`"
        ) from error

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")

    device = torch.device(args.device)
    requested_dtype = _dtype(torch, args.dtype)
    local_files_only = not args.allow_download
    cache_dir = str(args.cache_dir) if args.cache_dir else None

    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)

    started = datetime.now(timezone.utc).isoformat()
    load_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        artifact["repository"],
        revision=revision,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        trust_remote_code=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        artifact["repository"],
        revision=revision,
        cache_dir=cache_dir,
        local_files_only=local_files_only,
        trust_remote_code=False,
        torch_dtype=requested_dtype,
        use_safetensors=True,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    model.eval()
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    load_seconds = time.perf_counter() - load_start

    encoded = tokenizer(
        args.prompt,
        return_tensors="pt",
        add_special_tokens=True,
        truncation=True,
        max_length=args.max_tokens,
    )
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded.get("attention_mask")
    if attention_mask is not None:
        attention_mask = attention_mask.to(device)
    if input_ids.shape[1] < 2:
        raise RuntimeError("benchmark prompt must tokenize to at least two tokens")

    durations: list[float] = []
    losses: list[float] = []
    with torch.inference_mode():
        for index in range(args.warmup + args.repeats):
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            forward_start = time.perf_counter()
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                use_cache=False,
            )
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            duration = time.perf_counter() - forward_start
            shift_logits = outputs.logits[:, :-1, :].float()
            shift_labels = input_ids[:, 1:]
            loss = functional.cross_entropy(
                shift_logits.reshape(-1, shift_logits.shape[-1]),
                shift_labels.reshape(-1),
            )
            if index >= args.warmup:
                durations.append(duration)
                losses.append(float(loss.item()))
            del outputs, shift_logits, shift_labels, loss

    input_tokens = int(input_ids.numel())
    mean_seconds = sum(durations) / len(durations)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    gpu_record: dict[str, Any] | None = None
    if device.type == "cuda":
        gpu_record = {
            "name": torch.cuda.get_device_name(device),
            "capability": list(torch.cuda.get_device_capability(device)),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(device),
            "total_memory_bytes": torch.cuda.get_device_properties(
                device
            ).total_memory,
        }

    report = {
        "schema_version": 1,
        "mode": "execute",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "artifact_id": artifact["id"],
        "repository": artifact["repository"],
        "revision": revision,
        "checkpoint_ref": artifact.get("checkpoint_ref"),
        "network_download_permitted": args.allow_download,
        "local_files_only": local_files_only,
        "device": str(device),
        "requested_dtype": args.dtype,
        "model_dtype": str(next(model.parameters()).dtype),
        "parameter_count": parameter_count,
        "load_seconds": load_seconds,
        "prompt_sha256": __import__("hashlib").sha256(
            args.prompt.encode("utf-8")
        ).hexdigest(),
        "input_tokens": input_tokens,
        "warmup_repeats": args.warmup,
        "measured_repeats": args.repeats,
        "forward_seconds": durations,
        "mean_forward_seconds": mean_seconds,
        "tokens_per_second": input_tokens / mean_seconds,
        "mean_next_token_cross_entropy": sum(losses) / len(losses),
        "process_max_rss_bytes": _max_rss_bytes(),
        "gpu": gpu_record,
        "software": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
        },
    }

    del model, tokenizer, input_ids, attention_mask
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or execute an unquantized model loading/logits benchmark "
            "using the committed model manifest."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "artifacts" / "manifests" / "MODEL_MANIFEST.json",
    )
    parser.add_argument("--artifact", required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="load the model; without this flag the command is a no-network plan",
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="permit Transformers to download missing files during execution",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default="cuda",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "float16", "bfloat16", "float32"),
        default="auto",
    )
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument(
        "--prompt",
        default=(
            "In the fictional city of Lume, inspectors compare two reports "
            "before approving a reversible infrastructure test."
        ),
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.max_tokens < 2 or args.warmup < 0 or args.repeats < 1:
        print("error: invalid token or repeat settings", file=sys.stderr)
        return 2
    if args.allow_download and not args.execute:
        print(
            "error: --allow-download is meaningful only with --execute",
            file=sys.stderr,
        )
        return 2

    try:
        manifest = dict(load_model_manifest(args.manifest))
        errors = validate_model_manifest(manifest)
        if errors:
            raise ValueError("; ".join(errors))
        artifact = _artifact(manifest, args.artifact)
        report = (
            _execute(args, artifact)
            if args.execute
            else _plan(artifact, args.allow_download)
        )
    except (OSError, RuntimeError, ValueError) as error:
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
