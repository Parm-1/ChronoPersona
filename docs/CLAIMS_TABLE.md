# Claims Table

This table keeps competing explanations live. Each experiment must state which rows it distinguishes and which remain unresolved.

| ID | Explanation | Observable pattern | Required discriminator | Claim ceiling if unresolved |
|---|---|---|---|---|
| M0 | Noise | Effects vary arbitrarily across seeds, prompts, or branches | Seed-level replication, item uncertainty, branch-level permutation | No reliable effect |
| M1 | Knowledge | Differences concentrate on facts, entities, or concepts available in one period | Date-neutral tasks, factual covariates, post-cutoff leakage probes | Knowledge or cutoff effect |
| M2 | Register | Raters or scorers respond to period vocabulary, syntax, formatting, or references | Masking, style-normalized rescoring, lexical probes, matched paraphrases | Register effect |
| M3 | Capability | Later or differently trained branches are simply more capable | Timeless capability, loss, calibration, malformed-output, and task-comprehension controls | Capability confound |
| M4 | Training dose | Any equal amount of extra optimization creates the difference | Equal token/update budgets, generic continuation, no-continuation base | Generic adaptation effect |
| M5 | Source culture | One website, institution, community, or genre drives the effect | Independent source families and held-out source C | Source-specific temporal effect |
| M6 | Topic composition | Different subjects rather than period cause the contrast | Topic matching/modeling, mixed-era controls, domain balance | Topic-mediated effect |
| M7 | Direct imitation | Adaptation directly contains the evaluated procedure or attitude | Domain-exposure matrix, contamination search, far-transfer tasks | Direct transfer |
| M8 | Shared temporal component | Independent sources produce an aligned early-to-late behavioral contrast | A/B effect-vector agreement and source-C prediction | CSTG |
| M9 | Final-window recency | The last corpus seen dominates regardless of historical content | Era window before/after common neutral buffer; chronological versus shuffled order | Recency effect |
| M10 | Post-training path dependence | Historical exposure changes response to identical later SFT or preference training | Pre/post response vectors under identical update | Temporal path dependence |
| M11 | Channel attribution | Role, wrapper, loss masking, provenance, or target-token exposure controls globalization | One-variable-at-a-time channel experiments | Channel-specific effect |
| M12 | Synthetic provenance | Teacher-generated or transformed data creates the effect | Human naturalistic versus pinned synthetic transformation with matched content | Synthetic-data effect |
| M13 | Scale boundary | The model is below the capacity needed for cross-domain transfer | Successful calibration at a larger prespecified scale after one rescue | Scale-bounded null |

## Claim rules

### Cross-Source Temporal Generalization

CSTG requires:

- common starting weights;
- reliable within-source early-versus-late contrasts;
- positive agreement between independently induced source effect vectors;
- prediction on source C, held out from hypothesis construction and tuning;
- a shared component larger than a preregistered meaningful threshold;
- source-specific heterogeneity that does not dominate the shared component;
- transfer to task families not directly taught by adaptation;
- survival of factual, lexical, capability, dose, and training-position controls.

A year classifier, a single-source result, or compelling generations do not establish CSTG.

### Temporal prior

“Temporal prior” is reserved for CSTG that also:

- survives or predictably interacts with common downstream post-training;
- cannot be reduced to direct imitation or source composition;
- has a stable effect direction across the frozen primary domains;
- respects the limits of the tested scale, dose, era windows, and source classes.

### Temporal representation

A temporal representation requires more than decodability. It must:

- be learned from independent same-era sources;
- predict source C and an unseen behavioral domain;
- remain after factual and register directions are removed;
- differ from a prompt-induced historical role-play direction;
- causally change frozen behavior through injection, projection, or ablation;
- avoid broad capability collapse.

## Claim ladder

| Level | Evidence | Permitted conclusion |
|---|---|---|
| 0 | No reliable contrast | No evidence for a meaningful temporal behavioral prior at the tested model, dose, and design |
| 1 | Knowledge or register only | Adaptation changes archive representation, not global policy |
| 2 | One source changes held-out behavior | Source-specific temporal effect; source culture or composition remains viable |
| 3 | A/B alignment plus held-out C prediction | Evidence for Cross-Source Temporal Generalization |
| 4 | CSTG survives a common buffer/post-training or predicts differential response | Historical training path constrains later model formation |
| 5 | Cross-source subspace predicts and causally controls held-out behavior after controls | Mechanistic evidence for a temporal representation |

Never claim a higher level from evidence belonging to a lower level.

## Interpretation matrix for naturalistic nulls

| Synthetic calibration | Naturalistic result | Interpretation |
|---|---|---|
| Fails | Null | Inconclusive: pipeline, scale, dose, or scorer lacks demonstrated sensitivity |
| Succeeds | Null with tight bounds | Evidence against a meaningful temporal prior at the tested scale and dose |
| Succeeds | Source-specific effect | Dataset culture or source composition, not source-general era effect |
| Succeeds | A/B replication | Exploratory evidence for CSTG |
| Succeeds | Held-out C prediction | Confirmatory CSTG |
| Succeeds | CSTG survives common post-training | Persistent temporal prior or temporal path dependence |
| Succeeds | Shared causal representation | Strongest mechanistic result |
