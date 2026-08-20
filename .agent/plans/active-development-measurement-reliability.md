# Development Measurement Reliability

**Status:** complete — E0–E3 accepted; E4 Target Failed at exact green head `e435c40` after the consumed canonical attempt completed 224 forwards and failed the post-score VRAM gate before publication
**Started:** 2026-08-20
**Frozen baseline:** `a7dd27c63179e87c8f585adde3e6e2902d72c5d3`
**E3 stack base:** `dfa52a0aec11ad8f88fc4378c753a5dafb1ecab8` on draft PR #35
**Branch:** `feat/development-v1-scoring`
**Delivery:** draft PR #36 is open/draft and stacked on PR #35; exact execution head `e435c40` passed 18/18 checks before the failed target attempt
**Write-active deliverable:** publish D-037, the portable failure report, ledger
row, and closed-plan state; require that evidence head green. Do not run attempt
B or rerun A.

## Objective and claim boundary

Replace the confounded two-form `development-v0` instrument with one controlled
small-set coherence screen. Preserve v0 and its target evidence unchanged. The
v1 registry uses two contexts crossed with two continuation templates and two
explicit candidate orders: eight forms per item, exact 4/4 order balance, and
one common Pythia continuation-token count within each item. These constraints
separate scenario-context sensitivity from continuation-wording sensitivity,
make order duplication explicit, and make the frozen primary total-logprob
margin algebraically consistent with the mean-token diagnostic.

This is measurement development, not confirmatory evaluation. A pass permits a
later multi-model development panel and expansion; it does not establish stable
reliability, criterion validity, a meaningful-effect threshold, a temporal
effect, causal evidence, or CSTG.

## Preserved evidence and diagnosis

- Preserve `evaluations/registry/development-v0.jsonl`, its Git blob
  `39a229ca8a29243bc457f42c5fdc69e303bb5361`, and file SHA-256
  `5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d`.
- Preserve execution head `cee0f2fa436578bec2f90e57e7ae512f58335323`,
  score SHA-256
  `c3cc112c2aa7f082858ccf60b827290893b488e7adc834293bb8054d15e1cecb`,
  and comparison self-hash
  `fcf155c5414bdcda7ce9cbdd12e1723da35b268d05bc3d96c369401f7850e687`.
- Observed v0: four of twelve items reversed primary direction across their two
  forms. The two forms changed scenario, prompt, candidate wording, and JSON
  order simultaneously, so those effects are not separately identifiable.
- Unequal continuation lengths mathematically permitted the two form-level and
  one aggregate primary-versus-mean sign disagreements. Equal length did not
  eliminate all form reversals, so length is a defect channel, not a complete
  causal explanation.
- Candidate array order is not model-visible in the current scorer because each
  continuation is forwarded separately. Registry balance is a design check;
  canonical-versus-reverse execution is a separate engineering invariance.

## Versioned v1 topology

The profile name is `development-v1-pythia-reliability-v0`.

- exactly 14 development items;
- 6 evidence-integration items and 8 procedural-tradeoff items;
- the initial inheritance-oriented draft was rejected before tokenizer
  acceptance by a blind internal semantic audit; the current neutral constructs
  were rewritten from that pre-logits evidence rather than selected from model
  outcomes;
- exactly eight forms per item, 112 forms and 224 candidates total;
- a 2 x 2 x 2 form design per item: two scenario contexts crossed with two
  matched continuation templates and explicit forward/reverse candidate arrays;
- exactly four reference-first and four comparison-first registry forms per
  item;
- same actor role, modality, clause count, grammatical frame, and information
  content across the paired continuations; candidates introduce no facts absent
  from the prompt;
- every item remains `development`; direct-exposure and contamination reviews
  remain pending and prevent any frozen-instrument claim.

Each item is one small development probe, not evidence that its construct is
reliable. At least two items per construct and 24–40 items per primary domain
remain later expansion requirements.

## Frozen tokenizer and metric contract

- Artifact/revision, tokenizer runtime, snapshot, native prefix `none`, and
  maximum length remain exactly those accepted by the Pythia tokenizer gate.
- Every one of the 224 candidate occurrences must pass exact-boundary auditing with zero
  truncation or other failure.
- For item `i`, all sixteen continuation records must share one common token count `N_i`,
  with `1 <= N_i <= 24`.
- Primary metric remains complete-continuation total log probability. Do not
  switch to or select by the mean-token diagnostic.
- Because `N_i` is common, each form must satisfy
  `mean_margin == total_margin / N_i` within `rel_tol=1e-12` and
  `abs_tol=1e-12`; the same relation must hold for the item aggregate.
- No score-derived indifference interval is introduced. Exact zero is a failed
  coherence result. Meaningful-effect magnitude remains deliberately unset.

## Frozen target pass criteria

After the registry, criteria, model, tokenizer, scorer, run profile, Git blobs,
and hashes are sealed on a clean CI-green head:

1. attempt A executes candidates in canonical registry order;
2. after A exits and releases CUDA, staging, and the shared heavy-job lock,
   attempt B uses a fresh resource audit/process and executes candidates in
   reverse order;
3. both serialize canonical registry order and must produce byte-identical
   deterministic score files;
4. all 224 candidate scores are finite and complete, with zero boundary,
   truncation, identity, resource, or publication failures;
5. each item has eight nonzero primary margins with one common sign, so every
   item has directional agreement exactly `1.0`;
6. no form or aggregate has a primary/diagnostic sign mismatch;
7. all 14 items pass. There is no post-result item, form, or domain exclusion.

Canonical/reverse equality proves execution-order invariance and fresh-run
determinism. It does not prove behavioral label-position invariance because
candidate order is not part of the model prompt.

Prompt mention order is held fixed within each item rather than independently
factorialized. The gate therefore tests coherence under one prompt presentation,
not prompt-order invariance or unbiased pole direction. Reference metadata and
`direction_note` must remain outside the provider input; the scorer may pass
only the prompt and one continuation string to the model.

## Stop and rescue policy

Before logits, wording may be revised only from construct review and tokenizer
evidence. Freeze every byte before target scoring.

- A pre-load resource miss may retry only after resources return naturally and
  a new audit passes.
- Any failure after deserialization begins consumes the target attempt.
- Identity drift, incomplete coverage, nonfinite values, truncation,
  non-determinism, order mismatch, any form reversal, exact-zero margin, or any
  primary/diagnostic mismatch fails the whole v1 gate.
- Do not switch metrics, loosen thresholds, rewrite one form, drop one item, or
  run a tie-breaker after seeing v1 logits.
- The only permitted rescue is correction of one independently demonstrated
  implementation defect that is unrelated to the observed pole results. There
  is no presealed alternate wording registry. A semantic/reliability failure
  stops this line and requires a new recorded design decision, not an automatic
  v2.

## Evidence gates

### E0 — Transition and pre-logits decision (completed)

- Close the scorer plan at green exact head `a7dd27c` without rerunning E4.
- Record D-034 and this plan before changing registry wording or inspecting new
  logits.
- Pin v0 bytes/topology in regression tests.

### E1 — Dependency-light contract and registry (completed at `fb8cff1`)

- Add `evaluations/registry/development-v1.jsonl` and an internal review record.
- Add a closed, versioned criteria file plus
  `chronopersona.measurement_reliability` and a verifier CLI.
- Require exact 14/112/224 topology, constructs, eight forms, 4/4 order balance,
  closed schemas, path portability, parent-v0 identity, and deterministic
  self-hashed reports.
- Use blind internal structural reviews that receive v1 wording and the frozen
  criteria but not v0 model margins. Internal review is not independent peer
  review or criterion validation.

### E2 — Exact Pythia tokenizer gate (Target Verified at `fb8cff1`)

- Generalize the exact-known registry selection without weakening v0.
- Run two fresh offline tokenizer audits from the accepted hash-verified
  snapshot; require byte identity, zero failures, 14/112/224 coverage, and the
  common per-item `N_i` contract.
- No PyTorch import, model deserialization, or logits in this gate. Rehashing
  manifested weight bytes remains snapshot integrity, not deserialization.

### E3 — Versioned scorer profile and delivery (completed at `323dd0f`)

- Replace v0-only global scoring constants with an exact allowlist of closed v0
  and v1 profiles; retain compatibility aliases and golden v0 tests.
- Add canonical/reverse execution scheduling with canonical serialization.
- Require cross-profile substitutions to fail before optional import.
- Pass focused tests, full Python 3.11–3.13 CI, all top-level validators,
  compilation, and diff checks on a separate draft PR stacked on PR #35.

### E4 — Bounded target coherence score (Target Failed at `e435c40`)

- Only after E1–E3 pass at one clean exact head, run the canonical and reverse
  attempts under fresh audits and the existing resource envelope.
- Verify both receipts, exact score bytes, and every frozen coherence rule.
- Preserve one actionable failure or one complete equal comparison; do not
  rerun for presentation or timing.

Observed on 2026-08-20: attempt A at exact clean head `e435c40` passed the
fresh audit, identity, tokenizer, snapshot, deserialization, and post-load
resource gates. It completed all 224 canonical candidate forwards, then failed
`post-score-resource-check` below the frozen 1,610,612,736-byte resident-VRAM
floor. The transaction published no valid score, and no pole outcome was
inspected. Attempt A is consumed; B did not run. The seven-character evidence
suffix `e435c40` deviated from the frozen eight-character example `e435c40f`,
but full-head payload bindings remained exact and the deviation was noncausal.

### E5 — Decision and next boundary (completed by D-037)

- Publish only portable bounded aggregates and hashes; keep machine-specific
  receipts/audits private.
- If v1 passes, permit design of a multi-model development panel and expansion
  toward 24–40 items per primary domain. Do not freeze the instrument yet.
- Because v1 failed before score publication, close this pair without B or a
  rerun. A future condition requires a new recorded decision; only a result-
  blind, independently demonstrated implementation defect can qualify for the
  plan's one permitted rescue.
- If v1 fails semantically, stop model execution and record the failed design.
- Real-source qualification and causal training remain separately blocked.

## Required regression coverage

- v0 registry/config hashes and 12/24/48 topology remain exact.
- Missing, extra, duplicate, or unknown v1 item/form/candidate/criteria fields
  fail closed.
- One token-count deviation anywhere within an item fails.
- One unbalanced candidate order fails.
- Eight same nonzero signs pass; one reversal or zero fails.
- Any form/aggregate primary-diagnostic sign mismatch fails.
- Canonical and reverse provider call orders differ while canonical output is
  identical; a stateful/order-dependent provider fails comparison.
- Cross-profile registry, config, tokenizer-audit, scorer, or hash substitution
  fails before model import.
- Reports are dependency-light, canonical, self-hashed, path-free, and retain
  every failure.
- Existing tokenizer, scorer, training, registry, and repository-state tests
  remain green.

## Hard boundaries

- No external compute spend, paid licenses, new downloads, training, public
  model/data release, or real-source access is part of this plan.
- No target logits before the current closure head and fresh resource audit
  pass.
- Internal semantic review cannot establish human criterion validity.
- A v1 pass is one-checkpoint coherence only; a v1 semantic failure stops this
  workstream rather than authorizing outcome-driven wording search.

## Observed pre-logits results

- 2026-08-20: the first inheritance-oriented 14-item draft was rejected before
  tokenizer acceptance by blind internal review: 11 of 14 items had a concrete
  dominance, construct, or template defect. No model weights or logits were
  opened; the draft was discarded rather than tuned against pole outcomes.
- 2026-08-20: a neutral replacement draft passed 10 items and exposed four
  bounded defects: a missing reporting counter-cost, an additive dominance
  error, one asymmetric review-slot template, and one systematic breadth/depth
  length cue. The reviewer supplied the fixes, which were applied before any
  scoring.
- 2026-08-20: a local tokenizer-only diagnostic on the accepted Pythia snapshot
  found one common continuation-token count for every current item. Counts are
  9 through 18 tokens, within the frozen 1–24 range. This is diagnostic wording
  evidence only; the later clean-head E2 result supersedes it for acceptance.
- 2026-08-20: the final blind semantic lock accepted all 14 items and found no
  explicit temporal, institutional, political, demographic, copied-survey, or
  pole-specific moral cues. The review saw no v0 outcomes, tokenizer outputs,
  model outputs, or logits. `temporal-cues` and `political-moral-wording` now
  pass; direct-exposure and contamination remain pending. The durable review
  is `evaluations/reviews/development-v1-internal.md`.
- The sealed generated candidate is 14 items / 112 forms / 224 candidates,
  registry SHA-256
  `81eb8e331d9fbd8d80ec675f209998e081e00834e5d1d141e2979b4f541c49ea`,
  and criteria SHA-256
  `d73b9d4d575f64587c5aea9acc18a6073a42bb1bd70491d29bd8422e95a73bca`.
  The tokenizer validator now derives exact registry/criteria Git blobs, binds
  the frozen manifest blob and expected execution head, rejects inconsistent
  token IDs for identical text, and requires two distinct canonical
  byte-identical E2 reports.
- Dependency-light registry, tokenizer, score-identity, evaluation-loader, and
  verifier-CLI coverage passed 51 focused tests before E3 implementation.
- The full working-tree suite passes 494 tests with two platform-optional
  symlink skips. Generator reproduction, compilation, the three top-level
  validators, and diff checks pass. Draft PR #35 then passed all 18 exact-head
  checks on Python 3.11–3.13 at `fb8cff1`.
- 2026-08-20: two observed fresh offline tokenizer invocations at exact clean
  head `fb8cff1` produced distinct 587,948-byte files with identical raw
  SHA-256
  `acbb6fed70670c484e719c00775f95532f7282a76579c4c5d12804b5f3e2f76d`.
  All 14/112/224 records passed, common per-item continuation counts were
  10–18, and the canonical verifier report passed with no errors. No model
  weights were deserialized and no logits were inspected. The bounded report
  is `reports/stage0/pythia_v1_tokenizer_coherence_gate_2026-08-20.md`.
- 2026-08-20: E3 now has one closed v0/v1 scoring-profile allowlist,
  canonical/reverse full-occurrence scheduling without deduplication, canonical
  serialization, profile-bound receipts, and integrated repeat/coherence
  verification. Adversarial tests reject registry text substitution,
  cross-profile evidence, forged schedules, noncanonical inputs, and portable
  path aliases before optional model import. Focused and full offline suites,
  production compilation, top-level validators, and diff checks pass in the
  working tree. This was Tested pre-execution evidence only; delivery acceptance
  is recorded in the next entry. Model deserialization and v1 logits still do
  not exist.
- 2026-08-20: draft PR #36 first head `e3bd52b` passed 12/18 checks; six Linux
  CI jobs failed only because a fail-closed alias test required the Windows
  error message. The message-portable correction at exact head `323dd0f`
  passed all 18 push/PR checks across Python 3.11–3.13. E3 is accepted; no
  model import, deserialization, or scoring occurred.
- 2026-08-20: closure/execution head `e435c40` passed all 18 checks. Fresh
  resource audit A passed, then run `run-3aa8058dced36e7e88802079925500df`
  loaded the exact model and completed 224 canonical forwards. The post-score
  resident-resource check failed before publication; the canonical receipt is
  self-hash-valid, no score file exists, no outcome was inspected, and attempt
  B was not started. D-037 closes E4 as Target Failed.

## Restart procedure

1. Read `PROGRESS.md`, D-034 through D-037, the portable E4 failure report, and
   this plan.
2. Verify branch `feat/development-v1-scoring`, execution head `e435c40`, the
   absent A score/B artifacts, and the preserved private audit/receipt hashes.
3. Publish the failure-evidence state and require its exact head green. Do not
   run A or B. Any result-blind defect investigation or new scoring condition
   must begin under a separate recorded decision and plan.
