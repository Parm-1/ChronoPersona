from __future__ import annotations

from types import SimpleNamespace

import pytest

from chronopersona.attention_policy import (
    attention_policy_record,
    math_sdpa_context,
)


def test_attention_policy_is_exact_and_configures_math_context() -> None:
    observed: dict[str, object] = {"allowed": True}

    def set_reduction(value: bool) -> None:
        observed["allowed"] = value

    def get_reduction() -> bool:
        return bool(observed["allowed"])

    torch = SimpleNamespace(
        backends=SimpleNamespace(
            cuda=SimpleNamespace(
                allow_fp16_bf16_reduction_math_sdp=set_reduction,
                fp16_bf16_reduction_math_sdp_allowed=get_reduction,
            )
        )
    )
    context = object()

    def sdpa_kernel(backend: object) -> object:
        observed["backend"] = backend
        return context

    assert math_sdpa_context(torch, sdpa_kernel, "MATH") is context
    assert observed == {"allowed": False, "backend": "MATH"}
    assert attention_policy_record() == {
        "attention_implementation": "sdpa",
        "sdpa_backends": ["math"],
        "sdpa_math_allow_fp16_reduction": False,
    }


def test_attention_policy_fails_closed_without_required_torch_api() -> None:
    torch = SimpleNamespace(backends=SimpleNamespace(cuda=SimpleNamespace()))

    with pytest.raises(RuntimeError, match="PyTorch 2.5 or later"):
        math_sdpa_context(torch, lambda _backend: object(), "MATH")
