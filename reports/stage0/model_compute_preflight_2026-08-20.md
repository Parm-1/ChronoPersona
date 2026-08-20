# Model and Compute Preflight

**Date:** 2026-08-20
**Scope:** Milestone 0B metadata, local runtime, and benchmark-integrity gate
**Benchmark-integrity implementation:** `713081a669b3c7b5d19a64e26d431fe753bc9c34`
**Decision:** **PASS at no-weight preflight level; stop before model acquisition**

## Decision

Accept the bounded metadata-only artifact audit and local runtime preflight as
measured Milestone 0B evidence. Torch enumerates the local CUDA device, artifact
identities are materially better specified, and the benchmark entrypoint now
fails closed on stale repository state, CPU-only Torch, inadequate disk margin,
and untrusted execution manifests.

Do not promote this to a model-feasibility pass. No model weight was acquired,
no checkpoint was loaded, no logits were produced, and no training or resume
path was exercised. The next gate requires explicit authorization to acquire
the single pinned 2.09 GB final Pythia artifact.

## Evidence

### Observed

- A no-network local audit observed Windows, 12 logical processors, 17.13 GB
  physical RAM, approximately 255 GB free storage, and an NVIDIA GeForce RTX
  2060 with 6,144 MiB VRAM and compute capability 7.5.
- PyTorch `2.13.0+cu130` reports compiled CUDA 13.0, CUDA available, and one
  CUDA device.
- The model manifest validates with 13 artifacts. Exactly one artifact is
  `benchmark-ready`: `pythia-1b-deduped-main` at immutable revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`, with a declared 2.09 GB weight
  size and 5.225 GB minimum free-disk margin.
- The default Hugging Face cache contains no model weights. The work performed
  only package installation, local resource inspection, and metadata requests.
- Windows peak process memory is now measurable. The standalone live probe
  returned a positive value, and the regression test passes.
- A deliberate execution attempt against a dirty resource audit stopped before
  dependency import or model loading and wrote structured failure JSON with
  `status=failed` and `download_completion_status=not-permitted`.

### Reported by metadata sources

- The selected DatedGPT 2013/2016/2019/2022/2024 revisions now resolve to
  immutable commits, but their inspected model cards still expose no
  model-weight license. They remain blocked.
- Kairos resolves to
  `e4d8791d8f2bfbd55e8ac8d6998bca7a515c6c95`, uses a standard Llama causal-LM
  configuration, reports CC-BY-SA-4.0, and has an approximately 12.59 GB root
  checkpoint. It remains outside the local hardware path.
- The OLMo `stage1-step20000-tokens42B` branch resolves to
  `f9dd86fb2eee6a7f0c79dc6fc2f671b58523cddb`. The previously recorded
  `c70db05...` revision is the distinct default/main artifact and has different
  model-weight hashes.
- Pythia `step20000` resolves to
  `42c3ad398033019d65b051ba284f0994cee89134`, with an approximately 2.02 GB
  safetensors representation and a 12.20 GB optimizer file. Availability of
  that optimizer file does not establish exact-resume compatibility.

### Inferred

- The final Pythia checkpoint is the smallest policy-cleared artifact for the
  first local load/logits test. Its 2.09 GB file may fit available system
  storage, but fit in 6 GB VRAM cannot be inferred before activation and
  framework overhead are measured.
- Conventional full-weight Adam-style continued pretraining of a one-billion-
  parameter model is unlikely to fit entirely in 6 GB VRAM. Offload, sharding,
  altered optimizer state, or another machine may be required, and each option
  needs a frozen scientific and resource decision.

### Unverified

- successful unquantized model loading on the RTX 2060;
- complete-continuation logits correctness and throughput;
- peak RAM and VRAM during model use;
- tiny full-weight or PEFT training throughput;
- checkpoint write time, exact resume, recovery, and projected experiment cost;
- sustained thermals and machine usability during representative work.

## Artifacts

Committed evidence and controls:

- `artifacts/manifests/MODEL_MANIFEST.json` — immutable identities, licenses,
  execution states, and fail-closed blockers;
- `scripts/audit_local_resources.py` — no-network machine and Torch/CUDA audit;
- `scripts/audit_hf_model.py` — metadata-only identity, license, and
  known-filename-marker binary classification with unknown binaries reported
  separately;
- `scripts/benchmark_model.py` — no-network planning plus guarded execution and
  structured failure evidence;
- `docs/LOCAL_BENCHMARK_PROTOCOL.md` — exact bounded operator sequence.

Ignored local evidence under `artifacts/local/` contains the live resource
snapshots, metadata responses, plan output, and deliberate failure artifact.
These files may contain machine-specific paths and dynamic state and are not
publication artifacts.

## Validation

The implementation passed:

```text
python -m compileall scripts src tests
python -m pytest tests/test_audit_scripts.py tests/test_hf_model_audit.py tests/test_model_manifest.py tests/test_artifact_policy.py -q
python scripts/audit_local_resources.py --repo . --path .
python scripts/benchmark_model.py --artifact pythia-1b-deduped-main
python scripts/benchmark_model.py --artifact pythia-1b-deduped-main --execute ...
```

The focused suite passed 35 tests. The default benchmark command returned a
no-network `planned` report. The deliberate execute command failed before
model access because its audit correctly described a dirty worktree, and it
preserved the failure as JSON.

The complete local suite passed 281 tests with one skipped optional test. Pilot,
model-manifest, and evaluation-registry validation also passed; the manifest
reported 13 artifacts, one benchmark-ready and 12 metadata-only or blocked.
The final exact-head remote results are recorded in the draft pull request
checks. No validation command used `--allow-download`.

## Risks

1. Free RAM and VRAM are transient; a prior clean audit does not guarantee
   headroom after unrelated desktop workloads change.
2. Metadata APIs establish repository state at the resolved commit, not model
   scientific suitability, loader compatibility, or faithful resume behavior.
3. Alternative weight formats can coexist in one Hub repository. Total binary
   bytes are not the same as the minimum inference download.
4. A first successful load would still prove only local engineering
   feasibility, not scorer reliability, calibration sensitivity, or CSTG.
5. DatedGPT, PIT, ChronoGPT, TypewriterLM, Kairos, and both OLMo paths retain
   explicit license, custom-code, identity, conversion, or hardware blockers.

## Next write-active deliverable

After explicit authorization for the 2.09 GB acquisition, create a fresh clean-
head resource audit for the exact cache filesystem and execute one immutable
final-Pythia load/logits benchmark with no training. Stop on hash or revision
mismatch, inadequate live disk, CUDA mismatch, swapping, OOM, or instability.
Record both success and failure as structured evidence before considering a
tiny continued-pretraining benchmark.
