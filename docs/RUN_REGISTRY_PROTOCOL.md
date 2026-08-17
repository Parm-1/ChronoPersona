# Run Registry and Fixture Smoke Protocol

**Version:** v0  
**Status:** engineering validation only  
**Default external spend:** CAD $0

## 1. Purpose

This protocol establishes the repository machinery needed before any model-training branch can be trusted:

- immutable run identity;
- explicit run states;
- append-only, hash-chained runtime events;
- one active process per run;
- atomic checkpoints and artifacts;
- explicit interruption recovery;
- deterministic final manifests;
- fail-closed verification after corruption or identity mismatch.

The committed smoke does **not** load a model, import a model runtime, contact a network service, consume training tokens, or produce evidence about CSTG. It rebuilds the deterministic Synthetic Identifiability Calibration package and treats each generated file as an engineering work unit.

## 2. Identity versus runtime metadata

ChronoPersona keeps two classes of record separate.

### Immutable scientific identity

`identity.json` contains the canonical inputs that define one run:

- Git commit;
- complete smoke configuration hash;
- calibration configuration, expected-package identity, and evaluation-registry hashes;
- generated calibration-package identity;
- deterministic work-unit order;
- seed;
- model, tokenizer, training method, target-token, and precision declarations;
- environment identity;
- resource constraints;
- scientific-claim and training authorization flags.

The canonical SHA-256 of this object determines the run ID:

```text
run-<first 32 hexadecimal characters of identity SHA-256>
```

Changing an input, Git commit, environment identity, seed, or resource boundary creates a different run ID.

### Runtime event record

`events.jsonl` contains wall-clock and operational information. It is not part of the scientific identity. Each event records:

- run ID;
- sequence number;
- event type;
- state before and after;
- recording time;
- previous-event hash;
- structured event data;
- event hash.

Every read validates the entire chain. A changed, missing, duplicated, reordered, or malformed event fails verification.

## 3. Run states

The supported states are:

```text
design -> frozen -> running -> complete
                       |
                       v
                     failed -> running
```

An unclean process exit can be recovered only through an explicit `recover` event while the run remains `running`. A recorded failure can be resumed only through an explicit `resume` event.

Permitted events:

| Event | State before | State after |
|---|---|---|
| `create` | none | `design` |
| `freeze` | `design` | `frozen` |
| `start` | `frozen` | `running` |
| `progress` | `running` | `running` |
| `recover` | `running` | `running` |
| `fail` | `running` | `failed` |
| `resume` | `failed` | `running` |
| `complete` | `running` | `complete` |

`complete` is terminal. The tooling never silently rewrites an event or changes a completed identity.

## 4. Cross-run registry

The local output root contains `registry.jsonl`. It is an append-only hash chain containing one immutable entry per run ID.

Each entry records:

- sequence number;
- run ID;
- identity hash;
- creation time;
- previous-entry hash;
- entry hash.

Re-registering the same run returns the existing identical entry. A duplicate run ID with another identity, a broken chain, or a changed entry fails closed.

The runtime registry belongs under ignored `runs/` storage. It is not a manually edited project ledger.

## 5. Locking

Execution creates an exclusive lock under:

```text
<output-root>/.locks/<run-id>.lock
```

The lock covers run initialization, state changes, checkpoint updates, and finalization. A second process receives an error.

A stale lock is never removed automatically. The operator must inspect the lock, confirm that no process owns it, and remove it intentionally. This avoids two workers resuming the same run after an ambiguous failure.

## 6. Atomic artifacts

JSON artifacts are written to a temporary file in the destination directory, flushed, synchronized, and atomically replaced.

The smoke maintains:

```text
<run-root>/
  identity.json
  events.jsonl
  checkpoint.json
  artifacts/
    units/
      <ordered deterministic unit artifacts>.json
    final-manifest.json
```

`checkpoint.json` records:

- run and identity hashes;
- deterministic work-unit-order hash;
- completed work-unit prefix;
- exact relative artifact paths;
- artifact file hashes;
- deterministic unit-output hashes;
- next unit index;
- checkpoint hash.

A checkpoint may only describe an ordered prefix of the frozen unit list. Missing files, unsafe paths, duplicate units, a skipped unit, an incorrect next index, a changed file, or a changed hash aborts recovery.

## 7. Fixture-smoke configuration

The committed configuration is:

```text
configs/runs/synthetic-fixture-smoke-v0.json
```

It is deliberately restricted to:

- `run_kind = fixture-smoke`;
- `status = development`;
- no scientific claim;
- no training authorization;
- no network access;
- no model download;
- CAD $0 external spend;
- one parallel job;
- zero target tokens;
- no model, tokenizer, or weight revision;
- not-applicable precision;
- checkpoint after every work unit.

Changing any of these restrictions causes validation to fail. This file cannot be repurposed into a hidden model-training configuration.

## 8. Commands

### Plan

```powershell
python scripts/run_smoke_pipeline.py plan
```

Planning:

- rebuilds the deterministic calibration package in memory;
- verifies it against committed expected hashes;
- hashes all run inputs;
- resolves the Git commit and environment identity;
- derives the run ID;
- reports minimum local storage and unresolved model-training gates.

It writes no run directory.

### Execute

```powershell
python scripts/run_smoke_pipeline.py run
```

The default local output is ignored:

```text
runs/synthetic-fixture-smoke-v0/
```

### Exercise interruption

```powershell
python scripts/run_smoke_pipeline.py run --interrupt-after 2
```

A planned interruption exits with code `75` after checkpointing and recording a `failed` state.

### Resume

```powershell
python scripts/run_smoke_pipeline.py run --resume
```

Resume authorization is mandatory for a `failed` or still-`running` run. Every existing checkpoint and unit artifact is verified before new work starts.

### Verify

```powershell
python scripts/run_smoke_pipeline.py verify `
  --run-root runs/synthetic-fixture-smoke-v0/run-<identity>
```

Verification reconstructs the plan from the stored Git and environment identity, verifies all hashes and state, and refuses a different checkout unless the operator explicitly requests forensic verification:

```powershell
python scripts/run_smoke_pipeline.py verify `
  --run-root <run-root> `
  --allow-different-checkout
```

The override does not change the recorded identity. It only acknowledges that the verifier is running from another checkout.

## 9. Determinism requirement

The final manifest excludes timestamps and runtime-event hashes. Therefore:

> An interrupted-and-resumed execution must produce the exact same `final-manifest.json` bytes as an uninterrupted execution with the same identity.

CI enforces this with `cmp` after running both paths.

Runtime event logs are expected to differ because they record different operational histories.

## 10. Failure rules

The smoke fails on:

- changed immutable identity;
- invalid state transition;
- broken event or registry hash chain;
- existing run without explicit resume authorization;
- an existing or stale execution lock;
- unsafe checkpoint path;
- missing or changed unit artifact;
- checkpoint hash or index mismatch;
- generated calibration-package drift;
- malformed generated JSON or JSONL;
- a different current checkout during ordinary verification;
- nonzero token, spend, network, model, or training authorization in the fixture config.

A pipeline exception records only its type and a hash of the message. It does not put source text, credentials, or unrestricted error payloads into the durable event ledger.

## 11. What this milestone establishes

Observed after CI passes:

- deterministic run IDs;
- exact state-transition enforcement;
- append-only event and registry validation;
- exclusive process locking;
- atomic checkpoint and artifact writes;
- interruption and resume without duplicate completed work;
- corruption detection;
- deterministic final-manifest equivalence;
- a clean checkout CPU integration path.

It does **not** establish:

- model loading or logits correctness;
- GPU memory or throughput;
- optimizer or checkpoint compatibility;
- model-training resumption;
- calibration sensitivity;
- a frozen signal dose;
- a valid naturalistic corpus;
- a scientific result.

## 12. Next extension

The real training runner must reuse the identity, event, lock, checkpoint, and verification contracts rather than invent a parallel system. Before that extension is allowed, it must add:

- a manifest-approved model and tokenizer revision;
- measured hardware and benchmark identities;
- a positive frozen target-token budget;
- optimizer, scheduler, batch, context, precision, and insertion-point identities;
- model-checkpoint hashes;
- data and evaluation manifest hashes;
- storage and duration limits;
- deterministic resumption tests for the actual trainer.
