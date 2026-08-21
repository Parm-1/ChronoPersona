# Active ExecPlan — Pythia Local Feasibility

**Status:** complete — v0 failure preserved; sole v1 SDPA rescue passed
**Started:** 2026-08-20T02:10:08-04:00
**Last reconciled:** 2026-08-20T05:44:48-04:00
**Successful inference head:** `76c2479738d137d33d59d526a1392d17ceffe09a`
**Training execution head:** `3f03885b0237933ffb2b2f2a68bcf0e8f168a5d3`
**Branch:** `feat/tiny-training-resume-gate`

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

- Exact detached execution worktree is clean at inference commit `76c2479`;
  unrelated concurrent primary-worktree edits are excluded.
- PRs #28, #29, #30, and #31 were merged externally after their reported
  checks. PR #31 merged the preserved v0 head `f2568ab`. Draft PR #32 covers
  the v1 rescue through exact execution head `3f03885`; all 18 exact-head
  checks passed. Agents did not merge these PRs and are not authorized to
  merge PR #32.
- CPython 3.11.9 virtual environment with PyTorch `2.13.0+cu130`, Transformers
  5.15.1, Hugging Face Hub 1.28.0, and Accelerate 1.14.0.
- CUDA 13.0 available; RTX 2060 compute capability 7.5 and 6,144 MiB VRAM.
- Before the v1 resume attempt: 3,729 MiB free VRAM, approximately 2.95 GB
  available RAM, and approximately 251 GB free disk. The explicit RAM
  threshold override was used; VRAM/disk/integrity gates passed.
- Explicit cache `artifacts/local/hf-cache` contains the exact verified five-
  file Pythia snapshot at the pinned revision.
- Manifest: 13 artifacts, one benchmark-ready final Pythia revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`.
- Exact required inference set: five files totaling 2,092,816,302 bytes;
  exact 2.5x disk margin: 5,232,040,755 bytes.
- Exact clean training execution suite: 354 passed, one skipped; all three
  top-level validators and diff checks passed. The stored frozen no-network
  training plan and self-hash validated from both run identities.
- User explicitly authorized model downloads and training on 2026-08-20.
- The no-download plan at the tested commit resolved the exact required bytes
  and disk margin without acquiring weights.
- The verified snapshot loaded in CUDA FP16 and produced finite logits. Peak
  allocated VRAM was 2,042,486,784 bytes and peak process RSS was
  2,810,875,904 bytes.
- The first exact v0 training control is a preserved target failure:
  `run-b035b9becad60b6dc55ff3fd6fba6016` completed zero steps/tokens because
  its forced eager-attention forward produced non-finite logits/loss before
  backward or an optimizer update.
- A no-update exact-block discriminator changed only attention execution.
  Eager remained non-finite with LoRA removed and across prefix lengths
  16–128; automatic, MATH-only, and efficient SDPA produced finite outputs.
- The sole v1 rescue completed uninterrupted and planned interruption/resume
  conditions under run `run-1b8f0867fbd6038265f609b3595ae93d`; both
  verifiers passed and the comparator returned exact semantic equality.

## Completed deliverable and evidence gate

The deterministic tiny LoRA training/checkpoint/resume engineering gate and
its durable decision update are complete. The next local deliverable is owned
by a successor plan for verified-snapshot registry integration.

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

Falsified by complete exact-file, revision, hash, config, offline model load,
and finite-logits verification.

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

**Observed decision:** E3 passed. Advance to E5. The device-resident
full-weight AdamW lower bound fails analytically, so E5 is explicitly LoRA
infrastructure evidence rather than a substitute headline method.

### E5-v0 — Tiny LoRA training, checkpoint, and exact resume

- **Question:** can the verified Pythia base complete deterministic backward and
  optimizer plumbing, atomically checkpoint at step three, resume explicitly,
  and match an uninterrupted control?
- **Inputs:** exact offline snapshot; fresh training-head load report and
  resource audit; CC0 `calibration-neutral` and `control-neutral` synthetic
  fixtures; exact token-ID matrix hash.
- **Frozen profile:** seed 17; CUDA FP16; batch 1; sequence length 128; five
  steps; 640 input tokens and 635 causal-loss targets; LoRA rank 4, alpha 8,
  dropout 0, bias none, exact `query_key_value` targets; fresh AdamW with all
  hyperparameters recorded; one uninterrupted control and one interruption
  after step three followed by explicit resume.
- **Control:** offline/local-files-only base loading, exact snapshot rehash,
  same token blocks and initial seed, no shuffle/workers, one heavy job at a
  time, and no fallback to quantization/offload/another model or optimizer.
- **Pass:** both conditions complete five unique optimizer steps; final adapter,
  optimizer, scheduler, loss sequence, token count, and cursor semantic hashes
  match exactly; all checkpoint file hashes and the event chain verify.
- **Stop:** snapshot/load-report/audit drift; under 1,610,612,736 bytes post-load
  global GPU headroom;
  nonfinite loss or gradient; skipped update; CUDA OOM; 15-minute wall limit;
  severe instability; incomplete metrics; checkpoint corruption; or resume
  divergence.
- **Claim ceiling:** engineering smoke only. It does not justify PEFT for the
  headline causal claim or establish any behavioral result.

**Observed result:** failed before step one under forced eager attention. The
immutable v0 config, run, events, CLI report, and failed attempt remain the
authoritative result. Do not resume or overwrite them.

### E5-R1 — Sole attention-policy rescue

- **Question:** does the unchanged v0 training profile complete when the one
  diagnosed pre-backward variable is replaced by an explicitly reproducible
  finite attention path?
- **Preserved inputs:** exact model revision/files, token matrix, fixtures,
  sequence length, LoRA geometry, optimizer, scheduler, scaler, precision,
  seed, step count, resource limits, control/interruption/resume topology, and
  claim ceiling.
- **Changed variable:** new v1 run name plus the complete attention policy:
  Transformers `sdpa`, PyTorch `SDPBackend.MATH`, and reduced-precision
  FP16/BF16 math-SDPA reduction disabled.
- **Binding:** the policy must appear identically in config, plan/run identity,
  exact-head load report, and runtime summary. The MATH-only context spans
  forward and backward because activation checkpointing recomputes attention.
- **Diagnostic evidence:**
  `reports/stage0/pythia_lora_attention_diagnostic_2026-08-20.json`.
- **Pass:** the original E5 equality gate passes under a new v1 run ID.
- **Stop:** any v1 failure ends this local training path. No second rescue or
  tuning change is allowed.

**Observed result:** passed at exact clean head `3f03885`. Both conditions
completed five optimizer steps and 640 input tokens. Independent verification
and comparison found exact final adapter, optimizer, scheduler, scaler,
CPU/CUDA RNG, counter, loss, and complete-state equality. The final-manifest
SHA-256 is
`78ae0dd9272e6d046c237cf2b10243691098c70234a8b3db2f1c353b347f365a`.

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
- **2026-08-20T03:19:29-04:00:** E3 passed at exact head `76c2479`. The model
  loaded 1,011,781,632 FP16 parameters in 2.5291 seconds, peaked at
  2,042,486,784 allocated GPU bytes, produced finite `[1,20,50304]` logits,
  and averaged 1,294.30 predicted tokens/second across three repeats. The RAM
  override was requested but the ordinary threshold passed, so it was unused.
- **2026-08-20T04:49:51-04:00:** E5 implementation commit `7b6398f` passed
  344 tests with one optional skip in a clean detached worktree. All three
  top-level validators, diff checks, and the self-hashed no-network plan
  passed. The 40-test training/CLI subset covers exact checkpoint/resume
  equality, corruption, Windows junction escape, global locking, structured
  OOM/nonfinite failure, and transactional late-timeout rollback. No model was
  loaded during this validation.
- **2026-08-20T04:59:09-04:00:** exact training head `f2568ab`, v0 control
  `run-b035b9becad60b6dc55ff3fd6fba6016`, failed on the first eager-attention
  forward with non-finite loss. It completed zero steps/tokens; no backward or
  optimizer update ran. The structured failure and run tree are immutable.
- **2026-08-20T05:01:10-04:00 onward:** a bounded offline discriminator found
  the exact token block and embeddings valid, reproduced eager non-finiteness
  without LoRA and across prefixes 16–128, and produced finite loss under
  automatic, MATH-only, and efficient SDPA. This consumes the one rescue for
  the explicit MATH-only v1 policy; other training variables stay frozen.
- **2026-08-20T05:24:00-04:00:** exact rescue commit `192b0d7` passed 354
  tests with one optional skip in the clean detached worktree. All three top-
  level validators, diff checks, and the self-hashed v1 no-network plan passed.
- **2026-08-20T05:37:55-04:00:** exact clean head `3f03885` passed a fresh
  cache-bound resource audit and explicit SDPA-MATH offline load/logits probe.
  The model identity, all snapshot hashes, attention policy, parameter count,
  dtype, and finite `[1,20,50304]` logits verified.
- **2026-08-20T05:39:12-04:00:** the uninterrupted v1 control completed five
  steps. The planned resumed condition then stopped cleanly after its atomic
  step-three checkpoint.
- **2026-08-20T05:42:05-04:00:** a fresh audited process verified and restored
  the checkpoint, completed steps four and five, and published the same final
  manifest as control. Both run verifiers passed; comparison status was
  `equal` across every frozen semantic state component.

## Decisions

- Use final Pythia as the only first acquisition because it is the sole
  benchmark-ready artifact and is sufficient to test the local loading path.
- Retain scientific, legal, integrity, and resource stop conditions. The user
  lifted permission restrictions, not the evidentiary meaning of a result.
- Waive only the E3 available-host-RAM hard threshold through an explicit,
  reported CLI option. Continue to enforce VRAM, disk, identity, and integrity
  gates and stop on actual allocation failure or severe instability.
- Do not allocate a device-resident full-weight AdamW state: its optimistic
  8,094,253,056-byte lower bound exceeds the 6,441,992,192-byte GPU before
  activations. Advance with LoRA only as a trainer/resume diagnostic.
- Keep external spend at CAD $0 for this gate; no paid resource is needed.
- Defer CPU fallback, quantization, offload, optimizer choice, and training
  method until E3 identifies the actual limiting variable.
- Keep registry tokenizer/scoring execution blocked until the provider consumes
  a reusable manifest/hash-verified snapshot loader. Benchmark acquisition does
  not automatically authorize a separate unverified cache-loading path.
- Preserve the failed v0 spec and run. Implement exactly one versioned v1
  rescue changing only the attention policy. If v1 fails, stop rather than
  adjusting training hyperparameters or model execution again.
- Accept the passing v1 result only as bounded trainer/checkpoint/resume
  engineering evidence. Close the rescue without v2; do not infer PEFT
  adequacy or a temporal/model-behavior result.
- Activate reusable manifest/hash-verified snapshot integration as the next
  local engineering gate so registry tokenizer/scorer execution cannot trust
  arbitrary cache contents.

## Required validation

- Build: `python -m compileall scripts src tests` if code changes.
- Focused: benchmark, manifest, artifact-policy, and any new training tests.
- Regression: complete `pytest` and all three top-level validators before push.
- Integration: exact-head resource audit, load report, and structured training
  control/resume results.
- Target: five-step CUDA LoRA control plus interrupted/resumed semantic equality
  on the RTX 2060, or one preserved actionable failure.
- Operational: not required; this is a bounded engineering smoke.

## Resumable milestones

1. Authorization/current state committed and PR checks green — complete.
2. E1 exact-head audit passed — complete.
3. E2 acquisition result preserved and verified — complete.
4. E3 offline CUDA load/logits result preserved — complete.
5. State and decision updated; E5 training gate activated — complete.
6. E5 implementation and exact-head local validation — complete.
7. Stacked draft PR and exact-head CI for v0 — complete; the v0 CUDA control
   produced a preserved actionable failure.
8. Versioned v1 SDPA-MATH rescue implementation, validation, push, and CI —
   complete at `3f03885` / draft PR #32.
9. Fresh exact-head MATH-policy load report and one v1 control/interruption/
   resume/verify/compare gate — complete and equal.
10. E5 evidence, compute ledger, and advance/stop decision published —
    complete in the follow-up evidence commit.

## Exact restart procedure

This plan is complete. Read `PROGRESS.md`, preserve both v0 and v1 run trees,
and do not rerun or tune them. Resume local engineering from a successor plan
for reusable verified-snapshot registry integration. Draft PR #32 must receive
green exact-head CI after the evidence commit and must not be merged by agents.

## Completion classification

Complete. E5 has a preserved control/resume result, exact comparison, compute-
ledger entries, and a recorded close decision. The outcome is Target Verified
only for the bounded engineering objective and does not complete any scientific
training or CSTG objective.
