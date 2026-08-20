# ChronoPersona Progress

**Last updated:** 2026-08-20T15:14:11-04:00

## Decision

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

The user explicitly authorized making `Parm-1/ChronoPersona` public to restore
free standard GitHub-hosted Actions. The repository is public, anonymous access
works, fork workflows require approval from all external contributors, default
workflow tokens remain read-only, and secret scanning plus push protection are
enabled. The prior zero-step billing blocker is empirically closed: draft PR
#34 passed all 18 exact-head checks. No billing setting changed.

## Current objective and closure condition

Deliver the sealed `development-v1` measurement-coherence contract without
loading model weights. The final blind semantic lock accepted exactly 14 items,
eight forms per item from two contexts x two templates x two explicit candidate
orders, and exact 4/4 order balance. Finish adversarial contract review, push a
focused draft PR, and require exact-head CI before two fresh offline tokenizer
audits. Model scoring remains blocked until those reports pass and the v1
scoring profile is separately frozen.

## Current verified boundary

- **Development content-integrity gate — Target Verified:** bounded
  redistributable fixtures passed. Real-source qualification remains
  **externally blocked**.
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
- **Development-v1 pre-logits contract — Tested:** all 14 sealed items passed
  internal blind semantic lock; the generated 14/112/224 topology, closed
  criteria, tokenizer bindings, and failure paths pass focused tests. Internal
  review is not criterion validation, and the required clean-head E2 tokenizer
  pair has not run.
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
- decisions: D-029 through D-034 in `docs/DECISIONS.md`
- v1 internal review: `evaluations/reviews/development-v1-internal.md`
- v1 registry/criteria SHA-256:
  `81eb8e331d9fbd8d80ec675f209998e081e00834e5d1d141e2979b4f541c49ea` /
  `d73b9d4d575f64587c5aea9acc18a6073a42bb1bd70491d29bd8422e95a73bca`
- compute ledger: failed v0, completed v1 load/control/resume, and scorer A/B
  rows in `COMPUTE_LEDGER.csv`

## Artifacts

- Preserved v0 scoring config: `configs/runs/pythia-development-score-v0.json`
- Active reliability plan:
  `.agent/plans/active-development-measurement-reliability.md`
- Sealed pre-logits registry/criteria:
  `evaluations/registry/development-v1.jsonl` and
  `configs/evaluations/development-v1-reliability-v0.json`
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
- The current v1 pre-logits implementation passes 51 focused dependency-light
  registry, tokenizer, verifier, and evaluation-loader tests. This is
  working-tree Tested evidence only; no v1 tokenizer acceptance report,
  scoring profile, model deserialization, or logits exist yet.
- The full working-tree suite passes 494 tests with two platform-optional
  symlink skips. Generator reproduction, compilation, all three top-level
  validators, and diff checks pass. Exact-head CI remains the delivery gate.

## Risks

- `development-v0` is a small measurement-development registry. Reliability,
  order invariance, criterion validity, direct exposure, contamination, and
  sealed confirmation are not established.
- The 60 MiB post-score VRAM margin is narrow. It does not authorize a larger
  model, a concurrent heavy process, or weaker resident-resource gates.
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
- Current branch: `feat/development-measurement-reliability`, based on scorer
  evidence head `a7dd27c`. Its delivery head and exact-head CI status are live
  GitHub state and must not be inferred from this preserved base identity.
- Draft PR #34: `https://github.com/Parm-1/ChronoPersona/pull/34`, open and
  draft, green at final evidence head `a7dd27c`.
- PR #32/#33 remain open draft delivery history. PR #31 was merged externally
  at the preserved v0 head; Codex performed no merge.
- No force push, release, paid operation, model/data publication, or
  third-party contact occurred.

## Next write-active deliverable

Complete E1 adversarial review and deliver the scoped implementation on a new
draft PR. After exact-head CI passes, run the two distinct canonical
byte-identical E2 Pythia tokenizer audits. Do not deserialize model weights or
inspect v1 logits before the separate scorer-profile and exact-head CI gate.
