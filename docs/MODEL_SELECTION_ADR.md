# Model Selection ADR

**Date:** 2026-08-20
**Status:** provisional; local runtime preflight passed, model benchmark pending
**Decision class:** Stage 0 model and compute architecture

## Decision

ChronoPersona will use different model sets for different scientific roles.

### Public observational audit

1. **Primary family:** DatedGPT base checkpoints at approximately 2013, 2016, 2019, 2022, and 2024, after the model-weight license is resolved. The selected revisions are now immutable.
2. **Secondary family:** PIT 4B only when custom code is reviewed and confirmed hardware can run unquantized likelihood scoring.
3. **Boundary cases:** ChronoGPT, TypewriterLM, and Kairos are analyzed separately and never pooled into one temporal trajectory.

### Causal intervention

1. **Scientifically preferred starting point:** the original OLMo 2 1B stage-1 checkpoint at step 23,100, approximately 48.44 billion tokens of prior exposure.
2. **Transformers-compatible OLMo fallback:** the published early-training checkpoint around step 20,000 / 42 billion tokens, subject to exact checkpoint-identity and memory checks.
3. **Operational fallback and second family:** Pythia 1B deduped at step 20,000, approximately 41.94 billion prior tokens.
4. **First local loading benchmark:** the immutable final Pythia 1B deduped safetensors artifact. This proves only local loading and logits throughput; it is not the causal starting point.

No model is frozen for evidence-bearing training until the local resource audit, loading benchmark, tiny continued-pretraining benchmark, and Synthetic Identifiability Calibration design are complete.

## Why one model cannot serve every role

The public model panel asks whether the evaluation detects temporal trajectories in existing model families. The causal experiment asks what happens when identical weights receive matched era-window interventions. Using independently pretrained public cutoff models as causal branches would confound era with random initialization, training order, source composition, and optimization history.

Conversely, OLMo and Pythia do not provide public historical trajectories. They provide open checkpoints and training structure needed for common-start interventions.

## Artifact audit

The machine-readable source of truth is [`../artifacts/manifests/MODEL_MANIFEST.json`](../artifacts/manifests/MODEL_MANIFEST.json). The manifest distinguishes public availability from permission and execution readiness.

### DatedGPT

**Role:** first observational family.

Strengths:

- annual 2013–2024 base checkpoints;
- approximately 1.3B parameters;
- standard `LlamaForCausalLM` loading;
- bfloat16 safetensors around 2.69 GB each;
- base variants avoid instruction-tuning differences in the primary likelihood audit.

Blockers:

- no explicit model-weight license was found in the inspected cards;
- crawl-year filtering is not document-publication time;
- annual checkpoints are independent training runs.

The selected 2013, 2016, 2019, 2022, and 2024 artifacts are pinned to
`855538883fd62ae8138789c4858e1dcb708187dc`,
`8f6d90155a97ae22dce3abf9e8234f528bee7e55`,
`8fe891bd59e31c3666112dd00139c4ed7cee9dda`,
`1e2f7b5d6a019e0eafffcac6bb3023c3662736dd`, and
`ed8abac3e81ba4f964fc92cf9e9b412123f681f4`, respectively. Resolving
identity does not resolve the missing model-weight license.

Decision:

DatedGPT remains the intended first public panel, but execution is blocked until license status is resolved. Public access alone is not treated as authorization.

### PIT

**Role:** secondary observational family.

Observed public artifact:

- `Diamegs/PIT-4B-201912`;
- custom 4B architecture;
- approximately 17.8 GB float32 safetensors artifact;
- GPT-2 BPE tokenizer;
- custom Hub code and `trust_remote_code` requirement;
- Apache-2.0 model metadata and MIT repository code.

Decision:

PIT is not the default local panel. It is scientifically valuable but operationally expensive. It can be added only after:

1. custom code at the pinned model revision is reviewed;
2. unquantized loading is measured on confirmed hardware;
3. scoring parity with the primary panel is demonstrated.

Quantization may be used for engineering exploration, but not as the primary cross-family likelihood result because quantization can alter small log-probability margins.

### ChronoGPT

**Role:** long-range historical boundary case.

Strengths:

- annual checkpoints beginning in 1999;
- explicit historical model design;
- MIT model metadata.

Blockers:

- custom modified NanoGPT U-net architecture;
- custom Python loading path;
- PyTorch binary deserialization rather than safetensors in inspected artifacts;
- materially different context, tokenizer, architecture, corpus, and training regime.

Decision:

Do not load until the pinned code and serialized files are reviewed in isolation. Never pool ChronoGPT with DatedGPT or PIT as an interchangeable replication.

### TypewriterLM

**Role:** pre-1913 boundary case.

Strengths:

- full historical pretraining;
- 7B Llama-family architecture;
- bfloat16 safetensors.

Blockers:

- approximately 14.5 GB of weights;
- no explicit model-weight license found in the inspected artifact;
- one distant historical endpoint rather than a comparable trajectory;
- corpus dominated by books.

Decision:

Metadata and conceptual boundary only unless license and hardware blockers are resolved. It does not enter the primary public panel.

### Kairos

**Role:** chronological-order boundary case.

Strengths:

- direct sequential-versus-shuffled training design;
- standard `LlamaForCausalLM` configuration at the inspected checkpoint;
- immutable Hub revision
  `e4d8791d8f2bfbd55e8ac8d6998bca7a515c6c95`;
- card-reported CC-BY-SA-4.0 model license.

Blockers:

- the root checkpoint is approximately 12.59 GB before activation overhead;
- resource requirements exceed the current 6 GB local GPU path;
- primary result concerns temporal factual knowledge rather than CSTG.

Decision:

Use its methodology to design order controls. Do not make it an initial executable panel member.

## Causal-base analysis

### OLMo 2 1B

Strengths:

- Apache-2.0 code and model ecosystem;
- open architecture, tokenizer, training configuration, logs, and intermediate checkpoints;
- 16 layers, hidden size 2,048, 16 heads, context 4,096;
- global training batch of 512 sequences at length 4,096, or 2,097,152 tokens per step;
- compatible with later common post-training and activation analysis;
- closest match to the common-start final-window design used in the nearest path-dependence work.

Preferred insertion point:

- original stage-1 step 23,100;
- inferred prior exposure: `23,100 × 2,097,152 = 48,444,211,200` tokens;
- checkpoint locator is published in the official checkpoint registry.

Blockers:

- the checkpoint locator is not yet an immutable local file-and-hash manifest;
- conversion and loading through the current OLMo-core stack need a smoke test;
- the original `allenai/OLMo` repository now identifies itself as inactive, so it should be used as immutable historical configuration evidence rather than the default execution environment;
- straightforward full-weight AdamW training is not expected to fit the reported local machine without offload, sharding, optimizer changes, or a larger GPU.

The Transformers-compatible `stage1-step20000-tokens42B` branch resolves to
`f9dd86fb2eee6a7f0c79dc6fc2f671b58523cddb`. This is not the repository's
default/main revision: the previously recorded `c70db05...` identity named
main and contained different model-weight hashes. The manifest now binds the
named early-training branch rather than conflating those artifacts.

Decision:

OLMo 2 remains the provisional scientific primary. Execution should use a pinned compatible OLMo-core version while preserving the original checkpoint/config identity.

### Pythia 1B deduped

Strengths:

- Apache-2.0;
- standard Transformers GPT-NeoX loading;
- approximately 2.09 GB float16 safetensors;
- 154 public intermediate checkpoint branches;
- exact training order and configuration released;
- 2,097,152 tokens per training step, matching the OLMo global token step size;
- operationally lighter than the published OLMo early-training Hub artifact.

Candidate insertion point:

- step 20,000;
- inferred prior exposure: `20,000 × 2,097,152 = 41,943,040,000` tokens.

Blockers:

- exact resume compatibility of the published optimizer state has not been
  verified;
- continuing with a newly initialized optimizer is a different intervention and must be declared;
- Pythia is older and less capable than OLMo 2.

The `step20000` branch resolves to
`42c3ad398033019d65b051ba284f0994cee89134`. Hub metadata lists an
approximately 2.02 GB safetensors format and a 12.20 GB `optimizer.pt` at that
revision. File presence alone does not establish that the current training
stack can resume the original optimizer and scheduler exactly.

Decision:

Pythia is the operational fallback, first loading benchmark, and plausible second-family replication. It is not silently promoted over OLMo because it is easier to run.

## Local runtime preflight

The 2026-08-20 no-model audit observed:

- Windows with an NVIDIA GeForce RTX 2060, 6,144 MiB VRAM, and compute
  capability 7.5;
- 17.13 GB physical RAM and approximately 255 GB free storage at the sampled
  time;
- PyTorch `2.13.0+cu130`, compiled for CUDA 13.0, with CUDA available;
- one benchmark-ready artifact: immutable final Pythia 1B deduped, with a
  2.09 GB declared weight size and a 5.225 GB download safety margin;
- no local Hugging Face model-weight cache, no model load, and no training.

Free RAM and VRAM are transient and must be measured again on the exact clean
benchmark commit. The benchmark runner now requires that clean, exact-commit,
no-network resource audit and enforces CUDA-build and same-filesystem disk
preflight before it can load a model. This is a tooling/runtime preflight, not
evidence that the checkpoint fits or produces valid logits.

## Dose implication

The current design-state configuration intentionally has no frozen token budget.

At the preferred OLMo insertion point:

- 10 million intervention tokens are approximately 0.0206% of prior exposure;
- 50 million are approximately 0.103%;
- 100 million are approximately 0.206%;
- 500 million are approximately 1.03%.

At Pythia step 20,000, the proportions are similar.

The nearest final-window path-dependence experiment used a 500-million-token intervention after roughly 49 billion prior tokens. This does not prove ChronoPersona needs 500 million tokens, but it makes the old 10-million planning value scientifically weak as a headline dose. The calibration must measure a dose-response before a naturalistic token budget is frozen.

## Memory implication

A one-billion-parameter model does not imply a two-gigabyte training job.

Approximate full-weight Adam-style state before activations and framework overhead can include:

- 2 GB bfloat16/float16 model weights;
- 2 GB gradients;
- 4 GB float32 master weights, depending on implementation;
- 8 GB for two float32 Adam moments;
- activations, temporary buffers, dataloader state, and checkpoint staging.

A conventional single-GPU full-weight run can therefore exceed 16 GB before a useful batch is considered. CPU offload, sharded optimizer state, activation checkpointing, reduced-precision optimizer state, or a borrowed/larger machine may be required. Each changes throughput or, in some cases, the scientific intervention and must be recorded.

## Rejected alternatives

### Use public dated checkpoints as the causal experiment

Rejected because their weights, training runs, data mixtures, and optimization histories differ.

### Use the largest available public historical model

Rejected because model size does not repair causal confounding, and Typewriter/PIT/Kairos exceed the current local-first envelope.

### Use quantized checkpoints for all primary scores

Rejected because the primary effect may be a small likelihood contrast. Quantized models can support engineering tests only unless equivalence to the unquantized result is established.

### Use PEFT as the automatic headline method

Rejected. PEFT is appropriate for smoke tests and dose reconnaissance. The headline naturalistic result requires full-weight continued pretraining or a broad-update approximation justified before results.

### Resume an intermediate checkpoint with a fresh optimizer without disclosure

Rejected. Optimizer reset changes the intervention. If exact optimizer state cannot be recovered, the reset becomes a frozen design decision and sensitivity analysis.

## Exit criteria for model selection

The ADR can move from provisional to accepted only when:

1. the committed manifest validates;
2. exact immutable 40-character Hub commit revisions are resolved for every artifact labeled `benchmark-ready`;
3. model and code licenses are verified and linked to non-empty source evidence;
4. the current tokenizer and model-score path requires `trust_remote_code=false`; reviewed custom code needs a separate vendored and audited execution path rather than a `benchmark-ready` label;
5. the current machine's exact VRAM, RAM, storage, CUDA, and software stack are recorded;
6. the immutable Pythia loading/logits benchmark succeeds or fails with an actionable reason;
7. an OLMo checkpoint loading/conversion smoke test is completed;
8. a tiny legal continued-pretraining benchmark measures memory, throughput, and checkpoint storage;
9. full-weight and PEFT modes are distinguished;
10. projected calibration and pilot costs are derived from measurements.

## Current decision

- **Public panel:** DatedGPT first after license resolution; PIT optional; other models are boundary cases.
- **Scientific causal primary:** OLMo 2 1B original stage-1 step 23,100.
- **Operational causal fallback:** Pythia 1B deduped step 20,000.
- **First approved local model benchmark:** immutable Pythia 1B deduped final checkpoint.
- **External spend:** CAD $0 unless the user explicitly approves a later measured escalation.
