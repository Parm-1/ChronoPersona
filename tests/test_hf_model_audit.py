import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_hf_model.py"


def _module():
    spec = importlib.util.spec_from_file_location("audit_hf_model", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_binary_sizes_separate_optimizer_and_alternative_formats() -> None:
    siblings = [
        {"filename": "model.safetensors", "size": 100},
        {"filename": "pytorch_model.bin", "size": 110},
        {"filename": "optimizer.pt", "size": 600},
        {"filename": "alternate/model.safetensors", "size": 200},
    ]

    summary = _module()._binary_size_summary(siblings)

    assert summary["safetensors_file_bytes"] == 300
    assert summary["pytorch_bin_file_bytes"] == 110
    assert summary["optimizer_state_file_bytes"] == 600
    assert summary["training_state_file_bytes"] == 600
    assert summary["model_binary_file_bytes"] == 410
    assert summary["minimum_root_inference_format_bytes"] == 100


def test_sharded_safetensors_are_summed_as_one_root_format() -> None:
    siblings = [
        {"filename": "model-00001-of-00002.safetensors", "size": 150},
        {"filename": "model-00002-of-00002.safetensors", "size": 100},
    ]

    summary = _module()._binary_size_summary(siblings)

    assert summary["minimum_root_inference_format_bytes"] == 250


def test_training_state_and_unknown_binaries_are_not_inference_weights() -> None:
    siblings = [
        {"filename": "optimizer.safetensors", "size": 10},
        {"filename": "state/optimizer.bin", "size": 11},
        {"filename": "training_args.bin", "size": 12},
        {"filename": "scheduler.pt", "size": 13},
        {"filename": "rng_state.pth", "size": 14},
        {"filename": "weights.ckpt", "size": 15},
        {"filename": "tensor_dump.safetensors", "size": 16},
    ]

    summary = _module()._binary_size_summary(siblings)

    assert summary["optimizer_state_file_bytes"] == 21
    assert summary["other_training_state_file_bytes"] == 39
    assert summary["training_state_file_bytes"] == 60
    assert summary["unclassified_binary_file_bytes"] == 31
    assert summary["model_binary_file_bytes"] == 0
    assert summary["minimum_root_inference_format_bytes"] is None
    assert summary["binary_classification"] == "known-filename-markers-v1"
