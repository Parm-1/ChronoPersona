# Source Metadata Protocol

**Status:** Stage 0 development  
**Purpose:** qualify source availability, timestamps, versions, rights, provenance, exposure, and sampling without acquiring a corpus

## 1. Metadata is not corpus text

A source metadata record must not contain:

- document body;
- abstract text;
- full text;
- source text;
- copied excerpts;
- model-ready content.

The validator recursively rejects common embedded-text field names through nested objects and arrays, including inside `source_metadata`. Source-specific metadata may contain counts, hashes, categories, version identifiers, flags, and locators, but not prose payloads hidden at any depth.

This boundary serves four purposes:

1. prevents a metadata audit from silently becoming a bulk-data acquisition;
2. preserves the source-C holdout firewall;
3. keeps Stage 0 storage requirements small;
4. separates feasibility evidence from later corpus rights and transformation decisions.

## 2. Record identity

Every JSONL record contains:

- `schema_version`;
- project `record_id`;
- source-registry `source_id`;
- native item/version identifier;
- native timestamp and timestamp semantics;
- derived era window;
- version count and historical-version status;
- item-level rights status, license identifier, and locator;
- authorship provenance;
- source categories or strata;
- manual-review strata;
- metadata and possible content locators;
- `content_retrieved = false`;
- eligibility and reason-coded exclusions;
- source-specific non-text metadata.

The exact metadata file bytes receive a SHA-256. Deterministic summaries and samples record that hash.

## 3. Native timestamp requirements

Accepted semantics are source-specific:

- Wikimedia: `revision`;
- Stack Exchange: `initial-post-version`;
- arXiv: `submission-version`;
- PMC: `publication-version`.

Timestamps must be timezone-aware ISO-8601. The validator recalculates whether a record belongs to the early, late, or outside window using `SOURCE_REGISTRY.json`.

A record cannot declare itself late when its native timestamp belongs to the early window.

`unresolved` is permitted only while timestamp evidence is unresolved. It cannot be eligible for training.

## 4. Historical-version requirements

Version states are:

- `version-bounded` — exact historically eligible text version is recoverable;
- `single-version` — exactly one text version exists;
- `latest-only` — only a later/current representation is available;
- `unresolved`;
- `unavailable`.

An eligible record requires `version-bounded` or `single-version`.

Examples:

- a Wikimedia parent/child revision pair can be version-bounded;
- a Stack Exchange initial PostHistory body can be version-bounded;
- a one-version arXiv submission can be single-version;
- current PMC XML with a later correction is latest-only until the original is recovered.

## 5. Rights requirements

Rights states are:

- `eligible` — item-level terms meet the current internal-training design;
- `conditional` — potentially usable but requires an unresolved condition;
- `ineligible` — excluded under the frozen first-pass rights policy;
- `unresolved`.

An eligible metadata record requires item-level `rights_status = eligible` and non-empty license identity and locator.

This status is local to the current design. It does not authorize:

- bulk acquisition;
- corpus release;
- model-weight release;
- use outside the documented source policy.

## 6. Authorship provenance

Possible values are:

- human;
- mixed;
- bot;
- synthetic;
- transformed;
- unknown.

The first naturalistic design permits only records classified as human for final eligibility. Other records remain useful for audits, exclusions, and sensitivity strata.

A source platform being historically human-dominated is not sufficient. Provenance is recorded per item/version where possible.

## 7. Eligibility

### Eligible

Requires:

- early or late era membership;
- historically bounded text;
- eligible rights;
- human provenance;
- no exclusion reason.

Eligibility at the metadata stage means the record may proceed to bounded text/parser qualification. It does not mean the content has passed direct-exposure, contamination, quality, or duplicate review.

### Excluded

Requires one or more reason codes, such as:

- `license-not-eligible`;
- `historical-version-unavailable`;
- `direct-methodology-category`;
- `direct-policy-exposure`;
- `bot-authored`;
- `source-c-firewall`;
- `outside-era-window`.

### Unresolved

Used when evidence remains incomplete. Unresolved records cannot enter a frozen training manifest.

## 8. Review strata

A record can enter one or more deterministic audit pools:

- `eligible-random`;
- `timestamp-boundary`;
- `rights-boundary`;
- `exposure-boundary`;
- `high-concentration`.

These strata guide manual review. They do not alter eligibility automatically.

Specific boundary strata are sampled before `eligible-random` so one record cannot fill multiple target counts silently.

## 9. Deterministic sampling

`deterministic_audit_sample` ranks records using a SHA-256 of:

- frozen seed;
- review stratum;
- record ID.

The same metadata hash, target list, and seed produce the same selection.

Each record can be selected once. An infeasible target fails rather than silently returning fewer records.

Artifacts:

1. **review packet** — blinded identifier and permitted metadata;
2. **unblinding key** — blind identifier mapped to record, item, era, and timestamp.

Both artifacts receive canonical hashes.

## 10. Source-C blinding

For source C, use `--hide-era-labels`.

The review packet then omits:

- project record ID;
- native item ID;
- era window;
- native timestamp.

It retains only the fields needed for rights, parser, provenance, version, category, and exposure audit.

The unblinding key is stored separately under the source-C access controls in `HELD_OUT_SOURCE_PROTOCOL.md`.

Metadata locators can themselves reveal dates or identifiers. Before a real source-C manual packet is issued, a packet-redaction layer must replace revealing locators with local opaque handles. The current generic sampler intentionally preserves locators for ordinary source audits and does not claim full reviewer blinding from locator content.

## 11. Deterministic summary

The source metadata summary reports only aggregate counts:

- source;
- era window;
- eligibility;
- rights;
- version status;
- authorship provenance;
- review stratum;
- source/window cell counts.

It includes no document text and receives a canonical output hash.

## 12. Commands

Validate and summarize:

```bash
python scripts/validate_source_metadata.py \
  artifacts/local/source-metadata.jsonl \
  --summary-output artifacts/local/source-metadata-summary.json
```

Create an ordinary A/B audit packet:

```bash
python scripts/plan_source_sample.py \
  artifacts/local/source-metadata.jsonl \
  --target wikimedia-article-additions:early:timestamp-boundary:25 \
  --target wikimedia-article-additions:early:eligible-random:50 \
  --target wikimedia-article-additions:late:timestamp-boundary:25 \
  --target wikimedia-article-additions:late:eligible-random:50 \
  --seed wikimedia-stage0-v1 \
  --packet-output artifacts/local/wikimedia-audit-packet.json \
  --key-output artifacts/local/wikimedia-audit-key.json
```

Create an era-blinded C packet:

```bash
python scripts/plan_source_sample.py \
  artifacts/local/arxiv-metadata.jsonl \
  --target arxiv-cc-single-version-descriptive:early:rights-boundary:25 \
  --target arxiv-cc-single-version-descriptive:early:eligible-random:50 \
  --target arxiv-cc-single-version-descriptive:late:rights-boundary:25 \
  --target arxiv-cc-single-version-descriptive:late:eligible-random:50 \
  --seed arxiv-source-c-stage0-v1 \
  --hide-era-labels \
  --packet-output artifacts/local/source-c-review-packet.json \
  --key-output artifacts/local/source-c-unblinding-key.json
```

Real C packet generation must additionally apply locator redaction and access logging.

## 13. Validation sequence

Before a metadata output is accepted:

1. validate `SOURCE_REGISTRY.json`;
2. validate every JSONL record;
3. record the exact metadata file hash;
4. generate and hash the summary;
5. freeze target list and seed;
6. generate review packet and key separately;
7. verify selected counts;
8. store C key outside ordinary development paths;
9. record every manual disposition without mutating the source metadata input;
10. create a new metadata version for corrections.

## 14. What this tooling proves

It can prove:

- timestamp/window logic is consistent;
- rights/version/provenance fields are complete;
- source counts and strata are reproducible;
- manual samples are deterministic;
- source-C era labels can be withheld from the ordinary packet;
- no text was embedded in the qualification artifact.

It cannot prove:

- text is actually human-authored;
- a license permits every intended use;
- historical text can be reconstructed correctly;
- direct exposure is low;
- source families are independent;
- enough clean tokens remain;
- a source induces CSTG.

Those require source-specific adapters, bounded samples, manual audit, and later experiments.
