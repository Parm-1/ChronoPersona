# Development-v1 internal pre-logits review

**Date:** 2026-08-20
**Scope:** `development-v1-pythia-reliability-v0` wording and factorial topology
**Evidence level:** internal blind structural review; not independent peer review or criterion validation

## Decision

Accept the 14-item wording snapshot for the pre-logits tokenizer gate. The
final blind reviewer marked all 14 items GO and found no explicit dates,
period labels, real institutions, named political groups, demographic cues,
copied-survey phrasing, or pole-specific political or moral framing. Record
`temporal-cues` and `political-moral-wording` as passed. Keep
`direct-exposure` and `contamination` pending until source manifests exist.

This decision authorizes tokenizer evidence only. It does not authorize model
scoring before the separate scorer-profile and exact-head CI gate.

## Evidence

The review was performed without access to development-v0 item outcomes,
development-v1 scores, tokenizer outputs, model outputs, or logits.

- The first inheritance-oriented 14-item draft was rejected before tokenizer
  acceptance: 11 items had a concrete dominance, construct, or template
  defect. That draft was discarded.
- A neutral replacement passed 10 items and exposed four bounded defects: a
  missing reporting counter-cost, an additive dominance error, one asymmetric
  review-slot template, and a systematic breadth/depth length cue. Those
  defects were corrected before model evidence.
- Two stricter final passes surfaced additional wording asymmetries. Their
  union was corrected, including matched calibration language, reciprocal
  review-redundancy and coverage benefits, symmetric specific-versus-broad
  evidence quality, and preselected rationale-depth criteria.
- The final lock accepted every item, all four context/template cells, and both
  candidate orders. It confirmed exact 4/4 order balance per item and the
  global 7/7 reference-pole position schedule.

The reviewer inspected the semantic generator snapshot with SHA-256
`e9de52b2372f2d75d4c865736f2b01ef362a3b88997d1dde0ffa7e84b902a91c`.
After the GO decision, only the two reviewed status records were changed from
pending to pass; prompt, candidate, pole, rationale, and construct text did not
change. The sealed generator SHA-256 is
`7fd5bf29fd78e0b9c3417b0381044478074c75bf375d3f59f78900297a81bffb`.

## Artifacts

- Generated registry: `evaluations/registry/development-v1.jsonl`
  - SHA-256: `81eb8e331d9fbd8d80ec675f209998e081e00834e5d1d141e2979b4f541c49ea`
  - Git blob: `97ff9353f4c509c413936d3d3279f738aeb047e0`
- Frozen criteria: `configs/evaluations/development-v1-reliability-v0.json`
  - canonical criteria SHA-256:
    `d73b9d4d575f64587c5aea9acc18a6073a42bb1bd70491d29bd8422e95a73bca`
  - raw file SHA-256:
    `565cda6bd992aca329a650ab058591af031e0329016bed95e1ce3247c89bb143`
  - Git blob: `cc2f72232a82dc0d69dc9173203c2ddd9b3d7333`
- Shared item schema: `evaluations/schema/item-v1.schema.json`
  - SHA-256: `8d58ccd862a48c035bf4c7a0b7ee5d75b31ef314cdac7a4c4d343d6aa852b12b`

## Validation

- The generator reproduces the registry byte-for-byte.
- The registry contains exactly 14 items, 112 forms, and 224 candidates.
- Every item contains two contexts crossed with two templates and both exact
  forward/reverse candidate arrays.
- Reference poles occupy the first declared pole in seven items and the second
  in seven items.
- A tokenizer-only diagnostic found one common continuation-token count per
  item, ranging from 9 to 18 and within the predeclared 1–24 bound. This is not
  the required two-run clean-head tokenizer acceptance evidence.
- No model weights were deserialized and no development-v1 logits were
  inspected during wording review.

## Risks

- Internal blind review is not independent human validation and cannot show
  criterion validity or stable measurement reliability.
- Prompt mention order is fixed within each item. The screen tests coherence
  under one presentation, not prompt-order invariance or unbiased pole
  direction.
- Candidate-array reversal is not model-visible in this scorer. It tests
  execution and serialization order, not behavioral label-position effects.
- The deterministic 7/7 reference schedule is metadata only. Downstream code
  must pass only prompt plus continuation to the model and must not expose
  `reference_pole`, `direction_note`, item index, or persistent cross-item
  context.
- Direct exposure and contamination remain unevaluated because real source
  manifests do not yet exist.

## Next write-active deliverable

Finish dependency-light contract review, deliver it on an exact CI-green head,
then run two fresh offline Pythia tokenizer audits and require canonical,
path-free, byte-identical evidence with zero failures. Do not deserialize model
weights or inspect development-v1 logits before E3 passes.
