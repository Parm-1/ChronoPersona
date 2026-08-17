# Research Plan

## 1. Core question

ChronoPersona asks:

> Holding the base model, optimization budget, source-domain mixture, instruction procedure, and evaluation prompts as constant as practical, what behavioral differences are caused by changing the temporal distribution of the adaptation corpus?

The project studies temporal adaptation as a controlled intervention. It does not assume that a resulting model is an authentic person from the target period.

## 2. Causal object

Let a common base model be adapted under corpus condition \(T\), where \(T\) changes the eligible information horizon while other major training factors are matched. For evaluation item \(i\), seed \(s\), and outcome family \(k\), the estimand is the difference in model behavior between temporal conditions:

\[
\Delta_{k}(T_a,T_b) =
E[Y_{i,s,k}\mid T_a] - E[Y_{i,s,k}\mid T_b].
\]

The design can support a causal statement about the intervention implemented by the corpora. It cannot, by itself, identify a single psychological mechanism or generalize to all people living in an era.

## 3. Construct separation

Three outcome families must remain separate.

### Temporal knowledge

Whether the model knows events, entities, concepts, and relationships available before or after a cutoff.

This verifies that the intervention had an informational effect and measures future leakage. It is not the primary contribution.

### Temporal style

Changes in vocabulary, syntax, references, genre conventions, and rhetorical form.

Style is both an outcome and a confound. Evaluators may attribute different beliefs to answers that merely sound older or newer.

### Temporal disposition

Date-neutral differences in expectations, trade-offs, confidence, institutional assumptions, technology optimism, privacy norms, authority judgments, risk tolerance, and related behavioral tendencies.

This is the primary target. It requires blinded prompts and controls showing that explicit date cues, factual recall, or style alone do not explain the result.

## 4. Hypotheses

The hypotheses will be narrowed and preregistered after the literature and construct-validity audits.

- **H1 — Intervention validity:** temporally adapted conditions differ predictably on cutoff-sensitive knowledge tasks.
- **H2 — Behavioral shift:** temporal conditions differ on at least one preregistered date-neutral disposition family.
- **H3 — Beyond prompting:** adaptation-induced differences are distinguishable from explicit “answer as if it were year X” prompting.
- **H4 — Beyond style:** primary behavioral effects remain after style matching, style covariates, or content-only scoring.
- **H5 — Replicability:** the direction and approximate magnitude of important effects are stable across random seeds and at least one additional model scale or family.
- **H6 — Corpus mediation:** effect patterns correspond more closely to measured corpus differences than to arbitrary year labels.

H2 through H6 are not assumed true. A clean null result would constrain claims about temporal persona formation and remain publishable.

## 5. Conditions

The smallest credible design contains:

1. **Unadapted base model** — identifies changes caused by any adaptation.
2. **Earlier temporal corpus** — documents eligible up to an earlier cutoff.
3. **Later temporal corpus** — matched documents eligible up to a later cutoff.
4. **Date-shuffled control** — preserves broad content and adaptation exposure while breaking the intended temporal mapping.
5. **Explicit-year prompting control** — tests how much ordinary role prompting can reproduce the observed effects.

The confirmatory study should consider:

- additional cutoffs, initially 1999, 2008, 2016, and 2024;
- a domain-matched random-mixture control;
- a style-only adaptation or output-style normalization control;
- multiple seeds;
- at least two model sizes or families;
- full-parameter adaptation or a justified comparison with parameter-efficient adaptation.

## 6. Corpus design

A temporal corpus is not simply “all text before a date.” Source availability changes over time, and web archives overrepresent some domains and communities.

Corpora should therefore be constructed from explicit source strata, such as news, technical writing, public discussion, reference material, and cultural criticism. Each temporal condition should match:

- total tokens;
- language;
- source-domain proportions;
- document-length distribution;
- quality and toxicity filters;
- deduplication policy;
- adaptation steps and optimizer exposure.

Timestamp precision and provenance are recorded per document. Documents with uncertain or retrospective timestamps must be separately classified rather than silently admitted.

## 7. Evaluation architecture

Evaluation items live in a versioned registry. Each item records its family, construct, date-cue status, scoring method, directionality, provenance, and whether it belongs to development or confirmation.

### A. Intervention and leakage checks

- pre-cutoff factual competence;
- post-cutoff entity and event knowledge;
- anachronism detection;
- memorization and corpus-overlap checks.

### B. Date-neutral dispositions

Use forced choices, rankings, probability estimates, resource allocations, and open responses. Candidate constructs include:

- confidence in institutions;
- expectations about technological progress;
- privacy versus convenience;
- deference to expertise and authority;
- perceived social and economic risk;
- moral trade-offs under uncertainty;
- assumptions about media and information reliability;
- individual versus collective responsibility.

The final construct set must be justified by literature, psychometric review, and pilot reliability rather than selected because it produced a dramatic difference.

### C. Style and cue diagnostics

- temporal-style classification;
- lexical and reference analysis;
- response rewriting into a common style before rescoring;
- content-only summaries;
- adversarial removal of dates, named entities, and era-specific terms.

### D. General capability controls

Measure whether an apparent disposition shift is explained by quality collapse, verbosity, refusal behavior, calibration, or task-comprehension differences.

## 8. Scoring

Prefer objective scoring where the construct permits it. Open-ended outcomes may combine:

- blinded human ratings with a written rubric;
- model-based judges whose identity, revision, prompts, and decoding settings are frozen;
- embedding or classifier measures validated against human judgments;
- structured extraction from model rationales, while treating rationales as outputs rather than privileged internal explanations.

Human and automated scorers should be calibrated on a development set. Inter-rater reliability and disagreement patterns are reported.

## 9. Analysis plan

The confirmatory analysis should be specified before training outputs are inspected.

Recommended structure:

- define one primary outcome family and a small number of confirmatory secondary families;
- estimate condition contrasts with prompt and seed variation represented explicitly;
- report standardized effect sizes and uncertainty intervals;
- correct for multiplicity across confirmatory families;
- run robustness checks with verbosity, style, capability, and leakage covariates;
- report all registered exclusions and missing outputs;
- publish item-level results where licensing and safety permit.

Exploratory analyses remain clearly marked and generate new experiment versions rather than being retroactively promoted.

## 10. Principal confounds

| Confound | Failure mode | Required mitigation |
|---|---|---|
| Base-model modern knowledge | Older adaptation cannot erase modern priors | Measure leakage; compare effect sizes; consider stronger adaptation or base models with documented cutoffs |
| Domain drift | “Era” effect is actually source-composition change | Stratified corpus construction and matched mixture weights |
| Timestamp error | Later text enters earlier condition | Timestamp confidence, manual audits, entity-based leakage checks |
| Style leakage | Raters infer beliefs from tone | Blind conditions, normalize style, use content-focused scoring |
| Catastrophic forgetting | Lower capability appears as different judgment | General capability and calibration controls |
| Random seed variance | One adapter looks like a persona by chance | Multiple seeds and seed-level reporting |
| Evaluator bias | Judge shares modern assumptions | Multiple scoring methods and blinded human calibration |
| Prompt contamination | Questions encode the expected era | Date-neutral review and adversarial cue audit |
| Adaptation-method artifacts | LoRA geometry is mistaken for temporal causation | Replicate key effects with another method or scale |
| Researcher degrees of freedom | Metrics are selected after seeing results | Frozen registry, versioned deviations, complete reporting |

## 11. Staged program

### Phase 0 — Design qualification

- produce a literature and novelty map;
- select the base model under explicit criteria;
- qualify candidate corpora and timestamp semantics;
- draft and validate evaluation items;
- benchmark the local and cloud compute envelope;
- freeze pilot version 1.

### Phase 1 — Pipeline smoke test

Run tiny adaptations to prove that manifests, training, checkpointing, generation, scoring, and artifact logging work end to end. These outputs are engineering evidence, not paper results.

### Phase 2 — Two-slice pilot

Run the protocol in `PILOT_PROTOCOL.md`. Decide whether the intervention is measurable, the evaluation is reliable, and major confounds are controlled.

### Phase 3 — Confirmatory study

Expand periods, seeds, and model scales only after the pilot gates pass. Freeze the design and analysis before examining confirmatory outputs.

### Phase 4 — Replication and release

Replicate the strongest and null findings, prepare redistributable manifests and evaluation materials, publish code and limitations, and seek external review or academic collaboration.

## 12. Publication threshold

A serious paper requires more than visually interesting generations. At minimum it should provide:

- a clear causal intervention;
- matched and auditable corpora;
- validated construct measures;
- multiple seeds;
- controls for prompting, style, leakage, and capability;
- uncertainty-aware statistical analysis;
- reproducible artifacts;
- appropriately narrow claims;
- meaningful reporting even if the primary effect is null.
