# Catalog Rescore Runbook

The catalog (`data/{nyc,la}_metro_place_catalog_scores_merged.jsonl`) is a precomputed
snapshot. On top of the original build, a series of **offline rescores** layer in pillar
fixes without a full live re-run. Each tags the pillar it touches with a `_rescore_version`
so you can audit what's applied.

> ⚠️ **These are NOT in the build.** If the catalog is ever rebuilt from scratch (or
> refreshed from prod), every rescore below must be **re-applied in order** or the fixes are
> lost. This is the root of most "Live vs Explorer" drift — see
> [LIVE_SCORER_VS_EXPLORER.md](LIVE_SCORER_VS_EXPLORER.md).

## What's currently applied (audit via `_rescore_version`)

| Pillar | `_rescore_version` | Script | What it does |
|---|---|---|---|
| public_transit_access | `transit_v3_subway_commuter_split` | `scripts/rescore_transit_split.py` | split subway (rt 1) vs commuter rail (rt 2), weights 3/1/2/0.7, anchor 120 |
| public_transit_access | `commuter_access_floor_ridership` | `scripts/apply_commuter_access_floor.py` | floor commuter-rail towns at commute-time × tract transit-ridership (no cap) |
| air_travel_access | `air_travel_commute_bands` | `scripts/rescore_air_travel.py` | drive-time bands to best hub (fixes the LA std-0 saturation) |
| quality_education | `education_weight_enabled` | `scripts/enable_education_weight.py` | give education its weight (scores already existed) |
| diversity | `diversity_transient_refetch` / `diversity_nodata_unresolvable` | `scripts/repair_diversity_and_weights.py` | fix the 2 broken diversity=0 records + renormalize weights to 100 |
| economic_security | `econ_job_access_blend` | `scripts/apply_econ_job_access.py` | blend 0.55·job_access (LODES gravity) + 0.45·market_quality |
| neighborhood_amenities | `amenities_v3_walkable_density` | *(prior session — see script)* | walkable-density amenities model |
| social_fabric | `v14_two_morphology` | `scripts/apply_social_fabric_rescore.py` *(prior)* | two-morphology cohesion model |

(Natural-beauty preference is **not** stored — it's applied at serve time: live in
`apply_v9_preference`, Explorer in `applyNbPreferenceV9`. Nothing to re-apply to the catalog.)

## Re-apply order (after a rebuild)

Order matters where a rescore depends on another's output or touches weights. Recommended:

1. **Pillar score rescores** (each floors/replaces a pillar score and cascades total_score):
   1. `rescore_transit_split.py` — must precede the commuter floor (it floors the v3 supply).
   2. `apply_commuter_access_floor.py` — needs transit v3 + the stored Happiness `commute`
      component; fetches tract transit-share (Census, reliable).
   3. `rescore_air_travel.py` — offline, deterministic (static airports).
   4. `apply_econ_job_access.py` — needs the LODES parquet; blends with stored market_quality.
2. **Weight / structural repairs** (these renormalize weights across all pillars — run after
   scores exist):
   1. `enable_education_weight.py` — adds education to the active weight set.
   2. `repair_diversity_and_weights.py` — fixes broken diversity records AND renormalizes every
      place's weights to sum to 100 (supersedes the education-enable weight bug). Run it LAST
      so the final weights are correct.

After all steps: verify `0 total-score mismatches` and weight sums == 100:
```python
rec = sum((v.get('score') or 0)*(v.get('weight') or 0)/100 for v in lp.values())
assert abs(rec - score['total_score']) < 0.05
assert abs(sum(v.get('weight') or 0 for v in lp.values()) - 100) < 0.05
```

## Idempotency
- `apply_econ_job_access.py` checks `_rescore_version` and skips already-blended places (safe
  to re-run).
- Most others are **not** idempotent (they'd double-apply). Each writes a `.bak*` backup before
  mutating; to re-run cleanly, restore from the backup first (e.g. `apply_commuter_access_floor`
  expects the v3-supply base — restore `.bakCommute` before re-running).

## Dependencies / data
- `apply_econ_job_access.py` requires `data/lodes_h8_commuter.parquet` (force-committed,
  covers NY/NJ/CT/CA). Rebuild for new metros: `build_lodes_h8_commuter.py --states ...`.
- `apply_commuter_access_floor.py` and `apply_econ_job_access.py` make Census calls (tract
  transit-share / none respectively) — reliable, NOT the noisy Transitland path.

## The real fix
This whole layered-rescore pipeline exists because a full live catalog rebuild through
`main.py` is the "faithful but expensive" path. The clean long-term answer is to fold these
into the build (or do periodic faithful rebuilds) so drift doesn't accumulate. Until then,
this runbook is the source of truth for reproducing the catalog's current state.
