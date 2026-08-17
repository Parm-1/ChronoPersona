# Stage 0 Source Architecture Audit

**Date:** 2026-08-17  
**Scope:** source documentation, rights, timestamp semantics, version integrity, independence, domain exposure, and acquisition design  
**Behavioral outcomes inspected:** no  
**Bulk text acquired:** no

## Decision

Proceed with a **metadata-first, bounded-sample qualification** of:

- A — Wikimedia article-revision added-text deltas;
- B — initial Stack Exchange post versions from a frozen nontechnical site panel;
- C — single-version, item-level CC0 or CC BY arXiv descriptive-science source text;
- backup C — version-bounded item-level CC0 or CC BY PMC Open Access text.

Reject Federal Register/GovInfo documents from the headline A/B/C design because direct procedural and institutional exposure would make source culture and direct imitation dominant explanations.

The source architecture is **qualified with redesign**, not frozen.

## Evidence

### Timestamp semantics

- Wikimedia provides revision-native history suitable for assigning added spans to the revision that introduced them.
- Stack Exchange data contains post and history records, allowing reconstruction of the initial post state rather than using later edited text.
- arXiv exposes submission/version metadata, but current bulk source can represent later versions; single-version items avoid the first historical-version ambiguity.
- PMC exposes publication and update metadata but current XML can contain later corrections or replacements; it remains a backup until version integrity is proven.
- Federal Register/GovInfo provides strong official publication dates.

### Rights

- Wikimedia and Stack Exchange text carry attribution and share-alike lineage that must remain record-specific.
- Stack Exchange license version changes with contribution date.
- arXiv uses several item-level license choices; the default distribution license is not treated as a general reuse license. The first C design uses CC0 and CC BY only.
- PMC rights vary by article; the first backup-C design uses CC0 and CC BY only through approved automated services.
- Government hosting does not eliminate third-party or transferred-rights analysis.

### Independence

The assigned families differ in production process:

- collaborative encyclopedia revision;
- community question answering and moderation;
- scholarly preprint submission.

They still share events, language, contributors, citations, quotations, and upstream web culture. Exact, near-duplicate, citation, event, and contributor-overlap analyses remain mandatory.

### Domain exposure

No broad archive is naturally free of evidence and procedure concepts.

The proposed filtered strata reduce but do not eliminate structural exposure:

- Wikimedia: indirect after aggressive topic and namespace filtering;
- Stack Exchange: structurally related even after site exclusions;
- arXiv: structurally related for evidence integration and indirect for procedural trade-offs after methods/category exclusions;
- PMC: similar backup profile;
- Federal Register: direct procedural exposure and therefore rejected.

The current evaluation cannot be frozen before real source samples and direct-exposure audits exist.

## Artifacts

- `artifacts/manifests/SOURCE_REGISTRY.json`
- `src/chronopersona/source_registry.py`
- `scripts/validate_source_registry.py`
- `tests/test_source_registry.py`
- `docs/DATA_SOURCE_ADR.md`
- `docs/DOMAIN_EXPOSURE_MATRIX.md`
- `docs/HELD_OUT_SOURCE_PROTOCOL.md`
- `docs/SOURCE_SAMPLE_PROTOCOL.md`
- `docs/SOURCE_RIGHTS_MATRIX.md`
- `.github/workflows/source-registry.yml`

## Validation

The source registry validator enforces:

- A/B/C assignment uniqueness;
- exploratory versus confirmatory roles;
- source-C and backup-C holdout status;
- required holdout prohibitions;
- metadata-only and no-bulk-download state;
- timestamp/coverage fields;
- rights status;
- primary-domain exposure constraints;
- rejection of direct-exposure sources from assigned A/B/C.

CI runs the validator and focused tests on Python 3.11 and 3.12.

## Risks

### Scientific

- filtering may remove the era signal as well as direct exposure;
- retained Stack Exchange content may still teach procedural reasoning;
- scientific prose may create capability or evidence-language shifts rather than an era component;
- source C can cease to be confirmatory through information leakage;
- source families share upstream events and quoted text;
- one historical event or topic can dominate a window.

### Rights

- contribution/article-level license logic is operationally complex;
- share-alike implications for derived corpora and weights remain unresolved;
- historical versions can include imported or third-party text;
- metadata access permission does not imply text redistribution permission.

### Engineering

- full Wikimedia history is large;
- historical revision/post reconstruction is nontrivial;
- arXiv bulk source is requester-pays;
- version-accurate PMC text may be unavailable for many records;
- cross-source deduplication and exposure indexing require storage beyond normalized text alone.

## Stop conditions

Stop or redesign the source architecture when:

- two exploratory families cannot each supply matched early/late text;
- held-out C has insufficient permissively licensed, version-valid volume;
- direct exposure remains common after filters;
- filtering creates severe era imbalance;
- rights or attribution cannot be implemented;
- cross-source overlap destroys meaningful intervention independence;
- storage or acquisition exceeds authorized resources.

## Next write-active deliverable

Implement deterministic metadata-manifest and bounded-sample tooling, then produce no-cost metadata qualification reports for A, B, C, and backup C. Do not bulk-download text or inspect source-C model behavior.
