# Pythia verified-tokenizer boundary gate — 2026-08-20

## Decision

Accept the exact-head Pythia tokenizer loader and `development-v0` boundary
audit as **Target Verified engineering evidence**. Freeze `prefix-policy=none`
for the next development-scoring gate because the manifest-bound tokenizer
reports zero native special tokens and its pre-logits probe produces identical
IDs with `add_special_tokens=True` and `False`.

This result does not authorize model scoring, registry reliability claims,
evaluation freezing, model-behavior interpretation, temporal inference, or
CSTG evidence.

## Evidence

**Observed:**

- exact clean execution head:
  `c57ce40e2b0fad6a3e1ad07a3eada7e9405ccb6d`;
- delivery gate: draft PR #33 had 18 successful exact-head checks before
  execution;
- artifact: `pythia-1b-deduped-main` at immutable revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`;
- model-manifest Git blob:
  `2dbafc0d0fe10a717e1df3d5c7920e6af661138b`;
- execution-checkout model-manifest SHA-256:
  `f3a800e95887b96ec66a660efa51ab975b17b7ec1ada0f381f502e912d9cf4f6`;
- development-registry Git blob:
  `39a229ca8a29243bc457f42c5fdc69e303bb5361`;
- development-registry SHA-256:
  `5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d`;
- portable snapshot receipt SHA-256:
  `26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc`;
- tokenizer backend semantic SHA-256:
  `1b0aca3746c0870daeb9137101cd89acbb38710fc433db83331287d5b0e47ee0`;
- native-prefix probe SHA-256:
  `f2b89b376c56b7100ec3947ae1ccd3b468eceedcfbfe7031389bae0f8c327af1`;
- final canonical audit SHA-256:
  `6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523`;
- serialized raw-report SHA-256:
  `ee11e4c99d6577fa2e3be5a53e4c17b626ff91bcdee877b295799dc5926c39bb`.

Two separate CLI invocations each returned exit code 0 and produced a
50,169-byte report. The reports were byte-for-byte identical. Both covered 12
items, 24 forms, and 48 candidates with zero failures. The largest continuation
was 20 tokens, the largest prompt-plus-continuation was 59 tokens, and the
largest within-form candidate token-count difference was 3 under the frozen
2,048-token ceiling. The frozen `none` policy emitted an empty prefix-token ID
list.

The loaded fast `GPTNeoXTokenizer` matched the manifest-bound vocabulary
(50,254), tokenizer length (50,277), BOS/EOS/UNK identity
`<|endoftext|>`/0, PAD identity `<|padding|>`/1, backend fingerprint, native
special-token count 0, and native-prefix probe. Runtime identity was Python
3.11.9, Transformers 5.15.1, tokenizers 0.22.2, and huggingface-hub 1.28.0.

Each invocation rehashed the complete five-file 2,092,816,302-byte snapshot
before and after tokenizer construction. This included integrity streaming of
the 2,090,701,528-byte safetensors file; no model weight was deserialized.
Tokenizer construction consumed only four hash-verified plain files copied to
a private temporary stage.

## Artifacts

Ignored raw reports retained locally:

- `artifacts/local/pythia-tokenizer-none-a-c57ce40.json`
- `artifacts/local/pythia-tokenizer-none-b-c57ce40.json`

Tracked implementation and protocol:

- `src/chronopersona/model_snapshot.py`
- `src/chronopersona/transformers_provider.py`
- `scripts/audit_registry_tokenizer.py`
- `docs/TRANSFORMERS_SCORING_PROTOCOL.md`

## Validation

- Both top-level `output_sha256` values recomputed successfully after removing
  their self-hash fields.
- Both nested portable snapshot-receipt hashes recomputed successfully.
- Raw report bytes and every recorded Git, manifest, registry, snapshot,
  runtime, backend, and native-prefix identity matched between invocations.
- Recursive string inspection found no worktree, cache, snapshot, staging, or
  other absolute local path.
- Offline environment variables, `local_files_only=True`,
  `trust_remote_code=False`, private staging, and the absence of a
  download-capable provider path were recorded. Network traffic itself was
  labelled `not-instrumented` and is not claimed as independently observed.
- Before target execution, the exact implementation passed 390 repository
  tests with two platform-optional skips, all three top-level validators,
  compile checks, diff checks, and all 18 exact-head PR checks.

## Risks

- This proves one tokenizer/runtime/snapshot/registry boundary path only.
- No model was loaded and no registry log probability was computed.
- Development item reliability, score invariance, calibration, capability
  ceilings, direct exposure, and contamination remain unresolved.
- OLMo remains policy-allowed but snapshot-blocked; DatedGPT remains
  license-blocked.
- Offline controls were enforced, but network traffic was not independently
  instrumented.

Rerun this tokenizer gate before scoring if the artifact revision, manifest
`tokenizer_runtime` identity, or Python/Transformers/tokenizers/huggingface-hub
identity changes. Do not rerun it merely to improve presentation.

## Next write-active deliverable

Integrate the existing model scorer with the same exact local-snapshot
boundary, bind it to this tokenizer-audit identity and a fresh clean-head
resource/load gate, separate deterministic scientific score content from
runtime execution receipt, and run only the bounded repeated Pythia development
score. Keep direct repository/cache loading and all scientific interpretation
blocked until that gate passes.
