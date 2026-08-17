# Project State

**Last updated:** 2026-08-17  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, and compute audit**

The novelty gate, static model-artifact audit, dependency-light scorer, and first development evaluation registry are complete. Stage 0 remains open because local hardware, real-model scoring, source feasibility, calibration thresholds, and measured training cost are not yet qualified.

## Current write-active deliverable

**Manifest-approved Transformers scoring provider and tokenizer audit**

The next implementation should:

- load only model-manifest artifacts whose license, revision, and code gates permit execution;
- never enable custom remote code implicitly;
- prepare exact prompt/continuation boundaries for every registry candidate;
- calculate continuation token log probabilities at the recorded positions;
- expose a tokenizer-only audit that requires no weight download;
- produce deterministic score artifacts through the existing scorer;
- preserve all boundary, truncation, malformed-output, and out-of-memory failures;
- remain separate from evidence-bearing interpretation.

## Parallel external evidence needed

**Local resource and immutable Pythia benchmark**

The repository contains a safe protocol and scripts, but this evidence can only be produced on the user's machine:

- exact RTX 2060 VRAM variant;
- free RAM and disk;
- CUDA, driver, Python, Torch, and Transformers versions;
- immutable Pythia 1B loading time, peak RAM/VRAM, and logits throughput;
- later, a tiny continued-pretraining benchmark.

## Latest verified evidence

### Repository milestones

- PR #10 merged the CSTG redesign at `b2a18b050e801d7138a0a1babc7c94cc1d83e0ac`.
- PR #11 merged the primary-source novelty audit at `32d2a37fa02b65155c38df9df443c565d8d1b319`.
- PR #12 merged the model artifact and guarded benchmark architecture at `33378aae095ac8af7be6fb5b142fa2d3afb137ba`.
- The project is novel enough only under the CSTG design centered on frozen prediction of held-out source C.
- No evidence-bearing temporal adaptation experiment has run.
- The naturalistic pilot remains in `design` with an intentionally unfrozen zero token budget.

### Evaluation implementation

- `src/chronopersona/evaluation.py` loads, validates, describes, and hashes JSONL registries.
- `src/chronopersona/scoring.py` implements complete-continuation total log likelihood, mean-token diagnostics, semantic-pole normalization, stable pairwise probabilities, one calibrated alternative, paraphrase aggregation, token-level outputs, and deterministic output hashing.
- `src/chronopersona/tokenization.py` requires an exact prompt prefix, explicit whitespace boundary, no truncation, and recorded continuation logit positions.
- `evaluations/schema/item-v1.schema.json` defines the structural item format.
- `evaluations/registry/development-v0.jsonl` contains twelve items and twenty-four forms: six evidence-integration and six procedural-trade-off items.
- `docs/EVALUATION_SPEC.md` defines the measurement and freeze protocol.
- `evaluations/reviews/development-v0-internal.md` records the first internal review and rejects the current set for freezing.
- CI validates the pilot, model manifest, development registry, and tests on Python 3.11 and 3.12.

### Evaluation review findings

- No explicit temporal cue was found in development-v0 prompts or candidates.
- Candidate display order is counterbalanced and scoring is pole-normalized.
- Several evidence-integration items may exhibit capability ceilings because one continuation is epistemically stronger.
- Several procedural scenarios have asymmetric consequences that may bias the pole independent of the intended construct.
- The privacy item carries familiar human-domain moral salience.
- The punishment/rehabilitation item has material valence imbalance and cannot be frozen in its current form.
- Dissent tolerance and transparency versus secrecy are absent.
- Tokenizer matching, direct exposure, contamination, and human criterion validity remain unresolved.
- Development-v0 is suitable for boundary, order, ceiling, and paraphrase diagnostics only; it is not evidence-bearing.

### Model-artifact findings

- DatedGPT is the intended first observational family after model-weight license and immutable-revision resolution.
- PIT's inspected public checkpoint is a custom-code 4B float32 artifact around 17.8 GB and is not the default local path.
- ChronoGPT, TypewriterLM, and Kairos remain separate boundary cases.
- OLMo 2 1B original stage-1 step 23,100 remains the scientifically preferred causal starting point, provisional.
- Pythia 1B deduped step 20,000 remains the operational fallback and second-family candidate, provisional.
- The immutable final Pythia 1B deduped artifact is the first approved local loading/logits benchmark only.
- A conventional one-billion-parameter full-weight AdamW run can exceed 16 GB before useful activation and batch memory.

### Dose implication

- Ten million intervention tokens are only about 0.02% of prior exposure at the candidate OLMo/Pythia insertion points.
- The old ten-million-token planning value is not retained as a credible headline dose.
- The token budget remains zero until measured throughput and synthetic dose-response evidence justify a frozen value.

## Current decisions

- **Novelty:** `novel enough under current redesign`.
- **Primary confirmation:** frozen source-C prediction; A/B agreement is exploratory.
- **Public observational primary:** DatedGPT base family after license/revision resolution.
- **Scientific causal primary:** OLMo 2 1B original stage-1 step 23,100, provisional.
- **Operational fallback:** Pythia 1B deduped step 20,000, provisional.
- **Primary evaluation metric:** complete-continuation total-log-likelihood margin.
- **Diagnostic metric:** mean-token-log-likelihood margin.
- **Score direction:** semantic reference pole; not candidate order and not a moral ranking.
- **Calibration:** one alternative margin is supported in code but its baseline is not designed or frozen.
- **Registry status:** development-v0; explicitly rejected for freezing.
- Generated explanations cannot determine the primary outcome.
- Quantized weights cannot determine the primary likelihood result without unquantized equivalence evidence.
- A fresh optimizer at an intermediate checkpoint is a declared intervention.
- Synthetic Identifiability Calibration is mandatory before interpreting a naturalistic null.
- The provisional naturalistic windows remain 2012-01-01 through 2013-12-31 and 2018-01-01 through 2019-12-31, subject to data-only selection.
- The headline causal result should not rely on PEFT alone.
- At most one predeclared rescue is permitted per failed major gate.
- No external compute spend is authorized.

## Resource constraints

### Reported hardware

- Current machine: RTX 2060 and 16 GB RAM.
- Possible borrowed machine: RTX 5070 and 32 GB RAM.
- Exact GPU variants, VRAM, free disk, CPU, runtime versions, and sustained throughput remain unmeasured.
- Borrowed-machine availability is not assumed.

### Binding operating limits

- Default external-compute budget: CAD $0.
- No rental, purchase, paid license, or external account without explicit user authorization.
- One training job at a time.
- Benchmark before committing token budgets.
- Do not launch the twelve-branch naturalistic set until calibration, cost, storage, and run-completeness gates pass.
- Do not download a model unless its license, immutable revision, storage margin, and code path pass the manifest gates.
- Use the borrowed machine only after access is confirmed and the run has a measured purpose.

## Open blockers

1. Local resource audit and immutable Pythia benchmark.
2. Manifest-approved model provider and real tokenizer boundary audit.
3. DatedGPT model-weight license and four immutable revisions.
4. Original OLMo step-23,100 file manifest, hashes, and current-code loading path.
5. Immutable Pythia step-20,000 revision and optimizer-reset decision.
6. Tiny full-weight/PEFT continued-pretraining benchmark.
7. Timestamp-native corpus continuity, source independence, rights, and authorship provenance.
8. Domain exposure and contamination searches.
9. Development-v0 real-model reliability, ceiling, order, and paraphrase results.
10. Revision or replacement of valence- and consequence-asymmetric items.
11. Addition of dissent and transparency constructs.
12. Meaningful-effect threshold and null-equivalence interval.
13. Synthetic-calibration latent policies, dose, and seed count.
14. Confirmatory seed count and common post-training recipe.

## Current risk judgment

The evaluation code now fails closed on the most dangerous mechanical errors, but construct validity remains the larger risk. Passing schema and token checks does not make an item a valid measure. Real-model development results must be used to reject ceiling-prone, paraphrase-unstable, and wording-sensitive items before expansion.

The dominant execution risk remains full-weight memory and dose. An inference-capable one-billion-parameter model may still be an impractical full-weight training model on the current machine.

The dominant scientific risk remains source covariance. The project succeeds only if a component estimated from A and B predicts C under a frozen threshold and source heterogeneity remains subordinate to the shared component.

## Exact next action

Implement the manifest-approved Transformers provider and tokenizer-only registry audit. In parallel, begin the timestamp-native source and domain-exposure audit, which does not require model weights or paid compute.
