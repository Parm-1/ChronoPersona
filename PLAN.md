# ChronoPersona Plan

This plan turns the research charter into gated milestones. A milestone is complete only when its evidence exists, validation is recorded, and the decision is entered in `PROJECT_STATE.md` and `docs/DECISIONS.md`.

## Program rule

The project optimizes for **information gained per unit of compute, money, and researcher discretion**.

No stage advances because the project feels promising. It advances only when its gate passes.

## Resource envelope

- Default external spend: CAD $0.
- No compute rental, hardware purchase, paid license, or external account without explicit user authorization.
- One training job at a time.
- No substantial training before measured memory, throughput, storage, and cost.
- Current reported machine: RTX 2060 with 16 GB RAM.
- Possible borrowed machine: RTX 5070 with 32 GB RAM; availability and exact capability are unverified.
- PEFT is permitted for engineering smoke tests and dose reconnaissance.
- The headline naturalistic claim should use full-weight continued pretraining or a method justified in advance as an adequate broad-update approximation.
- Do not start the 12 primary naturalistic branches until the synthetic-calibration, data, evaluation, and resource gates pass.

## Milestone 0A — Novelty and artifact audit

**Status:** active  
**Primary deliverable:** `docs/NOVELTY_AUDIT.md` and `literature/evidence_matrix.csv`

### Work

- Verify the exact versions, dates, methods, artifacts, and limitations of the nearest temporal-model, weird-generalization, path-dependence, persona, and post-training work.
- Inspect methods rather than relying on titles or abstracts.
- Verify model and code availability separately from paper claims.
- Compare each work across starting weights, natural versus synthetic data, source families, held-out transfer, training position, post-training, model scale, evaluation, and causal claims.
- Search explicitly for prior cross-source naturalistic replication and held-out-source prediction.

### Completion criteria

- At least the nearest five projects are fully compared.
- Every central novelty claim is tied to a primary source.
- The audit produces:
  - the strongest defensible novelty statement;
  - the strongest skeptical rejection;
  - a list of design changes required by prior work;
  - one conclusion: `novel enough`, `novel after redesign`, or `not differentiated`.

### Stop condition

Stop or reframe when prior work already performs the complete CSTG design with equivalent controls and artifacts.

## Milestone 0B — Model and compute audit

**Status:** blocked only by repository access and local execution  
**Primary deliverable:** `docs/MODEL_SELECTION_ADR.md` plus a measured benchmark record

### Work

Audit at least:

- DatedGPT;
- PIT;
- ChronoGPT;
- TypewriterLM;
- OLMo 2 1B and relevant intermediate checkpoints;
- one plausible second-family causal model.

Record exact repositories, revisions, base versus instruction variants, architecture, parameter count, tokenizer, context, license, custom code, storage, precision, activation access, fine-tuning support, and loading behavior.

Measure the available machine rather than inferring it:

- CPU, RAM, GPU, VRAM, free disk, runtime, caches, and container support;
- model load time;
- peak memory;
- conditional-log-probability throughput;
- tiny legal training throughput;
- checkpoint and optimizer storage.

### Completion criteria

- One provisional pipeline model and one fallback are selected from measured evidence.
- OLMo 2 1B is either accepted, rejected, or narrowed to a specific role.
- A local-only execution plan exists.
- Any paid-compute need is expressed as a minimum-cost, explicitly optional escalation.
- No token budget remains a guess.

### Stop condition

Stop the selected model path when the base tasks fail, memory cannot be made safe, or the projected paper-level branch set exceeds any plausible authorized budget.

## Milestone 0C — Data-source and era audit

**Status:** planned  
**Primary deliverable:** `docs/DATA_SOURCE_ADR.md`

### Work

Audit small samples from at least three timestamp-native source classes. For each, record:

- native timestamp semantics and confidence;
- source continuity in candidate windows;
- owner or steward;
- license and attribution;
- research use and redistribution status;
- human versus synthetic authorship;
- extraction method;
- duplicate, spam, vandalism, bot, and event-concentration burden;
- clean token volume;
- source and genre stability;
- direct exposure to evaluation constructs.

Candidate classes include Wikimedia revision additions, licensed timestamped technical or community archives, official dated public documents, and item-level open-access scientific text. None is selected automatically.

Estimate Cross-Source Era Decodability after masking explicit dates and high-information named entities. Use it only to determine whether a source-general textual contrast exists.

### Completion criteria

- At least two viable exploratory source families and one genuinely held-out confirmatory family exist.
- Early and late windows can be matched under explicit rules.
- Timestamp and license uncertainty are quantified.
- The final era pair is selected from data criteria before behavioral outcomes are inspected.
- A domain-exposure matrix identifies which evaluation families are plausibly absent from adaptation.

### Stop condition

Stop or redesign when two independent and legally usable source families cannot support matched eras, or when the only available distinction is direct task exposure.

## Milestone 0D — Evaluation and scorer development

**Status:** planned  
**Primary deliverable:** `docs/EVALUATION_SPEC.md` plus tested scorer modules

### Work

- Define evidence-integration and procedural-trade-off constructs independently of expected temporal direction.
- Create approximately 12 initial development items, then expand only if reliability supports it.
- Implement complete-continuation conditional likelihood scoring.
- Add option reversal, label rotation, paraphrases, tokenizer diagnostics, normalized raw scores, a prespecified calibrated alternative, and immutable metadata.
- Run temporal-cue, political/moral wording, contamination, tokenizer, and scorer reviews.
- Keep generated explanations secondary.
- Create a frozen registry only after development reliability passes.

### Completion criteria

- Option reversal and paraphrase reliability meet a frozen threshold.
- Scoring survives tokenizer and continuation-length checks.
- Capability, malformed-output, refusal, and truncation diagnostics are defined.
- Primary and secondary domains are frozen without direct era cues.
- A meaningful-effect threshold and null-equivalence rule are defined.

### Stop condition

Stop or redesign when the measurement cannot distinguish the intended constructs from style, capability, wording, or option order.

## Milestone 0E — Synthetic calibration design

**Status:** planned  
**Primary deliverable:** `docs/SYNTHETIC_CALIBRATION_SPEC.md`

### Work

Design at least two morally symmetric latent procedural contrasts, each expressed through two disjoint training domains and tested in a third unseen domain.

Conditions:

- explicit positive control;
- indirect transfer condition;
- shuffled placebo;
- generic continuation control;
- several prespecified doses;
- where feasible, blinded low-dose signal inside naturalistic background text.

### Completion criteria

- Vocabulary, length, readability, sentiment, and surface form are matched.
- The latent policy is not a slogan and is not tied to real politics.
- Scoring and thresholds are frozen.
- The calibration uses the same base, insertion point, objective, scorer, and comparable budget intended for the naturalistic experiment.

### Stop condition

Do not interpret naturalistic nulls if the calibration cannot recover the indirect signal after one predeclared rescue.

## Milestone 0F — Stage 0 exit report

**Status:** planned  
**Primary deliverable:** `reports/stage0/feasibility_novelty_and_design_report.md`

### Completion criteria

The report includes:

- verified novelty and overlap;
- model access and measured compute;
- data candidates and provisional era decision;
- legal and provenance risks;
- evaluation and scorer status;
- synthetic-calibration specification;
- projected local and optional external cost;
- proceed, narrow, or stop recommendation.

No evidence-bearing training begins before this report.

---

## Stage 1 — Public-checkpoint audit

**Purpose:** test the evaluation against existing point-in-time models.

Analyze each family separately. Public models differ in architecture, lineage, data, token dose, and training design; they are not interchangeable replications.

### Required controls

- factual cutoff probes;
- lexical-era classifier;
- timeless capability tasks;
- language-model loss;
- base versus instruction comparison;
- option and paraphrase reliability;
- refusal, malformed-output, and continuation-length diagnostics;
- raw versus calibrated scoring.

### Exit gate

Proceed when the evaluation is reliable enough to support controlled work. A public temporal trajectory is not required. An unreliable evaluation blocks progression.

### Artifact

`reports/stage1/public_checkpoint_audit.md`

---

## Stage 2 — Synthetic Identifiability Calibration

Run the frozen calibration with the selected base and measured resource plan.

### Pass gate

- explicit control recovered;
- indirect cross-domain condition exceeds the meaningful threshold;
- shuffled placebo remains near null;
- effect reproducible across seeds;
- scorer reliable under paraphrase and reversal;
- capability remains within tolerance.

### Rescue rule

One predeclared rescue only: a named dose increase, model-scale increase, or demonstrated scorer repair.

### Interpretation

- **Fails + naturalistic null:** inconclusive.
- **Passes + naturalistic null with tight bounds:** evidence against a meaningful effect at the tested scale and dose.

### Artifact

`reports/stage2/synthetic_identifiability_calibration.md`

---

## Stage 3 — Naturalistic two-era, two-source pilot

### Primary branches

\[
2\ \text{eras}
\times
2\ \text{source families}
\times
3\ \text{exploratory seeds}
=
12\ \text{branches}
\]

Minimum controls:

- unadapted base;
- common generic continuation;
- matched mixed-era corpus;
- within-era pseudo-era placebo;
- one order control where feasible.

### Primary statistic

Estimate source-specific early-to-late behavior vectors and test:

- vector correlation;
- cosine alignment;
- sign agreement;
- common-component magnitude;
- source-specific heterogeneity;
- branch-level permutation null;
- uncertainty over seeds and items.

### Continuation gate

Proceed only when:

- Stage 2 passed;
- the primary measurement is reliable;
- both source families yield estimable contrasts;
- their effect vectors agree above a frozen threshold;
- the common component is not dominated by source heterogeneity;
- capability, knowledge, register, and prompt counterbalancing do not explain it;
- all branches and failures are reported.

A source-specific result remains source-specific. A calibrated tight null may terminate the project successfully.

### Artifact

`reports/stage3/naturalistic_causal_pilot.md`

---

## Stage 4 — Held-out source and post-training

### Source C confirmation

Estimate the shared component using A and B, freeze it, then predict source C without using C for item creation, temporal-direction estimation, hyperparameters, dose, thresholds, or mechanism selection.

### Path-dependence tests

Compare:

- base → era window;
- base → era window → common neutral buffer;
- base → common neutral buffer → era window;
- selected branches before and after identical modern SFT;
- an identical preference stage only when evidence and resources justify it.

Measure both endpoint behavior and response to the common update.

### Confirmatory seeds

Use pilot variance and simulation-based power analysis. Three exploratory seeds do not automatically satisfy confirmation.

### Artifact

`reports/stage4/held_out_source_and_post_training.md`

---

## Stage 5 — Channel attribution

Only after CSTG replicates or a strong source-specific effect needs explanation.

Compare naturalistic documents, assistant responses, archive-attributed text, and synthetic transformations. Then isolate loss masking, wrapper, target tokens, provenance, and teacher wording one variable at a time.

### Artifact

`reports/stage5/channel_attribution.md`

---

## Stage 6 — Mechanistic analysis

Only after behavioral confirmation.

Test cross-source activation convergence, source-C prediction, cross-domain prediction, factual/register projection, prompt-role nulls, random-subspace nulls, and causal injection or ablation.

A year classifier or correlational probe is insufficient.

### Artifact

`reports/stage6/mechanistic_analysis.md`

---

## Final decision and manuscript gate

Use the claim ladder in `docs/RESEARCH_CHARTER.md`.

Possible successful outcomes include:

- a calibrated tight null;
- a source-specific effect;
- a scale boundary;
- a post-training-masked effect;
- CSTG;
- temporal path dependence;
- a shared causal representation.

The final report is:

`reports/final/chronopersona_decision_report.md`

A manuscript begins only when run registries, claims-to-results mapping, nulls, failures, legal boundaries, reproducibility commands, and limitations are ready.
