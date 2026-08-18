# Charter Module 01 — Novelty, Scope, and Competing Explanations

## Prior work that constrains the claim

The Stage 0 literature audit treats the following as occupied territory:

- **ProgressGym** (`arXiv:2406.20087`): multi-source historical corpora spanning nine centuries, historical continued pretraining, timeless instruction tuning, and historical value-oriented model evaluation. Its reported limitations include temporal source-composition change and uncertainty about whether historical values were actually injected.
- **Weird Generalization / brittleness replications:** historical cues can recruit broad behavior, but effects depend strongly on model, data, and context.
- **Time Capsules:** naturalistic decade-indexed fiction can produce era-associated social outputs within one culturally proximal source family.
- **Innocuous-Seeming Data, Latent Ideology:** ordinary-looking narrow data can induce broader worldview changes.
- **Alignment Pretraining and final-window work:** pretraining composition and late training windows can change later behavior and response to identical post-training.
- **Synthetic Persona Pretraining and persona-vector work:** authored personas and internal persona directions can be installed or decoded.
- **DatedGPT, PIT, ChronoGPT, TypewriterLM:** historical and point-in-time model construction is established infrastructure.

The defensible novelty statement is therefore:

> Prior work shows that individual historical, ideological, or engineered corpora can induce broad behavioral changes. ChronoPersona tests whether an unengineered period-indexed variable can be identified through convergent effects across independent naturalistic discovery environments and prospectively transported to an untouched source family.

Do not defend novelty by saying that no paper combines a checklist of controls. The contribution is the identification and prospective transport of a latent temporal treatment.

## Causal scope

What is randomized is assignment of identical starting models to selected early- or late-period corpora under a common training procedure.

Permitted causal statement:

> Random assignment to the selected early versus late period-indexed corpora caused a reproducible behavioral difference.

Prohibited extrapolation:

> History itself, an era's population, or an average historical citizen caused or is represented by the difference.

The initial scope is English-language text, selected digital archives, selected modern windows, one base-model family and dose, and frozen date-neutral evaluation domains.

## Ecological versus adjusted questions

**Ecological CSTG** includes real period changes in subjects, contributors, genres, institutions, editorial practices, discourse priorities, and language.

**Composition-adjusted CSTG** asks what remains after balancing or weighting prespecified observed properties such as topic, subdivision, contributor class, genre, length, readability, quality, and timestamp confidence.

Possible outcomes:

- Ecological positive, adjusted positive: strongest evidence against major observed-composition explanations.
- Ecological positive, adjusted attenuated: shared effect combines composition drift with a residual component.
- Ecological positive, adjusted null: source composition transports; do not claim a latent historical disposition.
- Both null: no CSTG evidence at tested scope.

Adjustment never recovers a perfectly pure era effect; unobserved composition remains possible.

## Live competing explanations

Every experiment must state which mechanisms it distinguishes and what remains equivalent:

- M0 noise;
- M1 prompt, label, option, or tokenizer artifact;
- M2 temporal factual knowledge;
- M3 temporal register;
- M4 general capability change;
- M5 total training dose;
- M6 data quality or readability;
- M7 source culture;
- M8 topic composition;
- M9 contributor-population change;
- M10 direct imitation;
- M11 generic continued-pretraining drift;
- M12 final-window recency;
- M13 shared temporal covariance;
- M14 role or channel attribution;
- M15 synthetic or teacher provenance;
- M16 post-training path dependence;
- M17 model-scale boundary.

## Population and archive limits

Historical branches represent surviving textual archives filtered by authorship, publication, preservation, digitization, institutional access, licensing, and project selection. They are not historical human subjects or representative populations.

Use “source-general across the tested source families,” not “source-independent,” “universal,” or “the zeitgeist” as an established fact.