# ChronoPersona Progress

**Last updated:** 2026-08-20T09:37:11-04:00

## Decision

Accept exact head `c57ce40` as **Target Verified engineering evidence** for the
Pythia verified-snapshot tokenizer boundary path. Two fresh invocations audited
all 12 development items, 24 forms, and 48 candidates with zero failures and
byte-identical reports. Freeze native `prefix-policy=none` before logits.

Accept the dependency-light registry-scoring implementation as **Tested** in
the scoped working tree. Keep target scoring blocked until the implementation
is delivered and exact-head CI passes; then require fresh clean-head resource
evidence before either attempt. No development logits have been inspected.
Preserve the completed v0/v1 training evidence without rerunning it.

## Current objective

Deliver the tested scorer on `feat/verified-registry-scoring`, obtain exact-head
CI, then execute the frozen two-attempt gate only if fresh resource audits pass.
Require byte-identical deterministic scores and independently valid runtime
receipts.

## Current verified boundary

- **Training implementation — Tested:** exact execution head
  `3f03885b0237933ffb2b2f2a68bcf0e8f168a5d3` passed 354 tests with one
  optional skip in a clean detached worktree. The pilot, model-manifest, and
  development-evaluation validators and diff checks passed. The stored frozen
  no-network plan and its self-hash validated from both run identities.
- **Delivery — Tested:** draft PR #32 is open from
  `feat/tiny-training-resume-gate` to `main`; all 18 exact-head checks passed
  at evidence head `fa809ed`. PR #31 was merged externally at the preserved v0 head
  `f2568ab`. Agents did not merge either PR and are not authorized to merge
  PR #32.
- **Artifact — Tested:** the exact five-file Pythia snapshot at revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2` remains hash verified and
  offline. The 2,090,701,528-byte safetensors SHA-256 is
  `fdb3f09a4a4d30678e021247e71f5b160bdd147de2aedd2d7d25e01feecc8e13`.
- **Inference — Target Verified:** exact head `3f03885` loaded 1,011,781,632
  frozen FP16 parameters on the RTX 2060 under explicit Transformers `sdpa`,
  PyTorch `SDPBackend.MATH`, and disabled reduced-precision math-SDPA
  reduction, then produced finite logits.
- **Training v0 — Target Failed:** run
  `run-b035b9becad60b6dc55ff3fd6fba6016` at `f2568ab` failed on its first
  forced-eager forward. It completed zero steps/tokens and no backward or
  optimizer update. Its config, run tree, and evidence remain immutable.
- **Training v1 — Target Verified:** control and planned interruption/resume
  run `run-1b8f0867fbd6038265f609b3595ae93d` completed five optimizer steps,
  640 input tokens, and 635 causal targets. Both independent verifiers passed;
  the comparator returned `equal` for adapter, optimizer, scheduler, scaler,
  CPU/CUDA RNG, counters, losses, and complete state.
- **Scientific boundary — Externally blocked:** the v1 result is engineering
  evidence only. No real-source qualification, model-behavior result,
  temporal effect, PEFT-adequacy result, or CSTG evidence exists.
- **Tokenizer boundary — Target Verified:** exact clean head `c57ce40` produced
  two byte-identical offline-enforced reports over 12 items, 24 forms, and 48
  candidates with zero boundary/context/truncation failures. Both report and nested
  snapshot-receipt self-hashes validate; no local path or model deserialization
  occurred.
- **Tokenizer delivery — Tested:** evidence head `dd0b564` is pushed on draft
  PR #33 and all 18 exact-head checks passed. That head is the immutable baseline
  for the separate scoring branch.
- **Scoring implementation — Tested:** the complete scoped scorer working-tree
  diff based on `fd487dd` passed 457 tests with two platform-optional symlink
  skips, production-module compilation, all three top-level validators, and
  diff checks. Adversarial tests cover exact score semantics, complete resource
  evidence, model/runtime identity, output transactions, failure receipts,
  final Git/input rebinding, and byte-exact repeat verification. This is
  pre-execution Tested evidence; no exact-head CI or target-scoring evidence
  exists yet, and no development logits were inspected.

## Evidence

- v1 plan SHA-256:
  `4bc8104a3545c0df0b14371a24c09d278dcb5006c281a540330bb09350a628b4`
- v1 run ID: `run-1b8f0867fbd6038265f609b3595ae93d`
- v1 final manifest SHA-256:
  `78ae0dd9272e6d046c237cf2b10243691098c70234a8b3db2f1c353b347f365a`
- v1 comparator CLI self-hash:
  `9206851c74168bd9cacd7e46d326c697f501cfdc1c23d7c64339bec73936f2af`
- v1 tracked report:
  `reports/stage0/pythia_lora_resume_gate_2026-08-20.md`
- v0 diagnostic:
  `reports/stage0/pythia_lora_attention_diagnostic_2026-08-20.json`
- decisions: `docs/DECISIONS.md` D-029 and D-030
- compute ledger: failed v0 plus completed v1 load, control, and resume rows
- tokenizer report:
  `reports/stage0/pythia_tokenizer_boundary_gate_2026-08-20.md`
- tokenizer canonical output SHA-256:
  `6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523`
- portable snapshot receipt SHA-256:
  `26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc`
- tokenizer decision: `docs/DECISIONS.md` D-031

## Artifacts

- Frozen historical config: `configs/runs/pythia-lora-smoke-v0.json`
- Completed sole-rescue config: `configs/runs/pythia-lora-smoke-v1.json`
- Completed feasibility plan: `.agent/plans/active-pythia-local-feasibility.md`
- Protocol: `docs/LOCAL_BENCHMARK_PROTOCOL.md`
- Local ignored cache: `artifacts/local/hf-cache`
- Clean execution worktree:
  `C:\Users\sandh\Documents\Codex\2026-08-20\chronopersona-run-d812ba8`
- v1 local run roots:
  `runs/pythia-lora-smoke-v1/{control,resumed}/run-1b8f0867fbd6038265f609b3595ae93d`
- Preserved v0 run root:
  `runs/pythia-lora-smoke-v0/control/run-b035b9becad60b6dc55ff3fd6fba6016`
- Ignored tokenizer reports:
  `artifacts/local/pythia-tokenizer-none-{a,b}-c57ce40.json`
- Frozen scorer config:
  `configs/runs/pythia-development-score-v0.json`
- Active scorer plan:
  `.agent/plans/active-verified-registry-scoring.md`

## Validation

- Exact clean head `3f03885`: 354 passed, one optional skip; all three
  top-level validators and diff checks passed.
- Exact-head PR #32: all 18 checks passed before the evidence-only update.
- Explicit MATH-policy load report: complete, finite, offline, exact snapshot.
- Control verifier: `status=verified`, five steps.
- Resumed verifier: `status=verified`, planned fail/resume topology, five steps.
- Comparator: `status=equal`, identical final manifest and all state semantic
  hashes.
- Maximum allocated/reserved CUDA memory: 2,203,960,320 / 2,275,409,920
  bytes. Maximum process RSS: 2,807,263,232 bytes. The resume explicitly used
  the authorized host-RAM threshold override; all other gates passed.
- Tokenizer implementation: 390 tests passed with two platform-optional skips;
  all three validators, compile, and diff checks passed. Draft PR #33 then
  passed all 18 exact-head checks at `c57ce40` before target execution.
- Tokenizer target: both fresh invocations exited 0; raw reports were 50,169
  bytes with identical SHA-256
  `ee11e4c99d6577fa2e3be5a53e4c17b626ff91bcdee877b295799dc5926c39bb`.
  The canonical and receipt self-hashes recomputed, every candidate passed,
  runtime/backend/native-prefix identities matched, and recursive inspection
  found no absolute local path.
- Scoring implementation working tree: 457 passed, two platform-optional
  symlink skips; pilot, model-manifest, and development-registry validators
  passed; compile and `git diff --check` passed. Independent read-only review
  found no remaining provider, resource-verifier, or output-transaction
  blocker after replaying the adversarial regressions.

## Risks

- The smoke is only five steps on one GPU/runtime and does not establish
  sustained stability, broad-update capacity, or scientific training adequacy.
- The verified tokenizer path is accepted only for exact Pythia and this
  runtime/registry identity. Registry model scoring remains blocked; a
  populated cache or passing tokenizer audit is not proof that model scoring is
  resource-safe, deterministic, or reliable. Target scoring remains blocked
  until exact-head implementation CI passes and a fresh resource audit
  satisfies every frozen threshold.
- Rights-qualified, historically bounded A/B/C source samples, source-role
  feasibility, evaluation sealing, synthetic calibration, and branch-level
  cost evidence remain unresolved.
- The primary worktree contains an unknown untracked
  `.github/pull_request_template.md`; preserve and exclude it unless its
  provenance and intent are separately accepted.

## Delivery state

- Completed evidence branch: `feat/tiny-training-resume-gate`
- Completed tokenizer branch: `feat/verified-registry-loader` at green evidence
  head `dd0b56471b55babe2a4eb273381deeef2f852d49`.
- Current scorer branch: `feat/verified-registry-scoring`, created from exact
  tokenizer evidence head `dd0b564`.
- Current implementation worktree:
  `C:\Users\sandh\Documents\Codex\2026-08-20\chronopersona-verified-loader`.
- Draft PR #32: `https://github.com/Parm-1/ChronoPersona/pull/32`
- Draft PR #33: `https://github.com/Parm-1/ChronoPersona/pull/33`, stacked on
  `feat/tiny-training-resume-gate`; 18/18 checks passed at evidence head
  `dd0b564`.
- PR #31: externally merged at `f2568ab`; it does not contain the v1 rescue.
- No merge by Codex, force push, release, repository-visibility change, paid
  operation, model/data publication, or third-party contact occurred.

## Next write-active deliverable

1. Deliver the scoped implementation commit: push the feature branch and open
   a stacked draft PR against `feat/verified-registry-loader`.
2. Require exact-head CI before any development logits are inspected.
3. After CI, capture fresh audit A and run attempt A only if every frozen
   resource gate passes; then release state, capture fresh audit B, run attempt
   B, and require the offline repeat verifier to accept exact score bytes.

Do not reopen or tune v0/v1. Do not infer a scientific result from this gate.
