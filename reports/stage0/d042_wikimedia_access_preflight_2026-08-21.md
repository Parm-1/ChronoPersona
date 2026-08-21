# D-042 Wikimedia access preflight

## Decision

The official technical path is sufficient to implement and test a tiny,
read-only Wikimedia feasibility runner. It is not yet evidence that any
revision, source role, or corpus is qualified. Stack Exchange remains outside
this path.

## Evidence

### Reported by source

- The MediaWiki Action API accepts GET requests and recommends JSON output;
  English Wikipedia exposes `https://en.wikipedia.org/w/api.php` as its Action
  API endpoint. [API tutorial](https://www.mediawiki.org/wiki/API:Tutorial)
- `prop=revisions` can obtain data for exact revision IDs through `revids`.
  It can return IDs, timestamps, slot sizes/hashes, content model, and main-slot
  content; hidden content/hash fields are signaled explicitly. [Revisions
  module](https://www.mediawiki.org/wiki/API:Revisions)
- `prop=info` can return a page's canonical URL, which is usable as an
  attribution locator. [Info module](https://www.mediawiki.org/wiki/API:Info)
- Wikimedia asks automated callers to provide a descriptive User-Agent with
  contact information; generic Python request agents can be blocked. [User-Agent
  policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
- For noninteractive calls, the API etiquette recommends an integer `maxlag`.
  It also describes rate-limit retry. D-042 therefore requires an explicit
  bounded retry policy before execution rather than inheriting D-039's
  no-retry transport rule. [API etiquette](https://www.mediawiki.org/wiki/API:Etiquette)
- Wikimedia's Terms of Use describe its mission as publishing free-licensed or
  public-domain educational content. Project-specific reuse/attribution still
  needs per-record evidence. [Terms of
  Use](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en)

### Inferred acceptance requirements

The D-042 execution profile must require: HTTPS; an exact descriptive
User-Agent; `action=query`, JSON, `formatversion=2`, and an integer `maxlag`;
namespace-0 only; exact child/parent IDs bound by `parentid`; same-page main-slot
wikitext; present, non-hidden content and slot hash/size; no redirect resolution;
canonical-page attribution locator; and strict response/request/output caps.
The profile must reject missing, hidden, cross-page, redirect, malformed, or
identity-mismatched revisions.

## Artifacts

- Official endpoint class and response expectations are bound by the future
  D-042 profile, not by this report.
- No API call, page/revision selection, text retrieval, account action, or local
  private artifact was created.

## Validation

The cited official documentation was rechecked on 2026-08-21. No source
content, metadata response, or external account was opened.

## Risks

This preflight does not settle English Wikipedia's per-record attribution or
imported-text status, whether the tiny sample yields parsable retained spans,
or whether Wikimedia should become source A. It does not authorize Stack
Exchange, source C, bulk retrieval, public text/IDs, a model run, or source
qualification.

## Next write-active deliverable

Implement and validate the closed D-042 profile and synthetic Action API
fixtures before any real Wikimedia request.
