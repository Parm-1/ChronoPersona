# ChronoPersona Progress

**Last updated:** 2026-08-20T03:12:57-04:00

## Current objective

Establish whether the immutable final Pythia 1B deduped checkpoint can be
acquired, loaded unquantized, and scored on the local RTX 2060, then use that
measurement to decide whether a tiny continued-pretraining and checkpoint-
resume benchmark is locally viable.

## Current verified boundary

- **Repository tooling — Tested:** exact head
  `b8e0c5d699a8bf46548018ae803afb597524a336` passed 303 local tests with one
  optional skip. The pilot, model-manifest, and development-evaluation
  validators also passed against that exact clean commit. PR #29's prior head
  passed CI on Python 3.11, 3.12, and 3.13 and was merged externally; the new
  hardened head was published as draft PR #30 and all 18 exact-head checks
  passed. The low-RAM override requested after that run is pending validation.
- **Artifact policy — Tested:** the manifest validates with 13 artifacts and
  exactly one benchmark-ready model, final Pythia 1B deduped at immutable Hub
  revision `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`.
- **Local runtime — Integrated through immutable acquisition:** PyTorch
  `2.13.0+cu130` exposes CUDA 13.0 and the NVIDIA GeForce RTX 2060. A clean-
  head resource audit passed benchmark preflight and a local-only model load
  failed as expected because the explicit cache was empty. The exact five-file
  Pythia snapshot is now downloaded and independently verified.
- **Model behavior — Missing:** the first offline attempt stopped before model
  import/load at the conservative RAM gate; no logits or training has run.

## Active deliverable

One exact-head final-Pythia acquisition plus CUDA loading/logits benchmark with
structured success or failure evidence. This is an engineering feasibility
measurement, not a causal or behavioral research result.

## Next evidence gate

Commit and validate the explicit user-authorized low-RAM override, then repeat
the guarded offline CUDA benchmark against a fresh exact-head resource audit.
The verified snapshot remains offline and unchanged.

- **Pass:** immutable revision loads without remote code, logits complete, and
  load time, peak RAM/VRAM, dtype, parameter count, throughput, and loss are
  recorded.
- **Fail:** integrity, loader, CUDA, OOM/allocation, severe-instability, thermal,
  or disk gate
  produces an actionable structured failure; preserve the cache and stop that
  path before training.
- **Inconclusive:** interruption or an unrelated resource change invalidates
  the measurement; preserve partial cache state and repeat only after a fresh
  exact-head audit.

## Last known-good baseline

- Branch: `fix/model-feasibility-gates`
- Tested and acquired head: `b8e0c5d699a8bf46548018ae803afb597524a336`
- Upstream main: `78785b5c57b4bef306ac2d5632a191e97c5b6b0e`, which
  contains the externally merged PRs #28 and #29
- Delivery: draft PR #30 is open and its `b8e0c5d` head passed all 18 checks;
  the low-RAM override is not yet published
- Execution worktree: detached, clean, and exactly bound to the tested commit

## Status

- Evidence level: immutable acquisition is Integrated; model loading and
  training are Unverified after one pre-load resource stop.
- Delivery state: the earlier preflight implementation was merged through PR
  #29; acquisition/offline-load hardening is published in draft PR #30 and its
  exact head is green. The authorized load attempt has not reached model load.
- Authorization: on 2026-08-20 the user explicitly lifted restrictions on
  model downloads and training. This authorizes local ChronoPersona model
  acquisition and bounded local training. No paid-compute budget, public model
  or dataset release, repository-visibility change, or third-party contact is
  required or inferred for this gate.
- Primary risk: only 3,792 MiB of the 6,144 MiB GPU was free at reconciliation;
  headroom is dynamic and model fit remains unverified.

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
- The current acquisition-integrity focused suite passes 55 tests covering
  exact file hashes/allowlists, revision/config identity, audit recency,
  runtime/resource drift, exclusive evidence outputs, parent runtime identity,
  model/logits semantics, truncation rejection, and alternate-loader blocks.
- Exact clean implementation commit `d812ba8`: 303 passed, one skipped; pilot,
  model-manifest, and development-evaluation validators passed; the no-download
  Pythia plan resolved the expected 2,092,816,302-byte inference set and exact
  5,232,040,755-byte disk margin.

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

### Missing or unverified

- Successful model load/logits, peak load memory, and throughput.
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

## Open uncertainties and regression risks

- Free VRAM and RAM can change because this is a daily-use Windows machine.
- Transformers/PyTorch API compatibility is tested only up to the empty-cache
  loader boundary. Registry tokenizer/scoring execution is now deliberately
  blocked until it consumes the reusable hash-verified snapshot layer; plan
  mode remains available.
- A successful inference load does not imply full-weight training fits.
- Partial Hugging Face downloads must not be mistaken for a complete immutable
  artifact.
- PRs #28 and #29 were merged externally. Draft PR #30 covers the hardening
  work, but its `b8e0c5d` checks do not cover the new low-RAM override; update
  and recheck it. Agents remain unauthorized to merge it.

## Workspace state

- The exact execution worktree at `b8e0c5d` is clean. The primary worktree has
  unrelated concurrent `AGENTS.md` and untracked PR-template changes whose
  provenance is not part of this deliverable; they are preserved and excluded
  from commits and model-run identity.
- Ignored cache: `artifacts/local/hf-cache` contains the verified 2.09 GB
  pinned snapshot.
- Ignored evidence: resource audits and structured failure reports under
  `artifacts/local/`.
- No model, training, or background benchmark process is active.
- Most recent failed-attempt resources: 6,144 MiB total / 3,764 MiB free VRAM;
  3.28 GB available RAM after preflight imports; approximately 251 GB free disk.
- External writes by agents so far: branches and draft PRs #28, #29, and #30.
  PRs #28 and #29 were subsequently merged by an external actor; no agent
  performed a merge, release, visibility change, paid operation, or public
  model/data publication.

## Active plan and evidence

- Active plan: `.agent/plans/active-pythia-local-feasibility.md`
- Decision report: `reports/stage0/model_compute_preflight_2026-08-20.md`
- Model protocol: `docs/LOCAL_BENCHMARK_PROTOCOL.md`

## Exact restart instructions

1. Confirm branch `fix/model-feasibility-gates`, a clean worktree, and at least
   5,232,040,755 bytes free on `artifacts/local/hf-cache`.
2. Confirm no unrelated heavy GPU workload and record live RAM/VRAM without
   stopping user processes.
3. Use a clean exact-head execution worktree; do not include unrelated primary-
   worktree changes in the run identity.
4. Generate a new no-network resource audit bound to the exact clean head and
   cache directory.
5. Reverify the existing exact five-file allowlist, sizes, hashes, revision,
   config, and cache containment; do not reacquire or permit network access.
6. Set Hugging Face and Transformers offline mode and run
   `benchmark_model.py --execute --allow-low-ram --device cuda --dtype
   float16` without download permission. Preserve the JSON result even on
   failure.
7. Stop on revision/hash mismatch, VRAM/OOM/allocation failure, severe desktop
   impact, thermal/driver instability, disk risk, or incomplete metadata.
8. Do not begin training until the loading result is reviewed and the tiny-
   training procedure has deterministic checkpoint/resume evidence.
