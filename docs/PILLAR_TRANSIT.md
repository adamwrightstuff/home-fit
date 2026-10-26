# Pillar Deep-Dive: Public Transit Access

How `pillars/public_transit_access.py` scores a location today, end to end. This pillar has
the most moving parts (supply model + commuter floor), so it gets its own page.

## What it measures
Transit **service supply and commute access** at a point — how much frequent, useful transit
is reachable, plus a credit for genuine rail-commute towns. It is NOT a commute-time pillar
(that lives in the Happiness index) and NOT a ridership survey.

## Inputs
- **Transitland** `/routes` near the point (route_type per route) — the primary signal.
- **Transitland** stops/schedules — used for optional bonuses (often absent).
- **Census ACS** — mean commute time (`DP03_0025E`) and tract transit mode share
  (`B08301`, via `get_transit_mode_share`) for the commuter-access floor.
- ⚠️ The live route fetch is **noisy under load** — it can undercount (Astoria → 2 subway
  lines on a bad pass). Do not trust a single live pass as ground truth. See
  PILLAR_DATA_QUALITY / the transit-fetch-noisy memory.

## Scoring flow

### 1. Classify routes (GTFS `route_type`)
- `1` → **subway** (frequent, all-day, walk-to)
- `2` → **commuter rail** (peak-oriented, often drive-to)
- `0` → light rail / tram
- `3` → bus

`heavy_rail_routes` is kept as the union of subway+commuter for back-compat; summaries expose
`subway_routes` and `commuter_rail_routes` separately. Splitting these (v3) was the key fix —
the old model lumped them, so one suburban commuter station scored like a subway hub.

### 2. Absolute service-supply model (v3)
```
weighted = 3·subway + 1·commuter + 2·light + 0.7·bus
base_supply = 100 · min(1, log(1+weighted) / log(1+ANCHOR))    ANCHOR = 120
```
- Weights reflect real daily service: subway ≫ commuter (peak-only) ; light rail > bus.
- Absolute (not expectation-relative) so supply, not a low suburban bar, sets the score.
- Validated vs Walk Score Transit Score: MAE ~9.7 (East Village 100, Park Slope 96,
  Astoria 91, Darien ~31 before the floor).

### 3. Schedule-based bonuses (when data present)
Frequency / weekend / **hub-connectivity (Grand Central)** / commute / destination-diversity
bonuses (`total_score + total_bonus`). These need Transitland schedule + headsign data, which
is **frequently absent** — the hub-connectivity bonus in particular usually returns `None`.
Treat them as opportunistic, not load-bearing.

### 4. Station-distance commuter floor — ⚠️ effectively DEAD
A suburban fallback (`area_type in suburban/exurban/rural`, score < 50) bases a score on
`_nearest_heavy_rail_km`. That function **returns `inf` for most commuter towns** (it can't
locate the Metro-North/LIRR/NJT station in the town center), so it falls through to "no rail"
(base 20) and never lifts them. Left in place but does little; superseded by step 5.

### 5. Commuter-access floor — ridership-weighted (the current commute credit)
The reason people choose Pelham/Bronxville/Larchmont. For a commuter-rail town
(`commuter_rail_routes > 0`, `subway_routes == 0`, score < 85):
```
ridership_ramp = clamp((transit_share − 0.05) / 0.25, 0, 1)     # 0 at 5%, full at 30%
floor = _score_commute_time(commute_min, area_type) · ridership_ramp
total_score = max(total_score, floor)
```
- **`transit_share`** is tract-level ACS B08301 (`get_transit_mode_share`) — NOT
  `get_economic_geography` (which is CBSA/whole-metro and would return one value for everyone).
- **No artificial cap.** A short *car* commute earns no transit credit (low share → low ramp);
  a town where people genuinely take the train does. Self-limiting, naturally below subway hubs.
- Results (with FRESH commute, post-fix): Harrison 62, Greenwich 61.8, Rye 60.7, Bronxville
  58.9, Darien 56.6, Larchmont 56.1; New Canaan 22.7 (12% share), Norwalk stays at supply (2%
  share). Subway places excluded (`subway_count == 0`). A tight, sane band — not the 83 outlier
  the stale-commute bug produced.
- History: a hard `min(70)` cap was tried first and rejected as artificial; replaced by
  ridership weighting. **Don't reintroduce the cap.** See transit-commuter-access-floor memory.

## Catalog application
The catalog is rescored offline (not via live fetch — too noisy):
- `scripts/rescore_transit_split.py` → v3 supply from stored route counts.
- `scripts/apply_commuter_access_floor.py` → the ridership-weighted floor, using FRESH `get_commute_time` + tract transit-share (scripts/fix_commuter_floor_fresh.py).
  NOTE: the original apply_commuter_access_floor.py used the *stored* Happiness commute, which was
  stale for 36% of places (Harrison 83→62) — do not use it; use the fresh-fetch script. Run it **after** the v3 rescore
  (it floors the v3 supply). See CATALOG_RESCORE_RUNBOOK.

## Where it feeds
- `total_score` (one of the 14 livability pillars).
- NOT the Happiness `commute` component — that's a separate commute-minutes channel. So a
  great-commute town gets its commute value mostly via Happiness; the transit pillar credits
  it via the commuter-access floor.

## Gotchas
- Live vs catalog can differ because the live route fetch is noisy and the catalog uses stable
  stored counts. See LIVE_SCORER_VS_EXPLORER.
- Mixed subway+commuter hubs (PATH + NJ Transit, etc.): `subway_count > 0` excludes them from
  the commuter floor (correct — they already score high on subway supply).

## Failed reads and fallbacks (changed 2026-10-26)
A failed Transitland read (no key, HTTP error, timeout) or a failed OSM railway-station read after an empty Transitland answer now raises `TransitReadError`, so the pillar shows as no data and is retried; it is no longer scored as 0. A 200 answer with no routes and no OSM station is a real zero, marked `summary.no_service_found` and `no_transit_routes_found` in the data warnings. The invented fallback scores (15/12, 10/10, 5/8 plus 5% of a commute score) were removed.

Catalog: 273 places (169 stored as 0, 104 carrying the fallback) were re-read live. All 273 reads succeeded. 269 are confirmed no service within the search radius (166 stayed 0, 103 fallback places went from a mean of 23 to 0); 4 had real service the stored value missed (Pelham Bay 0 to 63, Glendale 0 to 55, Southport 0 to 14, Cedar Park 17 to 18). Total score moved -1.7 on average for the 104 fallback places and -0.5 across the 273. Caveats: the zeros are zeros inside the radius (1.5 km exurban and rural, 2 km suburban, 3 km urban core); Acton (MA) has one route at 2 km and Weston five at 5 km, so the radius, not a failed read, explains those zeros (a measurement-area question, audit P3). The data-quality assessor still gives confidence 0 to any empty transit read, so the 269 confirmed zeros keep confidence 0 in the catalog.

## Supply-only score and validation (changed 2026-10-26)
The pillar answers "can I live here without a car?" from service near home. Removed from the score: the legacy suburban layer (hard-coded distance base, connectivity and bus bonuses), the ridership-weighted commuter-access floor, the 5% commute blend and the +5 commute bonus. Commute minutes and score stay on the pillar as informational fields (weight 0) because the frontend uses them as the area-average commute fallback; commute to a workplace is the opt-in commute feature's job, and the area average is carried by the Happiness commute component, so it is counted once. Jobs access by transit (time to the primary job center) is likewise the commute feature's; it is precomputed for New York, San Francisco and Los Angeles only.

Score = 100 x log(1 + weighted routes) / log(1 + 120), weighted routes = 3 x subway + 3 x commuter rail + 2 x light rail + 0.7 x bus routes in range, plus the schedule bonuses that were computed for the place (frequency, weekend service, hub connectivity, destination diversity), capped at 100. The pillar stores the area type it used in `area_classification`.

### Parameters (P4)
| Parameter | Value | Status |
|---|---|---|
| Subway 3, light rail 2, bus 0.7 | judgments | Kept: refits to tract transit commute share did not beat them out of sample or on an independent measure |
| Commuter rail 3 | documented choice, range 2 to 4 | Largest weight at which no validation measure falls more than 0.01 below its value at weight 1 |
| Anchor 120 and log curve | judgment | Only ratios are identified by the data; the level is a judgment |
| Search radius 1.5 to 3 km by area type | judgment, unsourced | Tested 2026-10-26 against published walking catchments (bus 750 m, tram 710 m, subway and rail 1,180 m, the midpoints of published 85th-percentile walks): tract-share Spearman 0.715 vs 0.691, but within-metro 0.488 vs 0.526, no-vehicle 0.615 vs 0.609, pin-shift 95th percentile 13.1 vs 9.6 points, and 359 places move more than 15 points. Not adopted; the current radius stays as a recorded judgment |
| Schedule bonuses | judgments | Present for 9 to 207 places, scaled from small samples; unsourced |

### Validation (P7)
1,471 catalog places; outcome is tract transit commute share (ACS B08301), with households with no vehicle (ACS B25044) as an independent second measure.
- Commuter-rail weight 1, 2, 3, 4, 6: pooled Spearman with transit share 0.668, 0.681, 0.691, 0.696, 0.701; within-metro mean 0.527, 0.528, 0.526, 0.524, 0.517; no-vehicle Spearman 0.615, 0.613, 0.609, 0.606, 0.597.
- A non-negative fitted model of transit share on mode presence and log route counts scores 0.518 held out by metro and 0.593 on no-vehicle households; the formula scores 0.527 and 0.615. Adding peak train frequency or reachable jobs improved held-out fit by under 0.005.
- Walk Score Transit Score for three commuter towns (walkscore.com, 2026-10-26): Harrison 31, Darien 36, Hinsdale 23; our scores after the change 44, 44, 29. Walk Score is a proprietary proxy and is not used as validation.
- Why people ride commuter rail in some towns (230 commuter-only towns): reachable jobs (LODES gravity) correlates 0.38 to 0.75 with tract transit share within metros, peak trains per hour 0.23 to 0.45, income 0.42. Station frequency was pulled for these towns (data not kept; 57 places had stale feeds, 29 in Boston).

### Sensitivity (P6), catalog mean 39.2
Per-place change across the recorded ranges (median / 95th percentile / maximum): commuter rail 2 to 4 weight 0.0 / 4.4 / 7.0; light rail 1 to 3 weight 0.0 / 2.4 / 8.5; subway 2 to 4 weight 0.0 / 3.3 / 6.5; bus 0.5 to 1.0 weight 3.3 to 4.1 / 6.1 to 6.8 / 7.3 (the bus weight moves the catalog mean by 3 to 4 points). Pin-shift test (500 m, 8 bearings, 30 places, 240 shifted points, route counts re-fetched at each point): median change 0, 95th percentile 9.6 points, maximum 24.2 (North Andover). This exceeds the 5-point gate set for the audit, so it is a known limitation: a hard route-count circle is sensitive to pin position. Averaging scores over a ring of points would fix it but costs about nine times the route calls.

### Catalog effect
All 1,476 rows were recomputed offline from stored route counts by `scripts/catalog/recompute_transit_v2_offline.py`: transit mean 41.8 to 39.2, total score -0.17 on average. Commuter-rail towns: Harrison 76 to 44, Darien 68 to 44, Greenwich 62 to 52, Bronxville 59 to 51, Hinsdale 58 to 29. Subway neighborhoods barely move (Astoria 91 to 91).

### Known limits
Route counts do not see line quality (Harrison's tract share is 35% but route counts predict far less); the search radius is unsourced; frequency is only available as bonuses for some commuter-rail suburbs; confirmed zeros keep confidence 0 in the data-quality assessor.
