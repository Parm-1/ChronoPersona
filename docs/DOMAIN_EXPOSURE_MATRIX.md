# Domain Exposure Matrix

**Date:** 2026-08-17  
**Status:** Stage 0 provisional source audit  
**Primary rule:** A headline CSTG task family may not be directly taught by any included source branch.

## Exposure levels

### Direct

The source contains the same decision type, explicit procedural rule, benchmark template, answer rationale, or close paraphrase that the evaluation uses.

Examples:

- text explaining when to trust reliable evidence over authority;
- rules requiring independent verification before irreversible action;
- direct privacy-versus-detection policies;
- punishment-versus-rehabilitation guidance;
- secure-system architecture recommendations.

A direct source/evaluation pair cannot support a far-transfer claim.

### Structurally related

The source frequently contains the same abstract structure but not the evaluation template or explicit target rule.

Examples:

- scientific arguments that compare evidence quality;
- community answers that justify procedures;
- postmortems that discuss verification and failure;
- institutional descriptions involving review and accountability.

Structurally related exposure is not automatically disqualifying, but it requires topic filters, manual review, and sensitivity analysis.

### Indirect

The source can contain relevant ordinary language or isolated examples, but the procedural construct is not a central or recurrent teaching target after frozen filters.

### Plausibly absent

A documented source stratum and filter make meaningful exposure unlikely, subject to contamination search and manual audit.

### Unknown

The source has not been sampled or classified enough to assign another level.

## Source-level provisional matrix

| Source | Evidence integration | Procedural trade-offs | Secure-system decisions | Headline role |
|---|---|---|---|---|
| Wikimedia article additions | Indirect after explicit topic/namespace/template filters | Indirect after institutional/policy filters | Direct in technical/security strata; exclude | Exploratory A |
| Stack Exchange initial nontechnical posts | Structurally related | Structurally related | Direct on technical sites; exclude | Exploratory B |
| arXiv single-version permissive descriptive science | Structurally related | Indirect after category/method filters | Direct in CS/security/engineering strata; exclude | Held-out C |
| PMC permissive version-bounded OA | Structurally related | Indirect after clinical/policy/method filters | Plausibly absent in retained biological description strata | Backup C |
| Federal Register/GovInfo | Structurally related | Direct | Structurally related | Rejected headline source |

These classifications describe the proposed **filtered strata**, not the complete parent archives.

## Evaluation-construct matrix

| Construct | Wikimedia A | Stack Exchange B | arXiv C | PMC backup C | Federal Register |
|---|---|---|---|---|---|
| Reliability-sensitive authority weighting | Indirect; exclude institutions, governance, and dispute pages | Structurally related; exclude advice, skeptics, law, workplace, and expert-adjudication topics | Structurally related; exclude methods, review, epistemology, and decision papers | Structurally related; exclude evidence grading, clinical guidelines, and methods | Direct/structurally related |
| Evidence-order sensitivity | Indirect | Structurally related in troubleshooting/advice; filter | Structurally related in methods/results; filter | Structurally related in methods/results; filter | Structurally related |
| Underdetermination and calibrated uncertainty | Indirect | Structurally related in advice and troubleshooting | Structurally related or direct in inference/methodology; exclude | Structurally related or direct in diagnostic/methodological text; exclude | Indirect |
| Revision after evidence invalidation | Indirect | Structurally related in corrections/troubleshooting | Structurally related in retractions/methods; exclude direct examples | Structurally related in corrections and clinical evidence; exclude | Structurally related |
| Source-reliability discrimination | Indirect | Structurally related; exclude skepticism/evidence sites | Structurally related; exclude methodology and review | Structurally related; exclude evidence-quality text | Structurally related |
| Persistence of supported update | Plausibly absent after filters | Indirect | Indirect | Indirect | Indirect |
| Central authority versus distributed verification | Indirect after government/institutional filters | Structurally related in community governance and workplace advice; exclude | Indirect after systems/governance filters | Indirect after clinical governance filters | Direct |
| Speed versus procedural safeguards | Indirect after accident/policy filters | Structurally related in practical advice; exclude direct safety/process posts | Indirect after engineering/method filters | Structurally related in clinical processes; exclude | Direct |
| Privacy versus collective detection | Direct in privacy/surveillance/public-health pages; exclude | Structurally related or direct on many sites; exclude privacy/health/IT topics | Direct in privacy/security/public-health research; exclude | Direct in public health, records, and surveillance; exclude | Direct |
| Reversible pilot versus full commitment | Indirect | Structurally related in project/advice posts | Structurally related in experimental design; exclude direct decision text | Structurally related in trials/interventions; exclude | Structurally related |
| Expert deference versus independent checking | Indirect after institutional/dispute filters | Structurally related; exclude expert-advice and skeptics strata | Structurally related/direct in review and methodology; exclude | Structurally related/direct in guidelines and evidence reviews; exclude | Direct/structurally related |
| Punishment versus rehabilitation | Direct in justice/social-policy pages; exclude | Direct on law, parenting, workplace, interpersonal sites; exclude | Indirect after social-science exclusion | Indirect after behavioral/clinical/social exclusion | Direct |
| Dissent tolerance | Direct in politics/history/institutional pages; exclude | Direct on workplace/politics/community-governance sites; exclude | Indirect after social-science/governance exclusion | Indirect after behavioral/organizational exclusion | Direct |
| Transparency versus operational secrecy | Direct in government/security/institutional pages; exclude | Structurally related/direct on workplace/security sites; exclude | Direct in security/governance; exclude | Indirect after policy/records exclusion | Direct |

## Frozen exclusion families

The final source filters must exclude, at minimum, records whose central content belongs to the following families.

### Evidence integration exclusions

- Bayesian, probabilistic, or calibration tutorials;
- source reliability, media literacy, misinformation, fact checking, or skepticism instruction;
- peer-review and evidence-grading guidance;
- diagnostic reasoning and clinical evidence hierarchy;
- survey design, psychometrics, causal inference, and decision theory;
- benchmark, exam, or puzzle formats closely resembling evaluation items;
- explicit authority-versus-track-record disputes;
- retraction, invalid-measurement, or evidence-order teaching examples close to the registry.

### Procedural trade-off exclusions

- governance and institutional design;
- administrative procedure and regulation;
- privacy, surveillance, records, and collective monitoring;
- policing, punishment, rehabilitation, justice, and discipline;
- workplace, parenting, interpersonal, or community advice;
- safety-case, change-control, release-approval, and verification procedures;
- expert review, replication, and independent-audit requirements;
- transparency, secrecy, dissent, whistleblowing, and public-participation policy;
- irreversible intervention and staged-pilot decision guidance.

### Secure-system exclusions

- source code;
- software engineering and system architecture;
- cybersecurity, vulnerabilities, cryptography, and incident response;
- secure coding and threat modeling;
- benchmark solutions;
- network, authentication, privacy-preserving computation, and access-control tutorials.

## Filtering architecture

No single keyword list can establish absence. The required pipeline is layered.

### Layer 1 — source-native strata

- namespaces, sites, categories, journals, or subject classifications;
- frozen before behavioral outcomes;
- historically valid where possible.

### Layer 2 — deterministic lexical and metadata exclusions

- explicit terms, tags, categories, and document types;
- versioned and reviewed;
- used for high-recall removal, not final eligibility.

### Layer 3 — frozen direct-exposure classifier

A classifier trained on:

- evaluation construct descriptions;
- positive direct-exposure examples;
- structurally related examples;
- clearly absent examples.

The classifier must be trained and frozen without source-C behavioral outputs. Its purpose is to identify likely direct teaching, not infer the desired temporal direction.

### Layer 4 — similarity search

Search against:

- every evaluation prompt;
- every candidate continuation;
- construct cards;
- synthetic-calibration text;
- development and confirmatory templates.

Use exact, n-gram, near-duplicate, and semantic similarity.

### Layer 5 — stratified manual audit

Review samples from:

- retained low-risk records;
- records near the classifier threshold;
- every excluded direct-exposure family;
- every source/window/domain stratum;
- records with high event/entity concentration.

The reviewer records direct, structurally related, indirect, absent, or unresolved. Unresolved records are ineligible for confirmatory branches.

## Exposure metrics

For every source/window manifest report:

- raw and retained document/token counts;
- counts removed by each exclusion layer;
- classifier score distribution;
- direct/structural/indirect/manual labels;
- threshold false-positive and false-negative estimates;
- exact/semantic overlap with evaluation and calibration;
- topic and source-stratum distributions before and after filtering;
- sensitivity to stricter and looser thresholds.

A low classifier score is not proof of absence.

## Source-C firewall

The source-C direct-exposure classifier and thresholds must be frozen using:

- source A and B development records;
- synthetic direct-exposure fixtures;
- source documentation;
- non-C validation sources.

Permitted C inspection before confirmation:

- aggregate score distributions;
- blinded manual exposure labels;
- parser and rights failures;
- counts and balance diagnostics.

Prohibited:

- changing the classifier because C contains inconvenient content;
- examining C behavioral outputs;
- using C examples to rewrite evaluation items;
- choosing C categories based on temporal effect direction.

## Decision rules

### Eligible for primary CSTG

A source/evaluation domain pair may enter the primary analysis only when:

- no known direct exposure remains;
- the estimated direct-exposure rate is below a frozen tolerance;
- structurally related exposure is measured and included in sensitivity analysis;
- retained content remains sufficient and balanced across eras;
- source-specific effects do not simply track exposure intensity.

### Secondary only

A domain becomes secondary when:

- meaningful structurally related exposure is unavoidable;
- direct exposure can be bounded but not made negligible;
- the construct remains useful as a stress test rather than far transfer.

### Excluded

Exclude a source/domain pair when:

- direct teaching is common;
- filtering removes most of one era or source;
- exposure differs materially across eras and cannot be matched;
- manual false-negative rates exceed tolerance;
- the source's identity is inseparable from the construct.

## Current implication

The current development evaluation cannot be frozen before source samples exist. The source audit may force revision of constructs, especially:

- source reliability;
- independent checking;
- privacy;
- punishment and rehabilitation;
- transparency and dissent.

This is a valid redesign outcome. Evaluation convenience does not override domain-exposure validity.
