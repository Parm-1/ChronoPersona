# Pythia LoRA Checkpoint/Resume Gate

**Decision:** Accept the v1 SDPA-MATH run as **Target Verified** evidence for
the bounded trainer, checkpoint, interruption, and exact-resume engineering
path on this machine. Close the one-rescue gate without a v2. Preserve the v0
eager-attention failure as a separate immutable result. This does not authorize
or support a temporal, behavioral, PEFT-adequacy, or CSTG claim.

## Evidence

- **Observed — exact execution identity:** clean detached head
  `3f03885b0237933ffb2b2f2a68bcf0e8f168a5d3` used the immutable
  `EleutherAI/pythia-1b-deduped` revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`. All five required files
  totaling 2,092,816,302 bytes were rehashed before each offline load. The
  2,090,701,528-byte safetensors digest was
  `fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13`.
- **Observed — frozen rescue policy:** both the load probe and training runs
  resolved Transformers `sdpa`, constrained PyTorch SDPA to
  `SDPBackend.MATH`, and disabled reduced-precision FP16/BF16 math-SDPA
  reduction. The base had 1,011,781,632 frozen FP16 parameters; 524,288 FP32
  LoRA parameters were trainable.
- **Observed — uninterrupted control:** run
  `run-1b8f0867fbd6038265f609b3595ae93d` completed five unique optimizer
  steps, 640 input tokens, and 635 causal targets. Its losses were
  `[2.2249343395, 2.2572944164, 2.2881205082, 2.2311472893,
  2.3081409931]`; every logits/loss, gradient, parameter, and update check was
  finite and no update was skipped.
- **Observed — planned interruption and resume:** the matched resumed
  condition committed an atomic step-three checkpoint, published a structured
  planned-interruption failure, then loaded and verified that checkpoint in a
  fresh invocation before completing steps four and five. The checkpoint was
  6,335,483 bytes. Its step-three event binding was
  `263502220974c9e0652e0260e13f50cf1fab29b6ed3eaf234ca59203070f84d6`.
- **Observed — exact equality:** independent verification passed for both
  conditions. The comparator returned `status="equal"`; the final manifest
  SHA-256 was
  `78ae0dd9272e6d046c237cf2b10243691098c70234a8b3db2f1c353b347f365a`
  in both runs. Adapter weights, complete state, optimizer, scheduler, scaler,
  CPU RNG, CUDA RNG, counters, and the loss sequence had identical semantic
  hashes. The adapter file digest was
  `b42ff53b7a264068f41b6827aa59182587ddeb3644ccff802ba3b5555051b3eb`.
- **Observed — bounded resources:** maximum allocated/reserved CUDA memory was
  2,203,960,320 / 2,275,409,920 bytes in both conditions. Maximum process RSS
  was 2,800,746,496 bytes for control and 2,807,263,232 bytes for resumed.
  Control and resumed checkpoint save/round-trip validation took 0.109717 and
  0.099728 seconds respectively. Input throughput derived from recorded
  optimizer-step timings was 571.34 tokens/second for control and 398.06
  tokens/second for the two-invocation interrupted/resumed condition. The
  resume used the explicit host-RAM threshold override; disk, VRAM, runtime,
  identity, hash, and finite-value gates remained enforced and passed.
- **Observed — containment:** resource audits, training, verify, and compare
  evidence records `network_access_performed=false`; the load report
  separately records `network_download_permitted=false` and
  `local_model_load_only=true`. No paid compute, public model/data release,
  repository visibility change, or scientific run occurred.

## Artifacts

Generated machine/run evidence remains ignored local state in the clean
execution worktree. These file hashes bind this concise tracked report to that
evidence without committing weights, checkpoints, or machine-specific JSON.

| Artifact | File SHA-256 |
|---|---|
| `artifacts/local/resource-audit-training-v1-head.json` | `1b35a730619eed35c4416a42b348fedc66a1264173e136448b9b6eae7b701b6c` |
| `artifacts/local/pythia-main-cuda-training-v1-head.json` | `984eceb60c5e7fe5c2680ce2f2f6ba2f3a8b5f3c069842c5cae7aa0c62da743d` |
| `artifacts/local/resource-audit-lora-v1-control.json` | `5118dfec8a308046974f595aa9669e760a511baa66f1d8dff1a5dcb8a74b1f41` |
| `artifacts/local/pythia-lora-v1-control.json` | `168246127e108c0d31b24fa119cc4614588fb2fe031dbe7e71780c08bd0b24fb` |
| `artifacts/local/resource-audit-lora-v1-interrupt.json` | `d400e87f95281eab00d1f0321c485138a9f5526826c8790fa0bdf4f494386b53` |
| `artifacts/local/pythia-lora-v1-interrupted.json` | `55c68ec9867421c16f325d9163a314a7ffe7e48c9374e3503750d08090e8c56f` |
| `artifacts/local/resource-audit-lora-v1-resume.json` | `f57b32fa65b5c2fde7d5af562489286d498391bf767c9673b449a601382ad52f` |
| `artifacts/local/pythia-lora-v1-resumed.json` | `b46ab587886ec28aac79f510c515248320ece5f02896758c1fe392c872ad883c` |
| `artifacts/local/pythia-lora-v1-control-verify.json` | `827bddf921e41b278e408450aa11d5c8d1796641f95bb5d8bb5f5db8eba80406` |
| `artifacts/local/pythia-lora-v1-resumed-verify.json` | `e95905047222245d28f23e9b30ef359293690c2c0f2d2a5e3428d0c7e4be183a` |
| `artifacts/local/pythia-lora-v1-comparison.json` | `d527b191fb5b0a22b4f80d7e0ad860aca4e51f4088c6251953c10358ea4478a8` |
| `runs/pythia-lora-smoke-v1/control/run-1b8f0867fbd6038265f609b3595ae93d/events.jsonl` | `f346977b34e427b73a6d612101461e068b3bd1fd7e01c50961ae99c2f71972f4` |
| `runs/pythia-lora-smoke-v1/resumed/run-1b8f0867fbd6038265f609b3595ae93d/events.jsonl` | `15017dec1b72771c198b123658afcc81274fde7d324346352aaebe2ce73ba43b` |

## Validation

- Exact execution head: 354 tests passed with one optional skip in a clean
  detached worktree; the pilot, model-manifest, and development-evaluation
  validators and diff checks passed. The stored frozen no-network plan and its
  self-hash validated from both run identities.
- Draft PR #32: all 18 CI, content-integrity, and run-registry checks passed on
  exact head `3f03885` before this evidence-only update.
- Exact model execution: the explicit MATH-policy load report produced finite
  `[1,20,50304]` logits before training.
- Run verification: control and resumed event topologies, registry identity,
  snapshot and checkpoint hashes, runtime-step evidence, final artifacts, and
  terminal event bindings all passed the repository verifier.
- Provenance limitation: the standalone verify/compare CLI envelopes do not
  record the current Git head, run-root file hashes, or whether their forensic
  different-checkout override was requested. The enclosing clean-worktree
  audit and direct artifact verification bind this run, but a future schema
  hardening should make that provenance self-contained in each CLI envelope.

## Risks and claim ceiling

This result verifies only a five-step, batch-one, sequence-128 LoRA engineering
smoke on one RTX 2060 and the pinned software/runtime identity. It does not
establish sustained thermal stability, broad-update feasibility, model
capability after training, registry scorer validity, PEFT adequacy for the
causal design, source qualification, temporal effects, or CSTG. The original
v0 failure and the v1 pass jointly establish that attention execution was a
material numeric variable for this local path; they do not establish the exact
overflowing eager-attention intermediate.

## Next write-active deliverable

Integrate the existing registry tokenizer/scorer consumers with a reusable
manifest/hash-verified local-snapshot loader. Preserve no-network execution and
policy-first failure ordering, then run the bounded tokenizer and scoring gates
against the already verified Pythia snapshot. Rights-qualified A/B/C source
qualification remains a separate external blocker.
