# Content Integrity Protocol

**Version:** v0
**Status:** development tooling
**Scientific disposition:** triage only

## 1. Purpose

This protocol qualifies content-bearing candidate manifests before any adaptation dataset can be frozen. It detects and records:

- byte-identical records;
- records that become identical after the frozen normalization;
- high-overlap lexical near duplicates;
- overlap between adaptation and evaluation text;
- narrow phrases directly associated with evaluation constructs;
- cross-source, cross-era, cross-role, and held-out-source boundary crossings.

It does not decide whether two texts are semantically equivalent, whether a source directly teaches a behavior, or whether a record should be excluded. Those decisions require reviewed source context and belong in a later derived-data decision artifact.

The committed fixture is synthetic and redistributable. No real source text is included.

## 2. Separation of metadata and content

Source qualification metadata remains governed by `source_metadata.py`. This content layer uses a separate JSONL manifest whose records point to local UTF-8 files.

Raw text is never embedded in the manifest or in audit reports. The manifest records only:

- stable record, role, source, era, and holdout identities;
- safe relative content path;
- raw and normalized SHA-256;
- byte and word counts;
- license, rights, and authorship status;
- fixture, eligibility, exclusion, and structured metadata fields.

The validator recursively rejects common raw-text fields inside `metadata`.

## 3. Manifest roles

### Adaptation

- source family must be A, B, or C;
- era must be `early` or `late`;
- A and B must be `exploratory`;
- C must be `confirmatory-held-out`.

A production record marked `eligible` must have eligible rights and human authorship. A synthetic fixture can never be marked scientifically eligible.

### Evaluation

Evaluation records use:

```text
role = evaluation
source_family = EVAL
era_window = none
holdout_status = not-applicable
```

### Control and calibration

Control and calibration records use their dedicated source families, no era, and no holdout role.

## 4. Frozen normalization

Version `nfkc-casefold-words-v1` performs:

1. Unicode NFKC normalization;
2. Unicode case folding;
3. deterministic word extraction;
4. single-space joining.

The manifest stores both raw-content and normalized-content hashes. Execution recomputes:

- raw SHA-256;
- normalized SHA-256;
- exact byte count;
- normalized word count.

Any mismatch aborts the audit.

Normalization is deliberately conservative. It does not remove stopwords, stem words, translate text, normalize named entities, or use a language model.

## 5. Path and file boundaries

Content paths must be relative and remain under the explicit content root. The executor rejects:

- absolute paths and Windows drive paths;
- POSIX or Windows-style parent traversal;
- backslash-separated or non-canonical relative paths;
- paths escaping after resolution;
- symbolic-link components;
- missing files;
- empty files;
- NUL bytes;
- non-UTF-8 files;
- files with no visible normalized words.

The same content path cannot appear in two manifest records. Duplicate content must be represented by separate files and will be detected by content hashes.

## 6. Exact duplicate channels

### Raw exact

Records sharing the same raw SHA-256 form a raw-exact cluster.

### Normalized exact

Records sharing the same normalized SHA-256 form a normalized-exact cluster. Raw exact copies will also appear here. This is intentional: raw equality is a stronger subtype of normalized equality.

Each cluster reports record identity and whether it crosses:

- source family;
- era;
- role;
- holdout boundary.

No text excerpt is emitted.

## 7. Near-duplicate triage

The v0 near-duplicate detector is deterministic lexical triage:

1. produce frozen word shingles;
2. create candidate pairs from shared-shingle buckets;
3. create additional candidates from fixed-width 64-bit SimHash bands;
4. suppress buckets larger than the frozen maximum;
5. fail closed if the frozen candidate-pair cap is exceeded;
6. verify candidates with exact shingle Jaccard;
7. omit normalized-exact pairs from the near-duplicate list.

The report retains candidate methods, shingle counts, and Jaccard. It does not call these pairs semantic duplicates.

The fixture configuration uses small thresholds only to exercise the machinery. Production thresholds must be selected before inspecting outcome-sensitive model behavior and validated against manually labeled source samples.

## 8. Evaluation exposure

Every evaluation record is compared with every non-evaluation record using frozen word n-grams.

A pair is flagged when:

- the normalized evaluation text is an exact substring of the source text; or
- minimum shared n-grams are present and either Jaccard or evaluation-side containment exceeds its frozen threshold.

The report records overlap counts and scores but no text.

This is lexical exposure screening, not a complete contamination guarantee. Later production work still requires:

- prompt and continuation phrase searches;
- template and benchmark-solution searches;
- near and semantic similarity under reviewed methods;
- source-specific direct-exposure review.

## 9. Direct construct patterns

`evaluations/exposure/direct-patterns-v0.json` contains narrow literal phrase cues grouped into:

- evidence integration;
- procedural trade-offs;
- secure-system decisions.

The registry is `development` and `triage-only`. Matches report pattern IDs and categories, not source excerpts.

A match does not establish direct teaching. Absence of a match does not establish far transfer. The pattern registry is only an auditable way to prioritize review.

## 10. Held-out source C

The tool may inspect synthetic source-C fixtures without authorization. Any non-fixture source-C adaptation record requires a separate authorization object **before content files are opened**.

The authorization must bind:

- exact content-manifest SHA-256;
- source family C;
- the complete v0 integrity-audit scope;
- named authorizer and timezone-aware time;
- confirmation that no behavioral outcomes were inspected.

This authorizes content-integrity screening only. It does not authorize:

- evaluation construction from C;
- temporal-direction estimation from C;
- dose, threshold, rescue, or hyperparameter selection using C;
- source-C model scoring;
- unblinding source-C temporal results.

Source-C review packets and locator access remain governed by the separate source-C firewall.

## 11. Commands

### Structure-only plan

```powershell
python scripts/validate_content_manifest.py `
  --manifest <manifest.jsonl> `
  --content-root <documents-directory>
```

The default does not open document files.

### Execute identity validation

```powershell
python scripts/validate_content_manifest.py `
  --manifest <manifest.jsonl> `
  --content-root <documents-directory> `
  --execute `
  --output <validation-report.json>
```

### Plan integrity audit

```powershell
python scripts/audit_content_integrity.py `
  --manifest <manifest.jsonl> `
  --content-root <documents-directory> `
  --config configs/content-integrity-v0.json
```

### Execute integrity audit

```powershell
python scripts/audit_content_integrity.py `
  --manifest <manifest.jsonl> `
  --content-root <documents-directory> `
  --config configs/content-integrity-v0.json `
  --execute `
  --output <integrity-report.json>
```

For real source C, add:

```powershell
--holdout-authorization <authorization.json>
```

## 12. Report guarantees

The deterministic report includes:

- exact input hashes;
- normalization version;
- source-C authorization identity where required;
- aggregate counts;
- exact raw and normalized clusters;
- verified lexical near pairs;
- evaluation-exposure pairs;
- direct-pattern record matches;
- source-pair counts;
- explicit limitations;
- canonical report hash.

It guarantees:

- no source text excerpts;
- no semantic-similarity claim;
- no automatic exclusion;
- no scientific eligibility decision;
- no network access.

Reordering manifest records or direct patterns must not change the report.

## 13. Fixture coverage

The committed synthetic fixture intentionally contains:

- one cross-source, cross-era raw copy;
- one cross-source normalized copy;
- two high-overlap near pairs;
- one near pair crossing into held-out C;
- one exact evaluation substring exposure;
- one adaptation record matching two evidence-integration cues;
- clean evaluation, control, calibration, and unique held-out records.

The fixture exists to prove detection and failure behavior. Its counts are not estimates of real corpus quality.

## 14. Stop rules

Do not freeze a production data manifest when:

- any manifest identity fails;
- candidate-pair generation exceeds the frozen cap;
- source-C authorization is absent or mismatched;
- exact or near cross-source overlap is not dispositioned;
- evaluation exposure is not reviewed;
- direct-exposure rates are unknown;
- deduplication threshold sensitivity is not reported;
- source-level event and host concentration are not bounded;
- a derived exclusion manifest cannot be reproduced from reason codes.

## 15. Next extension

This v0 milestone is intentionally dependency-free. Production extension should add, under separate review:

- streaming manifests and external sorting;
- stable exact and near-duplicate cluster IDs at corpus scale;
- source-aware revision/syndication/quotation handling;
- benchmark phrase and template registries;
- reviewed semantic-similarity screening;
- event, contributor, host, topic, and genre concentration;
- deterministic derived-data manifests with reason-coded exclusions;
- sensitivity reports over deduplication thresholds;
- integration with the immutable run registry merged in PR #20.
