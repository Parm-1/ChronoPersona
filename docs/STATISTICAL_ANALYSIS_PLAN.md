# Statistical Analysis Plan — Prospective CSTG v1.0

**Status:** development; must be frozen before source-C outcome access.

## Experimental unit

The independently trained branch or seed is the experimental unit. Items, paraphrases, option orders, generated samples, and repeated evaluation runs are repeated measurements, not independent model replications.

Use paired seeds where feasible so corresponding early/late branches share optimizer initialization, random streams, shuffling policy, batch-construction policy, and checkpoint schedule while receiving different documents.

## Item-level outcome

For era `e`, source `s`, seed `r`, item `i`, prompt form `p`, and stage `k`:

`Y_e,s,r,i,p,k = log P(a_i,1 | x_i,p) - log P(a_i,2 | x_i,p)`

Candidate semantic orientation is fixed before outcomes. Average prompt forms under a prespecified rule; retain form-level diagnostics.

Source-specific temporal vector:

`tau_s,i,k = mean_r,p[Y_late,s,r,i,p,k - Y_early,s,r,i,p,k]`

## Discovery estimator

Using development data from A and B only, freeze one transparent estimator:

`g_AB,k = G(tau_A,k, tau_B,k)`

Candidate `G` choices are an inverse-variance weighted mean, a one-factor hierarchical model, or a prespecified low-rank multivariate model. The choice and hyperparameters must be frozen before confirmation outcomes. Do not select the estimator that maximizes A/B agreement.

A/B continuation statistics include weighted correlation, cosine alignment, sign agreement, shared-component magnitude, source residual variance, branch uncertainty, and item noise ceiling. These are discovery statistics, not the confirmatory claim.

## Confirmation object

On the sealed confirmation partition:

1. Recompute or load frozen `g_AB` using A/B only.
2. Estimate `tau_C` under the frozen branch and prompt rules.
3. Evaluate prospective prediction of `tau_C` by `g_AB`.

Primary confirmatory outputs:

- weighted out-of-sample correlation;
- predictive slope with interval;
- cosine alignment;
- sign agreement;
- prediction error relative to prespecified nulls;
- shared reliable variance;
- prespecified combined multivariate test.

Primary inference uses branch-level era-label randomization preserving source and paired-seed structure. Do not permute individual items as though they were independently trained models.

## Primary domains and multiplicity

Primary confirmatory tests:

1. evidence-integration transport;
2. procedural-decision transport;
3. one prespecified combined multivariate transport test.

Secure-system decisions, open-ended generations, human-survey triangulation, channel analyses, and mechanisms are secondary. Freeze multiplicity treatment before C.

## Reliability and uncertainty

Use hierarchical or cluster-aware uncertainty over branches and items. Report source-specific estimates and heterogeneity rather than only pooled composites. Correct for reliability only under a frozen method or report explicit noise ceilings.

Retain all seed-level results. A completed unfavorable seed may not be removed. Define malformed outputs, missing logits, truncation, refusal, partial checkpoints, engineering failures, rerun eligibility, and missing branches before execution.

## Smallest effect of interest

Freeze a meaningful threshold before C using:

- synthetic-calibration transfer magnitude;
- item and prompt-form reliability;
- practical change in normalized candidate probability;
- A/B branch and item variance;
- simulation-based power.

Null claims require equivalence intervals relative to that threshold, not merely nonsignificant tests.

## Ecological and adjusted analyses

The ecological analysis uses the natural selected source distribution.

The composition-adjusted analysis uses one frozen matching or weighting procedure based only on corpus observables such as topic clusters, subdivision, contributor class, genre, length, readability, quality, timestamp confidence, and event concentration.

Do not tune adjustment using model behavior. Report the four combinations of ecological/adjusted positive or null separately. Adjustment does not establish a pure era effect.

## Common post-training

For each branch:

`R_e,s = B(M_post,e,s) - B(M_pre,e,s)`

Differential response:

`Delta R_s = R_late,s - R_early,s`

Estimate both post-update endpoints and response to the common update. Classify erased, masked, persistent, transformed, or path-dependent under frozen criteria.

## Sealing and unsealing

Before C unsealing:

- all planned branches have terminal states;
- run IDs, model/data/evaluation hashes, and commit identities match;
- failed branches have frozen dispositions;
- analysis passes null-mock, synthetic, and permuted-map tests;
- source/era map is separate from routine summaries;
- no condition-linked C statistics have been inspected.

The analysis workflow is: completeness → manifest validation → frozen analysis → condition-map unsealing → report generation.

## Decision rule

C succeeds only if the frozen primary transport criterion is met with acceptable reliability and without a dominating capability, factual, register, generic-drift, or source-heterogeneity explanation.

C failure rejects CSTG for the tested scope. No source, era, item, estimator, threshold, or temporal-axis substitution is allowed afterward.