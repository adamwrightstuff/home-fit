# Development & one-off scripts

These are **not** the short list in [docs/ADMIN_TOOLS.md](../docs/ADMIN_TOOLS.md). They are safe to keep for debugging, research, and manual baselines. Run from repo root: `PYTHONPATH=. python3 scripts/<name>.py` (see each file’s docstring).

## Documented elsewhere (keep; see linked doc)

| Script | Referenced in |
|--------|----------------|
| `build_irs_engagement_baselines.py` | [docs/SOCIAL_FABRIC_PRD.md](../docs/SOCIAL_FABRIC_PRD.md) |
| `build_voter_registration_baselines.py` | docs/SOCIAL_FABRIC_PRD.md |
| `build_stability_baselines.py` | docs/SOCIAL_FABRIC_PRD.md |
| `build_oews_metro_wages.py` | [docs/economic_security_pillar_data_reference.md](../docs/economic_security_pillar_data_reference.md) |
| `download_natural_earth_water.py` | [analysis/PILLAR_SCORING_EXPLANATION.md](../analysis/PILLAR_SCORING_EXPLANATION.md) |
| `compare_beauty_larchmont.py` | [analysis/BEAUTY_TOWN_VS_ADDRESS.md](../analysis/BEAUTY_TOWN_VS_ADDRESS.md) |
| `collect_built_beauty_research_data.py` | [analysis/BUILT_BEAUTY_RESEARCH_DATA.md](../analysis/BUILT_BEAUTY_RESEARCH_DATA.md) |
| `investigate_built_beauty_preferences.py` | [analysis/CARROLL_GARDENS_BUILT_BEAUTY_INVESTIGATION.md](../analysis/CARROLL_GARDENS_BUILT_BEAUTY_INVESTIGATION.md) |
| `investigate_housing_issues.py` | [analysis/housing_data_issues_fixes.md](../analysis/housing_data_issues_fixes.md) |
| `compare_status_signal.py` | [analysis/status_signal_tribeca_vs_carroll_gardens.md](../analysis/status_signal_tribeca_vs_carroll_gardens.md) |
| `validate_natural_beauty_scoring.py` | [DESIGN_PRINCIPLES.md](../DESIGN_PRINCIPLES.md) |
| `calibrate_economic_baselines.sh` | Wraps `build_economic_baselines.py` |

## CI / deploy / npm (keep)

| Script | Where |
|--------|--------|
| `collector.py` | `.github/workflows/collector.yml` |
| `collect_active_outdoors.py` | `.github/workflows/active-outdoors-collect.yml` |
| `build_nrhp_db.py` | `railway.json`, [DEPLOY_INSTRUCTIONS.md](../DEPLOY_INSTRUCTIONS.md) |
| `build_status_signal_baselines.py` | Root `package.json` script `build-status-baselines` |

## Baseline builders from `data/results.csv`

| Script | Purpose |
|--------|---------|
| `build_economic_baselines_from_results.py` | Economic baselines from collector output |
| `build_status_signal_baselines_from_results.py` | Status signal baselines from results |
| `build_stability_baselines_from_results.py` | Stability baselines from results |

## Status signal / brand debugging

| Script | Purpose |
|--------|---------|
| `collect_status_signal.py` | Batch status-signal collection |
| `save_score_json.py` | Save API score JSON for offline inspection |
| `score_status_signal.py` | CLI score status signal for a location |
| `score_tribeca_status_happiness.py` | Tribeca-focused sample run |
| `status_signal_breakdown_md.py` | Markdown breakdown from saved JSON |
| `inspect_brand_matches.py` | Compare `business_list` / brand matches across JSON files |

## Debug / verification

| Script | Purpose |
|--------|---------|
| `check_calibration_and_scores.py` | Compare calibration vs live API |
| `verify_rescore_pillar.py` | Rescore pillar against a base URL |
| `debug_built_beauty.py` | Built beauty debug CLI |
| `debug_climate_risk.py` | Climate pillar debug |
| `normalize_dynamism_by_bucket.py` | Economic dynamism normalization experiment |

## Shell helpers

| Script | Purpose |
|--------|---------|
| `check_backend_score.sh` | Create job, poll, print score (see [ADMIN_TOOLS](../docs/ADMIN_TOOLS.md)) |
| `debug_production_status_signal.sh` | Curl production `/score` for status_signal breakdown (needs `HOMEFIT_PROXY_SECRET`) |

## Batch HTTP helper

| Script | Purpose |
|--------|---------|
| `batch_request.py` | Call batch scoring endpoint locally / staging |

## Data fetch (offline ETL)

| Script | Purpose |
|--------|---------|
| `fetch_voter_registration_data.py` | Fetch raw voter registration inputs (separate from baseline builder) |

## Tests & smoke scripts (`test_*.py`)

| Script | Purpose |
|--------|---------|
| `test_healthcare_access.py` | Healthcare pillar spot-check |
| `test_healthcare_fixes.py` | Healthcare regression checks |
| `test_scoring_direct.py` | Direct pillar import smoke test |
| `test_osm_restaurants.py` | OSM restaurant query experiment (Coconut Grove) |
| `test_osm_broad_query.py` | Broad Overpass query test |
| `test_natural_beauty.py` | Natural beauty manual test |
| `test_natural_beauty_wave2_percentiles.py` | Wave-2 percentile checks |
| `test_natural_beauty_improvements.py` | Natural beauty improvement validation |
| `test_coconut_grove_amenities.py` | Amenities pillar spot-check |
| `test_built_beauty_debug.py` | Built beauty debug |
| `test_rule_based_scoring.py` | Rule-based scoring smoke test |
| `test_social_fabric_locations.py` | Social fabric location spot-checks |

## Archive

| Path | Note |
|------|------|
| `archive/investigate_greenways.py` | Old greenways investigation; keep for history or delete when obsolete |

---

To promote a script into “official” tooling, add a short subsection under [docs/ADMIN_TOOLS.md](../docs/ADMIN_TOOLS.md) and a row in its summary table.
