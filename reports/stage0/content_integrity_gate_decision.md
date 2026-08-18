# Content-Integrity Gate Decision

**Date:** 2026-08-18  
**Gate:** deterministic content manifests, lexical duplication, evaluation exposure, and held-out-boundary integrity  
**Decision:** **PASS at the development-fixture level; next real-source gate is externally blocked**

## Decision

Accept the dependency-light content-integrity implementation as the project’s Stage 0 development gate for bounded content samples.

Do not interpret this pass as evidence that the provisional Wikimedia, Stack Exchange, arXiv, or PMC corpora are clean, independent, sufficiently large, or scientifically eligible. Those claims require real, rights-qualified, version-bounded source samples that have not been acquired or authorized in this repository.

The next decision gate is therefore externally blocked on bounded real-source content access and held-out source-C authorization. No bulk acquisition or model training should begin.

## Evidence

The recovered implementation establishes deterministic machinery for:

- source-neutral content-bearing JSONL manifests with text stored outside Git;
- exact recomputation of raw byte hashes, normalized-text hashes, byte counts, and word counts;
- strict role, source-family, era, holdout, rights, authorship, fixture, eligibility, and exclusion fields;
- recursive rejection of embedded source text in metadata;
- portable relative-path validation covering POSIX traversal, Windows-style traversal, Windows drive paths, backslashes, non-canonical paths, symlinks, and root escape;
- exact raw duplicate clusters;
- exact normalized duplicate clusters;
- bounded lexical near-duplicate candidate generation using word shingles and SimHash bands, followed by exact Jaccard verification;
- hard bucket and candidate-pair limits with visible skipped-bucket diagnostics;
- literal evaluation-overlap screening;
- narrow direct-construct phrase triage from a versioned pattern registry;
- cross-source, cross-era, cross-role, and held-out-boundary flags;
- exact manifest-bound authorization before non-fixture source-C content is opened;
- deterministic reports that contain no source excerpts, semantic-equivalence claim, automatic exclusion, or scientific eligibility decision.

The committed synthetic fixture deliberately exercises raw duplicates, normalized duplicates, near duplicates, held-out-boundary overlap, evaluation exposure, direct-construct exposure, and clean records. It is validation infrastructure, not historical evidence.

## Recovery evidence

The accidental importer on `main` contained eight base64 fragments. Its normalized stream was 37,105 characters and could not decode directly.

Boundary analysis established one specific construction defect:

- fragment 0 contained 4,867 normalized characters;
- fragments 1 through 6 contained 4,606 characters each;
- fragment 7 contained 4,602 characters;
- fragment 0 had a 261-character overrun beginning at the common 4,606-character boundary;
- the first 257 characters of that overrun duplicated the beginning of fragment 1.

Trimming fragment 0 to the common boundary produced a 36,844-character base64 stream, a valid gzip payload, and a safe 46-member tar archive.

Recorded identities:

- original normalized stream SHA-256: `677fba3681a444d51a98778f0a6185bc0ed923641b0d40ad315522361728b81e`;
- recovered gzip SHA-256: `73545589b59a7250a8f11cc06ce809cec35b4fec71ac33268019643cf7d040c1`;
- recovered tar SHA-256: `730603e9f7d88d5530c9001f810f420210ae4f4c2ab62968739dc601ad41b8d6`.

The fragments and one-time importer were removed after recovery. The exact recovery record remains in `reports/stage0/content_integrity_bundle_recovery.json`.

## Validation

The recovered implementation passed, before its branch commit:

```text
python -m pip install -e ".[dev]"
python -m compileall -q src scripts
python -m chronopersona validate configs/pilot.toml
python -m chronopersona validate-models artifacts/manifests/MODEL_MANIFEST.json
python -m chronopersona validate-evaluation evaluations/registry/development-v0.jsonl
python scripts/validate_source_registry.py artifacts/manifests/SOURCE_REGISTRY.json
python scripts/build_synthetic_calibration.py --check
pytest -q
git diff --check
```

Independent review then found and corrected a Windows portability defect in path validation. The hardened implementation adds adversarial Windows parent-traversal and drive-path tests while preserving the existing POSIX traversal checks.

Final merge remains conditional on ordinary connector-authored Python 3.11/3.12 CI, the dedicated Content Integrity workflow, the run-registry smoke, and a clean pull-request diff.

## Claim boundary

This pass supports only:

> The repository has deterministic, fail-closed development tooling capable of auditing bounded content samples for several important forms of duplication and direct lexical exposure.

It does not support:

- a clean-corpus claim;
- semantic independence;
- source-family independence;
- acceptable real-source contamination rates;
- frozen exclusion thresholds;
- production-scale streaming behavior;
- source eligibility;
- a temporal behavioral effect;
- CSTG;
- a temporal prior.

## Residual risks

1. The v0 implementation loads bounded sample text into memory and is not a production-scale streaming pipeline.
2. Lexical similarity does not detect all semantic paraphrase, translated overlap, or shared latent procedures.
3. Large similarity buckets are skipped after a hard cap; the report preserves this diagnostic, but real thresholds require sensitivity analysis.
4. Direct-pattern matching is narrow, literal, and triage-only.
5. Event, host, contributor, topic, genre, quotation, revision, and syndication concentration remain separate audits.
6. Real source C must remain behind the existing locator firewall and exact authorization record.

## Next gate

The next gate is **bounded real-content qualification**:

- acquire only small, rights-qualified, version-bounded samples from provisional A and B;
- construct source-C material through the held-out authorization and access-log path;
- run exact/normalized duplicate, near-duplicate, evaluation-exposure, direct-construct, and cross-source overlap audits;
- manually review candidate pairs and threshold sensitivity;
- issue `qualified`, `qualified after redesign`, or `not suitable` decisions for each source family and era window.

This gate is externally blocked because the repository currently contains no authorized real source-text sample, no completed source-C access authorization, and no approved bulk or requester-pays acquisition. The project stops here rather than silently crossing that boundary.
