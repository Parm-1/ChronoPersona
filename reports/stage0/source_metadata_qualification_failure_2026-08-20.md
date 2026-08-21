# Source metadata qualification failure — 2026-08-20

## Decision

Classify the frozen D-039 E4 run as **Target Failed operationally** at its
source-C transport gate. The exact invocation completed the Wikimedia and
Stack Exchange inventory groups, then the first arXiv early-window candidate
count request failed with a non-success HTTP status before a response was
accepted. The frozen no-retry rule consumed the run at that point. No later
group may be resumed or retried under this profile.

This failure does not establish that arXiv is scientifically unsuitable or
that its metadata, rights, version, category, or time-window yield is
insufficient. It does not qualify source roles A, B, C, or backup C. No source-C
identifier, response, sample, private artifact, or aggregate was published,
and no source-C prose was displayed or human-reviewed. Temporal behavior,
causal evidence, and CSTG remain unestablished.

## Evidence

**Observed:**

- exact clean execution head:
  `eb0f7949c552e0e733f33c63dd33b9e9d603d83b`;
- draft PR #38 had 30/30 successful push/pull-request checks across Python
  3.11–3.13 on that unchanged head before execution;
- run name: `source-metadata-v0-eb0f7949`;
- frozen profile: `live-source-metadata-qualification-v0`;
- runtime: CPython 3.11.9;
- request attempts / completed responses: 3 / 2;
- retry count: 0;
- completed prefix: Wikimedia inventory, then Stack Exchange inventory;
- failed group: `arxiv-early-candidate-sample`;
- failure stage: `group-execution`;
- failure reason/subtype: `metadata-transport-failed` / `transport` /
  `http-status`;
- failed global request ordinal: 2;
- final input binding: `matched`;
- valid aggregate published: `false`.

The five later groups remained `not-started`: arXiv early enrichment, arXiv
late candidate sampling and enrichment, and both PMC windows. The failed arXiv
group recorded one attempt and zero completed responses. The receipt exposes
neither the exact source-C URL nor a response body, status code, or native
identifier. The exact HTTP-status cause therefore cannot be distinguished
without another request or evidence that this frozen run deliberately did not
retain.

The run enforced serial HTTPS GET, direct origin with no proxy, redirect
rejection, a 270-request ceiling, zero automatic retries, exact clean-head
input/runtime binding, CAD $0 spend, and create-only mirrored publication.
Traffic observation remains honestly `not-instrumented`.

**Reported by the completed source metadata responses and normalized
inventories:**

- Wikimedia snapshot `enwiki/20260801` reported a complete selected job with
  969 retained files, 969 MD5 identities, 969 SHA-1 identities,
  1,919,846,105,093 total bytes, and a 2,399,807,631,367-byte 25% storage
  estimate. The accepted response was HTTP 200 and 639,351 bytes.
- The Stack Exchange metadata response satisfied the frozen company-
  attribution check and is explicitly classified
  `legacy-archive-not-current-official-delivery`. Its
  normalized inventory retained 371 files, 371 MD5 identities, 371 SHA-1
  identities, 99,092,341,190 total bytes, and a 123,865,426,488-byte 25%
  storage estimate. The accepted response was HTTP 200 and 115,969 bytes.

These facts Target Verify only the two bounded metadata inventory operations.
They do not verify archive contents, record continuity, historical versions,
rights-qualified text, or final A/B roles.

**Not established:**

- the numeric status or cause of the failed arXiv request;
- any arXiv or PMC category, date, version, rights, or usable-record yield;
- any final A/B/C role or era window;
- any archive/article body eligibility, source continuity, clean-token yield,
  contamination, temporal effect, or CSTG claim.

## Artifacts

The receipt and completed-prefix inventories remain ignored/private. Each has
one byte-identical backup in a separate non-Git owner-restricted directory.
Only file names, sizes, and hashes are reported here; no inventory contents
were opened for this failure review.

| Artifact | Bytes | Raw file SHA-256 |
|---|---:|---|
| `artifacts/local/source-audit/source-metadata-v0-eb0f7949/receipt.json` | 12,836 | `765acc89ce4cf0128cc2c385c684c2ccb0edc3332edabfbb076a1fda5e9471ec` |
| `artifacts/local/source-audit/source-metadata-v0-eb0f7949/wikimedia-inventory.json` | 891,366 | `a81cdb192ae32f6d56783ca1175396fe33dc848f9e617dac2256c3a01e528cb7` |
| `artifacts/local/source-audit/source-metadata-v0-eb0f7949/stackexchange-inventory.json` | 455,405 | `5b114d6231b03db78b7a2275a5f3ebf0b00673b2fddd20e4f0d41023aa464b37` |

The receipt self-hash is
`62c260fec086f8f593f15e56ae5eb878ff133a94009ed50603e329df5c94d72f`.
Its full sanitized-payload HMAC is
`6b888165641f18b2ee50135449c5f3678f35823704bfc59b26c3d698856c94e5`,
and its private failure-detail HMAC is
`14a6a648a0015c552ce4c031516bf2357a7aaec058485fb710ba63e82638c669`.
No `aggregate.json`, arXiv artifact, PMC artifact, or later-group file exists.

## Validation

- The 12,836-byte receipt is canonical pretty UTF-8/LF JSON.
- Its raw SHA-256, public self-hash, and keyed full-receipt commitment
  recomputed successfully with the frozen private key.
- The production receipt validator returned zero errors against the exact
  clean-head bindings.
- Local and backup directories contain the same exact three-file set; every
  corresponding byte count and SHA-256 matches.
- Both directories and all six files retained the predeclared protected local
  access boundary.
- The local evidence path is Git-ignored. The repository stayed clean and
  synchronized to the exact execution head after the failed run.
- No request was retried, no response prose or native source-C identifier was
  displayed, no model ran, and no external spend occurred.

## Result-blind cause review

Static review found no independently proven implementation or contract defect.
The runner issued the frozen count-query path through the exact allowlisted
fetcher, which intentionally classifies any non-success response as
`http-status`, publishes the consumed prefix, and stops. Because the sanitized
receipt deliberately omits the status code, body, and exact private URL, it
cannot distinguish upstream throttling or service policy from a request-shape
incompatibility. Do not infer a cause and do not use uncertainty as authority
to retry.

## Risks and claim ceiling

- The completed inventory files are transport evidence only; their contents
  have not been used to qualify A or B.
- No arXiv or PMC metadata yield was observed, so C and backup-C feasibility
  remain unknown.
- One HTTP-status failure on one exact invocation is not evidence of permanent
  endpoint unavailability or scientific source infeasibility.
- This is an operational failure of the exact metadata prequalification gate,
  not a temporal, behavioral, causal, or CSTG result.

## Next write-active deliverable

Publish this sanitized failure record and D-040 decision, preserve the private
mirrored evidence, and deliver the evidence commit through exact-head CI. Do
not retry or resume the run. Any new source-C metadata request requires a
separately frozen, versioned transport-adjudication decision supported by new
result-blind evidence or an explicit material user choice.
