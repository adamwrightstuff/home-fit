# Development & one-off scripts

These are **not** the short list in [docs/ADMIN_TOOLS.md](../docs/ADMIN_TOOLS.md). They are kept for debugging, research, and manual baselines.

**Scripts now live in subfolders** — see **[README.md](./README.md)** for the full layout and a one-line description of every entrypoint.

Run from repo root:

```bash
PYTHONPATH=. python3 scripts/<subfolder>/<name>.py
```

For looping `/score` over many places from a list, use **`collectors/collector.py`** or the catalog batch scripts, not ad-hoc one-off scripts.

Update references in analysis docs when you cite a script path (e.g. `scripts/debug/compare_status_signal.py` instead of `scripts/compare_status_signal.py`).

## Cross-references (docs that mention specific scripts)

| Topic | Script (new path) |
|-------|---------------------|
| Social Fabric PRD | `baselines/build_irs_engagement_baselines.py`, `build_voter_registration_baselines.py`, `build_stability_baselines.py` |
| Economic / OEWS | `baselines/build_oews_metro_wages.py` |
| Natural Earth / water | `baselines/download_natural_earth_water.py` |
| Built beauty research | `debug/collect_built_beauty_research_data.py` |
| Carroll Gardens built beauty | `debug/investigate_built_beauty_preferences.py` |
| Housing spot checks | `debug/investigate_housing_issues.py` |
| Tribeca vs Carroll status signal | `debug/compare_status_signal.py` |
| Natural beauty validation | `debug/validate_natural_beauty_scoring.py` |
| Economic calibration shell | `ops/calibrate_economic_baselines.sh` → `baselines/build_economic_baselines.py` |
