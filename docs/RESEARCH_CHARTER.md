# ChronoPersona Research Charter

**Status:** final research design v1.0  
**Design date:** 2026-08-18  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working title:** *From Archive to Policy: A Prospective Test of Cross-Source Temporal Generalization in Language Models*

## Goal

Build and execute a falsification-oriented program testing whether period-indexed naturalistic corpora induce a reproducible behavioral component that transports to a predesignated held-out source and persists through, or changes responses to, identical later post-training.

The decisive test is:

> Estimate an early-versus-late behavioral component from independent discovery sources A and B, freeze it, and prospectively test whether it predicts the corresponding contrast from sealed source C on unseen, date-neutral decisions.

Source C is not an optional replication. It determines whether the central CSTG claim survives. If C fails, CSTG is rejected for the tested sources, model, dose, windows, and evaluation domains. C may not be replaced after outcomes are available.

## Final novelty boundary

ProgressGym is the closest predecessor. It already continued-pretrained historical models on multi-source text spanning nine centuries, applied timeless instruction tuning, and used the resulting systems as historical value proxies. Weird Generalization, Time Capsules, ideological generalization, Alignment Pretraining, final-window pretraining, Synthetic Persona Pretraining, and point-in-time model projects occupy nearly every easier claim.

ChronoPersona therefore does **not** claim novelty from:

- constructing historical models;
- multi-source historical corpora;
- timeless post-training;
- measuring moral change;
- showing that one archive changes unrelated behavior;
- persistent pretraining-induced priors;
- path dependence by itself;
- or a decodable era/persona direction.

Its remaining contribution is the identification and prospective transport of an unengineered period-indexed treatment across naturalistic source families.

## Evidentiary sequence

1. **Measurement validity.** Build reliable date-neutral behavioral instruments with option, label, paraphrase, tokenizer, capability, factual, and register controls.
2. **Synthetic identifiability.** Demonstrate that the planned model, broad-update method, dose, and scorer recover a known latent rule from two disjoint synthetic domains into a third unseen domain.
3. **A/B discovery.** Estimate source-specific early-versus-late vectors and a frozen shared component from independent naturalistic sources A and B.
4. **Prospective C confirmation.** Test the frozen A/B component on a predesignated sealed source C and sealed confirmation evaluation.
5. **Composition adjustment.** Separate ecological transport from transport remaining after a prespecified balance or weighting procedure.
6. **Training-path consequences.** Apply common neutral continuation and identical SFT; classify erasure, masking, persistence, transformation, or path dependence.
7. **Optional mechanisms.** Begin only after source-C behavioral transport.

The optional public point-in-time checkpoint audit is observational and nonblocking.

## Estimands

For source family `s`:

`tau_s = B(M_late,s) - B(M_early,s)`

Discovery sources estimate a frozen component:

`g_AB = G(tau_A, tau_B)`

The estimator `G`, score orientation, thresholds, exclusions, and confirmation evaluation are frozen before source C is unsealed.

Report two distinct estimands:

- **Ecological CSTG:** transport under each source's natural historical composition.
- **Composition-adjusted CSTG:** transport after prespecified balancing or weighting over observed corpus properties.

An ecological effect that disappears after adjustment is a transportable period-indexed composition effect, not evidence for a coherent latent historical disposition.

## Claim language

- A within-source contrast is a **source-specific temporal effect**.
- Aligned A/B contrasts are **preliminary cross-source temporal agreement**.
- Only successful prospective C prediction is **CSTG across the tested sources**.
- A **temporal prior** additionally requires composition adjustment, capability/factual/register controls, neutral continuation, and common post-training or path-dependence analysis.
- A **temporal representation** additionally requires held-out prediction and causal intervention after factual and stylistic residualization.
- “Historical personality” is informal motivation only.

## Non-goals

Do not claim that a branch is a person from an era, an average citizen, a representative population, humanity's values, or a complete culture. Do not rank periods morally. Do not rescue a failed C test by changing source, era, item set, estimator, or axis. Do not begin mechanism fishing before behavioral confirmation.

## Scoped modules

- [`charter/01-novelty-scope.md`](charter/01-novelty-scope.md)
- [`charter/02-measurement-calibration.md`](charter/02-measurement-calibration.md)
- [`charter/03-discovery-confirmation.md`](charter/03-discovery-confirmation.md)
- [`charter/04-posttraining-mechanisms.md`](charter/04-posttraining-mechanisms.md)
- [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md)
- [`CLAIMS_TABLE.md`](CLAIMS_TABLE.md)

## Current boundary

No evidence-bearing model run has occurred. Source roles, era windows, model checkpoint, dose, evaluation confirmation partition, meaningful-effect threshold, and prospective estimator remain unfrozen. External spend authorization remains C$0. Scientific execution resumes only after bounded rights-qualified source evidence and measured local model/compute evidence exist.