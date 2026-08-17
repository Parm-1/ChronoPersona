# Source Sample Protocol

**Status:** Stage 0 development protocol  
**Authorization:** metadata and bounded parser samples only  
**Bulk download:** not authorized

## 1. Objective

Determine whether the provisional A/B/C source architecture can produce legally usable, historically valid, source-distinct, matched era-window corpora without directly teaching the primary evaluation constructs.

This protocol does not build the training corpus. It produces evidence for a later source-freeze decision.

## 2. General rules

- Use official steward documentation and approved automated access paths.
- Start with metadata, inventory files, checksums, and bounded records.
- Do not scrape rendered public sites when an API, dump, OAI, FTP, or cloud service is specified.
- Do not download a complete corpus before measuring size, storage margin, parser cost, and rights distribution.
- Do not inspect model behavioral outcomes during source qualification.
- Preserve failed, excluded, missing, and ambiguous records.
- Every retained text record needs immutable source and transformation hashes.
- Source C remains under `HELD_OUT_SOURCE_PROTOCOL.md`.

## 3. Era-window candidates

Evaluate both:

### Two-year design

- early: 2012-01-01 through 2013-12-31;
- late: 2018-01-01 through 2019-12-31.

### One-year sensitivity candidate

- early: 2013-01-01 through 2013-12-31;
- late: 2019-01-01 through 2019-12-31.

A narrower design is preferred when it reduces event/topic mixture and still supports sufficient eligible tokens across A, B, and C.

Do not select between these using model behavior.

## 4. Metadata qualification packet

For each source/window produce:

- total record count;
- records with high-confidence eligible timestamps;
- records with recoverable historical text versions;
- item-level rights categories;
- human, bot, synthetic, transformed, and unknown provenance counts;
- source/native stratum counts;
- author or contributor concentration where permitted;
- document-length estimates;
- parser input format counts;
- direct-exposure metadata flags;
- event/entity concentration proxies;
- expected compressed and expanded storage;
- expected retrieval and request cost;
- records requiring manual review;
- unresolved blockers.

The packet contains aggregate metadata and identifiers. It does not need bulk full text.

## 5. Bounded sample design

After metadata qualification, draw a deterministic sample from each source/window.

### Initial target

Per source/window:

- 50 clearly eligible records;
- 25 records near a timestamp/version boundary;
- 25 records near a rights or exposure boundary;
- 25 records from high-volume topics/events;
- 25 randomly selected eligible records.

Maximum initial sample: 150 records per source/window before deduplication. This is a parser and audit sample, not a statistical training sample.

### Sampling identity

The sample is generated from:

- source-registry version and hash;
- metadata-manifest hash;
- frozen selection query;
- explicit seed;
- code revision.

Running the same sampler over the same metadata must produce the same identifiers.

## 6. Wikimedia sample

### Metadata stage

Use official dump inventories and bounded MediaWiki metadata to record:

- page/revision identifiers;
- namespaces;
- revision and parent IDs;
- revision timestamps;
- contributor and bot indicators;
- page move/deletion/revert metadata where available;
- compressed dump file identity and checksum.

Do not download the full English history dump during this stage.

### Text sample

Retrieve or extract only the files/records necessary for the deterministic sample.

For each sampled revision:

1. reconstruct parent and child article text;
2. normalize through a committed parser;
3. calculate added spans;
4. classify revert/reintroduction status;
5. remove templates, references, lists, and boilerplate;
6. record survival under the frozen persistence rule;
7. record rights and attribution lineage;
8. run exposure and duplicate diagnostics.

### Required report

- added versus inherited token ratio;
- reverts/reintroductions;
- bot and vandalism exclusions;
- parser failures;
- category/topic leakage risk;
- attribution completeness;
- eligible clean-token yield.

## 7. Stack Exchange sample

### Metadata stage

Use an official data-dump inventory or approved API metadata to select a frozen candidate site panel.

For each site/window record:

- launch and continuous-coverage status;
- post and PostHistory counts;
- question/answer proportions;
- initial-version recoverability;
- post creation dates;
- applicable contribution license distribution;
- deletion/migration/edit burden;
- tag and topic distribution;
- author concentration where permitted;
- compressed dump size and checksum.

### Text sample

For sampled posts:

1. reconstruct the initial title/body;
2. distinguish question and answer strata;
3. remove code, quotations, links, signatures, and boilerplate;
4. record site, post, version, contributor, date, and license lineage;
5. identify automated, spam, migrated, deleted, and uncertain records;
6. run exposure and duplicate diagnostics.

### Required report

- percentage of current bodies differing from initial versions;
- initial-version recovery rate;
- license versions by window;
- site continuity and concentration;
- deleted/migrated record burden;
- direct advice/procedure exposure;
- eligible clean-token yield.

## 8. arXiv held-out source sample

Follow the holdout firewall.

### Metadata stage only

Use the official API or metadata listings to estimate:

- first-submission date;
- version count;
- item-level license;
- category;
- title and abstract length;
- author count;
- source-package availability;
- single-version CC0/CC BY counts by window/category;
- expected source-package size and requester-pays cost.

Do not use source C to write evaluation items or select expected temporal directions.

### Bounded source sample

A bounded sample can be retrieved only after:

- metadata counts demonstrate feasible volume;
- requester-pays and storage cost are explicitly approved if nonzero;
- source identifiers and versions are frozen;
- the review packet hides era labels where practical;
- direct-exposure classifier and thresholds are frozen from non-C material.

For each sampled record verify:

- exactly one version;
- eligible first/only submission date;
- CC0 or CC BY license;
- source content hash;
- parser success;
- no later-version text;
- direct-exposure class;
- third-party or quoted-text burden.

### Required report

Only aggregate and blinded quality findings before confirmation:

- eligible counts and token estimates;
- categories and concentration;
- license distribution;
- single-version rate;
- parser success;
- exposure classifier distribution;
- manual eligibility/error rates;
- retrieval/storage cost.

## 9. PMC backup sample

PMC remains untouched except for metadata and feasibility work.

Record:

- item-level license;
- publication and PMC update dates;
- article/version identifiers;
- correction/replacement indicators;
- JATS availability;
- overlap with preprint/arXiv records;
- CC0/CC BY counts by window and proposed stratum;
- approved OA retrieval path.

A source-text sample requires evidence that the sampled XML corresponds to the eligible historical version or has not been updated after the window.

## 10. Direct-exposure audit

For each source/window sample run:

1. deterministic metadata and lexical exclusions;
2. exact and n-gram search against evaluation/calibration text;
3. semantic similarity search;
4. frozen direct-exposure classifier;
5. blinded manual review.

Every record receives:

- exposure level;
- score and threshold version;
- manual label when sampled;
- exclusion reason;
- unresolved status where evidence is insufficient.

Unresolved records are ineligible for confirmatory data.

## 11. Cross-source overlap

Check:

- exact content hashes;
- normalized paragraph hashes;
- near-duplicate clusters;
- quotations and citations;
- Stack Exchange links/quotes from Wikimedia or scientific sources;
- Wikimedia references or copied passages;
- arXiv/PMC preprint-journal duplicates;
- common abstracts, summaries, and press releases.

A record cluster belongs to one source family or is excluded from the primary analysis. Do not expose the same text through multiple supposed independent interventions.

## 12. Event and topic concentration

For each source/window report:

- top entities and n-grams;
- topic mixture;
- token share of top events/topics;
- contributor/publisher/site concentration;
- sensitivity after capping dominant clusters;
- A/B/C differences.

The final era windows cannot be chosen because a specific event produces a desired behavioral pattern.

## 13. Storage and cost gate

Before moving beyond samples, estimate:

- compressed download size;
- expanded source size;
- normalized text size;
- manifest and index size;
- temporary extraction space;
- deduplication index space;
- checkpoint-independent cache space;
- request/download charges;
- cleanup and recovery plan;
- 25% minimum free-space margin after peak extraction.

The current external-spend authorization is CAD $0. Requester-pays or cloud retrieval is blocked until a specific cost is presented and approved.

## 14. Qualification decisions

Each source concludes as one of:

- `qualified`;
- `qualified-with-redesign`;
- `blocked`;
- `not-suitable`.

The decision report states:

- evidence;
- retained stratum;
- exclusions;
- unresolved risks;
- storage/cost;
- token yield;
- source independence;
- domain exposure;
- exact next action.

## 15. A/B/C freeze gate

Freeze the source architecture only when:

- A and B each have both era windows and a common within-source sampling rule;
- C has sufficient held-out eligible volume;
- the backup C rule remains viable;
- timestamps and versions are auditable;
- rights and attribution are implementable;
- direct exposure is below the frozen tolerance;
- cross-source overlap is bounded;
- topic/event/source concentration is acceptable;
- parser and exclusion pipelines are deterministic;
- storage and acquisition remain authorized;
- no model behavioral outcome influenced selection.

## 16. Current authorization

Authorized now:

- official documentation research;
- metadata queries that do not incur a charge;
- dump inventories and checksums;
- bounded no-cost parser samples;
- aggregate reports and manifests.

Not authorized now:

- bulk Wikimedia, Stack Exchange, arXiv, or PMC text acquisition;
- requester-pays arXiv source download;
- training on source samples;
- source-C behavioral scoring;
- public redistribution;
- nonzero data-access spending.
