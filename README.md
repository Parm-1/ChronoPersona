# ChronoPersona

**ChronoPersona** is the internal codename for a falsification-oriented research program on temporal training effects in language models.

Its scientific construct is **Cross-Source Temporal Generalization (CSTG)**.

## Central question

> When identical models are exposed to matched naturalistic corpora from different periods, does the historical period induce a shared component of date-neutral behavior that independently reappears across unrelated source families, predicts a held-out source, and changes how the model responds to identical later post-training?

This is not a project about interviewing “a 2013 personality.” Public historical and point-in-time checkpoints are useful observational infrastructure, but constructing dated models is not the core contribution.

A **temporal prior** may be discussed only after a stronger result has been established: replicated CSTG that survives source, topic, register, knowledge, capability, training-dose, insertion-position, and post-training controls.

## Why cross-source replication matters

A behavioral difference learned from one historical corpus can reflect that corpus's website, institution, genre, community, topic distribution, or formatting conventions. ChronoPersona therefore estimates the early-versus-late contrast separately for independent source families.

For source family \(s\), evaluation domain \(d\), and seed \(r\), let:

\[
B_d(M_{e,s,r})
\]

be the frozen behavioral vector of a model adapted to era \(e\). Define:

\[
\tau_{s,d}
=
\mathbb{E}_r
\left[
B_d(M_{\mathrm{late},s,r})
-
B_d(M_{\mathrm{early},s,r})
\right].
\]

The central result is not that one \(\tau_{s,d}\) differs from zero. Evidence for CSTG requires a reproducible shared component across sources A and B and successful prediction on source C, which is held out from hypothesis construction and tuning.

## Mandatory sensitivity calibration

A historical null can mean either “no effect” or “the experiment could not detect one.” Before naturalistic results are interpreted, the project runs a **Synthetic Identifiability Calibration** using morally symmetric fictional environments:

- an explicit positive control;
- an indirectly expressed cross-domain latent rule;
- a shuffled placebo;
- a neutral continuation control;
- several signal doses;
- multiple seeds;
- the same base checkpoint, training method, token budget, and scorer intended for the historical experiment.

A naturalistic null is informative only when the calibration succeeds and the confidence interval excludes a preregistered meaningful effect.

## Staged architecture

1. **Stage 0 — Feasibility and novelty.** Verify the literature, public model artifacts, licenses, timestamp semantics, local hardware, storage, training throughput, evaluation validity, and cost.
2. **Stage 1 — Public-checkpoint audit.** Test whether frozen date-neutral measurements detect reproducible temporal trajectories in public point-in-time model families. This stage is observational.
3. **Stage 2 — Synthetic identifiability.** Establish that the chosen model, dose, method, and scorer can recover a known cross-domain signal.
4. **Stage 3 — Naturalistic causal pilot.** Use common starting weights with two provisional eras, two independent source families, and three exploratory seeds.
5. **Stage 4 — Held-out-source and post-training confirmation.** Predict source C, test common neutral buffers, training position, identical modern SFT, and—only if justified—identical preference training.
6. **Stage 5 — Channel attribution.** Compare document, assistant-response, archive-attributed, and synthetic-transformation formats one variable at a time.
7. **Stage 6 — Mechanisms.** Search for a cross-source causal temporal subspace only after behavioral replication.

The provisional naturalistic windows are January 2012–December 2013 and January 2018–December 2019. They are not frozen. Data continuity, timestamps, rights, source matching, and event concentration must determine the final pair before model behavior is inspected.

## Primary outcomes

### Evidence integration

Fictional micro-worlds vary initial priors, source reliability, true and false evidence, underdetermination, authority versus track record, evidence order, and delayed persistence.

Primary measurements include complete-continuation likelihoods, update direction, reliability sensitivity, false-evidence uptake, order effects, persistence, and calibration.

### Procedural trade-offs

Timeless fictional organizations test centralized authority versus distributed verification, safeguards versus speed, privacy versus collective detection, reversible versus irreversible intervention, expert deference versus independent checking, punishment versus rehabilitation, dissent, transparency, and secrecy.

The design does not assume a morally preferred temporal direction.

### Secure-system decisions

Structured architecture choices form a secondary far-transfer domain. Executable code evaluation is gated on frozen functional capability and sandboxing.

## Resource boundary

The project is designed around the user's stated constraints:

- current reported machine: RTX 2060 and 16 GB RAM;
- possible borrowed machine: RTX 5070 and 32 GB RAM, availability not assumed;
- objective: spend as little as possible while preserving paper quality;
- default external-compute authorization: **CAD $0**;
- no compute rental, hardware purchase, paid license, or large branch set without explicit approval;
- one training job at a time;
- measured memory, throughput, storage, and cost projections before training;
- PEFT permitted for engineering smoke tests, not automatically sufficient for the headline causal claim;
- full-weight training deferred until novelty, data, evaluation, calibration, and cost gates pass.

See [`docs/RESOURCE_CONSTRAINTS.md`](docs/RESOURCE_CONSTRAINTS.md).

## Current status

**Stage 0 — design refactor and audit preparation.**

No scientific result is claimed. Specific papers, public checkpoints, source candidates, model revisions, and licenses mentioned in the research charter are audit targets until verified against primary sources.

The current write-active deliverable is the Stage 0 feasibility, novelty, and design package.

## Repository map

- [`docs/RESEARCH_CHARTER.md`](docs/RESEARCH_CHARTER.md) — scientific and operating charter.
- [`PROJECT_STATE.md`](PROJECT_STATE.md) — current phase, evidence, blockers, decision, and exact next action.
- [`PLAN.md`](PLAN.md) — milestone plan, gates, dependencies, and stop rules.
- [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md) — executable stage plan.
- [`docs/PILOT_PROTOCOL.md`](docs/PILOT_PROTOCOL.md) — synthetic calibration and naturalistic pilot protocol.
- [`docs/CLAIMS_TABLE.md`](docs/CLAIMS_TABLE.md) — competing explanations and discriminating tests.
- [`docs/SYNTHETIC_CALIBRATION_SPEC.md`](docs/SYNTHETIC_CALIBRATION_SPEC.md) — development design for the mandatory sensitivity calibration.
- [`docs/RESOURCE_CONSTRAINTS.md`](docs/RESOURCE_CONSTRAINTS.md) — compute and spending boundaries.
- [`RISKS.md`](RISKS.md) — current scientific, data, legal, and compute risks.
- [`docs/DATA_POLICY.md`](docs/DATA_POLICY.md) — provenance, rights, timestamps, deduplication, and leakage rules.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — durable design decisions and supersessions.
- [`configs/pilot.toml`](configs/pilot.toml) — design-state two-era/two-source specification.
- [`src/chronopersona`](src/chronopersona) — validation and later experiment tooling.
- [`AGENTS.md`](AGENTS.md) — concise recurring rules for Codex and other agents.

## Validate the current design specification

```bash
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m chronopersona validate configs/pilot.toml
pytest
```

The configuration deliberately leaves the token budget unfrozen while its status is `design`. It cannot advance to execution without a measured benchmark and a frozen positive budget.

## Working paper title

**From Archive to Policy: Testing Cross-Source Temporal Generalization in Language Models**

The repository does not select a positive- or null-result title before evidence exists.

## License

No open-source license has been selected. The repository remains all-rights-reserved until code, data, collaboration, and release decisions are made explicitly.
