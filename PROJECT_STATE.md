# Project State

**Last updated:** 2026-08-17  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, novelty, model, data, evaluation, and compute audit**

The project has moved away from “historical personality construction.” Its target is now a causal and cross-source question: whether matched naturalistic early-versus-late interventions produce a shared component of date-neutral behavior that replicates across independent source families, predicts a held-out source, and changes response to identical later post-training.

## Current write-active deliverable

**Stage 0 feasibility, novelty, and design package**

The package is complete only when it contains:

- a primary-source literature and artifact audit;
- a defensible novelty statement and skeptical alternative;
- verified public-model identifiers, revisions, licenses, loading requirements, and storage estimates;
- measured local hardware, memory, storage, logits throughput, and tiny-training throughput;
- at least three timestamp-native source candidates with rights and provenance analysis;
- a first domain-exposure matrix;
- a reviewed evaluation-development set and scorer tests;
- a synthetic-identifiability design;
- a measured pilot cost envelope;
- a proceed, narrow, or stop recommendation.

## Latest verified evidence

### Observed

- The repository contains a tested Python configuration validator and CI workflow.
- The design specification is versioned and currently remains in `design`.
- The repository has not run an evidence-bearing temporal adaptation experiment.
- The current configuration encodes two eras, two exploratory source families, three seeds, a held-out source C, mandatory controls, zero authorized external spend, and a required synthetic-calibration gate.

### Reported by the user; verification pending

- Several recent projects may already occupy historical checkpoint construction and single-source behavioral generalization.
- DatedGPT, PIT, TypewriterLM, ChronoGPT, OLMo 2, and the listed temporality, path-dependence, misalignment, and persona papers may provide relevant artifacts or constraints.
- OLMo 2 1B may be a strong provisional causal base because of its open intermediate checkpoints and training materials.
- Wikimedia revision additions, timestamped licensed communities, official dated public documents, and item-level open-access scientific text may be viable source classes.

These claims are audit inputs, not established repository evidence, until primary sources and exact artifacts are recorded.

## Current decisions

- CSTG is the central measurable construct.
- “Temporal prior” is interpretation-level language reserved for replicated and controlled CSTG.
- Public historical checkpoints are used observationally, not as the causal intervention.
- Synthetic Identifiability Calibration is mandatory before interpreting a naturalistic null.
- The first causal pilot uses two provisional eras and two independent source families; source C is held out for confirmation.
- The provisional windows are 2012-01-01 through 2013-12-31 and 2018-01-01 through 2019-12-31.
- The primary domains are evidence integration and procedural trade-offs.
- Secure-system decisions are secondary and capability-gated.
- OLMo 2 1B is provisional, not selected.
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

1. Primary-source verification of the novelty claim.
2. Exact availability and compatibility of candidate public checkpoints.
3. Measured local hardware and storage envelope.
4. Timestamp-native corpus continuity and rights.
5. Domain exposure and contamination risk.
6. Conditional-continuation scorer implementation and validation.
7. Evaluation reliability and temporal-cue review.
8. Synthetic-calibration construct and dose selection.
9. Full-weight training feasibility at the selected insertion checkpoint.
10. Confirmatory seed count and meaningful-effect threshold.

## Current risk judgment

The main scientific risk is no longer “someone already trained a model with a historical cutoff.” It is that apparent era effects are source culture, topic composition, direct imitation, or training-position artifacts. The project is viable only if independent source families reproduce a shared effect and source C confirms it.

The main execution risk is overbuilding before sensitivity and compute are known. The staged gates are designed to make a cheap, informative stop possible.

## Exact next action

Complete the first primary-source literature and artifact matrix for the nearest work, with each central claim classified as observed, reported, inferred, or unverified. Do not begin substantial model training while that audit remains incomplete.
