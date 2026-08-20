"""Lazy direct-Torch backend for the bounded Pythia LoRA training gate."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
import gc
import math
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

from .run_registry import canonical_sha256
from .training_smoke import (
    StepResult,
    TrainingCheckpointState,
    TrainingPlan,
    TrainingSmokeError,
)


def _max_rss_bytes() -> int | None:
    if platform.system() == "Windows":
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("page_fault_count", wintypes.DWORD),
                ("peak_working_set_size", ctypes.c_size_t),
                ("working_set_size", ctypes.c_size_t),
                ("quota_peak_paged_pool_usage", ctypes.c_size_t),
                ("quota_paged_pool_usage", ctypes.c_size_t),
                ("quota_peak_nonpaged_pool_usage", ctypes.c_size_t),
                ("quota_nonpaged_pool_usage", ctypes.c_size_t),
                ("pagefile_usage", ctypes.c_size_t),
                ("peak_pagefile_usage", ctypes.c_size_t),
            ]
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCounters),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            success = psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            )
        except (AttributeError, OSError):
            return None
        return int(counters.peak_working_set_size) if success else None
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)


def _nvidia_free_bytes() -> int:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.free",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise TrainingSmokeError(f"cannot capture conservative GPU memory: {error}") from error
    if result.returncode != 0:
        raise TrainingSmokeError("nvidia-smi failed during training resource check")
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        raise TrainingSmokeError("training requires exactly one visible nvidia-smi GPU")
    fields = [field.strip() for field in rows[0].split(",")]
    if len(fields) != 2 or fields[0] != "0":
        raise TrainingSmokeError("cannot bind nvidia-smi free memory to GPU 0")
    try:
        return int(fields[1]) * 1024 * 1024
    except ValueError as error:
        raise TrainingSmokeError("nvidia-smi returned invalid free memory") from error


def _optimizer_step_values(optimizer: Any) -> tuple[int, ...]:
    values: list[int] = []
    for parameter_group in optimizer.param_groups:
        for parameter in parameter_group["params"]:
            state = optimizer.state.get(parameter, {})
            raw = state.get("step", 0)
            if hasattr(raw, "item"):
                raw = raw.item()
            values.append(int(raw))
    return tuple(values)


def _tensor_bytes(torch: Any, value: Any) -> int:
    if torch.is_tensor(value):
        return int(value.numel()) * int(value.element_size())
    if isinstance(value, Mapping):
        return sum(_tensor_bytes(torch, item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_tensor_bytes(torch, item) for item in value)
    return 0


class TorchTrainingBackend:
    """Direct FP32-adapter/FP16-base LoRA backend with no network path."""

    def __init__(
        self,
        plan: TrainingPlan,
        snapshot_path: str | Path,
        resume_state: TrainingCheckpointState | None = None,
    ) -> None:
        if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
            raise TrainingSmokeError("offline environment must be set before the training runtime")
        expected_workspace = plan.config["determinism"]["cublas_workspace_config"]
        if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != expected_workspace:
            raise TrainingSmokeError("CUBLAS_WORKSPACE_CONFIG was not frozen before Torch import")

        try:
            import torch
            import torch.nn.functional as functional
            import transformers
            from safetensors.torch import save as save_safetensors
            from transformers import AutoModelForCausalLM
        except ImportError as error:
            raise TrainingSmokeError("install the ChronoPersona models dependencies") from error

        self.torch = torch
        self.functional = functional
        self.transformers = transformers
        self._save_safetensors = save_safetensors
        self.plan = plan
        self.snapshot_path = Path(snapshot_path).resolve(strict=True)
        self.device = torch.device("cuda")
        self._started = time.perf_counter()
        self._load_seconds = 0.0
        self._postload_conservative_free_bytes = 0
        self._prestep_conservative_free_bytes: int | None = None
        self._has_run_step = False

        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise TrainingSmokeError("training requires exactly one available CUDA device")
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.set_float32_matmul_precision("highest")
        seed = int(plan.config["seed"])
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.cuda.empty_cache()

        load_start = time.perf_counter()
        model = AutoModelForCausalLM.from_pretrained(
            self.snapshot_path,
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.float16,
            use_safetensors=True,
            low_cpu_mem_usage=True,
            attn_implementation="eager",
        )
        model.to(self.device)
        torch.cuda.synchronize(self.device)
        self._load_seconds = time.perf_counter() - load_start
        artifact = plan.plan["artifact"]
        if type(model).__name__ != artifact["architecture"]:
            raise TrainingSmokeError("loaded training model architecture mismatch")
        if getattr(model.config, "model_type", None) != artifact["model_type"]:
            raise TrainingSmokeError("loaded training model type mismatch")
        parameter_count = sum(parameter.numel() for parameter in model.parameters())
        if parameter_count != artifact["parameter_count"]:
            raise TrainingSmokeError("loaded training model parameter count mismatch")
        if {str(parameter.dtype) for parameter in model.parameters()} != {"torch.float16"}:
            raise TrainingSmokeError("loaded training base is not uniformly float16")

        self.model = model
        self._base_parameters = tuple(model.named_parameters())
        base_signature = [
            {
                "name": name,
                "shape": [int(size) for size in parameter.shape],
                "dtype": str(parameter.dtype),
            }
            for name, parameter in self._base_parameters
        ]
        model_weight = next(
            item for item in artifact["required_files"] if item["filename"] == "model.safetensors"
        )
        self._base_identity_sha256 = canonical_sha256(
            {
                "revision": artifact["revision"],
                "weight_sha256": model_weight["sha256"],
                "parameter_signature": base_signature,
            }
        )
        for _, parameter in self._base_parameters:
            parameter.requires_grad_(False)

        # Reset immediately before adapter initialization so model loading cannot
        # influence the frozen adapter initialization stream.
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        self._inject_lora()
        self._base_versions = {
            name: int(parameter._version) for name, parameter in self._base_parameters
        }
        self._validate_parameter_boundary()

        self.model.config.use_cache = False
        self.model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        self.model.enable_input_require_grads()
        self.model.train()
        optimizer_config = plan.config["optimizer"]
        self.optimizer = torch.optim.AdamW(
            [parameter for _, parameter in self._adapter_named_parameters],
            lr=float(optimizer_config["learning_rate"]),
            betas=tuple(float(value) for value in optimizer_config["betas"]),
            eps=float(optimizer_config["epsilon"]),
            weight_decay=float(optimizer_config["weight_decay"]),
            amsgrad=bool(optimizer_config["amsgrad"]),
            maximize=bool(optimizer_config["maximize"]),
            foreach=bool(optimizer_config["foreach"]),
            capturable=bool(optimizer_config["capturable"]),
            differentiable=bool(optimizer_config["differentiable"]),
            fused=bool(optimizer_config["fused"]),
        )
        scheduler_factor = float(plan.config["scheduler"]["factor"])
        self.scheduler = torch.optim.lr_scheduler.LambdaLR(
            self.optimizer, lr_lambda=lambda _step: scheduler_factor
        )
        gradient_config = plan.config["gradient"]
        self.scaler = torch.amp.GradScaler(
            "cuda",
            init_scale=float(gradient_config["scaler_init_scale"]),
            growth_factor=float(gradient_config["scaler_growth_factor"]),
            backoff_factor=float(gradient_config["scaler_backoff_factor"]),
            growth_interval=int(gradient_config["scaler_growth_interval"]),
            enabled=bool(gradient_config["scaler_enabled"]),
        )
        if resume_state is not None:
            self._restore(resume_state)

        torch.cuda.synchronize(self.device)
        torch_free, _ = torch.cuda.mem_get_info(self.device)
        self._postload_conservative_free_bytes = min(int(torch_free), _nvidia_free_bytes())
        minimum_postload = int(
            plan.config["resource_limits"]["minimum_postload_global_free_vram_bytes"]
        )
        if self._postload_conservative_free_bytes < minimum_postload:
            raise TrainingSmokeError("post-load global free VRAM is below the frozen threshold")
        self._condition_peak_allocated_bytes = int(
            torch.cuda.max_memory_allocated(self.device)
        )
        self._condition_peak_reserved_bytes = int(
            torch.cuda.max_memory_reserved(self.device)
        )
        torch.cuda.reset_peak_memory_stats(self.device)

    @property
    def base_identity_sha256(self) -> str:
        return self._base_identity_sha256

    @property
    def runtime_summary(self) -> dict[str, Any]:
        return {
            "model_load_seconds": self._load_seconds,
            "postload_conservative_free_vram_bytes": self._postload_conservative_free_bytes,
            "prestep_conservative_free_vram_bytes": self._prestep_conservative_free_bytes,
            "peak_allocated_bytes": self._condition_peak_allocated_bytes,
            "peak_reserved_bytes": self._condition_peak_reserved_bytes,
            "process_max_rss_bytes": _max_rss_bytes(),
            "torch": str(self.torch.__version__),
            "transformers": str(self.transformers.__version__),
        }

    def _inject_lora(self) -> None:
        torch = self.torch
        functional = self.functional
        lora = self.plan.config["lora"]
        rank = int(lora["rank"])
        scale = float(lora["alpha"]) / rank

        class LoRALinear(torch.nn.Module):
            def __init__(self, base: Any) -> None:
                super().__init__()
                self.base = base
                self.lora_A = torch.nn.Parameter(
                    torch.empty(rank, base.in_features, device=base.weight.device, dtype=torch.float32)
                )
                self.lora_B = torch.nn.Parameter(
                    torch.zeros(base.out_features, rank, device=base.weight.device, dtype=torch.float32)
                )
                torch.nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

            def forward(self, inputs: Any) -> Any:
                base_output = self.base(inputs)
                with torch.autocast(device_type="cuda", enabled=False):
                    hidden = functional.linear(inputs.float(), self.lora_A)
                    delta = functional.linear(hidden, self.lora_B)
                return base_output + (delta * scale).to(base_output.dtype)

        targets = [
            lora["target_template"].format(layer=layer)
            for layer in lora["target_layers"]
        ]
        observed: list[str] = []
        for target in targets:
            parent_name, child_name = target.rsplit(".", 1)
            parent = self.model.get_submodule(parent_name)
            base = getattr(parent, child_name)
            if type(base) is not torch.nn.Linear:
                raise TrainingSmokeError(f"LoRA target is not an exact Linear: {target}")
            setattr(parent, child_name, LoRALinear(base))
            observed.append(target)
        if observed != targets or len(observed) != int(lora["target_count"]):
            raise TrainingSmokeError("LoRA target set mismatch")
        adapter_named = sorted(
            (
                (name, parameter)
                for name, parameter in self.model.named_parameters()
                if name.endswith(".lora_A") or name.endswith(".lora_B")
            ),
            key=lambda item: item[0],
        )
        self._adapter_named_parameters = adapter_named
        self._adapter_names = tuple(name for name, _ in adapter_named)
        trainable = sum(parameter.numel() for _, parameter in adapter_named)
        if trainable != int(lora["trainable_parameters"]):
            raise TrainingSmokeError(
                f"LoRA trainable parameter count mismatch: observed {trainable}"
            )
        if any(parameter.dtype != torch.float32 for _, parameter in adapter_named):
            raise TrainingSmokeError("LoRA adapters must remain float32")

    def _validate_parameter_boundary(self) -> None:
        trainable_names = {
            name for name, parameter in self.model.named_parameters() if parameter.requires_grad
        }
        if trainable_names != set(self._adapter_names):
            raise TrainingSmokeError("trainable parameter set is not exactly the LoRA adapters")
        for name, parameter in self._base_parameters:
            if parameter.requires_grad or parameter.grad is not None:
                raise TrainingSmokeError(f"frozen base parameter became mutable: {name}")
            expected_version = getattr(self, "_base_versions", {}).get(name)
            if expected_version is not None and int(parameter._version) != expected_version:
                raise TrainingSmokeError(f"frozen base parameter changed in place: {name}")

    def _restore(self, state: TrainingCheckpointState) -> None:
        torch = self.torch
        if sorted(state.adapter_state) != list(self._adapter_names):
            raise TrainingSmokeError("resume adapter key set mismatch")
        parameter_by_name = dict(self._adapter_named_parameters)
        with torch.no_grad():
            for name in self._adapter_names:
                source = state.adapter_state[name]
                destination = parameter_by_name[name]
                if tuple(source.shape) != tuple(destination.shape) or source.dtype != destination.dtype:
                    raise TrainingSmokeError(f"resume adapter tensor mismatch: {name}")
                destination.copy_(source.to(self.device))
        if set(state.optimizer_state) != {"parameter_names", "state_dict"}:
            raise TrainingSmokeError("resume optimizer state has invalid fields")
        if state.optimizer_state["parameter_names"] != list(self._adapter_names):
            raise TrainingSmokeError("resume optimizer parameter order mismatch")
        optimizer_state = state.optimizer_state["state_dict"]
        if not isinstance(optimizer_state, Mapping):
            raise TrainingSmokeError("resume optimizer state_dict must be an object")
        self.optimizer.load_state_dict(dict(optimizer_state))
        self.scheduler.load_state_dict(dict(state.scheduler_state))
        self.scaler.load_state_dict(dict(state.scaler_state))
        torch.set_rng_state(state.cpu_rng_state)
        if len(state.cuda_rng_states) != torch.cuda.device_count():
            raise TrainingSmokeError("resume CUDA RNG device count mismatch")
        torch.cuda.set_rng_state_all(list(state.cuda_rng_states))
        self._validate_parameter_boundary()

    def run_step(self, token_block: Sequence[int], step: int) -> StepResult:
        torch = self.torch
        if time.perf_counter() - self._started > float(
            self.plan.config["resource_limits"]["maximum_condition_wall_seconds"]
        ):
            raise TrainingSmokeError("training condition exceeded its wall-time limit")
        if len(token_block) != int(self.plan.config["sequence_length"]):
            raise TrainingSmokeError("runtime token block length mismatch")
        if not self._has_run_step:
            torch_free, _ = torch.cuda.mem_get_info(self.device)
            self._prestep_conservative_free_bytes = min(int(torch_free), _nvidia_free_bytes())
            minimum = int(
                self.plan.config["resource_limits"]["minimum_postload_global_free_vram_bytes"]
            )
            if self._prestep_conservative_free_bytes < minimum:
                raise TrainingSmokeError("pre-forward global free VRAM is below the frozen threshold")
            self._has_run_step = True

        input_ids = torch.tensor([list(token_block)], dtype=torch.long, device=self.device)
        self.optimizer.zero_grad(set_to_none=True)
        torch.cuda.synchronize(self.device)
        step_start_allocated = int(torch.cuda.memory_allocated(self.device))
        step_start_reserved = int(torch.cuda.memory_reserved(self.device))
        step_start = time.perf_counter()
        torch.cuda.reset_peak_memory_stats(self.device)
        forward_start = time.perf_counter()
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            outputs = self.model(input_ids=input_ids, labels=input_ids, use_cache=False)
            loss = outputs.loss
        torch.cuda.synchronize(self.device)
        forward_seconds = time.perf_counter() - forward_start
        forward_end_allocated = int(torch.cuda.memory_allocated(self.device))
        forward_end_reserved = int(torch.cuda.memory_reserved(self.device))
        forward_peak_allocated = int(torch.cuda.max_memory_allocated(self.device))
        forward_peak_reserved = int(torch.cuda.max_memory_reserved(self.device))
        if not bool(torch.isfinite(loss).item()):
            raise TrainingSmokeError("training loss is non-finite")

        torch.cuda.reset_peak_memory_stats(self.device)
        backward_start = time.perf_counter()
        self.scaler.scale(loss).backward()
        self.scaler.unscale_(self.optimizer)
        gradients = [parameter.grad for _, parameter in self._adapter_named_parameters]
        if any(gradient is None for gradient in gradients):
            raise TrainingSmokeError("an adapter gradient is missing")
        if not all(bool(torch.isfinite(gradient).all().item()) for gradient in gradients):
            raise TrainingSmokeError("an adapter gradient is non-finite")
        grad_norm = torch.nn.utils.clip_grad_norm_(
            [parameter for _, parameter in self._adapter_named_parameters],
            float(self.plan.config["gradient"]["max_norm"]),
            error_if_nonfinite=True,
        )
        torch.cuda.synchronize(self.device)
        backward_seconds = time.perf_counter() - backward_start
        backward_end_allocated = int(torch.cuda.memory_allocated(self.device))
        backward_end_reserved = int(torch.cuda.memory_reserved(self.device))
        backward_peak_allocated = int(torch.cuda.max_memory_allocated(self.device))
        backward_peak_reserved = int(torch.cuda.max_memory_reserved(self.device))

        torch.cuda.reset_peak_memory_stats(self.device)
        optimizer_start = time.perf_counter()
        expected_before = step - 1
        before_steps = _optimizer_step_values(self.optimizer)
        if any(value != expected_before for value in before_steps):
            raise TrainingSmokeError("optimizer step counters drifted before update")
        scale_before = float(self.scaler.get_scale())
        self.scaler.step(self.optimizer)
        self.scaler.update()
        scale_after = float(self.scaler.get_scale())
        if scale_after < scale_before:
            raise TrainingSmokeError("GradScaler skipped an optimizer update")
        after_steps = _optimizer_step_values(self.optimizer)
        if any(value != step for value in after_steps):
            raise TrainingSmokeError("optimizer did not perform exactly one update")
        self.scheduler.step()
        if int(self.scheduler.last_epoch) != step:
            raise TrainingSmokeError("scheduler step counter drifted")
        torch.cuda.synchronize(self.device)
        optimizer_seconds = time.perf_counter() - optimizer_start
        optimizer_end_allocated = int(torch.cuda.memory_allocated(self.device))
        optimizer_end_reserved = int(torch.cuda.memory_reserved(self.device))
        optimizer_peak_allocated = int(torch.cuda.max_memory_allocated(self.device))
        optimizer_peak_reserved = int(torch.cuda.max_memory_reserved(self.device))
        self._condition_peak_allocated_bytes = max(
            self._condition_peak_allocated_bytes,
            forward_peak_allocated,
            backward_peak_allocated,
            optimizer_peak_allocated,
        )
        self._condition_peak_reserved_bytes = max(
            self._condition_peak_reserved_bytes,
            forward_peak_reserved,
            backward_peak_reserved,
            optimizer_peak_reserved,
        )
        self._validate_parameter_boundary()
        for name, parameter in self._adapter_named_parameters:
            if not bool(torch.isfinite(parameter).all().item()):
                raise TrainingSmokeError(f"adapter parameter became non-finite: {name}")
        maximum_reserved = int(
            self.plan.config["resource_limits"]["maximum_process_peak_reserved_bytes"]
        )
        if self._condition_peak_reserved_bytes > maximum_reserved:
            raise TrainingSmokeError(
                "training peak reserved VRAM exceeded limit: "
                f"{self._condition_peak_reserved_bytes} > {maximum_reserved}"
            )
        observed_loss = float(loss.detach().float().item())
        step_seconds = time.perf_counter() - step_start
        optimizer_state_bytes = _tensor_bytes(torch, self.optimizer.state)
        adapter_parameter_bytes = sum(
            int(parameter.numel()) * int(parameter.element_size())
            for _, parameter in self._adapter_named_parameters
        )
        adapter_gradient_bytes = sum(
            int(parameter.grad.numel()) * int(parameter.grad.element_size())
            for _, parameter in self._adapter_named_parameters
            if parameter.grad is not None
        )
        del outputs, loss, input_ids
        return StepResult(
            loss=observed_loss,
            runtime_metrics={
                "forward_seconds": forward_seconds,
                "backward_seconds": backward_seconds,
                "optimizer_seconds": optimizer_seconds,
                "step_seconds": step_seconds,
                "input_tokens_per_second": len(token_block) / step_seconds,
                "gradient_norm": float(grad_norm.detach().float().item()),
                "loss_scale_before": scale_before,
                "loss_scale_after": scale_after,
                "optimizer_update_skipped": False,
                "learning_rate": float(self.scheduler.get_last_lr()[0]),
                "step_start_allocated_bytes": step_start_allocated,
                "step_start_reserved_bytes": step_start_reserved,
                "forward_end_allocated_bytes": forward_end_allocated,
                "forward_end_reserved_bytes": forward_end_reserved,
                "forward_peak_allocated_bytes": forward_peak_allocated,
                "forward_peak_reserved_bytes": forward_peak_reserved,
                "backward_end_allocated_bytes": backward_end_allocated,
                "backward_end_reserved_bytes": backward_end_reserved,
                "backward_peak_allocated_bytes": backward_peak_allocated,
                "backward_peak_reserved_bytes": backward_peak_reserved,
                "optimizer_end_allocated_bytes": optimizer_end_allocated,
                "optimizer_end_reserved_bytes": optimizer_end_reserved,
                "optimizer_peak_allocated_bytes": optimizer_peak_allocated,
                "optimizer_peak_reserved_bytes": optimizer_peak_reserved,
                "condition_peak_allocated_bytes": self._condition_peak_allocated_bytes,
                "condition_peak_reserved_bytes": self._condition_peak_reserved_bytes,
                "optimizer_state_tensor_bytes": optimizer_state_bytes,
                "adapter_parameter_bytes": adapter_parameter_bytes,
                "adapter_gradient_bytes": adapter_gradient_bytes,
                "process_max_rss_bytes": _max_rss_bytes(),
                "input_tokens": len(token_block),
                "causal_targets": len(token_block) - 1,
            },
        )

    def capture_state(
        self,
        *,
        completed_steps: int,
        cursor: int,
        tokens_seen: int,
        losses: Sequence[float],
    ) -> TrainingCheckpointState:
        torch = self.torch
        self._validate_parameter_boundary()
        adapter_state = {
            name: parameter.detach().cpu().contiguous().clone()
            for name, parameter in self._adapter_named_parameters
        }
        return TrainingCheckpointState(
            completed_steps=completed_steps,
            cursor=cursor,
            tokens_seen=tokens_seen,
            losses=tuple(float(loss) for loss in losses),
            adapter_state=adapter_state,
            optimizer_state={
                "parameter_names": list(self._adapter_names),
                "state_dict": self.optimizer.state_dict(),
            },
            scheduler_state=self.scheduler.state_dict(),
            scaler_state=self.scaler.state_dict(),
            cpu_rng_state=torch.get_rng_state().cpu().clone(),
            cuda_rng_states=tuple(state.cpu().clone() for state in torch.cuda.get_rng_state_all()),
        )

    def serialize_adapter(self, adapter_state: Mapping[str, Any]) -> bytes:
        ordered = {name: adapter_state[name].contiguous() for name in sorted(adapter_state)}
        return self._save_safetensors(ordered)

    def close(self) -> None:
        if not hasattr(self, "torch"):
            return
        for name in ("optimizer", "scheduler", "scaler", "model"):
            if hasattr(self, name):
                delattr(self, name)
        gc.collect()
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
