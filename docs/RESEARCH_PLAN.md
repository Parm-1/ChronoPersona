# Research Plan

The detailed scientific design is in [`RESEARCH_CHARTER.md`](RESEARCH_CHARTER.md). This file is the compact executable research plan.

## 1. Scientific target

ChronoPersona tests **Cross-Source Temporal Generalization (CSTG)**:

> Does a matched early-versus-late corpus intervention create a shared component of date-neutral model behavior that independently replicates across source families, predicts a held-out source, and changes response to identical later post-training?

A temporal prior is a possible interpretation only after CSTG survives the required controls.

## 2. Causal object

For source family \(s\), domain \(d\), era \(e\), and training seed \(r\), let:

\[
B_d(M_{e,s,r})
\]

be the vector of frozen behavioral log-odds.

The source-specific temporal contrast is:

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

The central question is whether independently induced source contrasts contain a reproducible shared component:

\[
\tau_{A,d}
\approx
\tau_{B,d},
\]

and whether that component predicts \(\tau_{C,d}\) for a source family held out from hypothesis construction and tuning.

## 3. Construct separation

Keep these outcomes separate:

- **Temporal knowledge:** facts and concepts available by a date.
- **Temporal register:** period-linked vocabulary, syntax, formatting, and references.
- **Residual temporal signature:** structured behavioral difference after obvious knowledge and register cues are reduced.
- **Source-specific temporal effect:** a within-source contrast that does not replicate independently.
- **CSTG:** cross-source agreement with held-out-source prediction.
- **Temporal path dependence:** different response to identical later post-training.
- **Temporal representation:** a cross-source internal subspace with held-out predictive and causal validity.

## 4. Primary domains

### Evidence integration

Use fictional micro-worlds with varied priors, source reliability, true and false evidence, underdetermination, authority-versus-track-record conflicts, evidence order, and delayed persistence.

### Procedural trade-offs

Use timeless fictional organizations to test authority versus verification, safeguards versus speed, privacy versus detection, reversible versus irreversible action, expert deference, rehabilitation, dissent, transparency, and secrecy.

### Secure-system decisions

Secondary far-transfer domain. Begin with structured architecture choices; executable code is capability- and sandbox-gated.

## 5. Required experimental sequence

### Stage 0 — Feasibility and novelty

Verify:

- nearest literature and actual novelty;
- public model identifiers, revisions, licenses, and artifact access;
- local hardware, storage, memory, logits throughput, and tiny-training throughput;
- timestamp-native data sources, rights, provenance, and continuity;
- domain exposure and contamination;
- evaluation reliability;
- projected branch cost.

No substantial training before Stage 0 exit.

### Stage 1 — Public-checkpoint audit

Use public point-in-time models to test whether the frozen instrument detects reproducible temporal trajectories. Analyze each model family separately. This is observational.

### Stage 2 — Synthetic Identifiability Calibration

Use morally symmetric fictional latent rules expressed through disjoint training domains and tested in a third unseen domain.

Required conditions:

- explicit positive control;
- indirect transfer;
- shuffled placebo;
- neutral continuation;
- dose curve;
- optional blinded signal in naturalistic background.

A naturalistic null is uninterpretable if this calibration fails.

### Stage 3 — Naturalistic causal pilot

Provisional design:

\[
2\ \text{eras}
\times
2\ \text{source families}
\times
3\ \text{seeds}
=
12\ \text{primary branches}.
\]

Provisional windows:

- early: 2012-01-01 through 2013-12-31;
- late: 2018-01-01 through 2019-12-31.

The final windows and sources are chosen from data criteria before behavioral outcomes.

Required controls:

- unadapted base;
- common generic continuation;
- matched mixed-era corpus;
- within-era pseudo-era placebo;
- order control where feasible.

### Stage 4 — Held-out source and common post-training

Estimate the shared component using A and B, freeze it, and predict source C.

Then compare common neutral buffers, training-position order, identical modern SFT, and—only when justified—identical preference training. Measure both endpoints and response to the common update.

### Stage 5 — Channel attribution

Compare naturalistic documents, assistant-response formatting, archive attribution, synthetic transformation, role tokens, and loss masking one variable at a time.

### Stage 6 — Mechanisms

Only after behavioral replication, test cross-source activation convergence, source-C prediction, cross-domain prediction, projection of factual/register components, prompt-role nulls, and causal injection or ablation.

## 6. Data design

Every eligible document needs:

- source and locator;
- native timestamp and semantics;
- timestamp confidence;
- owner/steward;
- license, attribution, research-use, and redistribution status;
- human/synthetic provenance;
- language, genre, topic, quality, and contributor type;
- content hash and deduplication identity;
- token count;
- transformations;
- exclusion status and reason.

Within source families, match or model token count, document count/length, host distribution, genre, topic, readability, sentiment, toxicity, quality, duplication, language, contributor type, timestamp confidence, bot content, and event concentration.

Across branches, hold starting weights, tokenizer, insertion point, objective, optimizer, schedule, batch, context, target tokens, updates, checkpoint policy, and order policy fixed.

## 7. Evaluation

Primary scoring uses complete-continuation conditional log probabilities.

Requirements:

- natural-language continuation pairs;
- matched structure and length;
- option reversal;
- label rotation;
- paraphrases;
- tokenizer diagnostics;
- raw normalized scores;
- one prespecified calibrated alternative;
- malformed/truncation indicators;
- frozen metadata;
- blinded condition identities.

Generated explanations are secondary.

The evaluation registry is frozen before confirmatory outputs. Direct dates, events, era labels, and obvious intended-answer cues are forbidden from confirmatory date-neutral items.

## 8. Analysis

The independently trained branch or seed is the experimental unit.

Report:

- source-specific effect vectors;
- vector correlation;
- cosine alignment;
- sign agreement;
- common-component magnitude;
- source-specific residual variance;
- branch-level permutation statistics;
- source-C predictive performance;
- uncertainty over branches and items;
- intervals relative to a preregistered meaningful threshold;
- equivalence testing for nulls;
- sensitivity to capability, factual, lexical, topic, and training-position controls.

Do not select the strongest prompt, layer, score, model, dose, or era pair using final data.

## 9. Gates

### Stage 2 pass

- explicit signal recovered;
- indirect signal transfers;
- placebo near null;
- reproducible across seeds;
- scorer reliable;
- capability preserved.

### Stage 3 continuation

- calibration passed;
- primary measurement reliable;
- both sources have estimable contrasts;
- A/B vectors agree above threshold;
- source heterogeneity does not dominate;
- capability, knowledge, register, and prompt order do not explain the pattern;
- all branches and failures reported.

### Stage 4 confirmation

- shared A/B component frozen before source C;
- confirmatory seed count chosen from power analysis;
- source C predicts above frozen threshold;
- post-training tests use identical updates;
- no unregistered rescue or selection.

## 10. Stop rules

Stop or redesign when:

- novelty collapses;
- data timestamps or rights are inadequate;
- two independent source families cannot be matched;
- evaluation is unreliable;
- synthetic calibration fails after one rescue;
- the base model cannot perform the tasks;
- run identities or resumption are unreliable;
- contamination cannot be bounded;
- projected compute exceeds authorized resources.

A clean null is a valid outcome. Do not repeatedly change years, sources, prompts, doses, or scales until an effect appears.

## 11. Resource rule

Follow [`RESOURCE_CONSTRAINTS.md`](RESOURCE_CONSTRAINTS.md).

The default is local-only, CAD $0 external spend, one training job, measured benchmarks before budgets, and no 12-branch pilot before Stage 0 and Stage 2 gates pass.
