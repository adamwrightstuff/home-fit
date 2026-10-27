# Natural beauty: fail-loud change, draft for approval (2026-10-25)

Status: DRAFT. Nothing applied. No code, test, catalog or tracker file has been touched. Companion to `analysis/audit_natural_beauty_2026-10-25.md` (defects D1 to D4).

## What I found since the audit (changes the design)

A failed water read and a genuinely empty water read are the same value today. `osm_api.query_water_features` (15 km radius) returns `source: "osm_empty"` with no nearest water when nothing is found. `calculate_natural_beauty` swallows any exception from that call with a debug log, and then a line that nulls any result with no nearest distance erases the difference. Both end as `water_type: null`, and `_v9_score_water` turns that into 5.0. So the fix has to keep three states apart, not just stop defaulting.

## Part 1: Water

**New rule.** Three states, stored as `water_status` in the breakdown:

| State | Meaning | Water score |
|---|---|---|
| measured | OSM returned a nearest water body | existing curve, unchanged |
| none_within_15km | query succeeded, `osm_empty` | the curve's existing floor of 3.0 (already in the code for far water; not a new number) |
| unavailable | exception, non-dict result, or error result | None, no value at all |

When water is unavailable the scenery part is terrain alone and the place is marked degraded with reason `water_read_unavailable`. `_lead_pair` and `nb_two_part` already accept a missing component, so the blend code does not change.

**Code touch points (draft):**
1. `calculate_natural_beauty`, the parallel fetch block: set `water_status` from the three outcomes instead of nulling the result; carry it in `natural_context.debug_breakdown`.
2. `_v9_score_water`: return None when status is unavailable; remove the 5.0 default.
3. `_apply_v9_formula`: pass `water_score=None` through, write `water_status` and the degraded reason into the breakdown and into `data_quality.degraded_reasons`.
4. Mirrors to check before any change: `frontend/lib/nbPreference.ts`, `scripts/catalog/apply_preference_filters.py`, `recompute_natural_beauty_two_part_offline.py` (all must tolerate a null water score). I have not read them yet.

**Catalog (offline, no API).** 192 places have `water_type: null`. Active Outdoors stored water features for all 192 (135 within 3 km, 34 within 1 km), so all 192 are labeled `unavailable`, not `none_within_15km`. The label uses that stored evidence; the score uses only terrain. Script follows the housing value pattern (`recompute_housing_value_nodata_offline.py`): dry run first, `--write` needs `--backup-dir`, old values saved, then `recompute_catalog_composites.py --no-census`.

**Expected impact, offline-computed:**
- Pillar score, 192 places: mean +5.2, max +15.4 (water term dropped; scenery becomes terrain alone).
- Total score: mean +0.4, max +1.2 (pillar weight 7.7%).
- This is a placeholder state, not the final number. Use of the real water read, if you approve a re-read later (separate decision, Overpass queries for 192 places, private server): river type about +3 on average, lake about +8, ocean about +15 relative to today (max +11.5 / +25.7 / +39.0).

## Part 2: Live fail-loud flags

**Rule.** A part (streets, scenery) is available if at least one of its two components was measured. The pillar needs both parts. Otherwise it has no data and drops out of the headline, same as housing value (`RuntimeError`, weight redistributed). One component missing inside an available part means score from the other, mark degraded with the reason.

| Flag (degraded reason) | Fires when | Today |
|---|---|---|
| `canopy_unavailable` | GEE canopy, multi-radius and Census canopy all absent | read as 0.0 through `or 0.0` |
| `green_view_unavailable` | no GEE green view result | the composite fallback quietly fills it |
| `green_view_fallback` | composite fallback (canopy, street trees, parks) produced the value | labeled "measured" |
| `green_view_proxy` | measured green view under 2% replaced by 0.7 x canopy | labeled `canopy_proxy` in inputs only |
| `topography_unavailable` | no terrain result | read as 0.0 |
| `water_read_unavailable` | Part 1 | scored 5.0 |
| no data (pillar fails) | streets part or scenery part has no measured component | San Fernando scores 3.1 and keeps full weight |

**Code touch points (draft):**
1. `get_natural_beauty_score`: the "all sources failed" branch logs a warning and continues. Make it raise.
2. `_apply_v9_formula`: replace `or 0.0` on green view, canopy and terrain with None-aware reads; compute availability from the fetch results, not from `green_view_index is not None` (always true, so `streets_inputs_missing` can never fire live). Drop the `measured=` shortcut in `streets_inputs_missing`; keep the exact-zeros check only for stored data.
3. Label `gvi_source` honestly: "composite_fallback" when `green_view_details.method == "composite"`.
4. Carry the reasons into `data_quality.degraded`, `degraded_reasons`, and the pillar `confidence`.

**Update 2026-10-26 (approved: proxy rule removed).** The under-2% proxy rule (measured green view replaced by 0.7 x canopy) is gone; the measured value is used. My earlier estimate of -10.3 points on average was wrong: it left out the visible-green-fraction floor that still applies. Rerunning the real formula on the stored data moves 55 places by a mean of +0.2 (min 0.0, max +2.1 and +4.7 for one that also had missing water; none by more than 5 on the proxy change alone).

**Expected impact on the 1,476 stored places:**
- San Fernando: becomes no data. Total score 58.78 to 63.42 (+4.6) as its 7.7% weight is redistributed.
- Every other stored place: no score change from Part 2. All others have a green view and canopy value, and terrain is exactly 0 only for San Fernando.
- 60 places gain a `green_view_proxy` degraded flag, no score change. 192 gain `water_read_unavailable` (Part 1).
- Live path: no stored effect, it protects against future GEE and Overpass outages.

## Tests (draft)
- Water: status mapping for found, osm_empty, exception; unavailable gives scenery equal to terrain alone.
- Pillar: no streets measurement raises; no scenery measurement raises; one component missing gives a degraded score.
- Labeling: composite fallback is not called "measured".
- Catalog script: dry-run count equals 192 water places plus San Fernando; idempotent on second run; backup written.
- Regression: places with complete data score identically to today (spot set across all 21 metros).

## Sequence
1. Read the three mirror files; tell you if they need changes.
2. Code and tests, run `pytest tests/` including the existing natural beauty tests.
3. Offline catalog script dry run, show you the list, then write with backup.
4. `recompute_catalog_composites.py --no-census`, then re-run the reproducibility check (stored score equals recomputed from components).
5. Commit locally. No push without your say; the earlier two-part commit is also still unpushed.

## What is sourced and what is judgment
- Sourced: nothing new. This change adds no scoring parameter.
- Judgment: the 3.0 floor for "no water within 15 km" (an existing curve value, not new); the rule that both parts are required; the 2% proxy threshold (existing, unchanged).
- Not decided: whether the 192 water reads should be re-run, and whether the 2% proxy rule should stay.

## Decision for you

Approve the three-state water rule, the both-parts-required rule (San Fernando becomes no data), and the proxy flag without changing the proxy values, so I can implement them locally, uncommitted until you review the diff?
