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

## Triage (2026)

- [x] **ORPHAN scripts** — Catalogued in [scripts/DEV_SCRIPTS.md](../scripts/DEV_SCRIPTS.md); entry point [scripts/README.md](../scripts/README.md). [docs/ADMIN_TOOLS.md](ADMIN_TOOLS.md) links to the catalog.
- [x] **CLUTTER** — Root-level captures and local npm artifacts ignored via [.gitignore](../.gitignore) (`*.webm`, `homefit-*.png`, scratch JSON, `/node_modules/`, etc.).

### Remaining (optional)

### Env

Remove unused variables (e.g. `GEOCITY_*`) from `.env` after confirming no references.
