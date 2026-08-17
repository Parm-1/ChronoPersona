# Synthetic Identifiability Calibration Corpus v0

**Status:** development, reproducible, not frozen  
**Training authorized:** no  
**Model or network required to build:** no

## Purpose

A naturalistic null is uninterpretable unless the selected model, insertion
point, training method, dose, scorer, and evaluation can recover a known
cross-domain signal. This package creates that known signal without claiming
that historical archives contain an analogous latent policy.

The package includes two morally symmetric procedural contrasts:

1. independent verification versus accountable delegation;
2. reversible staging versus decisive commitment.

Each contrast appears in two disjoint training domains and is evaluated in a
third unseen domain. Neither pole is treated as universally correct.

## Conditions

For each policy pair and each training domain, v0 creates 16 documents in each
of six conditions:

- `explicit-a` and `explicit-b`: the rule is stated directly and demonstrated;
- `indirect-a` and `indirect-b`: the rule is expressed only through repeated
  decisions and outcomes;
- `shuffled-placebo`: policy, option order, and outcome are exactly
  counterbalanced so no coherent rule exists;
- `generic-neutral`: matched routine reports with no selected policy pole.

The unadapted base model is a model-level diagnostic and is not represented by
a corpus file.

## Physical separation of model input and experiment metadata

The most important engineering boundary is physical, not merely documentary:

- generated `documents.jsonl` contains only `schema_version`, `document_id`,
  and model-visible `text`;
- generated `metadata.jsonl` contains condition, pole, outcome, order, hashes,
  and balance metadata, but no text;
- every dose branch names `documents.jsonl` as model input and explicitly
  prohibits metadata serialization.

A training path that reads metadata fields is invalid even when the generated
prose is otherwise correct.

## Provenance

Every sentence is deterministic composition from human-authored, committed
templates. No teacher model, stochastic generator, external corpus, or model
output is used. This prevents synthetic-teacher identity from becoming an
unrecorded causal variable.

## Balance gates

The generator fails closed unless it establishes:

- exact document counts;
- equal paired word totals;
- at most 3% paired character-count difference;
- exact 12/4 success/failure schedules;
- exact first/second option-order balance;
- exact option-order/outcome independence;
- exact placebo pole/outcome independence;
- exact neutral absence of a selected pole;
- matched sentiment-lexicon counts;
- indirect vocabulary Jaccard of at least 0.98;
- indirect maximum unigram-frequency difference no greater than 0.005;
- no training/held-out entity overlap;
- no direct-rule leakage into indirect or placebo text;
- no evaluation candidate copied into training;
- no shared ten-word n-gram between training and evaluation;
- no temporal cues, unresolved placeholders, duplicated prompts, or duplicated
  evaluation candidates.

These are necessary internal checks, not construct-validity proof.

## Dose plan

The low, medium, and full subsets are nested at 4, 8, and 16 documents per
training domain. All `target_tokens` remain zero and all token budgets remain
`unfrozen`. Document dose is available for pipeline testing, but token dose
cannot be frozen until a real tokenizer and measured training throughput exist.

## Primary analysis architecture

The package records but does not numerically freeze:

- explicit A minus explicit B as the positive control;
- indirect A minus indirect B as the primary transfer contrast;
- shuffled placebo minus generic neutral as the placebo contrast;
- an ordered low/medium/full dose-response contrast.

The independently trained branch seed is the experimental unit. Evaluation
items and paraphrases are nested measurements. Absolute base-model preference
is diagnostic and cannot replace branch-to-branch causal contrasts.

## Build and verify

```bash
python scripts/build_synthetic_calibration.py --check
python scripts/build_synthetic_calibration.py \
  --output-root artifacts/local/synthetic-calibration-v0
python -m chronopersona validate-evaluation \
  artifacts/local/synthetic-calibration-v0/evaluations/registry/synthetic-calibration-v0.jsonl
pytest tests/test_synthetic_calibration.py
```

`--check` regenerates the complete package in memory and compares all generated
file hashes and byte counts with
`calibration/synthetic-v0/expected-hashes.json`. The large model-visible and
metadata files are generated into ignored local artifacts rather than committed.

## Remaining freeze blockers

Before an evidence-bearing calibration run:

- audit the registry with the selected tokenizer and prefix policy;
- demonstrate base-model capability on the held-out tasks;
- measure memory and throughput;
- freeze the model, insertion point, training method, token doses, seed count,
  meaningful-effect threshold, placebo equivalence region, capability
  tolerance, multiplicity rule, and one rescue action;
- obtain separate construct, wording, scorer, and statistical reviews;
- test whether template regularity rather than the latent policy explains
  transfer.

No positive historical or behavioral claim follows from generating this
package.
