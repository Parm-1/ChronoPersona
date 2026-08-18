# Charter Module 03 — Naturalistic Discovery and Prospective Confirmation

## Phase 0 source and era gate

Audit at least four timestamp-native candidate source families before assigning roles. Candidate classes include Wikimedia revision-derived text, explicitly licensed scientific text, Global Voices original articles, official dated public documents, and other sources found during audit.

For each candidate, measure:

- native publication/revision timestamp semantics;
- historical-version recoverability;
- continuous early/late coverage and token volume;
- exact license, attribution, training, redistribution, and release boundaries;
- human, synthetic, bot, and transformed authorship;
- source/genre/topic/contributor continuity;
- boilerplate, revisions, cross-posting, duplication, event concentration, and direct evaluation exposure;
- extraction, storage, and review cost.

The provisional windows remain 2012-01-01 through 2013-12-31 and 2018-01-01 through 2019-12-31. Freeze them using data feasibility only. One alternate pair is allowed before behavioral outcomes.

Before role freeze, run cross-source era decodability after masking explicit dates and high-information entities. This establishes shared textual distinction, not behavioral policy.

Predesignate A, B, C, and at most one feasibility backup before model behavioral inspection. The backup may activate only when C fails a prespecified feasibility criterion, never when C gives an unfavorable result.

## Common causal branch policy

All branches begin from identical pinned weights. Hold fixed tokenizer, objective, broad-update method, optimizer/reset policy, schedule, target tokens, sequence length, batch construction, precision, updates, checkpoints, and document-order policy.

Use paired randomization where possible so corresponding early/late branches share procedural randomness without sharing documents.

PEFT is permitted for loader, scorer, dose, and cost reconnaissance. The headline test requires full-weight continued pretraining or another broad-update method justified before results.

Naturalistic dose is selected from calibration, period-text loss, capability retention, training stability, measured throughput, and authorized budget—not desired behavioral direction.

## A/B discovery

Initial matrix:

`2 eras × 2 discovery sources × 3 exploratory paired seeds = 12 branches`

Minimum controls:

- no-continuation base;
- matched generic continuation;
- within-era pseudo-period placebo;
- opaque-label leakage check;
- optional mixed-era control only if interpretation and budget are frozen.

For source `s`, estimate:

`tau_s = mean_seed,prompt[Y_late,s - Y_early,s]`

Freeze one transparent estimator `G` and calculate:

`g_AB = G(tau_A, tau_B)`

Report source vectors, weighted correlation, cosine alignment, sign agreement, shared magnitude, source residual variance, branch uncertainty, item noise ceiling, capability/factual/register sensitivity, generic drift, and ecological composition diagnostics.

A/B agreement is a continuation gate and Level 3 preliminary evidence only.

Proceed to C only when measurement and calibration pass, both sources are estimable, agreement exceeds a frozen threshold, generic continuation does not explain it, source heterogeneity does not dominate, and no known engineering defect remains.

## Sealed source-C confirmation

Choose confirmatory seed count using simulation-based power analysis from calibration and A/B branch/item variance. Three seeds are not automatically adequate.

Use opaque branch identities. Do not expose condition-linked confirmation summaries until:

- all planned branches reach a frozen terminal state;
- hashes and run identities match;
- failures are dispositioned under frozen rules;
- analysis passes mock-null and permuted-map tests;
- the condition map is ready to unseal.

Primary confirmation:

1. Estimate and freeze `g_AB` using A and B only.
2. Estimate `tau_C` on the sealed confirmation partition.
3. Test whether `g_AB` predicts `tau_C`.

Report out-of-sample weighted correlation, predictive slope, cosine alignment, sign agreement, prediction error relative to null, shared reliable variance, and branch-level paired era-label randomization. Items and paraphrases are repeated measurements, not model replications.

## Decision rule

- **C succeeds:** CSTG across the tested source families, model, dose, windows, and domains.
- **C fails:** reject CSTG for that scope. Preserve A/B or source-specific findings at their lower claim level.

After C outcomes, do not change source, era pair, item set, estimator, meaningful threshold, or temporal axis.

## Composition-adjusted confirmation

Run the already-frozen balancing/weighting procedure after the ecological result. Report ecological and adjusted results separately. Do not tune matching using model behavior or describe adjustment as recovering a pure era effect.