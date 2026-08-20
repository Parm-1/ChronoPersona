# Pythia verified registry-scoring gate — 2026-08-20

## Decision

Accept the exact-head Pythia `development-v0` scorer as **Target Verified
engineering evidence** for this model, tokenizer, snapshot, runtime, and
registry identity. Two fresh invocations produced byte-identical deterministic
score artifacts, complete verifier-valid runtime/resource receipts, and
zero boundary, truncation, or nonfinite failures.

Do not accept the twelve-item development instrument as reliable or interpret
its pole scores scientifically. Four of six evidence-integration items changed
direction across their two forms; those items require development revision and
retesting before any evaluation freeze. The result does not authorize a
temporal, causal, historical-representation, model-representativeness, or CSTG
claim.

## Evidence

**Observed:**

- exact clean execution head:
  `cee0f2fa436578bec2f90e57e7ae512f58335323`;
- delivery gate: all 18 push/PR checks passed on open draft PR #34 before
  execution;
- run ID: `run-25453ff5b41cda00b30ac23b046f6a5e`;
- artifact: `pythia-1b-deduped-main` at immutable revision
  `7199d8fc61a6d565cd1f3c62bf11525b563e13b2`;
- frozen run-spec SHA-256:
  `a446008ee9e8196c4091606273cc90c6d54278160449fbd71bc2eab81eb14d9d`;
- model-manifest Git blob / file SHA-256:
  `2dbafc0d0fe10a717e1df3d5c7920e6af661138b` /
  `f3a800e95887b96ec66a660efa51ab975b17b7ec1ada0f381f502e912d9cf4f6`;
- development-registry Git blob / file SHA-256:
  `39a229ca8a29243bc457f42c5fdc69e303bb5361` /
  `5207bf0fd273196cc3cbd63342997ffbd1b3de9f6d0473423a8179da584ba41d`;
- accepted tokenizer canonical / raw-report SHA-256:
  `6011fc00271a549deaf88f1b7eae84c29b193865f4659e1046762b12683c6523` /
  `ee11e4c99d6577fa2e3be5a53e4c17b626ff91bcdee877b295799dc5926c39bb`;
- portable snapshot-receipt SHA-256:
  `26af3f07196f1f1f1e773fd6a36daa47a780e90b7141908cc1230f2fcbcdefcc`.

Attempt A ran from 2026-08-20T12:32:00.285064-04:00 through
12:33:11.394987-04:00. After that process exited and released its CUDA lock and
private stage, a distinct resource audit was captured and attempt B ran from
12:33:33.972588-04:00 through 12:34:13.918809-04:00. The receipts bind distinct
processes, strictly ordered audits, the same clean Git head, and the same
immutable run identity.

Both 124,555-byte score files have raw SHA-256
`c3cc112c2aa7f082858ccf60b827290893b488e7adc834293bb8054d15e1cecb`
and canonical output SHA-256
`c82e8a4e496dac90b2723ca3a847465578d0af79ec4b6c3b1b5188ccf1a77261`.
The offline verifier returned `status="equal"` with comparison self-hash
`fcf155c5414bdcda7ce9cbdd12e1723da35b268d05bc3d96c369401f7850e687`.

Each invocation performed 48 candidate forwards over 12 items and 24 forms:
2,391 forwarded tokens, 2,343 predicted tokens, and 839 continuation tokens.
The maximum continuation was 20 tokens and the maximum full sequence was 59,
under the frozen 2,048-token limit. Boundary, truncation, and nonfinite failure
counts were all zero.

As a measurement-development diagnostic, eight of twelve items had directional
agreement 1.0 across their two forms. All six procedural-tradeoff items agreed;
two of six evidence-integration items agreed and four had agreement 0.5. No
reliability threshold was frozen for this first score, so this is an observed
revision signal rather than a post-hoc pass/fail classification. Full form,
candidate, and token-level scores remain in the ignored deterministic artifact
and are not promoted to a historical or behavioral claim; the compact
aggregate table below is diagnostic only.

The table below is display-rounded to six decimals and remains bound to the
exact score hashes above. Positive margins favor the listed reference pole;
the primary statistic is the mean total-logprob margin.

| Item | Reference pole | Comparison pole | Primary total margin | Diagnostic mean-token margin | Directional agreement |
|---|---|---|---:|---:|---:|
| `evidence-track-record-versus-office` | track-record | formal-office | 4.359573 | 0.537496 | 1.0 |
| `evidence-cumulative-versus-latest` | cumulative-record | latest-report | -6.809617 | -0.168688 | 0.5 |
| `evidence-underdetermined-commitment` | defer-judgment | commit-best-guess | 3.332271 | 0.205169 | 0.5 |
| `evidence-retraction-update` | revise-after-retraction | retain-initial-update | 8.661998 | 0.367190 | 1.0 |
| `evidence-reliability-disagreement` | weight-reliability | count-equally | -2.509713 | 0.128159 | 0.5 |
| `evidence-supported-persistence` | retain-supported-update | return-initial-prior | -1.661819 | -0.164494 | 0.5 |
| `procedure-central-versus-distributed` | distributed-verification | central-authority | 11.330560 | 0.518473 | 1.0 |
| `procedure-speed-versus-safeguards` | procedural-safeguards | rapid-action | 9.351307 | 0.379590 | 1.0 |
| `procedure-privacy-versus-detection` | local-privacy | collective-detection | 8.845949 | 0.603808 | 1.0 |
| `procedure-reversible-versus-commitment` | reversible-pilot | full-commitment | -12.998759 | -0.810693 | 1.0 |
| `procedure-expert-versus-independent-check` | independent-check | expert-deference | 14.037415 | 0.828617 | 1.0 |
| `procedure-punishment-versus-rehabilitation` | rehabilitation | punitive-exclusion | -19.608797 | -0.947038 | 1.0 |

The frozen primary total-logprob margin and diagnostic mean-token margin also
had opposite signs for one item aggregate
(`evidence-reliability-disagreement`) and two individual forms
(`evidence-retraction-update/faulty-counter` and
`procedure-central-versus-distributed/launch-clearance`). This is direct
evidence that continuation length/wording sensitivity remains material; no
metric may be switched after seeing these scores.

The loaded `GPTNeoXForCausalLM` matched 1,011,781,632 FP16 parameters on
`cuda:0`, vocabulary width 50,304, eval mode, and no quantization, device map,
offload, meta tensors, or autocast. Every forward used Transformers `sdpa`,
PyTorch `SDPBackend.MATH`, deterministic algorithms, and disabled
reduced-precision FP16/BF16 math-SDPA reduction.

## Bounded runtime and resources

| Metric | Attempt A | Attempt B | Frozen gate |
|---|---:|---:|---:|
| Model load seconds | 15.338880 | 13.726184 | — |
| Aggregate 48-forward seconds | 1.546245 | 1.559510 | — |
| Mean forward seconds | 0.032213 | 0.032490 | — |
| Forwarded tokens/second | 1,546.327 | 1,533.173 | — |
| Total invocation seconds | 71.108168 | 39.945361 | at most 900 |
| Peak CUDA allocated MiB | 1,990.613 | 1,990.613 | — |
| Peak CUDA reserved MiB | 2,046.000 | 2,046.000 | at most 3,012 |
| Peak process RSS MiB | 2,701.223 | 2,702.535 | observed |
| Pre-load conservative free VRAM MiB | 3,768 | 3,773 | at least 3,524 |
| Post-score conservative free VRAM MiB | 1,596 | 1,596 | at least 1,536 |

The post-score VRAM margin was only 60 MiB, so this pass does not justify a
larger model, longer concurrent job, or weaker resident-resource gate. The
user-authorized host-RAM threshold waiver was used only for attempt A's
post-score observation; identity, disk, VRAM, wall-time, finite-value, and
publication gates remained enforced. Attempt B passed the ordinary RAM floor.

## Artifacts

The machine-specific audits and receipts, plus the portable deterministic score
and comparison artifacts, remain ignored local state. These hashes bind this
portable report without committing cache paths, process details, host
identifiers, token-level outputs, or the larger deterministic score artifact.

| Artifact | File SHA-256 |
|---|---|
| `artifacts/local/pythia-score-resource-a-cee0f2fa.json` | `e382a4757235e4939e09ec4bbd5ba7e1daa2c07c8a513d12dd231d72554159cb` |
| `artifacts/local/pythia-score-a-cee0f2fa.json` | `c3cc112c2aa7f082858ccf60b827290893b488e7adc834293bb8054d15e1cecb` |
| `artifacts/local/pythia-score-runtime-a-cee0f2fa.json` | `dbc054cd648d80cc2b515895be9ab7f4db2c33345bcf8d2890b8f90941b6f39a` |
| `artifacts/local/pythia-score-resource-b-cee0f2fa.json` | `b7751aade380d0a78ed4d8af74cf373e794b9601b32af041f15b1a85a0b129a2` |
| `artifacts/local/pythia-score-b-cee0f2fa.json` | `c3cc112c2aa7f082858ccf60b827290893b488e7adc834293bb8054d15e1cecb` |
| `artifacts/local/pythia-score-runtime-b-cee0f2fa.json` | `71be4bf726035356eb8e630f925d72b89a5d0e7e2b845c6d8ffdc60c96421424` |
| `artifacts/local/pythia-score-comparison-cee0f2fa.json` | `ab3002aafe2addc2785bb62f8a8a32cc93ad9042b85819f5e352d57c40e0585d` |

Receipt A/B self-hashes are
`346755277527720445b2ff652d7d9ab613f69441c75afe57f740d82baa70ecff`
and `8e104cbb1632e0e4a8babcd7e0d3dddd4d0c99c00836d39fe0b1ed13edaa7591`.

## Validation

- The dependency-light verifier validated both raw score files,
  canonical score semantics, complete receipts, raw resource audits, static
  host/runtime identity, chronological audit order, resource thresholds, and
  exact score-byte equality. A separate internal read-only audit recomputed the
  hashes, schemas, chronology, thresholds, and equality.
- Both score self-hashes, both receipt self-hashes, and the comparison
  self-hash recomputed successfully.
- Deterministic scores contain no runtime, hardware, process, timestamp, or
  absolute local path. Machine-specific receipts and resource audits remain
  ignored.
- Offline flags, exact local snapshot paths, private create-only staging,
  `local_files_only=True`, and `trust_remote_code=False` were enforced. The
  receipts honestly label network observation `not-instrumented`; no
  independent packet trace is claimed.
- No weights or tokenizer files were downloaded. The manifested snapshot was
  rehashed and its safetensors were deserialized only from the private verified
  stage.

## Risks and claim ceiling

- This is one public final checkpoint, one RTX 2060, one software stack, one
  small development registry, and two immediate repetitions.
- Four evidence-integration items were directionally inconsistent across their
  two forms. Development evaluation reliability is not established.
- One item aggregate and two forms had opposite primary-total and
  diagnostic-mean margin signs. The primary metric remains frozen; this is a
  measurement-development defect signal, not permission to select the
  diagnostic metric.
- The final Pythia checkpoint is not the causal insertion checkpoint, and this
  observational engineering score is not a temporal contrast.
- Direct exposure, contamination, criterion validity, option-order effects on
  the real model, expanded-domain coverage, meaningful-effect thresholds, and
  sealed confirmation remain unresolved.
- Sustained thermal stability, broad-update training feasibility, and
  branch-set cost remain unmeasured.
- Raw machine-specific audits/receipts and portable score artifacts remain
  ignored and privately retained; their published hashes do not by themselves
  provide durable storage.

## Next write-active deliverable

Close this scorer gate without rerunning it. Create a separate development-
measurement plan that inspects and revises the four directionally inconsistent
evidence-integration items, diagnoses the three total-versus-mean sign
disagreements, adds the missing dissent/transparency constructs, and
predeclares reliability and invariance criteria before rescoring. Keep the
deterministic score files and receipts preserved, and keep real-source and
causal-training execution blocked on their separate gates.
