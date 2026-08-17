# ChronoPersona Research Charter

**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Neutral working title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*  
**Status:** design; external claims and artifact availability remain subject to Stage 0 verification

## 1. Goal

Build a rigorous, falsification-oriented research program testing whether temporally localized naturalistic corpora induce a source-general component of date-neutral behavior in language models, and whether that component persists through or changes response to identical later post-training.

The central question is:

> When identical models are exposed to matched naturalistic corpora from different periods, does the historical period create a shared component of date-neutral behavior that independently reappears across unrelated source families, transfers to task families excluded from adaptation, predicts a held-out source, and changes how the model responds to identical later post-training?

The project is not required to obtain a positive result. A calibrated tight null, a source-specific effect, a scale boundary, a post-training-masked effect, or a channel-specific effect can all be successful scientific outcomes.

## 2. Why the target is CSTG

Historical-model construction is not the intended contribution. Candidate public projects reportedly provide annual or monthly point-in-time checkpoints, and other projects reportedly pretrain on much older archives. These claims and exact artifact properties must be verified during Stage 0. If verified, those checkpoints become infrastructure for an observational audit rather than the paper's main novelty.

Likewise, a result of the form “one narrow corpus changes unrelated behavior” is insufficient. Candidate recent work reportedly demonstrates broad transfer from several narrow synthetic or naturalistic domains, with important sensitivity to scale, dataset, framing, training channel, and later post-training. These reports must be checked against primary sources.

The defensible gap is narrower and stronger:

> Does the same early-versus-late behavioral contrast independently reappear when a common starting model is trained on unrelated naturalistic source families from those periods?

The intended novelty is the combination of:

1. identical starting weights;
2. timestamp-native naturalistic period corpora;
3. multiple independent source families;
4. a source family held out from hypothesis construction;
5. date-neutral evaluation domains;
6. explicit training-position controls;
7. identical downstream post-training;
8. synthetic identifiability calibration before naturalistic interpretation;
9. causal representation analysis only after behavioral replication.

Stage 0 must verify that this combination is not already occupied.

## 3. Claim vocabulary

### Temporal knowledge

Facts and concepts available to a model by a date.

### Temporal register

Period-associated vocabulary, syntax, formatting, references, and prose conventions.

### Residual temporal signature

A reproducible year- or era-associated difference in structured behavior after obvious factual and lexical cues are removed.

### Source-specific temporal effect

An early-versus-late behavioral difference appearing within one corpus family but not independently reproduced by other source families.

### Cross-Source Temporal Generalization

Agreement between independently induced early-versus-late behavioral contrasts from unrelated source families, including prediction on a source family held out from hypothesis construction.

### Temporal prior

A causal interpretation reserved for CSTG that:

- arises from common starting weights;
- transfers beyond direct training tasks;
- survives capability, knowledge, and register controls;
- is not dominated by source-specific heterogeneity;
- and persists, or predictably interacts, with common downstream post-training.

### Temporal path dependence

A difference in how historically adapted branches respond to the same later SFT, preference optimization, or other post-training update.

### Cutoff model

A model trained on information available up to a date.

### Era-window adapter

A common base model further trained on documents produced within a bounded historical window.

An era-window adapter is not a historically bounded model. Do not call an era-window branch “a model from 2013.”

### Temporal representation

An internal direction or low-dimensional subspace that predicts and causally changes held-out temporal behavior after factual and lexical-era components are separated.

“Historical personality” may be used informally as motivation. It is not an acceptable scientific conclusion.

## 4. Competing explanations

Maintain the live mechanism table in [`CLAIMS_TABLE.md`](CLAIMS_TABLE.md), including:

- M0 — noise;
- M1 — knowledge;
- M2 — register;
- M3 — capability;
- M4 — training dose;
- M5 — source culture;
- M6 — topic composition;
- M7 — direct imitation;
- M8 — shared temporal component;
- M9 — final-window recency;
- M10 — post-training path dependence;
- M11 — channel attribution;
- M12 — synthetic provenance;
- M13 — scale boundary.

Every experiment must state which mechanisms it distinguishes and which remain unresolved.

## 5. Hypotheses

### H1 — Public residual signature

Some public point-in-time model families show checkpoint-linked changes in date-neutral structured behavior after capability, factual, and lexical controls.

This is observational evidence only.

### H2 — Synthetic identifiability

The selected model, dose, training method, scorer, and evaluation recover a known latent procedural rule expressed across disjoint synthetic domains.

This validates experimental sensitivity, not historical ecology.

### H3 — Naturalistic within-source effect

Matched early and late corpora produce a behavioral contrast within at least one source family.

This is insufficient for a temporal-prior claim.

### H4 — Cross-source temporal generalization

Independent source families produce aligned early-versus-late behavioral contrasts on frozen, date-neutral tasks.

### H5 — Held-out-source prediction

A shared temporal component estimated using source families A and B predicts the direction and magnitude of the contrast in frozen source family C.

This is the primary confirmatory result.

### H6 — Persistence or path dependence

The shared contrast survives a common neutral buffer or identical post-training, or causes a reproducible difference in how branches respond to the same post-training.

### H7 — Shared causal representation

Independent same-era branches converge on an internal subspace that predicts a held-out source and domain and causally controls behavior after knowledge and register directions are removed.

## 6. Non-goals

Do not turn the project into:

- interviews with “the 2013 model”;
- a historical role-playing product;
- a generic cutoff benchmark;
- a personality-inventory study;
- a claim that a model represents an average historical citizen;
- a moral ranking of periods;
- a single left-right ideological axis;
- an open-ended LLM-judge benchmark;
- a giant uncontrolled historical web scrape;
- a four-era full-training project before the two-era design works;
- an interpretability search before behavioral replication;
- a positive-result hunt with repeatedly changed years, prompts, doses, sources, models, or thresholds.

Do not assume that later means safer, more liberal, more rational, more secure, more calibrated, more tolerant, or more technologically sophisticated.

## 7. Synthetic Identifiability Calibration

A naturalistic null is otherwise ambiguous. It could reflect absence of the phenomenon, weak historical signal, insufficient dose, insufficient model scale, insensitive evaluation, overmatching, or an adaptation method incapable of cross-domain transfer.

Before naturalistic results are interpreted, construct two or more fictional textual environments with opposing but morally symmetric latent procedural rules.

### Design requirements

- Express each latent rule indirectly through two disjoint training domains.
- Evaluate in a third domain whose surface content does not occur in training.
- Match vocabulary, length, readability, sentiment, and surface form.
- Avoid real political alignment and explicit good-versus-evil framing.
- Express the rule through repeated behavior and consequences rather than one slogan.
- Use the same base checkpoint, insertion point, objective, token budget, scorer, and run system intended for the naturalistic experiment.
- Use multiple seeds.

### Required conditions

1. **Explicit positive control** — the rule is directly stated and demonstrated.
2. **Indirect transfer condition** — the rule is only inferable across disjoint domains.
3. **Shuffled placebo** — the same documents are assigned inconsistently so no coherent rule exists.
4. **Generic continuation control** — equal exposure to matched neutral text.
5. **Dose curve** — several prespecified signal doses.
6. **Naturalistic-background injection** — where feasible, a blinded low-dose signal diluted by historical background text.

### Pass gate

Proceed to naturalistic interpretation only when:

- the explicit control is recovered;
- the indirect condition transfers above a preregistered threshold;
- the placebo remains near null;
- the effect is reproducible across seeds;
- the scorer is stable under paraphrase and option reversal;
- general capability remains within tolerance.

One predeclared rescue is allowed: a named dose increase, scale increase, or repair of a demonstrated scorer defect.

### Interpretation matrix

| Calibration | Naturalistic result | Interpretation |
|---|---|---|
| Fails | Null | Inconclusive; sensitivity at the tested pipeline, scale, or dose is not established |
| Succeeds | Null with tight bounds | Evidence against a meaningful temporal prior at the tested scale and dose |
| Succeeds | Source-specific effect | Dataset culture or source composition, not source-general era |
| Succeeds | A/B replication | Exploratory evidence for CSTG |
| Succeeds | Held-out C prediction | Confirmatory CSTG |
| Succeeds | Survives common post-training | Persistent temporal prior or temporal path dependence |
| Succeeds | Shared causal representation | Strongest mechanistic result |

## 8. Stage 0 — Feasibility and novelty audit

Substantial model training is blocked until this stage is complete.

### 8.1 Literature audit

Verify exact versions, dates, publication status, methods, artifacts, limitations, and overlap for the following candidate references supplied to the project:

- DatedGPT — arXiv:2603.11838
- Scaling Point-in-Time Language Models — arXiv:2607.11889
- Chronologically Consistent Large Language Models — arXiv:2502.21206
- Pretraining Language Models on Historical Text — arXiv:2606.02991
- Understanding Data Temporality Impact on LLM Pre-training — arXiv:2605.22769
- Set the Clock — arXiv:2402.16797
- Fine-Tuned LLMs Are “Time Capsules” — arXiv:2502.05331
- Weird Generalization and Inductive Backdoors — arXiv:2512.09742
- Weird Generalization Is Weirdly Brittle — arXiv:2604.10022
- Innocuous-Seeming Data, Latent Ideology — arXiv:2607.14888
- Harmful Content Is Not Enough — arXiv:2608.08212
- Data Attribution of Emergent Misalignment with Persona Features — arXiv:2608.11025
- Emergent and Subliminal Misalignment Through the Lens of Data-Mediated Transfer — arXiv:2605.12798
- Similar Models Learn Differently — arXiv:2607.25063
- Persona Vectors — arXiv:2507.21509
- Persona Features Control Emergent Misalignment — arXiv:2506.19823
- Emergent Misalignment Recruits a Pre-existing Persona Subspace — arXiv:2607.21356
- Model Spec Midtraining
- relevant synthetic-document fine-tuning, belief modification, pretraining path dependence, social-simulation robustness, and historical-model-validity work.

The list is an audit queue, not a verified bibliography.

For each source, record:

- result actually established;
- model family and scale;
- training or prompting channel;
- natural versus synthetic data;
- direct versus held-out transfer;
- scale dependence;
- contextual brittleness;
- source, code, and model availability;
- relevance to CSTG;
- remaining open question.

The audit must answer:

1. What has already been demonstrated?
2. Which results are model-, scale-, dataset-, or format-specific?
3. Which results failed to replicate broadly?
4. What makes held-out-source naturalistic replication distinct?
5. What remains publishable under a null?
6. Which project and paper names are already occupied?

### 8.2 Model-access audit

Verify rather than assume:

- exact repository identifier;
- available years or revisions;
- base versus instruction variants;
- architecture and parameter count;
- tokenizer and context length;
- license;
- custom-code requirement;
- revision hashes;
- storage and precision;
- activation access;
- training support;
- loading behavior on the available hardware.

Audit at least:

- DatedGPT;
- PIT;
- ChronoGPT;
- TypewriterLM;
- OLMo 2 1B and relevant intermediate checkpoints;
- one plausible second-family causal model.

Any custom remote code must be pinned and inspected before execution.

Public checkpoint candidates are observational tools. OLMo 2 1B is the provisional causal-base candidate because it may offer open intermediate checkpoints and training materials, but no model is selected until exact artifacts and measured feasibility are verified.

### 8.3 Local compute audit

Record and measure:

- operating system;
- CPU;
- GPU and VRAM;
- RAM;
- free storage;
- CUDA or equivalent runtime;
- Python environment;
- model caches;
- container capability;
- model load time;
- peak memory;
- conditional-log-probability throughput;
- checkpoint storage;
- tiny legal training throughput.

The reported current machine is RTX 2060 with 16 GB RAM. A borrowed RTX 5070 with 32 GB RAM may be available, but availability and exact capability are not assumed.

Do not purchase or rent compute. Produce a measured budget and escalation decision.

### 8.4 Data-source audit

Candidate sources must be evaluated for:

- native publication or revision timestamps;
- distinction among publication, event, upload, crawl, and archive-capture time;
- continuous coverage;
- license, attribution, research use, and redistribution;
- provenance;
- human versus synthetic authorship;
- source and genre stability;
- token volume;
- topic composition;
- bot, spam, vandalism, and duplicate rates;
- event concentration;
- extraction cost;
- evaluation contamination;
- direct overlap with primary constructs.

Candidate source classes include:

- Wikimedia revision histories using added-text deltas rather than repeated full snapshots;
- timestamped technical or community archives with explicit licenses;
- official dated public documents;
- item-level open-access scientific corpora;
- other sources discovered during audit.

Do not use Common Crawl crawl date as a silent substitute for publication date in the causal era-window experiment.

### 8.5 Domain-exposure matrix

For each source and evaluation domain, classify exposure as:

- direct;
- structurally related;
- indirect;
- plausibly absent;
- unknown.

The primary CSTG claim may use only task families not directly taught by any included source branch.

For secure-system decisions, exclude source code, cybersecurity tutorials, vulnerability descriptions, secure-coding instruction, and benchmark solutions.

For evidence integration, exclude calibration tutorials, Bayesian instruction, source-reliability teaching, misinformation benchmarks, and direct evaluation templates.

For procedural trade-offs, exclude copied survey questions, benchmark dilemmas, and targeted ideological text selected to manufacture an expected result.

### 8.6 Era-window selection

Provisional candidates:

- January 2012–December 2013 versus January 2018–December 2019;
- a narrower one-year version;
- another pair justified by continuity and licensing.

Select the pair using data criteria only:

- cross-source token sufficiency;
- timestamp confidence;
- source continuity;
- topic-match feasibility;
- historical separation;
- human-authorship confidence;
- license;
- event concentration.

Do not inspect behavioral outcomes before freezing the pair.

As a data diagnostic, estimate Cross-Source Era Decodability by masking explicit dates and high-information named entities, training a window classifier on source A, testing on B, reversing the direction, and comparing within-source with cross-source separability. This establishes textual contrast, not a behavioral prior.

### 8.7 Stage 0 exit

Produce `reports/stage0/feasibility_novelty_and_design_report.md` with:

- defensible novelty statement;
- overlap matrix;
- verified model access;
- measured local compute;
- source candidates;
- provisional era decision;
- legal and provenance risks;
- evaluation plan;
- synthetic-calibration design;
- estimated pilot cost;
- proceed, narrow, or stop recommendation.

## 9. Stage 1 — Evaluation instrument and public-checkpoint audit

### 9.1 Primary domains

#### Evidence integration

Use fictional micro-worlds with:

- explicit initial evidence or priors;
- independently varied source reliability;
- true and false claims;
- underdetermined cases;
- authority-versus-track-record conflict;
- reversed evidence order;
- distractors;
- delayed persistence questions.

Measure normalized likelihoods, update direction, reliability sensitivity, false-evidence uptake, order effects, persistence, and calibration.

#### Procedural trade-offs

Use date-neutral fictional institutions and organizations involving:

- centralized authority versus distributed verification;
- speed versus procedural safeguards;
- privacy versus collective detection;
- reversible versus irreversible action;
- expert deference versus independent checking;
- punishment versus rehabilitation;
- dissent;
- transparency;
- allocation under uncertainty.

Do not encode an assumed desirable era direction.

#### Secure-system decisions

Keep this secondary. Begin with structured architecture choices and advance to executable code only after every model passes a frozen functional-capability gate.

### 9.2 Item construction

Before creating many items:

1. write construct definitions;
2. write inclusion and exclusion rules;
3. define expected invariances;
4. define forbidden temporal cues;
5. create templates;
6. create a small development set;
7. run adversarial temporal-cue review;
8. run political and moral wording review;
9. run tokenizer and scorer review;
10. revise;
11. freeze;
12. hash the manifest.

Initial target:

- approximately 24–40 development items per primary domain;
- expansion toward at least 100 frozen items only when reliability supports it;
- counterbalanced paraphrases;
- approximately 40–60 structured security items if the secondary domain remains viable.

Each item needs a card with construct, rationale, answer balance, confounds, paraphrases, order variants, expected invariances, and contamination status.

### 9.3 Primary scoring

Use base-model conditional log probabilities as the primary instrument.

For each pairwise item:

- score complete natural-language continuations;
- match continuation structure and length;
- reverse option order;
- rotate labels when unavoidable;
- use meaning-preserving paraphrases;
- inspect tokenizer boundaries;
- retain token-level diagnostics;
- calculate raw normalized probabilities;
- calculate one prespecified calibrated alternative;
- preserve malformed and truncation indicators.

Generated explanations are secondary and do not determine the primary outcome.

### 9.4 Public model panel

Subject to access verification, audit base checkpoints from DatedGPT and PIT around:

- 2013;
- 2016;
- 2019;
- 2022;
- 2024.

Analyze each family separately before cross-family comparison. Independently trained annual models, cumulative monthly lineages, and long-range checkpoints are distinct observational designs.

ChronoGPT, TypewriterLM, and older models may be boundary cases. Do not pool them into the main trajectory when architectures, corpora, doses, or periods differ substantially.

### 9.5 Public-audit controls

Implement:

- factual-cutoff probes;
- lexical-era classifier;
- timeless capability tasks;
- language-model loss;
- refusal and malformed-output rate;
- continuation-length diagnostics;
- raw versus calibrated scoring;
- base versus instruction comparison;
- prompt-paraphrase reliability;
- option-order reliability.

Report checkpoint vectors, within-family trajectories, item-level deltas, cross-family delta correlations, split-half reliability, paraphrase reliability, noise ceilings, and capability-adjusted sensitivity analyses.

This stage is observational. Do not use causal language.

## 10. Stage 2 — Synthetic Identifiability Calibration

Run the frozen calibration with the same base, insertion point, objective, scorer, run registry, and comparable budget intended for Stage 3.

Produce `reports/stage2/synthetic_identifiability_calibration.md`.

If calibration fails, diagnose scorer, capability, dose, and method; use at most one predeclared rescue; and do not interpret a later naturalistic null as evidence against temporal priors.

## 11. Stage 3 — Naturalistic causal pilot

### 11.1 Common base

Select the causal base in `docs/MODEL_SELECTION_ADR.md`.

Criteria:

- openness;
- intermediate checkpoints;
- training-code availability;
- tokenizer;
- activation access;
- license;
- training feasibility;
- calibration capability;
- compatibility with common later post-training.

### 11.2 Primary design

Use:

\[
2\ \text{era windows}
\times
2\ \text{independent source families}
\times
3\ \text{exploratory seeds}
=
12\ \text{primary branches}.
\]

Minimum pilot controls:

- no-continuation base;
- common generic continuation;
- matched mixed-era corpus;
- within-era pseudo-era placebo;
- one order control where feasible.

Do not create a giant factorial before the primary signal is known.

### 11.3 Matching

Within each source family, match or model:

- target-token count;
- document count and length;
- source or host distribution;
- genre and topic;
- readability;
- sentiment and toxicity;
- quality;
- duplication;
- language;
- author or contributor type;
- timestamp confidence;
- human-authorship confidence;
- bot content;
- event concentration.

Across branches, hold fixed:

- starting weights;
- tokenizer;
- objective;
- optimizer and schedule;
- batch;
- context length;
- total target tokens and updates;
- checkpoint schedule;
- document-order policy;
- insertion point.

### 11.4 Training method

Parameter-efficient training may be used for pipeline debugging, scorer validation, dose reconnaissance, and cost estimation.

Do not make the central naturalistic claim from PEFT alone.

The headline experiment should use full-weight continued pretraining or a broad-update method justified in advance as an adequate approximation.

Run a tiny smoke test before any full branch.

### 11.5 Decontamination

Before training:

- exact-match search;
- near-duplicate search;
- semantic-similarity search;
- benchmark phrase search;
- direct evaluation vocabulary search;
- source-code and security-content filtering;
- calibration and Bayesian-tutorial filtering;
- survey-question filtering.

Preserve immutable raw data and derived-data lineage.

### 11.6 Primary estimand

For source family \(s\), domain \(d\), and seed \(r\), store:

\[
B_d(M_{e,s,r}).
\]

Estimate:

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

The primary pilot statistic is Cross-Source Temporal Agreement between A and B.

Report:

- vector correlation;
- cosine alignment;
- sign agreement;
- common-component magnitude;
- source-specific heterogeneity;
- branch-level permutation null;
- uncertainty over branches and items.

### 11.7 Continuation gate

Proceed only when:

- synthetic calibration passed;
- at least one primary domain is reliable;
- both source families have estimable era contrasts;
- effect vectors agree above a frozen threshold;
- source heterogeneity does not dominate;
- capability degradation does not explain the pattern;
- factual and lexical controls do not absorb it;
- prompt counterbalancing does not reverse it;
- all branches and failures are reported.

A source-specific result remains source-specific. A calibrated tight null can justify stopping and writing a null paper.

Allow at most one prespecified dose or scale rescue.

## 12. Stage 4 — Held-out source and path dependence

### 12.1 Source C

Select C during data audit but keep it unused for:

- item construction;
- temporal-direction estimation;
- hyperparameter selection;
- dose selection;
- threshold selection;
- mechanistic layer selection.

Estimate the shared component from A and B, freeze it, then test source C on frozen items.

The main confirmatory test is prediction of source C's direction, relative magnitude, and item-level effect pattern.

### 12.2 Confirmatory seeds

Use pilot variance and simulation-based power analysis. Three exploratory seeds do not automatically constitute adequate confirmation.

The independently trained branch or seed is the experimental unit.

### 12.3 Training-position control

For selected branches, compare:

- base → era window;
- base → era window → common neutral buffer;
- base → common neutral buffer → era window.

Hold total exposure constant where required.

### 12.4 Common post-training

Apply identical modern SFT to selected early and late branches. Measure:

- pre-SFT behavior;
- post-SFT behavior;
- change caused by SFT;
- capability and instruction following;
- refusal and malformed output;
- CSTG retention.

Add one identical preference-training stage only when resources and evidence justify it.

Estimate:

\[
\text{post-training response}
=
B(\text{after common update})
-
B(\text{before common update}).
\]

Classify the effect as erased, masked, persistent, transformed, or path-dependent.

### 12.5 Scale and family replication

A null at 1B is scale-bounded unless calibration succeeded, meaningful effects were excluded statistically, and the model passed capability gates.

Replicate the most important positive or tight-null result on a second family or scale only when compute is approved and scientifically decisive.

## 13. Stage 5 — Channel attribution

Run this only after naturalistic CSTG replicates or a clear source-specific effect needs explanation.

Compare:

- original naturalistic documents under next-token loss;
- closely matched assistant responses;
- archive-attributed or quoted historical text;
- source content transformed by a pinned synthetic teacher.

An omnibus difference does not identify speaker identity. The conditions can differ in role tokens, continuation structure, target-token exposure, label masking, synthetic phrasing, and provenance.

After an omnibus difference, isolate:

1. same sequence, different loss mask;
2. same target tokens, different wrapper;
3. same wrapper, human versus synthetic wording;
4. archive metadata versus neutral metadata;
5. matched continuation invitation.

## 14. Stage 6 — Mechanistic analysis

Do not begin substantial mechanism work before behavioral confirmation.

Test whether:

- independent same-era sources produce convergent activation shifts;
- same-era convergence exceeds cross-era and random nulls;
- a subspace trained on A and B predicts C;
- a subspace trained on one behavioral domain predicts another;
- the signal remains after factual and lexical-era projection;
- the training-induced subspace differs from prompted historical role play;
- injection or ablation changes frozen behavior;
- intervention avoids capability collapse and dated-word leakage.

Use activation deltas, representational similarity, principal angles, cross-source probes, cross-domain prediction, matched-style nulls, random-subspace nulls, and causal projection/injection/ablation.

Choose layers and hyperparameters using development runs only.

Do not claim a one-dimensional “era vector” unless the evidence supports one-dimensional structure. A decoder is not a causal representation.

## 15. Statistical requirements

Freeze `docs/STATISTICAL_ANALYSIS_PLAN.md` before confirmatory source-C runs.

Requirements:

- the independently trained branch or seed is the experimental unit;
- item, paraphrase, and sample repetitions do not create independent model replications;
- use hierarchical or cluster-aware uncertainty over models and items;
- use branch-level era-label permutations;
- estimate era, source, era-by-source, stage, and relevant interactions;
- report source heterogeneity, not only pooled averages;
- preregister primary composites;
- preregister the smallest scientifically meaningful effect;
- use equivalence testing for null claims;
- control multiplicity for secondary outcomes;
- define malformed-output and missing-run handling;
- preserve all seed-level results;
- never remove unfavorable seeds post hoc;
- do not choose layers, prompts, calibrations, or axes using final data.

For CSTG report at least:

- source-specific effect vectors;
- pairwise effect-vector agreement;
- shared-component estimate;
- source-specific residual variance;
- source-C predictive performance;
- randomization statistic;
- interval relative to the meaningful-effect threshold;
- sensitivity to capability, factual, and lexical controls.

## 16. Human-data triangulation

ANES and GSS are potential secondary directional triangulation sources, not historical ground truth. Their exact releases, repeated-item coding, weights, wording, placement, survey mode, and longitudinal comparability must be verified.

Permitted claim:

> Some model-level temporal changes align with independently measured human trends.

Prohibited claim:

> The model simulates the average person from the target year.

Do not train on survey questions or use survey agreement as the main endpoint.

## 17. Reproducibility

Every run records:

- immutable run ID;
- Git commit;
- complete configuration;
- environment lock;
- model repository and revision;
- model hashes where practical;
- tokenizer revision;
- base and insertion checkpoint;
- data-manifest hash;
- evaluation-manifest hash;
- seeds;
- hardware and precision;
- objective and target-token budget;
- start and end status;
- raw metrics and outputs;
- logs and checkpoints;
- failures and exclusions;
- generated report and artifact hashes.

No silent fallback to another model, revision, tokenizer, prompt, precision, device, source, evaluation subset, or scoring method.

Fail loudly on missing logits, truncation, incompatible tokenizers, partial datasets, hash mismatches, absent checkpoints, malformed outputs, or incomplete branch sets.

Use local Git commits as reversible milestones.

## 18. Engineering

Prefer a reproducible Python stack with:

- a locked environment;
- PyTorch;
- native or Transformers-compatible model loading;
- typed configuration;
- JSONL or Parquet artifacts;
- pytest;
- linting and type checking;
- deterministic report scripts.

Keep notebooks exploratory. Move final logic into tested modules.

Test:

- model adapters;
- conditional continuation scoring;
- option permutation;
- calibration;
- tokenizer edge cases;
- manifests;
- evaluation hashing;
- resumption;
- aggregation;
- exclusion handling;
- statistical inputs;
- report generation.

Generated-code security evaluation must use a sandbox with no unnecessary network, strict time/memory/process limits, filesystem isolation, and cleanup.

## 19. Data, legal, and ethical boundaries

For each source record:

- owner or steward;
- access method;
- exact license;
- permitted research use;
- attribution;
- redistribution;
- publication or revision timestamp;
- timestamp confidence;
- authorship provenance;
- extraction;
- cleaning and filtering;
- deduplication;
- transformations;
- document and token counts;
- hashes.

Do not assume:

- public access permits redistribution;
- a repository has one license;
- crawl time equals publication time;
- modern text is human-authored;
- government-hosted material is necessarily a government work;
- derived model-weight rights are obvious.

Do not ingest private correspondence, credentials, private user data, restricted datasets, or sensitive personal records.

If future work recruits human raters, stop before recruitment and identify the required ethics and consent process.

## 20. Resource constraints

Follow [`RESOURCE_CONSTRAINTS.md`](RESOURCE_CONSTRAINTS.md).

Binding defaults:

- current reported machine: RTX 2060 and 16 GB RAM;
- possible borrowed machine: RTX 5070 and 32 GB RAM, not assumed available;
- minimize cash spend;
- CAD $0 external compute unless explicitly authorized;
- one training job at a time;
- benchmark before token budgets;
- no full naturalistic branch set before calibration and cost gates;
- PEFT for smoke work only unless separately justified;
- no paid rescue of an unidentifiable design.

## 21. Review gates

Before freezing evaluation, obtain separate internal reviews for:

- construct validity;
- temporal-cue leakage;
- political and moral wording;
- scorer correctness;
- statistical design;
- decontamination;
- domain exposure;
- security-evaluation safety.

Before interpreting confirmation, obtain separate reviews for:

- run completeness;
- statistical correctness;
- source heterogeneity;
- capability confounding;
- factual and lexical leakage;
- alternative mechanisms;
- negative-result handling;
- reproducibility;
- claim strength.

Each review records finding, evidence, severity, recommendation, and manager disposition.

## 22. Claim ladder

### Level 0 — No reliable effect

No stable era contrast after controls.

Conclusion: no evidence for a meaningful temporal behavioral prior at the tested model, dose, and design.

### Level 1 — Knowledge or register

Facts and historical prose change; date-neutral behavior does not.

Conclusion: adaptation changes archive representation, not global policy.

### Level 2 — Source-specific temporal effect

One source changes held-out behavior but independent sources do not reproduce it.

Conclusion: source culture, topic mixture, or dataset-specific transfer.

### Level 3 — CSTG

Independent sources produce aligned contrasts and held-out source C reproduces the shared component.

Conclusion: evidence for a source-general temporal component.

### Level 4 — Persistence or path dependence

The component survives a common buffer or post-training, or predicts differential response to the same update.

Conclusion: historical training path constrains later model formation.

### Level 5 — Shared causal representation

A cross-source internal subspace predicts and causally controls held-out behavior after knowledge and register are separated.

Conclusion: mechanistic evidence for a temporal representation.

Never claim a higher level from lower-level evidence.

## 23. Stop and rescue rules

Stop or redesign when:

- evaluation is unreliable;
- synthetic positive controls fail;
- the model cannot perform base tasks;
- timestamp or license quality is inadequate;
- source matching is impossible;
- contamination cannot be bounded;
- branches cannot be reproduced;
- compute exceeds authorized resources.

For each major negative gate, permit at most one predeclared rescue, such as a dose increase, scale increase, demonstrated scorer repair, or replacement of a source that failed prespecified feasibility criteria.

Do not repeatedly alter the project until it becomes positive.

## 24. Reporting

Every material report includes:

### Decision

What was decided or what decision is required.

### Evidence

Observed results and source-backed facts.

### Artifacts

Files, commits, manifests, run IDs, and reports.

### Validation

Commands, tests, hashes, and run-completeness status.

### Risks

Scientific, statistical, legal, compute, and engineering risks.

### Next write-active deliverable

Exactly one primary deliverable.

Required reports:

- `reports/stage0/feasibility_novelty_and_design_report.md`
- `reports/stage1/public_checkpoint_audit.md`
- `reports/stage2/synthetic_identifiability_calibration.md`
- `reports/stage3/naturalistic_causal_pilot.md`
- `reports/stage4/held_out_source_and_post_training.md`
- `reports/stage5/channel_attribution.md`
- `reports/stage6/mechanistic_analysis.md`
- `reports/final/chronopersona_decision_report.md`

## 25. Paper package

When evidence justifies manuscript work, produce:

- frozen charter;
- locally timestamped and hashed protocol;
- literature matrix;
- model manifest;
- source data cards;
- derived-data manifests;
- evaluation cards;
- calibration documentation;
- statistical plan;
- run registry;
- claims-to-results map;
- reproducibility commands;
- scripted tables and figures;
- complete null and failure appendix;
- limitations;
- legal and ethics statement;
- manuscript draft.

Use the neutral title until results exist. Do not select a positive- or null-result title in advance.

## 26. Immediate execution sequence

1. Inspect repository state, instruction hierarchy, environment, hardware, storage, and existing artifacts.
2. Maintain `PROJECT_STATE.md`, `PLAN.md`, and `docs/DECISIONS.md`.
3. Produce the first primary-source literature matrix.
4. Verify exact model identifiers, revisions, licenses, loading code, and storage for the candidate public models.
5. Inspect required custom code before execution.
6. Run a tiny safe model-loading and logits smoke test on the smallest practical checkpoint.
7. Implement a conditional-continuation scorer with complete likelihoods, option reversal, paraphrases, tokenizer diagnostics, normalized scores, and immutable metadata.
8. Add scorer tests.
9. Draft approximately twelve development items across the two primary domains.
10. Run temporal-cue and wording reviews.
11. Audit small samples from at least three timestamp-native corpus families.
12. Create the first data-source decision record and domain-exposure matrix.
13. Freeze the synthetic calibration design before training it.
14. Produce the Stage 0 exit report.

Do not draw scientific conclusions from smoke tests or twelve development items. After recording a milestone, continue to the next unblocked Stage 0 task.
