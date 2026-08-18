# Charter Module 02 — Measurement and Synthetic Identifiability

## Measurement philosophy

The primary outcome is a model-level behavioral fingerprint, not a human personality score or historical-population proxy.

Use structured, date-neutral tasks with fictional entities, no recognizable events, no explicit years, no copied survey items, and no obviously approved answer.

Primary domains:

1. **Evidence integration** — factorial variation in priors, source track record, authority, directness, consistency, order, independent-source count, coordinated error, asymmetric error costs, and underdetermination.
2. **Procedural decision policy** — mirrored fictional organizations varying authority versus verification, speed versus safeguards, reversibility versus commitment, privacy versus detection, transparency versus secrecy, punishment versus repair, redundancy versus efficiency, and optimization versus resilience.

Secondary far-transfer domain:

3. **Secure-system decisions** — structured choices about canonicalization, parameterized queries, least privilege, fail-open/fail-closed behavior, cryptographic defaults, dependency verification, update validation, authentication boundaries, and recovery. Executable code requires a frozen functional-capability gate and sandbox.

## Development and confirmation separation

Maintain two independent partitions:

- **Development:** scorer debugging, reliability, A/B discovery, capability checks, and statistical-code validation.
- **Confirmation:** sealed until all source-C branches are complete, manifests pass, failed branches are dispositioned under frozen rules, and analysis is ready to unseal.

A/B and C are evaluated on the confirmation partition in one locked pipeline. Confirmation items may not be tuned using A/B result summaries.

## Scoring

For base models, primary scoring uses complete-continuation conditional likelihoods:

`Y = log P(a1 | x) - log P(a2 | x)`

For every item:

- score complete natural-language candidates;
- normalize over the candidate set;
- reverse candidate order;
- rotate arbitrary labels;
- use meaning-preserving paraphrases;
- inspect token boundaries;
- control candidate length;
- preserve token-level diagnostics;
- detect truncation and missing logits;
- report raw and one prespecified calibrated variant.

Generated explanations are illustrative only. They do not determine the primary result.

Required measurement controls include option order, label, paraphrase, prompt template, split-half and item-family reliability, tokenizer diagnostics, lexical-era classification, factual-cutoff probes, language-model loss, timeless reasoning, malformed output, refusal, and output length.

## Evaluation freeze gate

Before evidence-bearing calibration or naturalistic confirmation:

- complete construct review;
- complete temporal-cue review;
- complete political/moral wording review;
- complete scorer and tokenizer review;
- complete source-domain exposure review;
- freeze development and confirmation manifests;
- freeze direction, composites, missing-output rules, and meaningful-effect thresholds;
- hash all artifacts.

Approximately twelve current development items are engineering fixtures, not a frozen scientific instrument.

## Synthetic Identifiability Calibration

A naturalistic null is interpretable only if the system can recover a known source-general latent factor.

Construct at least two morally symmetric procedural contrasts. Express each through two disjoint synthetic training domains, and evaluate it in a third unseen domain with no shared entities or signature phrases.

Required conditions:

- explicit positive controls;
- indirect latent policy A and B;
- cross-domain replication;
- shuffled-policy placebo;
- generic neutral continuation;
- prespecified dose curve;
- optional blinded low-dose signal in naturalistic background.

The decisive calibration must use the same base checkpoint, insertion point, objective, broad-update method, scorer, run identity, and comparable exposure policy intended for the naturalistic experiment. PEFT may debug the pipeline but cannot silently substitute for the headline method.

Calibration passes only when:

- explicit controls are learned;
- indirect rules transfer from both synthetic domains into the unseen domain;
- domain effect vectors agree;
- placebo and generic continuation remain within frozen null regions;
- dose response follows its prespecified form;
- capability remains within tolerance;
- effects replicate across independent branches.

Allow one predefined rescue: greater dose, larger model, or correction of a verified implementation defect. A second failure blocks naturalistic causal interpretation.