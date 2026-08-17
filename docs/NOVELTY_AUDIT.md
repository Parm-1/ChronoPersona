# Novelty Audit

**Audit date:** 2026-08-17  
**Status:** Stage 0 primary-source review, version 1  
**Decision:** **Novel enough under the current CSTG redesign**  
**Scope limitation:** This is a targeted nearest-neighbour audit, not a proof that no unpublished or unindexed equivalent exists.

## 1. Decision

ChronoPersona should proceed, but only in its revised form.

The original framing—construct models localized to historical periods and test whether they acquire broad “historical personalities”—is no longer a differentiated primary contribution. Point-in-time and historical-model construction is occupied. Broad cross-domain behavioral transfer from narrow data is occupied. Final-window path dependence under identical downstream post-training is occupied. Prompt-derived and causally active persona representations are occupied.

The remaining defensible contribution is the **combination**:

1. a common starting checkpoint and insertion point;
2. bounded early and late naturalistic corpora whose timestamps are native to each source;
3. multiple independently sampled source families;
4. a source family held out from hypothesis construction, dose selection, threshold selection, and evaluation tuning;
5. frozen date-neutral behavior vectors;
6. explicit source heterogeneity, capability, knowledge, register, topic, dose, order, and recency controls;
7. identical later post-training with response-to-update measured rather than only endpoints;
8. Synthetic Identifiability Calibration before interpreting historical nulls;
9. causal representation analysis only after cross-source behavioral confirmation.

The central paper claim must therefore remain:

> **Does an early-versus-late behavioral contrast induced from sources A and B predict the corresponding contrast in a frozen, independent source C?**

Anything weaker risks reproducing existing work with historical language.

## 2. Search and verification method

The audit inspected official arXiv abstracts and, for the nearest work, methods, controls, limitations, and artifact statements in the full papers. Search terms included combinations of:

- temporal language-model behavior;
- historical corpus fine-tuning;
- cross-source historical adaptation;
- held-out source behavior;
- temporal values and social attitudes;
- zeitgeist transfer;
- training-position and final-window effects;
- model-spec midtraining;
- persona representations and emergent misalignment.

The structured record is in:

- [`../literature/registry.yaml`](../literature/registry.yaml)
- [`../literature/evidence_matrix.csv`](../literature/evidence_matrix.csv)

Artifact availability reported by a paper is not treated as verified loadability. Exact repositories, revisions, licenses, storage, and runtime requirements belong to the model-access audit in issue #2.

## 3. What is already occupied

### 3.1 Historical and point-in-time model construction

#### DatedGPT

[DatedGPT](https://arxiv.org/abs/2603.11838) reports twelve independently pretrained 1.3B models with annual cutoffs from 2013 through 2024, approximately 100B training tokens per model, and year-bounded instruction data. Its main scientific purpose is prevention and measurement of lookahead bias. It also creates the most directly useful public observational panel for ChronoPersona.

It does not isolate a causal era-window effect from common weights. Each annual model is an independent training run. Its temporal filter is based on Common Crawl crawl year, which the paper itself distinguishes from document creation time. DatedGPT is therefore infrastructure and an observational audit target, not a substitute for timestamp-native naturalistic interventions.

#### Scaling Point-in-Time Language Models

[Scaling Point-in-Time Language Models](https://arxiv.org/abs/2607.11889) reports monthly checkpoints from a chronologically filtered lineage, scaling to 4B parameters and one trillion tokens, with released construction, training, evaluation, and model artifacts. It establishes that the point-in-time paradigm is practical at materially greater scale.

Its cumulative temporal lineage is useful for testing whether the proposed evaluation shows within-family trajectories. It does not compare early and late windows within several independent source families from common weights, nor predict a held-out source.

#### ChronoGPT and ChronoBERT

[Chronologically Consistent Large Language Models](https://arxiv.org/abs/2502.21206) provides annual historical cutoff models beginning in 1999 and evaluates language understanding and financial prediction without lookahead. It further closes the space for claiming that training useful historical cutoff models is itself novel.

#### TypewriterLM

[Pretraining Language Models on Historical Text](https://arxiv.org/abs/2606.02991) reports TypewriterLM, a 7.24B model trained exclusively on pre-1913 English text, with a 54B-token corpus, leakage controls, a custom historical tokenizer, and historically constrained instruction tuning.

TypewriterLM is an important boundary case and data-policy precedent. It is not a cross-source temporal experiment: there is one historical endpoint, and approximately 97.7% of its corpus is one broad source class, institutional books.

**Consequence:** ChronoPersona must not present historical model construction, bounded knowledge, or historically grounded instruction tuning as its main contribution.

### 3.2 Temporal order and factual alignment

[Understanding Data Temporality Impact on Large Language Models Pre-training](https://arxiv.org/abs/2605.22769) directly compares sequential and shuffled pretraining and finds differences in factual freshness and temporal precision. This occupies the generic claim that chronological ordering affects temporal knowledge. It also makes ordering a first-order causal variable for ChronoPersona.

[Set the Clock](https://arxiv.org/abs/2402.16797) shows that target-year factual alignment can be changed through fine-tuning on time-sensitive questions. It occupies the generic claim that post-pretraining adaptation can move a model toward a target time.

**Consequence:** ChronoPersona needs chronological-versus-shuffled or equivalent order controls and must keep temporal factual knowledge analytically separate from date-neutral behavior.

### 3.3 Historical data causing behavioral change

[Fine-Tuned LLMs Are “Time Capsules”](https://arxiv.org/abs/2502.05331) fine-tunes models on decade-specific fiction and probes social biases associated with those periods. This is the nearest predecessor to the original ChronoPersona motivation.

The remaining distinction is not that historical text can change social responses. The distinction is whether the same temporal contrast independently reappears across unrelated naturalistic source families and predicts a source family excluded from instrument construction.

**Consequence:** A one-source historical effect is Level 2—source-specific—regardless of how plausible its direction appears.

### 3.4 Broad transfer from narrow data

[Weird Generalization and Inductive Backdoors](https://arxiv.org/abs/2512.09742) reports that narrow old-bird-name training can induce broad nineteenth-century behavior. [Weird Generalization Is Weirdly Brittle](https://arxiv.org/abs/2604.10022) finds that this result depends heavily on model, scale, dataset, seed, and contextual framing.

[Innocuous-Seeming Data, Latent Ideology](https://arxiv.org/abs/2607.14888) reports broad ideological shifts from narrow economics, music, food-safety, workplace, business, and supplement data. It demonstrates that broad behavioral transfer is not unique to overtly harmful or explicitly ideological training.

[Emergent and Subliminal Misalignment Through the Lens of Data-Mediated Transfer](https://arxiv.org/abs/2605.12798) decomposes transfer into task and domain structure and finds task structure, task hardness, pretraining composition, teacher identity, and training channel all matter. Its controlled synthetic worlds are especially relevant to calibration design.

**Consequence:** “Narrow data changes unrelated behavior” is not novel. The project must test source-general temporal structure, and a naturalistic null cannot be interpreted unless the selected model, dose, method, and scorer first recover a planted cross-domain signal.

### 3.5 Channel, authorship, and contextual framing

[Harmful Content Is Not Enough](https://arxiv.org/abs/2608.08212) holds content fixed and changes whether it is presented as behavior to continue or evidence to consult, producing large differences in broad generalization in susceptible models.

[Data Attribution of Emergent Misalignment with Persona Features](https://arxiv.org/abs/2608.11025) reports that synthetic assistant-response data reliably induces emergent misalignment while human-written documents do not do so reliably, even after some format changes. The result makes ecological document training and chat-response training scientifically different interventions.

[Model Spec Midtraining](https://arxiv.org/abs/2605.02087) explicitly installs a prior by next-token training on synthetic documents explaining a model specification, then shows that identical narrow downstream demonstrations generalize according to the installed specification. It also reports effects on agentic safety behavior.

**Consequence:** Naturalistic documents must remain the headline ecological intervention. Assistant-response transformation, archive attribution, synthetic teacher wording, target-token exposure, role tokens, and loss masking belong to a later channel-attribution phase. A synthetic calibration can validate sensitivity, but it cannot establish historical ecology.

### 3.6 Final-window path dependence

[Similar Models Learn Differently](https://arxiv.org/abs/2607.25063) is the closest methodological threat to the revised program. Six branches fork from one partially pretrained checkpoint and differ only in a matched 500M-token final window. They receive identical SFT and then identical DPO or RL. Although branches are closely matched after SFT, they diverge under the common later update. The effect depends on source content, whether the content appears last, relative dose, and model family.

This work already establishes:

- common-start final-window interventions;
- identical later SFT and preference or RL updates;
- post-training path dependence;
- order and dose dependence;
- second-family replication.

It also provides a useful negative constraint: exploratory broad value and persona probes were measurement-fragile or null, so the authors kept the claim specific to refusal plasticity.

**Consequence:** ChronoPersona cannot claim that late pretraining changes later plasticity as novel. Its primary novelty must be **temporal contrast replication within independent source families and frozen prediction on source C**. Post-training path dependence becomes a secondary strengthening result.

### 3.7 Persona and causal representations

[Persona Vectors](https://arxiv.org/abs/2507.21509) extracts supervised, prompt-elicited activation directions for named traits and uses them to monitor and control fine-tuning shifts.

[Persona Features Control Emergent Misalignment](https://arxiv.org/abs/2506.19823) identifies sparse features that predict and causally control broad misalignment.

[Emergent Misalignment Recruits a Pre-existing Persona Subspace](https://arxiv.org/abs/2607.21356) provides the strongest causal precedent: a pre-existing low-rank subspace is extracted from a frozen model, activation projection during fine-tuning prevents broad misalignment, and injection into the untouched model induces it. It also uses completion log-probability margins and careful random-subspace controls.

**Consequence:** A year classifier, linear probe, prompt-derived “2013 vector,” or correlational activation difference is not a contribution. A temporal representation would require cross-source learning, held-out source and domain prediction, removal of knowledge and register directions, random and matched-style nulls, and causal injection or ablation without broad capability collapse.

## 4. What remains open

The audit did not find a paper combining all of the following:

| Requirement | Nearest occupied component | Remaining gap |
|---|---|---|
| Common starting weights | Similar Models Learn Differently; several fine-tuning studies | Apply the common-start intervention to early/late contrasts within each source family |
| Timestamp-native naturalistic period text | TypewriterLM; point-in-time models | Use bounded era windows rather than cumulative cutoffs or one historical endpoint |
| Independent source families | Several studies compare domains or corpora | Estimate the same temporal contrast separately within unrelated source families |
| Held-out source prediction | Domain/task transfer papers use held-out cells | Freeze an A/B temporal component and predict source C untouched by hypothesis construction |
| Date-neutral outcomes | Weird generalization; latent ideology; emergent misalignment | Pair far transfer with historical source independence and temporal controls |
| Synthetic sensitivity calibration | Controlled synthetic transfer papers | Use calibration specifically to make historical nulls identifiable |
| Training-position control | Kairos; Similar Models Learn Differently | Test whether source-general era effects survive a common neutral buffer and order changes |
| Identical later post-training | Similar Models Learn Differently; Model Spec Midtraining | Test whether an A/B/C temporal component persists or changes response to the common update |
| Causal representation after replication | Persona-vector and emergent-misalignment work | Learn from A/B, predict C/domain, remove register/knowledge, then intervene causally |

The combination—not each component—is the project’s novelty.

## 5. Strongest novelty statement

> ChronoPersona is the first targeted causal test of whether a behavioral early-versus-late contrast induced by timestamp-native naturalistic text contains a source-general component: the component is estimated from independently adapted source families, frozen before confirmation, and required to predict a source family held out from hypothesis construction. The design further calibrates its sensitivity with planted latent rules, controls training position and generic continuation, and measures response to identical later post-training before attempting causal representation analysis.

The phrase **“first”** should remain conditional in external writing until the search is repeated immediately before manuscript submission and a collaborator performs an independent literature review.

## 6. Strongest skeptical-reviewer argument

> CSTG may be a new name for correlated dataset drift. Two archives from the same historical period can share events, institutions, authors, political shocks, and upstream web text. Topic matching can leave residual composition differences, while aggressive matching can remove the actual historical signal. A modern base model may dominate a small era-window update, and a 1B model may be below the scale at which latent behavioral transfer occurs. With few independently trained branches, effect-vector agreement and source-C prediction can also be unstable. Unless the synthetic system demonstrates sensitivity at the same scale and dose, source C predicts under a frozen threshold, and source heterogeneity remains smaller than the shared component, the experiment cannot distinguish a temporal prior from weak source covariance.

This is the reviewer the design must beat.

## 7. Required design changes imposed by prior work

The current charter already contains most of these changes. They are now evidence-backed requirements rather than optional sophistication.

### 7.1 Make source C the primary confirmation

A/B agreement is exploratory. Source C must be selected during the data audit and excluded from:

- item construction;
- temporal-direction estimation;
- source and era choice;
- dose and hyperparameter selection;
- meaningful-effect and heterogeneity thresholds;
- rescue decisions;
- mechanistic layer selection.

### 7.2 Keep Synthetic Identifiability Calibration mandatory

The weird-generalization replication and data-mediated-transfer literature make a historical null uninterpretable without demonstrated sensitivity. Calibration must use the same base, insertion point, broad-update method, dose scale, scorer, and run infrastructure as the historical pilot.

### 7.3 Treat scale and relative dose as boundaries

The final-window path-dependence result fades as the intervention becomes a smaller fraction of prior training. Weird generalization is also scale-dependent. ChronoPersona must report intervention tokens relative to the base checkpoint’s prior token exposure and cannot generalize a 1B null to larger models.

### 7.4 Preserve raw naturalistic documents as the ecological condition

Chat conversion, synthetic transformation, assistant attribution, archive framing, and loss masking can change generalization. Do not transform historical documents into assistant answers for the headline study and then claim an ecological historical-text effect.

### 7.5 Measure post-training response, not only final behavior

For each branch, retain:

\[
B_{\text{after common update}}-B_{\text{before common update}}.
\]

This separates persistent differences, masking, erasure, transformation, and path dependence.

### 7.6 Use measurement robustness as a gate

Similar Models Learn Differently found exploratory value rankings that changed with the scoring method. Primary CSTG outcomes therefore require:

- complete-continuation likelihoods;
- option reversal;
- paraphrase reliability;
- tokenizer diagnostics;
- raw and one prespecified calibrated score;
- capability and malformed-output controls;
- frozen human audit for illustrative generations.

### 7.7 Keep mechanisms downstream of behavior

Mechanistic exploration is blocked until source C confirms the shared component. Layer, rank, probe, and steering choices use development branches only.

## 8. Null-result publication path

A null can be a strong paper only when:

1. explicit and indirect synthetic controls succeed;
2. the shuffled synthetic placebo remains in an equivalence region;
3. the model passes base-task capability gates;
4. naturalistic source A and B interventions are strong enough to change knowledge or register in expected ways;
5. source matching and timestamp audits pass;
6. intervals exclude a preregistered meaningful shared CSTG component;
7. the claim is bounded to the tested model, insertion point, relative dose, eras, sources, and outcomes.

The resulting conclusion would be:

> At the tested scale and dose, historical naturalistic text changes knowledge, register, or source-specific behavior, but does not produce a meaningful source-general temporal behavioral component.

That is more informative than an uncalibrated positive anecdote.

## 9. Final Stage 0 novelty judgment

**Judgment: `novel enough under current redesign`.**

Proceed with the CSTG program. Do not revert to historical-personality construction, one-source historical fine-tuning, broad-transfer novelty, or generic final-window path-dependence claims.

The next literature actions are maintenance tasks rather than blockers:

- rerun the search before preregistration and manuscript submission;
- have a collaborator independently search the nearest work;
- update the matrix when any 2026 paper changes version or releases artifacts;
- inspect citation graphs around Similar Models Learn Differently, Model Spec Midtraining, Time Capsules, and the data-mediated-transfer papers.
