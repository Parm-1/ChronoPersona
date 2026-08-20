# Local Benchmark Protocol

This protocol captures the resource evidence that cannot be measured from GitHub or a browser session. It is designed for the reported Windows machine with an RTX 2060 and 16 GB RAM, but it records actual values rather than assuming the GPU variant or available storage.

No command below starts evidence-bearing training.

## 1. Obtain the branch

After the model-audit PR is merged:

```powershell
git switch main
git pull
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
$env:HF_HOME = "C:\hf-cache"
New-Item -ItemType Directory -Force $env:HF_HOME
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

The plan performs no network access. It reports the pinned model, weight size, constraints, and minimum disk margin.

Blocked artifacts should refuse execution. This is expected:

```powershell
python scripts/benchmark_model.py `
  --artifact datedgpt-2013-base `
  --execute
```

## 7. Run the first approved local loading benchmark

The first executable artifact is the immutable final Pythia 1B deduped checkpoint. It is used to measure the machine, not as the causal insertion point.

The explicit cache directory and post-model resource audit from section 4 are
required. The benchmark rejects a dirty or different Git head, a CPU-only
Torch audit for a CUDA run, a cache on a different filesystem, or less than the
2.5x live and audited disk margin.

First run, permitting the pinned download:

```powershell
python scripts/benchmark_model.py `
  --artifact pythia-1b-deduped-main `
  --execute `
  --allow-download `
  --device cuda `
  --dtype auto `
  --cache-dir $env:HF_HOME `
  --resource-audit artifacts/local/resource-audit-after-models.json `
  --max-tokens 128 `
  --warmup 1 `
  --repeats 3 `
  --output artifacts/local/pythia-main-cuda.json
```

Subsequent runs should omit `--allow-download` and use the local cache:

```powershell
python scripts/benchmark_model.py `
  --artifact pythia-1b-deduped-main `
  --execute `
  --device cuda `
  --dtype auto `
  --cache-dir $env:HF_HOME `
  --resource-audit artifacts/local/resource-audit-after-models.json `
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

If CUDA loading fails, preserve the complete error. Do not immediately switch to quantization. A CPU run may diagnose file integrity and software compatibility:

```powershell
python scripts/benchmark_model.py `
  --artifact pythia-1b-deduped-main `
  --execute `
  --device cpu `
  --dtype float32 `
  --cache-dir $env:HF_HOME `
  --resource-audit artifacts/local/resource-audit-after-models.json `
  --max-tokens 64 `
  --warmup 0 `
  --repeats 1 `
  --output artifacts/local/pythia-main-cpu.json
```

A CPU result is not a training-throughput estimate.

## 8. Failure rules

Stop the benchmark sequence when any of these occurs:

- free disk falls below the safety margin;
- the model revision differs from the manifest;
- the model requests custom remote code;
- the model license is unverified;
- the process causes system swapping or severe desktop instability;
- the GPU repeatedly runs out of memory;
- thermal or driver instability appears;
- output metadata is incomplete.

Preserve errors rather than changing dtype, quantization, model, or revision
silently. When `--output` is supplied, the benchmark writes a structured
failure artifact before returning nonzero; a download-permitted failure marks
download completion as unknown rather than claiming that no partial cache was
created.

## 9. Update the compute ledger

Add one row per completed or failed benchmark to `COMPUTE_LEDGER.csv`. Do not overwrite a previous measurement. Link the JSON artifact path and preserve the exact Git commit.

## 10. What remains after the loading benchmark

A successful inference benchmark proves only that the model and scorer can run. Issue #2 still requires a tiny continued-pretraining benchmark measuring:

- forward and backward memory;
- optimizer-state memory;
- activation checkpointing;
- tokens per second;
- checkpoint write size and time;
- safe interruption and resumption;
- full-weight versus PEFT modes.

That training benchmark should be implemented only after the model-loading result identifies the actual local envelope. It must use a tiny redistributable fixture and cannot be interpreted scientifically.

## 11. Borrowed RTX 5070 machine

Do not plan around the borrowed machine until access is confirmed. When available, repeat the same resource and immutable Pythia benchmark protocol there before using OLMo or running training. Record it under a separate machine label; never merge measurements from the two computers.

## 12. Paid compute

No command in this protocol authorizes paid compute. A later paid-compute proposal must use measured local throughput and state the exact model, branches, dose, storage, failure allowance, CAD cost, scientific decision, and stop rule.
