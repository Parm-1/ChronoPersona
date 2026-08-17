# Data

Raw and transformed corpora are intentionally excluded from Git.

Reproducible experiments use immutable JSON Lines manifests under `data/manifests/`. Each record follows `docs/DATA_POLICY.md` and points to a locally or remotely resolved document without assuming a private directory layout.

Planned subdirectories:

- `raw/` — untouched acquired material;
- `interim/` — normalized but not frozen material;
- `processed/` — tokenized or filtered experiment inputs;
- `manifests/` — versioned document records and hashes.

Only synthetic fixtures or redistributable samples should be committed. Do not place credentials, private communications, copyrighted corpora, or model checkpoints here.
