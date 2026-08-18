# Project State

**Last updated:** 2026-08-18  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, calibration, reproducibility, and compute audit**

The project now has:

- a CSTG charter and novelty audit;
- model-artifact roles and guarded local benchmark protocols;
- a complete-continuation likelihood scorer and development evaluation registry;
- provisional A/B/C source architecture;
- source-neutral metadata, official-interface adapters, and a source-C access firewall;
- a deterministic Synthetic Identifiability Calibration package;
- immutable run identity, hash-chained state, atomic checkpoints, and interruption/resume equivalence;
- deterministic content manifests and bounded lexical content-integrity audits;
- a final Stage 0 hardening layer for portable identities, bounded planning, exact metadata origins, evidence-type validation, and repository hygiene.

Stage 0 remains open. No model has been trained, no real source corpus has been bulk-downloaded, no token dose has been frozen, and no scientific temporal result exists.

## Gate decision

**The development content-integrity gate passed. The next real-source qualification gate is externally blocked.**

The accepted implementation provides:

- source-neutral content-bearing JSONL manifests whose text remains in separate local files;
- exact recomputation of raw/normalized hashes, byte counts, and word counts;
- strict role, source, era, holdout, rights, authorship, fixture, eligibility, and exclusion fields;
- recursive rejection of embedded text in metadata;
- portable path protection covering POSIX traversal, Windows traversal, drive paths, backslashes, non-canonical paths, symlinks, and root escape;
- exact raw and normalized duplicate clusters;
- bounded lexical near-duplicate candidates using shingles and SimHash bands, with exact Jaccard verification;
- visible hard caps and skipped-bucket diagnostics;
- literal evaluation-overlap and direct-construct triage;
- cross-source, cross-era, cross-role, and held-out-boundary flags;
- exact manifest-bound authorization before non-fixture source-C text can be opened;
- deterministic text-free reports;
- no automatic exclusion, semantic-independence claim, or scientific eligibility decision.

The gate is validated on redistributable synthetic fixtures only. It does not establish that the real provisional sources are clean or suitable. The final repository review preserves this claim ceiling while verifying the tracked tree is free of generated machine state and tightening validators that could otherwise admit ambiguous paths, provenance, authorization, token evidence, or metadata origins.

## Recovery of the accidental importer

PR #21 left a failed one-time importer and eight base64 fragments on `main`. The importer never extracted the intended implementation.

The recovery process established a specific fragment-boundary defect:

- normalized fragment lengths were `4867, 4606, 4606, 4606, 4606, 4606, 4606, 4602`;
- fragment 0 contained a 261-character overrun after the common 4,606-character boundary;
- the first 257 overrun characters duplicated the beginning of fragment 1;
- trimming fragment 0 to the common boundary produced a valid 36,844-character base64 stream, gzip payload, and safe 46-member tar archive.

Recorded identities:

- original normalized stream: `677fba3681a444d51a98778f0a6185bc0ed923641b0d40ad315522361728b81e`;
- recovered gzip: `73545589b59a7250a8f11cc06ce809cec35b4fec71ac33268019643cf7d040c1`;
- recovered tar: `730603e9f7d88d5530c9001f810f420210ae4f4c2ab62968739dc601ad41b8d6`.

The fragments and one-time workflows were removed. Exact evidence is preserved in `reports/stage0/content_integrity_bundle_recovery.json`.

## Current write-active deliverable

**None. Stop at the bounded real-content qualification boundary.**

The next gate requires external evidence that does not exist in the repository:

1. small rights-qualified and historically version-bounded samples for sources A and B;
2. a source-C review packet opened only through the existing authorization and access-log path;
3. real duplicate, overlap, direct-exposure, and cross-source covariance rates;
4. manual review and threshold-sensitivity analysis;
5. a `qualified`, `qualified after redesign`, or `not suitable` decision for each source family and era window.

Do not silently cross into corpus acquisition, requester-pays access, bulk archive download, or model training.

## Latest repository milestones

- PR #10 — CSTG redesign.
- PR #11 — primary-source novelty audit.
- PR #12 — model-artifact and guarded local benchmark architecture.
- PR #13 — complete-continuation scoring and development-v0 evaluation.
- PR #14 — manifest-gated tokenizer and Transformers scoring.
- PR #15 — provisional A/B/C source architecture.
- PR #16 — source-neutral metadata and deterministic sampling.
- PR #17 — offline source adapters and source-C access firewall.
- PR #18 — deterministic Synthetic Identifiability Calibration package; defects later corrected without weakening its gates.
- PR #20 — immutable run registry and resumable fixture smoke.
- PR #24 — recovered and hardened content-integrity gate, merged as `32717a5dcf6a67838e366b63ded33cd81b5552b2` after exact-head CI, Content Integrity, and Run Registry Smoke passed on Python 3.11 and 3.12.

Stale duplicate PR #22 and superseded recovery PR #23 were closed unmerged.

## Scientific architecture

### Primary confirmatory claim

Estimate a shared early-versus-late behavioral component using source families A and B, freeze it, and predict source family C. A/B agreement alone remains exploratory.

### Provisional source roles

- **A:** Wikimedia article-revision added-text deltas.
- **B:** initial post versions from a frozen nontechnical Stack Exchange site panel.
- **C:** single-version, item-level CC0 or CC BY arXiv descriptive-science source text.
- **Backup C:** version-bounded, item-level CC0 or CC BY PMC Open Access text.

These assignments remain `qualified-with-redesign`, not frozen. Federal Register/GovInfo remains excluded from the headline design because it directly teaches several primary institutional and procedural constructs.

### Model roles

- **Observational primary:** DatedGPT base family after weight-license and immutable-revision resolution.
- **Scientific causal primary:** OLMo 2 1B original stage-1 step 23,100, provisional.
- **Operational fallback / second family:** Pythia 1B deduped step 20,000, provisional.
- **First local load/logits benchmark:** immutable final Pythia 1B deduped artifact only.

A one-billion-parameter full-weight AdamW run may exceed the current machine’s practical memory envelope. Full-weight feasibility is unverified.

### Evaluation

- Primary metric: complete-continuation total-log-likelihood margin.
- Diagnostic metric: mean-token-log-likelihood margin.
- Score direction: semantic pole, not display order or moral rank.
- Development-v0 contains twelve items and twenty-four forms and is not frozen.
- Real-tokenizer behavior, public-model reliability, source exposure, contamination, and human criterion validity remain unresolved.

## Resource constraints

- Current reported machine: RTX 2060 and 16 GB RAM.
- Possible borrowed machine: RTX 5070 and 32 GB RAM; availability and exact VRAM remain unverified.
- Default external-compute budget: CAD $0.
- One training job at a time.
- No model download without immutable revision, verified license, approved code path, and measured storage margin.
- No bulk corpus download before rights, timestamp, continuity, storage, exposure, and integrity gates pass.
- No twelve-branch naturalistic pilot before calibration, cost, storage, and run-completeness gates pass.

## External blockers

### Real-source content

- no authorized real A/B content sample;
- no completed source-C access authorization;
- no measured real duplicate, contamination, exposure, event, host, contributor, topic, genre, quotation, revision, or syndication rates;
- no production-scale streaming or deterministic derived-exclusion manifest;
- no frozen integrity thresholds.

### Local model and compute

- exact RTX 2060 variant, VRAM, free RAM, and disk;
- CUDA, driver, Python, Torch, and Transformers versions;
- Pythia and OLMo tokenizer audits;
- immutable Pythia load time, peak memory, and logits throughput;
- first deterministic Pythia development score;
- tiny full-weight/PEFT continued-pretraining benchmark;
- DatedGPT weight license and immutable revisions;
- original OLMo step-23,100 file manifest and compatible loading path;
- immutable Pythia step-20,000 revision and optimizer-reset decision.

## Current risk judgment

The development content-integrity mechanics are now credible and portable, but real-source scientific validity is still unknown. Lexical triage can expose obvious duplication and direct phrase overlap; it cannot prove semantic independence or source-family independence.

The dominant scientific risk remains source covariance and direct exposure. Nominally independent archives may share events, institutions, authors, upstream text, quotations, or procedural concepts.

The dominant compute risk remains intervention dose and full-weight memory. Ten million intervention tokens are approximately 0.02% of prior exposure at the provisional OLMo/Pythia insertion points and are not retained as a credible headline dose.

## Exact next action

Stop. Preserve the content-integrity gate as passed at the development-fixture level.

Resume only when bounded real-source content access is explicitly authorized and can be performed under the existing rights, version, source-C firewall, storage, and no-bulk-acquisition rules. At that point, run the real-content qualification gate and issue a source-by-source proceed, redesign, or stop decision.
