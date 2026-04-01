# HomeFit cleanup checklist

Labels: **DEAD** (removed), **STALE** (fix in code/docs), **DOC** (documentation), **ORPHAN** (undocumented script — triage), **CLUTTER** (local artifacts).

## Done in this pass (2026)

- [x] **DEAD** — Removed `data_sources/satellite_api.py` (unused; GEE via `gee_api` / pillars).
- [x] **DEAD** — Removed `pillars/neighborhood_beauty.py` (superseded by `built_beauty` + `natural_beauty`; `neighborhood_beauty` remains a **token alias** in `main.py`).
- [x] **STALE** — `pillars/__init__.py`: dropped `neighborhood_beauty`; added `diversity`, `status_signal`, `happiness_index`, `composite_indices`.
- [x] **STALE** — `main.py` `_compute_scoring_hash()`: added major pillars + `census_api` + `geocoding`.
- [x] **STALE** — `data_sources/__init__.py`: documented non-exhaustive `__all__`.
- [x] **STALE** — `data_sources/regional_baselines.py`: removed broken pointers to missing `research_expected_values.py`.
- [x] **DOC** — `TESTING_ACTIVE_OUTDOORS.md`, `analysis/archive/EXPECTED_VALUES_RESEARCH.md`, `analysis/PILLAR_SCORING_EXPLANATION.md`, `analysis/pillar_design_principles_audit.md` aligned with removal of `neighborhood_beauty` module and missing scripts.

## Remaining (optional)

### ORPHAN scripts

Batch baseline builders, debug helpers, and `scripts/test_*.py` files are not listed in `docs/ADMIN_TOOLS.md`. Triage: document, move under `scripts/dev/`, or delete if obsolete.

### CLUTTER

Untracked screenshots, `.webm`, one-off JSON, or local `test_results.txt` — use `.gitignore` and avoid committing.

### Env

Remove unused variables (e.g. `GEOCITY_*`) from `.env` after confirming no references.
