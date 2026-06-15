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
- Results: Harrison 83 (35% share), Darien 70, Bronxville/Scarsdale 59, Larchmont 56;
  New Canaan 23 (12% share), Norwalk stays at supply (2% share). Subway places excluded
  (`subway_count == 0`).
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
