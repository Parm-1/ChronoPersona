"""Dependency-light binding for the one frozen SDPA-MATH rescue policy."""

from __future__ import annotations

from typing import Any


ATTENTION_IMPLEMENTATION = "sdpa"
SDPA_BACKENDS = ("math",)
SDPA_MATH_ALLOW_FP16_REDUCTION = False


def attention_policy_record() -> dict[str, Any]:
    return {
        "attention_implementation": ATTENTION_IMPLEMENTATION,
        "sdpa_backends": list(SDPA_BACKENDS),
        "sdpa_math_allow_fp16_reduction": SDPA_MATH_ALLOW_FP16_REDUCTION,
    }


def math_sdpa_context(torch: Any, sdpa_kernel: Any, math_backend: Any) -> Any:
    """Enforce accumulation policy and return a MATH-only SDPA context."""

    set_math_reduction = getattr(
        torch.backends.cuda, "allow_fp16_bf16_reduction_math_sdp", None
    )
    get_math_reduction = getattr(
        torch.backends.cuda, "fp16_bf16_reduction_math_sdp_allowed", None
    )
    if not callable(set_math_reduction) or not callable(get_math_reduction):
        raise RuntimeError("the frozen math-SDPA policy requires PyTorch 2.5 or later")
    set_math_reduction(SDPA_MATH_ALLOW_FP16_REDUCTION)
    if (
        bool(get_math_reduction())
        is not SDPA_MATH_ALLOW_FP16_REDUCTION
    ):
        raise RuntimeError("failed to enforce the frozen math-SDPA reduction policy")
    return sdpa_kernel(math_backend)
