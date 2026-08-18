# Project State

**Last updated:** 2026-08-18
**Internal codename:** ChronoPersona
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, calibration, reproducibility, and compute audit**

The project now has a CSTG charter, targeted novelty audit, model-artifact roles, likelihood scorer, development evaluation registry, guarded Transformers bridge, provisional A/B/C source architecture, metadata and source-adapter layers, source-C firewall, deterministic Synthetic Identifiability Calibration package, and a verified immutable run lifecycle.

Stage 0 remains open. No model has been trained, no source corpus has been bulk-downloaded, no token dose has been frozen, and no scientific temporal result exists.

## Current write-active deliverable

**Content-manifest integrity, lexical deduplication, and evaluation-exposure triage — `agent/content-integrity-v0`**

The milestone is designed to provide:

- a source-neutral content-bearing JSONL contract whose text stays in separate local files;
- exact recomputation of raw/normalized hashes, bytes, and word counts;
- safe path, symlink, UTF-8, and raw-text-field guards;
- exact raw and normalized duplicate clusters;
- deterministic lexical near-duplicate candidates using word shingles, SimHash bands, and verified Jaccard;
- hard bucket and candidate-pair caps;
- lexical evaluation-overlap screening;
- narrow direct-construct phrase triage;
- cross-source, cross-era, cross-role, and held-out-boundary flags;
- explicit authorization before non-fixture source-C content is opened;
- reports containing no source excerpts, semantic-equivalence claim, automatic exclusion, or scientific eligibility decision;
- a redistributable synthetic fixture that exercises every channel.

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
- PR #19 — closed unmerged after review found a duplicate adapter architecture and weaker timestamp/network guarantees.
- PR #20 — immutable run registry and resumable fixture smoke, merged at `6febed243d940daad08010943bbd9cb44bea2823`.

## Verified reproducibility status

PR #20 established:

- canonical run identities derived from exact inputs, Git commit, environment, seed, method, and resource boundaries;
- hash-chained event and cross-run registries;
- explicit `design`, `frozen`, `running`, `failed`, and `complete` states;
- exclusive per-run and global-registry locks with replacement detection;
- atomic artifacts and checkpoints;
- actual storage gating;
- explicit recovery/resume;
- no duplicate completed work;
- byte-identical final manifests after interrupted/resumed versus uninterrupted execution.

At its final head, the full suite passed 140 tests on Python 3.11 and 3.12, and the Synthetic Calibration and Run Registry Smoke workflows were green. This is engineering validation only; no model or trainer was exercised.

## Calibration status

The deterministic package contains morally symmetric policy pairs, explicit/indirect/placebo/neutral conditions, disjoint training and evaluation domains, dose placeholders, leakage checks, and immutable hashes.

PR #20 corrected a latent balance defect in PR #18 without weakening its gates:

- one verification option pair had unequal word count;
- neutral-control wording and one direct rule broke the sentiment-lexicon balance.

The package remains **untrained**. Target token counts, model scale, seeds, meaningful-effect threshold, placebo-equivalence region, capability tolerance, multiplicity method, and the one permitted rescue remain unfrozen.

## Scientific architecture

### Primary confirmatory claim

Estimate the shared early-versus-late behavioral component on source families A and B, freeze it, and predict source family C. A/B agreement alone remains exploratory.

### Provisional source roles

- **A:** Wikimedia article-revision added-text deltas.
- **B:** initial versions of posts from a frozen nontechnical Stack Exchange site panel.
- **C:** single-version, item-level CC0 or CC BY arXiv descriptive-science source text.
- **Backup C:** version-bounded, item-level CC0 or CC BY PMC Open Access text.

The assignment is `qualified-with-redesign`, not frozen. Federal Register/GovInfo remains excluded from the headline design because it directly teaches several primary institutional and procedural constructs.

### Model roles

- **Observational primary:** DatedGPT base family after weight-license and immutable-revision resolution.
- **Scientific causal primary:** OLMo 2 1B original stage-1 step 23,100, provisional.
- **Operational fallback / second family:** Pythia 1B deduped step 20,000, provisional.
- **First local load/logits benchmark:** immutable final Pythia 1B deduped artifact only.

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
- No bulk corpus download before rights, timestamp, continuity, storage, exposure, and integrity gates pass.
- No twelve-branch naturalistic pilot before calibration, cost, storage, and run-completeness gates pass.

## Parallel evidence requiring the user's machine or explicit live access

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

No source-text or archive download is authorized by those metadata-only tasks.

## Open blockers

1. Review and merge of the content-integrity milestone.
2. Production-scale streaming manifests, external sorting, and stable duplicate clusters.
3. Bounded real-content samples and reviewed exact/near duplicate rates.
4. Evaluation exposure, benchmark phrase, direct-construct, and contamination rates on real samples.
5. Cross-source overlap, syndication, quotation, event, contributor, host, topic, and genre concentration.
6. Deterministic derived-data manifests with reason-coded exclusions and threshold sensitivity.
7. Local resource audit and immutable Pythia benchmark.
8. DatedGPT weight license and selected immutable revisions.
9. Original OLMo step-23,100 file manifest and compatible loading path.
10. Immutable Pythia step-20,000 revision and optimizer-reset decision.
11. Real-model tokenizer, likelihood, memory, and throughput evidence.
12. Wikimedia added-text extraction, revert/bot/import handling, and contributor attribution.
13. Stack Exchange site-panel freeze and initial-version reconstruction feasibility.
14. arXiv source-package accessibility and eligible-license yield under the source-C firewall.
15. Development-v0 item repair and real-model reliability.
16. Frozen calibration dose, seeds, thresholds, equivalence region, and capability tolerance.
17. Manifest-approved real trainer resumption and measured cost.
18. Confirmatory seed count and common post-training recipe.

## Current risk judgment

The run lifecycle is now verified. The immediate engineering risk is data integrity at content-manifest scale: duplicate clusters, evaluation exposure, cross-source overlap, source-C access, and reproducible exclusion decisions.

The current content-integrity design is intentionally lexical and conservative. It can expose obvious and high-overlap contamination, but it cannot establish semantic independence. A production corpus still requires manually validated thresholds, reviewed semantic screening, source-specific revision/syndication handling, and sensitivity analysis.

The dominant scientific risk remains source covariance and direct exposure. Nominally independent archives can share events, institutions, authors, upstream text, and procedural concepts. The project reaches CSTG only if an A/B-derived component predicts held-out C under a frozen threshold and source-specific heterogeneity does not dominate.

The dominant compute risk remains intervention dose and full-weight memory. Ten million intervention tokens are only about 0.02% of prior exposure at the provisional OLMo/Pythia insertion points and are not retained as a credible headline dose.

## Exact next action

Complete and independently review the dependency-free content-integrity implementation on synthetic fixtures. Merge only after dedicated Python 3.11/3.12 CI and the full repository suite pass. Then add production-scale streaming and deterministic derived-exclusion tooling; real corpus acquisition and model training remain blocked.
