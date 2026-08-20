# Decision Log

Durable research decisions are recorded here. Reversals append a new entry; they do not erase prior rationale.

## D-001 — Treat temporal adaptation as an intervention

**Date:** 2026-08-17
**Status:** accepted

ChronoPersona studies behavior caused by defined corpus interventions. It does not claim to reconstruct an authentic historical person or population.

**Reason:** This is testable and keeps claims aligned with what the training design can identify.

## D-002 — Separate knowledge, style, and disposition

**Date:** 2026-08-17
**Status:** partially superseded by D-008

Temporal knowledge, temporal style, and date-neutral disposition were initially separated.

**Preserved:** knowledge and surface-era effects remain distinct from behavioral outcomes.

**Superseded:** “temporal disposition” is no longer the main construct. The project now distinguishes temporal register, residual temporal signature, source-specific effects, CSTG, path dependence, and temporal representation.

## D-003 — Start with a two-slice 2008/2024 pilot

**Date:** 2026-08-17
**Status:** superseded by D-010 and D-011

The initial scaffold proposed a maximally separated 2008/2024 pilot.

**Reason for supersession:** a single-source, cutoff-like contrast does not identify a source-general era component. The revised program uses synthetic calibration followed by provisional 2012–2013 versus 2018–2019 era windows across independent sources.

## D-004 — Require unadapted and date-shuffled controls

**Date:** 2026-08-17
**Status:** superseded in scope by D-012

The initial pilot required an unadapted checkpoint and date-shuffled control.

**Preserved:** an unadapted base and order/shuffle diagnostics remain useful.

**Expanded:** the required minimal naturalistic controls are now common generic continuation, matched mixed-era text, within-era pseudo-era placebo, and an order control where feasible.

## D-005 — Freeze evaluation before trained outputs

**Date:** 2026-08-17
**Status:** accepted and strengthened

A versioned evaluation registry, scoring procedure, meaningful-effect threshold, exclusions, and primary contrasts must be frozen before confirmatory condition outputs are inspected.

**Reason:** The project has many plausible constructs and metrics. Without a freeze, researcher degrees of freedom could manufacture a narrative.

## D-006 — Prefer a cheap falsification sequence

**Date:** 2026-08-17
**Status:** accepted and strengthened by D-015

Literature, data, measurement, sensitivity, and throughput gates precede large training runs.

**Reason:** The scarce resource is credible evidence, not generated text. Early failures should be found before compute is spent.

## D-007 — No license selected yet

**Date:** 2026-08-17
**Status:** accepted

The repository remains without an open-source license.

**Reason:** Licensing code, data-derived artifacts, and collaboration outputs is a rights decision and should not be guessed during scaffolding.

## D-008 — Make CSTG the central scientific construct

**Date:** 2026-08-17
**Status:** accepted

The central measurable phenomenon is **Cross-Source Temporal Generalization**: agreement between independently induced early-versus-late behavioral contrasts from unrelated naturalistic source families, including prediction on a held-out source.

**Reason:** Historical checkpoint construction and single-source cross-domain behavioral transfer appear to have close prior art. Cross-source naturalistic replication with held-out-source prediction is the sharper causal gap, subject to Stage 0 verification.

**Consequence:** “Historical personality” remains informal motivation only. A temporal prior is an interpretation reserved for controlled CSTG.

## D-009 — Treat public dated checkpoints as observational infrastructure

**Date:** 2026-08-17
**Status:** accepted

DatedGPT, PIT, ChronoGPT, TypewriterLM, and other historical models are candidates for evaluation validation and boundary analysis. They do not substitute for the common-starting-weight causal intervention.

**Reason:** Their architectures, corpora, lineages, doses, and training procedures differ. Pooling them would confound temporal effects with model construction.

**Verification status:** exact artifacts and claims remain unverified until the Stage 0 audit.

## D-010 — Require Synthetic Identifiability Calibration

**Date:** 2026-08-17
**Status:** accepted

Before interpreting a naturalistic null, the project must show that the chosen model, dose, training method, scorer, and evaluation recover a known cross-domain latent procedural signal.

**Reason:** Without sensitivity calibration, a null cannot distinguish absence of a temporal effect from insufficient scale, dose, transfer capacity, or measurement.

**Consequence:** calibration failure makes a naturalistic null inconclusive. One predeclared rescue is permitted.

## D-011 — Use two provisional era windows and independent source families

**Date:** 2026-08-17
**Status:** accepted as provisional

The current design candidates are:

- early: 2012-01-01 through 2013-12-31;
- late: 2018-01-01 through 2019-12-31.

The exploratory causal pilot uses two independent source families and three seeds per era/source cell.

**Reason:** The windows align approximately with candidate public checkpoint years while avoiding the pandemic and widespread public generative-AI deployment.

**Boundary:** source continuity, timestamps, rights, authorship, topic balance, and event concentration determine the final windows before behavior is inspected.

## D-012 — Expand the minimum control set

**Date:** 2026-08-17
**Status:** accepted

The naturalistic pilot must include:

- unadapted base;
- common generic continuation;
- matched mixed-era corpus;
- within-era pseudo-era placebo;
- one training-order or chronology control where feasible.

**Reason:** The design must distinguish historical content from generic optimization, mixture, arbitrary partitions, and final-window recency.

## D-013 — Make held-out source C the primary confirmation

**Date:** 2026-08-17
**Status:** accepted

Source C is selected during the data audit but cannot be used for item construction, temporal-direction estimation, hyperparameter selection, dose selection, threshold selection, or mechanism-layer selection.

The shared component is estimated on A and B, frozen, and tested on C.

**Reason:** A/B agreement alone can still reflect researcher adaptation to those sources. Held-out-source prediction is the strongest practical confirmation of source-general temporal structure.

## D-014 — Measure response to common post-training

**Date:** 2026-08-17
**Status:** accepted

Selected early and late branches will receive identical later SFT and, only if justified, identical preference training.

The analysis measures both final endpoints and the change caused by the common update.

**Reason:** models with similar endpoints may respond differently to identical later training. This path-dependent response may be more informative than a static personality score.

## D-015 — Bind the project to a resource escalation ladder

**Date:** 2026-08-17
**Status:** accepted

The default resource envelope is:

- current reported machine: RTX 2060 and 16 GB RAM;
- possible borrowed machine: RTX 5070 and 32 GB RAM, not assumed available;
- CAD $0 external compute;
- one training job at a time;
- measured memory, throughput, storage, and cost before budgets;
- no rental, hardware purchase, paid license, or large branch set without explicit user authorization.

**Reason:** The user wants to spend as little as possible while preserving paper quality. Cheap falsification and measured escalation prevent both waste and scientifically underpowered spending.

## D-016 — Keep OLMo 2 1B provisional

**Date:** 2026-08-17
**Status:** accepted

OLMo 2 1B at a suitable intermediate checkpoint is the provisional causal-base candidate, not the selected model.

**Reason:** its reported openness and intermediate artifacts may support controlled insertion of an era window, but exact revisions, code, license, memory, training support, capability, and post-training compatibility must be verified and benchmarked.

## D-017 — Do not base the headline causal claim on PEFT alone

**Date:** 2026-08-17
**Status:** accepted

Parameter-efficient methods are permitted for pipeline debugging, scorer validation, dose reconnaissance, and cost estimation.

The headline naturalistic experiment should use full-weight continued pretraining or a broad-update approximation justified before results.

**Reason:** adapter geometry could be mistaken for a temporal causal effect, and attaching a small adapter to a completed modern model does not create a historically bounded model.

## D-018 — Use conditional continuation likelihoods as the primary instrument

**Date:** 2026-08-17
**Status:** accepted as provisional evaluation architecture

Primary pairwise outcomes use complete natural-language continuation likelihoods with option reversal, paraphrases, tokenizer diagnostics, raw normalized probabilities, and one prespecified calibrated alternative.

**Reason:** this reduces dependence on open-ended judge narratives and supports precise counterbalancing.

**Boundary:** scorer reliability must still be demonstrated before freezing the instrument.

## D-019 — Preserve a strict claim ladder

**Date:** 2026-08-17
**Status:** accepted

The project uses Levels 0–5:

0. no reliable effect;
1. knowledge or register;
2. source-specific temporal effect;
3. CSTG;
4. persistence or path dependence;
5. shared causal representation.

**Reason:** compelling examples, year classifiers, single-source transfer, and correlational probes should not be promoted into stronger claims.

## D-020 — One rescue per failed major gate

**Date:** 2026-08-17
**Status:** accepted

Each major negative gate permits at most one predeclared rescue: a named dose increase, scale increase, demonstrated scorer repair, or replacement of a source that failed prespecified feasibility criteria.

**Reason:** repeated redesign after observing nulls would convert falsification into positive-result search.

## D-021 — Accept the bounded content-integrity gate and stop before real-source acquisition

**Date:** 2026-08-18
**Status:** accepted at development-fixture level

Accept the deterministic content-manifest and lexical integrity implementation as the Stage 0 gate for bounded sample audits.

The accepted gate includes:

- exact raw and normalized content identities;
- portable path and symlink safety across Linux and Windows path forms;
- exact and bounded lexical near-duplicate channels;
- evaluation-overlap and direct-construct triage;
- cross-source, cross-era, cross-role, and held-out-boundary flags;
- exact authorization before opening non-fixture source-C content;
- text-free deterministic reports;
- no automatic exclusion or scientific eligibility decision.

**Reason:** Before any real historical text can support a causal training intervention, the repository must be able to prove what text it read, detect obvious contamination and overlap, preserve held-out boundaries, and produce reviewable identities without leaking source content.

**Claim ceiling:** this decision validates development tooling on redistributable synthetic fixtures only. It does not establish semantic independence, acceptable contamination rates, source-family independence, production-scale behavior, source eligibility, or any temporal model effect.

**Next gate:** bounded real-content qualification. That gate is externally blocked until small rights-qualified, version-bounded A/B samples and an explicitly authorized source-C review packet exist. Bulk acquisition and model training remain unauthorized.

**Evidence:** `reports/stage0/content_integrity_gate_decision.md` and `reports/stage0/content_integrity_bundle_recovery.json`.

## D-022 — Treat portable paths, fixture provenance, and source-C authorization as identity boundaries

**Date:** 2026-08-18
**Status:** accepted

Persisted repository, manifest, checkpoint, and artifact paths must use one canonical forward-slash relative spelling that is safe on POSIX and Windows. Traversal aliases, backslashes, drive forms, control characters, non-NFC spellings, case-insensitive collisions, Windows-reserved names, forbidden characters, and components ending in a space or period fail closed.

A content record marked as a synthetic fixture must use `synthetic-fixture` authorship provenance, and that authorship value cannot be attached to a non-fixture record. A source-C authorization is valid only when the exact bound manifest contains at least one non-fixture source-C adaptation record; extraneous authorization is rejected.

**Reason:** Cross-platform path aliases and contradictory provenance can change which bytes are read without changing a superficially similar manifest. Stale or unrelated authorization can create misleading evidence that the held-out firewall was satisfied. These are identity failures, not recoverable warnings.

**Boundary:** this decision hardens development tooling. It does not authorize source acquisition or establish that any real source is eligible.

## D-023 — Make evidence semantics executable rather than descriptive

**Date:** 2026-08-18
**Status:** accepted

Claims about token-aligned evaluation exposure, option-order counterbalancing, metadata-only operation, model readiness, and official metadata origins must be enforced by validators rather than left as documentation conventions.

The final Stage 0 review therefore requires contiguous token-sequence exposure checks, both balanced candidate orders, recursive metadata payload rejection, exact digest formats, non-negative token identities, non-positive finite log probabilities, benchmark-ready artifacts that satisfy the executable no-remote-code policy, and exact HTTPS host allowlists that redirects cannot escape.

**Reason:** A documented rule that malformed evidence can bypass is not an integrity boundary. These checks prevent silent false positives, false negatives, misleading readiness labels, and source-origin drift.

**Boundary:** these changes harden development evidence. They do not qualify real corpora, authorize network or corpus acquisition, or advance the claim ladder.

## D-024 — Accept the final Stage 0 repository hardening and preserve the external stop boundary

**Date:** 2026-08-18
**Status:** accepted subject to exact-head CI

Accept the final repository review as a hardening pass over the existing Stage 0 development system. The accepted scope centralizes portable persisted-path identity, makes bounded manifest limits apply during planning and execution, tightens fixture and source-C authorization semantics, enforces tokenizer/scorer/evaluation/model-readiness evidence, constrains live metadata requests to exact HTTPS origins, verifies generated coverage, cache, and bytecode state are absent from Git, and adds a regression guard against their return.

**Reason:** research infrastructure is only defensible when the repository state, validators, workflows, and documentation enforce the same boundaries. Machine-generated cache state and permissive type or path coercions are not valid scientific evidence.

**Claim ceiling:** this is an engineering and governance pass. It does not qualify real source content, demonstrate model sensitivity, authorize training, or advance CSTG beyond the existing claim level.

**Decision after validation:** merge only after the exact PR head passes CI, content-integrity, source, synthetic-calibration, and run-registry workflows on Python 3.11, 3.12, and 3.13. Then stop at the bounded real-content and local-model evidence boundary.

**Evidence:** `reports/stage0/final_repository_review.md`.

## D-025 — Accept the no-weight model/runtime preflight and preserve the acquisition boundary

**Date:** 2026-08-20
**Status:** accepted at metadata and runtime-preflight level

Accept the bounded local resource audit, metadata-only Hub audit, corrected
artifact identities, and benchmark-integrity hardening as the first measured
part of Milestone 0B.

The accepted preflight establishes that:

- PyTorch `2.13.0+cu130` exposes CUDA 13.0 on the local RTX 2060;
- the selected public artifacts are pinned when a live immutable revision is
  available, while missing licenses and unreviewed execution paths remain
  fail-closed;
- the OLMo `stage1-step20000-tokens42B` artifact is bound to
  `f9dd86fb2eee6a7f0c79dc6fc2f671b58523cddb`, not the distinct default/main
  artifact;
- exactly one artifact, final Pythia 1B deduped at
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`, is eligible for the first
  loading/logits benchmark;
- benchmark execution requires an exact-clean-head resource audit and records
  actionable structured failures.

**Reason:** artifact identity, executable policy, and measured machine state
must be trustworthy before a multi-gigabyte weight acquisition or an OOM can be
interpreted as model feasibility evidence.

**Claim ceiling:** no model weights were acquired, no model was loaded, no
logits or training throughput were measured, no checkpoint/resume path was
validated, and no temporal claim is advanced.

**Boundary:** the 2.09 GB final Pythia artifact is not downloaded under the
current authorization. Tiny continued pretraining remains further gated on a
successful load, measured headroom, and its own legal/resource preflight.

**Evidence:** `reports/stage0/model_compute_preflight_2026-08-20.md`.

## D-026 — Activate bounded local model acquisition and training measurement

**Date:** 2026-08-20
**Status:** accepted and active

The user explicitly lifted restrictions on model downloads and training. The
project may therefore acquire pinned, legally cleared model artifacts and run
bounded local loading and training measurements without another routine
permission request.

The first active operation remains one immutable final-Pythia acquisition and
CUDA loading/logits benchmark. Training follows only if that measurement gives
enough headroom to design a deterministic tiny checkpoint/resume gate.

**Reason:** the prior stop was an authorization boundary rather than negative
model evidence. Removing it should advance the smallest measured gate, not
silently expand to every candidate, corpus, branch, or compute environment.

**Preserved requirements:** verified license and immutable identity, no
unreviewed remote code, exact run/resource binding, one heavy job at a time,
structured failure preservation, and immediate stop on integrity mismatch,
swapping, repeated OOM, severe desktop impact, thermal/driver instability, or
disk risk.

**Scope interpretation:** the active local gate remains CAD $0 and requires no
paid service, public release, repository-visibility change, or third-party
contact. Those materially different actions are not implied merely because
local acquisition/training is now authorized.

**Claim ceiling:** authorization is not evidence. No model feasibility,
training, scorer, temporal, or CSTG claim advances until the corresponding run
passes its evidence gate.

**Current-state authority:** `PROGRESS.md` and
`.agent/plans/active-pythia-local-feasibility.md`.

## D-027 — Permit a recorded low-RAM final-Pythia load attempt

**Date:** 2026-08-20
**Status:** accepted and active for the bounded loading measurement

After the exact pinned snapshot was acquired and verified, the first offline
CUDA execution stopped before model loading because post-import available RAM
fell below the conservative two-times-weight threshold. The user then
explicitly authorized using as much RAM as needed.

Add an explicit `--allow-low-ram` execution option. It waives only the hard
available-RAM threshold while preserving both audited and live RAM values, the
threshold, whether it passed, and whether the override was used in the
structured result. Immutable file identity, offline loading, clean exact-head
binding, disk, conservative VRAM, model/logit semantics, and structured failure
gates remain unchanged.

**Reason:** the first failure measured a conservative host-headroom policy, not
model incompatibility or an allocation failure. A named and visible override
honors the user's resource authorization without silently weakening the normal
default or erasing the failed attempt.

**Claim ceiling:** a successful override run would establish only bounded local
loading/logits feasibility under the observed host-memory pressure. It would
not establish full-weight training fit, sustained stability, scorer validity,
temporal behavior, or CSTG.

## D-028 — Accept local inference and activate the tiny LoRA resume gate

**Date:** 2026-08-20
**Status:** accepted at bounded local inference level

Accept the exact-head offline Pythia measurement as evidence that the immutable
final checkpoint loads unquantized in FP16 on the RTX 2060 and produces finite
logits for the frozen synthetic probe. The successful run loaded 1,011,781,632
parameters in 2.5291 seconds, peaked at 2,042,486,784 allocated GPU bytes, and
completed three measured forward passes at 1,294.30 predicted tokens/second.

Advance to one five-step LoRA training/checkpoint/resume engineering smoke using
only the verified offline snapshot and CC0 synthetic fixtures. Compare a planned
step-three interruption plus explicit resume against an uninterrupted control.

Do not attempt a device-resident full-weight AdamW step on this GPU. An
optimistic FP16 lower bound for weights, gradients, and two same-dtype moments
is 8,094,253,056 bytes, already 1,652,260,864 bytes above total device memory
before activations and runtime overhead. Do not silently substitute CPU
offload, quantization, another optimizer, or another model.

**Reason:** inference viability clears the loader/runtime uncertainty, while the
optimizer lower bound resolves full-weight device capacity without an
intentional OOM. A tiny adapter smoke can now test the remaining trainer,
backward, checkpoint, and resume plumbing without being misrepresented as the
headline training method.

**Claim ceiling:** the inference pass is engineering evidence on one synthetic
prompt. A LoRA smoke, even if exact, proves only training infrastructure and
does not justify PEFT for the causal claim or establish any model-behavior,
temporal, or CSTG result.

**Evidence:** `reports/stage0/pythia_local_inference_2026-08-20.md`.

## D-029 — Consume the one tiny-training rescue for explicit SDPA MATH

**Date:** 2026-08-20
**Status:** executed and passed at bounded engineering level

The first frozen tiny-LoRA control at exact head `f2568ab` and run
`run-b035b9becad60b6dc55ff3fd6fba6016` failed on its first forward with
non-finite loss. It completed zero steps and zero training tokens; no backward
or optimizer update occurred. Preserve that v0 run as failed evidence and do
not resume, overwrite, or reinterpret it.

A bounded, offline, no-update discriminator used the same immutable model and
first 128-token block. Eager attention produced non-finite logits both with
zero-initialized LoRA wrappers and after removing them, and at every tested
prefix from 16 through 128 tokens. SDPA produced finite logits and loss across
evaluation, training, and gradient-checkpointing modes. Explicit MATH-only and
efficient SDPA were each finite. This observes an attention-implementation
cause; FP16 eager-attention overflow is a plausible but not independently
proven intermediate mechanism.

Consume the single predeclared rescue by creating v1. Relative to v0, change
only the run name and the full attention policy: load with Transformers
`attn_implementation="sdpa"`, constrain PyTorch SDPA to `SDPBackend.MATH`
through forward and checkpoint-recomputed backward, and disable reduced-
precision FP16/BF16 math-SDPA reduction. Bind and verify all three fields in
the configuration, plan identity, successful exact-head load report, runtime
summary, and failure evidence. The diagnostic is preserved in
`reports/stage0/pythia_lora_attention_diagnostic_2026-08-20.json`.

**Rejected alternatives:** do not change LoRA geometry, learning rate,
optimizer, loss scaler, dtype, data, token packing, sequence length, model, or
offload/quantization. Those variables occur after or outside the observed
eager-forward failure and would confound the rescue.

**Stop rule:** if the exact v1 control fails any integrity, finite-value,
memory, update, wall-time, or stability gate, stop this local training path.
There is no second tuning rescue.

**Claim ceiling:** a v1 pass would prove only the bounded trainer/checkpoint/
resume engineering gate on this exact runtime. It would not validate PEFT for
the causal design or establish temporal, behavioral, or CSTG evidence.

**Observed result:** exact clean head `3f03885` completed the sole v1 rescue.
Uninterrupted control and planned step-three interruption/resume run
`run-1b8f0867fbd6038265f609b3595ae93d` each completed five optimizer steps.
Both independent verifiers passed, and the comparator returned exact equality
for adapter, optimizer, scheduler, scaler, CPU/CUDA RNG, counters, losses, and
complete state. The shared final-manifest SHA-256 is
`78ae0dd9272e6d046c237cf2b10243691098c70234a8b3db2f1c353b347f365a`.
The rescue is closed; do not create v2 or tune v0/v1.

**Evidence:**
`reports/stage0/pythia_lora_resume_gate_2026-08-20.md`.

## D-030 — Accept the bounded resume gate and close the training rescue

**Date:** 2026-08-20
**Status:** accepted at Target Verified engineering level

Accept exact clean head `3f03885` and run
`run-1b8f0867fbd6038265f609b3595ae93d` as evidence that the frozen local
Pythia LoRA path can perform backward and optimizer updates, publish and verify
an atomic step-three checkpoint, resume in a fresh process, and reproduce the
uninterrupted final semantic state exactly. The control and resumed conditions
each completed five unique optimizer steps, 640 input tokens, and 635 causal
targets. Independent verification passed and comparison returned `equal` for
adapter, optimizer, scheduler, scaler, CPU/CUDA RNG, counters, losses, and
complete state.

Close E5 and the one-rescue path. Preserve the failed eager v0 and successful
SDPA-MATH v1 artifacts; do not rerun them to improve timing, create v2, or tune
another training variable. The next local engineering decision is whether the
existing registry tokenizer/scorer consumers can use a shared manifest/hash-
verified offline snapshot interface without trusting arbitrary cache contents.

**Rejected alternatives:** do not treat the five-step smoke as evidence that
LoRA is scientifically adequate, that a full-width causal branch fits, or that
sustained operation has passed. Do not unblock real-source or temporal claims
from an engineering equality result.

**Claim ceiling:** Target Verified for this bounded trainer/checkpoint/resume
path on the exact RTX 2060, software stack, model revision, fixtures, and
training profile only. No model-behavior, temporal, causal-training, or CSTG
claim is authorized.

**Evidence:**
`reports/stage0/pythia_lora_resume_gate_2026-08-20.md`.

## D-031 — Accept the verified Pythia tokenizer boundary and freeze native no-prefix execution

**Date:** 2026-08-20
**Status:** accepted at Target Verified engineering level

Accept exact clean head `c57ce40` as evidence that the canonical Pythia
tokenizer can be constructed only from a private copy of manifest/hash-verified
local snapshot files and can audit all 12 `development-v0` items, 24 forms, and
48 candidates without a boundary, context, or truncation failure. Two fresh
invocations produced byte-identical reports with canonical output SHA-256
`6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523`.

Freeze `prefix-policy=none` before any registry logits are inspected. The
manifest-bound tokenizer reports zero native special tokens and the exact
backend's pre-logits probe produced identical token IDs with and without native
special-token insertion. A BOS condition is therefore not the native path and
must not be selected later because it yields preferred scores.

**Rejected alternatives:** do not trust an arbitrary populated cache, load by
repository/name, enable downloads during tokenizer construction, accept a
slow/custom tokenizer fallback, add an item-specific tokenizer adapter, or run
both prefix policies and select after model scoring. Do not treat hashing the
safetensors file as model deserialization.

**Claim ceiling:** Target Verified for this exact Pythia tokenizer,
snapshot/runtime identity, and development-registry boundary path only. No
model score, reliability result, calibration result, temporal effect, or CSTG
claim is authorized. Model scoring remains blocked until its separate
clean-head resource, exact-load, verified-snapshot, and deterministic-output
gate passes.

Revisit this decision before scoring if the artifact revision, manifest
`tokenizer_runtime` identity, or Python/Transformers/tokenizers/huggingface-hub
identity changes. Otherwise preserve the passing reports without rerunning
them.

**Evidence:**
`reports/stage0/pythia_tokenizer_boundary_gate_2026-08-20.md`.

## D-032 — Use public repository visibility for standard hosted CI

**Date:** 2026-08-20
**Status:** accepted and applied by explicit user authorization

Change `Parm-1/ChronoPersona` from private to public so its existing standard
GitHub-hosted Actions workflows can use GitHub's free public-repository
capacity without changing billing or spending settings. Treat visibility as a
delivery mechanism only: it does not authorize merging, releases, a reuse
license, paid compute, or publication of models, datasets, or raw corpora.

Before exposure, scan the current tree, all reachable Git history, GitHub
issues/PRs/comments, Actions configuration, repository secrets and variables,
and publication surfaces. The audit found no credentials, private keys,
repository secrets, tracked model weights, raw corpora, releases, deployments,
Pages site, environments, or self-hosted runners. Existing workflows use
standard hosted runners, read-only default tokens, and no privileged fork
trigger.

**Accepted disclosure:** public visibility exposes every remote branch,
reachable commit, issue, PR, retained Actions log, one personal email in commit
metadata, and historical local workspace strings. These disclosures and the
fact that returning to private cannot recall third-party copies were stated
before the change. No history rewrite, force push, or remote branch deletion
was authorized or performed. The repository has no license, so public access
is not a reuse grant.

**Observed result:** GitHub reports `PUBLIC`, anonymous API and Git access work,
main and draft PR #32/#33/#34 heads are unchanged, and the fork network remains
empty. Actions remain enabled with read-only default workflow permissions;
every external contributor's fork workflow now requires approval. Secret
scanning and push protection are enabled. No billing setting changed.

**Revisit rule:** another visibility change requires explicit user
authorization. A private rollback restores GitHub access control only; it does
not retract public clones, copied logs, or indexed commit metadata.

## D-033 — Accept the repeated registry scorer path and reject instrument readiness

**Date:** 2026-08-20
**Status:** accepted at Target Verified engineering level

Accept exact clean head `cee0f2fa436578bec2f90e57e7ae512f58335323` and run
`run-25453ff5b41cda00b30ac23b046f6a5e` as evidence that the frozen Pythia
provider can load the manifest/hash-verified private snapshot stage, bind the
accepted tokenizer identity, compute finite complete-continuation log
probabilities for all 48 `development-v0` candidates, publish deterministic
scores separately from runtime evidence, and reproduce the score bytes exactly
in a second fresh process. The verifier returned `equal`; score file SHA-256 is
`c3cc112c2aa7f082858ccf60b827290893b488e7adc834293bb8054d15e1cecb`
and comparison self-hash is
`fcf155c5414bdcda7ce9cbdd12e1723da35b268d05bc3d96c369401f7850e687`.

Do not accept the development instrument as reliable. Eight of twelve items
had the same pole direction across both forms, but four of six
evidence-integration items had directional agreement 0.5. Treat this as a
pre-freeze development signal requiring controlled wording/order diagnosis,
revision, and retesting under predeclared reliability criteria. One item
aggregate and two forms also had opposite signs under the frozen primary
total-logprob margin and diagnostic mean-token margin. Preserve the primary
metric; do not select items, poles, phrasing, or the diagnostic metric to
obtain a preferred model-behavior narrative.

**Rejected alternatives:** do not round or tolerance-compare the two score
files, run a third tie-breaker, switch dtype/device/attention backend, shorten
the registry, publish machine-specific receipts, or interpret this public final
checkpoint as a causal insertion checkpoint or historical condition. Do not
rerun the passing scorer gate merely to improve timing or presentation.

**Claim ceiling:** Target Verified for the exact scorer/snapshot/tokenizer/
runtime/resource path only. The item-level output is measurement-development
evidence, not a temporal contrast, calibration result, model-representativeness
claim, causal effect, or CSTG evidence. The 60 MiB post-score VRAM margin also
does not authorize a larger or concurrent local model job.

**Evidence:**
`reports/stage0/pythia_registry_scoring_gate_2026-08-20.md`.

## D-034 — Replace the confounded two-form seed with one strict v1 coherence screen

**Date:** 2026-08-20
**Status:** accepted for pre-logits development

Preserve `development-v0` and its exact scorer evidence. Create a new
`development-v1` registry with 14 items and eight forms per item: two contexts
crossed with two continuation templates and two explicit candidate orders,
with exact 4/4 order balance. The first inheritance-oriented draft was rejected
by blind internal semantic review before tokenizer acceptance or model logits;
the current neutral constructs were rewritten from those pre-logits findings.
This is a new development identity, not a repaired or relabeled v0 result.

For each item, require all sixteen Pythia continuation records to have one
common token count between 1 and 24 before model scoring. This makes the primary
total-logprob margin and mean-token diagnostic algebraically proportional for
every form and aggregate. After the wording, tokenizer evidence, run profile,
and hashes are sealed, require eight nonzero same-sign margins for every item,
zero primary/diagnostic sign disagreements, and byte-identical scores from
fresh canonical-order and reverse-execution attempts. All 14 items must pass;
no failed form, item, or domain may be removed after inspection.

**Observed basis:** v0's two forms simultaneously changed scenario, prompt,
candidate wording, and candidate array order. Four items reversed direction,
so those factors cannot be identified separately. Unequal continuation lengths
mathematically permitted the two form-level and one aggregate primary/diagnostic
sign disagreements, while equal lengths did not prevent every reversal. Length
is therefore a controlled defect channel, not a complete causal explanation.
Candidate array order is not model-visible in the current independent-
continuation scorer; reverse execution tests engineering state/order
invariance, not behavioral label-position effects. Blind review of the initial
candidate draft found dominance or template defects in eleven of fourteen
items; that draft was discarded before acceptance evidence or logits, rather
than patched after observing pole scores.

The final blind pre-logits lock accepted all fourteen rewritten items and found
no explicit temporal, institutional, political, demographic, copied-survey, or
pole-specific moral cues. The accepted generated registry SHA-256 is
`81eb8e331d9fbd8d80ec675f209998e081e00834e5d1d141e2979b4f541c49ea`;
the criteria SHA-256 is
`d73b9d4d575f64587c5aea9acc18a6073a42bb1bd70491d29bd8422e95a73bca`.
The review remains internal and direct-exposure/contamination checks remain
pending. Its bounded evidence is preserved in
`evaluations/reviews/development-v1-internal.md`.

Prompt mention order is not independently counterbalanced in this small screen.
The v1 claim is therefore coherence under one prompt presentation, not prompt-
order invariance, an unbiased direction estimate, or criterion validity. The
model-input projection remains limited to prompt plus one continuation; pole
IDs, `reference_pole`, and `direction_note` are scoring metadata and must not be
passed to the provider.

**Rejected alternatives:** do not rewrite only the four inconsistent items,
select wording that restores a preferred pole, switch to mean-token scoring,
introduce a score-derived deadband, discard capability-like anchors after
seeing their values, run a third tie-breaker, or overwrite v0. Do not claim that
eight forms or one public checkpoint estimates stable psychometric reliability.

**Failure and rescue:** before logits, wording may change only from construct
review and tokenizer evidence. After freeze, any form reversal, exact-zero
margin, metric-sign mismatch, incomplete coverage, identity drift, nonfinite
value, truncation, or non-determinism fails the whole gate. The sole permitted
rescue is one independently demonstrated implementation correction unrelated
to pole outcomes; there is no alternate content rescue. A semantic failure
requires a new recorded design decision.

**Claim ceiling:** a pass is one-checkpoint small-set coherence evidence. It may
authorize a later multi-model development panel and expansion toward 24–40
items per primary domain. It does not establish criterion validity, a
meaningful-effect threshold, confirmation readiness, a temporal result, causal
evidence, or CSTG.

**Procedure:**
`.agent/plans/active-development-measurement-reliability.md`.

## D-035 — Accept the development-v1 tokenizer coherence gate

**Date:** 2026-08-20
**Status:** accepted; E3 scorer-profile implementation authorized

Accept exact clean head
`fb8cff1495fedef9c08d5426efbea53234339a29` as Target Verified tokenizer
engineering evidence for `development-v1-pythia-reliability-v0`. Draft PR #35
passed all 18 exact-head checks before two observed fresh offline tokenizer
invocations. Their distinct 587,948-byte reports were byte-identical with raw
SHA-256
`acbb6fed70670c484e719c00775f95532f7282a76579c4c5d12804b5f3e2f76d`;
the dependency-light verifier and a separate 5,824-assertion replay found no
discrepancy.

All 14 items, 112 forms, and 224 candidate occurrences passed. Each item has
one exact continuation-token count from 10 through 18, all sequences fit within
2,048 tokens, and no prompt, continuation, order, token-ID, index, truncation,
identity, path, or publication failure occurred. Offline/local-only controls
were enforced; traffic was not independently instrumented. The manifested
2,090,701,528 safetensors bytes were rehashed for integrity but never
deserialized. No development-v1 model logits were inspected.

Authorize only E3: implement an exact allowlisted v1 scorer profile,
canonical-versus-reverse provider scheduling, canonical serialization, and
pre-import rejection of every cross-profile substitution. Do not run the model
until that implementation is committed, delivered, and green at its exact
head. Do not reinterpret tokenizer equality as prompt-order invariance,
measurement reliability, criterion validity, temporal evidence, or CSTG.

**Rejected alternatives:** do not reuse the v0 score profile implicitly, hand
edit an accepted tokenizer report, treat one invocation as repeat evidence,
skip exact-head delivery, change token-count bounds, or proceed directly to
logits from this evidence commit.

**Artifacts:**
`reports/stage0/pythia_v1_tokenizer_coherence_gate_2026-08-20.md`,
`evaluations/registry/development-v1.jsonl`, and
`configs/evaluations/development-v1-reliability-v0.json`.

## D-036 — Accept the profile-bound development-v1 scorer delivery

**Date:** 2026-08-20
**Status:** accepted; bounded E4 authorized after the closure head and fresh resource gate pass

Accept exact E3 delivery head
`323dd0f72acf6bedc29ec68230a405214293f10d` on draft PR #36. It is stacked
on PR #35 at `dfa52a0` and passed all 18 push/pull-request checks across Python
3.11–3.13. The first E3 head `e3bd52b` passed 12/18 checks; all six CI failures
were one platform-specific expected-error-message assertion while both alias
paths remained fail-closed. The message-portable regression correction was the
only change in the accepted head.

The delivered scorer has one exact closed v0/v1 profile allowlist. The v1
profile binds config Git blob
`967868cb1e4f23b7992e88b0fb9e604bcfdeba5c` and canonical run-spec SHA-256
`e4de6ef590939e156f862f452585678cdc21a7872b6d18c0aaf36464f984bb86`,
the sealed registry and criteria, and the accepted E2 tokenizer report. Attempt
A must execute all 224 candidate occurrences in canonical order; attempt B
must execute the exact global reverse order. Neither may deduplicate the 112
text-identical duplicate pairs, and both must serialize canonical registry
order. Complete profile-bound receipts and raw resource audits are required
before the integrated repeat/coherence verifier can authorize a result.

Dependency-light adversarial review confirmed that v0 evidence remains
verifier-equal while v0/v1 prompt, candidate-text, config, registry,
tokenizer-audit, schedule, receipt, run-ID, and portable-path substitutions
fail closed. The offline working-tree suite collected 536 tests and passed 534
with two platform-optional symlink skips; focused E3 coverage passed 142 tests,
production modules compiled, all top-level validators passed, and the no-import
v1 plan froze A=`canonical`, B=`reverse`, downloads disabled, and no scientific
claim. No model weights were deserialized and no development-v1 logits were
inspected.

Authorize only the frozen E4 pair after this closure record is green at its
exact head and a fresh clean-head resource audit passes. Attempt A must fully
exit and release CUDA, private staging, and the shared heavy-job lock before
audit B. Preserve one complete comparison or one actionable failure; do not
inspect partial poles, reuse an audit, change content or metrics, add a third
run, or continue after a consumed-attempt failure.

**Claim ceiling:** Tested and exact-head-delivered scorer engineering only.
This does not establish model-level item coherence, measurement reliability,
criterion validity, a meaningful-effect threshold, temporal behavior, causal
evidence, or CSTG.

**Procedure:**
`.agent/plans/active-development-measurement-reliability.md`,
`configs/runs/pythia-development-score-v1.json`, and
`docs/TRANSFORMERS_SCORING_PROTOCOL.md` section 7A.

## D-037 — Preserve the consumed development-v1 attempt and stop E4

**Date:** 2026-08-20
**Status:** accepted; E4 Target Failed before publication

Accept exact clean execution head
`e435c40f1b1b2c9e8be1c1f3bb6ecd1ea9c89aa0` and run
`run-3aa8058dced36e7e88802079925500df` as the one consumed attempt A for
`development-v1-pythia-reliability-v0`. Draft PR #36 had passed all 18 checks
on that exact head. The fresh audit and pre-import/load gates passed, the exact
verified Pythia model loaded, and the canonical schedule completed all 224
candidate forwards. The invocation then failed at
`post-score-resource-check` because conservative global free VRAM fell below
the frozen 1,610,612,736-byte resident floor.

The output transaction rolled back: no valid score was published, no attempt-B
audit or invocation occurred, and no item, form, pole, margin, or token-
logprobability result was inspected. The canonical schedule/topology and timing
metadata are admissible engineering failure evidence; they are not a semantic
measurement result. The exact failing post-score free-VRAM value was not
retained because validation raised before returning that audit to the failure
receipt. Preserve that schema limitation rather than estimating the value.

The raw audit and receipt filenames use seven-character suffix `e435c40`, while
the frozen example would derive eight-character suffix `e435c40f`. Both
payloads bind the complete head and the deviation did not cause the resource
failure. Preserve the original names and record the deviation; do not rename or
recreate the evidence.

Attempt A is consumed under D-034 and the active plan. Do not run B, repeat A,
lower the threshold, change content/metrics, or recover transient scores. The
only possible rescue remains one separately accepted correction of an
independently demonstrated implementation defect unrelated to pole outcomes.
The current threshold breach is an observed resource failure, not by itself
proof of such a defect. Any result-blind investigation must end in a new
decision and versioned exact-head implementation before it can authorize a new
condition.

**Claim ceiling:** Target Failed for the exact E4 resource/publication gate.
Model-level v1 coherence and measurement reliability remain unknown. This is
not evidence for any model preference, temporal effect, causal result, or CSTG.

**Evidence:**
`reports/stage0/pythia_v1_scoring_failure_2026-08-20.md` and the failed v1 row
in `COMPUTE_LEDGER.csv`.

## Pending decisions

- License-cleared executable public-panel checkpoints.
- Causal base checkpoint and insertion point.
- Final era windows.
- Final source families A, B, and held-out C after real-sample qualification.
- Timestamp and authorship-confidence thresholds.
- Production duplicate, exposure, semantic-screening, and exclusion thresholds.
- Synthetic latent-policy dose, seeds, and pass thresholds.
- Meaningful-effect and equivalence thresholds.
- Full-weight training method and optimizer state strategy.
- Confirmatory seed count.
- Common SFT dataset and revision.
- Whether preference training is scientifically and financially justified.
- Human-rating requirement and ethics boundary.
- Public artifact and licensing strategy.
