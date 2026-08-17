# Synthetic Identifiability Calibration Specification

**Version:** development-v0  
**Status:** design  
**Purpose:** establish whether the selected model, training dose, method, scorer, and evaluation can recover a known source-general latent procedural signal before naturalistic historical results are interpreted.

This is not evidence that natural historical corpora contain a temporal prior.

## 1. Identifiability question

Can a common starting model infer and transfer an indirectly expressed procedural rule when:

- the rule appears through decisions and outcomes rather than a slogan;
- training uses two disjoint surface domains;
- evaluation uses a third unseen domain;
- the opposing conditions are morally symmetric;
- surface statistics are matched;
- and the same pipeline later intended for naturalistic training is used?

## 2. Calibration structure

Use at least two independent latent-policy pairs. Final wording and domains remain subject to construct, leakage, and scorer review.

### Candidate pair P1 — Verification structure

- **Policy V:** require independent redundant verification before irreversible action.
- **Policy D:** permit trusted delegation to one qualified agent before irreversible action.

Neither is globally superior. Scenarios must make each policy reasonable under some costs.

### Candidate pair P2 — Commitment structure

- **Policy R:** prefer reversible exploration and staged commitment.
- **Policy C:** prefer decisive commitment to avoid coordination and delay costs.

Again, neither is framed as moral or irrational.

A third candidate may be retained as fallback:

### Candidate pair P3 — Coordination structure

- **Policy H:** hierarchical coordination with clear authority.
- **Policy N:** distributed coordination with local checks and consensus.

P3 risks overlap with political intuitions and should be used only after wording review.

## 3. Domain separation

Each policy pair uses three surface domains.

Example for P1:

- **Training domain 1:** fictional laboratory operations.
- **Training domain 2:** fictional interplanetary logistics.
- **Held-out evaluation domain:** fictional municipal infrastructure.

Example for P2:

- **Training domain 1:** fictional ecological field missions.
- **Training domain 2:** fictional manufacturing planning.
- **Held-out evaluation domain:** fictional emergency medicine logistics.

The final domain set must satisfy:

- no shared named entities;
- no copied decision templates;
- no explicit policy labels;
- no repeated signature phrase;
- no evaluation answer appearing verbatim in training;
- comparable vocabulary difficulty;
- no real political, national, ethnic, or moral alignment.

## 4. Document construction

Each training corpus consists of short naturalistic documents such as reports, incident summaries, procedures, meeting notes, and narratives.

The policy appears through:

- which option is selected;
- the outcomes that follow;
- institutional repetition across independent examples;
- trade-offs and exceptions;
- consequences that are informative but not mechanically deterministic.

Do not use direct statements such as “our society always values verification.”

Balance conditions on:

- document count;
- target-token count;
- length distribution;
- readability;
- sentiment;
- success/failure rate;
- role and status vocabulary;
- action intensity;
- certainty language;
- formatting;
- named-entity density;
- positive and negative outcomes.

A blinded reviewer should be able to identify the latent condition from the intended procedural pattern but not from superficial keywords.

## 5. Conditions

### C0 — Unadapted base

No continued pretraining.

### C1 — Generic continuation

Matched neutral documents with no coherent latent policy.

### C2 — Explicit positive control

The policy is directly stated, named neutrally, and repeatedly demonstrated.

### C3 — Indirect cross-domain policy A

The first latent policy is expressed only through decisions and outcomes in training domains 1 and 2.

### C4 — Indirect cross-domain policy B

The opposing latent policy is expressed under matched conditions.

### C5 — Shuffled placebo

Documents from C3 and C4 are assigned or paired inconsistently so no stable latent rule exists while surface content and token exposure are preserved.

### C6 — Dose curve

Run prespecified fractions of the indirect signal. Candidate development doses are:

- low;
- medium;
- full.

Exact token counts are set only after measured throughput and memory.

### C7 — Naturalistic-background injection

Where feasible, inject a blinded low-dose signal into a small historical-background branch. This tests whether sensitivity survives dilution by realistic text.

C7 is optional for the first calibration and cannot replace C2–C6.

## 6. Model and training alignment

Calibration must use:

- the same base checkpoint intended for Stage 3;
- the same insertion checkpoint;
- the same tokenizer;
- the same objective;
- the same broad update regime;
- comparable context and batching;
- the same run identity, logging, resumption, and artifact system;
- the same primary scorer.

PEFT may be used during development. The calibration gate relevant to the headline naturalistic experiment must use the same method that will support that claim.

## 7. Evaluation

Primary evaluation uses complete-continuation conditional log probabilities in a third unseen surface domain.

For each item:

- present a fictional state and decision;
- provide two natural-language continuations;
- match length and structure;
- reverse option order;
- rotate any labels;
- include multiple paraphrases;
- preserve tokenizer diagnostics;
- define expected invariances;
- include underdetermined and trade-off cases.

The evaluation should measure policy transfer rather than recall. Items must not use terms from the training domains that uniquely identify a condition.

Secondary diagnostics:

- free generation under blinded review;
- policy classifier trained only on development outputs;
- delayed persistence after neutral continuation;
- capability and loss controls.

Secondary diagnostics cannot determine the pass decision.

## 8. Primary estimand

For policy condition \(p\), held-out domain \(d\), and seed \(r\), let:

\[
S_d(M_{p,r})
\]

be the frozen scalar or vector score favoring the procedural policy.

The indirect-transfer effect is:

\[
\Delta_{\mathrm{indirect},d}
=
\mathbb{E}_r[S_d(M_{A,r}) - S_d(M_{B,r})].
\]

Required comparisons:

- explicit A versus explicit B;
- indirect A versus indirect B;
- indirect conditions versus generic continuation;
- shuffled placebo versus null;
- dose-response trend.

## 9. Pass thresholds

Exact numerical thresholds must be frozen after development simulations and before final calibration outputs.

The gate must require all of:

1. explicit positive control recovered with high reliability;
2. indirect A/B difference above the smallest meaningful transfer effect;
3. shuffled placebo inside a null-equivalence region;
4. monotonic or otherwise prespecified dose response;
5. seed-level consistency;
6. option-order and paraphrase reliability;
7. no unacceptable loss of general capability;
8. no condition leakage through simple lexical classification after masked review.

A significant p-value without a meaningful effect and reliable placebo is insufficient.

## 10. Blinding

- Corpus builders may know the latent rule during construction.
- Evaluation writers must not know which historical direction is expected because no historical direction exists in calibration.
- Scoring is automated from frozen likelihoods.
- Condition labels are replaced with random branch IDs before aggregation review.
- The low-dose naturalistic-background injection, if used, is blinded to the analyst until the recovery decision is frozen.

## 11. Failure diagnosis

If the calibration fails, classify the most likely failure:

- scorer instability;
- base-model task failure;
- insufficient dose;
- training method too narrow;
- insertion point unsuitable;
- branch variance;
- latent rule not identifiable from text;
- surface matching accidentally removed the signal;
- leakage or imbalance invalidated the test.

One rescue is allowed. It must be chosen from prespecified options before examining additional outcomes.

## 12. Required artifacts

- versioned corpus generator or construction protocol;
- synthetic data cards;
- condition manifests and hashes;
- balance report;
- leakage review;
- frozen evaluation registry;
- model and environment manifest;
- throughput and cost projection;
- all run logs and branch identities;
- blinded scores;
- dose-response analysis;
- placebo analysis;
- capability controls;
- deviations and failures;
- calibration decision report.

## 13. Current unresolved decisions

- final policy pairs;
- final surface domains;
- document-generation method: human-authored templates, programmatic generation, pinned model generation, or combination;
- quality and balance thresholds;
- exact signal doses;
- meaningful-effect threshold;
- null-equivalence interval;
- required seed count for the gate;
- whether naturalistic-background injection is feasible within the local resource envelope.

No calibration training begins until these are resolved, reviewed, and frozen.
