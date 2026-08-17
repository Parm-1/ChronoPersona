# Source Rights and Redistribution Matrix

**Date:** 2026-08-17  
**Status:** Stage 0 planning; not legal advice  
**Rule:** Public access and technical retrievability do not establish training or redistribution permission.

| Source | Eligible first-pass rights class | Attribution record | Raw/derived text redistribution | Weight release boundary | Current decision |
|---|---|---|---|---|---|
| Wikimedia article additions | Applicable Wikimedia text license with traceable revision lineage | Page, revision, contributor/history locator, license notice, imported-text provenance | Conditional on attribution/share-alike analysis; raw redistribution not authorized now | Separate review required; no assumption that source license automatically permits or forbids weight release | Internal metadata and bounded samples only |
| Stack Exchange initial posts | Contribution-specific CC BY-SA version determined by contribution date | Site, post, version, author/account or required attribution locator, creation date, license version | Conditional on versioned attribution/share-alike plan; raw redistribution not authorized now | Separate review required | Official dump/API metadata and bounded samples only |
| arXiv held-out C | Item-level CC0 or CC BY only | arXiv ID, exact version, authors, title, date, category, license locator, source hash | Permitted only according to item-level license and preserved attribution; default/noncommercial/no-derivatives/share-alike/custom licenses excluded initially | Separate review required | Metadata-only qualification; bulk source retrieval blocked |
| PMC backup C | Item-level CC0 or CC BY only, with historical-version integrity | PMCID, DOI/publisher locator, exact article/version dates, authors, license, hash | Approved service plus item-level license; embedded third-party content excluded | Separate review required | Metadata-only backup feasibility |
| Federal Register/GovInfo | Verified U.S. government works or separately licensed material at item/component level | Package, agency, publication, document, source locator, rights notices | Only after item/component rights classification | Separate review required | Rejected from headline A/B/C |

## General rules

### Rights status per record

Every source manifest records:

- owner or steward;
- exact license identifier and locator;
- contribution/article/version date relevant to that license;
- permitted internal research use;
- attribution requirement;
- redistribution status;
- share-alike, noncommercial, no-derivatives, notice, or custom terms;
- embedded or third-party components;
- unresolved questions;
- model-release status as a separate field.

### Unknown is not eligible

A record with missing, conflicting, custom, or ambiguous rights is:

- eligible for metadata analysis when metadata terms permit;
- ineligible for confirmatory text training;
- excluded from public corpus release;
- not silently assigned the collection's most common license.

### Transformations preserve lineage

Cleaning, delta extraction, markup removal, quotation removal, or format conversion does not erase rights provenance.

Every derived record preserves:

- input locator and hash;
- original rights record;
- transformation code/configuration;
- output hash;
- attribution lineage;
- whether protected or third-party portions were removed.

### Mixed documents

When one document contains components under different terms:

- exclude or separately identify those components;
- do not infer that the host or surrounding document license applies to everything;
- treat images, tables, supplements, standards, quotations, and submitted comments separately where needed.

### Corpus release and model release are separate decisions

The project may reach different conclusions for:

- internal research training;
- sharing locators and hashes;
- sharing normalized text;
- sharing evaluation items;
- sharing adapter or full model weights;
- publishing sample outputs.

No release is authorized merely because internal research use is qualified.

## Source-specific notes

### Wikimedia

The official terms permit reuse under the applicable Wikimedia licensing framework and require attribution; text can also involve imported material and historical license lineage. The project must preserve revision history and may need share-alike analysis for a distributed derived corpus.

### Stack Exchange

The official licensing page assigns Creative Commons BY-SA versions based on contribution date. The initial-version reconstruction therefore needs both textual version time and applicable license time. The official terms also govern automated access; use the documented dump/API rather than scraping.

### arXiv

arXiv supports multiple item-level licenses. The default arXiv distribution license is not a general reuse license. The first held-out C design narrows to CC0 and CC BY to avoid mixing materially different reuse conditions.

### PMC

PMC is an archive, not one rights regime. The Open Access Subset exposes item-level terms, and approved automated retrieval paths must be used. The project excludes license classes with noncommercial, no-derivatives, share-alike, custom, missing, or unresolved terms from its first backup-C design.

### Federal Register/GovInfo

17 U.S.C. §105 excludes U.S. government works from copyright protection under Title 17, but government-hosted documents may contain third-party, submitted, transferred, or incorporated material. The source remains item/component-specific and is scientifically rejected from the headline design regardless of rights convenience.

## Required review before text training

Before any source moves from metadata/sample qualification to training:

1. verify exact source terms and item-level rights fields;
2. test attribution-manifest completeness;
3. document transformation lineage;
4. sample mixed/third-party content errors;
5. state internal training permission rationale;
6. state raw/derived redistribution decision;
7. leave model release unresolved unless separately reviewed;
8. record reviewer findings and manager disposition.

## Current decision

No source in this matrix is authorized for bulk acquisition, corpus publication, or model release. Metadata-only and bounded no-cost parser samples remain the current limit.
