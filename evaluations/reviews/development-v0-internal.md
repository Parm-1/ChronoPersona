# Development-v0 Internal Evaluation Review

**Date:** 2026-08-17  
**Registry:** `evaluations/registry/development-v0.jsonl`  
**Review type:** internal design review; not independent peer review  
**Decision:** retain as a development seed set; do not freeze

## Review method

The twelve items were reviewed separately for:

1. temporal cues;
2. political and moral directionality;
3. option-order balance;
4. paraphrase equivalence;
5. candidate structural matching;
6. likely capability ceilings;
7. direct adaptation exposure;
8. contamination readiness.

The dependency-light validator additionally checks identifiers, required domains, semantic pole coverage, option-order/paraphrase invariances, explicit years and period terms, candidate leading-space boundaries, and coarse word-count imbalance.

Direct-exposure and contamination reviews cannot be completed until source manifests and model artifacts are selected. They remain explicitly pending in every item record.

## Findings

### F-01 — No explicit temporal cue found

**Severity:** pass  
**Evidence:** No item contains a date, real event, named political group, period label, or inspected temporal keyword in its prompt or candidates. Organizations and locations are fictional or generic.  
**Disposition:** retain. Repeat the review after every wording change and run a lexical classifier before freezing.

### F-02 — Candidate display order is counterbalanced

**Severity:** pass  
**Evidence:** Each item has two forms and reverses the candidate display order between forms. Scoring normalizes by semantic pole rather than list position.  
**Disposition:** retain. Model-level option-order invariance remains untested.

### F-03 — Paraphrases preserve broad constructs but are not proven equivalent

**Severity:** medium  
**Evidence:** Each item uses a second fictional domain and re-expresses the same procedural contrast. Some forms alter stakes or institutional context in addition to wording.  
**Disposition:** retain for development only. Measure form-level correlation and directional agreement; revise or split items with unstable forms.

### F-04 — Evidence-integration items may have capability ceilings

**Severity:** high  
**Evidence:** Track-record weighting, invalid-evidence retraction, and calibrated-sensor integration contain an epistemically stronger answer. Capable base models may assign nearly all probability to the same pole, leaving little room for a temporal contrast.  
**Disposition:** retain as capability and sensitivity anchors, not necessarily as final primary items. Add more ambiguous reliability trade-offs and item-response diagnostics before expansion.

### F-05 — Procedural alternatives are directionally neutral at the label level

**Severity:** pass with caveat  
**Evidence:** Reference poles define sign only. No item states that distributed, private, reversible, independent, or rehabilitative procedures are morally superior.  
**Disposition:** retain as development items. Do not interpret aggregate sign as moral progress.

### F-06 — Several procedural scenarios have asymmetric consequences

**Severity:** medium  
**Evidence:** The safeguards items describe potentially system-wide hidden defects; privacy items describe personal exposure; punishment items describe admitted non-malicious violations without harm. These details can make one pole easier to endorse independent of the intended construct.  
**Disposition:** retain for initial scorer testing. Add counterfactual stake variants in which costs favor the opposite pole, and estimate sensitivity to consequence framing.

### F-07 — Privacy item carries domain-specific moral salience

**Severity:** medium  
**Evidence:** Patient and worker records invoke familiar privacy norms. This may measure domain convention more than a general privacy-versus-detection policy.  
**Disposition:** add a non-human operational-information variant before freezing and test whether the pole margin transfers across domains.

### F-08 — Punishment item risks valence imbalance

**Severity:** medium-high  
**Evidence:** “Punitive exclusion” is paired with admitted, non-malicious, no-harm violations, while rehabilitation language emphasizes rebuilding trust. The item may partly measure wording valence.  
**Disposition:** do not freeze in current form. Add matched deterrence benefits, repeated-offense variants, and less valenced pole labels; require wording review after revision.

### F-09 — Dissent and transparency constructs are absent

**Severity:** medium  
**Evidence:** The charter identifies tolerance of dissent and transparency versus operational secrecy, but development-v0 does not represent them.  
**Disposition:** add them in the next development batch rather than expanding the current registry indiscriminately.

### F-10 — Tokenizer matching is unresolved

**Severity:** high, blocked  
**Evidence:** Candidate word counts are coarsely matched, but DatedGPT, OLMo, and Pythia tokenizers have not been run. Boundary merges, token-count differences, and truncation remain unknown.  
**Disposition:** every selected tokenizer must pass `prepare_continuation`; record candidate token lengths and reject or rewrite boundary-unstable forms.

### F-11 — Direct exposure is unresolved

**Severity:** high, blocked  
**Evidence:** No final adaptation sources or domain-exposure matrix exist. Technical, institutional, medical, or procedural source text could teach these exact choices.  
**Disposition:** keep `direct-exposure` review pending. Search final manifests and reject primary items directly represented in any source branch.

### F-12 — Contamination is unresolved

**Severity:** high, blocked  
**Evidence:** Exact model revisions and source corpora are not yet locally materialized, so exact, near-duplicate, and semantic searches have not run.  
**Disposition:** keep `contamination` review pending. No item may move to frozen status before the searches and manual review complete.

### F-13 — Generated explanations are unnecessary for primary scoring

**Severity:** pass  
**Evidence:** Every item is expressible as two complete continuations, and the scorer retains token-level likelihood evidence.  
**Disposition:** primary outcomes remain likelihood-based. Open explanations may be generated later for blinded illustration only.

### F-14 — Development set is too small for confirmatory reliability

**Severity:** high  
**Evidence:** Six items per primary domain and two forms per item cannot support the intended final construct breadth or stable hierarchical inference.  
**Disposition:** use the set to debug tokenization, score stability, and ceiling effects. Expand only after these twelve produce interpretable development diagnostics.

## Manager disposition

The registry is accepted as **development-v0** and rejected for freezing.

The next evaluation gate is not “write more questions.” It is:

1. implement a manifest-approved model provider;
2. run tokenizer-only audits;
3. score development-v0 on at least one immutable base model;
4. identify ceiling, order, boundary, and paraphrase failures;
5. revise the item architecture from observed diagnostics;
6. then add dissent, transparency, counterfactual stakes, and broader domain variants.

No scientific conclusion may cite development-v0 scores.
