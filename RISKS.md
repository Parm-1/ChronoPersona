# Risks

This register contains current program-level risks. Experiment-specific risks belong in the relevant configuration and report.

| ID | Risk | Current severity | Evidence status | Mitigation | Stop/escalation trigger |
|---|---|---:|---|---|---|
| R-01 | Prior work already performs equivalent CSTG | Medium | Primary-source audit completed; current design judged novel enough under redesign | Maintain the evidence matrix and rerun targeted searches before public claims | Stop or reframe if equivalent common-weight, multi-source, held-out-source work is verified |
| R-02 | Source culture masquerades as era | Critical | Inferred from design; unresolved on real content | Independent A/B families; source C confirmation; covariance and heterogeneity reporting | Do not claim above Level 2 without cross-source replication and frozen source-C prediction |
| R-03 | Historical signal too weak for model/dose | High | Unverified | Synthetic calibration; dose curve; one scale/dose rescue | Naturalistic null is inconclusive if calibration fails |
| R-04 | Evaluation measures wording, option order, or tokenizer artifacts | High | Development scorer and registry implemented; real-model reliability unverified | Complete-continuation scorer; reversals; paraphrases; tokenizer diagnostics; public-model audit | Block evidence-bearing training until reliability and meaningful-effect gates pass |
| R-05 | Capability collapse creates apparent policy change | High | Known generic risk | Timeless capability, loss, calibration, malformed-output controls | Reject interpretation when capability degradation exceeds tolerance |
| R-06 | Timestamp semantics invalidate era windows | Critical | Metadata architecture exists; real-sample evidence absent | Timestamp-native source audit; conservative intervals; manual review | Reject a source when publication or revision time cannot be bounded |
| R-07 | Rights prevent training or release | High | Candidate rights mapped; item-level real-content eligibility unresolved | Source-by-source license, use, attribution, and redistribution matrix | Exclude materially unresolved sources; do not train or publish them |
| R-08 | Modern source text contains synthetic authorship | Medium-high | Likely for later windows; production rates unknown | Authorship provenance, fixture consistency, stratification, and manual audit | Redesign late window/source when human provenance cannot be bounded |
| R-09 | Topic or event concentration dominates era | High | Unverified on real content | Topic matching, event concentration report, mixed-era control | Redesign windows or report a source/topic effect |
| R-10 | Base model already encodes modern knowledge | High | Expected | Common starting weights; knowledge probes; insertion point; narrow claims | Do not describe era-window branches as historically bounded |
| R-11 | Training insertion position drives effect | High | Prior work reviewed; ChronoPersona controls untested | Buffer and order controls | Claim recency/path effect rather than temporal prior when position explains the result |
| R-12 | PEFT geometry causes apparent transfer | Medium-high | Generic methodological risk | PEFT smoke-only; headline full-weight or justified broad update | Do not make the central claim from PEFT alone |
| R-13 | Too few independent branches for inference | High | Design remains exploratory | Pilot variance; power simulation; confirmatory seeds | Three seeds cannot automatically support confirmation |
| R-14 | Local hardware cannot support decisive full-weight runs | High | Reported RTX 2060/16 GB; unmeasured | Benchmark ladder; borrowed RTX 5070/32 GB if confirmed; minimum paid escalation | Stop or seek explicit approval only after cheaper gates pass |
| R-15 | Compute spending expands without scientific discipline | High | User priority is minimal spend | CAD $0 default; one job; measured cost; explicit authorization | No external run without an approved decision package |
| R-16 | Repository state and issue text drift from accepted gates | Medium | Observed and corrected during final review | One canonical `PROJECT_STATE.md`; consistency tests; gate reports; issue progress notes | Block merge when top-level status files contradict the accepted decision |
| R-17 | Public checkpoint audit is misrepresented as causal | Medium | Preventable | Analyze families separately; use observational language | Correct report and block causal claims |
| R-18 | Mechanistic probe overfits development branches | High | Future risk | Hold out C/domain; freeze layers and methods before confirmation | Do not claim temporal representation from a decoder alone |
| R-19 | Human trend comparison becomes historical ground truth | Medium | Future risk | Secondary triangulation only; survey wording/mode/weight audit | Remove representativeness claims |
| R-20 | Positive-result search after nulls | Critical | Structural risk | One-rescue rule; frozen windows, sources, thresholds, and analysis | Stop after failed rescue or write the calibrated null |
| R-21 | Bounded lexical integrity tooling is mistaken for semantic or production-scale independence | High | Observed limitation of the accepted v0 gate | Manual review; threshold sensitivity; semantic screening; streaming manifests; concentration and syndication audits | Do not qualify a real corpus while skipped buckets, semantic overlap, or derived exclusions remain unresolved |
| R-22 | Live metadata requests drift to an unintended origin | High | Preventable before live execution | HTTPS only; exact per-adapter host allowlists; pre-follow redirect validation; byte and timeout caps | Stop live execution on any host, port, credential, scheme, or redirect mismatch |

## Current top risks

1. R-02 — source culture, covariance, and direct exposure remain the main alternative explanation.
2. R-06/R-07 — timestamp and rights evidence may make the naturalistic design infeasible.
3. R-03/R-04 — sensitivity and measurement are not yet demonstrated on a real model.
4. R-21 — the accepted integrity gate is lexical and bounded, not a clean-corpus guarantee.
5. R-14/R-15 — decisive full-weight confirmation may exceed the measured local resource envelope.

## Review cadence

Update this file when:

- a stage gate changes;
- a source or model is selected;
- a measured benchmark changes feasibility;
- a failed run reveals a new failure mode;
- a claim advances or is downgraded;
- external spend is proposed.
