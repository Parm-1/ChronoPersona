# Verified Registry Model Scoring

**Status:** complete — E0-E5 passed; exact evidence head `a7dd27c` passed all 18 required checks
**Started:** 2026-08-20T07:17:14-04:00
**Frozen baseline:** `dd0b56471b55babe2a4eb273381deeef2f852d49`
**Branch:** `feat/verified-registry-scoring`
**Worktree:** current branch worktree; do not persist its machine-local absolute path
**Parent delivery:** draft PR #33, 18/18 checks green at `dd0b564`
**Write-active deliverable:** publish the accepted bounded Pythia scorer
evidence, current-state reconciliation, and portability regression fix without
rerunning the model.

## Objective and acceptance boundary

Enable `development-v0` scoring only after the accepted tokenizer identity,
exact local snapshot, clean Git head, fresh live resources, CUDA FP16 model
load, and frozen SDPA-MATH policy all pass. Two fresh invocations must produce
byte-identical deterministic score files. Runtime receipts may differ in
declared attempt-specific process, timing, resource, storage, and metric
evidence; their frozen Git, run, input, model, and runtime identities must
match.

A pass is Target Verified engineering evidence for this exact scorer path. It
does not establish score reliability, a temporal effect, calibration
sensitivity, model representativeness, causal evidence, or CSTG.

## Frozen inputs

- Artifact: `pythia-1b-deduped-main` at revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`.
- Safetensors: 2,090,701,528 bytes, SHA-256
  `fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13`.
- Portable snapshot receipt SHA-256:
  `26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc`.
- Canonical manifest Git blob / byte SHA-256:
  `2dbafc0d0fe10a717e1df3d5c7920e6af661138b` /
  `f3a800e95887b96ec66a660efa51ab975b17b7ec1ada0f381f502e912d9cf4f6`.
- Development registry Git blob / byte SHA-256:
  `39a229ca8a29243bc457f42c5fdc69e303bb5361` /
  `5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d`.
- Accepted tokenizer canonical / raw report SHA-256:
  `6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523` /
  `ee11e4c99d6577fa2e3be5a53e4c17b626ff91bcdee877b295799dc5926c39bb`.
- Accepted ordered scoring-token matrix SHA-256:
  `b2477a108542308b17d80811aa0ff15ad72f37a67363c3fa9177fde85805dfe1`.
- Tokenizer backend SHA-256:
  `1b0aca3746c0870daeb9137101cd89acbb38710fc433db83331287d5b0e47ee0`.
- Prefix policy `none`, empty prefix token IDs, maximum length 2,048.
- Registry topology: 12 items, 24 forms, 48 candidates, 2,391 forwarded
  tokens, 839 continuation tokens, maximum full sequence length 59.
- Model: `GPTNeoXForCausalLM`, `gpt_neox`, 1,011,781,632 parameters, logits
  width 50,304.
- Execution: exactly `cuda:0`, FP16 parameters, float32 log-softmax, eval mode,
  no quantization, device map, offload, autocast, truncation, download, or
  remote code.
- Attention: Transformers `sdpa`, PyTorch `SDPBackend.MATH`, reduced-precision
  FP16/BF16 math-SDPA reduction disabled around every forward.
- Repeat rule: two fresh invocations, exact score-byte equality, no rescue run.

Freeze these values in `configs/runs/pythia-development-score-v0.json`. Any
manifest or registry edit invalidates the accepted tokenizer evidence and stops
this plan; do not update either input inside this gate.

## Resource and execution contract

- One heavy process at a time under a fixed repository/machine-scoped lock.
- Supplied resource audit must be fresh, clean, cache-bound, and from the exact
  execution head. Capture live audits before optional imports and immediately
  before deserialization; bind Python, executable, packages, CUDA, driver,
  GPU, RAM, VRAM, platform, Git, and filesystem identity.
- Minimum pre-load conservative free VRAM: 3,695,181,824 bytes.
- Maximum peak reserved VRAM: 3,158,310,912 bytes.
- Minimum post-load global free VRAM: 1,610,612,736 bytes.
- Minimum free staging/output disk: 2,227,034,030 bytes.
- Minimum output reserve: 134,217,728 bytes.
- Maximum invocation wall time: 900 seconds.
- The user-authorized host-RAM threshold override is frozen and recorded. RAM,
  paging, allocation failures, thermal/driver errors, or severe desktop
  instability remain observed stop conditions.
- Set `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
  `CUBLAS_WORKSPACE_CONFIG=:4096:8`, deterministic algorithms on, TF32 off,
  cuDNN benchmark off, and float32 matmul precision `highest` before execution.

## Implementation invariants

1. Reuse one tested resource-policy implementation. The scoring CLI calls the
   existing `benchmark_model.py` validators directly and preserves their
   ordering and behavior; it does not maintain a second threshold
   implementation.
2. Generalize the create-only verified staging helper. Model loading stages
   only `config.json` and `model.safetensors`, stream-verifies them during and
   after copy, and never consumes the mutable cache as the deserialization
   source.
3. Require canonical manifest/registry bytes bound to one clean captured HEAD,
   explicit cache/snapshot paths, the frozen run spec, and the accepted
   tokenizer report before optional model imports.
4. Load with `local_files_only=True`, `trust_remote_code=False`,
   `use_safetensors=True`, `torch_dtype=float16`, `low_cpu_mem_usage=True`, and
   `attn_implementation=sdpa`; assert exact class, type, parameter count, dtype,
   device, vocabulary, attention policy, eval state, and absence of meta/CPU/
   offloaded parameters.
5. Reuse the verified tokenizer provider and require its snapshot receipt,
   backend, special-token, native-prefix, and runtime identities to equal the
   accepted tokenizer audit.
6. Every provider call must require finite rank-3 logits shaped
   `[1, sequence, 50304]`, exact prepared boundaries, finite non-positive
   selected log probabilities, and no truncation.
7. Publish two create-only artifacts per invocation: a deterministic score
   containing only stable scientific-computation inputs/outputs, and a runtime
   receipt containing attempt, resource, Git, runtime, validation, timing,
   memory, and score-file binding. Failures publish only a structured failed
   receipt; orphan or partial scores are invalid.
8. A dependency-light repeat verifier must validate both self-hashes, raw score
   byte equality, both complete receipts, immutable receipt identity equality,
   both distinct raw resource-audit bindings, 12/24/48 and token totals, zero
   integrity failures, and recursive absence of absolute paths from
   deterministic scores.

## Pre-logits implementation decisions

- The original E1 wording proposed extracting the resource validators into a
  new shared module. Direct reuse of the already tested benchmark validators is
  the smaller behavior-preserving implementation, so this plan records that
  amendment before any development logits are inspected.
- Model deserialization reads only a private, randomly named create-only stage.
  Its exact files are rehashed before the resource callback, again immediately
  before deserialization, and after loading. This closes ordinary cache-writer
  races. A malicious same-account process that can replace and restore private
  staged bytes during deserialization remains outside the trusted-local-host
  threat model.
- The complete receipt records elapsed time through score-file fsync, before
  the receipt itself is written. A final wall-limit check runs after receipt
  fsync and rolls back both owned outputs if it fails; therefore publication is
  transactionally bounded even though that last duration is not embedded in
  the already-written receipt.

## Evidence gates

### E0 — Baseline and frozen plan (complete)

- Close the tokenizer-loader plan at green evidence head `dd0b564`.
- Create this successor branch, plan, frozen run specification, and one-writer
  state transition without changing manifest or registry.

### E1 — Shared loader/resource implementation (complete)

- Extract/reuse the exact resource gate, add verified model staging/loading,
  accepted-tokenizer binding, deterministic attention controls, split output
  schemas, and repeat verifier.
- Keep plan mode dependency-light and model execution fail-closed until every
  required input is explicit.

### E2 — Dependency-light validation (complete)

- Cover canonical-input/run-spec drift, tokenizer-report drift, snapshot and
  stage integrity, links/escape, resource/runtime drift, pre-import ordering,
  exact load kwargs and model identity, nonfinite/malformed logits,
  SDPA-MATH use, output transactions, final rebind, structured failures, path
  portability, and exact repeat mismatch detection.
- Pass compile checks, all validators, focused tests, full pytest, and
  `git diff --check`.

Observed at exact code head `dc14bf83171dce66c3c92a02ce44e1fb656d667a`:
457 tests passed with two platform-optional symlink skips in a fresh detached
worktree that began without `artifacts/local`; the pilot, model-manifest, and
development-registry validators passed; production modules compiled; and
`git show --check` passed. Focused adversarial review additionally replayed
resource chronology, raw-hash transport, path alias, type-alias, platform,
threshold, output-transaction, lock-release, and final-rebind failures. This is
pre-execution Tested evidence only; no exact-head CI or target-scoring evidence
exists yet and no model logits were inspected.

### E3 — Implementation delivery (complete)

- Complete: pushed exact tested code head `dc14bf8` and opened draft PR #34
  stacked on `feat/verified-registry-loader`.
- Observed blocker: all 18 hosted push/PR matrix jobs for `dc14bf8` were
  rejected before startup. GitHub Actions run `32377136301` reports failed
  account payments or an insufficient spending limit; this is not a test
  failure and no agent is authorized to change billing.
- A later bounded rerun probe of that run's Python 3.11 job produced job
  `96453153543`, which again completed with no steps and the same account-level
  rejection. After the user resumed the blocked goal, one fresh availability
  probe produced job `96483944575`; it likewise completed with no steps and the
  same annotation. Hosted-runner availability remained blocked while the
  repository was private.
- On 2026-08-20 the user explicitly authorized changing
  `Parm-1/ChronoPersona` from private to public to restore free standard
  GitHub-hosted Actions capacity. Pre-exposure scans found no credentials,
  repository secrets, tracked model weights, or raw corpora. The user was
  informed that commit metadata includes a personal email and that historical
  Actions logs and local path strings become public and cannot be recalled
  after third-party copying.
- Observed after the change: anonymous GitHub API access returned HTTP 200;
  repository visibility is `public`; main and draft PR #32/#33/#34 heads were
  unchanged; default workflow permissions remain read-only; Pages, releases,
  deployments, environments, repository secrets, and variables remain absent.
  Secret scanning and push protection are enabled, and every external fork PR
  requires workflow approval.
- Require every check to pass at the resulting exact head before inspecting
  development logits. A public visibility flag alone is not CI evidence; jobs
  must start and complete on standard hosted runners.
- Observed at public-delivery head `0f58e60`: all 18 push/PR checks started.
  Content Integrity and Run Registry Smoke passed 12/12. All six CI matrix
  jobs reached the full suite and reported 458 passing tests plus one shared
  Linux-only cleanup failure: the linked-parent regression used `os.rmdir` on
  a POSIX directory symlink after its security assertion had passed. Deliver
  the narrow platform-correct cleanup and require a new exact-head green run;
  this is a test-portability defect, not model-scoring evidence.
- Complete: exact correction head
  `39052c5876feefd5716493b2fd0d9cc149762bd5` passed all 18/18 push/PR checks
  across Python 3.11, 3.12, and 3.13. PR #34 remains open and draft. E3 is
  closed; do not rerun prior failed billing/cleanup heads.

### E4 — Exact-head target scoring (complete)

- Exact clean head `cee0f2fa436578bec2f90e57e7ae512f58335323`
  completed attempts A and B under distinct fresh audits/processes after the
  first process released CUDA, staging, and the heavy-job lock.
- Run `run-25453ff5b41cda00b30ac23b046f6a5e` completed 48 forwards per
  attempt over 12 items, 24 forms, and 48 candidates with zero boundary,
  truncation, or nonfinite failures.
- Both 124,555-byte score files are byte-identical with raw SHA-256
  `c3cc112c2aa7f082858ccf60b827290893b488e7adc834293bb8054d15e1cecb`.
  The repeat verifier returned `equal`; comparison self-hash is
  `fcf155c5414bdcda7ce9cbdd12e1723da35b268d05bc3d96c369401f7850e687`.
- This is Target Verified scorer-path evidence only. Four items had
  directional agreement `0.5`, so measurement reliability remains open.

### E5 — Evidence publication (conditional completion)

- Preserve ignored raw audits/scores/receipts/comparison. A hash-matched private
  local backup exists outside the public repository.
- Commit only a bounded portable aggregate report, D-033, compute-ledger rows,
  and canonical state/protocol updates.
- Include the dependency-light Windows/Python 3.13 stable-read portability fix
  found during evidence review; do not change or rerun E4 artifacts.
- Push the evidence head and require exact-head CI again. Do not rerun a pass to
  improve timing or presentation.
- Treat the containing E5 commit as the last change in this plan. Once every
  required check on that exact head is green, E5 and this plan are complete
  without a post-CI closure commit.

## Required tests and validation

- Negative tests for mutated/noncanonical spec, manifest, registry, accepted
  tokenizer report, artifact/revision/prefix/runtime/snapshot/backend, cache
  layout, files, links/reparse points, resources, runtime, model identity,
  logits, output overwrite, final rebind, and repeat mismatch.
- Spies prove every preflight failure occurs before optional import or model
  deserialization, as appropriate.
- Fake-model integration proves exact private-stage load kwargs, all frozen
  deterministic controls, score/receipt separation, and byte-identical repeat
  acceptance without requiring Torch in CI.
- Preserve all existing benchmark, tokenizer, scoring, and repository tests.
- Target validation is two exact-head CUDA invocations on the RTX 2060 or one
  preserved actionable failure.

## Stop and failure policy

Stop without automatic retry after deserialization begins if any identity,
resource, stage, model, logits, boundary, determinism, or publication invariant
fails. A pre-import headroom failure remains pending and may be retried only
after resources naturally return and a fresh audit is captured.

If A and B differ, classify the gate `determinism-failed`. Do not round floats,
compare with tolerance, run a third tie-breaker, switch device/dtype/backend,
shorten the registry, quantize, offload, or choose a preferred output.

## Non-goals

- No registry, manifest, tokenizer policy, model revision, or evaluation-item
  change.
- No OLMo, DatedGPT, model acquisition, training, mechanism work, real-source
  content, paid compute, public release, or repository merge.
- No scientific interpretation of development scores.

## Exact restart procedure

Read `PROGRESS.md`, confirm this is the sole active plan, inspect branch/status,
and preserve PR #33 at `dd0b564` plus draft PR #34. Do not rerun E4. Verify the
seven ignored raw artifacts against their recorded hashes and keep their
private backup. Finish the portable report/state/portability commit, push it,
and require exact-head CI. If that exact head is green, close this plan by its
recorded condition and create the separate measurement-reliability successor;
otherwise address only the observed failure. Never merge draft PRs.
