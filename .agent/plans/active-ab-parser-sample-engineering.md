# A/B Parser-Sample Engineering

**Status:** E0 result-blind offline freeze active; no real source content or
network access authorized by this plan
**Started:** 2026-08-20
**Baseline:** `c245e7aaa16b2be35293fc5ca4d965efb7f5b84e`
**Branch:** `feat/ab-parser-sample-engineering`
**Stack base:** draft PR #38 / `feat/live-source-metadata-qualification`
**Write-active deliverable:** build and adversarially validate dependency-light
Wikimedia parent/child added-span parsing and Stack Exchange initial-version
reconstruction using synthetic official-shape fixtures only.

## Objective and claim boundary

Close a bounded offline software uncertainty inside the already-authorized A/B
parser-sample rung. This does not establish that dump XML is the eventual live
access shape: a Stack Exchange per-post API would use a different JSON revision
contract, while full site-dump acquisition remains unauthorized.

- A — can a bounded MediaWiki history record be parsed into an exact
  parent/child lineage and conservative added-prose candidate without using a
  current page snapshot as historical text?
- B — can a bounded Stack Exchange dump record reconstruct the initial title
  and body from `PostHistory` without using the current `Posts.Body`?

This plan may establish **Tested parser engineering** only. Synthetic fixtures
do not establish real format prevalence, endpoint usability, site/page
continuity, authorship, bot status, rights eligibility, clean-token yield,
source independence, direct-exposure burden, source suitability, final roles,
era windows, or any temporal/CSTG result.

The parser implementation, runner, and tests make no network request, open no
D-039 private inventory, retrieve no archive or source document, execute no
model, and incur CAD $0. Result-blind research against public official format
documentation is permitted to make the synthetic contracts exact, but it may
not request source records or data. This plan does not authorize a live micro-
sample. A later result-blind decision must freeze official access paths,
selection identities, site/page strata, request and byte ceilings, license
rules, private output roots, and stop behavior before any real text is opened.

## Frozen offline envelope

Implementation is standard-library-only and supports Python 3.11+. The public
CLI must default to a plan result and require `python -I -S`. Under this plan it
accepts only explicitly marked synthetic fixtures and must reject a live/network
flag, non-fixture provenance, unknown source, unknown schema, or input outside
the bounded fixture/test transaction.

Freeze these limits:

- one ordered, hash-bound synthetic bundle selection: page plus child/parent
  revision IDs for A, and site plus post IDs for B;
- at most 8 MediaWiki pages, 32 MediaWiki revisions, 16 `Posts` rows, and 32
  `PostHistory` rows, with at most 64 revisions/rows combined per invocation;
  every parsed object counts, selected or not;
- at most 4 MiB per XML input;
- at most 8 MiB total XML input;
- at most 256 KiB decoded text per source revision/version;
- at most 16,384 normalized tokens per text and a parent-by-child alignment
  product no larger than 16,777,216;
- UTF-8 only, no BOM, NUL, DTD, entity declaration, processing instruction
  beyond the XML declaration, or trailing second document;
- exact create-only output, canonical JSON/JSONL, `allow_nan=false`, LF final
  newline, and no overwrite or path alias;
- no prose, native ID, contributor/user value, title, URL, or per-record raw or
  normalized prose hash in a portable aggregate or receipt. Exact config,
  synthetic fixture-bundle, and complete artifact identity hashes are required.

The versioned config introduced under E1 must close every top-level and nested
field, bind the exact E0 commit plus the D-041 decision and plan Git blobs,
record the baseline and claim ceiling, and keep live execution disabled. Config
or parser drift must fail before input parsing or output creation.

## A — Wikimedia parent/child added spans

### Input and lineage

Use a minimal exact synthetic main-namespace, inline, single-main-slot subset
of MediaWiki export 0.11. Require:

- root `{http://www.mediawiki.org/xml/export-0.11/}mediawiki`, exact
  `version="0.11"`, required `xml:lang`, and the HTTP (not HTTPS) export
  namespace throughout; when present, `xsi:schemaLocation` is exactly the HTTP
  namespace followed by `http://www.mediawiki.org/xml/export-0.11.xsd`;
- direct `page/title`, `page/ns`, and `page/id` fields, with `ns=0`; page-level
  `redirect` is current-state metadata and may never describe the selected
  historical revision;
- direct revision fields in 0.11 order: positive `id`, optional positive
  `parentid`, canonical UTC timestamp, one exact contributor form, optional
  empty `minor`, optional inline `comment`, positive `origin`,
  `model=wikitext`, `format=text/x-wiki`, inline `text`, and sibling `sha1`;
- contributor form exactly `(username, nonnegative id)` or `ip`; deleted or
  empty contributor identity is rejected and no username implies a human;
- `text@xml:space=preserve`, `text@bytes` equal to its serialized UTF-8 byte
  length, and `text@sha1` plus the single-slot sibling `sha1` equal to the
  recomputed 31-character zero-padded lowercase base-36 SHA-1;
- no `text@deleted`, `text@location` stub, extra MCR `content` slot, upload,
  log item, deleted comment, unknown critical element/attribute, mixed
  namespace, or duplicate scalar;
- unique page/revision IDs and an acyclic parent graph. Resolve lineage only by
  the selected child's `parentid`, independent of XML order, revision-ID order,
  or timestamp order. Equal timestamps are structurally valid; chronology
  inversion is preserved as unresolved rather than relabeled malformed XML;
- `origin == child revision id` for a candidate new addition. A different
  origin is an inherited/rollback signal and cannot become eligible;
- a bundle-declared history coverage state of `complete-synthetic-page` or
  `bounded-synthetic-subgraph`. Absence of a revert/reintroduction may be
  asserted only for complete synthetic history; otherwise it is `unresolved`.

Contributor values and native IDs may exist only in the private parsed record.
The parser must not infer human/bot eligibility from a username. Without an
independently bound bot/provenance record, emit `authorship_status=unresolved`
and keep scientific eligibility unresolved.

### Transformation v0

On both parent and child, deterministically:

1. normalize line endings and Unicode to NFC;
2. remove comments, `ref`/gallery/code/math blocks, templates (including
   nesting), tables, file/image/category links, and list/navigation-only lines;
3. keep the visible label of ordinary internal/external links but discard the
   locator;
4. remove residual tags and heading/markup delimiters;
5. collapse whitespace into paragraph-preserving plain text;
6. tokenize with `nfkc-casefold-words-v1` through the repository's frozen
   content tokenizer;
7. run `difflib.SequenceMatcher(isjunk=None, autojunk=False)` over the parent
   and child token tuples inside the frozen work cap; take only the child side
   of `insert` and `replace` opcodes, merging adjacent runs only when no equal
   token separates them. Record exact token offsets and emit those contiguous
   runs as candidate added spans.

Each private record binds raw parent/child bytes, normalized text, tokens,
candidate spans, transformation version, and page/revision/parent lineage by
exact hashes. It also reports, without asserting resolution:

- exact-parent match;
- `origin` plus child-equals-earlier-revision rollback signals;
- added span seen in an earlier non-parent revision reintroduction signal, with
  `unresolved` used when fixture history is incomplete;
- a non-authoritative import/copy signal from a closed comment-only heuristic;
  export 0.11 revision XML has no change-tag element, so tag evidence is
  deferred to a separately frozen later input;
- bot/provenance, persistence, and rights status as `unresolved` unless supplied
  by a separately frozen later gate.

No candidate is scientifically `eligible` under this offline plan.

## B — Stack Exchange initial versions

### Input and lineage

Use paired synthetic `Posts.xml` and `PostHistory.xml` fixtures shaped like the
official data-dump row format. The D-041 fixture subset is UTF-8/no-BOM only;
that is not a claim about every real dump release. Require:

- XML declaration `version="1.0" encoding="utf-8"`, no namespace, exact roots
  `posts` and `posthistory`, and direct empty `row` children. Row and attribute
  order is irrelevant and nullable fields are represented by omission;
- zero or one exact normalized current Stack Exchange `ContentLicense` prolog
  comment; reject comments inside the roots/rows or arbitrary comments;
- a closed documented Posts attribute allowlist (`Id`, `PostTypeId`,
  `AcceptedAnswerId`, `ParentId`, `CreationDate`, `Score`, `ViewCount`, `Body`,
  `OwnerUserId`, `OwnerDisplayName`, `LastEditorUserId`,
  `LastEditorDisplayName`, `LastEditDate`, `LastActivityDate`, `Title`, `Tags`,
  `AnswerCount`, `CommentCount`, `FavoriteCount`, `ClosedDate`,
  `CommunityOwnedDate`, `ContentLicense`) and exact PostHistory allowlist (`Id`,
  `PostHistoryTypeId`, `PostId`, `RevisionGUID`, `CreationDate`, `UserId`,
  `UserDisplayName`, `Comment`, `Text`, `ContentLicense`);
- exact direct `row` records with canonical positive integer IDs and dump UTC
  timestamp spelling `YYYY-MM-DDTHH:MM:SS.fff` without `Z`, normalized
  internally to `Z`;
- one `Posts` row per selected post, `PostTypeId` exactly question or answer,
  excluding generated IDs `1000000001` and `1000000010`, and a creation
  timestamp inside the fixture's declared window; a question omits `ParentId`
  and an answer requires a positive `ParentId`, bound as lineage but not used as
  answer prose;
- exactly one initial-body history row (`PostHistoryTypeId=2`);
- exactly one initial-title history row (`PostHistoryTypeId=1`) for a question
  and none for an answer;
- exactly one initial-tags history row (`PostHistoryTypeId=3`) for a question
  and none for an answer; bind and validate its `Text`, but do not use it as
  prose;
- every selected history row to match the same post, occur no earlier than the
  post creation time, and have a unique row ID;
- canonical history timestamps and `RevisionGUID` in exact 8-4-4-4-12
  hexadecimal syntax, case-normalized without imposing a UUID version/variant.
  The parser never trusts row order: it groups by GUID/time and uses row ID only
  as a deterministic diagnostic tie-break. Same-time distinct actions are
  edit-order ambiguity, not silently ordered. A question's initial
  title/body/tags share PostId, CreationDate, RevisionGUID, and a compatible
  history-actor form; an answer's type-2 row is its initial action;
- `Posts.CreationDate` equal to initial-action time for a parser-audit
  acceptance. Because the official schema does not promise that equality,
  mismatch is preserved as unresolved/excluded, not malformed XML;
- current `Posts.Body`/`Posts.Title` to be ignored even when present and
  deliberately different from the initial history. A valid differing-current
  fixture must include the corresponding later documented type-5 body and, for
  a question, type-4 title edit rows with their own later action GUID/time.

Documented non-initial types are recognized only as closed edit, rollback,
deletion, migration, merge, or other lineage signals; types 12/13 and
17/35/36 cause closed deletion/migration exclusion. A type outside the frozen
official map, duplicate/absent initial row, edit-order ambiguity, suppressed
content, or current-body fallback fails. Bind current Posts owner separately
from the compatible initial-history actor: equality is not a format invariant,
and ambiguity remains unresolved. Do not infer a contribution license from the
date; emit `license_status=unresolved` pending a later official result-blind
license schedule.

### Transformation v0

On the initial title/body only, deterministically:

1. preserve and hash `PostHistory.Text` after exactly the XML parser's one
   entity-decoding layer; never blanket-`html.unescape` the raw Markdown;
2. identify and remove fenced/indented/inline code, `pre`, `code`,
   `blockquote`, script/style, quoted lines, link targets, signatures, and
   recognized boilerplate before any visible-entity normalization;
3. decode visible Markdown/HTML character references at most once outside the
   excluded regions, remove remaining tags while preserving ordinary visible
   prose, and test literal `&`, `&amp;`, and XML-escaped forms;
4. normalize Unicode/line endings and collapse whitespace into paragraph-
   preserving plain text; normalize the plain initial title separately rather
   than passing it through the Markdown-body sanitizer;
5. keep question and answer strata distinct;
6. hash raw and normalized fields and record removed code/quote/link/boilerplate
   counts.

Each private record binds site, post, history version, author/owner, creation,
question/answer stratum, transformation, and exact raw/normalized hashes. User
identities and native IDs remain private. Rights, authorship, migration,
deletion, and final eligibility remain unresolved unless the fixture explicitly
tests an exclusion.

## Output and privacy contract

E1 must produce three logical artifacts through one create-only transaction:

1. private parsed JSONL, containing synthetic fixture prose and full lineage;
2. portable aggregate JSON, containing only closed-vocabulary counts and byte/
   token totals by source/fixture-window/stratum/reason;
3. canonical success/failure receipt binding config/input/runtime identities,
   parser order, limits, output identities, final rebind, and claim ceiling.

The aggregate/receipt may report attempted, accepted-for-parser-audit,
excluded, unresolved, parser-failure, raw/clean byte and token totals, and
closed reason/count vocabularies. They must recursively reject prose, native
IDs, user/contributor values, locators, per-record raw/normalized prose hashes,
absolute paths, host/process fields, and arbitrary upstream strings. Exact
config, fixture-bundle, and complete artifact hashes remain required. A fixture
record is `accepted-for-parser-audit`, never scientifically `eligible`.

CLI stdout is either the canonical plan payload or a closed success/failure
summary. Stderr and receipts use closed reason/stage codes only: never raw
exception text, fixture prose, native IDs, user values, or machine paths.

The production fixture runner writes only a new canonical child of
`artifacts/local/ab-parser-sample/`, with exact leaves
`private-records.jsonl`, `aggregate.json`, and `receipt.json`. Fixture-mode
private output may be temporary and needs no outside-Git mirror because every
input is committed synthetic text. Future live private output must remain
ignored with an outside-Git exact mirror, but that production transaction and
its private key/ACL preflight require the later live decision.

## Primary format contracts inspected for E0

The fixture contract above is grounded in the public
[MediaWiki export 0.11 XSD](https://www.mediawiki.org/xml/export-0.11.xsd),
[current XML dump writer](https://doc.wikimedia.org/mediawiki-core/master/php/XmlDumpWriter_8php_source.html),
and [revision-table semantics](https://www.mediawiki.org/wiki/Manual:Revision_table),
plus the Stack Exchange
[public dump schema](https://meta.stackexchange.com/questions/2677/database-schema-documentation-for-the-public-data-dump-and-sede/2678)
and [staff XML-wrapper example](https://meta.stackexchange.com/a/401839).
These sources constrain only the frozen synthetic subset. Stack Exchange has no
formal dump XSD, and a later live gate must pin and byte-preflight one named
release or separately freeze the official API's JSON revision contract.

## Evidence gates

### E0 — Result-blind freeze

- Record D-041 and this plan from exact green E5 head `c245e7a`.
- Reconcile canonical state to D-040 and this offline A/B gate.
- Commit the freeze before parser implementation.
- Make no network request and open no D-039 private artifact.

### E1 — Offline implementation

- Add one closed `ab-parser-sample-v0` config.
- Add source-specific parser modules and one isolated fixture runner.
- Reuse established canonical JSON, path, hash, and output invariants without
  importing network code or weakening source-specific contracts.
- Keep all live flags and non-fixture content fail-closed.

### E2 — Dependency-light validation

Add valid synthetic early/late fixtures for Wikimedia parent/child histories
and Stack Exchange question/answer initial histories. Required negatives cover:

- wrong/missing parent, duplicate IDs/scalars, timestamp/order drift,
  current-page/current-body substitution, deleted/suppressed content, bot or
  author ambiguity, same-timestamp/out-of-order parent resolution,
  origin/rollback, incomplete-history reintroduction, and comment-only import
  signals;
- malformed/nested markup, template/reference/list/code/quote-only output,
  stub/MCR text, bad bytes/base36 SHA-1, missing origin, missing/duplicate
  initial title/body/tags, mismatched RevisionGUID/actor, edit ambiguity,
  migration/deletion, generated post IDs, double entity decoding, license
  unresolvedness, invalid UTF-8/NUL/DTD/entity/oversize input;
- record/byte/token/alignment ceilings, unknown fields/schema, output collision,
  path alias,
  symlink/reparse/casefold collision, config/input/runtime drift, artifact/hash
  mismatch, portable prose/ID/hash leakage, and nondeterministic bytes.

Require focused tests, full offline suite, compilation, top-level validators,
isolated plan mode, `git diff --check`, and independent adversarial review.

### E3 — Exact-head delivery

- Commit and push one scoped branch stacked on exact green PR #38 head.
- Open one draft PR and require every attached check green on one unchanged
  head across Python 3.11–3.13.
- Freeze implementation state in the delivery commit; external green checks
  fulfill E3 without a post-green state-only commit.

### E4 — Future live micro-sample, not authorized here

A later plan may propose a parser-only micro-sample after official documentation
and terms confirm unauthenticated, no-cost, per-record access. It must freeze an
exact public selection rule, Stack Exchange site whitelist and license schedule,
Wikimedia page/revision selection, byte/request ceilings, private keys/roots,
group order, zero retry, and create-only run identity before any record is
opened. A design candidate is one record per half-year cell per source/window,
but this plan does not freeze or authorize that design.

Stop before live access on any account/credential/terms acceptance, charge,
bulk archive requirement, unresolved official access path, unfrozen site panel,
ambiguous license rule, or need to inspect source C. Do not shrink, substitute,
or choose prose based on desired findings.

## Stop conditions

Stop E0–E3 on any implementation/test network access or source-data request,
non-synthetic input, private D-039 artifact access, source-C path, parser
fallback to a current snapshot/body, unknown critical XML, prose/ID leakage
into portable evidence, nondeterminism, output overwrite/alias,
dirty/head/input drift, or validator failure. Result-blind public official-
documentation research remains allowed.

Also stop on any attempt to classify real-source yield, rights, authorship,
source suitability, era choice, or behavioral effect from fixture results.

## Restart procedure

1. Read `PROGRESS.md`, D-040/D-041, this plan, `SOURCE_SAMPLE_PROTOCOL.md`, and
   `DATA_SOURCE_ADR.md`.
2. Verify branch `feat/ab-parser-sample-engineering` has exact baseline
   `c245e7aaa16b2be35293fc5ca4d965efb7f5b84e` and frozen E0 commit.
3. Resume only the offline E1/E2 implementation or E3 delivery gate.
4. Do not open D-039 private inventories, issue a source request, retrieve a
   real archive/document, inspect source C, run a model, or incur external cost.
