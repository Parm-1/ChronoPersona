# Project State

**Last updated:** 2026-08-17  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, and compute audit**

The novelty gate, static model-artifact audit, dependency-light scorer, first development registry, and manifest-gated real-model adapter are complete. Stage 0 remains open because local hardware, real-model scoring, source feasibility, calibration thresholds, and measured training cost are not yet qualified.

## Current write-active deliverable

**Timestamp-native source, rights, independence, and domain-exposure audit**

The next repository work should:

- audit at least three candidate source families from primary steward documentation;
- distinguish publication, revision, upload, crawl, and archive-capture time;
- record exact license, attribution, research-use, training-use, and redistribution status;
- assess continuous early/late coverage, human-authorship confidence, duplicate/revision burden, event concentration, and extractable token volume;
- test whether source families are genuinely independent rather than different URLs over shared upstream text;
- classify every source/evaluation pair as direct, structurally related, indirect, plausibly absent, or unknown;
- identify a provisional A/B/C assignment or reject the current source architecture;
- avoid downloading bulk corpora before feasibility, rights, and storage gates pass.

## Parallel external evidence needed

**Local resource, tokenizer, and immutable Pythia benchmark**

The repository contains safe protocols and scripts, but this evidence can only be produced on the user's machine:

- exact RTX 2060 VRAM variant;
- free RAM and disk;
- CUDA, driver, Python, Torch, and Transformers versions;
- Pythia and OLMo tokenizer boundary audits over development-v0;
- immutable Pythia 1B loading time, peak RAM/VRAM, and logits throughput;
- the first deterministic Pythia development score;
- later, a tiny continued-pretraining benchmark.

## Latest verified evidence

### Repository milestones

- PR #10 merged the CSTG redesign at `b2a18b050e801d7138a0a1babc7c94cc1d83e0ac`.
- PR #11 merged the primary-source novelty audit at `32d2a37fa02b65155c38df9df443c565d8d1b319`.
- PR #12 merged the model artifact and guarded benchmark architecture at `33378aae095ac8af7be6fb5b142fa2d3afb137ba`.
- PR #13 merged the complete-continuation scorer and development-v0 registry at `a19662a279d02b362b34437fcc52e1290a399696`.
- The project is novel enough only under the CSTG design centered on frozen prediction of held-out source C.
- No evidence-bearing temporal adaptation experiment has run.
- The naturalistic pilot remains in `design` with an intentionally unfrozen zero token budget.

### Real-model adapter

- `src/chronopersona/artifact_policy.py` defines operation-specific tokenizer and model-score gates.
- Tokenizer/model execution requires an immutable 40-character Hub commit, verified model license, standard `owner/name` repository, and no custom remote code.
- Model scoring additionally requires explicit `benchmark-ready` status.
- `src/chronopersona/tokenizer_audit.py` deterministically audits every prompt/candidate boundary, token count, prediction position, and failure without model weights.
- `src/chronopersona/transformers_provider.py` provides manifest-gated tokenizer loading and unquantized causal-LM scoring. It never enables remote code or quantization.
- Tokenizer-only dependencies are separated from the PyTorch model stack.
- `scripts/audit_registry_tokenizer.py` and `scripts/score_registry_transformers.py` default to no-network plans and require separate `--execute` and `--allow-download` flags.
- `docs/TRANSFORMERS_SCORING_PROTOCOL.md` defines the local sequence, failure policy, and interpretation boundary.
- Unit tests verify operation gates, no-network plans, blocked execution before optional imports, exact continuation-logprob selection, deterministic tokenizer audits, and visible boundary failures.

### Evaluation implementation

- `src/chronopersona/evaluation.py` loads, validates, describes, and hashes JSONL registries.
- `src/chronopersona/scoring.py` implements complete-continuation total log likelihood, mean-token diagnostics, semantic-pole normalization, stable pairwise probabilities, one calibrated alternative, paraphrase aggregation, token-level outputs, identical pairwise prompt contexts, and deterministic output hashing.
- `src/chronopersona/tokenization.py` requires an exact prompt prefix, explicit whitespace boundary, no truncation, and recorded continuation logit positions.
- `evaluations/registry/development-v0.jsonl` contains twelve items and twenty-four forms: six evidence-integration and six procedural-trade-off items.
- `evaluations/reviews/development-v0-internal.md` rejects the current set for freezing.
- CI validates the pilot, model manifest, development registry, and tests on Python 3.11 and 3.12.

### Evaluation review findings

- No explicit temporal cue was found in development-v0 prompts or candidates.
- Candidate display order is counterbalanced and scoring is pole-normalized.
- Several evidence-integration items may exhibit capability ceilings because one continuation is epistemically stronger.
- Several procedural scenarios have asymmetric consequences that may bias the pole independent of the intended construct.
- The privacy item carries familiar human-domain moral salience.
- The punishment/rehabilitation item has material valence imbalance and cannot be frozen in its current form.
- Dissent tolerance and transparency versus secrecy are absent.
- Real-tokenizer matching, direct exposure, contamination, and human criterion validity remain unresolved.
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
- **Registry status:** development-v0; explicitly rejected for freezing.
- **Real-model policy:** immutable revision, verified license, no remote code, no quantization, and operation-specific approval.
- **Tokenizer policy:** explicit `none` or `bos`; choose and freeze from native convention and development reliability, not desired temporal outcomes.
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
- Do not bulk-download corpora until source rights, timestamp semantics, storage, and domain exposure pass the data gate.
- Use the borrowed machine only after access is confirmed and the run has a measured purpose.

## Open blockers

1. Local resource audit and immutable Pythia benchmark.
2. Real Pythia/OLMo tokenizer boundary audits and first development score.
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

The model adapter now fails closed on artifact identity, licensing, custom code, token boundaries, and score positions. The next risk is not implementation access; it is whether actual tokenizers expose unstable boundaries and whether actual models reveal ceilings, paraphrase instability, or score-length artifacts.

The dominant execution risk remains full-weight memory and dose. An inference-capable one-billion-parameter model may still be an impractical full-weight training model on the current machine.

The dominant scientific risk remains source covariance and direct domain exposure. Natural archives can teach the same verification, authority, privacy, and procedural structures that the evaluation intends to treat as far transfer. The source audit may therefore require narrowing source strata, redesigning primary constructs, or changing the A/B/C architecture before training.

## Exact next action

Complete the timestamp-native source, rights, independence, and domain-exposure audit. Do not select sources merely because they are downloadable or large. Reject any source architecture that cannot support held-out-source confirmation without directly teaching the primary evaluation constructs.
