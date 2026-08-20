# Pythia development-v1 scoring failure — 2026-08-20

## Decision

Classify the frozen `development-v1` E4 target pair as **Target Failed** at its
resource/publication gate. Attempt A consumed the exact canonical schedule and
completed all 224 candidate forwards, then failed the post-score resident-VRAM
check before a score artifact was published. Under the predeclared stop rule,
attempt A is consumed, attempt B must not run, and the pair must not be retried
for timing or presentation.

This failure does not establish or refute model-level item coherence. Candidate
logits and scores were produced transiently inside the failed process, but no
score file was retained and no item, form, pole, margin, or token-logprob result
was inspected. Measurement reliability, criterion validity, temporal behavior,
causal evidence, and CSTG remain unestablished.

## Evidence

**Observed:**

- exact clean execution head:
  `e435c40f1b1b2c9e8be1c1f3bb6ecd1ea9c89aa0`;
- draft PR #36 had 18/18 successful push/pull-request checks on that exact head
  before execution;
- run ID: `run-3aa8058dced36e7e88802079925500df`;
- frozen profile: `development-v1-pythia-reliability-v0`;
- attempt/mode: A / `canonical`;
- started: `2026-08-20T16:43:30.629437-04:00`;
- failed: `2026-08-20T16:44:38.951425-04:00`;
- failure stage: `post-score-resource-check`;
- error: `free VRAM is below the model-load safety threshold`;
- valid score published: `false`.

The receipt binds scoring-config Git blob
`967868cb1e4f23b7992e88b0fb9e604bcfdeba5c` and canonical run-spec SHA-256
`e4de6ef590939e156f862f452585678cdc21a7872b6d18c0aaf36464f984bb86`,
registry SHA-256
`81eb8e331d9fbd8d80ec675f209998e081e00834e5d1d141e2979b4f541c49ea`,
accepted tokenizer raw/output SHA-256
`acbb6fed70670c484e719c00775f95532f7282a76579c4c5d12804b5f3e2f76d` /
`8c4f75718ed6da986e2f7c316a62e6c420069577e2fb39919972d91a5857f0bb`,
and portable snapshot receipt
`26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc`.

The verified model was `GPTNeoXForCausalLM` with 1,011,781,632 FP16
parameters on `cuda:0`, vocabulary width 50,304, eval mode, Transformers
`sdpa`, PyTorch MATH-only SDPA, deterministic algorithms, and no quantization,
device map, offload, meta tensors, or autocast. Loading diagnostics reported no
missing, unexpected, mismatched, or error keys.

The canonical execution schedule has trace SHA-256
`ecec74a48757c381b80af5206268b7beb0b7f1baa38a9918a4d0aaf48d2a9706`.
Runtime metrics prove 224 candidate-occurrence forwards with no deduplication:
18,672 forwarded tokens, 18,448 predicted tokens, 3,216 continuation tokens,
and 6.073412 seconds of aggregate forward time. These topology/timing values do
not expose pole outcomes.

The last successfully preserved resident audit was the post-load audit. It
recorded 1,789,919,232 bytes (1,707 MiB) of conservative free VRAM, above the
frozen 1,610,612,736-byte resident floor. After all forwards, a fresh
post-score observation fell below that floor and the validator raised before
returning the observation to the receipt. The exact failing free-VRAM value is
therefore not preserved. The failure itself is fail-closed and sufficient to
reject E4; the missing exact value is an evidence-schema limitation, not a
reason to rerun.

## Artifacts

The raw audit and failure receipt remain ignored because they contain local
paths, process, host, filesystem, and GPU identifiers. Hash-matched private
backup copies exist in a separate non-Git directory outside every public
worktree.

| Artifact | Bytes | File SHA-256 |
|---|---:|---|
| `artifacts/local/pythia-v1-score-resource-a-e435c40.json` | 2,433 | `f10cf8d37c53dc30df3f04d16e3b3523215b09a503355945159fd4e57da1e1de` |
| `artifacts/local/pythia-v1-score-runtime-a-e435c40.json` | 32,515 | `19ded6dc8642fd661ac0451b529a52219df563802be6d8d714ce0068e29aa9a7` |

The receipt self-hash is
`79253400d524b883f41073d0be77aa9d0dd3339372ea22ed95e72f1541b8290b`.
No `pythia-v1-score-a-e435c40.json` file exists, and no attempt-B audit,
receipt, score, comparison, or coherence artifact was created.

The actual local filenames use the seven-character suffix `e435c40`, while the
frozen PowerShell example derives an eight-character `e435c40f` suffix. The
receipt and audit bind the complete Git head, so this naming deviation did not
cause or obscure the resource failure. It is nevertheless preserved as a
procedural deviation and the evidence files must not be renamed.

## Validation

- The 32,515-byte failure receipt is canonical pretty JSON.
- Its raw file SHA-256 and canonical self-hash recomputed successfully.
- The receipt records `status="failed"`, `scientific_claim_authorized=false`,
  `network_access_permitted=false`, and `network_observation="not-instrumented"`.
- Offline/local-only controls, private verified staging, `local_files_only`, and
  no-download execution were enforced. Traffic was not independently traced.
- The score/output reservation was rolled back and the scorer process, CUDA
  allocation, private stage, and shared heavy-job lock released naturally.
- No unrelated process was stopped or reconfigured to create headroom.

## Risks and claim ceiling

- The frozen v1 reliability criteria were never evaluated because no valid
  deterministic score artifact or A/B comparison exists.
- The post-score resource observation that triggered the failure is not
  embedded in the failure receipt, so only the threshold breach—not its exact
  magnitude—is durable.
- A seven-character evidence filename suffix deviated from the frozen example;
  full content/head bindings remain intact.
- This is one failed engineering attempt on one RTX 2060 and one software
  stack. It is not evidence about model preference, temporal behavior, causal
  training, or CSTG.

## Next write-active deliverable

Publish this bounded failure record, ledger row, and decision without exposing
the raw machine-specific files. Close the v1 canonical/reverse pair: do not run
attempt B and do not rerun A. Any future scoring condition requires a new
recorded design decision; the existing plan permits a rescue only after an
independently demonstrated implementation defect unrelated to pole outcomes,
and no such defect has been established here.
