# Pythia development-v1 tokenizer coherence gate — 2026-08-20

## Decision

Accept E2 as **Target Verified tokenizer engineering evidence** for exact head
`fb8cff1495fedef9c08d5426efbea53234339a29`. Two observed fresh invocations
produced distinct files with exactly identical canonical bytes. The frozen
dependency-light verifier accepted both reports and every 14-item / 112-form /
224-candidate tokenizer constraint.

This result authorizes E3 scorer-profile implementation only. It does not
authorize development-v1 model execution until that profile is delivered and
passes exact-head CI. It establishes neither measurement reliability nor a
scientific result.

## Evidence

### Execution and delivery identity

- Branch: `feat/development-measurement-reliability`
- Draft PR: `#35`, stacked on `feat/verified-registry-scoring`
- Execution head: `fb8cff1495fedef9c08d5426efbea53234339a29`
- Parent head: `a7dd27c63179e87c8f585adde3e6e2902d72c5d3`
- Exact-head CI before execution: 18/18 successful checks across Python 3.11,
  3.12, and 3.13 for both push and pull-request events
- Registry SHA-256:
  `81eb8e331d9fbd8d80ec675f209998e081e00834e5d1d141e2979b4f541c49ea`
- Criteria SHA-256:
  `d73b9d4d575f64587c5aea9acc18a6073a42bb1bd70491d29bd8422e95a73bca`
- Model-manifest / registry / criteria Git blobs:
  `2dbafc0d0fe10a717e1df3d5c7920e6af661138b` /
  `97ff9353f4c509c413936d3d3279f738aeb047e0` /
  `cc2f72232a82dc0d69dc9173203c2ddd9b3d7333`

### Deterministic tokenizer evidence

| Evidence | Value |
|---|---|
| Attempt A raw SHA-256 | `acbb6fed70670c484e719c00775f95532f7282a76579c4c5d12804b5f3e2f76d` |
| Attempt B raw SHA-256 | `acbb6fed70670c484e719c00775f95532f7282a76579c4c5d12804b5f3e2f76d` |
| A/B file size | 587,948 bytes each |
| Shared report self-hash | `8c4f75718ed6da986e2f7c316a62e6c420069577e2fb39919972d91a5857f0bb` |
| Verification raw SHA-256 | `d15cdbd75fe540fd1b6a2710614ab3c85b6a85385003cab15b2792a2a158853c` |
| Verification self-hash | `64874e3dd26a150ca34a7000ced4bc52ddd5645cfea82edf05ab6f0cbfe60c72` |
| Snapshot receipt | `26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc` |
| Loaded-tokenizer identity | `e4128adadf87e0b6250e39b8c5409db704d968deee6dd8da671dcda02da875eb` |
| Runtime identity | `62d2bf7a6341ad42fd3f7042f35d05c2942a56a569a39303df5e3c81cd8c1156` |

Both audit files are canonical pretty JSON, self-hash-valid, byte-for-byte
equal, and recursively free of absolute local paths. The deterministic report
schema intentionally contains no process ID or timestamp. Separate fresh
processes were directly observed by the executor; file distinctness plus byte
equality proves two publications and deterministic content, but the content
alone is not cryptographic proof of independent execution.

### Coverage and token constraints

- Items / forms / candidates: 14 / 112 / 224
- Failures: 0
- Maximum continuation length: 18 tokens
- Maximum full sequence length: 127 of 2,048 tokens
- Maximum within-form token-count difference: 0
- Prompt/continuation hashes, prompt-context identity, candidate pole/order,
  token IDs, and prediction indices: 224/224 valid
- Token-ID range observed: 13 through 50,010, below tokenizer length 50,277
- Every exact continuation string had one token-ID sequence across contexts,
  templates, and candidate order

| Item | Common continuation tokens |
|---|---:|
| evidence-point-accuracy-versus-interval-calibration | 16 |
| evidence-mixed-versus-target-matched-sample | 16 |
| evidence-underdetermined-commitment | 16 |
| evidence-measurement-versus-checking-fault | 12 |
| evidence-replication-versus-method-independence | 16 |
| evidence-specific-measurements-versus-broad-model | 13 |
| procedure-independent-versus-joint-review | 14 |
| procedure-live-coverage-versus-check-capacity | 13 |
| procedure-privacy-versus-detection | 13 |
| procedure-comparison-versus-uniform-scope | 18 |
| procedure-review-redundancy-versus-coverage | 18 |
| procedure-fit-evidence-versus-exposure | 16 |
| procedure-alternative-rationale-versus-implementation-detail | 10 |
| procedure-rationale-breadth-versus-depth | 10 |

### Containment and runtime boundary

- Python: 3.11.9
- Transformers / tokenizers / huggingface-hub: 5.15.1 / 0.22.2 / 1.28.0
- Native prefix policy: `none`
- Network access permitted: false
- Network observation: `not-instrumented`
- Local-only and offline environment controls: enforced
- Tokenizer files downloaded: false
- Model weights downloaded: false
- Model weights deserialized: false
- Scientific claim authorized: false
- Manifested safetensors bytes rehashed for snapshot integrity:
  2,090,701,528

Rehashing the weight file proves byte identity; it is not model loading or
tensor deserialization.

## Artifacts

- Ignored attempt A:
  `artifacts/local/pythia-v1-tokenizer-a-fb8cff1.json`
- Ignored attempt B:
  `artifacts/local/pythia-v1-tokenizer-b-fb8cff1.json`
- Ignored verifier report:
  `artifacts/local/pythia-v1-tokenizer-verification-fb8cff1.json`
- Frozen criteria:
  `configs/evaluations/development-v1-reliability-v0.json`
- Frozen registry: `evaluations/registry/development-v1.jsonl`
- Internal pre-logits review:
  `evaluations/reviews/development-v1-internal.md`

All three ignored raw artifacts have a separate private hash-matched backup.
This tracked report publishes only portable identities and aggregates.

## Validation

- Both tokenizer invocations exited 0 from separate fresh processes.
- `verify_measurement_reliability.py tokenizer` returned `passed=True` with no
  errors.
- An independent standard-library replay completed 5,824 structural,
  hash-binding, token-boundary, topology, and arithmetic assertions with zero
  discrepancies.
- The implementation head was clean during both executions and remained bound
  to the same manifest, registry, criteria, snapshot, tokenizer, and runtime
  identities.

## Risks

- Internal replay is not external validation or independent peer review.
- Network traffic was not independently instrumented. The evidence proves the
  enforced offline/local-only code path and absence of a download-capable
  provider path, not observed network silence.
- This gate tests exact tokenizer boundaries and deterministic evidence only.
  It does not test model logits, score direction, prompt-order invariance,
  criterion validity, stable reliability, or CSTG.
- Direct-exposure and contamination reviews remain pending until real source
  manifests exist.

## Next write-active deliverable

Implement E3 as an exact allowlisted development-v1 scorer profile with
canonical-versus-reverse provider scheduling and canonical serialization.
Preserve v0 compatibility and reject every cross-profile substitution before
optional model import. Do not run development-v1 model logits until E3 is
committed, delivered, and green on its exact head.
