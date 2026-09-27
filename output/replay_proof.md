# Replay proof — the published evidence can be rebuilt from preserved raw inputs

**Verdict: REPRODUCED**

- Replayed run: `run_example` (its preserved raw inputs in `data/raw/run_example/`).
- Integrity: 28 of 28 preserved artefacts matched the SHA-256 recorded at retrieval (`replay_integrity.csv`, one row per artefact).
- No client system was contacted: the SQL extracts, files, every raw Dispatch API page and the weather response were read from the preserved copies.
- Outputs: 46 of 46 deterministic outputs are byte-identical to the original run.

Command: `python run_pipeline.py --replay run_example`