# ChronoPersona Progress

**Last updated:** 2026-08-20T02:42:05-04:00

## Current objective

Establish whether the immutable final Pythia 1B deduped checkpoint can be
acquired, loaded unquantized, and scored on the local RTX 2060, then use that
measurement to decide whether a tiny continued-pretraining and checkpoint-
resume benchmark is locally viable.

## Current verified boundary

- **Repository tooling — Tested:** commit
  `99219b7445fc2ba330f348c39deec57cf45fbab2` passed 281 local tests with one
  optional skip. Draft PR #29 passed CI, content-integrity, and run-registry
  checks on Python 3.11, 3.12, and 3.13.
- **Artifact policy — Tested:** the manifest validates with 13 artifacts and
  exactly one benchmark-ready model, final Pythia 1B deduped at immutable Hub
  revision `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`.
- **Local runtime — Integrated at enumeration/preflight level:** PyTorch
  `2.13.0+cu130` exposes CUDA 13.0 and the NVIDIA GeForce RTX 2060. A clean-
  head resource audit passed benchmark preflight and a local-only model load
  failed as expected because the explicit cache was empty.
- **Model behavior — Missing:** no weights have yet been downloaded, no model
  has loaded, no logits have been produced, and no training has run.

## Active deliverable

One exact-head final-Pythia acquisition plus CUDA loading/logits benchmark with
structured success or failure evidence. This is an engineering feasibility
measurement, not a causal or behavioral research result.

## Next evidence gate

Commit the exact-file acquisition/load split, then download only the pinned
final-Pythia inference artifact into `artifacts/local/hf-cache`, verify it, and
execute the guarded offline CUDA benchmark against a fresh post-acquisition
audit.

- **Pass:** immutable revision loads without remote code, logits complete, and
  load time, peak RAM/VRAM, dtype, parameter count, throughput, and loss are
  recorded.
- **Fail:** integrity, loader, CUDA, OOM, swapping, thermal, or disk gate
  produces an actionable structured failure; preserve the cache and stop that
  path before training.
- **Inconclusive:** interruption or an unrelated resource change invalidates
  the measurement; preserve partial cache state and repeat only after a fresh
  exact-head audit.

## Last known-good baseline

- Branch: `fix/model-feasibility-gates`
- Head: `99219b7445fc2ba330f348c39deec57cf45fbab2`
- Stacked base: `fix/windows-fixture-line-endings` at
  `bbcad88f04afc9f276806997168aebe953f2c972`
- Upstream main: `8d6644b299cedfc57e8bdc590d85e17b4f97d2b5`
- Delivery: draft PR #29, clean merge state, all reported checks passing
- Worktree at reconciliation: clean and synchronized with origin

## Status

- Evidence level: model/runtime preflight is Integrated; model loading and
  training are Unverified.
- Delivery state: preflight implementation is Published for review in draft PR
  #29; the authorized model run is not yet executed.
- Authorization: on 2026-08-20 the user explicitly lifted restrictions on
  model downloads and training. This authorizes local ChronoPersona model
  acquisition and bounded local training. No paid-compute budget, public model
  or dataset release, repository-visibility change, or third-party contact is
  required or inferred for this gate.
- Primary risk: only 3,792 MiB of the 6,144 MiB GPU was free at reconciliation;
  headroom is dynamic and model fit remains unverified.

## Current evidence by level

### Inspected

- The intended cache exists and was empty at reconciliation.
- Approximately 255 GB of disk was free on the cache drive.
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
- Most recent full candidate-tree run before the final durability additions:
  298 passed, one skipped; pilot, model-manifest, and
  development-evaluation validators passed. Exact staged-commit verification
  is pending.

### Integrated

- Exact-clean-head no-network resource audit and benchmark preflight completed
  on the RTX 2060.
- Local-only execution reached the model-load stage and preserved an expected
  missing-cache failure without network access.

### Missing or unverified

- Model file hashes after acquisition.
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

## Open uncertainties and regression risks

- Free VRAM and RAM can change because this is a daily-use Windows machine.
- Transformers/PyTorch API compatibility is tested only up to the empty-cache
  loader boundary. Registry tokenizer/scoring execution is now deliberately
  blocked until it consumes the reusable hash-verified snapshot layer; plan
  mode remains available.
- A successful inference load does not imply full-weight training fits.
- Partial Hugging Face downloads must not be mistaken for a complete immutable
  artifact.
- Draft PR #29 is stacked on unmerged draft PR #28; neither may be merged
  automatically under the current delivery workflow.

## Workspace state

- Tracked worktree was clean at reconciliation. The current intentional dirty
  state contains the authorization plan, exact manifest identities,
  acquisition/load split, alternate-loader block, tests, and protocol updates.
- Ignored cache: `artifacts/local/hf-cache` (exists, empty at reconciliation).
- Ignored evidence: resource audits and structured failure reports under
  `artifacts/local/`.
- No model, training, or background benchmark process was active.
- Measured live resources: 6,144 MiB total / 3,792 MiB free VRAM; approximately
  6.9 GB available RAM; approximately 255 GB free disk.
- External writes so far: branches and draft PRs #28 and #29 only. No merge,
  release, visibility change, paid operation, or public model/data publication.

## Active plan and evidence

- Active plan: `.agent/plans/active-pythia-local-feasibility.md`
- Decision report: `reports/stage0/model_compute_preflight_2026-08-20.md`
- Model protocol: `docs/LOCAL_BENCHMARK_PROTOCOL.md`

## Exact restart instructions

1. Confirm branch `fix/model-feasibility-gates`, a clean worktree, and at least
   5,232,040,755 bytes free on `artifacts/local/hf-cache`.
2. Confirm no unrelated heavy GPU workload and record live RAM/VRAM without
   stopping user processes.
3. Commit any tracked plan/state changes before auditing resources.
4. Generate a new no-network resource audit bound to the exact clean head and
   cache directory.
5. Run `benchmark_model.py --acquire-only --allow-download` with the explicit
   cache and pre-download audit. Preserve its distinct JSON result.
6. Require the exact five-file allowlist, sizes, hashes, revision, config, and
   cache containment to pass; then capture a fresh post-download audit.
7. Set Hugging Face and Transformers offline mode and run
   `benchmark_model.py --execute --device cuda --dtype float16` without download
   permission. Preserve the JSON result even on failure.
8. Stop on revision/hash mismatch, OOM, swapping, severe desktop impact,
   thermal/driver instability, disk-margin failure, or incomplete metadata.
9. Do not begin training until the loading result is reviewed and the tiny-
   training procedure has deterministic checkpoint/resume evidence.
