# Project State

**Last updated:** 2026-08-17  
**Internal codename:** ChronoPersona  
**Scientific construct:** Cross-Source Temporal Generalization (CSTG)  
**Working paper title:** *From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models*

## Current phase

**Stage 0 — feasibility, model, data, evaluation, calibration, and compute audit**

The novelty gate, static model-artifact audit, dependency-light scorer, first
development registry, manifest-gated real-model adapter, provisional A/B/C
source architecture, source-neutral metadata contract, and offline source
adapter layer are complete.

Stage 0 remains open because no live metadata panel, local hardware benchmark,
real-model score, source-content sample, direct-exposure rate, synthetic
calibration threshold, or measured training cost has been established.

## Current write-active deliverable

**Deterministic Synthetic Identifiability Calibration corpus and balance system**

The next repository milestone should turn
`docs/SYNTHETIC_CALIBRATION_SPEC.md` into an executable but untrained
calibration package:

- at least two morally symmetric latent procedural contrasts;
- two disjoint training domains and one held-out evaluation domain per contrast;
- explicit-positive, indirect-transfer, shuffled-placebo, and neutral controls;
- deterministic generation from versioned templates and seeds;
- exact token-independent balance checks for document count, length, sentiment,
  success/failure, named-entity density, and surface vocabulary;
- leakage checks preventing repeated slogans, shared entities, copied decision
  templates, or evaluation answers in training;
- immutable corpus manifests and hashes;
- a dose-plan schema whose token counts remain unfrozen until local throughput
  is measured;
- no model download and no training.

## Parallel external evidence needed

### Local machine and model evidence

The repository contains guarded protocols, but the following evidence requires
the user's actual machine:

- exact RTX 2060 variant and VRAM;
- free RAM and disk;
- CUDA, driver, Python, Torch, and Transformers versions;
- Pythia and OLMo tokenizer-boundary audits over development-v0;
- immutable Pythia 1B load time, peak RAM/VRAM, and logits throughput;
- the first deterministic Pythia development score;
- a later tiny continued-pretraining benchmark.

### Bounded live source evidence

The source adapters are offline-validated but have not contacted their live
interfaces. The project still needs explicitly authorized, bounded metadata
runs for:

- pinned Wikimedia history-dump inventory;
- the frozen legacy Stack Exchange Archive.org inventory;
- arXiv submitted-date candidate enumeration followed by exact `arXivRaw`
  version/license enrichment;
- PMC OAI Dublin Core lifecycle-date candidates, followed by a separate
  publication-time and historical-version audit if PMC remains backup C.

No archive or source-text download is authorized by those metadata runs.

## Latest verified repository milestones

- PR #10 merged the CSTG redesign at
  `b2a18b050e801d7138a0a1babc7c94cc1d83e0ac`.
- PR #11 merged the primary-source novelty audit at
  `32d2a37fa02b65155c38df9df443c565d8d1b319`.
- PR #12 merged the model-artifact and guarded benchmark architecture at
  `33378aae095ac8af7be6fb5b142fa2d3afb137ba`.
- PR #13 merged complete-continuation scoring and development-v0 at
  `a19662a279d02b362b34437fcc52e1290a399696`.
- PR #14 merged manifest-gated tokenizer and Transformers scoring at
  `da42946cc8bbe61b64d1e2c70c5968f585830f99`.
- PR #15 merged the provisional A/B/C source architecture at
  `288582d46a25e56089b50d1245bf0ae42494f658`.
- PR #16 merged source-neutral metadata and deterministic sampling at
  `72eafcc617ab913b92cf53334a22dd31dd0d1b14`.
- PR #17 contains the offline source-adapter and source-C access-firewall
  milestone. Earlier revisions passed complete and focused CI; final validation
  is required after the latest date-semantics corrections.
- No evidence-bearing temporal adaptation experiment has run.
- The naturalistic pilot remains in `design` with an intentionally unfrozen
  zero token budget.

## Verified source architecture and tooling

### Provisional source roles

- **A:** Wikimedia article-revision added-text deltas.
- **B:** initial versions of posts from a frozen nontechnical Stack Exchange
  site panel.
- **C:** single-version, item-level CC0 or CC BY arXiv descriptive-science
  source text.
- **Backup C:** version-bounded, item-level CC0 or CC BY PMC Open Access text.

This architecture is `qualified-with-redesign`, not frozen.

Federal Register/GovInfo material remains rejected from the headline A/B/C
architecture because it directly teaches authority, safeguards, enforcement,
privacy, procedure, and related primary constructs.

### Source-neutral metadata contract

`src/chronopersona/source_metadata.py`:

- rejects document text fields;
- derives era membership from timezone-aware native timestamps when the
  timestamp semantics are qualified;
- permits unresolved era status when timestamp meaning is not yet strong enough;
- requires item-level rights, historical-version status, and authorship
  provenance before eligibility;
- produces deterministic summaries and stratified samples;
- keeps source-C era labels in a separate unblinding key.

### Offline source adapters

The current source-adapter milestone provides:

- bounded, explicit metadata-only network access;
- arXiv API candidate enumeration by first-submission date over an exact
  category list;
- exact arXiv OAI `arXivRaw` enrichment for selected base IDs, resolving
  version history and item license without using OAI modification dates as the
  era selector;
- PMC OAI parsing through the current endpoint with lifecycle-date evidence,
  no synthetic epoch fallback, unresolved era assignment, and unresolved
  historical-version status;
- pinned Wikimedia `YYYYMMDD` history inventory parsing that refuses the
  mutable `latest` alias during execution;
- legacy Stack Exchange Archive.org inventory parsing that requires company
  attribution, validates numeric file mtimes, and explicitly does not claim
  current official delivery;
- deterministic archive size, hash, and storage-margin summaries;
- frozen XML/JSON fixtures and no-network command tests.

No adapter downloads archive or source-text content.

### Held-out source-C locator firewall

`src/chronopersona/source_review.py` and the corresponding commands:

- remove locators, native IDs, timestamps, era labels, obvious PMCIDs, arXiv
  IDs, and URL schemes from reviewer packets;
- replace them with deterministic opaque access IDs;
- place locators in a separate protected access map;
- verify manager-packet, reviewer-packet, access-map, and access-event hashes
  before use;
- enforce an exact content-free access-event schema;
- produce append-only access events containing locator hashes, response hashes,
  byte counts, reviewer, purpose, canonical UTC time, and outcome;
- reject source bodies, raw locators, unexpected fields, tampered events, and
  malformed pre-existing log lines.

An era-hidden manager sample is not reviewer-ready until this second redaction
step passes.

## Evaluation status

- Primary metric: complete-continuation total-log-likelihood margin.
- Diagnostic metric: mean-token-log-likelihood margin.
- Score direction: semantic pole, not candidate display order or moral rank.
- Development-v0: twelve items, twenty-four forms, explicitly not frozen.
- Mechanical checks cover exact prompt context, continuation boundaries,
  option order, paraphrases, truncation, non-finite scores, and deterministic
  output identity.
- Several evidence items remain ceiling-prone.
- Several procedural items remain consequence- or valence-asymmetric.
- The punishment/rehabilitation item cannot be frozen in its current form.
- Dissent and transparency constructs remain absent.
- Real-tokenizer stability, model reliability, direct exposure, contamination,
  and human criterion validity remain unresolved.

## Model and dose status

- Public observational primary: DatedGPT base family after license and immutable
  revision resolution.
- Scientific causal primary: OLMo 2 1B original stage-1 step 23,100,
  provisional.
- Operational fallback: Pythia 1B deduped step 20,000, provisional.
- First local benchmark: immutable final Pythia 1B deduped artifact only.
- Quantized weights cannot determine the primary likelihood result without
  unquantized equivalence evidence.
- A fresh optimizer at an intermediate checkpoint is a declared intervention.
- A conventional one-billion-parameter full-weight AdamW run can exceed 16 GB
  before useful activation and batch memory.
- Ten million intervention tokens are only about 0.02% of prior exposure at the
  candidate OLMo/Pythia insertion points and are not retained as a credible
  headline dose.
- The token budget remains zero until throughput and synthetic dose-response
  evidence justify a frozen value.

## Current decisions

- **Novelty:** `novel enough under current redesign`.
- **Primary confirmation:** frozen source-C prediction; A/B agreement is
  exploratory.
- **Naturalistic null interpretation:** blocked until Synthetic Identifiability
  Calibration passes.
- **Source architecture:** provisional A/B/C above; Federal Register excluded
  from the headline design.
- **arXiv selection:** submitted-date API candidate enumeration, followed by
  exact OAI `arXivRaw` enrichment. OAI datestamps are not era selectors.
- **PMC timing:** Dublin Core dates are lifecycle evidence only; PMC era remains
  unresolved until publication-specific evidence is obtained.
- **Source C:** held out from item construction, temporal-direction estimation,
  hyperparameters, dose, thresholds, rescue decisions, and mechanism selection.
- **Real-model execution:** immutable revision, verified license, no remote code,
  no quantization, operation-specific approval.
- **Evaluation registry:** development-v0, rejected for freezing.
- **Era windows:** provisionally 2012-01-01 through 2013-12-31 and 2018-01-01
  through 2019-12-31; final selection remains data-only.
- **Training method:** PEFT may support engineering and dose reconnaissance but
  cannot silently become the headline causal method.
- **Rescue policy:** at most one predeclared rescue per failed major gate.
- **External spend:** CAD $0 unless the user authorizes a specific measured
  escalation.

## Resource constraints

- Current reported machine: RTX 2060 and 16 GB RAM.
- Possible borrowed machine: RTX 5070 and 32 GB RAM; availability and exact VRAM
  are not assumed.
- One training job at a time.
- Benchmark before committing token budgets.
- Do not download model weights without license, immutable revision, code-path,
  storage, and operation gates.
- Do not bulk-download corpora before rights, timestamps, source continuity,
  storage, and domain exposure pass.
- Do not launch the twelve-branch pilot before calibration, cost, storage, and
  run-completeness gates pass.

## Open blockers

1. Local resource audit and immutable Pythia benchmark.
2. Real Pythia/OLMo tokenizer audits and first development score.
3. DatedGPT model-weight license and selected immutable revisions.
4. Original OLMo step-23,100 file manifest, hashes, and current-code loading
   path.
5. Immutable Pythia step-20,000 revision and optimizer-reset decision.
6. Tiny full-weight/PEFT continued-pretraining benchmark.
7. Live metadata volume and continuity evidence for provisional A/B/C sources.
8. Frozen Stack Exchange site panel and version-reconstruction feasibility.
9. Wikimedia added-text extraction, revert/bot/import handling, and contributor
   attribution.
10. arXiv API-to-OAI enrichment yield, source-package accessibility, and
    license distribution under the source-C firewall.
11. PMC authoritative publication-time and historical-version retrieval
    feasibility if retained as backup C.
12. Direct-exposure, contamination, duplicate, event-concentration, and
    source-independence rates from bounded content samples.
13. Development-v0 real-model reliability and item revision.
14. Meaningful-effect threshold and null-equivalence interval.
15. Synthetic-calibration corpus, balance thresholds, dose, and seed count.
16. Run registry, resumable training pipeline, and measured cost envelope.
17. Confirmatory seed count and common post-training recipe.

## Current risk judgment

The archive interfaces are now represented more honestly: arXiv OAI
modification dates are not used to select submission eras, PMC lifecycle dates
are not promoted into publication dates, missing timestamps are not fabricated,
Wikimedia snapshot identity is not confused with schema version, and the Stack
Exchange Archive.org item is not misrepresented as current delivery.

The dominant source risk is still structural exposure and covariance. Even
narrowed archives may teach verification, hierarchy, privacy, uncertainty, or
procedure directly, and nominally independent sources can share events,
institutions, authors, or upstream text.

The dominant execution risk remains full-weight memory and intervention dose.
A model that fits for inference may still be impractical for broad-update
continued pretraining on the current machine.

## Exact next action

Complete PR #17 validation and merge it if review remains clean. Then build and
validate the deterministic Synthetic Identifiability Calibration corpus and
balance system without downloading a model or starting training. Keep all token
doses unfrozen. In parallel, the user can run the existing local resource,
tokenizer, and Pythia benchmark protocols and explicitly authorize bounded live
metadata queries when ready.
