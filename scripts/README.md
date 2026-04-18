# `scripts/`

Run Python entrypoints from the **repository root** with `PYTHONPATH=.` unless a script’s docstring says otherwise.

**Documented admin flows:** [docs/ADMIN_TOOLS.md](../docs/ADMIN_TOOLS.md)

---

## Layout

| Folder | Purpose |
|--------|---------|
| **`catalog/`** | Place-catalog JSONL pipeline: batch score, rerun failures, rescore pillars, recompute composites, export CSV, health reports. |
| **`ops/`** | Shell wrappers: prod refresh, completeness threshold rescoring, economic calibration, backend smoke checks. |
| **`baselines/`** | Build or refresh `data/*.json` normalization files (economic, status signal, stability, IRS, voter, OEWS, NRHP DB, Natural Earth download). |
| **`collectors/`** | Long-running API batch jobs: `locations.csv` → `results.csv`, status-signal-only runs, active-outdoors batch, simple score list. |
| **`debug/`** | One-off analysis, pillar validation CLIs, comparisons, markdown reports (not for production cron). |
| **`manual/`** | Ad-hoc `test_*.py` smoke scripts (not pytest); API/pillar spot checks. |

`paths.py` — small helper used by convention (some scripts use `Path(__file__).resolve().parents[2]` for repo root).

---

## Super short: what each script does

### `catalog/`

| Script | Does |
|--------|------|
| `batch_score_place_catalog.py` | CSV catalog → API → JSONL scores. |
| `rerun_failed_catalog_pillars.py` | Fix failed pillars in JSONL → merged JSONL. |
| `rescore_catalog_pillar.py` | Rescore chosen pillar(s); optional completeness/confidence filters; `--dry-run` lists only. |
| `recompute_catalog_composites.py` | Refresh longevity / status_signal / happiness from existing JSONL (no pillar re-run). |
| `export_catalog_scores_csv.py` | JSONL → wide CSV. |
| `report_catalog_pillar_health.py` | JSONL → pillar health CSVs. |
| `report_catalog_confidence_below.py` | Count places under a confidence threshold. |
| `verify_rescore_pillar.py` | E2E check for single-pillar job flow. |

### `ops/`

| Script | Does |
|--------|------|
| `catalog_rescore_pillar_completeness_threshold.sh` | NYC+LA: rescore one pillar below completeness **T**, recompute composites, commit+push, print stragglers. Set `PILLAR` (default `neighborhood_amenities`). |
| `refresh_merged_catalog_from_prod.sh` | Prod API → merged JSONLs + composites. |
| `refresh_nyc_catalog_amenities_prod.sh` | NYC merged: refresh neighborhood_amenities + composites. |
| `calibrate_economic_baselines.sh` | Runs `baselines/build_economic_baselines.py`. |
| `check_backend_score.sh` | POST job, poll, print scores. |
| `debug_production_status_signal.sh` | Curl prod health + status_signal sample. |

### `baselines/`

| Script | Does |
|--------|------|
| `build_economic_baselines.py` | Sample locations → `economic_baselines.json`. |
| `build_economic_baselines_from_results.py` | Same from `results.csv`. |
| `build_status_signal_baselines.py` | Census sample → `status_signal_baselines.json`. |
| `build_status_signal_baselines_from_results.py` | From `results.csv`. |
| `build_stability_baselines.py` | ACS stability → `stability_baselines.json`. |
| `build_stability_baselines_from_results.py` | From `results.csv`. |
| `build_irs_engagement_baselines.py` | IRS BMF → tract counts + stats. |
| `build_voter_registration_baselines.py` | Tract CSV → voter JSONs. |
| `fetch_voter_registration_data.py` | Download CVAP/EAVS → voter JSONs. |
| `build_oews_metro_wages.py` | BLS OEWS XLSX → wage JSON. |
| `build_nrhp_db.py` | NPS → SQLite NRHP index (deploy). |
| `download_natural_earth_water.py` | Download Natural Earth layers for water scoring. |

### `collectors/`

| Script | Does |
|--------|------|
| `collector.py` | `locations.csv` → API → append `results.csv`. |
| `score_locations.py` | Simple: print `location,total_score`. |
| `collect_status_signal.py` | Status-signal pillars only → `results.csv`. |
| `collect_active_outdoors.py` | Active outdoors batch → JSONL + summary. |

### `debug/`

| Script | Does |
|--------|------|
| `check_calibration_and_scores.py` | Baseline sanity + API spot checks. |
| `compare_status_signal.py` | Two locations → status signal comparison. |
| `score_status_signal.py` | One location → status signal + breakdown. |
| `status_signal_breakdown_md.py` | Saved JSON → markdown breakdown. |
| `inspect_brand_matches.py` | Brand matches from saved score JSON. |
| `compare_beauty_larchmont.py` | Town vs address beauty comparison. |
| `investigate_built_beauty_preferences.py` | Built beauty preference permutations. |
| `investigate_housing_issues.py` | Housing data spot investigations. |
| `collect_built_beauty_research_data.py` | Research sampling for built beauty stats. |
| `debug_built_beauty.py` | Built beauty JSON CLI. |
| `debug_climate_risk.py` | Climate pillar + GEE debug. |
| `normalize_dynamism_by_bucket.py` | Dynamism normalization experiment CSV. |
| `validate_economic_security.py` | Economic pillar distribution / resilience checks. |
| `validate_natural_beauty_scoring.py` | Natural beauty validation suite. |

### `manual/` (`test_*.py`)

Ad-hoc tests: API health, healthcare, natural beauty, built beauty, rule-based scoring, social fabric, etc. Open each file’s docstring for usage.

---

## Automation

- **GitHub Actions:** `.github/workflows/collector.yml` → `collectors/collector.py`; `active-outdoors-collect.yml` → `collectors/collect_active_outdoors.py`.
- **Railway:** `railway.json` → `baselines/build_nrhp_db.py`.
- **npm:** `package.json` `build-status-baselines` → `baselines/build_status_signal_baselines.py`.

More detail on lesser-used scripts: [DEV_SCRIPTS.md](./DEV_SCRIPTS.md).
