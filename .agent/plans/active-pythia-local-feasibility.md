# Active ExecPlan — Pythia Local Feasibility

**Status:** active
**Started:** 2026-08-20T02:10:08-04:00
**Last reconciled:** 2026-08-20T03:03:06-04:00
**Tested and acquired head:** `b8e0c5d699a8bf46548018ae803afb597524a336`
**Branch:** `fix/model-feasibility-gates`

## Objective and end state

Produce reproducible evidence that the immutable final Pythia 1B deduped model
either loads and completes a small unquantized CUDA logits benchmark on the
local RTX 2060, or fails for one preserved actionable reason. If loading passes,
design and implement the smallest deterministic tiny continued-pretraining
benchmark that measures backward/optimizer memory, throughput, checkpoint
time, and exact resume behavior before any scientific training branch.

## Non-goals

- No temporal, personality, CSTG, or causal conclusion.
- No naturalistic corpus acquisition or source-C access.
- No public model/data release, repository visibility change, or paid compute.
- No quantized result promoted as primary likelihood evidence.
- No fallback to a different revision, model, precision, or training method
  without a recorded decision.

## Verified starting state

- Exact detached execution worktree is clean at acquired commit `b8e0c5d`;
  unrelated concurrent primary-worktree edits are excluded.
- PRs #28 and #29 were merged externally after passing their reported checks.
  Draft PR #30 covers the hardening head and all 18 `b8e0c5d` checks passed;
  the subsequent low-RAM override is pending validation and publication.
- CPython 3.11.9 virtual environment with PyTorch `2.13.0+cu130`, Transformers
  5.15.1, Hugging Face Hub 1.28.0, and Accelerate 1.14.0.
- CUDA 13.0 available; RTX 2060 compute capability 7.5 and 6,144 MiB VRAM.
- At reconciliation: 3,792 MiB free VRAM, approximately 6.9 GB available RAM,
  and approximately 255 GB free disk.
- Explicit cache `artifacts/local/hf-cache` contains the exact verified five-
  file Pythia snapshot at the pinned revision.
- Manifest: 13 artifacts, one benchmark-ready final Pythia revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`.
- Exact required inference set: five files totaling 2,092,816,302 bytes;
  exact 2.5x disk margin: 5,232,040,755 bytes.
- Exact implementation suite: 303 passed, one skipped; all three top-level
  validators and the no-download acquisition plan passed.
- User explicitly authorized model downloads and training on 2026-08-20.
- The no-download plan at the tested commit resolved the exact required bytes
  and disk margin without acquiring weights.

## Active deliverable and evidence gate

The single write-active deliverable is the final-Pythia local loading/logits
measurement plus its durable decision update.

The gate decides whether to advance to a tiny training benchmark:

- **Pass:** pinned safetensors load with `trust_remote_code=false`; logits and
  cross-entropy complete; memory, load time, throughput, dtype, parameter count,
  exact revision, environment, and resource-audit identity are recorded.
- **Fail:** one integrity, software, memory, thermal, or storage cause is
  preserved; do not alter multiple variables or start training.
- **Inconclusive:** external interruption or changed resources invalidate the
  run; preserve partial state and rerun only after a new clean audit.

## Hypotheses

### H1 — Local CUDA inference is viable

The approximately 2.09 GB float16 final checkpoint plus framework and small-
prompt overhead fits the available RTX 2060 memory and produces logits.

Falsified by a reproducible OOM or resource stop after artifact integrity and
software compatibility pass.

### H2 — Software or artifact compatibility fails first

Transformers 5.15.1, PyTorch 2.13, the pinned GPT-NeoX configuration, or local
safetensors loading fails before meaningful CUDA allocation.

Falsified by successful immutable load and forward pass.

### H3 — Dynamic desktop headroom triggers the conservative RAM gate

Unrelated GPU/RAM use leaves insufficient safe headroom even though the hardware
class is nominally capable.

Observed on the first offline attempt: post-import available RAM fell below the
two-times-weight threshold. Preserve that result and use the explicit user-
authorized RAM override on the single retry; do not terminate unrelated
processes to manufacture headroom.

### H4 — Acquisition or identity is incomplete

The download is partial, resolves a different revision, or lacks the required
safe inference files.

Falsified at the acquisition layer by the complete exact-file, revision, hash,
and config verification. Model loading remains a separate unresolved gate.

## Scope and ownership

- **Write scope:** `PROGRESS.md`, `.agent/`, the existing feature branch, a new
  follow-up draft PR, bounded benchmark code/tests if defects are found, and
  decision reports.
- **Generated evidence:** ignored `artifacts/local/` only; no weights or machine-
  specific paths in Git.
- **Read-only scope:** manifest, protocol, run registry, evaluation code, Hub
  metadata, CI, and PR state.
- **Protected state:** unrelated user processes, data, caches, branches, merged
  PR history, repository visibility, and external accounts.
- **Concurrency:** root agent is the only writer. Subagents are read-only.

## Prohibited shortcuts

- Do not disable manifest/license/remote-code/hash/resource gates.
- Do not substitute a mutable branch or default revision.
- Do not silently quantize, offload, change dtype/device, or shorten evidence
  requirements after failure.
- Do not treat an inference pass as training feasibility.
- Do not run multiple heavy jobs concurrently or kill unrelated GPU workloads.
- Do not commit cache files, model weights, checkpoints, raw corpora, or machine-
  specific evidence.

## Planned experiments

### E0 — Freeze authorization and run identity

- **Question:** can the expensive gate bind to a coherent exact tracked state?
- **Inputs:** current branch, this plan, `PROGRESS.md`, project authorization
  records.
- **Changed variable:** authorization state only.
- **Procedure:** update current state/decision documents, run focused validation,
  commit, push the feature branch, open a new draft PR, and wait for required
  CI.
- **Expected:** clean exact head with authorization and stop conditions recorded.
- **Stop:** inconsistent repository state or failing validation.
- **Artifacts:** tracked plan/state commit and PR checks.

### E1 — Fresh pre-download resource audit

- **Question:** does the exact clean head have sufficient current disk and a
  CUDA-enabled runtime at the intended cache?
- **Inputs:** committed head and `artifacts/local/hf-cache`.
- **Control:** no-network resource audit.
- **Changed variable:** live machine state.
- **Procedure:** run `scripts/audit_local_resources.py` against the cache path.
- **Expected:** clean matching head, CUDA available, one RTX 2060, and disk well
  above 5,232,040,755 bytes.
- **Stop:** dirty/mismatched head, CPU-only Torch, missing cache mount, disk
  margin failure, or severe live resource contention.
- **Artifact:** `artifacts/local/resource-audit-authorized-pre-download.json`.

### E2 — Immutable acquisition

- **Question:** can the exact pinned Pythia inference file set be acquired and
  independently verified without loading code or tensors?
- **Inputs:** canonical manifest, E1 audit, explicit cache, immutable revision,
  and five exact file size/SHA-256 records.
- **Control:** no mutable revision and no remote code; the existing local-only
  missing-cache failure is the pre-acquisition negative control.
- **Changed variable:** permit one pinned model download.
- **Procedure:** run `scripts/benchmark_model.py --acquire-only
  --allow-download` with the explicit cache/audit. Require cache containment,
  the exact snapshot revision and file set, every size/hash, GPT-NeoX config,
  float16 declaration, and absence of `auto_map`.
- **Expected:** a complete acquisition JSON or one distinct structured failure
  with audit identity and failure stage.
- **Stop:** revision/cache/allowlist/hash/config mismatch, disk-margin failure,
  or incomplete metadata.
- **Resources:** one 2,092,816,302-byte required file set; CAD $0.
- **Artifact:** `artifacts/local/pythia-main-acquisition.json`.

### E3 — Fresh audit and offline CUDA logits benchmark

- **Question:** can the verified local snapshot load and score a small prompt?
- **Inputs:** E2 snapshot/report, a new post-acquisition audit, default synthetic
  prompt, `max_tokens=128`, one warmup, three measured repeats.
- **Control:** offline Hub/Transformers environment, `local_files_only=true`,
  exact-file rehash, no download flag, no remote code, and explicit float16.
- **Changed variable:** model load and forward execution only.
- **Procedure:** capture a fresh cache-bound audit, set `HF_HUB_OFFLINE=1` and
  `TRANSFORMERS_OFFLINE=1`, then execute the benchmark on CUDA. The script
  embeds child-process audits before and after parent model-stack imports,
  validates the actual imported runtime/GPU identity, and rechecks physical RAM
  plus conservative VRAM headroom immediately before load. Pass
  `--allow-low-ram` so the user-authorized run records but does not enforce the
  physical-RAM margin.
- **Expected:** complete JSON with loaded model/logits semantics, memory, load
  time, throughput, loss, and both resource bindings, or one structured
  failure.
- **Stop:** stale/drifted audit, low VRAM, architecture/dtype/parameter/logit
  mismatch, allocation failure, OOM, severe desktop impact, thermal/driver
  instability, or incomplete metadata. Low available host RAM is recorded but
  is not a stop under the explicit override.
- **Artifact:** `artifacts/local/pythia-main-cuda-authorized.json`.

### E4 — Post-run decision

- **Question:** does E3 justify building a tiny training/resume benchmark?
- **Pass path:** preserve measurement, update compute ledger/state/decision, and
  implement a bounded training benchmark with tests before training.
- **Fail path:** preserve the failure, change at most one diagnosed variable,
  or stop the local path.
- **Inconclusive path:** repeat only after the invalidating external condition
  is removed and a fresh audit is captured.

## Observed results

- **2026-08-20T02:10:08-04:00:** repository and PR state reconciled clean at
  `99219b7`; cache exists and is empty; CUDA runtime exposes the RTX 2060;
  3,792 MiB VRAM, approximately 6.9 GB RAM, and approximately 255 GB disk were
  free. Interpretation: the permission blocker is gone, but E1–E3 remain
  necessary because artifact integrity and live fit are not established.
- **2026-08-20T03:03:06-04:00:** exact clean implementation commit `d812ba8`
  passed 303 tests with one optional skip, all top-level validators, and the
  no-download acquisition plan. No model weights were downloaded.
- **2026-08-20T03:08:56-04:00:** E2 completed at exact head `b8e0c5d`; all
  five files totaling 2,092,816,302 bytes matched the pinned revision, exact
  allowlist, sizes, SHA-256 digests, and GPT-NeoX config.
- **2026-08-20T03:09:27-04:00:** the first offline E3 attempt stopped at
  `live-resource-preflight` before model import/load because available RAM was
  3,281,063,936 bytes versus the 4,181,403,056-byte conservative threshold.
  Artifact integrity and 3,764 MiB conservative free VRAM remained valid.
- **2026-08-20T03:12:57-04:00:** the user explicitly authorized using as much
  host RAM as needed. E3 will repeat from a new exact head with a recorded
  low-RAM override; the first failure remains preserved.

## Decisions

- Use final Pythia as the only first acquisition because it is the sole
  benchmark-ready artifact and is sufficient to test the local loading path.
- Retain scientific, legal, integrity, and resource stop conditions. The user
  lifted permission restrictions, not the evidentiary meaning of a result.
- Waive only the E3 available-host-RAM hard threshold through an explicit,
  reported CLI option. Continue to enforce VRAM, disk, identity, and integrity
  gates and stop on actual allocation failure or severe instability.
- Keep external spend at CAD $0 for this gate; no paid resource is needed.
- Defer CPU fallback, quantization, offload, optimizer choice, and training
  method until E3 identifies the actual limiting variable.
- Keep registry tokenizer/scoring execution blocked until the provider consumes
  a reusable manifest/hash-verified snapshot loader. Benchmark acquisition does
  not automatically authorize a separate unverified cache-loading path.

## Required validation

- Build: `python -m compileall scripts src tests` if code changes.
- Focused: benchmark, manifest, artifact-policy, and any new training tests.
- Regression: complete `pytest` and all three top-level validators before push.
- Integration: exact-head resource audit and structured model execution result.
- Target: successful CUDA load/logits on the RTX 2060, or preserved actionable
  failure.
- Operational: not required for E2/E3; sustained thermal/training validation is a
  later gate.

## Resumable milestones

1. Authorization/current state committed and PR checks green.
2. E1 exact-head audit passed.
3. E2 acquisition result preserved and verified.
4. E3 offline CUDA load/logits result preserved.
5. State and decision updated; training gate either activated or stopped.

## Exact restart procedure

Read `PROGRESS.md`, confirm this is the sole active plan, inspect branch/cache/
resource reality, and resume the first incomplete milestone. Never reconstruct
authorization or run identity from chat alone. Before E2, require a clean head,
fresh audit, existing explicit cache, and all E1 stop conditions passing. Before
E3, require complete E2 integrity, a second fresh audit, explicit offline mode,
no conflicting heavy job, and all non-RAM E3 headroom checks passing. Record
the user-authorized RAM-threshold override explicitly.

## Completion classification

Complete this plan only after E3 has a preserved result and E4 records the
advance/stop decision. A downloaded file without a complete identity-bound
result is partial acquisition, not completion.
