# Bounded Live Source-Metadata Qualification

**Status:** E0 result-blind freeze complete in this plan commit; E1 active; no evidence-bearing live query has run
**Started:** 2026-08-20
**Baseline:** `d669b4e3c36069398efdac831c8f1fec7036359c`
**Branch:** `feat/live-source-metadata-qualification`
**Stack base:** draft PR #37 / `fix/scoring-failure-observability`
**Write-active deliverable:** harden, deliver, and execute one bounded no-cost
metadata-only prequalification across provisional source roles A, B, C, and
backup C. Retrieve no archive, article body, or source package; incidental API
metadata prose is transient hash/count-only. Keep native source-C identifiers
outside tracked evidence.

## Objective and claim boundary

Use the repository's existing metadata adapters to establish whether the four
provisional source interfaces are live, bounded, and capable of producing the
specific inventory or metadata evidence required for the next source decision:

- A — Wikimedia article-revision additions: one immutable English Wikipedia
  `pages-meta-history` file inventory, sizes, published hashes, and storage
  estimate for snapshot `20260801`;
- B — Stack Exchange initial nontechnical posts: the company-attributed legacy
  Archive.org item inventory only, explicitly not a current-delivery claim;
- C — arXiv single-version CC0/CC BY descriptive science: one deterministic
  100-record time-stratified submitted-date metadata sample in each provisional
  window, followed by exact `arXivRaw` version/license enrichment of all 100;
- backup C — PMC version-bounded CC0/CC BY: at most ten OAI pages and 100
  upstream Dublin Core records per release/update-datestamp range, with the
  usable filtered yield retained as era/version unresolved.

This gate may prove endpoint usability, bounded metadata volume, immutable
archive identity, and aggregate license/version yield. It cannot qualify A or
B content, promote PMC, authorize source-C prose access, freeze final roles or
eras, establish clean-token volume or contamination, authorize requester-pays
retrieval, run a model, or support temporal/CSTG claims.

## Result-blind freeze

The provisional windows remain exactly:

- early: `2012-01-01` through `2013-12-31`;
- late: `2018-01-01` through `2019-12-31`.

The execution profile must bind the exact canonical paths and filtered Git
blob identities of:

- `artifacts/manifests/SOURCE_REGISTRY.json`;
- `configs/sources/arxiv-metadata-v0.json`;
- `configs/sources/pmc-metadata-v0.json`;
- the versioned metadata-gate execution config introduced under E1.

The execution config must freeze all endpoints, roles, dates, categories,
limits, timeouts, delays, output kinds, and privacy rules. Unknown or aliased
paths, dirty tracked inputs, a changed Git head, or a changed config/input blob
must fail before any network import or request.

The one planning-only Wikimedia directory-index observation on 2026-08-20
found completed-date directory names through `20260801`; no dumpstatus payload
was fetched. E4 must request only
`https://dumps.wikimedia.org/enwiki/20260801/dumpstatus.json` and stop if that
snapshot or its history job is incomplete. Do not fall back to `latest` or a
different date.

## Frozen live envelope

All calls are serial HTTPS GET requests, CAD $0, with exact host allowlists and
no credentials. The only permitted hosts are:

- `dumps.wikimedia.org`;
- `archive.org`;
- `export.arxiv.org`;
- `oaipmh.arxiv.org`;
- `pmc.ncbi.nlm.nih.gov`.

No content/archive locator may be opened. Atom/OAI responses can inherently
contain titles, author names, and abstracts; those fields may transit memory
only long enough to compute lengths/hashes and must never be displayed,
persisted as prose, or human-reviewed. The response ceilings are 20 MB for
Wikimedia, 30 MB for the Stack Exchange item metadata, 8 MB per arXiv API or
PMC response, and 2 MB per arXiv OAI `GetRecord`. Timeouts are 60 seconds.
arXiv pagination/enrichment delays are at least three seconds; PMC pagination
delay is at least one second. Every multi-request adapter must also freeze a
maximum request/page count, reject repeated pagination/resumption tokens, and
preserve completed response identities on failure. There is no retry after a
semantically consumed successful response; transport failure may be preserved
and adjudicated before any separately versioned rerun.

The complete happy-path ceiling is 270 HTTP requests: one Wikimedia, one Stack
Exchange, 24 arXiv candidate/count pages per window, 100 arXiv enrichments per
window, and at most ten PMC pages per range. A lower count is valid only when
an endpoint ends naturally or the frozen upstream-record cap is reached; it
must not result from silent truncation or retry. PMC must count upstream records
seen, not only retained/usable records.

The fail-fast group order is immutable:

1. Wikimedia inventory;
2. Stack Exchange inventory;
3. arXiv early candidate sample;
4. arXiv early exact enrichment;
5. arXiv late candidate sample;
6. arXiv late exact enrichment;
7. PMC early-range metadata;
8. PMC late-range metadata.

If a group fails, preserve its failure receipt and do not start a later group.

### A — Wikimedia

Fetch one pinned `enwiki/20260801/dumpstatus.json`. Retain only completed
`pages-meta-history` inventory entries with file names, sizes, MD5/SHA-1 when
published, snapshot identity, total bytes, and 25% storage margin. Do not fetch
any listed archive.

### B — Stack Exchange

Fetch `https://archive.org/metadata/stackexchange` once. Retain only the
company-attributed `.7z` site inventory, sizes, hashes, and legacy snapshot
metadata. Reject a mirror or missing company attribution. Do not fetch any
archive and do not infer that this is the current official delivery path.

### C — arXiv

For each window, partition the exact dates into four fixed half-year cells
(`YYYY-01-01..YYYY-06-30` and `YYYY-07-01..YYYY-12-31` for both years).
Cell IDs are exactly `YYYY-h1` and `YYYY-h2`. Within each cell query the exact
predeclared category union in
`arxiv-metadata-v0.json`, sorted by submitted date ascending. One count request
at `start=0,max_results=1` supplies exact `totalResults=T`; its returned record
is not part of the sample. Require `25 <= T <= 30005`.

Process the cells in exact chronological order: early is `2012-h1`,
`2012-h2`, `2013-h1`, `2013-h2`; late is `2018-h1`, `2018-h2`, `2019-h1`,
`2019-h2`. Within each cell, make the count request first and the five sample
requests in slot order. Preserve records within each sample page in exact Atom
response-entry order `0` through `4`.

Let `B = floor(T / 5)`, the number of complete disjoint five-record blocks.
Because `T >= 25`, require `B >= 5`. For slots `0` through `4` in ascending
order, serialize the slot as ASCII base-10 with no sign and no leading zero,
compute
`sha256(UTF8(seed + NUL + cell_id + NUL + slot_decimal))` with seed
`arxiv-source-c-rank-sample-v0`, interpret the 32 digest bytes as one unsigned
big-endian integer, and reduce it modulo `B` to obtain a candidate block index.
If that index was selected by an earlier slot, increment it modulo `B` until
the first unused block is found. Permit at most `B` probes and fail before any
sample request if no unused block is found. With five slots and `B >= 5`, this
procedure is cycle-free and guarantees five distinct complete blocks.

For each selected block, set `start = 5 * block_index` and request the pages in
slot order with `max_results=5`. Require every block index to be in `[0,B)`,
all five block indices and starts to be distinct, every start to be a multiple
of five, and every start to be at most 30,000 before making any sample request.
Fetch exactly those five pages, producing 25 records per cell and 100 per
window. Records in the incomplete tail `T mod 5`, if any, are deliberately
outside this bounded sample.

Every response in a cell must report the same `totalResults=T`; count responses
must report `startIndex=0,itemsPerPage=1`; sample responses must report the
exact requested `startIndex` and `itemsPerPage=5`. Every sample page must
contain five records, its submitted dates must remain inside its cell, and all
100 base IDs per window and all 200 base IDs across both windows must be
unique. This is a deterministic time-stratified rank sample, not a random
sample or an unbiased window-level yield estimator.

Enrich all 100 private base identifiers per window through serial `arXivRaw`
`GetRecord` calls. The exact enrichment order is the concatenation of
chronological cell order, slot order `0` through `4`, and response-entry order
`0` through `4`; complete all early IDs before any late-window candidate or
enrichment request under the frozen macro-group order. The execution runner
may handle native IDs in memory and ignored private artifacts only; public
receipts bind ordered ID hashes and aggregates. Titles, summaries, abstracts,
and author names are transient hash/count-only fields and must never enter
tracked evidence or human review. Do not request any separate abstract page,
PDF, source package, or requester-pays object. Report exact observed sample
yield and category/time coverage without generalizing it to the full window
population.

### Backup C — PMC

Query `oai_dc` with `set=pmc-open`, bounded at ten responses and at most 100
upstream records for each provisional date range. Record the usable filtered
yield and that OAI `from`/`until` filter PMC
release/update datestamps and that Dublin Core dates remain lifecycle evidence,
not confirmed publication dates. Keep every record's era and historical-
version eligibility unresolved. Do not request `pmc` full text or `pmc_fm`.

## Evidence and privacy contract

Before E4, shared execution hardening must provide:

1. stable single-read and duplicate-key rejection for canonical tracked JSON
   inputs;
2. exact canonical-path, clean-head, Git-blob, and raw SHA-256 binding before
   any request and again before publication;
3. create-only canonical JSON/JSONL publication with no overwrite, traversal,
   alias, reparse/symlink, reserved-name, or casefold-collision path;
4. per-response byte count/SHA-256 plus requested/final URL identity and
   request-count evidence without retaining response prose or native C/backup-C
   locators in a portable report; C-family URL identities must be hashes only;
5. a strict no-prose-output validator over every nested persisted field;
6. portable config identities rather than absolute local paths;
7. honest network evidence: access permitted and the metadata request path
   used, while independent traffic observation remains `not-instrumented`;
8. a self-hashed execution receipt that binds the exact Git head, input blobs,
   adapter/runtime identity, commands/limits, private artifact hashes, counts,
   stop status, and claim ceiling.

The final self-hash must cover the completed adapter/receipt payload, not the
pre-enrichment base summary. Exact arXiv OAI identifiers must match requested
base IDs rather than prefixes. Every Wikimedia file locator must remain HTTPS
on `dumps.wikimedia.org` under the pinned project/snapshot path; an absolute or
off-host file URL is invalid.

PMC rights evidence must normalize recognized license URLs/IDs; arbitrary
`dc:rights` prose is hash/count-only and cannot be treated as a license locator.
Any mid-run failure must create one sanitized self-hashed failure receipt with
the completed ordered response hashes/counts and original stop reason, without
native C-family URLs or identifiers. It must never auto-retry.

Identifier-bearing records and raw response-derived metadata,
host/process paths, and native source-C locators remain ignored/private with a
hash-matched backup outside public Git worktrees. The tracked aggregate may
contain only counts, byte totals, published archive hashes, response/artifact
hashes, eligibility/license/version aggregates, endpoint identities, exact
execution head, limitations, and stop decisions. Recursively reject private
paths, native source-C IDs/locators, titles, summaries, authors, abstracts,
body text, and host/process identifiers from tracked evidence.

## Evidence gates

### E0 — Result-blind plan freeze

- Record D-039 and this ExecPlan on a new branch from exact green PR #37 head
  `d669b4e`.
- Reconcile current state to PR #37's completed delivery and this metadata-only
  gate.
- Run plan modes only; make no evidence-bearing live query.

**Result:** completed in the plan/state commit. The official documentation and
planning-only Wikimedia directory index were inspected; all adapter plan modes
and the source registry validated. No evidence-bearing endpoint response,
source document body, model, or behavioral outcome was retrieved.

### E1 — Execution contract hardening

- Add one versioned closed metadata-gate config and dependency-light shared
  evidence helpers.
- Apply the evidence/privacy contract without weakening current adapter
  content firewalls, host allowlists, ceilings, or delays.
- Keep fixture parse mode useful and no-network by default.

### E2 — Dependency-light validation

- Preserve existing adapter fixtures and plan-mode bytes where frozen.
- Add negative coverage for overwrite, dirty/wrong input, path aliases,
  duplicate JSON keys, response/count/config drift, persisted prose fields,
  source-C locator leakage, incomplete/mutable Wikimedia snapshots, mirror
  Stack Exchange attribution, exact arXiv identity prefix collisions, off-host
  Wikimedia file locators, arXiv cell total/start/page-size drift, invalid
  slot serialization, duplicate blocks, non-multiple/max starts, short-page
  failures, `T=25` termination, collision-heavy block selection, cell/slot/
  entry/enrichment-order drift, cross-window duplicate base IDs, PMC page/token
  cycles, arbitrary rights prose, group-order drift, and network flag misuse.
- Add an end-to-end fixture gate producing one portable self-hashed receipt and
  sanitized aggregate.
- Require focused tests, full offline suite, source/model/registry validators,
  compilation, and `git diff --check` with no live query.

### E3 — Exact-head delivery

- Commit and push one scoped implementation branch stacked on draft PR #37.
- Open one draft PR and require every attached check green on one unchanged
  head.
- Do not execute E4 until that exact head is clean locally, synchronized with
  the remote, and fully green.

### E4 — Bounded live metadata execution

- Execute A, B, C-early, C-late, backup-C early-range, and backup-C late-range
  exactly once under the frozen profile.
- Enrich exactly all 100 time-stratified arXiv records per window only if the
  systematic sample passes every count/page/identity invariant.
- Preserve one complete portable receipt or one actionable failure receipt.
- Stop the gate at the first policy, identity, schema, privacy, transport, or
  publication failure; do not silently shrink, substitute, or promote a backup.

### E5 — Portable evidence publication

- Independently replay all hashes, schemas, counts, privacy scans, and claim
  boundaries without displaying or human-reviewing transient metadata prose.
- Publish only the sanitized aggregate report and a bounded D-040 decision.
- Preserve private raw artifacts and hash-matched backup, then deliver the
  evidence commit through exact-head CI.

## Stop conditions

Stop immediately on any charge, credential request, requester-pays path,
archive/document body or source-package retrieval beyond the allowed metadata
responses, unexpected redirect, nonallowlisted
host, response ceiling, timeout, malformed or duplicate-key payload, missing
published archive hash, mutable/incomplete Wikimedia state, unattributed Stack
Exchange mirror, fewer than 100 unique records in either frozen arXiv sample,
output collision, nondeterminism, privacy leak, dirty/input/head drift, or validator
failure.

Also stop on any attempt to inspect source-C prose, unblind a reviewer to era,
use behavioral/model outcomes, alter E4 scoring, promote PMC because arXiv is
inconvenient, revise roles/windows/categories after seeing yields, train on the
metadata, or infer temporal/CSTG behavior.

## Hard boundary after E5

Even a passing metadata gate leaves A/B content qualification and source-C
content review incomplete. Bounded no-cost A/B parser samples remain authorized
by `SOURCE_SAMPLE_PROTOCOL.md`, but require a later frozen plan and may begin
only after this gate. Those samples must establish record continuity, initial-
version reconstruction, authorship, clean-token yield, duplication,
composition, exposure, and cost. Source C requires frozen
identifiers/versions, a frozen non-C exposure classifier, an exact locator-
redacted review manifest/access log, and explicit user authorization before
any prose is opened. Requester-pays arXiv source needs a separate cost/storage
proposal and approval. Bulk A/B acquisition and source-C document bodies remain
externally blocked. No model execution or scientific claim is authorized.

## Restart procedure

1. Read `PROGRESS.md`, D-037 through D-039, this plan, and the three source
   protocols.
2. Verify branch `feat/live-source-metadata-qualification` is based on exact
   head `d669b4e` and inspect the scoped diff.
3. Continue the earliest incomplete evidence gate.
4. Do not human-inspect transient metadata prose, retrieve an archive/article
   body/source package, execute a model, rerun development-v1 E4, or incur
   external cost.
