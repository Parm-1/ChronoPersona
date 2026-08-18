# Final Repository Review

**Date:** 2026-08-18
**Reviewed base:** `a8421143326f3365c581434e3fbe401ecb4531f7`
**Reviewed implementation:** `13a31b1cb3f2b3488599e121c000c0084a431ad0`
**Permanent workflow set:** `8bcf0392d8a066cc00453c505f288c273ca6d382`
**Decision:** **PASS after final Stage 0 hardening; stop at the existing external evidence boundary**

## Decision

The repository is coherent enough to preserve as the current Stage 0 research system after the hardening in this review is merged and passes exact-head CI.

This is an engineering and research-governance pass. It does not qualify a real source corpus, demonstrate model sensitivity, authorize training, or advance the CSTG claim ladder. The next scientific gate remains externally blocked on bounded real-source evidence and measured local model/compute evidence.

## Material findings corrected

### 1. Persisted path identity

Path checks had been implemented independently and did not cover all Windows/POSIX aliases. The review centralizes a canonical portable-path policy and applies it to content manifests, pilot configuration, model outputs, smoke inputs, generated unit paths, and checkpoint artifact references.

The policy rejects traversal, backslashes, drive forms, control characters, non-NFC spellings, Windows-reserved names, forbidden characters, trailing spaces/periods, root escape, symlinks where applicable, and case-insensitive path collisions in persisted collections.

### 2. Bounded and durable content evidence

The content-integrity configuration is advanced to schema version 2 and now freezes:

- maximum manifest records;
- maximum bytes per record;
- maximum total content bytes.

Declared limits are checked during both planning and execution: manifest loading stops at the frozen record cap before the full file is accumulated, declared content sizes are checked before content access, and observed sizes are checked during bounded reads. Requested validation and audit reports use atomic replacement. Synthetic-fixture provenance must agree with the fixture flag, and source-C authorization is rejected when it is missing, malformed, hash-mismatched, or attached to a manifest containing no real source-C record.

### 3. Correct lexical exposure semantics

Exact evaluation exposure now uses contiguous normalized token sequences rather than character substring matching. Short exact phrases are no longer suppressed by the n-gram size. Holdout-boundary flags now mean that `confirmatory-held-out` source-C material is crossed; ordinary role differences are not mislabeled as holdout crossings.

Direct-pattern IDs must be stable slugs, and two pattern IDs cannot normalize to the same literal phrase.

### 4. Metadata-only and network boundaries

Source metadata and archive inventories now recursively reject nested source-text payload fields. Inventory MD5, SHA-1, and SHA-256 values must have exact lowercase hexadecimal lengths. Every source-registry candidate must cite at least one official source.

Live metadata requests now require HTTPS and an exact per-adapter host allowlist. Redirect targets are validated before following and cannot escape to another host, non-default port, credential-bearing URL, or plaintext endpoint. Existing response byte, timeout, delay, and explicit-authorization gates remain in force.

### 5. Evaluation, tokenizer, scorer, and model readiness

The evaluation registry now enforces the option-order invariance it declares: both candidate orders must exist and their counts must be balanced within one form.

Tokenizer and scorer evidence now rejects booleans, numeric strings, negative token IDs, malformed sequences, NaN/Inf, positive log probabilities, inexact boundaries, truncation, and token/log-probability length mismatches. Smoke interruption limits now require an actual positive integer rather than accepting booleans through Python's integer subtype behavior.

A model artifact cannot be `benchmark-ready` unless it has an immutable pinned 40-character Hub commit SHA, a verified license with source evidence, an exact owner/name repository, non-empty artifact sources, and no custom remote-code requirement. This aligns the declarative manifest with the executable loader policy.

### 6. Repository state and CI

README, plan, risk register, decisions, agent instructions, and the accepted content-integrity protocol now share the same current gate boundary. Consistency tests prevent the top-level state from reverting to stale claims such as “novelty remains unverified” or an active training deliverable.

CI matrices add Python 3.13 while retaining Python 3.11 and 3.12, and official checkout/setup actions move to `actions/checkout@v7` and `actions/setup-python@v7`.

### 7. Repository hygiene

The tracked Git tree was verified free of generated `.coverage` data, pytest cache entries, and compiled Python bytecode. The review adds a repository-state regression test based on `git ls-files` so caches and bytecode cannot silently enter the evidentiary tree in a future commit.

## Validation performed

The hardened tree passed locally on CPython 3.13.5:

```text
python -m pip install -e ".[dev]" --no-build-isolation --no-deps
python -m compileall -q src scripts
python -m chronopersona validate configs/pilot.toml
python -m chronopersona validate-models artifacts/manifests/MODEL_MANIFEST.json
python -m chronopersona validate-evaluation evaluations/registry/development-v0.jsonl
python scripts/validate_source_registry.py artifacts/manifests/SOURCE_REGISTRY.json
python scripts/build_synthetic_calibration.py --check
python scripts/validate_content_manifest.py ...
python scripts/audit_content_integrity.py ... --execute
cmp <audit-one.json> <audit-two.json>
python -m pytest -q
```

Results:

- 268 tests collected and passed;
- deterministic content-audit outputs were byte-identical;
- pilot, model manifest, evaluation registry, source registry, and synthetic calibration validators passed;
- no external network request, model load, corpus acquisition, training job, or paid compute was performed;
- coverage was measured at 78% across the Python package, with the critical scorer and portable-path modules above 90%; coverage is diagnostic, not a scientific gate.

The ordinary editable install initially attempted build-isolation dependency resolution and was blocked by the review environment's unavailable DNS. The same checkout installed successfully using the already present compliant build dependencies with `--no-build-isolation --no-deps`.

A one-time GitHub importer reconstructed and verified reviewed patch SHA-256 `3a74cb6c7c322600efb1a36318bb8022ec9fccf06397309225af69dd46a1108e`, confirmed the tracked tree contained no generated machine state, ran the complete validator and deterministic-audit sequence on CPython 3.13.15, and passed all 268 tests before committing the non-workflow implementation as `13a31b1cb3f2b3488599e121c000c0084a431ad0`.

The permanent seven-workflow set was then published as `8bcf0392d8a066cc00453c505f288c273ca6d382`, with `actions/checkout@v7`, `actions/setup-python@v7`, and Python 3.11, 3.12, and 3.13 matrices. The final report commit exists to trigger ordinary exact-head CI against that permanent workflow set.

## Residual risks and external blockers

The following are not defects to hide with more local scaffolding:

1. Real A/B/C content has not been authorized or qualified.
2. Lexical screening cannot establish semantic or translated independence.
3. Production-scale streaming, stable large-corpus clusters, reason-coded derived exclusions, and threshold sensitivity remain unfinished.
4. Event, host, contributor, topic, genre, quotation, revision, and syndication concentration remain unmeasured.
5. Real-model tokenizer reliability, logits behavior, memory, throughput, and training feasibility remain unmeasured on the user's hardware.
6. DatedGPT revisions/licenses and the preferred OLMo/Pythia execution identities remain partly unresolved.
7. No live official metadata endpoint was contacted during this review; network-origin behavior was tested with deterministic local doubles.

## Final action

Merge the hardening only after exact-head CI passes on Python 3.11, 3.12, and 3.13. Then stop.

Resume scientific work only when small rights-qualified, historically version-bounded A/B samples and a manifest-bound authorized source-C review packet are available under the existing firewall. At that point, run the bounded real-content qualification gate and issue source-by-source proceed, redesign, or stop decisions.
