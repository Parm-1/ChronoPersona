# Final Pythia Local Inference Measurement

**Decision:** The immutable final Pythia 1B deduped checkpoint is locally
viable for unquantized CUDA/FP16 loading and bounded logits work on the measured
RTX 2060. Advance only to a tiny LoRA training/checkpoint/resume engineering
smoke. Do not attempt a device-resident full-weight AdamW step on this GPU.

## Evidence

- **Observed — acquisition:** exact head `b8e0c5d699a8bf46548018ae803afb597524a336`
  acquired five required files totaling 2,092,816,302 bytes in 25.0 seconds.
  The resolved revision, exact file allowlist, every size and SHA-256, and the
  GPT-NeoX configuration passed. The 2,090,701,528-byte safetensors digest was
  `fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13`.
- **Observed — preserved resource stop:** the first offline attempt stopped at
  `live-resource-preflight`, before model import/load, when available RAM was
  3,281,063,936 bytes versus the conservative 4,181,403,056-byte threshold.
  Its structured result is retained rather than overwritten.
- **Observed — successful execution:** exact head
  `76c2479738d137d33d59d526a1392d17ceffe09a` loaded 1,011,781,632 FP16
  parameters on CUDA in 2.5291 seconds. Peak allocated/reserved GPU memory was
  2,042,486,784 / 2,084,569,088 bytes; peak process RSS was 2,810,875,904
  bytes.
- **Observed — logits:** the 20-token synthetic prompt produced finite logits
  with shape `[1, 20, 50304]`. Three measured passes averaged 0.014680 seconds,
  1,294.30 predicted tokens/second, and next-token cross-entropy 5.769263.
- **Observed — override semantics:** `--allow-low-ram` was explicitly requested
  and recorded, but both live checks exceeded the normal RAM threshold, so
  `ram_threshold_override_used` was false. Conservative free VRAM was 3,742
  MiB before model import, above the unchanged 3,136,052,292-byte threshold.
- **Inferred — full-weight optimizer capacity:** even an optimistic same-dtype
  AdamW lower bound needs 8 bytes per parameter for FP16 weights, gradients,
  and two FP16 moments: 8,094,253,056 bytes (7.538 GiB). That exceeds the
  6,441,992,192-byte device by 1,652,260,864 bytes before activations, CUDA
  context, allocator overhead, or any FP32 state. A device-resident full-weight
  AdamW step is therefore ruled out without intentionally causing an OOM.

## Artifacts

All generated evidence is ignored local state under `artifacts/local/`; no
weights or machine-specific JSON are committed.

| Artifact | SHA-256 |
|---|---|
| `resource-audit-authorized-pre-download-b8e0c5d.json` | `a19e47496c8c186e1a160a1efde26db102667ecfbc760d7c9c4d54e23b7bf171` |
| `pythia-main-acquisition-b8e0c5d.json` | `4f94a6e905f82029b7a7e7da9cbb4f42f223e329214380e763a3246d4ae778a8` |
| `resource-audit-authorized-post-download-b8e0c5d.json` | `b9ab42a5d147c19de85c077cea408ed76c445b96415e9710e3a417adf8843bd3` |
| `pythia-main-cuda-authorized-b8e0c5d.json` | `11522ec4ab0ba290c2f730bf19625ffe0a055f92ce245d53072c9b426b966e91` |
| `resource-audit-authorized-low-ram-76c2479.json` | `16c2222caf39605219326177b55838971b0a7fae6c33904acd42db46fa009201` |
| `pythia-main-cuda-low-ram-76c2479.json` | `b2e3581c80e3a7f424a305c393349269b03fdda348859466895fd192cad0fc68` |

## Validation

- Exact execution head: 304 passed, one optional skip.
- Pilot, model-manifest, and development-evaluation validators passed.
- Draft PR #30: all 18 CI, content-integrity, and run-registry jobs passed on
  the execution head.
- Network was disabled during model execution; the cached snapshot was rehashed
  before loading with `local_files_only=true` and `trust_remote_code=false`.

## Risks and claim ceiling

This is **Target Verified** only for bounded loading/logits on this machine and
environment. It does not establish sustained thermal stability, backward or
optimizer fit, checkpoint/resume correctness, registry scorer execution,
training adequacy, model behavior, temporal effects, or CSTG. The successful
prompt is a synthetic engineering probe, not an evaluation result.

## Next write-active deliverable

Implement and run one five-step, batch-one, sequence-128 LoRA engineering smoke
with a planned step-three interruption/resume and an uninterrupted control.
Require exact final adapter/optimizer/scheduler and loss-sequence equivalence.
Use only the verified offline snapshot and the existing CC0 synthetic neutral
fixtures. Record the device-resident full-weight AdamW capacity failure as a
separate result; do not substitute offload, quantization, or another optimizer
silently.
