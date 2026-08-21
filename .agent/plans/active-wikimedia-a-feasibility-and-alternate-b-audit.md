# Wikimedia A Feasibility and Alternate-B Audit

**Status:** active — D-042 result-blind feasibility gate
**Started:** 2026-08-21
**Baseline:** `55a8e4f76f18c9d72cd1e9b36ae6d879ecd20da9`
**Write-active deliverable:** one synthetic-tested Wikimedia feasibility runner
and one aggregate-only result-blind alternate-B audit report.

## Objective and claim boundary

Measure only whether a tiny historical Wikimedia revision sample can traverse
the D-041 parser path with auditable version, rights, attribution, and storage
evidence. In parallel, determine whether at least one non-Q&A candidate merits
a later source-B feasibility proposal. This is not source qualification, a
source-role freeze, corpus acquisition, model work, or a scientific result.

Stack Exchange is dormant: no network request, dump, API call, archive, text,
identifier, or manual review is permitted unless explicit written authorization
or an independently reviewed compliant access contract is later recorded.

## Frozen scope

- Source endpoint: English Wikipedia read-only Action API only.
- Candidate windows: 2012-01-01 through 2013-12-31 and 2018-01-01 through
  2019-12-31; they remain candidate windows, not final eras.
- Maximum retained child revisions: four per window; every child requires its
  exact immediate parent. Maximum retained pairs: eight.
- Maximum live requests: 32 total, no authentication, no account, no charge,
  no retry, and no source substitution.
- Public output: canonical aggregate counts, byte totals, closed disposition
  counts, profile/source hashes, and receipt hashes only. IDs, page titles,
  contributor fields, URLs, raw wikitext, normalized prose, and request details
  remain private.
- Private output: owner-restricted, create-only local artifact root outside Git;
  no raw output is committed, copied, or displayed.
- Alternate-B work: official documentation and metadata only. At least one
  non-Q&A candidate is audited; candidate text, feeds, bulk files, and APIs are
  out of scope.

## E0 — Documentation and contract freeze

1. Record official Wikimedia Action API, revision, user-agent, and reuse
   requirements in a source-bound audit note.
2. Record Stack Exchange’s current automated-AI restriction and keep it
   dormant; do not infer that Creative Commons contribution licensing resolves
   access permission or downstream model obligations.
3. Freeze a closed D-042 profile with candidate enumeration, deterministic
   selection seed and ordering, exact request parameters, byte/request caps,
   receipt schema, private-root identity, and stop reasons.
4. Add synthetic API-response fixtures and negative tests for response identity,
   child/parent linkage, hidden content, reparse/redirect drift, request cap,
   output containment, and no-public-prose behavior.

**Acceptance:** no real record has been opened; profile, fixtures, and runner
pass isolated validation and bind exact source/config/runtime inputs.

## E1 — Wikimedia A feasibility execution

1. Enumerate metadata only under the frozen profile; select by a deterministic,
   content-blind rule before any selected revision content is read.
2. For each selected child, retrieve and bind the exact child and immediate
   parent; reject missing, cross-page, hidden, non-main-slot, redirect, or
   identity-mismatched results.
3. Run the D-041 conservative added-span parser. Preserve parse failures,
   unresolved lineage, rights/attribution gaps, and zero-yield cells.
4. Stop immediately on any transport, cap, binding, or containment failure.
   Publish no aggregate unless every frozen request and terminal rebind pass.

**Acceptance:** a valid aggregate may report feasibility counts only. It must
not declare Wikimedia qualified, set source A, select source B/C, or expose any
text/identifier. Any failure is a preserved operational outcome, not permission
to modify selection or retry.

## E2 — Alternate-B result-blind audit

For at least one non-Q&A candidate, gather only current primary documentation
and metadata evidence for automated access, cost, licenses/attribution,
timestamp/version semantics, historical access, likely direct-exposure risks,
and whether a bounded parser/yield sample could be specified. Classify it as
`candidate`, `blocked`, or `not-suitable`; do not select it as B.

**Acceptance:** the report distinguishes source-reported facts from inferences,
contains no candidate prose or identifiers, and ends with a bounded next
decision rather than a role assignment.

## Stop conditions

Stop before or during execution on a payment, account/terms acceptance,
credential requirement, unfrozen endpoint/selection/order, request or byte cap,
bulk retrieval, non-Wikimedia real text, Stack Exchange access, source-C path,
portable private-data leak, model operation, or any attempt to select a source
from behavioral direction. Do not recover a failed E1 run by retrying,
substituting, or changing the selection.

## Restart procedure

1. Verify `main`, D-040 through D-042, `PROGRESS.md`, this plan, and the
   source-sample protocol.
2. Confirm the D-042 profile and private output root are exact, owner-restricted,
   outside Git, and distinct from D-039 artifacts.
3. Resume only the current numbered gate. Do not open a Stack Exchange or
   source-C path.
