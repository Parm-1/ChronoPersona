# Decision Log

Durable research decisions are recorded here. Reversals append a new entry; they do not erase prior rationale.

## D-001 — Treat temporal adaptation as an intervention

**Date:** 2026-08-17
**Status:** accepted

ChronoPersona studies behavior caused by defined corpus interventions. It does not claim to reconstruct an authentic historical person or population.

**Reason:** This is testable and keeps claims aligned with what the training design can identify.

## D-002 — Separate knowledge, style, and disposition

**Date:** 2026-08-17
**Status:** partially superseded by D-008

Temporal knowledge, temporal style, and date-neutral disposition were initially separated.

**Preserved:** knowledge and surface-era effects remain distinct from behavioral outcomes.

**Superseded:** “temporal disposition” is no longer the main construct. The project now distinguishes temporal register, residual temporal signature, source-specific effects, CSTG, path dependence, and temporal representation.

## D-003 — Start with a two-slice 2008/2024 pilot

**Date:** 2026-08-17
**Status:** superseded by D-010 and D-011

The initial scaffold proposed a maximally separated 2008/2024 pilot.

**Reason for supersession:** a single-source, cutoff-like contrast does not identify a source-general era component. The revised program uses synthetic calibration followed by provisional 2012–2013 versus 2018–2019 era windows across independent sources.

## D-004 — Require unadapted and date-shuffled controls

**Date:** 2026-08-17
**Status:** superseded in scope by D-012

The initial pilot required an unadapted checkpoint and date-shuffled control.

**Preserved:** an unadapted base and order/shuffle diagnostics remain useful.

**Expanded:** the required minimal naturalistic controls are now common generic continuation, matched mixed-era text, within-era pseudo-era placebo, and an order control where feasible.

## D-005 — Freeze evaluation before trained outputs

**Date:** 2026-08-17
**Status:** accepted and strengthened

A versioned evaluation registry, scoring procedure, meaningful-effect threshold, exclusions, and primary contrasts must be frozen before confirmatory condition outputs are inspected.

**Reason:** The project has many plausible constructs and metrics. Without a freeze, researcher degrees of freedom could manufacture a narrative.

## D-006 — Prefer a cheap falsification sequence

**Date:** 2026-08-17
**Status:** accepted and strengthened by D-015

Literature, data, measurement, sensitivity, and throughput gates precede large training runs.

**Reason:** The scarce resource is credible evidence, not generated text. Early failures should be found before compute is spent.

## D-007 — No license selected yet

**Date:** 2026-08-17
**Status:** accepted

The repository remains without an open-source license.

**Reason:** Licensing code, data-derived artifacts, and collaboration outputs is a rights decision and should not be guessed during scaffolding.

## D-008 — Make CSTG the central scientific construct

**Date:** 2026-08-17
**Status:** accepted

The central measurable phenomenon is **Cross-Source Temporal Generalization**: agreement between independently induced early-versus-late behavioral contrasts from unrelated naturalistic source families, including prediction on a held-out source.

**Reason:** Historical checkpoint construction and single-source cross-domain behavioral transfer appear to have close prior art. Cross-source naturalistic replication with held-out-source prediction is the sharper causal gap, subject to Stage 0 verification.

**Consequence:** “Historical personality” remains informal motivation only. A temporal prior is an interpretation reserved for controlled CSTG.

## D-009 — Treat public dated checkpoints as observational infrastructure

**Date:** 2026-08-17
**Status:** accepted

DatedGPT, PIT, ChronoGPT, TypewriterLM, and other historical models are candidates for evaluation validation and boundary analysis. They do not substitute for the common-starting-weight causal intervention.

**Reason:** Their architectures, corpora, lineages, doses, and training procedures differ. Pooling them would confound temporal effects with model construction.

**Verification status:** exact artifacts and claims remain unverified until the Stage 0 audit.

## D-010 — Require Synthetic Identifiability Calibration

**Date:** 2026-08-17
**Status:** accepted

Before interpreting a naturalistic null, the project must show that the chosen model, dose, training method, scorer, and evaluation recover a known cross-domain latent procedural signal.

**Reason:** Without sensitivity calibration, a null cannot distinguish absence of a temporal effect from insufficient scale, dose, transfer capacity, or measurement.

**Consequence:** calibration failure makes a naturalistic null inconclusive. One predeclared rescue is permitted.

## D-011 — Use two provisional era windows and independent source families

**Date:** 2026-08-17
**Status:** accepted as provisional

The current design candidates are:

- early: 2012-01-01 through 2013-12-31;
- late: 2018-01-01 through 2019-12-31.

The exploratory causal pilot uses two independent source families and three seeds per era/source cell.

**Reason:** The windows align approximately with candidate public checkpoint years while avoiding the pandemic and widespread public generative-AI deployment.

**Boundary:** source continuity, timestamps, rights, authorship, topic balance, and event concentration determine the final windows before behavior is inspected.

## D-012 — Expand the minimum control set

**Date:** 2026-08-17
**Status:** accepted

The naturalistic pilot must include:

- unadapted base;
- common generic continuation;
- matched mixed-era corpus;
- within-era pseudo-era placebo;
- one training-order or chronology control where feasible.

**Reason:** The design must distinguish historical content from generic optimization, mixture, arbitrary partitions, and final-window recency.

## D-013 — Make held-out source C the primary confirmation

**Date:** 2026-08-17
**Status:** accepted

Source C is selected during the data audit but cannot be used for item construction, temporal-direction estimation, hyperparameter selection, dose selection, threshold selection, or mechanism-layer selection.

The shared component is estimated on A and B, frozen, and tested on C.

**Reason:** A/B agreement alone can still reflect researcher adaptation to those sources. Held-out-source prediction is the strongest practical confirmation of source-general temporal structure.

## D-014 — Measure response to common post-training

**Date:** 2026-08-17
**Status:** accepted

Selected early and late branches will receive identical later SFT and, only if justified, identical preference training.

The analysis measures both final endpoints and the change caused by the common update.

**Reason:** models with similar endpoints may respond differently to identical later training. This path-dependent response may be more informative than a static personality score.

## D-015 — Bind the project to a resource escalation ladder

**Date:** 2026-08-17
**Status:** accepted

The default resource envelope is:

- current reported machine: RTX 2060 and 16 GB RAM;
- possible borrowed machine: RTX 5070 and 32 GB RAM, not assumed available;
- CAD $0 external compute;
- one training job at a time;
- measured memory, throughput, storage, and cost before budgets;
- no rental, hardware purchase, paid license, or large branch set without explicit user authorization.

**Reason:** The user wants to spend as little as possible while preserving paper quality. Cheap falsification and measured escalation prevent both waste and scientifically underpowered spending.

## D-016 — Keep OLMo 2 1B provisional

**Date:** 2026-08-17
**Status:** accepted

OLMo 2 1B at a suitable intermediate checkpoint is the provisional causal-base candidate, not the selected model.

**Reason:** its reported openness and intermediate artifacts may support controlled insertion of an era window, but exact revisions, code, license, memory, training support, capability, and post-training compatibility must be verified and benchmarked.

## D-017 — Do not base the headline causal claim on PEFT alone

**Date:** 2026-08-17
**Status:** accepted

Parameter-efficient methods are permitted for pipeline debugging, scorer validation, dose reconnaissance, and cost estimation.

The headline naturalistic experiment should use full-weight continued pretraining or a broad-update approximation justified before results.

**Reason:** adapter geometry could be mistaken for a temporal causal effect, and attaching a small adapter to a completed modern model does not create a historically bounded model.

## D-018 — Use conditional continuation likelihoods as the primary instrument

**Date:** 2026-08-17
**Status:** accepted as provisional evaluation architecture

Primary pairwise outcomes use complete natural-language continuation likelihoods with option reversal, paraphrases, tokenizer diagnostics, raw normalized probabilities, and one prespecified calibrated alternative.

**Reason:** this reduces dependence on open-ended judge narratives and supports precise counterbalancing.

**Boundary:** scorer reliability must still be demonstrated before freezing the instrument.

## D-019 — Preserve a strict claim ladder

**Date:** 2026-08-17
**Status:** accepted

The project uses Levels 0–5:

0. no reliable effect;
1. knowledge or register;
2. source-specific temporal effect;
3. CSTG;
4. persistence or path dependence;
5. shared causal representation.

**Reason:** compelling examples, year classifiers, single-source transfer, and correlational probes should not be promoted into stronger claims.

## D-020 — One rescue per failed major gate

**Date:** 2026-08-17
**Status:** accepted

Each major negative gate permits at most one predeclared rescue: a named dose increase, scale increase, demonstrated scorer repair, or replacement of a source that failed prespecified feasibility criteria.

**Reason:** repeated redesign after observing nulls would convert falsification into positive-result search.

## D-021 — Accept the bounded content-integrity gate and stop before real-source acquisition

**Date:** 2026-08-18
**Status:** accepted at development-fixture level

Accept the deterministic content-manifest and lexical integrity implementation as the Stage 0 gate for bounded sample audits.

The accepted gate includes:

- exact raw and normalized content identities;
- portable path and symlink safety across Linux and Windows path forms;
- exact and bounded lexical near-duplicate channels;
- evaluation-overlap and direct-construct triage;
- cross-source, cross-era, cross-role, and held-out-boundary flags;
- exact authorization before opening non-fixture source-C content;
- text-free deterministic reports;
- no automatic exclusion or scientific eligibility decision.

**Reason:** Before any real historical text can support a causal training intervention, the repository must be able to prove what text it read, detect obvious contamination and overlap, preserve held-out boundaries, and produce reviewable identities without leaking source content.

**Claim ceiling:** this decision validates development tooling on redistributable synthetic fixtures only. It does not establish semantic independence, acceptable contamination rates, source-family independence, production-scale behavior, source eligibility, or any temporal model effect.

**Next gate:** bounded real-content qualification. That gate is externally blocked until small rights-qualified, version-bounded A/B samples and an explicitly authorized source-C review packet exist. Bulk acquisition and model training remain unauthorized.

**Evidence:** `reports/stage0/content_integrity_gate_decision.md` and `reports/stage0/content_integrity_bundle_recovery.json`.

## D-022 — Treat portable paths, fixture provenance, and source-C authorization as identity boundaries

**Date:** 2026-08-18
**Status:** accepted

Persisted repository, manifest, checkpoint, and artifact paths must use one canonical forward-slash relative spelling that is safe on POSIX and Windows. Traversal aliases, backslashes, drive forms, control characters, non-NFC spellings, case-insensitive collisions, Windows-reserved names, forbidden characters, and components ending in a space or period fail closed.

A content record marked as a synthetic fixture must use `synthetic-fixture` authorship provenance, and that authorship value cannot be attached to a non-fixture record. A source-C authorization is valid only when the exact bound manifest contains at least one non-fixture source-C adaptation record; extraneous authorization is rejected.

**Reason:** Cross-platform path aliases and contradictory provenance can change which bytes are read without changing a superficially similar manifest. Stale or unrelated authorization can create misleading evidence that the held-out firewall was satisfied. These are identity failures, not recoverable warnings.

**Boundary:** this decision hardens development tooling. It does not authorize source acquisition or establish that any real source is eligible.

## D-023 — Make evidence semantics executable rather than descriptive

**Date:** 2026-08-18
**Status:** accepted

Claims about token-aligned evaluation exposure, option-order counterbalancing, metadata-only operation, model readiness, and official metadata origins must be enforced by validators rather than left as documentation conventions.

The final Stage 0 review therefore requires contiguous token-sequence exposure checks, both balanced candidate orders, recursive metadata payload rejection, exact digest formats, non-negative token identities, non-positive finite log probabilities, benchmark-ready artifacts that satisfy the executable no-remote-code policy, and exact HTTPS host allowlists that redirects cannot escape.

**Reason:** A documented rule that malformed evidence can bypass is not an integrity boundary. These checks prevent silent false positives, false negatives, misleading readiness labels, and source-origin drift.

**Boundary:** these changes harden development evidence. They do not qualify real corpora, authorize network or corpus acquisition, or advance the claim ladder.

## D-024 — Accept the final Stage 0 repository hardening and preserve the external stop boundary

**Date:** 2026-08-18
**Status:** accepted subject to exact-head CI

Accept the final repository review as a hardening pass over the existing Stage 0 development system. The accepted scope centralizes portable persisted-path identity, makes bounded manifest limits apply during planning and execution, tightens fixture and source-C authorization semantics, enforces tokenizer/scorer/evaluation/model-readiness evidence, constrains live metadata requests to exact HTTPS origins, verifies generated coverage, cache, and bytecode state are absent from Git, and adds a regression guard against their return.

**Reason:** research infrastructure is only defensible when the repository state, validators, workflows, and documentation enforce the same boundaries. Machine-generated cache state and permissive type or path coercions are not valid scientific evidence.

**Claim ceiling:** this is an engineering and governance pass. It does not qualify real source content, demonstrate model sensitivity, authorize training, or advance CSTG beyond the existing claim level.

**Decision after validation:** merge only after the exact PR head passes CI, content-integrity, source, synthetic-calibration, and run-registry workflows on Python 3.11, 3.12, and 3.13. Then stop at the bounded real-content and local-model evidence boundary.

**Evidence:** `reports/stage0/final_repository_review.md`.

## D-025 — Accept the no-weight model/runtime preflight and preserve the acquisition boundary

**Date:** 2026-08-20
**Status:** accepted at metadata and runtime-preflight level

Accept the bounded local resource audit, metadata-only Hub audit, corrected
artifact identities, and benchmark-integrity hardening as the first measured
part of Milestone 0B.

The accepted preflight establishes that:

- PyTorch `2.13.0+cu130` exposes CUDA 13.0 on the local RTX 2060;
- the selected public artifacts are pinned when a live immutable revision is
  available, while missing licenses and unreviewed execution paths remain
  fail-closed;
- the OLMo `stage1-step20000-tokens42B` artifact is bound to
  `f9dd86fb2eee6a7f0c79dc6fc2f671b58523cddb`, not the distinct default/main
  artifact;
- exactly one artifact, final Pythia 1B deduped at
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`, is eligible for the first
  loading/logits benchmark;
- benchmark execution requires an exact-clean-head resource audit and records
  actionable structured failures.

**Reason:** artifact identity, executable policy, and measured machine state
must be trustworthy before a multi-gigabyte weight acquisition or an OOM can be
interpreted as model feasibility evidence.

**Claim ceiling:** no model weights were acquired, no model was loaded, no
logits or training throughput were measured, no checkpoint/resume path was
validated, and no temporal claim is advanced.

**Boundary:** the 2.09 GB final Pythia artifact is not downloaded under the
current authorization. Tiny continued pretraining remains further gated on a
successful load, measured headroom, and its own legal/resource preflight.

**Evidence:** `reports/stage0/model_compute_preflight_2026-08-20.md`.

## D-026 — Activate bounded local model acquisition and training measurement

**Date:** 2026-08-20
**Status:** accepted and active

The user explicitly lifted restrictions on model downloads and training. The
project may therefore acquire pinned, legally cleared model artifacts and run
bounded local loading and training measurements without another routine
permission request.

The first active operation remains one immutable final-Pythia acquisition and
CUDA loading/logits benchmark. Training follows only if that measurement gives
enough headroom to design a deterministic tiny checkpoint/resume gate.

**Reason:** the prior stop was an authorization boundary rather than negative
model evidence. Removing it should advance the smallest measured gate, not
silently expand to every candidate, corpus, branch, or compute environment.

**Preserved requirements:** verified license and immutable identity, no
unreviewed remote code, exact run/resource binding, one heavy job at a time,
structured failure preservation, and immediate stop on integrity mismatch,
swapping, repeated OOM, severe desktop impact, thermal/driver instability, or
disk risk.

**Scope interpretation:** the active local gate remains CAD $0 and requires no
paid service, public release, repository-visibility change, or third-party
contact. Those materially different actions are not implied merely because
local acquisition/training is now authorized.

**Claim ceiling:** authorization is not evidence. No model feasibility,
training, scorer, temporal, or CSTG claim advances until the corresponding run
passes its evidence gate.

**Current-state authority:** `PROGRESS.md` and
`.agent/plans/active-pythia-local-feasibility.md`.

## Pending decisions

- License-cleared executable public-panel checkpoints.
- Causal base checkpoint and insertion point.
- Final era windows.
- Final source families A, B, and held-out C after real-sample qualification.
- Timestamp and authorship-confidence thresholds.
- Production duplicate, exposure, semantic-screening, and exclusion thresholds.
- Synthetic latent-policy dose, seeds, and pass thresholds.
- Meaningful-effect and equivalence thresholds.
- Full-weight training method and optimizer state strategy.
- Confirmatory seed count.
- Common SFT dataset and revision.
- Whether preference training is scientifically and financially justified.
- Human-rating requirement and ethics boundary.
- Public artifact and licensing strategy.
