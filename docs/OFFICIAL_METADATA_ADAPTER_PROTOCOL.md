# Official Metadata Adapter Protocol

**Status:** Stage 0 metadata qualification  
**Authority:** subordinate to `DATA_POLICY.md`, `DATA_SOURCE_ADR.md`, `SOURCE_METADATA_PROTOCOL.md`, and the source-C firewall  
**Canonical implementation:** `src/chronopersona/official_metadata_adapters.py`

## Purpose

The adapters qualify official source metadata without silently crossing into corpus acquisition. They answer narrow questions:

- Does the official interface expose a native item identity?
- Does it expose a production, submission, revision, or publication timestamp with known semantics?
- Can historical-version integrity be established or bounded?
- Is item-level licensing visible?
- Which metadata strata appear viable for a later bounded content review?
- Which files would a future, separately authorized acquisition need?

They do **not** answer whether a document is scientifically suitable, uncontaminated, human-authored, topically matched, or legally redistributable as training text.

## Binding rules

1. Metadata adapters must not emit titles, abstracts, descriptions, comments, post bodies, full text, or archive contents.
2. Missing dates remain `null` with a reason-coded exclusion. A sentinel date is prohibited.
3. OAI datestamps are retained as audit metadata and are not silently substituted for document-production dates.
4. Item-level license information is required for arXiv and PMC source-C qualification.
5. Wikimedia and Stack Exchange commands inspect file inventories only. They do not download history dumps or `.7z` archives.
6. Default command mode performs no network access.
7. A live request requires `--execute`, `--allow-network`, an explicit host allowlist, a response-byte limit, a timeout, a user agent, and an append-only access log.
8. Response pages are bounded independently. Resumption tokens do not authorize automatic unbounded crawling.
9. Source-C packets and unblinding keys are stored separately.
10. Source-C identity/date blinding does not by itself remove all leakage: categories, set names, and source-specific metadata require review before a packet is released to a blinded reviewer.

## Supported interfaces

### arXiv OAI `arXivRaw`

The adapter parses OAI records using the `arXivRaw` metadata prefix and retains:

- OAI identifier and datestamp;
- native arXiv identifier;
- initial submission date when supplied by `created`;
- update metadata;
- version indicator;
- subject categories;
- item-level license locator;
- metadata and source-package locators.

It deliberately omits title, authors, comments, journal reference, and abstract text.

A record is not eligible for bounded review when its native submission date, version count, or item-level license is unresolved. Multi-version records are excluded from the provisional single-version source-C stratum.

### PMC OAI Dublin Core

The adapter parses PMC OAI Dublin Core metadata and retains:

- OAI identifier and datestamp;
- PMC identifier;
- all date values as audit metadata;
- the earliest parseable date as a provisional production timestamp;
- item-level rights values;
- coarse resource types.

The adapter never replaces a missing `dc:date` with `1900-01-01`, `1970-01-01`, the OAI datestamp, or the retrieval date.

Dublin Core metadata alone does not establish historical full-text version integrity. Every parsed PMC record therefore remains excluded under `historical-version-integrity-unverified` until a later adapter proves that the content version corresponding to the period is recoverable.

### Wikimedia `dumpstatus.json`

The adapter returns only page-history archive inventory entries whose filenames contain `pages-meta-history` and use an expected archive suffix. It records:

- file name;
- resolved locator;
- declared byte size;
- available SHA-1 or MD5 identity;
- dump job and status.

The inventory is not permission to fetch the files. Any future acquisition must separately freeze the project, dump date, file list, total bytes, hashes, storage margin, extraction method, and attribution plan.

### Stack Exchange Internet Archive metadata

The adapter parses the Internet Archive metadata response for the Stack Exchange dump item and returns only allowlisted `.7z` site archives. It records:

- site filename;
- file locator;
- byte size;
- available hashes;
- source, format, and modification metadata.

The allowlist is mandatory for the eventual source-B panel. Inventory inspection does not authorize downloading any archive.

## Canonical local-fixture examples

```powershell
python scripts/audit_official_source_metadata.py arxiv `
  --input tests/fixtures/official_metadata/arxiv-oai-arxivraw.xml `
  --execute `
  --max-records 2

python scripts/audit_official_source_metadata.py pmc `
  --input tests/fixtures/official_metadata/pmc-oai-dc.xml `
  --execute `
  --max-records 2

python scripts/audit_official_source_metadata.py wikimedia `
  --input tests/fixtures/official_metadata/wikimedia-dumpstatus.json `
  --base-url https://dumps.wikimedia.org/enwiki/20130101 `
  --execute `
  --max-records 10

python scripts/audit_stackexchange_inventory.py `
  --input tests/fixtures/official_metadata/stackexchange-archive-metadata.json `
  --archive-base-url https://archive.org/download/stackexchange `
  --allowed-site gardening.stackexchange.com `
  --execute
```

These commands parse committed fixtures and perform no network request.

## Live bounded request pattern

A live metadata request must be intentional and small:

```powershell
python scripts/audit_official_source_metadata.py arxiv `
  --url "<OFFICIAL-BOUNDED-OAI-URL>" `
  --execute `
  --allow-network `
  --allowed-host export.arxiv.org `
  --max-bytes 4194304 `
  --max-records 100 `
  --timeout-seconds 30 `
  --access-log artifacts/local/access/arxiv-oai.jsonl `
  --output artifacts/local/metadata/arxiv-page-001.json
```

The access log stores:

- start and completion time;
- host;
- sanitized endpoint shape with query values removed;
- status code;
- response size and SHA-256;
- response content type;
- configured byte and timeout bounds;
- user agent.

It does not store the original query values. The output artifact retains the response-derived record metadata required for audit.

## Source-C blinding

To create a source-C review packet:

```powershell
python scripts/audit_official_source_metadata.py arxiv `
  --input artifacts/local/raw-metadata/arxiv-bounded.xml `
  --execute `
  --blind-source-c `
  --blinding-secret-file artifacts/local/secrets/source-c.bin `
  --unblinding-key artifacts/local/source-c/key.json `
  --output artifacts/local/source-c/packet.json
```

The review packet removes:

- native item identifiers;
- native timestamps;
- raw date and OAI identity fields;
- usable metadata and content locators.

The unblinding key restores those fields and must not be shared with the blinded reviewer. Both artifacts carry deterministic hashes linking the key to the packet.

Before real source-C review, additionally inspect retained categories and source metadata for date-identifying or event-identifying leakage. The current blinding helper is a technical safeguard, not a complete blinded-review protocol by itself.

## Validation

Offline CI uses frozen interface fixtures. It must verify:

- no document text is emitted;
- native date semantics are preserved;
- missing PMC dates remain null;
- multi-version arXiv records are excluded;
- only history files are selected from Wikimedia inventory;
- only allowlisted `.7z` files are selected from Stack Exchange inventory;
- source-C packet and key are deterministic and separate;
- live permissions are independent from execution permissions;
- denied hosts fail before a network request.

## Exit criteria

The adapter layer is complete when:

- all four interface fixtures pass offline tests;
- every live command defaults to plan mode;
- source-C locators and identities can be blinded;
- access logs are bounded and sanitized;
- real bounded responses can be transformed into source-neutral metadata manifests;
- no missing-date sentinel or silent timestamp substitution remains;
- a reviewed PR merges with Python 3.11 and 3.12 CI passing.
