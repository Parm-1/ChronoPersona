# Data Policy

## Scope

This policy applies to every document considered for adaptation, evaluation construction, calibration, or analysis.

ChronoPersona's central intervention depends on time. Timestamp quality is therefore part of the experimental treatment, not ordinary metadata.

## Repository boundary

Do not commit raw corpora, private data, model checkpoints, credentials, or generated outputs containing restricted text.

The repository may contain:

- data-source documentation;
- acquisition and transformation code;
- small synthetic fixtures;
- immutable manifests when redistribution is permitted;
- hashes and aggregate statistics;
- evaluation material with clear rights.

Local data paths are implementation details. Reproducible runs consume versioned manifests.

## Required manifest fields

Every eligible document record must include at least:

- `document_id` — stable project identifier;
- `source_id` — source collection or publisher identifier;
- `locator` — URL, archive key, dataset row ID, or other auditable locator;
- `license` — license or documented rights status;
- `permitted_use` — training, evaluation, redistribution, or internal analysis;
- `published_at` — normalized timestamp when available;
- `time_precision` — day, month, year, interval, or unknown;
- `timestamp_source` — publisher metadata, archive capture, dataset field, or manual inference;
- `timestamp_confidence` — `high`, `medium`, or `low`;
- `retrieved_at` — acquisition timestamp;
- `language`;
- `domain` — the project source stratum;
- `content_sha256`;
- `tokenizer_id`;
- `token_count`;
- `dedup_cluster_id`;
- `cutoff_eligible`;
- `exclusion_reason` when ineligible.

Additional fields may be added, but frozen manifests must not silently change semantics.

## Timestamp rules

### High confidence

A contemporaneous publication timestamp from an authoritative source, or an archive capture that reliably bounds publication before the cutoff.

### Medium confidence

A dataset timestamp with documented provenance, a month or year-level authoritative date, or multiple consistent indirect indicators.

### Low confidence

Search-engine dates, filesystem metadata, undated reposts, retrospective references, inferred dates from prose, or archive captures that occur long after probable publication.

Low-confidence documents are excluded from confirmatory temporal conditions unless a frozen sensitivity analysis explicitly studies them.

A page discussing 2008 but published in 2020 is a 2020 document. Topical date is not publication date.

## Cutoff eligibility

Eligibility is determined by the frozen cutoff rule and timestamp evidence. It must not be inferred from:

- file modification time;
- current page URL structure;
- copyright footer alone;
- the dates of events mentioned in the text;
- a model's guess.

When a document has a date interval, the conservative bound controls eligibility unless the experiment specification states otherwise.

## Source matching

Temporal conditions use the same target source-domain mixture. Document availability differences are reported rather than hidden.

Match or model at least:

- source domain;
- language;
- document length;
- quality-filter score;
- duplicate density;
- topic distribution;
- author or publisher concentration where measurable.

Do not fill an earlier corpus with one source type and a later corpus with another, then interpret the difference as time.

## Deduplication

Deduplicate exact content by hash and near-duplicates by a documented method. Preserve cluster identifiers so related documents can be kept within one split.

Deduplication must cover:

- within-condition duplicates;
- cross-condition duplicates;
- adaptation versus evaluation overlap;
- quotations and syndicated versions where practical;
- repeated boilerplate.

Never delete duplicates without recording counts and rules.

## Future leakage

Leakage audits should combine:

- post-cutoff named entities and events;
- retrospective phrases and updated pages;
- archive-capture timing;
- unexpected n-gram overlap;
- manual review of stratified samples;
- model-assisted triage followed by human verification.

A classifier score is not proof of eligibility. Record false positives, false negatives, and unresolved cases.

## Licensing and rights

Technical access does not imply permission to train or redistribute.

For each source, record:

- license or terms;
- acquisition method;
- permitted use;
- redistribution status;
- attribution requirements;
- unresolved legal or ethical questions.

Exclude sources with unresolved material restrictions from public or confirmatory releases. Seek qualified legal review before distributing a corpus assembled from mixed sources.

## Privacy and sensitive content

Minimize personal data. Exclude credentials, private communications, doxxing material, and unnecessary identifiers. Document handling of hate, sexual, violent, medical, or otherwise sensitive text.

Historical accuracy is not a reason to ignore modern safety and privacy obligations.

## Immutability and lineage

A frozen manifest receives:

- a versioned filename;
- SHA-256 hash;
- generation command and code revision;
- source snapshots or stable locators;
- row and token counts;
- exclusion summary;
- deduplication summary;
- timestamp-confidence distribution;
- license summary.

Corrections create a new manifest version. Never mutate an input manifest used by a completed run.

## Publication

Publish code, schema, hashes, aggregate statistics, and redistributable records where possible. When text cannot be redistributed, publish enough provenance and transformation detail for independent audit without exposing restricted content.

Data limitations belong in the main paper, not only in an appendix.
