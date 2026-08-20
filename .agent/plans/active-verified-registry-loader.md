# Verified Registry Tokenizer Loader

**Status:** active — E5 passed; E6 evidence publication and exact-head CI pending
**Frozen baseline:** `fa809ed6a0337400088834a64f0718c85e7dd0fd`
**Branch:** `feat/verified-registry-loader`
**Target execution head:** `c57ce40e2b0fad6a3e1ad07a3eada7e9405ccb6d`
**Write-active deliverable:** publish the accepted Pythia tokenizer evidence
and require final exact-head CI on draft PR #33.

## Objective

Replace the tokenizer provider's deliberate execution blocker with one explicit
local-snapshot contract that proves the selected cache, repository, immutable
revision, exact required-file allowlist, sizes, hashes, safe config, and frozen
tokenizer runtime identity before Transformers is imported. Produce
deterministic, portable tokenizer-audit evidence without deserializing model
weights or implementing a download-capable path. The complete-snapshot verifier
still streams every manifested byte, including the safetensors file, through
SHA-256. Offline controls are enforced; network traffic is not independently
instrumented and must be labelled `not-instrumented`.

Model scoring remains blocked until the same snapshot boundary is combined with
the existing clean-head, live-resource, CUDA, dtype, and exact-load gates. This
plan does not authorize scoring or another training run.

## Starting evidence

- `fa809ed` is the tested and delivered evidence baseline on draft PR #32.
- The exact Pythia snapshot revision is
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2` and its five required files are
  already pinned by size and SHA-256 in the canonical model manifest.
- Direct provider repository/cache loading is currently fail-closed.
- The development registry contains 12 items, 24 forms, and 48 candidates.
- The completed v0/v1 training evidence and its worktree are immutable inputs,
  not part of this implementation branch.

## Frozen execution contract

Execution must:

1. capture the canonical model manifest and development registry once, prove
   those exact bytes are the blobs at one captured clean Git head, and parse,
   hash, and execute from those same bytes;
2. require explicit existing `--cache-dir` and `--snapshot-path` values;
3. derive the exact Hugging Face cache locator from the manifest repository and
   revision rather than accepting a caller-authored identity;
4. reject cache/snapshot directory links or reparse points and reject required
   files whose targets escape the selected repository cache; standard Hub leaf
   symlinks are allowed only when their resolved regular-file targets remain
   inside that cache;
5. enumerate exactly the manifest allowlist, verify stable size and SHA-256,
   validate model/tokenizer configuration, and bind the expected tokenizer
   class, backend fingerprint, special-token identities, vocabulary, and native
   prefix behavior before any optional dependency import;
6. copy only the four verified tokenizer inputs from stable reads into a
   private create-only plain-file staging directory, rehash them there, and load
   only that private stage with `local_files_only=True`,
   `trust_remote_code=False`, and `use_fast=True`;
7. require offline environment flags, reverify the source snapshot after
   tokenizer construction, and validate the loaded runtime/backend/native-prefix
   identity against the manifest;
8. record a portable receipt with no machine path, normalize tokenizer identity
   so the report cannot leak the absolute snapshot or staging path, and record
   Python/Transformers/tokenizers/Hub versions;
9. rebind Git head, clean state, and canonical input bytes immediately before
   create-only output publication, then hash the final complete report envelope.

Private staging prevents the mutable cache from being the byte source consumed
by Transformers after verification. The source is reverified after loading;
canonical Git inputs are stable-read and rebound before publication.

## Gates

### E0 — Baseline and plan (complete)

- Confirm a clean isolated branch at exact `fa809ed`.
- Record this plan and keep one writer for the implementation worktree.

### E1 — Shared verifier (complete)

- Add a verified-snapshot result with local path kept separate from its portable
  self-hashed receipt.
- Enforce exact repository/revision cache layout, containment, link policy,
  file identity stability, allowlist, hashes, config, and manifest-bound
  tokenizer runtime expectations.
- Preserve compatibility for the existing acquisition/training consumers.

### E2 — Provider and CLI (complete)

- Unlock tokenizer loading only; keep the model loader and scoring CLI blocked.
- Bind execution to single-read HEAD blobs for the canonical manifest/registry
  and explicit local paths.
- Load only from a private verified tokenizer-file stage; no model file enters
  that stage.
- Produce a portable, deterministic, self-hashed execution report and refuse
  output overwrite. Record enforced offline controls and
  `network_observation=not-instrumented`.

### E3 — Dependency-light validation (complete)

- Pass dependency-light adversarial tests covering policy-first ordering,
  wrong repository/revision/layout, missing/extra/changed files, cache escape,
  unsafe links, offline requirements, import ordering, exact load kwargs,
  post-load mutation, output overwrite, final report hashing, and path
  portability, manifest-bound runtime drift, and prefix-policy mismatch.

### E4 — Implementation delivery gate (complete)

- Commit the scoped implementation on this isolated branch.
- Push the exact branch and open a stacked draft PR against the delivered
  `feat/tiny-training-resume-gate` baseline.
- Require exact-head CI to pass before target execution.

### E5 — Target tokenizer audit (complete)

- Run the real Pythia tokenizer audit with prefix policy `none`, the native
  no-prefix convention frozen in the manifest before logits. Require the
  manifest-bound native special-token count and the add-specials probe to agree.
- Repeat from a fresh invocation and require identical canonical output hashes.
- Require 12 items, 24 forms, 48 candidates, zero boundary/context/truncation
  failures, and no local path in either report.

### E6 — Evidence publication (active)

- Preserve a bounded tracked aggregate report and a decision accepting or
  rejecting the tokenizer gate without changing registry content.
- Reconcile canonical project state and advance the next gate only if E5 passes.
- Commit and push the evidence-only update, refresh the same draft PR, and
  require exact-head CI again. Do not rerun a passing target merely to improve
  timing or presentation.

## Observed E5 result

Two separately observed CLI invocations at exact clean head `c57ce40` returned
0 and wrote distinct output files whose 50,169 serialized bytes were identical.
Both audited 12 items, 24 forms, and 48 candidates with zero failures. The
canonical output SHA-256 is
`6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523`;
the portable snapshot receipt SHA-256 is
`26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc`.
Both self-hashes recomputed, all identities matched, and recursive inspection
found no absolute local path. No model weight was deserialized. Network traffic
was not instrumented; offline/local-only/no-download controls were enforced.

The bounded tracked result is
`reports/stage0/pythia_tokenizer_boundary_gate_2026-08-20.md`. Do not rerun E5
unless the artifact revision, manifest tokenizer runtime identity, or
Python/Transformers/tokenizers/huggingface-hub identity changes.

## Stop conditions

Stop and preserve the failure on any policy, canonical-path, revision,
allowlist, size, hash, config, containment, network, custom-code,
tokenizer-boundary, context, truncation, overwrite, or determinism failure.
Do not discover another cache, download, switch artifacts, change prefix policy,
load weights, edit the registry, or weaken the verifier as a rescue.

## Non-goals and claim ceiling

- no model-weight deserialization or registry scoring;
- no OLMo or DatedGPT execution;
- no registry edits or item selection based on tokenizer results;
- no temporal, causal, behavioral, or CSTG claim;
- no training, paid compute, or network acquisition.

A passing result is Target Verified engineering evidence for the Pythia
tokenizer boundary path only. It does not make model scoring or scientific work
ready.

## Delivery

After E3, publish the implementation commit and require exact-head CI. After E5,
reconcile `PROGRESS.md`, the Transformers scoring protocol, and the development
evaluation limitation; publish the evidence-only commit on the same draft PR
and require exact-head CI again. Never merge it.
