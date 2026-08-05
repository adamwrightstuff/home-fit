# Scoring Bug Backlog

Populated 2026-07-27 via `scripts/audit/scoring_anomaly_detector.py` (empirical, not code review).
No rescores done yet — all catalog values are as-stored.

---

## BUG-001 · Vacation AO collapse (systemic)
**Severity: HIGH** | ✅ LARGELY FIXED 2026-08-04

Metro catalogs (Explorer): all clean — NYC/LA/SF all have AO ≥ 19. Santa Monica, Pasadena
fixed in prior sessions.

Vacation Explorer: rescored 2026-08-04 via `force_rescore_vacation_pillars.py` (local API).

| Place | AO before | AO after |
|---|---|---|
| Washington, DC | 3.7 | 67.0 |
| New Orleans, LA | 1.9 | 88.6 |
| Virginia Beach, VA | 8.3 | 49.4 |
| Vail, CO | 29.4 | 86.3 |
| Moab, UT | (low) | 45.3 |
| Malibu, CA | (low) | 62.0 |
| Provincetown, MA | (low) | 47.5 |
| Bar Harbor, ME | (low) | 77.0 |

**Residual:** Charleston, SC AO=0.0 (conf=0) — persistent Overpass failure, not transient.
City parks not queryable; no fallback rescued it. Low priority (flat coastal city, AO may
legitimately be moderate).

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
**Severity: HIGH** | ✅ FIXED 2026-08-04 | Canarsie=2.6, Coney Island=3.0 vs. urban_residential mean 84.1 (3.9σ)

Both are served by NYC subway (L train and D/F/N/Q respectively). Transit=2-3 in an NYC
urban_residential place is impossible — these have more transit access than most US cities.

**Root cause (2026-08-04):** Transitland API returned 0 routes for both coordinates at scoring
time (transient API failure / data gap). All route counts stored as 0. Commuter-access floor
did not help — it requires `commuter_count > 0` (commuter rail suburbs only, not subway places).
The stored `contribution=0.0` was the bug. Transitland now returns 10 routes for Canarsie and
15 for Coney Island at the same coordinates (1500m radius, same area_type=urban_residential).

**Fix applied (2026-08-04):** Rescored `public_transit_access` for both places
(`HOMEFIT_TRANSIT_STABLE_COMMUTE=true`); recomputed composites (`--no-census`, zero
status_signal drift). Propagated to `composites_recomputed.jsonl`.

**Result:**
- Canarsie: transit 2.6 → 49.6 (1 heavy/L train + 11 bus), total_score → 59.43
- Coney Island: transit 0.0 → 61.5 (5 heavy/D+F+N+Q + 8 bus), total_score → 74.33

---

## BUG-006 · Sleepy Hollow air_travel = 58 (5.2σ below urban_residential mean 94.3)
**Severity: MEDIUM**

Sleepy Hollow is 30 miles from JFK, LGA, and EWR. air_travel=58 for an NYC suburb is wrong.

**Fix requires:** check air_travel breakdown (nearest airport distance, # airports in radius)
for Sleepy Hollow to see if it got classified with wrong coordinates.

---

## BUG-007 · Overpass errors → score collapse (no fallback triggered)
**Severity: MEDIUM** | ✅ FIXED 2026-08-05 | Affects: 22 places (reduced from original 68 estimate)

All 22 had `places_ao.reason=disabled_or_no_key` and `daily_urban_outdoors=0` due to local
Overpass query failures. `wild_adventure` and `waterfront_lifestyle` were partially populated
from working queries. Google Places AO fallback was off at scoring time — not a code bug.

**Fix applied:** rescored `active_outdoors` for all 22 with fresh Overpass (transient failures
cleared). Walnut Creek threw ValueError on rescore — retained pre-rescore value (38.9/conf=90).
Newark and South San Francisco still have local+trail Overpass errors but regional ok; scores
30.1 and 27.3 are plausible for flat industrial suburbs.

| Metro | Places fixed |
|---|---|
| SF (17) | Atherton, Campbell, Evergreen, Excelsior, Foster City, Kentfield, Los Altos Hills, Mill Valley, Newark, Orinda, San Bruno, San Ramon, Santa Clara, South San Francisco, Sunnyvale, Walnut Creek (retained), Willow Glen |
| NYC (2) | Ditmas Park, Ridgewood |
| LA (3) | Little Tokyo, Pasadena, West LA |

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
