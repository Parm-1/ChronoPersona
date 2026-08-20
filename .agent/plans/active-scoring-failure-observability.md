# Scoring Failure Observability

**Status:** implementation Tested; complete when every check passes on the unchanged delivery head, otherwise active at the first failed delivery gate
**Started:** 2026-08-20
**Baseline:** `8fc16af35b27089b1f0bde68c249d0313e8f0e9e`
**Branch:** `fix/scoring-failure-observability`
**Stack base:** draft PR #36 / `feat/development-v1-scoring`
**Write-active deliverable:** preserve an exact resident-resource observation in
future failed scorer receipts when validation raises, then deliver the bounded
fix through exact-head CI. Do not execute a model or reopen E4.

## Objective and claim boundary

Fix one result-blind failure-evidence defect exposed by the consumed
`development-v1` E4 attempt. The scorer currently captures a live post-load or
post-score resource audit, but validation can raise before the captured audit is
stored in the failure context. Future failed receipts must retain that exact
observation and its hashes without weakening the resource gate.

This plan is evidence-observability hardening only. It cannot reconstruct the
missing post-score value from attempt A, show that the rejection was erroneous,
recover a score, authorize attempt B, authorize an A retry, or establish model
behavior. D-037 and every E4 stop rule remain in force.

## Preserved evidence

- E4 attempt A remains consumed at exact clean head
  `e435c40f1b1b2c9e8be1c1f3bb6ecd1ea9c89aa0`.
- Run `run-3aa8058dced36e7e88802079925500df` completed 224 canonical
  forwards and failed `post-score-resource-check` before publication.
- The audit and failure receipt remain unchanged, ignored, privately backed
  up, and bound by the hashes recorded in D-037.
- No score, attempt B, comparison, or coherence artifact exists; no pole
  outcome was inspected.
- Failure-evidence head
  `8fc16af35b27089b1f0bde68c249d0313e8f0e9e` passed all 18 draft-PR
  checks.

## Frozen implementation

1. In `_resident_resource_check`, immediately after capture and before
   `_validate_execution_resources`, store a clearly partial
   `pending_resident_resource_check` record in the existing mutable resource
   state.
2. Bind the record to the phase label, raw audit SHA-256, semantic SHA-256,
   capture timestamp, audit age, frozen minimum-free-VRAM threshold,
   conservative VRAM observation, and complete captured audit.
3. Leave the pending record present if resource validation or the explicit
   conservative-free check raises. Remove it only after the resident check
   fully passes.
4. When a failed receipt is built, copy a present pending record to
   `failure_context.failed_resident_resource_check`.
5. Do not change validator order, thresholds, resource policy, score
   construction, successful resource-record shape, complete receipt schema,
   output transaction behavior, or any v0/v1 frozen identity.

The raw failed receipt remains ignored/private because the embedded audit can
contain host, process, device, and filesystem identity. Public evidence may
publish only a sanitized aggregate and hashes.

## Evidence gates

### E0 — Result-blind freeze

- Record D-038 and this plan before implementation.
- Bind the work to baseline `8fc16af` on a separate branch.
- Reaffirm that the fix supplies no rescue authority.

**Result:** completed in the pre-implementation plan commit based on
`8fc16af`.

### E1 — Failure-context implementation

- Preserve the exact captured observation before validation can raise.
- Copy it into a failed receipt without changing successful output semantics.
- Keep all resource failures fail-closed and score publication rolled back.

**Result:** completed. The pending record is stored before the shared validator;
the validator retains its original call order and exception precedence. Failure
enrichment bare re-raises the original exception, while success clears the
pending record and returns the prior eight-field schema.

### E2 — Dependency-light validation

- Inject a well-formed below-floor post-score audit and use the real shared
  resource validator.
- Require the same threshold exception while the pending record retains the
  exact audit, hashes, label, conservative value, and frozen floor.
- Require the failed receipt to expose the record while
  `scientific_claim_authorized=false` and `valid_score_published=false`.
- Require a successful resident check to clear the pending record and return
  the preexisting success schema exactly.
- Run focused scoring tests, the full offline suite, top-level validators,
  compilation, and `git diff --check`. No model import, deserialization,
  logits, or network action is part of validation.

**Result:** completed in the scoped working tree. Three focused resident-
resource regressions passed. The full offline suite passed 536 tests with two
platform-optional skips. Pilot, model-manifest, development-v0, and
development-v1 validators passed; changed modules compiled; `git diff --check`
was clean apart from line-ending warnings. No model import, deserialization,
logits, or network action occurred.

### E3 — Delivery

- Freeze the implementation, validation, and closure state in the scoped
  delivery commit before pushing it.
- Open one draft PR stacked on draft PR #36.
- Require every attached check to pass on one unchanged exact head.
- When those external checks pass, that unchanged head is exact-head delivered
  and this plan is complete. Do not add a post-green state-only closure commit,
  and do not run E4.

## Stop conditions

- Stop if the change weakens or reorders validation, changes a frozen threshold
  or score/receipt identity, makes machine-specific evidence public, or needs a
  model execution to validate.
- Stop if successful receipt bytes or preserved v0 evidence change.
- Do not turn an observability fix into a scoring rescue. A future scoring
  condition still needs a separate material decision and a causal defect that
  could invalidate the failed execution decision.

## Hard boundary after delivery

After this gate, no further model execution is authorized. Scientific progress
requires bounded rights-qualified, historically version-bounded A/B samples
and an explicitly authorized held-out source-C review packet. A new scoring
condition or scientific source-access decision is outside this plan.

## Restart procedure

1. Read `PROGRESS.md`, D-037, D-038, and this plan.
2. Verify branch `fix/scoring-failure-observability` is based on exact green
   head `8fc16af` and inspect the scoped diff.
3. Continue the earliest incomplete evidence gate without loading a model.
4. Preserve consumed E4 attempt A and do not run attempt B.
