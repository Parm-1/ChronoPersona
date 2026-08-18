# Novelty Audit — Design v1.0

**Decision date:** 2026-08-18  
**Status:** novelty survives only under the prospective source-transport formulation

## Closest predecessor: ProgressGym

ProgressGym (`arXiv:2406.20087`, NeurIPS 2024 Datasets & Benchmarks Spotlight) is materially closer than the initial ChronoPersona map acknowledged. It uses historical text spanning nine centuries and multiple source classes, continued-pretrains historical models including Llama-3 8B and 70B families, applies a timeless instruction-tuning stage, and evaluates historical/value-oriented behavior.

Its authors explicitly identify temporal source-composition change, limited cultural representativeness, and uncertainty about whether historical values were successfully injected as limitations.

Consequences for ChronoPersona:

- historical model construction is not novel;
- multi-source historical corpora are not novel;
- timeless instruction tuning after historical training is not novel;
- using historical models as value proxies is not novel;
- measuring apparent moral progress is not the contribution.

ProgressGym's limitations sharpen the remaining identification problem: distinguish a source-general period-indexed component from source composition and test it prospectively on an untouched naturalistic source.

## Other occupied claims

- **Weird Generalization and Inductive Backdoors / brittle replications:** historical cues can cause broad historical answers, but effects are scale-, model-, data-, framing-, and context-dependent.
- **Fine-Tuned LLMs Are “Time Capsules”:** natural fiction from different decades can produce era-associated social portrayals; one source family and culturally proximal outcomes remain important distinctions.
- **Innocuous-Seeming Data, Latent Ideology:** ordinary-looking domain corpora can induce unrelated ideological shifts without obvious capability loss.
- **Alignment Pretraining:** explicit pretraining content can install behavioral priors that are dampened yet survive post-training.
- **Similar Models Learn Differently / final-window work:** a common checkpoint plus different late pretraining can alter response to identical later SFT or preference/RL updates.
- **Synthetic Persona Pretraining and persona-feature/vector work:** authored personas can be installed and internal persona directions can be decoded or controlled.
- **Data-attribution and channel work:** semantically related natural documents may remain descriptive rather than become default policy; formatting, target-token exposure, loss masking, and synthetic instruction-response structure may matter.
- **DatedGPT, PIT, ChronoGPT, TypewriterLM:** point-in-time, cumulative, adapted, and historical-only model families are infrastructure and observational baselines.

## Remaining contribution

The strongest defensible statement is:

> Prior work shows that individual historical, ideological, or engineered corpora can induce broad behavioral changes. We test whether an unengineered period-indexed variable can be identified through convergent effects across independent naturalistic discovery environments and prospectively transported to an untouched source family.

Operationally:

1. Randomly assign common starting models to early/late corpora from A and B.
2. Estimate source-specific temporal vectors and one frozen shared component.
3. Predesignate and seal C before inspecting behavioral outcomes.
4. Freeze estimator, direction, thresholds, exclusions, and confirmation evaluation.
5. Test whether A/B predicts C.
6. Reject CSTG if C fails; do not substitute another source.
7. Separately report ecological and composition-adjusted transport.

The novelty is not that no previous paper combines a checklist. It is the prospective transport test for a naturally co-occurring latent treatment.

## Null-result publishability

Publishable outcomes include:

- successful calibration followed by a tight naturalistic null;
- A/B discovery that fails prospective C transport;
- source-specific far transfer;
- ecological transport explained by composition adjustment;
- naturalistic text that fails to globalize unless transformed into a particular training channel;
- an intermediate-state effect erased or masked by common post-training;
- evidence that historical models are unreliable historical-human proxies.

## Rejection criteria

The novelty claim fails if prior work is found that performs equivalent common-weight naturalistic A/B discovery, freezes a temporal component, and prospectively predicts a predesignated held-out source on unseen date-neutral decisions.

## Current judgment

**Novel enough after redesign.**

The claim ceiling remains source-general across the tested sources, model, dose, windows, and domains. It is not universal, population-representative, or proof of a singular historical personality.