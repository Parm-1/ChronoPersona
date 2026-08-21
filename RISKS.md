# Risks — Design v1.0

| ID | Risk | Severity | Mitigation / stop rule |
|---|---|---:|---|
| R-01 | Prior work already performs equivalent prospective naturalistic A/B→C transport | Critical | Maintain primary-source novelty registry; reframe or stop if equivalent work exists |
| R-02 | Source culture or composition masquerades as period | Critical | Independent A/B, sealed C, ecological and prespecified adjusted analyses, heterogeneity reporting |
| R-03 | A/B agreement overfits discovery choices | Critical | Predesignate C, freeze estimator/direction/thresholds/evaluation, no C tuning |
| R-04 | C is replaced after failure | Critical | Machine-readable role seal and explicit no-substitution rule; C failure rejects CSTG |
| R-05 | Measurement captures prompt, option, label, tokenizer, or capability artifacts | High | Factorial items, reversals, paraphrases, token diagnostics, capability/factual/register controls; block training until reliable |
| R-06 | Pipeline cannot detect a real latent factor | High | Mandatory synthetic identifiability; one predefined rescue; nulls inconclusive after failed calibration |
| R-07 | Timestamp or historical-version semantics are invalid | Critical | Native timestamps, version recovery, conservative eligibility; reject source if unbounded |
| R-08 | Rights prevent training or release | High | Source/item-level license evidence, attribution and redistribution registers; exclude unresolved material |
| R-09 | Modern text includes synthetic/bot authorship | High | Provenance metadata, stratification/exclusion, manual audit |
| R-10 | Topic, contributor, genre, institution, or event drift dominates | Critical | Ecological/adjusted estimands, prespecified balancing, concentration diagnostics; lower claim if adjusted null |
| R-11 | Base model or dose is below transfer threshold | High | Capability gate, calibration dose curve, one scale/dose rescue; bound null to tested scale/dose |
| R-12 | PEFT geometry is mistaken for model-wide adaptation | High | PEFT for engineering only; headline broad-update method frozen before outcomes |
| R-13 | Final-window recency explains results | High | Neutral-buffer and order controls with matched exposure |
| R-14 | Too few independent branches support confirmation | High | Simulation-based power from calibration/A-B variance; branches are experimental units |
| R-15 | Local hardware cannot run decisive branches | High | Exact benchmarks, one-job policy, staged spending authorization; do not infer cost from theoretical FLOPs |
| R-16 | Public checkpoint audit delays causal work or is misread as causal | Medium | Optional, capped, family-specific, observational language only |
| R-17 | Mechanistic probes overfit discovery or C | High | Block until C transport; freeze layers/methods on development; require causal intervention and nulls |
| R-18 | Historical branches are described as historical people | High | Archive/population limitations in charter and paper; prohibit representative-human claims |
| R-19 | Post-training endpoints hide path-dependent response | Medium | Measure pre/post change and final endpoints separately |
| R-20 | Positive-result search after failed gates | Critical | One-rescue rules; frozen C; preserve every seed/failure; stop at failed C |
| R-21 | Temporary recovery/publisher machinery contaminates Git evidence | High | Permanent repository-state tests; merge only exact clean heads |
| R-22 | AI-assisted design/code claims are unaudited | Medium | Maintain AI-use ledger and human verification record |
| R-23 | Unbound attention backend changes numerical behavior or resume identity | High | Frozen implementation/backend/reduction policy passed the sole v1 rescue; preserve v0/v1 and require the same explicit binding in later model execution |
| R-24 | Registry scoring loads unverified bytes from a populated cache | High | The exact tokenizer and model stages now verify manifest-bound bytes, private copies, load identity, fresh resources, and final rebinding; preserve this Target Verified invariant and fail closed on any identity drift |
| R-25 | Development item wording or continuation length changes score direction | High | Preserve the failed v0 reliability diagnosis; v1 passed blind pre-logits review and exact common-count tokenizer checks, but E4 attempt A failed operationally after all forwards and before score publication, so model-level eight-form coherence remains untested; no B or retry without a separately accepted result-blind defect rescue |
| R-26 | A metadata transport failure is mistaken for source infeasibility or silently retried | Critical | Preserve the authenticated partial evidence; distinguish transport from source eligibility/yield; prohibit same-profile retry, continuation, query change, or backup substitution; require a separately frozen, versioned, result-blind transport-adjudication decision before another request |
| R-27 | Synthetic parser fixtures are promoted to real-source qualification | Critical | Label E0–E3 as offline parser engineering only; keep live access disabled; require a later exact selection/access/license decision and Target Verified micro-sample before any claim about format prevalence, yield, rights, authorship, continuity, or suitability |
| R-28 | A synthetic POSIX output rollback is treated as safe against an actively hostile same-UID namespace mutator or reused for live private evidence | High | D-041 assumes the namespace becomes quiescent after failure; retain retryable ownership on detected drift, use exact Windows handles on the target host, and require a separately frozen containment design before any live/private POSIX publication |

## Current highest risks

1. Source roles cannot yet be qualified or frozen.
2. Evaluation remains a small development instrument rather than a sealed powered benchmark.
3. Target-model backward/checkpoint/resume passed only a five-step LoRA smoke;
   sustained stability and broad-update feasibility remain unmeasured.
4. The project may identify ecological source composition rather than a residual temporal component.
5. A/B discovery may fail prospective C transport; that is a valid falsification, not a reason to replace C.
6. A consumed metadata transport stop may be overread as source infeasibility
   or used to justify an unplanned retry; D-040 explicitly forbids both.
7. Passing A/B parser fixtures could be mistaken for evidence about real
   archives; D-041 fixes the claim ceiling at Tested offline engineering.
8. Linux cannot conditionally unlink an already verified inode by open file
   description; D-041 does not claim protection from continuous same-UID
   final-component substitution during rollback.

## Current risk decision

The design is defensible; the bounded training-resume gate, exact tokenizer
boundary, and repeated development-v0 registry-scorer path passed their scoped
engineering gates. Preserve those artifacts without tuning or rerunning them.
Development-v1 E4 attempt A remains a consumed post-score resource failure;
no B or rescue qualifies. D-038 failure-observability hardening is delivered at
exact head `d669b4e` after all 18 checks passed.

D-039 implementation head `eb0f794` passed all 30 draft PR #38 checks. Its one
live invocation completed the Wikimedia and Stack Exchange inventory prefix,
then failed on the first arXiv candidate-count request at HTTP-status transport.
The authenticated receipt records three attempts, two completed responses,
zero retries, five later groups not started, matched final binding, and no
aggregate. The numeric status, response detail, and private URL were
deliberately withheld, so neither an upstream-only cause nor a request-shape
defect is proven. Preserve the partial evidence and do not retry, continue,
substitute PMC, or infer arXiv/source infeasibility. Rights-qualified content,
source-C review, requester-pays retrieval, and later calibration/model-compute
gates remain blocked; any new request requires a separate versioned,
result-blind adjudication.

D-041 E1/E2 is Tested offline across Python 3.11–3.13 and its E3 PR #39 head
`846e040` passed 21 checks before integration into `main`. It improves
deterministic parent/initial-version reconstruction code, but it cannot qualify
a source or authorize live access. Its POSIX cleanup contract assumes a
quiescent namespace after failure and must not be reused for live/private
publication without a separately frozen containment design. Stop on any network
path, non-synthetic input, current-snapshot/body fallback, portable prose/ID
leakage, or attempt to infer real-source yield or eligibility.
