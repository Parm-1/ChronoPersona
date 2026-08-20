# Transformers Tokenizer and Scoring Protocol

This protocol connects the dependency-light evaluation system to real Hugging Face tokenizers and causal language models without weakening the artifact gates.

It does not authorize evidence-bearing training or interpret development scores scientifically.

## 1. Safety model

Every operation begins from `artifacts/manifests/MODEL_MANIFEST.json`.

A tokenizer audit is permitted only when:

- the repository is a Hugging Face `owner/name` artifact;
- the revision is a pinned 40-character commit SHA;
- the artifact is marked immutable;
- the model license is verified;
- no custom remote code is required.

Model scoring additionally requires:

- `execution_status = "benchmark-ready"`;
- unquantized safetensors;
- the local memory and storage gates in `LOCAL_BENCHMARK_PROTOCOL.md`.

The scripts never set `trust_remote_code=True` and contain no quantization path.
Their execution modes are temporarily fail-closed: direct repository or cache
loading is disabled until the provider consumes a reusable local-snapshot
verifier that enforces the manifest file allowlist, sizes, hashes, config, and
revision. Plan mode remains available.

## 2. Install the smallest dependency set first

Tokenizer-only audit:

```powershell
python -m pip install -e ".[tokenizers]"
```

Full model scoring later:

```powershell
python -m pip install -e ".[models]"
```

Tokenizer audits therefore do not require PyTorch or model weights.

## 3. Plan before network access

Pythia final checkpoint tokenizer plan:

```powershell
python scripts/audit_registry_tokenizer.py `
  --artifact pythia-1b-deduped-main `
  --prefix-policy none `
  --max-length 2048 `
  --output artifacts/local/pythia-tokenizer-plan.json
```

OLMo early-training tokenizer plan:

```powershell
python scripts/audit_registry_tokenizer.py `
  --artifact olmo2-1b-early-step20000 `
  --prefix-policy none `
  --max-length 4096 `
  --output artifacts/local/olmo-tokenizer-plan.json
```

A plan performs no network access. It reports whether policy permits the operation and why a blocked artifact is blocked.

DatedGPT should currently report a license blocker. That is expected and must not be bypassed.

## 4. Tokenizer-only audit execution gate

Tokenizer execution is deliberately blocked at present. A populated Hugging
Face cache is not proof that the tokenizer files match the manifest, and
`--allow-download` is rejected with guidance to the separate acquisition
command. `benchmark_model.py --acquire-only` can create and verify the exact
Pythia snapshot, but the tokenizer provider must first be changed to consume
that verified local snapshot rather than an owner/name cache lookup.

When that reusable loader is implemented and tested, run both prefix policies
during development when a model has a BOS token. The chosen execution command,
snapshot/report binding, and result paths must be added here before use.

The chosen policy must be frozen before confirmatory scoring. Do not select it based on which policy produces the preferred temporal result. Selection is based on the model's native evaluation convention, development reliability, and explicit documentation.

## 5. Tokenizer audit output

The deterministic report records:

- registry SHA-256;
- artifact and immutable revision;
- tokenizer class, vocabulary, maximum length, and special-token IDs;
- explicit prefix policy and prefix token IDs;
- prompt and continuation token counts;
- continuation start and prediction positions;
- continuation token IDs;
- candidate token-count differences within every form;
- all boundary, truncation, and prompt-context failures;
- a canonical output hash.

The audit fails when:

- the prompt tokenization is not an exact prefix of prompt plus continuation;
- a complete sequence exceeds the frozen maximum length;
- candidate prompt contexts differ;
- a tokenizer cannot be loaded under the pinned no-remote-code path.

Do not repair a failed item by trimming or tokenizing candidates separately. Rewrite the item or create a reviewed tokenizer-specific adapter.

## 6. Model-score plan

Before loading weights:

```powershell
python scripts/score_registry_transformers.py `
  --artifact pythia-1b-deduped-main `
  --prefix-policy none `
  --device cuda `
  --dtype auto `
  --max-length 2048 `
  --output artifacts/local/pythia-score-plan.json
```

The plan performs no network access and does not import PyTorch.

## 7. First development score gate

Scoring execution remains blocked until all of these are true:

1. the local resource audit passes;
2. immutable Pythia acquisition and loading/logits benchmarks succeed;
3. the provider consumes the exact hash-verified local snapshot and rechecks it
   before loading;
4. tokenizer audit passes through the same verified-snapshot layer;
5. the cache has sufficient storage and the exact Git commit is recorded.

No scoring command may download or load directly by repository/revision. After
the shared loader exists, add an offline, explicit-float16 command here and
require deterministic repeated score artifacts with identical canonical
`output_sha256` values. Hardware/runtime metadata remains in the separate run
and compute ledgers.

## 8. Score semantics

For every complete continuation, the provider:

1. prepares the exact prompt/continuation token boundary;
2. runs one unquantized causal-LM forward pass;
3. computes log-softmax over logits in float32;
4. gathers the log probability assigned to every actual next token;
5. selects only the continuation prediction positions;
6. passes token IDs and token log probabilities into the dependency-light scorer.

Before aggregation, the scorer requires non-negative integer prompt and continuation token IDs, exact token/log-probability length agreement, and finite numeric log probabilities no greater than zero. Numeric strings, booleans, negative IDs, NaN/Inf, positive log probabilities, truncation, and inexact boundaries fail closed.

The scorer then computes:

- complete-continuation total log likelihood;
- mean-token log likelihood as a diagnostic;
- semantic-pole-normalized pairwise margin;
- normalized reference-pole probability;
- paraphrase agreement and dispersion;
- deterministic output identity.

Generated explanations are not used.

## 9. Development interpretation

The first Pythia final-checkpoint score is an engineering and measurement-development artifact. It can identify:

- exact-boundary failures;
- severe token-length imbalance;
- candidate-order implementation defects;
- paraphrase disagreement;
- item ceilings or floors;
- raw-versus-mean-score divergence.

It cannot establish:

- a temporal trajectory;
- CSTG;
- a historical prior;
- model representativeness;
- naturalistic calibration sensitivity.

The final Pythia checkpoint is not the causal insertion checkpoint.

## 10. Failure policy

Stop and preserve the error when:

- artifact policy blocks the operation;
- the resolved revision differs from the manifest;
- custom code is requested;
- safetensors are unavailable;
- tokenizer boundaries fail;
- CUDA is unavailable or repeatedly out of memory;
- system swapping or desktop instability occurs;
- model output lacks expected causal-LM logits;
- score artifacts are incomplete or non-deterministic.

Do not silently switch to:

- a mutable branch;
- another checkpoint;
- quantization;
- CPU offload;
- a different prefix policy;
- mean-token scoring;
- remote code;
- a truncated evaluation subset.

Any such change is a new documented development condition.

## 11. OLMo and DatedGPT next steps

### OLMo

The early-training Hub artifact passes the policy-level tokenizer gate because
its revision and Apache-2.0 license are pinned and it requires no remote code.
Actual tokenizer loading remains disabled until its exact required files are
manifested and supported by the shared verified-snapshot loader. It is not
model-score ready until the hardware benchmark passes.

The scientifically preferred original OLMo step-23,100 checkpoint still requires an immutable file-and-hash manifest and a reviewed conversion/loading path.

### DatedGPT

DatedGPT remains blocked from tokenizer and model execution until an explicit model-weight license is established and all selected annual revisions are pinned. Do not treat the paper's license or public Hub access as a weight license.

## 12. Commit policy

Files under `artifacts/local/` are ignored by Git. Commit only:

- aggregate non-sensitive measurements;
- exact artifact and revision identities;
- hashes;
- failure classifications;
- reviewed protocol or manifest changes.

Do not commit caches, weights, raw logs containing local paths or host identifiers, or large score artifacts without deliberate review.
