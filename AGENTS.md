# AGENTS.md

This file governs coding and research agents working in the ChronoPersona repository.

## Mission

Build a reproducible empirical test of whether controlled temporal adaptation changes language-model behavior beyond factual knowledge and surface-era imitation.

Optimize for scientific validity, falsifiability, and low-cost learning. Do not optimize for a dramatic result.

## Source-of-truth order

When instructions conflict, use this order:

1. Explicit instructions from the user in the active task.
2. The frozen experiment specification for the relevant run.
3. This file.
4. `docs/RESEARCH_PLAN.md`, `docs/PILOT_PROTOCOL.md`, and `docs/DATA_POLICY.md`.
5. Existing implementation conventions.

Do not silently resolve a material conflict. Record it in `docs/DECISIONS.md` or the relevant issue.

## Non-negotiable research rules

- Never describe an unrun experiment as evidence.
- Never describe exploratory findings as confirmatory.
- Never change a frozen evaluation, exclusion rule, or primary metric after seeing results. Create a new version instead.
- Preserve negative and null results.
- Keep temporal knowledge, temporal style, and temporal disposition conceptually and analytically separate.
- Treat corpus composition, timestamp quality, data leakage, base-model priors, and stochastic training variance as first-order confounds.
- Do not claim historical authenticity, population representativeness, stable personality, or causal mechanisms beyond what the design identifies.
- Do not claim novelty until a versioned literature map supports it.
- Do not use data with unclear redistribution or training rights merely because it is technically accessible.
- Never commit secrets, credentials, copyrighted raw corpora, private data, or model checkpoints.

## Experiment lifecycle

Every meaningful experiment moves through these states:

1. `design` — hypotheses, conditions, metrics, exclusions, and analysis are editable.
2. `frozen` — the specification and evaluation registry are immutable for this experiment ID.
3. `running` — only execution bugs may be fixed; substantive changes require a new experiment version.
4. `complete` — artifacts, deviations, failures, and results are recorded.

A run is not reproducible unless it records:

- experiment ID and committed configuration;
- repository commit SHA;
- environment or lock-file identity;
- base checkpoint identifier and revision;
- immutable data-manifest hashes;
- adaptation method and all hyperparameters;
- random seed;
- hardware and precision mode;
- evaluation-registry hash;
- generated artifact hashes;
- known deviations and failures.

## Data rules

Follow `docs/DATA_POLICY.md`.

Code must consume manifests rather than undisclosed local directory layouts. Each document must have provenance, timestamp semantics, license or rights status, source domain, content hash, token count, and deduplication identity before it is eligible for a frozen run.

Never infer a document's historical eligibility from file modification time alone.

## Evaluation rules

- Date-neutral disposition prompts must not contain explicit years, era names, dated events, or obvious period-specific lexical cues unless the item is explicitly a leakage control.
- Keep development prompts separate from frozen confirmatory prompts.
- Blind human raters to model condition and randomize response order.
- Record scorer model, revision, prompt, decoding settings, and calibration examples when model-based judging is used.
- Report item-level and seed-level variation, not only aggregate means.
- Analyze whether style cues explain apparent behavioral differences.
- Use effect sizes and uncertainty intervals. A low p-value alone is not a scientific conclusion.

## Engineering rules

- Python support begins at 3.11.
- Prefer the standard library for core configuration and manifest logic.
- Add dependencies only when they remove substantial implementation or correctness risk.
- Keep functions typed and deterministic where practical.
- Validate external inputs at boundaries and return actionable errors.
- Tests must cover both the valid path and important research-integrity failures.
- Do not hide failed checks, skipped samples, discarded runs, or scoring exceptions.
- Generated artifacts belong outside version control unless they are small, redistributable, and intentionally reviewed.

## Change workflow

Before changing code or design:

1. Identify the experiment or issue being advanced.
2. Inspect the relevant configuration and documentation.
3. State the smallest coherent change.
4. Implement only that scope.
5. Run the relevant validator and tests.
6. Update documentation when behavior or scientific meaning changes.
7. Report what was proven, what remains unverified, and any new risk.

Do not bundle literature work, data acquisition, training, evaluation redesign, and paper conclusions into one opaque change.

## Completion criteria

A task is complete only when:

- the requested artifact exists;
- relevant automated checks pass;
- documentation and configuration agree with implementation;
- no placeholder is presented as a measured result;
- limitations and remaining gates are explicit.

## Current project boundary

The repository is in Phase 0. The immediate objective is to qualify the research design, data sources, base model, and frozen pilot evaluation before expensive training. Large-scale training, polished paper claims, and public dataset release are out of scope until the pilot gates are satisfied.
