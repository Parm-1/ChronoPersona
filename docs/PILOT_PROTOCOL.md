# Pilot Protocol

## Purpose

The pilot answers one decision question:

> Is there enough reproducible signal, after basic controls, to justify a larger multi-period ChronoPersona study?

It is not designed to establish the final paper claim. Its job is to falsify weak versions of the idea cheaply and expose failures in corpus construction, training, and evaluation.

## Design

The machine-readable starting point is `configs/pilot.toml`.

Conditions:

1. `base-model-control` — the unadapted checkpoint.
2. `temporal-2008` — continued pretraining on a corpus eligible through 2008.
3. `temporal-2024` — continued pretraining on a matched corpus eligible through 2024.
4. `date-shuffled-control` — matched adaptation exposure with the temporal assignment disrupted.

Two adaptation seeds are the minimum smoke design. More seeds are required before inferential claims.

The initial configuration assigns 10 million tokens to each adapted condition. This is a planning value, not a commitment. A measured throughput and memory benchmark must precede training, and any change creates a new configuration version.

## Model-selection gate

Select the pilot base model only after documenting:

- architecture and parameter count;
- original training cutoff and known data contamination risks;
- tokenizer suitability for all corpora;
- license and redistribution constraints;
- support for deterministic local inference;
- measured adaptation memory and throughput;
- whether parameter-efficient and full-parameter adaptation are feasible.

A small decoder model is acceptable for pipeline and effect detection. Parameter-efficient adaptation may be used in the pilot, but a paper-level claim must either replicate key effects with another adaptation regime or explicitly limit its scope.

## Corpus gate

Before freezing the pilot:

- every record has the required manifest fields from `DATA_POLICY.md`;
- token totals are matched within the frozen tolerance;
- source-domain weights use the same target mixture;
- near-duplicate clusters do not cross train and evaluation boundaries;
- a manual timestamp audit is completed on a stratified sample;
- future-entity and retrospective-reference leakage tests are recorded;
- licenses and permitted uses are documented;
- no corpus is represented only by data that appeared online long after the claimed period.

Failing this gate blocks training. Lowering the standard after seeing model outputs is prohibited.

## Evaluation freeze

The pilot registry must be frozen before trained outputs are generated. It should include:

- cutoff-sensitive knowledge checks;
- post-cutoff leakage checks;
- a small set of date-neutral disposition constructs;
- style and named-entity cue diagnostics;
- general-capability and response-quality controls;
- explicit-year prompting baselines;
- scoring rubrics and directionality;
- development versus confirmatory designation.

Item writers should not know which condition is expected to “win.” Human ratings must be blinded and response order randomized.

## Execution sequence

1. Validate the committed configuration.
2. Resolve and hash the base checkpoint revision.
3. Resolve and hash all data manifests.
4. Record the environment, hardware, precision mode, and code revision.
5. Run a short training benchmark and predict total cost from measured throughput.
6. Execute each condition and seed under the same stopping rule.
7. Generate outputs with identical decoding settings.
8. Score without exposing condition labels.
9. Unblind only after scoring artifacts are immutable.
10. Run the preregistered analysis.
11. Publish a decision report including failures and nulls.

## Mandatory sanity checks

- The later condition should show more post-2008 knowledge than the earlier condition. If it does not, the intervention may be too weak or the evaluation invalid.
- The earlier condition must not display unexplained high confidence on post-cutoff items.
- General capability differences must be small enough that disposition comparisons remain interpretable.
- Date-shuffled adaptation must reveal whether “any additional training” creates the apparent effect.
- Explicit-year prompting must establish the baseline achievable without adaptation.
- Style-only classifiers and style-normalized rescoring must test whether surface cues dominate.

These checks diagnose the design. They are not success metrics to optimize against repeatedly.

## Go criteria

Expansion is justified only when all of the following are true:

- manifests and timestamps survive audit;
- the pipeline is reproducible from a clean environment;
- intervention checks show a measurable temporal information difference;
- primary scoring has acceptable human or criterion validity;
- effects or informative nulls are reasonably stable across the smoke seeds;
- no single obvious confound explains the main pattern;
- the projected confirmatory compute and annotation cost is affordable;
- the literature map still supports a differentiated contribution.

A disposition effect is not required for every construct. A robust null result can justify expansion when the intervention was strong and the measurement was sensitive.

## No-go or redesign criteria

Stop or redesign when:

- reliable temporally bounded corpora cannot be assembled legally;
- timestamp leakage cannot be reduced to an auditable level;
- adaptation fails to move temporal knowledge;
- results reverse arbitrarily across seeds;
- capability degradation explains the apparent behavioral changes;
- scorers primarily react to tone, verbosity, or named entities;
- explicit role prompting reproduces every claimed effect at much lower cost;
- pilot cost implies that adequate seeds and controls are infeasible;
- novelty collapses after literature review.

## Required pilot artifacts

- frozen configuration;
- corpus manifests and audit report;
- evaluation registry and hash;
- environment and hardware manifest;
- training logs for every seed and condition;
- checkpoint or adapter hashes;
- generation settings and raw outputs;
- blinded scoring artifacts;
- analysis notebook or script;
- deviations log;
- concise go, redesign, or stop decision.

No result should depend on an untracked local file or a hand-edited spreadsheet.
