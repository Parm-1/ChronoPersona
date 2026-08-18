# Evaluation Specification

**Version:** development-v0  
**Status:** development; not frozen for confirmatory use  
**Primary instrument:** complete-continuation conditional log likelihood  
**Development registry:** `evaluations/registry/development-v0.jsonl`

## 1. Measurement objective

The evaluation asks whether model branches differ on structured, date-neutral behavior after obvious factual and lexical temporal cues are removed.

It is not intended to measure:

- whether a model knows events from a target period;
- whether prose sounds older or newer;
- whether a model can role-play a date;
- whether one procedural pole is morally correct;
- whether a model represents an average person from an era.

The two primary development domains are:

1. **Evidence integration** — reliability-sensitive updating, order effects, underdetermination, retraction, and persistence.
2. **Procedural trade-offs** — distributed verification, safeguards, privacy, reversibility, expert checking, and rehabilitation.

Secure-system decisions remain a secondary future domain and are not included in development-v0.

## 2. Item structure

Each JSONL line is one item conforming structurally to:

`evaluations/schema/item-v1.schema.json`

The dependency-light Python validator in `chronopersona.evaluation` is authoritative for cross-field and project-specific rules that JSON Schema cannot express conveniently.

Each item contains:

- an immutable item identifier;
- development/frozen/retired status;
- domain and construct;
- a rationale;
- two semantically named poles;
- one reference pole that defines score direction only;
- at least two paraphrase forms;
- two complete natural-language continuations per form;
- expected option-order and paraphrase invariances;
- forbidden cue categories;
- temporal-cue, wording, direct-exposure, and contamination reviews.

A reference pole is not a preferred or correct answer. It establishes a stable sign convention so effect vectors can be compared across branches and sources.

## 3. Current development registry

Development-v0 contains twelve items and twenty-four forms:

### Evidence integration

- demonstrated track record versus formal office;
- cumulative evidence versus the latest report;
- preserved uncertainty versus forced commitment;
- revision after evidence invalidation;
- reliability-weighted testimony versus equal counting;
- persistence of a supported update after unrelated material.

### Procedural trade-offs

- distributed verification versus central authority;
- procedural safeguards versus speed;
- local privacy versus collective anomaly detection;
- reversible pilot versus immediate full commitment;
- independent checking versus expert deference;
- rehabilitation versus punitive exclusion.

The alternatives are intentionally not arranged so that one temporal period is assumed more rational, moral, liberal, safe, or sophisticated.

The registry has passed an internal first-pass temporal-cue and political/moral wording review. Direct-exposure and contamination reviews remain pending because they require the final adaptation source manifests and selected model artifacts. The validator prohibits an item from moving to `frozen` while any required review remains unresolved.

## 4. Primary score

For prompt \(x\) and candidate continuation \(y = (y_1,\ldots,y_T)\), the complete-continuation log likelihood is:

\[
L(y\mid x)
=
\sum_{t=1}^{T}
\log p(y_t\mid x,y_{<t}).
\]

For an item whose frozen reference pole is \(a\) and comparison pole is \(b\), the primary form-level margin is:

\[
m = L(y_a\mid x)-L(y_b\mid x).
\]

The normalized reference-pole probability is:

\[
p_a = \frac{e^{L(y_a\mid x)}}{e^{L(y_a\mid x)}+e^{L(y_b\mid x)}}
=\sigma(m).
\]

The implementation uses a numerically stable logistic transform.

### Why total log likelihood is primary

The candidates are written to have matched structure and approximately matched length. Total log likelihood measures the probability assigned to the complete proposed action, not the average ease of predicting each token.

Mean token log likelihood is retained as a diagnostic:

\[
\bar{L}(y\mid x)=\frac{L(y\mid x)}{T}.
\]

It cannot silently replace the primary metric. A discrepancy between total and mean margins is a length/tokenization warning requiring review.

## 5. Option-order invariance

Candidate display order is counterbalanced across paraphrases. The registry validator requires both pole orders and balances their counts within one form whenever `option-order` invariance is declared. Scoring is normalized by semantic pole identifier, not list position or label letter.

For each form, the output preserves:

- original candidate display order;
- candidate pole identifiers;
- continuation token identifiers;
- token-level log probabilities;
- total and mean log likelihood;
- pole-normalized margin and probability.

Reversing candidate order without changing text must produce an identical pole-normalized score. This property is covered by unit tests.

## 6. Paraphrase handling

Forms are repeated measurements of one item, not independent model replications.

Development-v0 aggregates forms using:

- mean total-log-likelihood margin;
- mean mean-token margin as a diagnostic;
- standard deviation across form margins;
- directional agreement across forms;
- normalized probability from the mean primary margin.

Items with poor paraphrase agreement are revised or removed before freezing. Repeated forms, samples, and item variants do not increase the number of independently trained model branches in statistical inference.

## 7. Exact continuation boundaries

Tokenizers can merge text across the prompt/continuation boundary. ChronoPersona therefore does not score separately tokenized answer strings and assume that their tokens match the suffix of the combined sequence.

`chronopersona.tokenization.prepare_continuation`:

1. requires the prompt to have no leading or trailing whitespace;
2. requires each continuation to begin with whitespace and end without it;
3. tokenizes the prompt and `prompt + continuation` without automatic special tokens;
4. requires the prompt token sequence to be an exact prefix of the full sequence;
5. allows a model adapter to prepend a frozen explicit BOS/prefix token sequence;
6. records the exact logit positions for continuation tokens;
7. fails closed if the full sequence exceeds the frozen maximum length.

A tokenizer-specific adapter may be introduced only when the generic exact-prefix rule is demonstrably inappropriate. The adapter, tokenizer revision, and tests then become part of the frozen scorer identity.

## 8. Truncation and malformed evidence

The primary scorer rejects:

- empty prompt tokenization;
- empty continuation tokenization;
- non-exact boundaries;
- truncation;
- mismatched token and log-probability counts;
- non-finite log probabilities;
- duplicate or missing poles;
- model or tokenizer identity omissions.

Failures remain visible in the run registry. They are not converted to neutral scores or removed silently.

## 9. Calibrated alternative

The code supports one prespecified calibrated margin:

\[
m_{\mathrm{cal}}=m_{\mathrm{observed}}-m_{\mathrm{baseline}}.
\]

The calibration prompt, candidate form, tokenizer handling, and aggregation are not yet frozen. They must be selected on development models and simulations before confirmatory outputs exist.

Calibration cannot be chosen after observing which method strengthens the temporal result. Raw total-log-likelihood margins remain mandatory in every report.

## 10. Immutable output

`score_evaluation_registry` produces deterministic output containing:

- scorer version and metric identities;
- exact evaluation-registry SHA-256;
- model, model revision, and tokenizer identities;
- every item/form/candidate token-level score;
- pole-normalized margins;
- paraphrase aggregates;
- a canonical output hash.

Wall-clock and hardware metadata are deliberately kept in the separate run record so identical scientific inputs can produce byte-identical score artifacts.

Generated explanations are not used to calculate the primary outcome.

## 11. Item development process

Before an item becomes frozen:

1. define the construct independently of an expected temporal direction;
2. write at least two semantically matched forms;
3. counterbalance candidate display order;
4. inspect candidate word and tokenizer lengths;
5. run exact-boundary checks on every selected tokenizer;
6. run temporal-cue review;
7. run political and moral wording review;
8. search final adaptation manifests for direct procedural exposure;
9. run exact, near-duplicate, and semantic contamination searches;
10. test option-order and paraphrase reliability on development checkpoints;
11. revise or reject unstable items;
12. freeze the registry file, score direction, calibration, exclusions, and hash.

The current twelve items are a development seed set. They are not evidence-bearing and are too small for the final confirmatory instrument.

## 12. Required development analyses

Before expansion or freezing, report:

- token counts by candidate, form, tokenizer, and model family;
- rate of boundary mismatch and truncation;
- option-order invariance;
- paraphrase correlation and directional agreement;
- item-total and split-half reliability;
- raw versus calibrated score stability;
- base versus instruction variant differences;
- capability, language-model-loss, refusal, and malformed-output diagnostics;
- lexical/register classifier sensitivity;
- item ceiling and floor effects;
- human audit of any central open-ended illustration.

## 13. Freeze gate

The registry may advance from `development` to a versioned frozen registry only when:

- both primary domains show acceptable reliability;
- all required reviews pass;
- all executed tokenizers pass exact-boundary checks or have reviewed adapters;
- option-order effects are negligible under a frozen threshold;
- paraphrase reliability passes a frozen threshold;
- candidate token-length differences are bounded;
- no direct training exposure or unresolved contamination remains;
- the meaningful-effect threshold and null-equivalence interval are specified;
- primary and secondary composites are fixed;
- missing-output and exclusion rules are fixed;
- the registry SHA-256 is recorded before confirmatory model outputs.

Changes after freezing create a new registry version. They never overwrite a completed experiment's input.

## 14. Known limitations of development-v0

- Several evidence-integration items have an epistemically stronger alternative and may exhibit capability ceilings.
- The current procedural set does not yet cover dissent tolerance or transparency versus operational secrecy.
- Only two paraphrases per item are included.
- No tokenizer audit has run on DatedGPT, OLMo, or Pythia.
- No public-checkpoint score has been generated.
- Direct-exposure and contamination reviews are pending.
- Human criterion validity has not been established.
- The calibrated alternative is implemented but not designed or frozen.

These are explicit next tasks, not details to conceal in a final appendix.

## 15. Immediate next evaluation work

After this scaffold is validated:

1. add a model-specific Transformers provider using only manifest-approved artifacts;
2. run tokenizer-only boundary audits before loading model weights;
3. use the immutable Pythia loading benchmark to exercise the scorer;
4. measure reliability on the twelve development items;
5. revise ceiling-prone or wording-sensitive items;
6. add dissent and transparency constructs;
7. expand toward 24–40 development items per primary domain only if the small set behaves coherently;
8. keep the final confirmatory registry frozen and separate from development outputs.
