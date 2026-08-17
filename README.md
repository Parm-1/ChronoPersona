# ChronoPersona

ChronoPersona is an empirical research project about **temporal adaptation in language models**.

The central question is not whether a model can role-play a year when prompted. It is whether adapting the same base model to carefully matched information environments from different historical periods produces measurable changes in its world model, uncertainty, priorities, social assumptions, and decision patterns—even when prompts contain no dates or obvious historical clues.

## Research question

> Holding model architecture, optimization, instruction tuning, token budget, and evaluation prompts constant, what changes are caused by the temporal distribution of the adaptation corpus?

The project separates three effects that are often conflated:

1. **Temporal knowledge** — what events, technologies, people, and concepts the model can know.
2. **Temporal style** — era-linked language, references, and surface conventions.
3. **Temporal disposition** — differences in judgments, expectations, trust, risk tolerance, institutional assumptions, and other behavioral tendencies on date-neutral tasks.

The third category is the main scientific target. The first two are necessary controls rather than sufficient evidence.

## What this project will not claim

ChronoPersona does not create a person literally transported from the past, recover the beliefs of an entire historical population, or prove that a language model has a stable human-like personality. A model adapted to an older corpus remains a modern model shaped by its original pretraining, tokenizer, architecture, filtering, and training process.

The defensible claim is narrower: **changing the temporal information environment may causally shift model behavior under controlled conditions**.

## Core experimental design

The intended full study uses several temporal slices, initially framed around 1999, 2008, 2016, and 2024. Every condition should use:

- the same base checkpoint;
- matched token budgets and training schedules;
- balanced source domains and quality filters;
- documented timestamps, licensing, provenance, and deduplication;
- a common post-adaptation instruction-tuning procedure, when instruction tuning is used;
- blinded, versioned evaluation prompts;
- multiple random seeds;
- controls for explicit year prompting, shuffled dates, factual leakage, style, and corpus composition.

The repository begins with a cheaper two-slice smoke pilot plus controls. The four-period study is gated on the pilot demonstrating that the data and evaluation pipeline can support credible causal inference.

## Current status

**Phase 0: research design and executable scaffold.**

No empirical result is claimed yet. The current goal is to freeze the key definitions, qualify data sources, build reproducible manifests, and run the smallest experiment capable of falsifying the idea.

## Repository map

- [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md) — hypotheses, causal design, confounds, analysis, and staged roadmap.
- [`docs/PILOT_PROTOCOL.md`](docs/PILOT_PROTOCOL.md) — smallest serious pilot and go/no-go gates.
- [`docs/DATA_POLICY.md`](docs/DATA_POLICY.md) — provenance, licensing, timestamp, deduplication, and leakage requirements.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — durable design decisions and their rationale.
- [`configs/pilot.toml`](configs/pilot.toml) — machine-readable pilot specification.
- [`src/chronopersona`](src/chronopersona) — configuration validation and, later, experiment orchestration.
- [`AGENTS.md`](AGENTS.md) — operating rules for Codex and other coding agents working in this repository.

## First executable check

ChronoPersona currently provides a dependency-light validator for experiment specifications.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m chronopersona validate configs/pilot.toml
pytest
```

The validator catches structural errors before expensive data or training work begins: duplicate conditions, malformed cutoffs, unequal token budgets, missing controls, and invalid manifest paths.

## Near-term sequence

1. Complete a literature and novelty map.
2. Audit candidate corpora for timestamp semantics, licensing, source balance, and future leakage.
3. Freeze an evaluation registry before training results are inspected.
4. Build deterministic data manifests and contamination checks.
5. Run a low-cost smoke adaptation on a small base model.
6. Decide whether evidence justifies scaling to more periods, seeds, and model sizes.

## Research discipline

All meaningful runs must be reproducible from a committed configuration, immutable input manifests, code revision, environment lock, seed set, and artifact manifest. Negative results are first-class outcomes. Evaluation changes made after results are visible must create a new registered experiment version rather than silently replacing the original test.

Dataset text and model artifacts are not committed by default. Only redistributable material with clear provenance and licensing may be published.

## License

No open-source license has been selected yet. Until one is added, the repository remains all-rights-reserved despite being accessible to collaborators.