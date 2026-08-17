# Source Adapter and Held-Out Review Protocol

**Status:** Stage 0 development  
**Scope:** metadata and archive-inventory qualification only  
**Bulk corpus acquisition:** not authorized

This protocol converts external archive interfaces into source-neutral,
metadata-only evidence. It does not retrieve document bodies, build a training
corpus, freeze the era windows, or establish that any source is suitable for
CSTG.

## 1. Common operating boundary

Every adapter has three modes:

1. **Plan** — the default. Prints the exact endpoint, limits, and rules without
   network access.
2. **Frozen-input parse** — reads a saved XML or JSON response and produces a
   deterministic metadata or inventory artifact.
3. **Bounded live execution** — requires both `--execute` and
   `--allow-network`, enforces a response-size ceiling and timeout, and still
   retrieves metadata only.

The adapters never authorize archive or source-text downloads. A live metadata
response is not a corpus sample.

Generated metadata must pass the common contract in
`src/chronopersona/source_metadata.py`. Archive inventories must pass
`src/chronopersona/source_inventory.py`.

## 2. arXiv two-stage metadata qualification

arXiv needs two distinct interfaces because one interface cannot safely do both
historical candidate selection and rights/version qualification.

### 2.1 Submitted-date candidate enumeration

**Endpoint:** `https://export.arxiv.org/api/query`

The Atom API supports a `submittedDate` search expression. The candidate
adapter therefore enumerates records over an exact category list and date
interval, sorted by submission date.

For each result, it uses the Atom `<published>` value as the first-version
submission timestamp and stores `<updated>` separately. A version suffix in the
Atom entry URL is stripped before the base identifier is used for subsequent
OAI enrichment.

Candidate records remain `unresolved` because the API feed does not establish:

- complete version count;
- item-level reuse license;
- final eligibility under the single-version and CC0/CC BY rules.

Titles, summaries, and author fields are hashed and counted rather than retained
as prose. Forbidden cross-list categories are recorded immediately.

Plan:

```powershell
python scripts/audit_arxiv_api_candidates.py `
  --start-date 2012-01-01 `
  --end-date 2013-12-31
```

Frozen fixture or response:

```powershell
python scripts/audit_arxiv_api_candidates.py `
  --input tests/fixtures/arxiv_api_sample.xml `
  --start-date 2012-01-01 `
  --end-date 2019-12-31 `
  --output artifacts/local/source-audit/arxiv-candidates.jsonl `
  --summary-output artifacts/local/source-audit/arxiv-candidates-summary.json
```

The live API path allows at most 100 results per page, at most 1,000 records per
bounded invocation, and at least three seconds between requests.

### 2.2 Exact `arXivRaw` version and license enrichment

**Endpoint:** `https://oaipmh.arxiv.org/oai`

arXiv OAI-PMH datestamps represent last modification, not first submission.
The OAI interface is therefore **not** used to harvest an era by `from` and
`until`. It is used only for exact `GetRecord` enrichment of base IDs already
selected through the submitted-date API.

The `arXivRaw` record supplies:

- complete listed version history and first-version date;
- item license;
- categories and cross-lists;
- metadata hashes and counts.

A record is metadata-stage eligible only when:

- its first version lies in an era window;
- exactly one version exists;
- its item license is CC0 or CC BY;
- at least one category matches the descriptive-science allowlist;
- no category matches the cross-list denylist.

The denylist removes computing, economics, mathematics, quantitative finance,
statistics, and social-physics cross-lists even when an allowed category is
also present. This is a conservative direct-exposure control, not evidence that
the remaining material is behaviorally neutral.

Plan exact enrichment:

```powershell
python scripts/audit_arxiv_oai_metadata.py `
  --identifier 1301.00001
```

Frozen fixture or response:

```powershell
python scripts/audit_arxiv_oai_metadata.py `
  --input tests/fixtures/arxiv_oai_sample.xml `
  --output artifacts/local/source-audit/arxiv-enriched.jsonl `
  --summary-output artifacts/local/source-audit/arxiv-enriched-summary.json
```

Live enrichment accepts base IDs only, permits at most 100 IDs in one bounded
invocation, and waits at least three seconds between exact requests.

## 3. PMC OAI-PMH metadata candidate audit

### Endpoint

`https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`

The adapter uses the current PMC OAI-PMH service and defaults to the
`pmc-open` set. The retired `/pmc/oai/oai.cgi` endpoint is not pinned.

PMC OAI `from` and `until` filter PMC release or update datestamps, not article
publication dates. Dublin Core `dc:date` is associated with an article lifecycle
 event and is not assumed to be a publication date.

The parser:

- omits records with no usable `dc:date` rather than introducing an epoch or
  other synthetic date;
- records day, month, year, or datetime precision;
- computes a **candidate** era window for diagnostics;
- keeps the top-level era assignment `unresolved` until a publication-specific
  source confirms the timestamp;
- keeps historical-version status unresolved.

Dublin Core metadata alone cannot promote a PMC article into backup source C.
A later approved step must establish both authoritative publication timing and
historical JATS version integrity.

Only item-level CC0 or CC BY records may later become eligible. Other Creative
Commons variants, custom statements, and absent rights remain excluded or
unresolved.

Plan:

```powershell
python scripts/audit_pmc_oai_metadata.py `
  --from-date 2012-01-01 `
  --until-date 2013-12-31
```

Frozen fixture or response:

```powershell
python scripts/audit_pmc_oai_metadata.py `
  --input tests/fixtures/pmc_oai_sample.xml `
  --from-date 2012-01-01 `
  --until-date 2019-12-31 `
  --output artifacts/local/source-audit/pmc.jsonl `
  --summary-output artifacts/local/source-audit/pmc-summary.json
```

## 4. Wikimedia history inventory

### Endpoint shape

`https://dumps.wikimedia.org/<project>/<YYYYMMDD>/dumpstatus.json`

The mutable `latest` alias may be inspected in plan mode only. Any parsed or
live inventory requires an explicit eight-digit dump snapshot. The
`dumpstatus.json` schema-version field is recorded separately and is never used
as the snapshot identity.

Only completed `pages-meta-history` files with a size, URL, and published hash
enter the inventory. Waiting, failed, current-page, and article-only outputs are
not treated as immutable history inputs.

This step records file count, total bytes, hashes, and a 25% storage margin. It
does not download the history archives and does not establish that revision
added-text reconstruction is feasible.

Plan:

```powershell
python scripts/audit_wikimedia_inventory.py
```

Pinned frozen response:

```powershell
python scripts/audit_wikimedia_inventory.py `
  --input tests/fixtures/wikimedia_dumpstatus_sample.json `
  --snapshot 20260101 `
  --inventory-output artifacts/local/source-audit/wikimedia-inventory.json `
  --summary-output artifacts/local/source-audit/wikimedia-summary.json
```

## 5. Stack Exchange legacy inventory

### Endpoint

`https://archive.org/metadata/stackexchange`

Stack Exchange stopped publishing new data dumps to Archive.org in 2024. The
Archive.org item is therefore treated as a frozen legacy inventory, not the
current official delivery mechanism. The adapter requires item metadata to
attribute the archive to Stack Exchange; a community mirror requires a separate
provenance and rights decision.

The adapter records per-site `.7z` sizes and hashes without downloading any
site archive. Snapshot identity uses the maximum validated numeric file mtime,
not lexical ordering. A later site-panel decision must be frozen independently
and must exclude technical, advice, policy, legal, medical, workplace, and
other direct-exposure domains.

Plan:

```powershell
python scripts/audit_stackexchange_inventory.py
```

Frozen response:

```powershell
python scripts/audit_stackexchange_inventory.py `
  --input tests/fixtures/stackexchange_archive_sample.json `
  --inventory-output artifacts/local/source-audit/stackexchange-inventory.json `
  --summary-output artifacts/local/source-audit/stackexchange-summary.json
```

## 6. Source-C locator firewall

`deterministic_audit_sample(..., hide_era_labels=True)` removes explicit era
labels and native timestamps, but its manager packet retains locators so
selected records can be resolved. That manager packet is **not reviewer-ready**.

Create the reviewer packet and protected access map:

```powershell
python scripts/prepare_source_review.py `
  artifacts/local/source-audit/source-c-sample-manager.json `
  --redaction-seed source-c-locator-firewall-v0 `
  --review-output artifacts/local/source-review/source-c-review.json `
  --access-map-output artifacts/local/source-review/source-c-access-map.json
```

The reviewer packet contains opaque `access_id` values and no native IDs,
locators, era labels, timestamps, obvious arXiv IDs, PMCIDs, or URL schemes.
The access map contains the locators and must remain protected and uncommitted.

Manager packets, reviewer packets, and access maps verify their canonical
self-hashes before use. A changed locator or review field invalidates the
artifact.

Record each access without storing source text:

```powershell
python scripts/log_source_access.py `
  --access-map artifacts/local/source-review/source-c-access-map.json `
  --access-id access-... `
  --locator-kind content `
  --reviewer internal-reviewer-1 `
  --purpose content-review `
  --accessed-at 2026-08-17T16:00:00Z `
  --outcome succeeded `
  --response-sha256 <64-hex-digest> `
  --response-bytes 12345 `
  --log artifacts/local/source-review/access-events.jsonl
```

Access events have an exact schema and self-derived ID. They record locator
hash, response hash, byte count, purpose, reviewer, canonical UTC time, and
outcome. They never record a locator, response body, or source text. Every
existing line is revalidated before a new event is appended, and duplicate or
tampered events fail closed.

## 7. CI and fixtures

CI uses only frozen fixtures under `tests/fixtures/`. It does not contact arXiv,
PMC, Wikimedia, Archive.org, or any corpus host. Live outputs must be created
locally, inspected, and committed only when they contain metadata or aggregate
evidence permitted by the source and held-out protocols.

The focused workflow covers:

- arXiv API candidate enumeration;
- exact arXivRaw enrichment;
- PMC unresolved lifecycle-date metadata;
- pinned Wikimedia inventories;
- legacy Stack Exchange inventories;
- source-C redaction, artifact tamper detection, and exact access-event schema.

## 8. What this milestone does not establish

This work does not establish:

- sufficient early/late volume;
- source continuity;
- a stable Stack Exchange site panel;
- Wikimedia revision-delta extraction quality;
- arXiv source-package accessibility or final version/license yield;
- PMC authoritative publication timing or historical version integrity;
- direct-exposure or contamination rates;
- human-authorship confidence at scale;
- legal permission to redistribute a derived corpus or model;
- final source assignments or era windows.

Those decisions require bounded live metadata evidence and manually reviewed
samples. Behavioral outcomes remain prohibited during source qualification.
