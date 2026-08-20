# Local Benchmark Protocol

This protocol captures the resource evidence that cannot be measured from GitHub or a browser session. It is designed for the reported Windows machine with an RTX 2060 and 16 GB RAM, but it records actual values rather than assuming the GPU variant or available storage.

No command below starts a scientific or naturalistic training branch. Section
11 runs one deliberately tiny synthetic-fixture LoRA engineering smoke after
the loading gate has passed.

## 1. Obtain the branch

Use the exact branch head containing the model-audit implementation after that
head passes the required checks. During the active stacked-PR workflow this is
`fix/model-feasibility-gates`; do not switch to `main` until the relevant PRs
have been merged by an authorized maintainer.

```powershell
git switch fix/model-feasibility-gates
git pull --ff-only
```

Use a clean checkout. The output records the current commit and whether the working tree is dirty.

## 2. Create the lightweight environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Validate repository state:

```powershell
python -m chronopersona validate configs/pilot.toml
python -m chronopersona validate-models artifacts/manifests/MODEL_MANIFEST.json
pytest
```

## 3. Capture the machine before installing model dependencies

```powershell
python scripts/audit_local_resources.py `
  --repo . `
  --path . `
  --output artifacts/local/resource-audit-before-models.json
```

This command performs no network access. Inspect at least:

- exact RTX 2060 name and VRAM;
- NVIDIA driver;
- total and free RAM;
- free disk at the intended cache path;
- Python version;
- Git commit and dirty state.

Do not begin a download if the expected artifact plus a 2.5× safety margin does not fit the measured free space.

## 4. Install optional model-audit dependencies

```powershell
python -m pip install -e ".[models]"
python -m pip install --force-reinstall "torch==2.13.0" `
  --index-url https://download.pytorch.org/whl/cu130
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

The default PyPI Windows wheel can be CPU-only even on a CUDA-capable machine.
The explicit official PyTorch CUDA index is therefore part of the measured
Windows environment. Stop if the verification prints a `+cpu` build, no
compiled CUDA version, or `False` for CUDA availability.

Choose and create the explicit cache directory before the post-install audit so
the measured disk belongs to the filesystem that will receive any later model
download:

```powershell
$cache = New-Item -ItemType Directory -Force artifacts\local\hf-cache
$env:HF_HOME = $cache.FullName
```

Capture the environment again:

```powershell
python scripts/audit_local_resources.py `
  --repo . `
  --path $env:HF_HOME `
  --output artifacts/local/resource-audit-after-models.json
```

Inspect the structured `torch_runtime` record in addition to `nvidia-smi`.
Driver visibility alone does not prove that the installed Torch build can use
CUDA.

## 5. Resolve Hub metadata without downloading weights

The command below accesses the Hugging Face metadata API but does not download model weights:

```powershell
python scripts/audit_hf_model.py `
  EleutherAI/pythia-1b-deduped `
  EleutherAI/pythia-1b-deduped@step20000 `
  allenai/OLMo-2-0425-1B-early-training@stage1-step20000-tokens42B `
  datedgpt/datedgpt-2013-base `
  datedgpt/datedgpt-2016-base `
  datedgpt/datedgpt-2019-base `
  datedgpt/datedgpt-2022-base `
  datedgpt/datedgpt-2024-base `
  --output artifacts/local/hub-model-audit.json
```

The resulting JSON should provide:

- resolved immutable commit SHA;
- card license field;
- model library and tags;
- every file name, size, blob identity, and LFS SHA-256 when available;
- total repository and weight bytes;
- failures.

Do not manually copy mutable branch names into a frozen run. Update the committed model manifest with the resolved SHAs through a reviewed PR.

## 6. Produce a no-download benchmark plan

```powershell
python scripts/benchmark_model.py `
  --artifact pythia-1b-deduped-main `
  --output artifacts/local/pythia-main-plan.json
```

The plan performs no network access. It reports the pinned model, the five
required files and SHA-256 identities, their exact 2,092,816,302-byte total,
constraints, and the 5,232,040,755-byte minimum disk margin.

Blocked artifacts should refuse execution. This is expected:

```powershell
python scripts/benchmark_model.py `
  --artifact datedgpt-2013-base `
  --execute
```

## 7. Acquire, verify, and load the first approved local model

The first executable artifact is the immutable final Pythia 1B deduped checkpoint. It is used to measure the machine, not as the causal insertion point.

The explicit cache directory and a resource audit captured no more than 15
minutes earlier are required. Acquisition and model loading are separate
operations. The benchmark rejects a dirty or different Git head, a cache on a
different filesystem, or less than the 2.5x live and audited disk margin.

First capture a fresh pre-acquisition audit against the exact cache:

```powershell
python scripts/audit_local_resources.py `
  --repo . `
  --path $env:HF_HOME `
  --output artifacts/local/resource-audit-authorized-pre-download.json
```

Acquire only the five manifest-allowlisted files at the immutable revision:

```powershell
python scripts/benchmark_model.py `
  --artifact pythia-1b-deduped-main `
  --acquire-only `
  --allow-download `
  --cache-dir $env:HF_HOME `
  --resource-audit artifacts/local/resource-audit-authorized-pre-download.json `
  --output artifacts/local/pythia-main-acquisition.json
```

Do not load the model unless the acquisition report is complete and verifies:

- snapshot leaf equals revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`;
- the snapshot is contained by the selected cache;
- its file set exactly equals the five required manifest files;
- every size and SHA-256 matches the manifest;
- config type is `gpt_neox`, architecture is `GPTNeoXForCausalLM`, dtype is
  `float16`, and no `auto_map` exists.

After acquisition, capture another fresh audit. This binds dynamic physical RAM,
the conservative lower of Torch and `nvidia-smi` free VRAM, the software stack,
GPU identity, clean Git head, and cache filesystem immediately before loading:

```powershell
python scripts/audit_local_resources.py `
  --repo . `
  --path $env:HF_HOME `
  --output artifacts/local/resource-audit-authorized-post-download.json
```

Then execute offline, without download permission and with explicit float16:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

python scripts/benchmark_model.py `
  --artifact pythia-1b-deduped-main `
  --execute `
  --allow-low-ram `
  --device cuda `
  --dtype float16 `
  --cache-dir $env:HF_HOME `
  --resource-audit artifacts/local/resource-audit-authorized-post-download.json `
  --max-tokens 128 `
  --warmup 1 `
  --repeats 3 `
  --output artifacts/local/pythia-main-cuda-authorized.json
```

Execution rehashes the full allowlist, captures a live audit before importing
the model stack, verifies the actual parent Torch/Transformers/CUDA/device
identity, and captures another live audit after those imports and immediately
before loading. Both complete child audits and their hashes are embedded in the
result. By default the run fails if available physical RAM is below twice the
weight bytes. The explicit `--allow-low-ram` option records that threshold and
whether it passed but waives only that hard stop under the user's 2026-08-20
authorization. Conservative free VRAM must still remain at least 1.5 times the
weight bytes, and all runtime, disk, and integrity gates remain enforced.

For a subsequent run, capture a new resource audit and continue to omit
`--allow-download`:

```powershell
python scripts/benchmark_model.py `
  --artifact pythia-1b-deduped-main `
  --execute `
  --allow-low-ram `
  --device cuda `
  --dtype float16 `
  --cache-dir $env:HF_HOME `
  --resource-audit artifacts/local/resource-audit-authorized-repeat.json `
  --max-tokens 128 `
  --warmup 1 `
  --repeats 5 `
  --output artifacts/local/pythia-main-cuda-repeat.json
```

Record:

- load time;
- actual parameter count and model dtype;
- peak allocated and reserved VRAM;
- process peak RAM;
- tokens per second;
- mean next-token cross-entropy;
- exact model revision and software versions.

If CUDA loading fails, preserve the complete error. Do not immediately switch
to CPU, quantization, offload, another dtype, or another revision. A CPU
diagnostic would be a separately planned condition and is not a
training-throughput estimate.

## 8. Failure rules

Stop the benchmark sequence when any of these occurs:

- free disk falls below the safety margin;
- the resource audit is stale or runtime/GPU identity drifts;
- physical RAM falls below the declared load margin unless the run explicitly
  records `--allow-low-ram`; conservative free VRAM always remains enforced;
- the model revision differs from the manifest;
- a required file hash, exact allowlist, or model config identity differs;
- the model requests custom remote code;
- the model license is unverified;
- the process encounters an allocation failure or causes severe desktop
  instability; low-RAM runs may page and must record observed peak process RAM;
- the GPU repeatedly runs out of memory;
- thermal or driver instability appears;
- output metadata is incomplete.

Preserve errors rather than changing dtype, quantization, model, or revision
silently. Output paths are exclusive and an existing evidence file is never
overwritten. When `--output` is supplied, acquisition and execution each write
a distinct structured success or failure artifact before returning. A
download-permitted acquisition failure marks completion as unknown rather than
claiming that no partial cache was created. An execution failure records the
verified artifact and the supplied, pre-import live, and post-import live
resource-audit bindings when they were reached.

## 9. Update the compute ledger

Add one row per completed or failed model benchmark to `COMPUTE_LEDGER.csv`.
Keep the acquisition report as separate artifact-integrity evidence; do not
mislabel an acquisition failure as a CUDA benchmark. Do not overwrite a
previous measurement. Link the JSON artifact path and preserve the exact Git
commit.

## 10. What remains after the loading benchmark

A successful inference benchmark proves only that the verified model
loading/logits path can run. Registry scoring remains unverified until the
provider uses the same verified-snapshot layer, tokenizer audit passes, and an
explicit registry execution completes. Issue #2 still requires a tiny
continued-pretraining benchmark measuring:

- forward and backward memory;
- optimizer-state memory;
- activation checkpointing;
- tokens per second;
- checkpoint write size and time;
- safe interruption and resumption;
- full-weight versus PEFT modes.

That training benchmark should be implemented only after the model-loading result identifies the actual local envelope. It must use a tiny redistributable fixture and cannot be interpreted scientifically.

## 11. Run the frozen tiny LoRA checkpoint/resume gate

The committed training configuration is
`configs/runs/pythia-lora-smoke-v0.json`. It is limited to five batch-one,
sequence-128 optimizer updates over the two eligible CC0 synthetic fixture
records. It uses rank-4 FP32 LoRA adapters over the frozen FP16 base, targets
the 16 fused GPT-NeoX `query_key_value` projections, and has exactly 524,288
trainable parameters. AdamW and dynamic-loss-scaler defaults are expanded into
explicit frozen fields in the config rather than inherited from library
defaults. This is trainer/checkpoint evidence only.

First inspect the no-network plan:

```powershell
python scripts/benchmark_lora_training.py plan `
  --output artifacts/local/pythia-lora-plan.json
```

The runner deliberately has no download option. Use the already verified
snapshot and construct its explicit path:

```powershell
$snapshot = Join-Path $env:HF_HOME `
  "models--EleutherAI--pythia-1b-deduped\snapshots\7199d8fc61a6d565cd1f3c62bf11525b563e13b2"
```

Real execution requires the canonical `runs/pythia-lora-smoke-v0` output root
and also holds one fixed host-temporary training lock, independent of run ID or
condition. A stale lock is never removed automatically; inspect it before any
manual recovery. This keeps control and resumed invocations, alternate run
identities, and separate worktrees from loading concurrent heavy jobs.

Commit and validate the complete training implementation first. Then capture a
fresh audit and repeat Section 7's offline loading/logits command at that exact
clean training head. The resulting successful inference report is an immutable
input to the training run identity; do not reuse the older `76c2479` report.

Capture a fresh cache-bound audit immediately before the uninterrupted
operational reference, then run it:

```powershell
python scripts/audit_local_resources.py `
  --repo . `
  --path $env:HF_HOME `
  --output artifacts/local/resource-audit-lora-control.json

python scripts/benchmark_lora_training.py run `
  --condition control `
  --cache-dir $env:HF_HOME `
  --snapshot-path $snapshot `
  --resource-audit artifacts/local/resource-audit-lora-control.json `
  --load-report artifacts/local/pythia-main-cuda-training-head.json `
  --output-root runs/pythia-lora-smoke-v0 `
  --output artifacts/local/pythia-lora-control.json
```

Capture another fresh audit and execute the declared step-three interruption.
Exit code 75 is expected only after the immutable checkpoint, runtime-step
artifact, progress event, attempt report, and `failed` event have been written:

```powershell
python scripts/audit_local_resources.py `
  --repo . `
  --path $env:HF_HOME `
  --output artifacts/local/resource-audit-lora-interrupt.json

python scripts/benchmark_lora_training.py run `
  --condition resumed `
  --interrupt-after 3 `
  --cache-dir $env:HF_HOME `
  --snapshot-path $snapshot `
  --resource-audit artifacts/local/resource-audit-lora-interrupt.json `
  --load-report artifacts/local/pythia-main-cuda-training-head.json `
  --output-root runs/pythia-lora-smoke-v0 `
  --output artifacts/local/pythia-lora-interrupted.json
```

Capture one more fresh audit, then authorize the explicit resume. The runner
rehashes the snapshot before model import, verifies the checkpoint bytes before
`torch.load(weights_only=True)`, checks its step-three event binding, restores
adapter/optimizer/scheduler/scaler state, and restores CPU/CUDA RNG last:

```powershell
python scripts/audit_local_resources.py `
  --repo . `
  --path $env:HF_HOME `
  --output artifacts/local/resource-audit-lora-resume.json

python scripts/benchmark_lora_training.py run `
  --condition resumed `
  --resume `
  --cache-dir $env:HF_HOME `
  --snapshot-path $snapshot `
  --resource-audit artifacts/local/resource-audit-lora-resume.json `
  --load-report artifacts/local/pythia-main-cuda-training-head.json `
  --output-root runs/pythia-lora-smoke-v0 `
  --output artifacts/local/pythia-lora-resumed.json
```

Finally verify each condition and require exact semantic equality:

```powershell
$runId = (Get-Content artifacts/local/pythia-lora-control.json -Raw |
  ConvertFrom-Json).run_id
$control = Join-Path "runs/pythia-lora-smoke-v0/control" $runId
$resumed = Join-Path "runs/pythia-lora-smoke-v0/resumed" $runId

python scripts/benchmark_lora_training.py verify --run-root $control
python scripts/benchmark_lora_training.py verify --run-root $resumed
python scripts/benchmark_lora_training.py compare `
  --control-root $control `
  --resumed-root $resumed `
  --output artifacts/local/pythia-lora-comparison.json
```

The frozen resource gates require at least 3,695,181,824 bytes conservative
free VRAM before each load, at least 1,610,612,736 bytes global free VRAM after
load, no more than 3,158,310,912 process-reserved GPU bytes, 128 MiB output
headroom, a checkpoint no larger than 16 MiB, and at most 15 minutes per
condition cumulatively; the interrupted and resumed attempts share that
15-minute budget. Each attempt records elapsed wall time. Available host RAM is
recorded but is not a threshold under the user's instruction. Per-step evidence
separates forward, backward, and optimizer CUDA allocation/reservation peaks,
optimizer-state tensor bytes, and input-token throughput. Allocation failure,
severe paging or desktop instability, driver/thermal instability, a nonfinite
value, a skipped optimizer update, or any integrity mismatch still stops the
gate.

The full-weight AdamW path is not attempted. Even the optimistic FP16
weights/gradients/two-FP16-moment lower bound is 8,094,253,056 bytes, exceeding
the 6,441,992,192-byte GPU by 1,652,260,864 bytes before activations.

## 12. Borrowed RTX 5070 machine

Do not plan around the borrowed machine until access is confirmed. When available, repeat the same resource and immutable Pythia benchmark protocol there before using OLMo or running training. Record it under a separate machine label; never merge measurements from the two computers.

## 13. Paid compute

No command in this protocol authorizes paid compute. A later paid-compute proposal must use measured local throughput and state the exact model, branches, dose, storage, failure allowance, CAD cost, scientific decision, and stop rule.
