# Resource Constraints

This document is a binding design input. ChronoPersona should maximize scientific information per dollar and per unit of available compute, not maximize model size or branch count.

## Reported resources

### Current machine

- GPU: NVIDIA GeForce RTX 2060, 6,144 MiB VRAM, compute capability 7.5
- System RAM: 17.13 GB decimal (16 GiB class)
- CPU: 12 logical processors
- Sampled free storage on the intended local drive: approximately 251 GB
- Runtime: PyTorch `2.13.0+cu130`, compiled CUDA 13.0, CUDA available
- Model load, bounded inference, and five-step LoRA training/checkpoint/resume
  throughput: recorded; sustained thermals and full-width training remain
  unmeasured

### Potential borrowed machine

- GPU: NVIDIA RTX 5070
- System RAM: 32 GB
- Availability, GPU VRAM, free storage, software environment, and permission window: not assumed

The current-machine values were measured by the no-network resource audit on
2026-08-20; free RAM, VRAM, disk, and thermals remain live values that must be
remeasured on the exact run head. The borrowed-machine values remain reported
and unverified.

For final-Pythia loading and bounded training measurements, the user explicitly
authorized using as much host RAM as needed on 2026-08-20. Those local runs may
therefore waive the conservative available-RAM margin while continuing to
record live and peak RAM. This does not waive GPU, disk, artifact-integrity,
exact-head, or severe system-instability stops, and it does not by itself
authorize a larger training plan.

## User objective

Spend as little money as possible while producing the strongest credible paper.

This means:

- do cheap falsification before expensive confirmation;
- prefer public artifacts and local inference where scientifically adequate;
- do not save money by weakening the causal design until the result becomes uninterpretable;
- do not spend money to rescue an unpromising or unidentifiable design;
- escalate only for a named, decisive experiment whose cheaper predecessors passed.

## Default authorization envelope

- External-compute spend: **CAD $0**
- Paid data or model licenses: not authorized
- Hardware purchases: not authorized
- External accounts created for the project: not authorized
- Parallel GPU training jobs: one maximum
- Repository publication, model release, and dataset release: not authorized by this document

Explicit user authorization is required to change any of these boundaries.

## Compute ladder

Use the lowest rung capable of answering the current question.

### Rung 0 — CPU and repository-only work

Use for:

- literature and license audit;
- manifests, hashing, deduplication, and leakage tooling;
- evaluation authoring;
- scorer unit tests with synthetic logits or tiny fixtures;
- statistical simulations;
- dry runs and run-registry testing;
- report generation.

### Rung 1 — Current local GPU

Use for:

- the smallest practical public-checkpoint loading test;
- conditional-log-probability smoke tests;
- tiny legal training benchmarks;
- PEFT pipeline validation;
- calibration dose reconnaissance when memory-safe.

Do not assume that full-weight optimizer states fit an RTX 2060.

### Rung 2 — Borrowed RTX 5070 machine

Use only after access is confirmed and the run has a measured purpose.

Priority uses:

- the selected synthetic calibration;
- full-weight feasibility tests at a justified model size or insertion checkpoint;
- the smallest evidence-bearing branch set that cannot run on the current machine;
- throughput measurements needed to price a later confirmation.

Do not occupy the borrowed machine with broad exploratory sweeps that could have been eliminated by local simulations or smaller tests.

### Rung 3 — Paid compute

This is an explicit escalation, not a default.

A proposal for paid compute must state:

- exact model and revision;
- exact run count;
- token budget and updates;
- memory and storage requirement;
- measured throughput basis;
- expected wall-clock range;
- minimum provider configuration;
- estimated CAD cost including failed-run allowance and storage;
- scientific decision enabled;
- cheaper alternatives already exhausted;
- stop condition.

No rental begins until the user approves the specific plan.

## Training gates

Substantial training is blocked until all are true:

1. novelty remains defensible;
2. timestamp-native sources and rights are qualified;
3. direct domain exposure is bounded;
4. the evaluation and scorer are reliable;
5. local memory and throughput are measured;
6. the token budget is frozen;
7. synthetic calibration is designed;
8. the run registry and resumption path work;
9. projected storage fits;
10. the user has authorized any nonzero external spend.

Naturalistic interpretation is blocked until Synthetic Identifiability Calibration passes.

The smaller trainer/checkpoint/resume prerequisite passed on the bounded v1
LoRA smoke. The 12-branch two-era/two-source pilot remains blocked by source,
evaluation, synthetic-calibration, causal-checkpoint, broad-update, and cost
gates; the smoke does not satisfy those requirements.

## Method constraints

- PEFT may be used for debugging, scorer validation, and dose reconnaissance.
- PEFT alone does not automatically support the headline causal claim.
- Full-weight continued pretraining is preferred for the central naturalistic experiment.
- Another broad-update approximation is allowed only when its adequacy is argued before results.
- Training insertion point is a causal variable and must be fixed.
- Do not attach a tiny adapter to a completed modern model and describe the result as a historically bounded model.
- Do not increase model scale merely because a smaller result is null. A scale rescue is allowed once and must be predeclared.

## Storage constraints

Before downloading or generating large artifacts, record:

- compressed and expanded model size;
- optimizer and gradient-state multiplier;
- checkpoint count and retention policy;
- dataset cache size;
- generated-output size;
- free-space margin;
- cleanup and recovery plan.

Prefer:

- pinned revisions;
- shared immutable caches;
- sparse checkpoint retention;
- hashes and manifests instead of duplicated corpora;
- resumable downloads;
- deletion only after artifact identities are preserved.

Do not commit model weights, raw corpora, or large checkpoints to Git.

## Scheduling constraints

- One write owner per artifact.
- One training job at a time.
- Do not run multiple seeds concurrently on the current machine.
- Avoid making the daily-use computer unusable for speculative sweeps.
- Prefer interruptible checkpoints and clean resume semantics.
- Stop immediately on thermal instability, disk exhaustion risk, hash mismatch,
  repeated out-of-memory failure, or severe desktop instability. Record paging;
  bounded final-Pythia work may use it under the explicit low-RAM override.

## Budget decision format

Any request to increase compute must be presented as:

**Decision:** what authorization is requested.  
**Evidence:** measured local limitation and passed scientific gates.  
**Minimum plan:** smallest run that resolves the decision.  
**Cost:** estimated CAD range and assumptions.  
**Failure allowance:** maximum authorized loss from failed runs.  
**Output:** exact artifact and decision produced.  
**Stop rule:** when the run terminates without further escalation.

## Current resource decision

The repository remains at Rungs 0–1 and CAD $0. The user explicitly authorized
model downloads and training on 2026-08-20. Pinned acquisition and bounded
loading/logits passed. The first tiny-LoRA v0 control failed before backward;
its sole attention-only v1 rescue then passed the five-step control and planned
interruption/resume equality gate with one job at a time. This bounded smoke
does not establish sustained or broad-update fit and does not authorize the
full naturalistic branch set. The exact Pythia tokenizer boundary audit passed
twice without deserializing model weights. The next local operation is bounded
offline registry model-scoring integration through the existing hash-verified
snapshot and accepted tokenizer identity; integrity, swapping, OOM, thermal,
disk, and scientific stop rules remain.
