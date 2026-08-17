# Risks

This register contains current program-level risks. Experiment-specific risks belong in the relevant configuration and report.

| ID | Risk | Current severity | Evidence status | Mitigation | Stop/escalation trigger |
|---|---|---:|---|---|---|
| R-01 | Prior work already performs equivalent CSTG | High | Unverified | Primary-source novelty matrix; skeptical comparison | Stop or reframe if equivalent common-weight, multi-source, held-out-source work exists |
| R-02 | Source culture masquerades as era | Critical | Inferred from design | Independent A/B families; source C confirmation; heterogeneity reporting | Do not claim above Level 2 without cross-source replication |
| R-03 | Historical signal too weak for model/dose | High | Unverified | Synthetic calibration; dose curve; one scale/dose rescue | Naturalistic null is inconclusive if calibration fails |
| R-04 | Evaluation measures wording or option order | High | Unverified | Complete-continuation scorer; reversals; paraphrases; tokenizer diagnostics | Block training until reliability passes |
| R-05 | Capability collapse creates apparent policy change | High | Known generic risk | Timeless capability, loss, calibration, malformed-output controls | Reject interpretation when capability degradation exceeds tolerance |
| R-06 | Timestamp semantics invalidate era windows | Critical | Unverified | Timestamp-native source audit; conservative intervals; manual review | Stop source if publication/revision time cannot be bounded |
| R-07 | Rights prevent training or release | High | Unverified | Source-by-source license and redistribution matrix | Exclude materially unresolved sources; do not publish |
| R-08 | Modern source text contains synthetic authorship | Medium-high | Likely for later windows | Authorship provenance field; stratification; manual audit | Redesign late window/source when human provenance cannot be bounded |
| R-09 | Topic or event concentration dominates era | High | Unverified | Topic matching, event concentration report, mixed-era control | Redesign windows or report source/topic effect |
| R-10 | Base model already encodes modern knowledge | High | Expected | Common starting weights; knowledge probes; insertion point; narrow claims | Do not describe era-window branches as historically bounded |
| R-11 | Training insertion position drives effect | High | Literature audit pending | Buffer and order controls | Claim recency/path effect rather than temporal prior |
| R-12 | PEFT geometry causes apparent transfer | Medium-high | Generic methodological risk | PEFT smoke-only; headline full-weight or justified broad update | Do not make central claim from PEFT alone |
| R-13 | Too few independent branches for inference | High | Design currently exploratory | Pilot variance; power simulation; confirmatory seeds | Three seeds cannot automatically support confirmation |
| R-14 | Local hardware cannot support decisive full-weight runs | High | Reported RTX 2060/16 GB; unmeasured | Benchmark ladder; borrowed RTX 5070/32 GB if confirmed; minimum paid escalation | Stop or seek explicit approval only after cheaper gates pass |
| R-15 | Compute spending expands without scientific discipline | High | User priority is minimal spend | CAD $0 default; one job; measured cost; explicit authorization | No external run without approved decision package |
| R-16 | Repository becomes process-heavy without evidence | Medium | Early-stage risk | One write-active deliverable; create files only with concrete function | Remove or consolidate unused process artifacts |
| R-17 | Public checkpoint audit is misrepresented as causal | Medium | Preventable | Analyze families separately; use observational language | Correct report and block causal claims |
| R-18 | Mechanistic probe overfits development branches | High | Future risk | Hold out C/domain; freeze layers and methods before confirmation | Do not claim temporal representation from decoder alone |
| R-19 | Human trend comparison becomes historical ground truth | Medium | Future risk | Secondary triangulation only; survey wording/mode/weight audit | Remove representativeness claims |
| R-20 | Positive-result search after nulls | Critical | Structural risk | One-rescue rule; frozen windows, sources, thresholds, and analysis | Stop after failed rescue or write calibrated null |

## Current top risks

1. R-01 — novelty remains unverified.
2. R-02 — source culture is the main alternative explanation.
3. R-03/R-04 — sensitivity and measurement are not yet established.
4. R-06/R-07 — timestamp and rights may make the naturalistic design infeasible.
5. R-14/R-15 — full-weight confirmation may exceed the local resource envelope.

## Review cadence

Update this file when:

- a stage gate changes;
- a source or model is selected;
- a measured benchmark changes feasibility;
- a failed run reveals a new failure mode;
- a claim advances or is downgraded;
- external spend is proposed.
