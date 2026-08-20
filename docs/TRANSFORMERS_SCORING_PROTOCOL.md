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
Tokenizer execution consumes only an explicit local snapshot after the shared
verifier enforces the canonical manifest, repository/revision cache layout,
complete file allowlist, sizes, hashes, config, and cache-contained targets.
Direct repository lookup and download-on-load remain disabled. Model scoring is
implemented only through the frozen exact-snapshot, accepted-tokenizer,
live-resource, exact-load, and deterministic-output gate below. Target
execution remains blocked until that implementation is committed, exact-head
CI passes, and a fresh resource audit satisfies every threshold. Plan mode
remains available for both operations.

## 2. Install the smallest dependency set first

Tokenizer-only audit:

```powershell
python -m pip install -e ".[tokenizers]"
```

Full model scoring later:

```powershell
python -m pip install -e ".[models]"
```

Tokenizer audits do not import PyTorch or deserialize model weights. The current
complete-snapshot integrity contract does require the already-acquired Pythia
snapshot and streams every manifested file, including safetensors, through
SHA-256 verification before and after tokenizer construction.

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

Execution requires a clean exact Git head, the canonical committed manifest and
development registry, explicit absolute cache/snapshot paths, and a new output
path outside the cache. `--allow-download` remains rejected.

Pythia's development audit freezes `prefix-policy=none` before any registry
logits are inspected. The canonical manifest pins zero native special tokens;
the provider must also prove that the exact backend produces identical probe
IDs with `add_special_tokens=True` and `False`. Run it twice from fresh
invocations:

```powershell
$cache = (Resolve-Path "artifacts/local/hf-cache").Path
$revision = "7199d8fc61a6d565cd1f3c62bf11525b563e13b2"
$snapshot = (Resolve-Path (Join-Path $cache "models--EleutherAI--pythia-1b-deduped/snapshots/$revision")).Path

python scripts/audit_registry_tokenizer.py `
  --artifact pythia-1b-deduped-main `
  --prefix-policy none `
  --max-length 2048 `
  --cache-dir $cache `
  --snapshot-path $snapshot `
  --execute `
  --output artifacts/local/pythia-tokenizer-none-a.json

python scripts/audit_registry_tokenizer.py `
  --artifact pythia-1b-deduped-main `
  --prefix-policy none `
  --max-length 2048 `
  --cache-dir $cache `
  --snapshot-path $snapshot `
  --execute `
  --output artifacts/local/pythia-tokenizer-none-b.json
```

Both reports must pass all 12 items, 24 forms, and 48 candidates, validate their
final self-hashes, contain no absolute local path, and have identical canonical
`output_sha256` values. A different prefix policy is a new documented
development condition; do not select one based on a preferred model score.

**Observed 2026-08-20 result:** exact clean head `c57ce40` ran both commands
from fresh invocations. Both reports were byte-identical, passed 12 items, 24
forms, and 48 candidates with zero failures, and shared canonical output
SHA-256
`6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523`.
The accepted prefix remains `none`; no model was loaded. See
`reports/stage0/pythia_tokenizer_boundary_gate_2026-08-20.md`.

## 5. Tokenizer audit output

The deterministic report records:

- registry SHA-256;
- artifact and immutable revision;
- tokenizer class, vocabulary, maximum length, and special-token IDs;
- canonical Git/manifest/registry and portable snapshot-receipt identities;
- a fast-backend semantic fingerprint and post-load snapshot re-verification;
- explicit prefix policy and prefix token IDs;
- prompt and continuation token counts;
- continuation start and prediction positions;
- continuation token IDs;
- candidate token-count differences within every form;
- all boundary, truncation, and prompt-context failures;
- a canonical output hash.

The report records the enforced offline variables, local-only/trust settings,
and absence of any download-capable provider path. Network traffic is labelled
`not-instrumented`, not falsely presented as independently observed. The report
also states that no files were downloaded and no model weights were
deserialized, and records how many safetensor bytes were rehashed for integrity.
Absolute cache and snapshot paths are intentionally excluded.

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
  --config configs/runs/pythia-development-score-v0.json `
  --artifact pythia-1b-deduped-main `
  --prefix-policy none `
  --device cuda:0 `
  --dtype float16 `
  --max-length 2048 `
  --output artifacts/local/pythia-score-plan.json
```

The plan performs no network access and does not import PyTorch.

## 7. First development score gate

Do not run this section until the implementation commit is clean, pushed, and
green in exact-head CI. Scoring then remains fail-closed unless all of these are
true:

1. the local resource audit passes;
2. immutable Pythia acquisition and loading/logits benchmarks succeed;
3. the model provider consumes the exact hash-verified local snapshot and
   rechecks it before loading;
4. the accepted exact Pythia tokenizer audit is bound by report hash through
   that snapshot layer;
5. the cache has sufficient storage and the exact Git commit is recorded.

No scoring command may download or load directly by repository/revision. The
only accepted target procedure is two fresh invocations with separate fresh
resource audits and a dependency-light offline verifier. Every named output is
create-only and must not already exist.

Use the existing hash-verified cache. In an isolated worktree without its own
cache, set `$cache` to the absolute existing cache directory; do not create a
junction or symlink. The commands below use a worktree-local cache only as the
portable example.

```powershell
$cache = (Resolve-Path "artifacts/local/hf-cache").Path
$revision = "7199d8fc61a6d565cd1f3c62bf11525b563e13b2"
$snapshot = (Resolve-Path (Join-Path $cache "models--EleutherAI--pythia-1b-deduped/snapshots/$revision")).Path
$tokenizerAudit = (Resolve-Path "artifacts/local/pythia-tokenizer-none-a-c57ce40.json").Path
$head = (git rev-parse --short=8 HEAD).Trim()
$auditA = "artifacts/local/pythia-score-resource-a-$head.json"
$scoreA = "artifacts/local/pythia-score-a-$head.json"
$receiptA = "artifacts/local/pythia-score-runtime-a-$head.json"
$auditB = "artifacts/local/pythia-score-resource-b-$head.json"
$scoreB = "artifacts/local/pythia-score-b-$head.json"
$receiptB = "artifacts/local/pythia-score-runtime-b-$head.json"
$comparison = "artifacts/local/pythia-score-comparison-$head.json"

python scripts/audit_local_resources.py `
  --path $cache `
  --repo (Get-Location) `
  --output $auditA

python scripts/score_registry_transformers.py `
  --config configs/runs/pythia-development-score-v0.json `
  --artifact pythia-1b-deduped-main `
  --prefix-policy none `
  --max-length 2048 `
  --device cuda:0 `
  --dtype float16 `
  --cache-dir $cache `
  --snapshot-path $snapshot `
  --resource-audit $auditA `
  --tokenizer-audit $tokenizerAudit `
  --attempt a `
  --allow-low-ram `
  --execute `
  --output $scoreA `
  --runtime-output $receiptA

python scripts/audit_local_resources.py `
  --path $cache `
  --repo (Get-Location) `
  --output $auditB

python scripts/score_registry_transformers.py `
  --config configs/runs/pythia-development-score-v0.json `
  --artifact pythia-1b-deduped-main `
  --prefix-policy none `
  --max-length 2048 `
  --device cuda:0 `
  --dtype float16 `
  --cache-dir $cache `
  --snapshot-path $snapshot `
  --resource-audit $auditB `
  --tokenizer-audit $tokenizerAudit `
  --attempt b `
  --allow-low-ram `
  --execute `
  --output $scoreB `
  --runtime-output $receiptB

python scripts/verify_registry_scores.py `
  --config configs/runs/pythia-development-score-v0.json `
  --score-a $scoreA `
  --receipt-a $receiptA `
  --resource-audit-a $auditA `
  --score-b $scoreB `
  --receipt-b $receiptB `
  --resource-audit-b $auditB `
  --output $comparison
```

Attempt A must fully release its lock, CUDA state, and private staging before
audit B is captured. The verifier requires distinct process IDs, distinct raw
resource audits, ordered timestamps, exact clean-head identity, complete
resource/runtime receipts, and byte-identical score artifacts. Hardware and
runtime measurements remain outside the deterministic score identity. A
pre-import resource failure is pending and may be retried only after resources
naturally return and a new audit is captured; any failure after deserialization
starts consumes the sole attempt and stops this gate.

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
