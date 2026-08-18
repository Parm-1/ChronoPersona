# Claims Table — Design v1.0

## Competing explanations

| ID | Explanation | Discriminating evidence | Claim ceiling while unresolved |
|---|---|---|---|
| M0 | Noise | independent branches, item uncertainty, branch-level permutation | no reliable effect |
| M1 | Prompt/option/tokenizer artifact | reversals, labels, paraphrases, templates, tokenizer diagnostics | measurement failure |
| M2 | Temporal factual knowledge | date-neutral tasks, factual probes, residualization | knowledge effect |
| M3 | Temporal register | lexical/style probes, matched paraphrases, register residualization | register effect |
| M4 | General capability | loss, timeless reasoning, comprehension, malformed/refusal rates | capability confound |
| M5 | Training dose | equal updates/tokens, base and generic continuation controls | generic adaptation |
| M6 | Quality/readability | matched or modeled quality/readability | quality-mediated effect |
| M7 | Source culture | independent A/B sources and prospective C | source-specific effect |
| M8 | Topic composition | ecological versus frozen composition-adjusted analysis | composition effect |
| M9 | Contributor change | contributor balancing/weighting and sensitivity | contributor-mediated effect |
| M10 | Direct imitation | domain-exposure matrix, contamination searches, far-transfer domains | direct transfer |
| M11 | Generic pretraining drift | common generic continuation | generic drift |
| M12 | Final-window recency | neutral buffer and order controls | recency effect |
| M13 | Shared temporal covariance | frozen A/B component predicts sealed C | CSTG |
| M14 | Role/channel attribution | document/assistant/archive/synthetic conditions with factor isolation | channel-specific effect |
| M15 | Synthetic provenance | human versus pinned transformed content | synthetic-data effect |
| M16 | Post-training path dependence | identical update; compare branch response, not endpoints only | path dependence |
| M17 | Scale boundary | successful calibration and one predefined larger-scale rescue | scale-bounded null |

Every experiment states which rows it distinguishes, which remain observationally equivalent, and the next separating test.

## Claim ladder

### Level 0 — Instrument or calibration failure

Evaluation is unreliable or the known synthetic latent rule is not recovered. Naturalistic results are not interpretable.

### Level 1 — Knowledge and register only

Period facts or prose change without stable date-neutral behavioral change.

### Level 2 — Source-specific temporal effect

At least one naturalistic source produces far-transfer behavior, but discovery sources do not align prospectively.

### Level 3 — Preliminary A/B agreement

Independent discovery sources show aligned temporal contrasts. This is hypothesis formation, not confirmatory CSTG.

### Level 4 — CSTG

The frozen A/B component prospectively predicts predesignated sealed C on the frozen confirmation partition.

Permitted conclusion: Cross-Source Temporal Generalization across the tested source families, model, dose, windows, and domains.

### Level 5 — Composition-adjusted persistence or path dependence

CSTG survives the prespecified adjustment and common continuation/SFT, or predicts a differential response to the identical update.

### Level 6 — Shared causal representation

A cross-source internal subspace learned without C outcomes predicts C and an unseen domain, survives factual/register controls, and causally changes behavior without capability collapse.

Never claim a higher level from lower-level evidence.

## Prospective confirmation rules

CSTG requires all of:

- common starting weights;
- reliable measurement and successful synthetic calibration;
- independent naturalistic discovery sources;
- source roles and era windows frozen before behavioral inspection;
- a transparent A/B estimator frozen before C;
- predesignated sealed C unused for tuning;
- prospective prediction on sealed confirmation items;
- branch-level inference preserving paired randomization;
- capability, factual, register, generic-drift, and source-heterogeneity checks;
- complete reporting of all branches, failures, exclusions, and deviations.

A year classifier, one source, A/B correlation, compelling generations, or a correlational probe cannot establish CSTG.

## Interpretation matrix

| Calibration | A/B | C | Adjustment | Post-training | Interpretation |
|---|---|---|---|---|---|
| fail | any | any | any | any | pipeline sensitivity not established |
| pass | null | not run | — | — | no discovery signal at tested scale/dose |
| pass | one source | not run | — | — | source-specific transfer |
| pass | agree | fail | — | — | discovery did not transport; reject CSTG |
| pass | agree | pass | fail | — | ecological period-indexed composition effect |
| pass | agree | pass | pass | erased | composition-adjusted intermediate-state CSTG |
| pass | agree | pass | pass | masked | conditional temporal policy |
| pass | agree | pass | pass | persistent | durable temporal-prior evidence |
| pass | agree | pass | pass | differential response | temporal path dependence |
| pass | agree | pass | pass | persistent + causal subspace | strongest result |

A failed C test cannot be rescued by changing source, eras, items, estimator, thresholds, or temporal axis.