# Project State

**Last updated:** 2026-08-17  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, calibration, reproducibility, and compute audit**

The project now has a defensible CSTG charter, targeted novelty audit, audited model-artifact roles, likelihood scorer, development evaluation registry, guarded Transformers bridge, provisional A/B/C source architecture, source-neutral metadata contract, offline source adapters, source-C access firewall, deterministic Synthetic Identifiability Calibration package, and an immutable run-registry/resumption milestone under review.

Stage 0 remains open. No model has been trained, no source corpus has been bulk-downloaded, no token dose has been frozen, and no scientific temporal result exists.

## Current write-active deliverable

**Immutable run registry and resumable CPU fixture smoke — PR #20**

The milestone establishes:

- scientific run identity derived from canonical inputs;
- separation of immutable identity from runtime events;
- explicit `design`, `frozen`, `running`, `complete`, and `failed` states;
- append-only hash chains for run events and the cross-run registry;
- exclusive per-run and global registry locks;
- lock-replacement detection;
- atomic artifact and checkpoint replacement;
- actual free-storage gating before initialization;
- ordered-prefix checkpoint semantics;
- explicit recovery after unclean exit and explicit resume after recorded failure;
- deterministic final-manifest equivalence between interrupted/resumed and uninterrupted execution;
- corruption, duplicate-work, unsafe-path, and identity-mismatch failure tests;
- no network, model loading, downloads, training, external spend, or scientific interpretation.

## Latest verified repository milestones

- PR #10 — CSTG redesign.
- PR #11 — primary-source novelty audit.
- PR #12 — model-artifact and guarded local benchmark architecture.
- PR #13 — complete-continuation scoring and development-v0 evaluation.
- PR #14 — manifest-gated tokenizer and Transformers scoring.
- PR #15 — provisional A/B/C source architecture.
- PR #16 — source-neutral metadata and deterministic sampling.
- PR #17 — offline source adapters and source-C access firewall, merged at `689ba848b21ddcc292c7c6ef75d1fedd53b1ce3c`.
- PR #18 — deterministic Synthetic Identifiability Calibration package, merged at `23293023ec3ad78a650f09b3818a5b74f7a8d03e`.
- PR #19 — closed unmerged as superseded after review found a duplicate adapter stack, unsafe PMC timestamp promotion, and an incomplete redirect-host boundary.
- PR #20 — immutable run registry and resumable fixture smoke, active.

## Calibration-package correction found by PR #20

Full repository CI exposed two defects in the merged synthetic package:

1. one verification evaluation option pair was 14 versus 15 words;
2. neutral-control wording and one direct rule broke the promised sentiment-lexicon balance.

PR #20 repairs the wording rather than weakening the balance gates and regenerates the deterministic package identity. The repair was validated by rebuilding the full package and running the complete test suite before its commit was created.

The calibration package remains **untrained**. Its target token counts, seed count, meaningful-effect threshold, placebo equivalence region, capability tolerance, multiplicity method, and one-rescue action remain unfrozen.

## Scientific architecture

### Primary confirmatory claim

Estimate the shared early-versus-late behavioral component on source families A and B, freeze it, and predict source family C. A/B agreement alone remains exploratory.

### Provisional source roles

- **A:** Wikimedia article-revision added-text deltas.
- **B:** initial versions of posts from a frozen nontechnical Stack Exchange site panel.
- **C:** single-version, item-level CC0 or CC BY arXiv descriptive-science source text.
- **Backup C:** version-bounded, item-level CC0 or CC BY PMC Open Access text.

This assignment is `qualified-with-redesign`, not frozen. Federal Register/GovInfo material remains excluded from the headline design because it directly teaches institutional procedures and several primary constructs.

### Model roles

- **Observational primary:** DatedGPT base family after weight-license and immutable-revision resolution.
- **Scientific causal primary:** OLMo 2 1B original stage-1 step 23,100, provisional.
- **Operational fallback / second family:** Pythia 1B deduped step 20,000, provisional.
- **First local loading/logits benchmark:** immutable final Pythia 1B deduped artifact only.

A conventional one-billion-parameter full-weight AdamW run may exceed the current machine's practical memory envelope. Full-weight feasibility is not assumed.

### Evaluation

- Primary metric: complete-continuation total-log-likelihood margin.
- Diagnostic metric: mean-token-log-likelihood margin.
- Score direction: semantic pole, not display order or moral rank.
- Development-v0: twelve items and twenty-four forms, explicitly not frozen.
- Several items remain ceiling-, consequence-, or valence-sensitive.
- Real-tokenizer behavior, public-model reliability, direct exposure, contamination, and human criterion validity remain unresolved.

## Resource constraints

- Current reported machine: RTX 2060 and 16 GB RAM.
- Possible borrowed machine: RTX 5070 and 32 GB RAM; availability and exact VRAM remain unverified.
- Default external-compute budget: CAD $0.
- One training job at a time.
- No model download without immutable revision, verified license, approved code path, and measured storage margin.
- No bulk corpus download before rights, timestamp, continuity, storage, and domain-exposure gates pass.
- No twelve-branch naturalistic pilot before calibration, cost, storage, and run-completeness gates pass.

## Parallel evidence that requires the user's machine or explicit live access

### Local machine/model evidence

- exact RTX 2060 variant, VRAM, free RAM, and free disk;
- CUDA, driver, Python, Torch, and Transformers versions;
- Pythia and OLMo tokenizer-boundary audits;
- immutable Pythia 1B load time, peak RAM/VRAM, and logits throughput;
- first deterministic Pythia development score;
- later, a tiny continued-pretraining benchmark.

### Bounded live source evidence

- pinned Wikimedia history-dump inventory;
- frozen legacy Stack Exchange Archive.org inventory;
- arXiv submitted-date enumeration and exact `arXivRaw` version/license enrichment;
- PMC publication-time and historical-version evidence if PMC remains backup C.

No source-text or archive download is authorized by these metadata-only tasks.

## Open blockers

1. Green review and merge of PR #20.
2. Local resource audit and immutable Pythia benchmark.
3. DatedGPT weight license and selected immutable revisions.
4. Original OLMo step-23,100 file manifest and compatible loading path.
5. Immutable Pythia step-20,000 revision and optimizer-reset decision.
6. Real-model tokenizer, likelihood, memory, and throughput evidence.
7. Live metadata volume and continuity evidence for provisional A/B/C sources.
8. Wikimedia added-text extraction, revert/bot/import handling, and contributor attribution.
9. Stack Exchange site-panel freeze and initial-version reconstruction feasibility.
10. arXiv source-package accessibility and license yield under the source-C firewall.
11. Direct-exposure, exact/near-duplicate, contamination, event-concentration, and source-independence rates from bounded content samples.
12. Development-v0 item repair and real-model reliability.
13. Frozen calibration dose, seeds, meaningful-effect threshold, equivalence region, and capability tolerance.
14. Manifest-approved real training resumption and measured cost.
15. Confirmatory seed count and common post-training recipe.

## Current risk judgment

The run lifecycle is no longer the largest uncontrolled engineering risk: PR #20 makes identity, state, checkpoints, locks, resume behavior, and final artifacts directly testable. The next engineering risk is data integrity at content-manifest scale—especially duplicate clusters, evaluation exposure, cross-source overlap, and reason-coded exclusions.

The dominant scientific risk remains source covariance and direct exposure. Nominally independent archives can share events, institutions, authors, upstream text, and procedural concepts. The project only reaches CSTG when a component estimated from A and B predicts held-out C under a frozen threshold and source-specific heterogeneity does not dominate.

The dominant compute risk remains intervention dose and full-weight memory. Ten million intervention tokens are only about 0.02% of prior exposure at the provisional OLMo/Pythia insertion points and are not retained as a credible headline dose.

## Exact next action

Complete independent code/CI review of PR #20 and merge only if all general, calibration, and resumable-smoke workflows pass. Then implement deterministic content-manifest, exact/near-duplicate, evaluation-exposure, contamination, and cross-source-overlap tooling on redistributable synthetic fixtures. Real corpus acquisition and model training remain blocked.