# ChronoPersona Progress

**Last updated:** 2026-08-20T04:49:51-04:00

## Current objective

Implement and run the smallest deterministic tiny LoRA continued-pretraining
and checkpoint/resume benchmark now that the immutable final Pythia 1B deduped
checkpoint has loaded and produced finite logits on the local RTX 2060.

## Current verified boundary

- **Repository tooling — Tested:** exact clean training implementation head
  `7b6398fe6f4fe8fcf55762b3cb246eb38468bf90` passed 344 local tests with one
  optional skip. The pilot, model-manifest, and development-evaluation
  validators and the self-hashed no-network training plan also passed. Draft PR
  #30 remains open at the successful inference head `92a3e09`, where all 18
  checks passed on Python 3.11, 3.12, and 3.13.
- **Artifact policy — Tested:** the manifest validates with 13 artifacts and
  exactly one benchmark-ready model, final Pythia 1B deduped at immutable Hub
  revision `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`.
- **Local runtime — Target Verified for bounded inference:** PyTorch
  `2.13.0+cu130` exposes CUDA 13.0 and the NVIDIA GeForce RTX 2060. A clean-
  head resource audit passed benchmark preflight. The exact five-file Pythia
  snapshot was independently verified, loaded unquantized in CUDA FP16, and
  produced finite logits in the frozen synthetic probe.
- **Training behavior — Tested in the dependency-free harness, Target
  Unverified:** the exact five-step state machine, planned interruption,
  checkpoint verification, resume, equality comparison, failure artifacts,
  locking, and path containment pass locally. No Pythia backward pass or
  optimizer step has run yet.

## Active deliverable

One five-step, batch-one, sequence-128 LoRA engineering smoke with a planned
step-three interruption/resume and an uninterrupted control. Final adapter,
optimizer, scheduler, loss sequence, step count, and token count must match.

## Next evidence gate

Publish the validated runner on a stacked draft PR and require exact-head CI.
Then reproduce the successful load at that clean head and execute the control
and interrupted/resumed conditions from the same verified offline snapshot and
token blocks.

- **Pass:** five optimizer updates complete in both conditions; checkpoint
  hashes validate; the resumed and uninterrupted semantic states and loss
  sequence match exactly; memory, throughput, and checkpoint timing are
  complete.
- **Fail:** integrity, nonfinite loss/gradient, skipped update, CUDA OOM,
  checkpoint mismatch, resume divergence, severe instability, thermal, or disk
  gate produces an actionable structured failure and stops the path.
- **Inconclusive:** interruption or an unrelated resource change invalidates
  the measurement; preserve partial cache state and repeat only after a fresh
  exact-head audit.

## Last known-good baseline

- Branch: `feat/tiny-training-resume-gate`
- Validated training implementation head:
  `7b6398fe6f4fe8fcf55762b3cb246eb38468bf90`
- Tested inference head: `76c2479738d137d33d59d526a1392d17ceffe09a`
- Upstream main: `78785b5c57b4bef306ac2d5632a191e97c5b6b0e`, which
  contains the externally merged PRs #28 and #29
- Delivery: draft PR #30 is open at `92a3e09` and passed all 18 checks; the
  training implementation commit is local and awaiting its own stacked draft
  PR.
- Execution worktree: detached, clean, and exactly bound to `7b6398f`

## Status

- Evidence level: bounded model loading/logits is Target Verified; training is
  Unverified.
- Delivery state: the earlier preflight implementation was merged through PR
  #29; acquisition/offline-load hardening and successful local inference are
  published in green draft PR #30. The training implementation is committed
  locally and exact-head validated but not yet pushed.
- Authorization: on 2026-08-20 the user explicitly lifted restrictions on
  model downloads and training. This authorizes local ChronoPersona model
  acquisition and bounded local training. No paid-compute budget, public model
  or dataset release, repository-visibility change, or third-party contact is
  required or inferred for this gate.
- Primary risk: the model consumes about 2.04 GB allocated VRAM before backward
  activations. LoRA is plausible but backward/checkpoint headroom is unmeasured.

## Current evidence by level

### Inspected

- The intended cache contains only the verified pinned Pythia snapshot and Hub
  cache metadata; approximately 251 GB remained free after acquisition.
- The exact five-file inference set is 2,092,816,302 bytes. The safetensors file
  is 2,090,701,528 bytes with SHA-256
  `fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13`.
- The exact 2.5x download safety margin is 5,232,040,755 bytes.
- Pythia is Apache-2.0 and does not require custom remote code at the pinned
  revision.

### Tested

- Benchmark safety tests cover canonical manifest binding, clean matching Git
  identity, explicit existing cache and audited directory identity, CUDA audit
  rejection, disk margin, Windows peak process memory, and structured failure
  context.
- The acquisition-integrity focused suite covers
  exact file hashes/allowlists, revision/config identity, audit recency,
  runtime/resource drift, exclusive evidence outputs, parent runtime identity,
  model/logits semantics, truncation rejection, and alternate-loader blocks.
- The combined training, CLI, acquisition, manifest, and alternate-loader suite
  passes 96 tests. The training/CLI subset passes 40 tests, including
  checkpoint tampering, Windows junction escape, OOM/nonfinite failures,
  transactional timeout rollback, global locking, exact event topology, and
  control/resume comparison.
- Exact clean implementation commit `7b6398f`: 344 passed, one skipped; pilot,
  model-manifest, development-evaluation validators, diff checks, and the
  no-network training plan passed.

### Integrated

- Exact-clean-head no-network resource audit and benchmark preflight completed
  on the RTX 2060.
- Local-only execution reached the model-load stage and preserved an expected
  missing-cache failure without network access.
- Exact-head acquisition completed in 25.0 seconds. All five required files,
  the immutable revision, exact allowlist, sizes, hashes, and config passed.
- The first offline execution preserved a structured pre-load RAM-gate failure:
  3,281,063,936 bytes available versus a 4,181,403,056-byte threshold, with
  3,764 MiB conservative free VRAM.
- The exact offline retry loaded 1,011,781,632 FP16 parameters in 2.5291
  seconds, peaked at 2,042,486,784 allocated / 2,084,569,088 reserved GPU bytes
  and 2,810,875,904 bytes process RSS, and produced finite `[1,20,50304]`
  logits. Three repeats averaged 0.014680 seconds, 1,294.30 predicted tokens/s,
  and loss 5.769263. The RAM override was requested but not needed.

### Missing or unverified

- Sustained thermals and desktop impact.
- Backward/optimizer memory, tiny-training throughput, checkpoint write, and
  exact resume behavior.

## Material changes and decisions

- The former model-acquisition authorization blocker is superseded by the
  user's 2026-08-20 instruction.
- Legal identity, artifact integrity, scientific gates, and resource stop
  conditions remain validity requirements, not permission restrictions.
- Start with one licensed immutable Pythia artifact; do not bulk-download the
  blocked DatedGPT, PIT, ChronoGPT, TypewriterLM, Kairos, or OLMo candidates.
- Continue at CAD $0 because the next gate is local and no paid resource is
  needed. A concrete paid operation would require its own bounded cost target.
- The user's follow-up authorizes using as much host RAM as needed. The retry
  will explicitly record and waive only the available-RAM threshold; GPU,
  disk, identity, integrity, and actual allocation-failure stops remain.
- Device-resident full-weight AdamW is infeasible: the optimistic
  8,094,253,056-byte state lower bound exceeds total GPU memory by
  1,652,260,864 bytes before activations. Use LoRA for the engineering smoke
  only; do not reinterpret it as the headline training method.

## Open uncertainties and regression risks

- Free VRAM and RAM can change because this is a daily-use Windows machine.
- Transformers/PyTorch loading compatibility is verified for the pinned model.
  Registry tokenizer/scoring execution remains deliberately
  blocked until it consumes the reusable hash-verified snapshot layer; plan
  mode remains available.
- A successful inference load does not imply full-weight training fits.
- Partial Hugging Face downloads must not be mistaken for a complete immutable
  artifact.
- PRs #28 and #29 were merged externally. Draft PR #30 covers the full
  inference path through `92a3e09` and is green. The new training branch must
  receive its own exact-head checks. Agents remain unauthorized to merge any
  PR.

## Workspace state

- The exact execution worktree at `7b6398f` is clean. The primary worktree has
  unrelated concurrent `AGENTS.md` and untracked PR-template changes whose
  provenance is not part of this deliverable; they are preserved and excluded
  from commits and model-run identity.
- Ignored cache: `artifacts/local/hf-cache` contains the verified 2.09 GB
  pinned snapshot.
- Ignored evidence: resource audits and structured failure reports under
  `artifacts/local/`.
- No model, training, or background benchmark process is active.
- Successful-run resources: 6,144 MiB total VRAM; 3,742 MiB conservative free
  before load; 2,042,486,784 peak allocated model/logits bytes; approximately
  251 GB free disk.
- External writes by agents so far: branches and draft PRs #28, #29, and #30.
  PRs #28 and #29 were subsequently merged by an external actor; no agent
  performed a merge, release, visibility change, paid operation, or public
  model/data publication.

## Active plan and evidence

- Active plan: `.agent/plans/active-pythia-local-feasibility.md`
- Decision report: `reports/stage0/model_compute_preflight_2026-08-20.md`
- Inference result: `reports/stage0/pythia_local_inference_2026-08-20.md`
- Model protocol: `docs/LOCAL_BENCHMARK_PROTOCOL.md`

## Exact restart instructions

1. Commit this reconciled state on `feat/tiny-training-resume-gate` without
   staging the unrelated primary-worktree files.
2. Push the branch, open a stacked draft PR against
   `fix/model-feasibility-gates`, and wait for exact-head CI without merging.
3. Capture a fresh exact-head resource audit and a new successful load report;
   do not reuse the older Git-bound audit as current evidence.
4. Run one uninterrupted control and one planned step-three interruption plus
   explicit resume. Stop on any declared failure and preserve both output roots.
5. Verify and compare both conditions, then update the compute ledger and
   decision record from the observed result.
