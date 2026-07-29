# Catalog Toolkit

All scripts run from the **repo root** with `PYTHONPATH=.` unless noted.  
Production API: `https://home-fit-production.up.railway.app`  
Auth header (if `HOMEFIT_PROXY_SECRET` is set): `X-HomeFit-Proxy-Secret: $HOMEFIT_PROXY_SECRET`

---

## Quick Decision Guide

```
Something looks wrong with a place's score
│
├─ Is the data already stored in the JSONL? (sub-scores, breakdowns, weights)
│   └─ YES → offline recompute or patch — no API needed
│
└─ Does the fix require new external data? (Overpass, Census, GEE, Places)
    └─ YES → API rescore
        │
        ├─ One or more pillars failed entirely (success=False, api_error)?
        │   └─ rerun_failed_catalog_pillars.py
        │
        ├─ Pillar scored but on wrong logic / old version / bad data?
        │   └─ rescore_catalog_pillar.py  (supports --confidence-filter-lt, --completeness-filter-lt)
        │
        └─ Want to rescore one pillar AND recompute composites in one shot?
            └─ rescore_pillar_and_recompute.py
```

**After any API rescore**, always recompute composites unless you used `rescore_pillar_and_recompute.py`:
```bash
PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \
  --input data/nyc_metro_place_catalog_scores_merged.jsonl \
  --output data/nyc_metro_place_catalog_scores_merged.jsonl
```

---

## 1. Health & Diagnostics (read-only, no API)

| Script | What it does |
|--------|-------------|
| `check_catalog_health.py` | **Main health check.** Per-place, per-pillar: old versions, null scores, low confidence, degraded, data warnings, fallback usage, missing subcomponents, composite drift, plausibility outliers (z-score). |
| `report_catalog_pillar_health.py` | Pillar-level health summary CSVs from a batch JSONL. |
| `report_catalog_confidence_below.py` | Count places under a confidence threshold per pillar. |
| `audit_pillar_confidence_staleness.py` | Audit for stale confidence/data_warning fields. |
| `verify_rescore_pillar.py` | E2E check that single-pillar rescore flow works. |
| `analyze_built_environment_patterns.py` | Cross-catalog built beauty pattern analysis. |
| `analyze_vibe_vs_status.py` | Scatter: vibe score vs status signal across NYC + LA. |

**Canonical health check:**
```bash
PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --no-unversioned
# One pillar:   --pillar active_outdoors
# CSV export:   --csv > health.csv
# Noisy places: --min-flags 3
```

---

## 2. Initial Batch Scoring

| Script | What it does |
|--------|-------------|
| `batch_score_place_catalog.py` | CSV catalog → API → JSONL. Starting point for a new catalog. |
| `batch_score_vacation_destinations.py` | Batch score top US vacation destinations in vacation mode. |
| `score_missing_places.py` | Score places in the input CSV that are absent from the merged JSONL. |

---

## 3. API Rescores (requires running API or Railway)

Set `HOMEFIT_API_BASE` to target Railway; default is `http://127.0.0.1:8000`.

### General-purpose

| Script | When to use |
|--------|-------------|
| `rerun_failed_catalog_pillars.py` | Rows where scoring *broke* — success=False, api_error, null score. Reactive patch for failures. |
| `rescore_catalog_pillar.py` | Rows that scored correctly but need a pillar update — new logic, old version, bad data. Supports `--confidence-filter-lt`, `--completeness-filter-lt`, `--names`, `--dry-run`. |
| `rescore_pillar_and_recompute.py` | Rescore one pillar then immediately recompute composites — one command instead of two. |
| `rescore_live_pillars_area_type.py` | Live rescore of active_outdoors, public_transit_access, and economic_security for area_type changes. |

**Rescore one pillar for all low-confidence places:**
```bash
HOMEFIT_API_BASE=https://home-fit-production.up.railway.app \
HOMEFIT_PROXY_SECRET=<secret> \
PYTHONPATH=. python3 scripts/catalog/rescore_catalog_pillar.py \
  --pillars active_outdoors \
  --in-place --no-backup \
  --confidence-filter-pillar active_outdoors \
  --confidence-filter-lt 70
```

### Pillar-specific API rescores

| Script | What it targets |
|--------|----------------|
| `rescore_ao_overpass_errors.py` | AO places where Overpass failed during original batch. |
| `rescore_ao_waterfront.py` | AO places with known waterfront data issues. |
| `refetch_ao_local_parks.py` | Re-fetch only the local parks Overpass query for `overpass_local` failures. |
| `rescore_built_environment_api_errors.py` | Built environment where Overpass failed. |
| `rescore_built_environment_full.py` | Full built beauty rescore for both catalog files. |
| `refetch_built_environment.py` | Live refetch of built_environment where stored data is unusable. |
| `rescore_social_fabric_targeted.py` | Social fabric places with known data issues. |
| `rescore_political_lean.py` | Add/refresh political_lean data. |
| `rescore_housing_blend.py` | Housing value — tenure-weighted blend update. |
| `rescore_housing_multifamily.py` | Housing value — multi-family building value inflation fix. |
| `rescore_water_type_fix.py` | Natural beauty for NYC places misclassified as 'ocean'. |

---

## 4. Offline Recomputes (no API, pure logic on stored data)

These re-derive scores from numbers already in the JSONL. No external calls.

| Script | What it recomputes |
|--------|-------------------|
| `recompute_catalog_composites.py` | longevity_index, status_signal, happiness_index. **Run after every API rescore.** |
| `recompute_active_outdoors_offline.py` | AO score from stored OSM summary data. |
| `recompute_built_environment_offline.py` | Built environment from stored form metrics. |
| `recompute_social_fabric_v15_offline.py` | Social fabric v16 (no API calls). |
| `recompute_social_fabric_engagement.py` | SF engagement component only. |
| `recompute_stability_blend.py` | SF stability scores from new blend logic. |
| `recompute_waterfront_offline.py` | AO waterfront_lifestyle artifact correction. |
| `recompute_community_safety_scores.py` | Community safety from stored crime data. |
| `rescore_community_safety_offline.py` | Community safety offline rescore. |
| `rescore_natural_beauty_v9_offline.py` | Natural beauty V9 from stored GEE/canopy data. |
| `rescore_built_environment_offline.py` | Built environment offline (preview-safe). |
| `recalibrate_waterfront_offline.py` | Waterfront scores from revised base values. |
| `_merge_neighborhood_beauty_offline.py` | Merge built_environment + natural_beauty → neighborhood_beauty. |

---

## 5. Offline Patches (surgical data fixes, no scoring logic change)

Inject or correct a specific field without re-running any scoring.

| Script | What it patches |
|--------|----------------|
| `patch_ao_water_winner.py` | Inject best_feature_type / best_feature_dist_m into AO summary. |
| `patch_ao_waterfront.py` | Targeted AO waterfront corrections. |
| `patch_best_fit_labels.py` | Add best-fit preference labels to NB and built_environment breakdowns. |
| `patch_school_charter_flag.py` | Add is_charter_school onto school arrays. |
| `patch_school_radius_bleed.py` | Fix school radius bleed (e.g. Westchester pulling Bronx schools). |
| `patch_transit_stable_commute.py` | Patch transit commute_time using stable multi-tract Census lookup. |
| `patch_water_type_direct.py` | Fix water_type misclassifications directly. |
| `backfill_housing_stock.py` | Inject Census ACS B25024 housing stock type. |
| `backfill_river_waterfront.py` | Inject river/waterway scores where AO waterfront_lifestyle=0. |
| `backfill_zip_codes.py` | Backfill missing ZIP codes via Nominatim reverse geocode. |
| `apply_v3_beauty_to_catalog.py` | Apply built_environment_v3 from stored form metrics. |
| `rescore_social_fabric_area_type.py` | Patch SF effective_area_type correction offline. |

---

## 6. Export & Merge

| Script | What it does |
|--------|-------------|
| `export_catalog_scores_csv.py` | JSONL → wide CSV (one row per place, all pillars as columns). |
| `merge_refetch_into_preview.py` | Merge live-refetched built_environment into offline-rescored preview catalogs. |

---

## 7. Analysis & Utilities

Not part of the fix pipeline — used for investigation or one-off generation.

| Script | What it does |
|--------|-------------|
| `apply_preference_filters.py` | Mirror of filter + weight UI — all levers configurable, no hardcoded profile. |
| `compute_local_scene.py` | Compute local_scene_score from stored business_list data. |
| `generate_archetype_summaries.py` | Claude-based archetype classifications and neighborhood summaries. |

---

## Standard Fix Workflow

```
1. Diagnose
   PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --no-unversioned

2. Decide: offline fix or API rescore?
   - Stored data is sufficient → pick from section 4 or 5
   - Need fresh external data → pick from section 3

3. Run the fix (API rescore example):
   HOMEFIT_API_BASE=https://home-fit-production.up.railway.app \
   HOMEFIT_PROXY_SECRET=<secret> \
   PYTHONPATH=. python3 scripts/catalog/rescore_catalog_pillar.py \
     --pillars <pillar> --in-place --no-backup \
     --confidence-filter-pillar <pillar> --confidence-filter-lt <threshold>

4. Recompute composites (skip if using rescore_pillar_and_recompute.py):
   PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \
     --input data/nyc_metro_place_catalog_scores_merged.jsonl \
     --output data/nyc_metro_place_catalog_scores_merged.jsonl

5. Re-run health check to confirm no regressions.
```
