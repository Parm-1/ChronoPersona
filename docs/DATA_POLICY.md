# Data Policy

## Scope

This policy applies to every document considered for:

- public-checkpoint audit support;
- synthetic calibration;
- naturalistic continued pretraining;
- evaluation construction;
- common post-training;
- mechanism analysis.

ChronoPersona's causal intervention depends on publication or revision time. Timestamp semantics are part of the treatment, not ordinary metadata.

## Repository boundary

Do not commit:

- raw copyrighted corpora;
- private data;
- credentials;
- model checkpoints or weights;
- restricted outputs;
- caches;
- paid datasets.

The repository may contain:

- source and license audits;
- acquisition and transformation code;
- small redistributable synthetic fixtures;
- immutable manifests when permitted;
- hashes and aggregate statistics;
- evaluation materials with clear rights;
- data cards and lineage records.

Reproducible runs consume versioned manifests, not undisclosed local directories.

## Required record fields

Every candidate document record should include:

- `document_id` — stable project identifier;
- `source_family` — experimental family A, B, C, control, or calibration;
- `source_id` — collection, publisher, archive, or platform;
- `source_item_id` — native item/revision identifier when available;
- `locator` — URL, archive key, dataset row, or auditable reference;
- `owner_or_steward`;
- `license`;
- `license_locator`;
- `permitted_use`;
- `attribution_requirement`;
- `redistribution_status`;
- `authorship_provenance` — human, synthetic, mixed, transformed, bot, unknown;
- `authorship_confidence`;
- `published_at` or `revision_at`;
- `time_precision`;
- `timestamp_semantics` — publication, revision, upload, crawl, capture, event, inferred;
- `timestamp_source`;
- `timestamp_confidence`;
- `retrieved_at`;
- `language`;
- `domain`;
- `genre`;
- `host_or_publisher`;
- `contributor_type`;
- `content_sha256`;
- `raw_content_sha256` when transformations occur;
- `tokenizer_id`;
- `token_count`;
- `dedup_cluster_id`;
- `transformation_chain`;
- `era_window`;
- `eligible`;
- `exclusion_reason`;
- `manual_review_status`.

Frozen schemas may add fields but must not silently change their meaning.

## Timestamp rules

### Native high-confidence time

Prefer:

- authoritative publication timestamps;
- authoritative revision timestamps;
- repository-native item creation dates;
- official issue or release dates;
- archive evidence that tightly bounds publication before the era cutoff.

### Medium confidence

Examples:

- documented dataset timestamps;
- authoritative month or year dates;
- consistent indirect records with a conservative interval.

### Low confidence

Examples:

- crawl time without publication evidence;
- search-engine dates;
- filesystem metadata;
- copyright footers;
- undated reposts;
- retrospective pages;
- inferred dates from prose;
- archive captures far after probable publication;
- model guesses.

Low-confidence records are excluded from confirmatory era branches unless a frozen sensitivity analysis studies them separately.

A document about 2013 that was published in 2020 is a 2020 document. Event time is not publication time.

Common Crawl crawl date must not silently substitute for publication date in the naturalistic causal experiment.

## Era-window eligibility

The frozen era rule controls eligibility.

For each record:

1. determine the relevant native time semantics;
2. assign a conservative date or interval;
3. apply the frozen window;
4. record confidence and uncertainty;
5. preserve ineligible and unresolved counts.

Do not infer eligibility from URL patterns, current-page metadata, event dates, or model classification.

When a date interval overlaps a boundary, the record is unresolved or excluded unless the frozen protocol states a conservative rule.

## Source-family independence

The central claim requires unrelated source families.

Source families must be assessed for shared:

- website or host;
- publisher;
- institution;
- contributor population;
- genre;
- editorial process;
- syndication;
- upstream text;
- data vendor;
- extraction pipeline;
- topic concentration.

A and B should not be treated as independent merely because they have different URLs.

Source C is selected during Stage 0 but remains held out from:

- item construction;
- hypothesis direction;
- dose and hyperparameter selection;
- meaningful-effect threshold selection;
- mechanistic layer selection.

## Source matching

Within each source family, match or explicitly model:

- target-token count;
- document count;
- length;
- host or publisher;
- genre;
- topic;
- readability;
- sentiment;
- toxicity;
- quality;
- duplicate density;
- language;
- contributor type;
- authorship provenance;
- timestamp confidence;
- bot content;
- event concentration.

Across branches, hold training exposure fixed according to the frozen experiment specification.

Do not fill the early condition with one genre and the late condition with another and call the result temporal.

## Human versus synthetic provenance

Modern text may be synthetic, transformed, bot-authored, or mixed.

Every selected source needs:

- a provenance policy;
- detection or metadata method;
- uncertainty estimate;
- exclusion or stratification rule;
- manual audit.

Synthetic or transformed text is not silently pooled with natural human text. If used, it becomes a named channel or sensitivity condition.

## Domain exposure

Maintain a matrix classifying each source/evaluation pair as:

- direct;
- structurally related;
- indirect;
- plausibly absent;
- unknown.

Primary CSTG task families may not be directly taught by any included adaptation source.

### Secure-system exclusions

Exclude source code, cybersecurity tutorials, vulnerability reports, secure-coding instruction, benchmark solutions, and direct architecture-answer material.

### Evidence-integration exclusions

Exclude calibration tutorials, Bayesian instruction, source-reliability teaching, misinformation benchmarks, and copies of evaluation templates.

### Procedural-trade-off exclusions

Exclude copied survey items, direct benchmark dilemmas, and targeted ideological text selected to manufacture a desired direction.

## Deduplication

Deduplicate:

- exact content;
- near-duplicate content;
- repeated revisions;
- syndicated copies;
- quotations;
- boilerplate;
- adaptation/evaluation overlap;
- cross-source overlap;
- train/development/confirmation overlap.

Use documented thresholds and stable cluster identifiers. Keep related records within one split when possible.

Never silently delete. Record counts, cluster membership, reason codes, and sensitivity to thresholds.

For Wikimedia-style sources, prefer added-text deltas or another method that prevents repeated full-snapshot text from dominating exposure.

## Temporal leakage

Audit using:

- post-window entities and phrases;
- retrospective or updated-page markers;
- archive and timestamp inconsistencies;
- unexpected n-gram and semantic overlap;
- source revision histories;
- stratified manual review;
- model-assisted triage followed by human verification.

A classifier score cannot by itself mark a record eligible.

Record false positives, false negatives, unresolved cases, and manual-review sampling.

## Event concentration

A period contrast can be dominated by one election, crisis, product launch, war, or scandal.

For each source/window:

- identify high-volume events;
- quantify token concentration;
- compare source families;
- define caps, stratification, or sensitivity exclusions;
- preserve the full and event-balanced views.

Do not choose windows after behavioral outcomes to reduce or increase an effect.

## Licensing and rights

Technical access is not permission to train, transform, or redistribute.

For each source, record:

- exact license or terms;
- owner/steward;
- acquisition method;
- permitted research use;
- model-training status when specified;
- derivative-data treatment;
- attribution;
- share-alike or notice obligations;
- redistribution;
- unresolved questions.

Do not assume:

- public access permits redistribution;
- an entire repository has one license;
- government-hosted text is necessarily a government work;
- model weights derived from licensed text have an obvious legal status.

Exclude materially unresolved sources from confirmatory or public release. Seek qualified legal review before releasing mixed-source corpora or weights when needed.

## Privacy and sensitive content

Exclude:

- credentials;
- private correspondence;
- doxxing;
- private user data;
- sensitive personal records;
- restricted datasets;
- unnecessary identifiers.

Document handling of hate, sexual, violent, medical, political, and otherwise sensitive text.

Historical authenticity does not override modern privacy or safety obligations.

## Transformations

Every transformation records:

- input hashes;
- code revision;
- command/configuration;
- model/teacher revision when synthetic transformation is used;
- random seed;
- output hashes;
- records added, changed, or excluded;
- whether meaning, register, timestamps, or provenance were altered.

Do not use an LLM transformation to “clean” a historical corpus without treating the teacher and transformation as causal variables.

## Immutability and lineage

A frozen manifest receives:

- versioned filename;
- SHA-256;
- generation command;
- code revision;
- source snapshot or stable locators;
- row and token counts;
- exclusion summary;
- deduplication summary;
- timestamp-confidence distribution;
- authorship-provenance distribution;
- rights summary;
- topic/genre/source balance;
- event-concentration report;
- manual-review record.

Corrections create a new manifest version. Never mutate an input manifest used by a completed run.

## Publication

Publish code, schemas, hashes, aggregate statistics, data cards, and redistributable records where possible.

When text cannot be redistributed, publish enough provenance, filtering, and transformation detail for independent audit without exposing restricted content.

Data limitations belong in the main paper, not only an appendix.
