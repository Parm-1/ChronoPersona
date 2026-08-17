# Source Adapter and Held-Out Review Protocol

**Status:** Stage 0 development  
**Scope:** metadata and archive-inventory qualification only  
**Bulk corpus acquisition:** not authorized

This protocol converts four external archive interfaces into source-neutral,
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

## 2. arXiv OAI-PMH adapter

### Endpoint

`https://export.arxiv.org/oai2`

The adapter requests `metadataPrefix=arXivRaw`. OAI `from` and `until` constrain
repository OAI datestamps; they are not silently treated as the historical
intervention date. Era membership is derived independently from the first
version date in the `arXivRaw` record.

### Qualification rules

A record is eligible at metadata stage only when:

- its first submission-version date lies in an era window;
- exactly one arXiv version exists;
- its item license is CC0 or CC BY;
- at least one category matches the frozen descriptive-science allowlist;
- no category matches the frozen cross-list denylist.

The denylist currently removes computing, economics, mathematics,
quantitative-finance, statistics, and social-physics cross-lists even when the
record also has an allowed category. This is a conservative direct-exposure
control, not a claim that the remaining categories are behaviorally neutral.

Titles, abstracts, and author fields are hashed and counted; they are not
retained in the metadata output.

### Commands

Plan:

```powershell
python scripts/audit_arxiv_oai_metadata.py `
  --from-date 2012-01-01 `
  --until-date 2013-12-31
```

Frozen fixture or response:

```powershell
python scripts/audit_arxiv_oai_metadata.py `
  --input tests/fixtures/arxiv_oai_sample.xml `
  --from-date 2012-01-01 `
  --until-date 2019-12-31 `
  --output artifacts/local/source-audit/arxiv.jsonl `
  --summary-output artifacts/local/source-audit/arxiv-summary.json
```

A live query requires a delay of at least three seconds between paginated
requests.

## 3. PMC OAI-PMH adapter

### Endpoint

`https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/`

The adapter uses the current PMC OAI-PMH service and defaults to the
`pmc-open` set. The old `/pmc/oai/oai.cgi` endpoint is not pinned in this
project.

PMC OAI `from` and `until` filter PMC release or update datestamps, not article
publication dates. The parser derives publication evidence from `dc:date` and
omits records for which no usable date exists. It never substitutes an epoch or
other synthetic timestamp.

### Qualification boundary

Dublin Core metadata does not establish historical JATS version integrity.
Every emitted PMC record remains `unresolved`, even when its item-level license
and subject stratum pass. PMC can become backup source C only after a separate,
approved distribution/version audit proves that the historical article object
is bounded.

Only item-level CC0 or CC BY records may later become eligible. Other Creative
Commons variants, custom statements, and absent rights remain excluded or
unresolved.

### Commands

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

### Commands

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
current official delivery mechanism. The adapter requires the item metadata to
attribute the archive to Stack Exchange; a community mirror requires a separate
provenance and rights decision.

The adapter records per-site `.7z` sizes and hashes without downloading any
site archive. A later site-panel decision must be frozen independently and must
exclude technical, advice, policy, legal, medical, workplace, and other direct
exposure domains.

### Commands

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

The access event records the locator hash, response hash, byte count, purpose,
reviewer, and outcome. It never records the locator itself or a response body.
Duplicate event IDs fail closed.

## 7. CI and fixtures

CI uses only the frozen fixtures under `tests/fixtures/`. It does not contact
arXiv, PMC, Wikimedia, Archive.org, or any corpus host. Live outputs must be
created locally, inspected, and committed only when they contain metadata or
aggregate evidence permitted by the source and held-out protocols.

## 8. What this milestone does not establish

This work does not establish:

- sufficient early/late volume;
- source continuity;
- a stable Stack Exchange site panel;
- Wikimedia revision-delta extraction quality;
- PMC historical version integrity;
- direct-exposure or contamination rates;
- human-authorship confidence at scale;
- legal permission to redistribute a derived corpus or model;
- final source assignments or era windows.

Those decisions require bounded live metadata evidence and manually reviewed
samples. Behavioral outcomes remain prohibited during source qualification.
