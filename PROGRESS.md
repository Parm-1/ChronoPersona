# ChronoPersona Progress

**Last updated:** 2026-08-20T17:43:51-04:00

## Decision

Classify `development-v1` E4 as **Target Failed operationally** at exact clean
execution head `e435c40f1b1b2c9e8be1c1f3bb6ecd1ea9c89aa0`. Attempt A
`run-3aa8058dced36e7e88802079925500df` completed the frozen 224-forward
canonical schedule, then failed `post-score-resource-check` below the frozen
resident-VRAM floor before create-only score publication. Attempt A is
consumed. No A score, B audit/run, comparison, or coherence artifact exists,
and no item or pole value was inspected. Do not run B or retry A.

Accept exact execution head
`cee0f2fa436578bec2f90e57e7ae512f58335323` and run
`run-25453ff5b41cda00b30ac23b046f6a5e` as **Target Verified engineering
evidence** for the frozen Pythia registry-scoring path. Two fresh invocations
completed all 48 candidate forwards and produced byte-identical 124,555-byte
score files. The dependency-light verifier returned `status="equal"`.

Do not accept `development-v0` as a reliable measurement instrument or infer a
scientific result. Four of twelve items changed direction across their two
forms, and one item aggregate plus two forms changed sign between the frozen
primary total-logprob margin and the diagnostic mean-token margin. Preserve the
score and primary metric; revise the instrument only under a separate
predeclared development plan.

Accept the exact `development-v1` scorer implementation as **Tested and
exact-head delivered**. It adds one closed v0/v1 profile allowlist,
full canonical-versus-reverse provider scheduling with canonical score
serialization, profile-bound receipts, and an integrated fail-closed repeat
and coherence verifier. E4's later operational failure does not invalidate that
software evidence, but no deterministic v1 score pair or coherence result was
published.

Accept E3 closure/execution head
`e435c40f1b1b2c9e8be1c1f3bb6ecd1ea9c89aa0` as the exact implementation
boundary. Draft PR #36 is open and draft, stacked on PR #35, and all 18
push/pull-request checks passed on that head before E4. D-037 now closes the
consumed failure without a second invocation.

The user explicitly authorized making `Parm-1/ChronoPersona` public to restore
free standard GitHub-hosted Actions. The repository is public, anonymous access
works, fork workflows require approval from all external contributors, default
workflow tokens remain read-only, and secret scanning plus push protection are
enabled. The prior zero-step billing blocker is empirically closed: draft PR
#34 passed all 18 exact-head checks. No billing setting changed.

Accept failure-observability delivery head
`d669b4e3c36069398efdac831c8f1fec7036359c` as **Tested and exact-head
delivered**. Draft PR #37 is open/draft and all 18 push/pull-request checks
passed on that unchanged head. The scoped change preserves exact failed
resident-resource observations without changing thresholds or reopening E4.

The next hard boundary is not yet reached. The source protocols explicitly
authorize CAD-$0 official metadata queries, archive inventories/checksums, and
aggregate reports without document-body retrieval. D-039 therefore activates
one bounded metadata-only prequalification across provisional Wikimedia,
Stack Exchange, arXiv, and PMC roles. No evidence-bearing live query has run
under D-039.

## Current objective and closure condition

Freeze and deliver one fail-closed metadata-evidence contract on
`feat/live-source-metadata-qualification`, based on exact green head
`d669b4e`. After exact-head CI, execute only the predeclared no-cost metadata
inventory/enrichment profile: pinned `enwiki/20260801`, the legacy
company-attributed Stack Exchange item, one 100-record time-stratified arXiv
sample plus exact enrichment of all 100 per provisional window, and up to 100
upstream PMC Dublin Core records per release/update-datestamp range within a
ten-response cap. Raw identifiers remain private; incidental metadata prose is
hash/count-only and must not be displayed or human-reviewed. The gate closes
with one portable independently replayed
aggregate or one actionable failure, followed by exact-head CI on the evidence
commit.

## Current verified boundary

- **Development content-integrity gate — Target Verified:** bounded
  redistributable fixtures passed. Live source metadata remains unverified but
  is now the authorized local/network gate. Bounded no-cost A/B parser samples
  remain a later authorized gate; bulk and source-C content remain blocked.
- **Artifact/load — Target Verified:** immutable final Pythia 1B deduped at
  revision `7199d8fc61a6d565cd1f3c62bf11525b563e13b2` was hash verified,
  loaded offline in CUDA FP16, and produced finite logits under frozen
  SDPA-MATH policy.
- **Training v0 — Target Failed:** `run-b035b9becad60b6dc55ff3fd6fba6016`
  failed before backward under forced eager attention and remains immutable.
- **Training v1 — Target Verified:** sole rescue run
  `run-1b8f0867fbd6038265f609b3595ae93d` completed five-step control and
  planned interruption/resume conditions with exact final semantic equality.
- **Tokenizer boundary — Target Verified:** exact head `c57ce40` produced two
  byte-identical 12-item/24-form/48-candidate boundary reports with zero
  failures and native prefix policy `none`.
- **Scoring path — Target Verified:** exact head `cee0f2fa` completed two fresh
  48-forward invocations with 2,391 forwarded, 2,343 predicted, and 839
  continuation tokens per invocation. Both deterministic score files are
  byte-identical; all boundary, truncation, and nonfinite failure counts are
  zero.
- **Measurement instrument — Not verified:** eight items agreed across both
  forms; four evidence-integration items had directional agreement `0.5`.
  The observed primary/diagnostic sign disagreements make reliability work the
  next local gate.
- **Development-v1 tokenizer coherence — Target Verified:** exact clean head
  `fb8cff1` passed all 18 PR checks, then two observed fresh offline tokenizer
  invocations produced distinct byte-identical 587,948-byte reports. All
  14/112/224 records passed with one common 10–18-token continuation count per
  item and zero failures. Internal semantic review and token coherence do not
  establish criterion or model-level reliability.
- **Development-v1 scorer profile — Tested and delivered:** exact closure head
  `e435c40` passed all 18 PR #36 checks. Attempts were frozen as
  A=`canonical` and B=`reverse`, with canonical serialization and no candidate
  deduplication.
- **Development-v1 E4 — Target Failed operationally:** attempt A loaded the
  exact verified model and completed all 224 canonical forwards, then failed
  the post-score resident-VRAM gate before publication. The failure receipt is
  canonical and self-hash-valid; no score was retained or inspected. Attempt A
  is consumed, B did not run, and model-level coherence remains unverified.
- **Scientific boundary — Externally blocked:** no rights-qualified A/B/C
  source roles, causal insertion checkpoint, evaluation freeze, synthetic
  calibration, temporal contrast, or CSTG result exists.

## Evidence

- scorer execution head:
  `cee0f2fa436578bec2f90e57e7ae512f58335323`
- scorer run ID: `run-25453ff5b41cda00b30ac23b046f6a5e`
- run-spec SHA-256:
  `a446008ee9e8196c4091606273cc90c6d54278160449fbd71bc2eab81eb14d9d`
- raw score A/B SHA-256:
  `c3cc112c2aa7f082858ccf60b827290893b488e7adc834293bb8054d15e1cecb`
- score canonical/self SHA-256:
  `c82e8a4e496dac90b2723ca3a847465578d0af79ec4b6c3b1b5188ccf1a77261`
- comparison raw/self SHA-256:
  `ab3002aafe2addc2785bb62f8a8a32cc93ad9042b85819f5e352d57c40e0585d` /
  `fcf155c5414bdcda7ce9cbdd12e1723da35b268d05bc3d96c369401f7850e687`
- scorer report:
  `reports/stage0/pythia_registry_scoring_gate_2026-08-20.md`
- tokenizer report:
  `reports/stage0/pythia_tokenizer_boundary_gate_2026-08-20.md`
- training report:
  `reports/stage0/pythia_lora_resume_gate_2026-08-20.md`
- decisions: D-029 through D-037 in `docs/DECISIONS.md`
- v1 internal review: `evaluations/reviews/development-v1-internal.md`
- v1 registry/criteria SHA-256:
  `81eb8e331d9fbd8d80ec675f209998e081e00834e5d1d141e2979b4f541c49ea` /
  `d73b9d4d575f64587c5aea9acc18a6073a42bb1bd70491d29bd8422e95a73bca`
- v1 tokenizer A/B raw SHA-256:
  `acbb6fed70670c484e719c00775f95532f7282a76579c4c5d12804b5f3e2f76d`
- v1 tokenizer report/verifier self-hashes:
  `8c4f75718ed6da986e2f7c316a62e6c420069577e2fb39919972d91a5857f0bb` /
  `64874e3dd26a150ca34a7000ced4bc52ddd5645cfea82edf05ab6f0cbfe60c72`
- v1 tokenizer evidence report:
  `reports/stage0/pythia_v1_tokenizer_coherence_gate_2026-08-20.md`
- v1 scoring config: `configs/runs/pythia-development-score-v1.json`
- v1 scoring config Git blob / canonical run-spec SHA-256:
  `967868cb1e4f23b7992e88b0fb9e604bcfdeba5c` /
  `e4de6ef590939e156f862f452585678cdc21a7872b6d18c0aaf36464f984bb86`
- E3 working-tree base: `dfa52a0aec11ad8f88fc4378c753a5dafb1ecab8`
- E3 accepted delivery head: `323dd0f72acf6bedc29ec68230a405214293f10d`
- E3 closure / E4 execution head:
  `e435c40f1b1b2c9e8be1c1f3bb6ecd1ea9c89aa0`
- E4 attempt-A run ID: `run-3aa8058dced36e7e88802079925500df`
- E4 topology: 224 canonical forwards; 18,672 forwarded, 18,448 predicted,
  and 3,216 continuation tokens
- E4 audit raw SHA-256:
  `f10cf8d37c53dc30df3f04d16e3b3523215b09a503355945159fd4e57da1e1de`
- E4 failure receipt raw/self SHA-256:
  `19ded6dc8642fd661ac0451b529a52219df563802be6d8d714ce0068e29aa9a7` /
  `79253400d524b883f41073d0be77aa9d0dd3339372ea22ed95e72f1541b8290b`
- E4 failure report:
  `reports/stage0/pythia_v1_scoring_failure_2026-08-20.md`
- failure-evidence delivery head:
  `8fc16af35b27089b1f0bde68c249d0313e8f0e9e` (18/18 checks passed)
- compute ledger: failed v0 training, completed v1 load/control/resume, completed
  v0 scorer A/B, and failed v1 scorer A rows in `COMPUTE_LEDGER.csv`

## Artifacts

- Preserved v0 scoring config: `configs/runs/pythia-development-score-v0.json`
- Active reliability plan:
  `.agent/plans/active-development-measurement-reliability.md`
- Sealed pre-logits registry/criteria:
  `evaluations/registry/development-v1.jsonl` and
  `configs/evaluations/development-v1-reliability-v0.json`
- Sealed pre-execution scoring profile:
  `configs/runs/pythia-development-score-v1.json`
- Ignored v1 tokenizer evidence:
  `artifacts/local/pythia-v1-tokenizer-{a,b,verification}-fb8cff1.json`
- All three ignored v1 tokenizer artifacts have a separate private
  hash-matched backup.
- Ignored E4 failure evidence:
  `artifacts/local/pythia-v1-score-resource-a-e435c40.json` and
  `artifacts/local/pythia-v1-score-runtime-a-e435c40.json`. Both have a
  hash-matched backup in a separate non-Git private directory outside every
  public worktree. Their seven-character suffix deviates from the frozen
  eight-character example, while each payload binds the full exact head;
  preserve the original names.
- No v1 score, attempt-B, comparison, or coherence artifact exists.
- Ignored raw scorer evidence:
  `artifacts/local/pythia-score-{resource-a,resource-b,a,b,runtime-a,runtime-b,comparison}-cee0f2fa.json`
- Raw audits and receipts remain untracked because they contain local paths,
  host, process, filesystem, and GPU identifiers. All seven files also have a
  hash-matched private local backup outside the public repository.
- The deterministic score and comparison artifacts contain no absolute local
  paths but remain ignored under the frozen evidence-publication policy.

## Validation

- Draft PR #34 exact evidence head `a7dd27c`: 18/18 push/PR checks passed across
  Python 3.11, 3.12, and 3.13; PR remains open and draft. The scorer plan is
  complete by its predeclared exact-head closure condition.
- Both target scorer invocations exited 0. The verifier accepted complete
  receipts, strict chronology, distinct process/audit identities, frozen
  Git/model/tokenizer/runtime identity, resource thresholds, and exact score
  equality.
- Peak CUDA allocated/reserved was 1,990.613/2,046 MiB in both attempts,
  below the 3,012 MiB reserved limit. Post-score free VRAM was 1,596 MiB,
  only 60 MiB above the 1,536 MiB floor.
- Host-RAM enforcement was frozen off. Attempt A used that waiver only at its
  post-score observation, 22,320,560 bytes below the reference; attempt B
  passed the reference at every stage.
- Offline/local-only controls were enforced, while traffic observation is
  honestly `not-instrumented`.
- A Windows/Python 3.13 path-versus-descriptor `ctime` mismatch was reproduced
  after E4. The current scoped fix compares portable identity across APIs and
  ctime only within each API view; direct Python 3.13 probes and focused tests
  pass without weakening mutation detection. The full current-tree suite passes
  with 463 tests and two platform-optional skips; all three top-level validators,
  compilation, and diff checks pass. Exact-head CI subsequently passed and
  closed that E5 delivery.
- The E3 implementation passes 142 focused scoring/profile/verifier
  tests. The full offline working-tree suite collects 536 tests and passes 534
  with two platform-optional symlink skips. Production modules compile, pilot,
  model-manifest, and both v0/v1 registry validators pass, and `git diff
  --check` is clean apart from expected line-ending warnings. This is Tested
  evidence only; it does not establish target-model behavior.
- PR #36 first head `e3bd52b` passed 12/18 checks; all six CI jobs rejected
  only a platform-specific error-message assertion while the invalid alias
  remained fail-closed. Head `323dd0f` made that test message-portable and
  passed 18/18 checks across Python 3.11–3.13 for push and pull-request events.
  No model import or scoring occurred in either delivery run.
- PR #36 closure/execution head `e435c40` also passed 18/18 checks before E4.
  Fresh audit A passed every pre-load threshold. Attempt A then loaded the
  verified 1,011,781,632-parameter FP16 model and completed all 224 frozen
  forwards before the post-score resident-VRAM check failed below the
  1,610,612,736-byte floor. The output transaction rolled back. The 32,515-byte
  failure receipt is canonical and self-hash-valid; no score file or outcome
  payload exists. The exact failing free-VRAM value was not retained because
  validation raised before the captured audit returned to the receipt.
- A separate result-blind receipt/code audit confirmed all immutable bindings,
  the 224-forward schedule, rollback, and stop rule. It classified the missing
  failed-audit payload as an observability gap, not proof that the threshold
  rejection was an implementation defect. No rescue is authorized.
- D-038 observability hardening is Tested in the scoped working tree. A real
  below-floor injected audit still raised from the shared validator, while the
  failed receipt retained the exact audit, raw/semantic hashes, phase, frozen
  threshold, and conservative VRAM. Success cleared the pending record and
  returned the unchanged eight-field resident-resource schema. Three focused
  regressions and the full offline suite (536 passed, two skipped) passed; no
  model import, deserialization, logits, or network action occurred.
- Draft PR #37 exact delivery head `d669b4e`: 18/18 push/pull-request checks
  passed across Python 3.11–3.13. The branch is synchronized and clean. This
  externally closes D-038 without a follow-up state-only commit.
- Draft PR #35 implementation head `fb8cff1` passed 18/18 exact-head checks
  across Python 3.11–3.13. Both subsequent tokenizer invocations exited 0; the
  dependency-light verifier and an independent 5,824-assertion replay found no
  discrepancy. A/B bytes, self-hashes, Git/blob identities, token boundaries,
  common counts, and path/privacy controls all match.
- Offline/local-only controls were enforced and downloads were disabled.
  Traffic remained honestly `not-instrumented`. The 2,090,701,528 manifested
  safetensors bytes were rehashed for integrity but never deserialized.

## Risks

- `development-v0` is a small measurement-development registry. Reliability,
  order invariance, criterion validity, direct exposure, contamination, and
  sealed confirmation are not established.
- The 60 MiB post-score VRAM margin is narrow. It does not authorize a larger
  model, a concurrent heavy process, or weaker resident-resource gates.
- The longer v1 schedule crossed the frozen post-score resident-VRAM boundary
  after completing its forwards. E4 is stopped, and the absent score means v1
  coherence cannot be classified. The missing exact failing audit value is an
  observability gap, not proof that the threshold failure was erroneous.
- The five-step LoRA smoke does not establish sustained stability,
  broad-update feasibility, or causal-training adequacy.
- Public visibility exposes branch history, issues, PRs, commit metadata, and
  retained Actions logs. A personal commit email and historical local path
  strings are public; returning the repository to private cannot recall copies.
  No repository license exists, so visibility is not a reuse grant.
- The separate primary checkout contains an unrelated untracked pull-request
  template. Preserve and exclude it unless its provenance is separately
  accepted.

## Delivery state

- Repository: public by explicit user authorization; anonymous access and
  security settings verified.
- Current branch: `feat/live-source-metadata-qualification`, created cleanly
  from exact PR #37 head
  `d669b4e3c36069398efdac831c8f1fec7036359c`. D-039 and the E0 result-blind
  freeze are recorded on this branch; no evidence-bearing live metadata query
  has run.
- Draft PR #37: `https://github.com/Parm-1/ChronoPersona/pull/37`, open and
  draft. Exact head `d669b4e` passed all 18 checks and closes D-038.
- Draft PR #35: `https://github.com/Parm-1/ChronoPersona/pull/35`, open and
  draft. Its final E2 evidence head `dfa52a0` passed 18/18 checks and is the
  intended stack base for E3.
- Draft PR #36: `https://github.com/Parm-1/ChronoPersona/pull/36`, open and
  draft, stacked on PR #35. Exact execution head `e435c40` passed 18/18 checks;
  failure-evidence head `8fc16af` also passed all 18 checks.
- Draft PR #34: `https://github.com/Parm-1/ChronoPersona/pull/34`, open and
  draft, green at final evidence head `a7dd27c`.
- PR #32/#33 remain open draft delivery history. PR #31 was merged externally
  at the preserved v0 head; Codex performed no merge.
- No force push, release, paid operation, model/data publication, or
  third-party contact occurred.

## Next write-active deliverable

Implement and test the D-039 shared evidence contract before any live request:
exact clean-head/input-blob
binding, strict duplicate-key parsing, response hashes, create-only outputs,
final self-hashes, portable paths, and source-C privacy checks. Deliver that
implementation through exact-head CI before executing the bounded metadata
profile. Do not display or human-review transient metadata prose, retrieve an
archive/article body or source package, use requester-pays access, run a model,
retry development-v1 E4, or alter roles/windows/categories after observing
yields.
