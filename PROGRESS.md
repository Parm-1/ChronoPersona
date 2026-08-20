# ChronoPersona Progress

**Last updated:** 2026-08-20T05:44:48-04:00

## Decision

Accept the sole v1 attention-policy rescue as **Target Verified** for the
bounded Pythia trainer/checkpoint/resume engineering gate. The uninterrupted
and interrupted/resumed conditions completed five steps and produced exact
semantic state equality. Close this rescue without a v2 and preserve the v0
eager-attention failure as separate immutable evidence.

The next local engineering deliverable is a reusable manifest/hash-verified
snapshot loader for registry tokenizer/scorer execution. Evidence-bearing
real-source work remains externally blocked.

## Current objective

Publish the v1 target evidence on draft PR #32, require exact-head CI, then
integrate the existing registry tokenizer/scorer consumers with the verified
offline snapshot layer without reintroducing repository/cache loading bypasses.

## Current verified boundary

- **Repository implementation — Tested:** exact execution head
  `3f03885b0237933ffb2b2f2a68bcf0e8f168a5d3` passed 354 tests with one
  optional skip in a clean detached worktree. The pilot, model-manifest, and
  development-evaluation validators and diff checks passed. The stored frozen
  no-network plan and its self-hash validated from both run identities.
- **Delivery — Tested:** draft PR #32 is open from
  `feat/tiny-training-resume-gate` to `main`; all 18 exact-head checks passed
  at `3f03885`. PR #31 was merged externally at the preserved v0 head
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

## Risks

- The smoke is only five steps on one GPU/runtime and does not establish
  sustained stability, broad-update capacity, or scientific training adequacy.
- Direct registry tokenizer/scorer loading remains deliberately disabled until
  it consumes a reusable verified-snapshot interface. A populated cache is not
  proof of content integrity.
- Rights-qualified, historically bounded A/B/C source samples, source-role
  feasibility, evaluation sealing, synthetic calibration, and branch-level
  cost evidence remain unresolved.
- The primary worktree contains an unknown untracked
  `.github/pull_request_template.md`; preserve and exclude it unless its
  provenance and intent are separately accepted.

## Delivery state

- Branch: `feat/tiny-training-resume-gate`
- Target execution head and last green PR #32 head before the evidence update:
  `3f03885b0237933ffb2b2f2a68bcf0e8f168a5d3`
- Draft PR #32: `https://github.com/Parm-1/ChronoPersona/pull/32`
- PR #31: externally merged at `f2568ab`; it does not contain the v1 rescue.
- No merge by Codex, force push, release, repository-visibility change, paid
  operation, model/data publication, or third-party contact occurred.

## Next write-active deliverable

1. Require green exact-head CI for the scoped evidence commit on draft PR #32.
2. After that delivery gate passes, freeze a small plan for the shared
   manifest/hash-verified snapshot loader.
3. Integrate tokenizer and model consumers without network-on-load or an
   unverified-cache path.
4. Run dependency-light regression tests, then bounded offline tokenizer and
   registry-scoring target checks on the verified Pythia snapshot.

Do not reopen or tune v0/v1. Do not infer a scientific result from this gate.
