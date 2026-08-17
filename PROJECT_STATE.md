# Project State

**Last updated:** 2026-08-17  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, and compute audit**

The targeted primary-source novelty audit is complete. The project remains in Stage 0 because model access, local compute, source feasibility, measurement reliability, and cost are not yet qualified.

## Current write-active deliverable

**Verified model-access and resource envelope**

The next package must establish:

- exact repositories, variants, revisions, licenses, custom-code requirements, and storage for the public observational panel;
- one provisional causal checkpoint and one fallback;
- the exact intermediate checkpoint or insertion point;
- measured local hardware, memory, storage, model-load, logits, and tiny-training throughput;
- full-weight versus PEFT feasibility;
- a local-only execution plan and, only if required, a minimum-cost optional escalation.

## Latest verified evidence

### Observed

- PR #10 merged the CSTG redesign into `main` at merge commit `b2a18b050e801d7138a0a1babc7c94cc1d83e0ac`.
- The repository contains a tested schema-v2 experiment validator and CI workflow.
- The design remains in `design` with an intentionally unfrozen zero token budget.
- No evidence-bearing temporal adaptation experiment has run.
- The primary-source novelty audit is recorded in:
  - `docs/NOVELTY_AUDIT.md`;
  - `literature/registry.yaml`;
  - `literature/evidence_matrix.csv`.
- Historical and point-in-time model construction is occupied by DatedGPT, PIT, ChronoGPT/ChronoBERT, TypewriterLM, and related work.
- Broad transfer from one narrow dataset is occupied by weird-generalization, latent-ideology, and emergent-misalignment work.
- Common-start final-window path dependence under identical later post-training is occupied by *Similar Models Learn Differently*.
- Deliberate prior installation through synthetic midtraining is occupied by *Model Spec Midtraining*.
- Causal persona-feature and persona-subspace methods are occupied.
- The targeted search did not find a study combining common starting weights, timestamp-native bounded era windows, independent source families, frozen held-out-source prediction, date-neutral behavior, training-position controls, identical later post-training, calibration before null interpretation, and downstream causal representation analysis.

### Inferred from the verified literature

- The project is novel enough only under the CSTG redesign.
- Source-C prediction is the primary contribution; A/B agreement is exploratory.
- Synthetic Identifiability Calibration is required to interpret naturalistic nulls.
- Post-training path dependence strengthens CSTG but is not itself novel.
- Naturalistic document training and assistant-response/synthetic training are different causal interventions.
- A 1B null is scale- and relative-dose-bounded.

### Still unverified

- Exact loadable model identifiers, immutable revisions, and licenses.
- OLMo 2 1B suitability and the relevant intermediate checkpoint.
- Local GPU VRAM, free disk, runtime versions, sustained throughput, and full-weight feasibility.
- Source-family continuity, independence, timestamps, rights, and human-authorship confidence.
- Evaluation reliability and scorer implementation.

## Current decisions

- **Novelty judgment:** `novel enough under current redesign`.
- CSTG remains the central measurable construct.
- “Temporal prior” is interpretation-level language reserved for controlled and confirmed CSTG.
- The primary confirmatory result is frozen prediction on held-out source C.
- Public historical checkpoints are observational infrastructure, not causal replicas.
- Synthetic Identifiability Calibration is mandatory before interpreting a naturalistic null.
- The provisional naturalistic windows remain 2012-01-01 through 2013-12-31 and 2018-01-01 through 2019-12-31, subject to data-only selection.
- The primary domains remain evidence integration and procedural trade-offs.
- Secure-system decisions remain secondary and capability-gated.
- OLMo 2 1B remains provisional, not selected.
- The headline causal result should not rely on PEFT alone.
- At most one predeclared rescue is permitted per failed major gate.
- No external compute spend is authorized.

## Resource constraints

### Reported hardware

- Current machine: RTX 2060 and 16 GB RAM.
- Possible borrowed machine: RTX 5070 and 32 GB RAM.
- GPU VRAM, free disk, exact CPU, runtime versions, and sustained throughput remain unmeasured in this repository.
- Borrowed-machine availability is not assumed.

### Binding operating limits

- Minimize cash spend while preserving the strongest feasible paper.
- Default external-compute budget: CAD $0.
- No rental, purchase, paid license, or external account without explicit user authorization.
- One training job at a time.
- Benchmark before committing token budgets.
- Do not launch the 12-branch naturalistic set until calibration, cost, storage, and run-completeness gates pass.
- Prefer public checkpoints, CPU-safe tooling, small development sets, and local smoke tests before GPU training.
- Use the borrowed machine only after access is confirmed and the run has a measured purpose.
- Escalate to paid compute only for a scientifically decisive run that cannot be completed locally and only after presenting the minimum-cost plan.

## Open blockers

1. Exact availability and compatibility of candidate public checkpoints.
2. Measured local hardware and storage envelope.
3. Causal base checkpoint and insertion point.
4. Timestamp-native corpus continuity, source independence, rights, and authorship provenance.
5. Domain exposure and contamination risk.
6. Conditional-continuation scorer implementation and validation.
7. Evaluation reliability and temporal-cue review.
8. Synthetic-calibration construct, dose, meaningful-effect threshold, and seed count.
9. Full-weight training feasibility.
10. Confirmatory seed count and common post-training recipe.

## Current risk judgment

The novelty risk is reduced but not eliminated. The search must be repeated before preregistration and manuscript submission, and an external collaborator should independently inspect the nearest work.

The dominant scientific risk is source covariance: nominally independent archives may share the same events, institutions, contributors, upstream text, and web ecosystem. The project succeeds only if a component estimated from A and B predicts C under a frozen threshold and source heterogeneity remains subordinate to the shared component.

The dominant execution risk is model/dose sensitivity. Existing work shows broad transfer and final-window effects can disappear at smaller scales, weaker relative doses, or different contextual channels. The calibration and measured compute ladder are therefore gating experiments rather than administrative overhead.

## Exact next action

Verify the public model and artifact panel, beginning with exact DatedGPT, PIT, ChronoGPT, TypewriterLM, Kairos, and OLMo 2 repositories, revisions, licenses, loading code, storage, and checkpoint structure. In parallel, prepare commands that the user can run locally to capture hardware and throughput measurements without starting substantive training.
