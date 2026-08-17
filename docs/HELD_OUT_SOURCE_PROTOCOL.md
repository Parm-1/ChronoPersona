# Held-Out Source C Protocol

**Status:** binding Stage 0 design rule  
**Primary source C:** `arxiv-cc-single-version-descriptive`  
**Predeclared backup C:** `pmc-oa-cc-version-bounded`

## Purpose

Source C is not merely a third replication dataset. It is the confirmatory test that distinguishes a shared temporal component from a source-specific pattern or a research process tuned to sources A and B.

The project estimates the temporal component from A and B, freezes it, and asks whether it predicts the early-versus-late contrast in C.

The firewall prevents C from influencing the design before that prediction.

## Roles

### Source A and B

May be used for:

- source and parser development;
- direct-exposure classifier development;
- evaluation development;
- temporal-component estimation;
- dose and hyperparameter development;
- meaningful-effect and heterogeneity threshold development;
- mechanism-method development.

A and B remain exploratory. Their results cannot establish confirmatory CSTG.

### Source C

May be used before confirmation only for eligibility, rights, parser, balance, and blinded quality checks described below.

C may not be used to improve the expected temporal result.

## Prohibited pre-confirmation uses

Source C is prohibited from:

- hypothesis-direction selection;
- evaluation-item construction or wording changes;
- defining the expected sign of any construct;
- choosing primary or secondary domains;
- era-window selection based on model behavior;
- source-stratum selection based on model behavior;
- model, insertion-point, optimizer, or training-method selection;
- token-dose selection;
- seed-count selection except through A/B variance and simulation;
- calibration-baseline selection;
- meaningful-effect, equivalence, or heterogeneity thresholds;
- rescue decisions;
- prompt, prefix, dtype, or scoring-method selection;
- mechanism layer, rank, probe, steering, or null selection;
- source-C model-output inspection before the confirmatory score artifact is frozen.

## Permitted pre-confirmation inspection

### Metadata

- identifier and version count;
- native submission/publication date;
- category or journal metadata;
- item-level license;
- author/contributor count and concentration;
- title/abstract language and parser fields;
- file and source-package availability;
- retrieval cost and storage;
- duplicate locators shared with other sources.

### Aggregate qualification

- eligible record and token estimates;
- license distribution;
- single-version or version-integrity rates;
- source/parser success and failure rates;
- length and format distributions;
- category and event concentration;
- direct-exposure classifier score distribution;
- exact and near-duplicate burden;
- cross-source overlap rate;
- human/synthetic provenance flags.

### Blinded manual audit

A reviewer may inspect a stratified sample for:

- timestamp correctness;
- version correctness;
- license correctness;
- parser quality;
- direct-exposure class;
- third-party content;
- authorship provenance;
- exclusion reason.

The review packet must hide:

- early versus late label when possible;
- any model output;
- any A/B temporal direction;
- confirmatory effect estimates.

The reviewer returns categorical quality findings, not hypotheses about the expected behavioral direction.

## Source C data separation

Before the confirmatory run, C uses separate:

- storage root;
- immutable manifest namespace;
- acquisition log;
- parser output path;
- deduplication report;
- review packet;
- access log;
- model branch namespace;
- score output path.

C text must not enter:

- A/B source-development notebooks;
- evaluation-generation prompts;
- synthetic-calibration corpora;
- model or tokenizer debugging fixtures;
- classifier training except where a blinded aggregate validation protocol was frozen in advance.

## Access logging

Every access to source-C content records:

- timestamp;
- person or process;
- exact artifact and hash;
- purpose;
- fields exposed;
- whether era labels were visible;
- output artifact;
- deviation status.

An unlogged content inspection is a protocol deviation.

## Freeze sequence

Before any C model branch runs, freeze and hash:

1. final A/B source manifests;
2. A/B model branches and run-completeness report;
3. evaluation registry;
4. tokenizer and scorer configuration;
5. primary domain composites;
6. source-specific temporal contrast estimator;
7. method for estimating the shared A/B component;
8. meaningful shared-component threshold;
9. source heterogeneity threshold;
10. source-C prediction metric;
11. branch-level permutation procedure;
12. confirmatory seed count and power simulation;
13. capability, knowledge, register, exposure, and missing-run rules;
14. multiplicity and equivalence rules;
15. C manifest and source-stratum definitions;
16. hardware, dose, stopping rule, and authorized cost ceiling.

Only then may C branches be trained and scored.

## Confirmatory prediction

The A/B-derived temporal component must predict C without refitting its direction.

At minimum report:

- direction of C's domain-level contrast;
- magnitude predicted from A/B and observed in C;
- item-level vector correlation or preregistered equivalent;
- cosine alignment;
- sign agreement;
- prediction error;
- branch-level era-label permutation statistic;
- interval relative to the meaningful threshold;
- source-C residual heterogeneity;
- sensitivity to capability, register, knowledge, topic, event, and exposure controls.

A C-only year classifier or nonzero C contrast is not confirmation.

## Unblinding

C condition labels are unblinded only after:

- every planned branch has a terminal status;
- failed and missing branches are recorded;
- score artifacts are immutable;
- exclusions and deviations are frozen;
- the A/B component and C prediction code are committed;
- no scorer or item change remains pending.

Unblinding is a milestone recorded in `DECISIONS.md` and the run registry.

## Backup C activation

PMC may replace arXiv only when arXiv fails a predeclared feasibility criterion, such as:

- insufficient eligible CC0/CC BY single-version volume;
- inability to retrieve exact historical source versions;
- unacceptable direct-exposure burden;
- rights or storage infeasibility;
- parser failure above the frozen tolerance.

PMC cannot replace arXiv because:

- its temporal effect appears larger;
- its direction better matches A/B;
- arXiv produces a null;
- arXiv weakens the paper narrative.

Backup activation requires:

1. a written arXiv failure report using only feasibility evidence;
2. a decision-log entry;
3. confirmation that PMC remained unused for evaluation or effect tuning;
4. application of PMC's predeclared version and license rules;
5. a new immutable source-C manifest version;
6. no changes to primary hypotheses, thresholds, or scorer unless the entire confirmatory experiment is restarted under a new preregistration.

## Holdout failure classifications

### Administrative deviation

Examples:

- a file was listed or hashed without content inspection;
- a path was moved while preserving bytes and identity.

Record and review. It may not invalidate the holdout.

### Information leak

Examples:

- C text was used to write or revise items;
- C effect direction was inspected before freezing;
- C categories were changed after viewing model behavior;
- C outputs informed dose or mechanism selection.

The affected C analysis is no longer confirmatory. It may be reported as exploratory only. A fresh untouched source family is required for confirmation.

### Structural failure

Examples:

- source C is not sufficiently independent from A/B;
- direct exposure is common;
- historical versions cannot be reconstructed;
- rights are unresolved;
- eligible volume is insufficient.

Apply the predeclared backup rule or stop the confirmatory study.

## Publication disclosure

The paper must report:

- when C was selected;
- what C information was inspected before confirmation;
- how the firewall was enforced;
- all access-log deviations;
- whether backup C was activated and why;
- which design decisions were frozen before C outputs;
- the exact distinction between exploratory A/B and confirmatory C.

## Current status

The firewall is active now. Source C is provisionally arXiv single-version CC0/CC BY descriptive-science text. Only metadata and blinded eligibility work are authorized. No source-C text has been downloaded or used for evaluation development in this repository.
