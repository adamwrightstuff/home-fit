# Scoring Bug Backlog

Populated 2026-07-27 via `scripts/audit/scoring_anomaly_detector.py` (empirical, not code review).
No rescores done yet — all catalog values are as-stored.

---

## BUG-001 · Vacation AO collapse (systemic)
**Severity: HIGH** | Affects: ~15 vacation destinations

Every scenic vacation place shows natural_beauty 70–96 but active_outdoors 2–21.
The magnitude and consistency make this a structural scoring failure, not noise.

| Place | AO | NB |
|---|---|---|
| Moab, UT | 0.2 | 71.7 |
| Provincetown, MA | 2.5 | 80.5 |
| Malibu, CA | 3.7 | 94.5 |
| Santa Fe, NM | 6.9 | 72.3 |
| Bar Harbor, ME | 7.2 | 88.4 |
| Monterey, CA | 11.2 | 80.4 |
| Park City, UT | 11.1 | 91.3 |
| Vail, CO | 12.0 | 91.9 |
| Gatlinburg, TN | 12.9 | 89.7 |
| Pelham Bay, NY | 15.8 | 88.8 |
| Napa, CA | 21.4 | 96.7 |
| Sedona, AZ | 34.4 | 91.3 |
| Pasadena, CA | 4.1 | 82.2 |
| Jackson, WY | (low) | (high) |

**Also affects LA metro catalog (confirmed 2026-07-28):**

| Place | AO | NB | daily | wild | water | overpass status |
|---|---|---|---|---|---|---|
| Santa Monica, CA | 2.0 | — | 0.0 | 2.0 | 0.0 | success (not error) |
| Pasadena, CA | 4.1 | 82.2 | 0.0 | 4.1 | 0.0 | success (not error) |
| Downtown LA | 0.6 | — | 0.0 | 0.6 | 0.0 | success (not error) |

These were missed by `rescore_ao_overpass_errors.py` because `_is_affected` only flags `overpass_error` status. Santa Monica and Pasadena's Overpass queries returned data but below the density threshold — status=success, score=~0. The existing fix script has no coverage for this failure mode.

**Fix requires:** extend rescore targeting to catch `AO score < 10 AND status=success AND daily_urban_outdoors=0`. Either add a second detection pass to `rescore_ao_overpass_errors.py` or write a targeted one-off rescore for these three places.

**Hypothesis:** vacation catalog uses area_type=rural/exurban for scenic destinations,
and something in the AO scoring pipeline (radius, density thresholds, or OSM coverage)
is collapsing for sparse geographies even when green space exists. Overpass errors are
confirmed on Malibu, Moab, Provincetown, Bar Harbor — so Overpass failure → AO bottom-out
is likely the mechanism for vacation places; for SM/Pasadena the query succeeded but
returned insufficient density to score.

**Fix requires:** diagnosing whether AO fallback (Google Places AO) is triggering correctly
for vacation catalog, and whether the OSM-down score cap is being applied punitively.

---

## BUG-002 · social_fabric = 0 for Fort Greene and Glendale
**Severity: HIGH** | ✅ FIXED 2026-08-04 | Affects: Fort Greene NY, Southport CT, Glendale CA

**Root cause confirmed (2026-07-28):** `pillars/social_fabric.py:671` calls `round(channel_a, 1)` without a None guard. `channel_a` is None when the Social Capital Atlas has no ZIP-level cohesion data, causing the entire pillar to crash with `TypeError: type NoneType doesn't define __round__ method`. Scoring formula at line 521 correctly skips cohesion via `w_sc=0.0` but never reaches it because the breakdown dict serialization runs first and crashes. Southport is a separate timeout failure.

**Fix applied (2026-07-28):** `pillars/social_fabric.py:671` patched to `round(channel_a, 1) if channel_a is not None else None`.

**Rescored:**
- Fort Greene NY: already fixed in prior session (score=40.2)
- NYC Glendale: already fixed in prior session (score=41.1)
- LA Glendale: rescored 2026-08-04 → social_fabric=52.9 (conf=92, success); composites recomputed with --no-census (zero status_signal drift)

---

## BUG-003 · quality_education = 0 for multiple places
**Severity: HIGH** | Affects: Fort Greene NY, NYC Glendale, Maspeth NY, Pelham Bay NY, Southport CT, LA Glendale CA

**Root cause confirmed (2026-07-28):** These 6 places have `total_schools_rated=0` and `fallback_reason="School scoring disabled"`, while all other 286 LA+NYC catalog places scored correctly. They were rescored in a separate batch pass when `ENABLE_SCHOOL_SCORING=False`. Not a code bug — stale data from a flag-off run.

**Rescore required** (`ENABLE_SCHOOL_SCORING` must be true, rescore by confidence=0 filter):
```bash
cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/rescore_catalog_pillar.py --input data/nyc_metro_place_catalog_scores_merged.jsonl --in-place --pillars quality_education --confidence-filter-pillar quality_education --confidence-filter-lt 1
```
```bash
cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/rescore_catalog_pillar.py --input data/la_metro_place_catalog_scores_merged.jsonl --in-place --pillars quality_education --confidence-filter-pillar quality_education --confidence-filter-lt 1
```
Then recompute composites on both catalogs.

---

## BUG-004 · natural_beauty = 0 for Denver, Newport RI, Las Vegas, Newport CT, Glendale CA
**Severity: MEDIUM** | All flagged 3.2σ below suburban mean (65.6±20.6)

Denver has the Rockies visible from the city. Newport RI has ocean views and coastline.
0.0 is not defensible for either.

| Place | NB |
|---|---|
| Denver, CO | 0.0 |
| Newport, RI | 0.0 |
| Las Vegas, NV | 0.0 |
| Glendale, CA | 0.0 |

**Likely cause:** same as BUG-001/002 — null coerced to 0, or a GEE/terrain query failed
silently and wrote 0 instead of null.

**Fix requires:** check natural_beauty breakdown (tree_canopy, terrain_variety, water_proximity)
for these places in the stored JSONL to see which sub-component zeroed.

---

## BUG-005 · Transit near-zero for Canarsie and Coney Island (NYC urban)
**Severity: HIGH** | Canarsie=2.6, Coney Island=3.0 vs. urban_residential mean 84.1 (3.9σ)

Both are served by NYC subway (L train and D/F/N/Q respectively). Transit=2-3 in an NYC
urban_residential place is impossible — these have more transit access than most US cities.

**Likely cause:** transit fetch failed or returned empty for these specific census tracts,
and the commuter-access floor (which requires transit ridership data) also failed to apply.

**Fix requires:** inspect public_transit_access breakdown for both places in the JSONL;
confirm whether commuter_floor was applied and what the GTFS/commute lookup returned.

---

## BUG-006 · Sleepy Hollow air_travel = 58 (5.2σ below urban_residential mean 94.3)
**Severity: MEDIUM**

Sleepy Hollow is 30 miles from JFK, LGA, and EWR. air_travel=58 for an NYC suburb is wrong.

**Fix requires:** check air_travel breakdown (nearest airport distance, # airports in radius)
for Sleepy Hollow to see if it got classified with wrong coordinates.

---

## BUG-007 · Overpass errors → score collapse (no fallback triggered)
**Severity: MEDIUM** | Affects: 68 places total

Places with confirmed overpass_error/overpass_empty outcomes AND pillar score < 40:
Moab, San Francisco, Philadelphia, New Orleans, Santa Monica, Provincetown, Charleston SC,
Malibu, Washington DC, Pasadena CA, Santa Fe, South Lake Tahoe, Bar Harbor, Austin TX,
Virginia Beach.

These aren't all wrong scores — some may be legitimately low — but the Overpass failure
should have triggered the Google Places AO fallback, and apparently didn't for many of them.

**Fix requires:** for each flagged place, check `places_ao.triggered` and `places_ao.reason`
in the AO breakdown to confirm whether fallback fired and whether it recovered the score.

---

## BUG-008 · economic_security outliers in LA urban_residential
**Severity: LOW** | Van Nuys=76.0 (4.8σ), Playa del Rey=76.5 (4.5σ), Palms=77.3 (4.1σ)

urban_residential economic_security mean is 84.9±1.9 — it's extremely tight.
These three LA neighborhoods are ~9 points below. Could be legitimately lower opportunity
access (Van Nuys is further from job centers), or a metro-baseline mismatch.

**Fix requires:** confirm whether LA metro baselines were applied correctly vs. NYC metro;
check if the gravity model is using the right employment center data for LA.

---

---

## BUG-009 · Summit community_safety = None coerced to 0
**Severity: HIGH** | ✅ FIXED 2026-08-04 | Affects: 10 places (Summit, Hempstead, Sleepy Hollow, Southport, Glendale NY, Pelham Bay NY, East LA, Lakewood, Palos Verdes Estates, Rancho Palos Verdes)

**Root cause:** Original scorer wrote `contribution = round(None × weight, 2) = 0.0` for pillars
with `score=None`. The recompute script treated this stored `0.0` as an authoritative contribution
and summed it into `_stored_total`, penalising places as if the pillar scored 0.

**Fix (`pillars/composite_indices.py`):** Detect stored-gap pattern (`contribution=0.0 AND score=None
AND weight>0`) and exclude from denominator; scale up `_stored_total + _recomp_total` by
`100 / (100 - gap_weight)` to fill the hole. `data_gaps` field now includes these pillars.

**Fix (`scripts/catalog/rerun_failed_catalog_pillars.py`):** `recompute_totals` now writes
`contribution=None` (not 0.0) for score=None pillars, and renormalises total_score over
available weight only — prevents recurrence.

**Result:** Summit 65.73 → 71.71. All 10 affected places rescored; `data_gaps` field populated.

---

## BUG-010 · Rye matched to wrong police agency (Johnson City Village PD)
**Severity: HIGH** | ✅ FIXED 2026-08-04

**Root cause:** `city_hint="Rye City"` → the word "City" (4 chars, passed `len > 3` filter) matched
"Johnson **City** Village Police Department", producing a false-positive `nibrs_city_match`. Also,
`_find_nibrs_agency_by_name` couldn't find "Rye City PD" because "Rye" (3 chars) was filtered
out by the same `len > 3` guard.

**Fix (data_sources/crime_api.py):**
- Added `_CITY_HINT_GENERIC` frozenset (`{"city", "town", "village", "county", ...}`) to exclude
  generic place-type words from city name → agency name matching
- Changed `len(word) > 3` to `len(word) >= 3` in `nibrs_city_match` and `_find_nibrs_agency_by_name`,
  with `_CITY_HINT_GENERIC` exclusion applied

**Result:** 78.2 → 74.4, source switched from `fbi_nibrs_agency / Johnson City Village PD`
to `ny_state_ucr / Rye Brook Vg PD` (Westchester County, correct jurisdiction).

---

## BUG-011 · CT places passing political lean filter with null lean
**Severity: MEDIUM** | Confirmed: New Canaan, Old Greenwich, Weston

All three show `lean_2024 = None`, `pl.score = None`, `display_label = None`.
Known from memory: CT political lean data has only ~8 values statewide (near-useless).
The filter is letting these through with "?" display rather than excluding them cleanly,
so the Explorer shows a lean value that is actually unknown data, not a real signal.

**Fix requires:** ensure places with `lean_2024 = None` are explicitly excluded from any
lean-based filtering/display rather than displaying as ambiguous — they are not moderate,
they are unscored.

---

## BUG-012 · NB water_score not surfaced at top-level — preference re-weighting runs blind
**Severity: HIGH** | Confirmed: affects all places in merged JSONL

`natural_beauty.breakdown = {}` and `natural_beauty.summary = {}` for all catalog records.
The actual `water_score` (e.g. 97.43 for Battery Park City) and `water_type` (e.g. "bay")
are stored deep inside `v9_breakdown` and `natural_context`, but not promoted to a
top-level field that the NB preference re-weighting logic can read.

**Result:** ocean/waterfront preference re-weighting is running on `water_score = None`
for every catalog place, meaning the re-weighting is either silently no-oping or
applying a default — not actually adjusting for water type.

**Stored evidence:** `breakdown = {}`, but `v9_breakdown.water_score = 97.43` and
`natural_context.water_type = "bay"` exist — correct data is there, just not at the
path the re-weighting code reads.

**Fix requires:** either promote `water_score` and `water_type` to the top-level NB
breakdown dict in the scorer output, or update the re-weighting code to read from
`v9_breakdown` directly.

---

## Run the detector

```bash
python3 scripts/audit/scoring_anomaly_detector.py
python3 scripts/audit/scoring_anomaly_detector.py --sigma 1.5  # more sensitive
```
