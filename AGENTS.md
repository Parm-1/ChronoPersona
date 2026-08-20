# AGENTS.md

This file contains recurring repository rules for coding and research agents. The detailed scientific design lives in [`docs/RESEARCH_CHARTER.md`](docs/RESEARCH_CHARTER.md).

## Mission

Build ChronoPersona into a rigorous, resource-aware test of **Cross-Source Temporal Generalization (CSTG)**:

> Do matched early-versus-late corpus interventions induce a shared component of date-neutral model behavior that replicates across independent source families, predicts a held-out source, and changes response to identical later post-training?

A temporal prior is an interpretation reserved for evidence that passes the CSTG controls. Do not optimize for a positive result.

## Instruction order

When instructions conflict, use:

1. the user's active instruction;
2. a frozen experiment or run specification;
3. this file;
4. `docs/RESEARCH_CHARTER.md`;
5. `docs/DATA_POLICY.md`, `docs/PILOT_PROTOCOL.md`, and `PLAN.md`;
6. existing implementation conventions.

Record material conflicts in `docs/DECISIONS.md`. Preserve the user's layered instruction architecture; do not replace it with one oversized project handbook.

## Operating posture

Act as research project manager, principal research engineer, evaluation architect, reproducibility owner, and evidence integrator.

Before changing anything:

1. inspect repository state, applicable instructions, relevant plans, and existing artifacts;
2. identify one write-active deliverable;
3. state the smallest coherent change;
4. preserve useful prior work;
5. run relevant validation;
6. update project state and decisions when scientific meaning changes.

Use bounded, read-heavy subagents for literature verification, model access, license review, statistical review, leakage review, code review, and run-completeness review. Keep one write owner per artifact. A subagent review is internal review, not independent peer review.

## Evidence language

Label material findings as:

- **Observed**
- **Reported by source**
- **Inferred**
- **Unverified**

Never invent access, results, citations, model revisions, hardware, completed runs, or validation. Never describe smoke tests, development items, or public-checkpoint correlations as causal paper evidence.

## Scientific rules

- Keep temporal knowledge, temporal register, residual temporal signature, source-specific effects, CSTG, temporal path dependence, and temporal representation distinct.
- Require common starting weights for causal claims.
- Require at least two independent source families for exploration and a third source family held out from hypothesis construction for confirmation.
- Treat source culture, topic composition, training dose, insertion position, model scale, capability, factual leakage, lexical leakage, direct imitation, and seed variance as first-order alternatives.
- Synthetic Identifiability Calibration is mandatory before interpreting a naturalistic null.
- Public dated checkpoints are observational infrastructure, not causal replicas of the naturalistic intervention.
- Freeze the evaluation, scoring, primary contrasts, exclusion rules, and meaningful-effect threshold before confirmatory outputs.
- Treat the independently trained branch or seed as the experimental unit.
- Preserve negative results, failed seeds, malformed outputs, deviations, and exclusions.
- Allow at most one predeclared rescue for a failed major gate.
- Do not begin substantial mechanism work before behavioral CSTG replicates.
- Never claim that a model is an average person from an era or that later periods are more moral, rational, safe, liberal, calibrated, or technically sophisticated.

## Resource rules

Follow [`docs/RESOURCE_CONSTRAINTS.md`](docs/RESOURCE_CONSTRAINTS.md).

The default authorization envelope is:

- local-only work;
- CAD $0 external compute spend;
- one training job at a time;
- no substantial training before measured memory and throughput benchmarks;
- no naturalistic interpretation before synthetic calibration succeeds;
- parameter-efficient methods for smoke work only unless their scientific adequacy is separately justified;
- full-weight training for the headline causal claim only after the evidence and resource gates pass.

Do not rent compute, purchase hardware, accept paid licenses, or start a branch set whose projected cost has not been measured and approved.

## External-action boundaries

Continue safe, reversible, local work without repeated permission requests. Do not, without explicit user authorization:

- rent or purchase compute;
- accept paid licenses;
- change repository visibility again;
- push or publish branches outside the requested GitHub workflow;
- release models, datasets, or raw corpora;
- register a study;
- contact researchers;
- create external accounts;
- recruit human participants;
- perform irreversible external actions.

### Standing GitHub delivery authorization

The user has authorized agents working on this repository to stage scoped
changes, create focused local commits, push feature branches, open or update
draft pull requests, and address CI or review feedback when a coherent tested
deliverable is ready. Do not request routine confirmation for those actions.

This standing authorization does not include merging pull requests, force
pushing, deleting remote branches, creating releases, changing repository
visibility again, spending money, or publishing models, datasets, or raw
corpora.
Those actions still require explicit user authorization.

## GitHub collaboration

Use public `Parm-1/ChronoPersona`, one gate per draft PR. Public visibility is
an Actions-delivery decision, not a license grant or authorization to publish
models, datasets, or raw corpora. Bind review to the
exact base/head and omitted local state; a material commit is stale. Review is
advisory and CI does not prove CSTG, license, or publication claims. Standing
delivery authority still excludes the actions above.

## Experiment lifecycle

Every experiment uses one of these states:

1. `design`
2. `frozen`
3. `running`
4. `complete`
5. `failed`

A run is not reproducible unless it records:

- immutable run ID;
- repository commit;
- complete configuration and environment identity;
- model and tokenizer identifiers and revisions;
- base and insertion checkpoint;
- data and evaluation hashes;
- objective, optimizer, schedule, token budget, seeds, hardware, and precision;
- logs, raw metrics, outputs, checkpoint identities, failures, exclusions, and artifact hashes.

No silent fallback to another model, tokenizer, prompt, precision, device, source, evaluation subset, or scoring method.

## Data and evaluation

Follow `docs/DATA_POLICY.md` and the domain-exposure matrix once created.

- Use timestamp-native records for the causal era-window experiment; crawl time is not silently equivalent to publication time.
- Consume immutable manifests rather than undisclosed local directories.
- Record provenance, rights, authorship confidence, timestamp semantics, transformations, hashes, token counts, deduplication identity, and exclusion reasons.
- Keep persisted repository, manifest, checkpoint, and artifact paths canonical and portable across POSIX and Windows; reject traversal, normalization aliases, case-insensitive collisions, reserved names, symlinks, and root escape.
- Require `synthetic_fixture` and authorship provenance to agree, and validate exact manifest-bound authorization before opening non-fixture source-C content.
- Keep primary evaluation task families outside direct adaptation exposure.
- Use complete-continuation conditional log probabilities as the primary instrument unless a frozen design justifies another scorer.
- Counterbalance option order and labels, use paraphrases, inspect tokenizer boundaries, and retain token-level diagnostics.
- Generated explanations are secondary evidence and do not determine the primary score.
- Blind condition labels during scoring.

## Engineering

- Support Python 3.11 and later.
- Prefer typed, deterministic, dependency-light foundations.
- Keep notebooks exploratory; move final logic into tested modules.
- Fail loudly on partial datasets, hash mismatches, absent checkpoints, missing logits, truncation, malformed outputs, or incomplete branch sets.
- Test valid paths and research-integrity failures.
- Keep generated corpora, checkpoints, model weights, private data, and large run artifacts out of Git unless intentionally reviewed and legally redistributable.
- Sandbox executable security evaluations with no unnecessary network, strict resource limits, filesystem isolation, and cleanup.

## Progress reporting

Every material report includes:

- **Decision**
- **Evidence**
- **Artifacts**
- **Validation**
- **Risks**
- **Next write-active deliverable**

Activity is not progress unless it creates evidence or a reusable artifact.

## Code Review Rules

- Block weakened run identity, weights/holdouts, source authorization,
  provenance, containment, fail-loud behavior, secrets/private data, silent
  fallback, hidden exclusion, or claims above evidence.
- Require exact-head integrity tests and honest evidence labels. Review cannot
  authorize spending, release, registration, or outreach.

## Current boundary

The repository remains in Stage 0. The development content-integrity gate has
passed; local model acquisition, bounded engineering training, the verified
tokenizer boundary, and the deterministic registry scorer have completed their
scoped engineering gates. The next real-content qualification gate is
externally blocked.

The first frozen tiny-LoRA v0 control is preserved as a pre-backward numeric
failure. Its single versioned v1 attention-policy rescue passed the bounded
five-step control/interruption/resume engineering gate with exact semantic
state equality; do not reopen either profile or infer scientific training
adequacy. The exact Pythia tokenizer boundary path is Target Verified through
the shared hash-verified snapshot loader. The bounded repeated registry scorer
also passed with byte-identical deterministic outputs, but four development
items were paraphrase-direction inconsistent. The active local gate is the
`development-v1` measurement-coherence screen: blind internal semantic lock,
dependency-light implementation, exact-head CI, and two clean-head tokenizer
audits passed at `fb8cff1`. The next gate is its separately versioned scorer
profile and exact-head CI. Do not deserialize the model or inspect v1 logits
before that gate passes. Evidence-bearing naturalistic execution still
requires rights-qualified, historically version-bounded A/B samples and an
explicitly authorized held-out source-C review packet. Paid compute, public
model/data release, another repository-visibility change, and requester-pays
retrieval remain outside the active gate.
