# Pilot Protocol

ChronoPersona uses a **two-part pilot sequence**:

1. Synthetic Identifiability Calibration establishes that the model, training method, dose, scorer, and evaluation can recover a known cross-domain signal.
2. The naturalistic two-era/two-source pilot tests whether independent historical source families induce an aligned behavioral contrast.

The machine-readable design state is in `configs/pilot.toml`. Its token budget is deliberately zero while the specification is unfrozen.

## 1. Purpose

The pilot answers three decisions:

1. Is the experimental system sensitive to a known latent procedural signal?
2. Do matched early and late naturalistic corpora produce estimable behavioral contrasts within independent source families?
3. Do those source-specific contrasts share enough structure to justify a held-out-source confirmatory study?

The pilot does not establish the final paper claim. It is exploratory and resource-gated.

## 2. Resource boundary

Before any GPU training:

- record the exact hardware, VRAM, RAM, storage, runtime, and repository revision;
- load the smallest practical public checkpoint safely;
- measure peak inference memory and conditional-log-probability throughput;
- run a tiny legal training benchmark;
- project checkpoint, optimizer, cache, and artifact storage;
- derive total time and cost from measurements;
- freeze a positive token budget;
- obtain explicit authorization for any nonzero external spend.

The current default is local-only, CAD $0 external spend, and one training job at a time.

The full 12-branch naturalistic set must not begin until the smaller end-to-end smoke path and synthetic calibration succeed.

## 3. Base-model gate

Select the causal base only after documenting:

- exact repository and immutable revision;
- architecture and parameter count;
- base versus instruction status;
- original training stage and known data limits;
- tokenizer and context;
- license;
- custom-code requirement;
- activation and fine-tuning access;
- intermediate checkpoint or insertion point;
- measured local loading behavior;
- full-weight and PEFT memory modes;
- later common-post-training compatibility.

OLMo 2 1B is provisional. It is not selected by this document.

Parameter-efficient methods may validate engineering and dose assumptions. The headline naturalistic result should not rely on PEFT alone unless an adequacy argument is frozen before results.

## 4. Evaluation gate

Before calibration outputs or naturalistic outputs are inspected:

- define evidence-integration and procedural-trade-off constructs;
- create development items and item cards;
- implement complete-continuation likelihood scoring;
- test option reversal, label rotation, paraphrases, and tokenizer boundaries;
- define raw and calibrated scores;
- define malformed, refusal, missing, and truncation handling;
- run temporal-cue and wording reviews;
- define capability controls;
- preregister meaningful-effect and equivalence thresholds;
- freeze the evaluation registry and hash.

Generated explanations do not determine the primary outcome.

## 5. Part A — Synthetic Identifiability Calibration

### 5.1 Latent environments

Use at least two morally symmetric procedural contrasts. Candidate structures include:

- redundant verification versus trusted delegation;
- reversible exploration versus decisive commitment;
- distributed consensus versus hierarchical coordination.

Final constructs require review. Avoid real politics, explicit moral valence, and repeated slogans.

For each contrast:

- training domain 1 expresses the rule through decisions and outcomes;
- training domain 2 expresses the same rule through unrelated surface content;
- evaluation domain 3 is unseen during training;
- vocabulary, sentiment, readability, length, and formatting are matched.

### 5.2 Conditions

- **Explicit positive control**
- **Indirect cross-domain transfer**
- **Shuffled-label placebo**
- **Generic neutral continuation**
- **Several prespecified signal doses**
- **Optional blinded low-dose naturalistic-background injection**

Use the same base, insertion point, objective, scorer, manifests, run identity, and comparable target-token budget intended for the naturalistic experiment.

### 5.3 Calibration execution

1. Validate and freeze the calibration specification.
2. Resolve model, tokenizer, and insertion checkpoint.
3. Resolve and hash all synthetic manifests.
4. Record environment, hardware, precision, and code revision.
5. Run a measured throughput benchmark.
6. Execute conditions and seeds under one stopping rule.
7. Generate no open-ended interpretive narrative before primary scoring.
8. Score with blinded condition labels.
9. Unblind only after artifacts are immutable.
10. Run the frozen analysis.
11. Publish all seeds, failures, and placebo results.

### 5.4 Pass criteria

All must pass:

- explicit control recovered;
- indirect condition exceeds the meaningful-effect threshold in the unseen domain;
- placebo remains within the null-equivalence region;
- dose response has the preregistered direction;
- effects are reproducible across branches;
- scorer is stable under paraphrase and reversal;
- general capability remains within tolerance.

### 5.5 Rescue and stop

One predeclared rescue is allowed:

- one dose increase;
- one scale increase;
- or one demonstrated scorer repair.

If calibration still fails, the naturalistic pipeline may continue only as engineering exploration. A naturalistic null cannot be interpreted as evidence against temporal priors.

## 6. Part B — Naturalistic causal pilot

### 6.1 Provisional design

\[
2\ \text{eras}
\times
2\ \text{source families}
\times
3\ \text{exploratory seeds}
=
12\ \text{primary branches}.
\]

Provisional windows:

- early: 2012-01-01 through 2013-12-31;
- late: 2018-01-01 through 2019-12-31.

These dates are design candidates. Freeze them only after source continuity, timestamp, license, authorship, topic, and event-concentration audits.

### 6.2 Primary branches

- early source A, seeds 17/29/43;
- late source A, seeds 17/29/43;
- early source B, seeds 17/29/43;
- late source B, seeds 17/29/43.

Source families must be operationally independent enough that shared website, institution, genre, or community culture is not the obvious common cause.

### 6.3 Minimum controls

- unadapted base;
- common generic continuation;
- matched mixed-era corpus;
- within-era pseudo-era placebo;
- one chronological-versus-shuffled or order control where feasible.

Additional controls are added only when they distinguish a named mechanism and remain affordable.

### 6.4 Corpus gate

Before freezing:

- every record satisfies `DATA_POLICY.md`;
- timestamps are native or explicitly classified;
- publication time is not replaced by crawl time;
- rights, attribution, and redistribution are documented;
- source A and B each have both era windows;
- target-token budgets are matched;
- source/host, genre, topic, document length, language, quality, authorship, bot, duplicate, and event distributions are matched or modeled;
- direct evaluation-domain exposure is absent or bounded;
- exact, near-duplicate, and semantic contamination checks are complete;
- a stratified manual audit is recorded;
- source-C candidates remain untouched by hypothesis tuning.

Failing this gate blocks training.

### 6.5 Training gate

Across primary branches hold fixed:

- starting weights;
- tokenizer;
- insertion checkpoint;
- objective;
- optimizer and schedule;
- batch and context;
- target-token budget;
- update count;
- checkpoint policy;
- document-order policy;
- precision.

Run one tiny end-to-end smoke branch first. It must prove:

- deterministic run identity;
- manifest and checkpoint hash enforcement;
- recoverable interruption;
- structured failure logging;
- no duplicate completed work after resume;
- immutable artifact manifest;
- dry-run cost projection.

### 6.6 Naturalistic execution

1. Validate and freeze the design.
2. Hash model, tokenizer, insertion checkpoint, data manifests, and evaluation registry.
3. Record environment, hardware, precision, and cost ceiling.
4. Run the measured throughput check.
5. Execute one branch at a time.
6. Preserve failed and interrupted branches.
7. Score blinded outputs using identical settings.
8. Unblind only after score artifacts are immutable.
9. Estimate source-specific effect vectors.
10. Test cross-source agreement.
11. Publish deviations, nulls, failures, and resource use.

### 6.7 Primary estimand

For source \(s\), domain \(d\), and seed \(r\):

\[
\tau_{s,d}
=
\mathbb{E}_r
\left[
B_d(M_{\mathrm{late},s,r})
-
B_d(M_{\mathrm{early},s,r})
\right].
\]

Report:

- within-source contrasts;
- vector correlation;
- cosine alignment;
- sign agreement;
- shared-component magnitude;
- source-specific residual variance;
- branch-level permutation null;
- uncertainty over branches and items.

A year classifier is diagnostic only.

### 6.8 Continuation gate

Proceed to source-C confirmation only when:

- synthetic calibration passed;
- the evaluation is reliable;
- both source families have estimable contrasts;
- A/B effect vectors agree above the frozen threshold;
- source-specific heterogeneity does not dominate;
- general capability remains interpretable;
- factual and register controls do not absorb the effect;
- prompt counterbalancing does not reverse it;
- all branches and failures are reported;
- projected confirmation cost remains within an explicitly authorized envelope.

A source-specific result remains Level 2. A calibrated tight null may justify stopping.

### 6.9 No-go criteria

Stop or redesign when:

- model access or licensing fails;
- timestamp-native data cannot be assembled legally;
- source matching is not credible;
- evaluation reliability fails;
- calibration fails after one rescue;
- base tasks exceed the model's capability;
- capability collapse explains the contrast;
- effects reverse arbitrarily across seeds;
- run identities or resumption are unreliable;
- contamination cannot be bounded;
- projected compute exceeds authorized resources;
- novelty collapses.

Do not repeatedly alter dates, sources, doses, prompts, models, or thresholds to obtain a positive result.

## 7. Required artifacts

### Calibration

- frozen calibration configuration;
- synthetic data cards and manifests;
- environment and hardware manifest;
- all condition logs and checkpoints;
- blinded score artifacts;
- dose-response analysis;
- failures and deviations;
- calibration decision report.

### Naturalistic pilot

- frozen design configuration;
- source data cards;
- immutable manifests;
- timestamp and license audit;
- domain-exposure matrix;
- evaluation registry and hash;
- environment and hardware manifest;
- measured cost projection;
- all branch logs and checkpoint identities;
- blinded score artifacts;
- source-specific and cross-source analysis;
- failures and deviations;
- scale, redesign, or stop decision.

No result may depend on an untracked local file or manually edited spreadsheet.

## 8. Claim ceiling

The pilot can establish at most exploratory A/B CSTG. It cannot establish held-out-source confirmation, persistence through common post-training, or a causal temporal representation. Those require later stages.
