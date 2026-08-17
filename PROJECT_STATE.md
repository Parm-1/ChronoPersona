# Project State

**Last updated:** 2026-08-17  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, and compute audit**

The novelty gate and static model-artifact audit are complete. Stage 0 remains open because the local hardware envelope, source feasibility, evaluation reliability, synthetic-calibration thresholds, and measured training cost are not yet qualified.

## Current write-active deliverable

**Conditional-continuation scorer and evaluation development system**

This work is unblocked while the local machine audit remains pending. It must produce:

- exact complete-continuation log-likelihood scoring;
- option reversal and paraphrase support;
- tokenizer and truncation diagnostics;
- immutable score metadata;
- development item schema and approximately twelve reviewed seed items;
- tests using synthetic logits and a tiny local model adapter;
- no model download in CI.

## Parallel external evidence needed

**Local resource and immutable Pythia benchmark**

The repository now contains a safe protocol and scripts, but this evidence can only be produced on the user's machine:

- exact RTX 2060 VRAM variant;
- free RAM and disk;
- CUDA, driver, Python, Torch, and Transformers versions;
- immutable Pythia 1B loading time, peak RAM/VRAM, and logits throughput;
- later, a tiny continued-pretraining benchmark.

## Latest verified evidence

### Observed

- PR #10 merged the CSTG redesign into `main` at `b2a18b050e801d7138a0a1babc7c94cc1d83e0ac`.
- PR #11 merged the primary-source novelty audit at `32d2a37fa02b65155c38df9df443c565d8d1b319`.
- The project is novel enough only under the CSTG design centered on frozen prediction of held-out source C.
- The repository contains a schema-v2 experiment validator and a model-manifest validator.
- `artifacts/manifests/MODEL_MANIFEST.json` records immutable revisions, licenses, sizes, custom-code status, execution gates, and scientific roles.
- `docs/MODEL_SELECTION_ADR.md` separates observational, causal-primary, fallback, and boundary-case models.
- `docs/LOCAL_BENCHMARK_PROTOCOL.md`, `scripts/audit_local_resources.py`, `scripts/audit_hf_model.py`, and `scripts/benchmark_model.py` provide guarded local audit paths.
- `COMPUTE_LEDGER.csv` distinguishes reported hardware from measured runs.
- No evidence-bearing temporal adaptation experiment has run.
- The design remains in `design` with an intentionally unfrozen zero token budget.

### Model-artifact findings

#### Observational panel

- DatedGPT base checkpoints are approximately 1.3B, standard Llama-family bfloat16 safetensors, and operationally plausible one at a time on local hardware.
- DatedGPT execution is blocked because no explicit model-weight license was found and four selected immutable revisions remain unresolved.
- PIT's inspected public checkpoint is a custom-code 4B float32 artifact around 17.8 GB. It is a secondary panel, not the default local path.
- ChronoGPT uses custom Python and inspected PyTorch binary serialization; it remains a boundary case pending isolated code review.
- TypewriterLM's inspected base checkpoint is approximately 14.5 GB and lacks an explicit weight license in the audited metadata.
- Kairos is a 6B custom-architecture ordering boundary case, not a default local artifact.

#### Causal candidates

- OLMo 2 1B remains the scientifically preferred causal base.
- The preferred original insertion point is stage-1 step 23,100, corresponding to approximately 48.44 billion prior tokens under the published global batch.
- The original OLMo repository is now marked inactive. It remains immutable configuration/checkpoint evidence; future execution should use a pinned compatible OLMo-core version.
- Pythia 1B deduped at step 20,000, approximately 41.94 billion prior tokens, is the operational fallback and plausible second-family replication.
- The immutable final Pythia 1B deduped checkpoint is the first approved local loading/logits benchmark. It is not the causal insertion point.
- A straightforward one-billion-parameter full-weight AdamW run can exceed 16 GB before useful activations and batch memory. Full-weight feasibility is not assumed.

### Dose implication

- Ten million intervention tokens are only about 0.02% of prior exposure at the candidate OLMo/Pythia insertion points.
- The old ten-million-token planning value is therefore not retained as a credible headline dose.
- The token budget remains zero until measured throughput and synthetic dose-response evidence justify a frozen value.

### Still unverified

- Actual current-machine VRAM, free storage, runtime versions, and sustained throughput.
- Immutable revisions and model-weight license for the complete DatedGPT panel.
- Exact file hashes and conversion path for the original OLMo step-23,100 checkpoint.
- Immutable Pythia step-20,000 Hub commit.
- Full-weight and optimizer-state feasibility on either reported machine.
- Source-family continuity, independence, timestamps, rights, and human-authorship confidence.
- Evaluation reliability and scorer correctness.

## Current decisions

- **Novelty judgment:** `novel enough under current redesign`.
- **Public observational primary:** DatedGPT base family after license and revision resolution.
- **Public observational secondary:** PIT only after custom-code review and a hardware gate.
- **Scientific causal primary:** OLMo 2 1B original stage-1 step 23,100, provisional.
- **Operational causal fallback:** Pythia 1B deduped step 20,000, provisional.
- **First local model benchmark:** immutable final Pythia 1B deduped safetensors.
- Quantized weights cannot determine the primary likelihood result without unquantized equivalence evidence.
- A fresh optimizer at an intermediate checkpoint is a declared intervention, not a silent implementation detail.
- Source-C prediction remains the primary confirmatory result; A/B agreement is exploratory.
- Synthetic Identifiability Calibration remains mandatory before interpreting a naturalistic null.
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

- Minimize cash spend while preserving the strongest feasible paper.
- Default external-compute budget: CAD $0.
- No rental, purchase, paid license, or external account without explicit user authorization.
- One training job at a time.
- Benchmark before committing token budgets.
- Do not launch the twelve-branch naturalistic set until calibration, cost, storage, and run-completeness gates pass.
- Do not download a model unless its license, immutable revision, storage margin, and code path pass the manifest gates.
- Use the borrowed machine only after access is confirmed and the run has a measured purpose.
- Escalate to paid compute only for a scientifically decisive run that cannot be completed locally and only after presenting the minimum-cost plan.

## Open blockers

1. Local resource audit and immutable Pythia benchmark.
2. DatedGPT model-weight license and four immutable revisions.
3. Original OLMo step-23,100 file manifest, hashes, and current-code loading path.
4. Immutable Pythia step-20,000 revision and optimizer-reset decision.
5. Tiny full-weight/PEFT continued-pretraining benchmark.
6. Timestamp-native corpus continuity, source independence, rights, and authorship provenance.
7. Domain exposure and contamination risk.
8. Conditional-continuation scorer implementation and validation.
9. Evaluation reliability, meaningful-effect threshold, and temporal-cue review.
10. Synthetic-calibration construct, dose, and seed count.
11. Confirmatory seed count and common post-training recipe.

## Current risk judgment

The static artifact plan is feasible, but the original assumption that every public temporal family could form one local panel was wrong. DatedGPT is the only plausible first local observational family; PIT, ChronoGPT, TypewriterLM, and Kairos require distinct code, license, or hardware decisions.

The dominant execution risk is now full-weight memory and dose. An inference-capable one-billion-parameter model can still be an impractical full-weight training model on the current machine. The local benchmark must precede optimizer and dose design.

The dominant scientific risk remains source covariance. Nominally independent archives may share events, institutions, authors, upstream text, and web infrastructure. The project succeeds only if a component estimated from A and B predicts C under a frozen threshold and source heterogeneity remains subordinate to the shared component.

## Exact next action

Implement and test the conditional-continuation scorer and development evaluation registry without downloading models. In parallel, run the commands in `docs/LOCAL_BENCHMARK_PROTOCOL.md` on the current machine when local execution is available, then commit only aggregate measurements and non-sensitive artifact identities through a reviewed PR.
