# ChronoPersona Progress

**Last updated:** 2026-08-20T05:20:35-04:00

## Decision

Preserve the first frozen tiny-LoRA control as a target failure and consume the
single permitted rescue on a separately versioned v1 attention policy. The v1
profile changes only the run name and attention execution: Transformers
`sdpa`, PyTorch `SDPBackend.MATH`, and reduced-precision FP16/BF16 math-SDPA
reduction disabled. If v1 fails, stop the local training path; there is no v2
tuning rescue.

## Current objective

Commit, validate, publish, and execute the exact v1 five-step LoRA control plus
planned step-three interruption/resume gate on the verified immutable Pythia
snapshot. Require exact semantic equality between uninterrupted and resumed
conditions, or preserve one final actionable failure.

## Current verified boundary

- **Repository implementation — Tested:** exact head
  `f2568ab47d3162cf99eb445feac1b711980ff4f4` passed 344 tests with one
  optional skip in a clean detached worktree. The pilot, model-manifest, and
  development-evaluation validators and no-network training plan passed.
- **Delivery — Tested:** stacked draft PR #31 is open at `f2568ab`; all 18
  exact-head checks passed. Draft PR #30 remains green at the successful
  inference head. Agents are not authorized to merge either PR.
- **Artifact — Tested:** the exact five-file Pythia snapshot at revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2` remains hash verified and
  offline. The 2,090,701,528-byte safetensors SHA-256 is
  `fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13`.
- **Inference — Target Verified:** Pythia loads unquantized in CUDA FP16 on the
  RTX 2060 and produces finite logits on the bounded synthetic probe.
- **Training v0 — Target Failed:** exact run
  `run-b035b9becad60b6dc55ff3fd6fba6016` failed on the first forced-eager
  forward with non-finite loss. It completed zero steps and zero training
  tokens; no backward or optimizer update ran. Its run tree and evidence are
  immutable and must not be resumed or overwritten.
- **Diagnosis — Inspected/Target diagnostic:** on the same model and exact
  first 128-token block, eager attention remained non-finite after removing
  LoRA and across prefix lengths 16–128. Automatic, explicit MATH-only, and
  explicit efficient SDPA produced finite logits/loss. This localizes the
  observed cause to attention implementation. A specific FP16 overflow
  intermediate remains inferred rather than directly measured.
- **Training v1 — Tested locally, Target Unverified:** dependency-free tests
  now bind the entire SDPA policy, preserve pre-backward numeric evidence, and
  isolate v0/v1 outputs. No v1 backward or optimizer step has run.

## Evidence

- Failed v0 run: `run-b035b9becad60b6dc55ff3fd6fba6016`
- Failed v0 plan SHA-256:
  `c97329c4c64f0fedd37f940eae37bfb061e949fbb8527557c4014fa23e2dcf0d`
- Failed attempt semantic SHA-256:
  `84ab0221299779a66d6a44196382a0edb8358274f440df87f68d0b4b0d86c2ad`
- Failed CLI report SHA-256:
  `6405a6e68138250c39fb70988075e1cbe39a7b7bbf495e3b5a2e74f3ae67c347`
- Exact token matrix SHA-256:
  `e7ecab791e9e736c980e61639b20a1cf9bfd7701c81c1757ed51a49e644683ea`
- Diagnostic envelope:
  `reports/stage0/pythia_lora_attention_diagnostic_2026-08-20.json`
- Decision: `docs/DECISIONS.md` D-029
- Compute ledger: failed v0 row appended; v1 remains absent until observed.

## Artifacts

- Frozen historical config: `configs/runs/pythia-lora-smoke-v0.json`
- Sole rescue config: `configs/runs/pythia-lora-smoke-v1.json`
- Active plan: `.agent/plans/active-pythia-local-feasibility.md`
- Protocol: `docs/LOCAL_BENCHMARK_PROTOCOL.md`
- Inference report: `reports/stage0/pythia_local_inference_2026-08-20.md`
- Local ignored cache: `artifacts/local/hf-cache`
- Preserved v0 run tree in the detached execution worktree:
  `runs/pythia-lora-smoke-v0/control/run-b035b9becad60b6dc55ff3fd6fba6016`

## Validation

- Current uncommitted v1 rescue focused suite: benchmark/training/CLI tests
  pass; full exact-commit validation is pending the scoped commit.
- PyTorch minimum for model execution is now 2.5 because the frozen reduction-
  policy setter/getter is unavailable in 2.3–2.4. The installed target runtime
  is `2.13.0+cu130` with Transformers 5.15.1.
- The successful exact-head v1 load report must explicitly prove `sdpa`,
  `sdpa_backends=["math"]`, and disabled reduced-precision math reduction.
  Older automatic-SDPA reports are invalid inputs to v1.

## Risks

- The MATH backend may use more activation memory than automatic efficient
  SDPA. All original conservative VRAM, allocation, wall-time, disk, identity,
  finite-value, and stability gates remain enforced.
- Free RAM/VRAM can drift on this daily-use Windows host. Available host RAM is
  observed but not thresholded under the user's explicit instruction; actual
  allocation failure, severe paging, thermal, or driver instability still
  stops the run.
- The diagnosis is an engineering result, not evidence about model behavior,
  temporal priors, training adequacy, or CSTG.
- The original primary worktree contains unrelated `AGENTS.md` and untracked
  PR-template state. Preserve and exclude both from scoped commits.

## Delivery state

- Branch: `feat/tiny-training-resume-gate`
- Current published head: `f2568ab47d3162cf99eb445feac1b711980ff4f4`
- Draft PR #31:
  `https://github.com/Parm-1/ChronoPersona/pull/31`
- No merge, release, repository-visibility change, paid operation, model/data
  publication, or third-party contact was performed.

## Next write-active deliverable

Finish the scoped v1 rescue commit, validate it from a clean exact-head
worktree, push it to draft PR #31, and require exact-head CI. Then:

1. capture a fresh cache-bound audit;
2. regenerate the offline inference report under the explicit MATH-only policy;
3. run the uninterrupted v1 control;
4. if it passes, run the planned step-three interruption and explicit resume;
5. verify both conditions and compare exact semantic state;
6. update the ledger, decision, plan, and this file from observed evidence.

Stop permanently on any v1 integrity, numeric, memory, update, checkpoint,
resume, stability, or wall-time failure. Do not change another variable.
