# Work Commute Playbook (adding a metro)

How to give a new metro the "Where do you work?" commute feature: job hubs, precomputed
weekday-morning commute times from every catalog place, and station access context.
Written from the NYC build (Sept 2026), including the mistakes, so the next metro skips them.

Scope: runs after the metro's catalog is scored (see `METRO_EXPANSION_PLAYBOOK.md`).
User-facing units are always miles, minutes, feet, °F.

---

## How the feature works (so the steps make sense)

1. User types a work address. It's geocoded by the backend `/geocode` (Census, then OSM; free, cached).
2. The browser snaps it to the nearest **job hub** (`frontend/lib/workZones.json`) within 15 mi.
3. Place cards and the commute filter use **precomputed** times to that hub stored on each
   catalog row as `work_commute[zone_id] = {transit, transit_centroid, transit_station, drive}`.
4. No Google call happens at request time. Google is only used by the offline batch script
   `scripts/manual/add_work_zone_commutes.py`.

---

## Step 1. Choose hubs from job data, not intuition

NYC lesson: the first 9 hubs were picked from general knowledge and left a ~440k-job gap
(Flatiron, Union Square, SoHo) between 34th St and FiDi. Always pick from data.

**Data:** Census LEHD LODES8 Workplace Area Characteristics (WAC), latest year, `S000_JT00`,
plus the state crosswalk for block lat/lon and CBSA.
`https://lehd.ces.census.gov/data/lodes/LODES8/{st}/wac/{st}_wac_S000_JT00_{year}.csv.gz`
`https://lehd.ces.census.gov/data/lodes/LODES8/{st}/{st}_xwalk.csv.gz`
Download every state the CBSA touches. Filter to the metro's CBSA code(s).

**Method:**
1. Measure current coverage: share of metro jobs within 0.6 mi of any hub.
2. Greedy add: grid job blocks into ~0.3 mi cells; repeatedly add the cell center that covers
   the most still-uncovered jobs within 0.6 mi. Stop when the next hub adds < ~100k jobs
   (large metro) or < ~25k (small metro). In NYC the top 3 adds were 243k, 203k, 194k; the
   4th dropped to 98k.
3. Move each chosen point to the nearest **major transit interchange** in that cluster
   (e.g. Union Square rather than the 23rd St grid centroid): same coverage, realistic routing.
4. Keep secondary CBDs that suburban commuters actually go to (White Plains, Stamford, Newark)
   even though their coverage is small.
5. Expect a ceiling: most metro jobs are dispersed (NYC: ~78% of jobs are not within 0.6 mi of
   any hub). Hubs serve office-cluster commuters; everyone else sees the snap-distance warning.

**Mark `transitOnly: true`** for hubs where driving + parking is unrealistic (Manhattan,
Downtown Brooklyn, LIC, Jersey City in NYC; likely SF FiDi and SoMa). The filter then ignores
drive time there. Google drive times never include parking.

---

## Step 2. Get origins right

Every catalog place is routed from **two origins** and the faster transit time is kept:

- **Town centroid** (catalog lat/lon). Catches bus routes that beat the train
  (NJ towns to Port Authority).
- **Rail station**, for commuter-rail towns.

**Use station coordinates, never station names as text.** NYC lesson: Distance Matrix
silently resolved "Ridgewood Train Station, Ridgewood, NJ" to the ZIP code center and
"Morristown Train Station" / "Mount Kisco ... Station" to the town center. Nothing errors;
`origin_addresses` in the response is the only tell.

Station coordinates, in order of preference:
1. The agency's GTFS `stops.txt` (authoritative).
2. OpenStreetMap: one Overpass bbox query for `railway=station|halt` across the metro, then
   match by name locally. Exclude `railway=service_station` (NYC: matched "Stamford Yard").
3. Google Geocoding only as a cross-check. It returned a street, parking lot, town center or
   ZIP for 17 of 75 NYC stations.

Station lists per metro live in `scripts/manual/fix_cbd_station_coords.py`
(`NYC_STATIONS`, `SF_STATIONS`, `LA_STATIONS`). Towns that were deliberately excluded there
(e.g. Monrovia, Cold Spring Harbor) stay excluded.

---

## Step 3. Time sampling

- Day: next **Tuesday** (avoids Monday holidays), metro-local timezone.
- Dense, frequent rail (NYC): `arrival_time` at 8:30, 9:00, 9:30; keep the minimum.
  Fallback: if the best is missing or > 150 min, also try `departure_time` 8:00.
- Sparse schedules (SF, LA): use `departure_time` samples instead (e.g. 7:30, 8:00, 8:30).
  `arrival_time` inflates times there (existing CBD pipeline convention).
- Drive (non-transitOnly hubs only): `departure_time` 7:30 and 8:15, `traffic_model=best_guess`.
- Google `ZERO_RESULTS` is stored as `null` so re-runs don't re-query it (e.g. Weston CT).

---

## Step 4. Budget before you run

Google Maps Platform free caps reset on the 1st of each month:
10,000 elements on "Distance Matrix" (transit, walking, plain driving) and
5,000 on "Distance Matrix Advanced" (traffic-aware driving). Over that: $5 and $10 per 1,000.

Element math per metro:

```
transit  = (places + station_towns) x hubs x samples      (+ worst-case fallback: 1 per place per hub)
drive    = places x non_transitOnly_hubs x 2
```

Check what's left: Cloud Console -> Billing -> Reports, current month, group by SKU.
The script refuses to run past `--free-left transit=N,drive=N` (worst case counted up front).
Other scripts share the same SKU (e.g. the CBD commute scripts), so always read the report.

---

## Step 5. Run with gates

For each batch (centroid pass, then `--station-origins --only-station-towns` pass):

1. `--dry-run`: prints every origin, destination, day and time, element counts. Review it.
2. Pilot: `--places "A,B,C,D,E"` (mix of rail towns, bus towns, city neighborhoods).
   Checks: the hub nearest the old CBD pin should match stored `cbd_transit_minutes` within
   ~5 min; a hub 1 subway ride from a terminal should be terminal time + 10 to 15 min.
3. Full run. Then: every place has every hub key; count nulls; spot-check min/median/max.
4. Origin check for station towns (a few elements): request once with the origins and read
   `origin_addresses`; any town or ZIP answer means the station origin is wrong.

---

## Step 6. Station access context (door to platform)

Commute times start at the platform for rail towns. Show typical access time separately.

**Best source: the agency's own rider survey** (actual reported access mode and minutes):
- Metro-North 2017 Origin-Destination Survey (East of Hudson): `Q5_EAST` station, `Q6` minutes
  to station, `Q7_*` access mode, weight `Level_1_linked_weights` (drop blank weights).
  Filter: home origin, AM Peak, commuting to work. From `mta.info/transparency/surveys`.
- LIRR 2012-14 O-D Survey: `Q7` station, `Q8` access mode. No access minutes.
- Other metros (verify availability before relying on them): BART Station Profile Survey,
  Caltrain rider survey, Metrolink 2018 O-D study, Sound Transit rider surveys.

**Why the survey beats a model:** riders self-select. People far from the station drive,
people who walk live close. NYC: the Census home-distance model put Larchmont at a 9 to 21 min
walk; surveyed Larchmont AM commuters actually take a median 6 min (middle half 5 to 10),
48% walk. Across all 34 surveyed NYC-catalog Metro-North stations, the median access time is
7 min and the middle half tops out around 10 min, while the walk-everyone model ranged up to
50+ min for spread-out towns (Fairfield, Westport, Bedford). The model is wrong in kind, not
degree: far-away residents drive. Model only where no survey exists, and calibrate it against
a surveyed metro. Surveys are dated (MNR 2017 predates COVID and Grand Central Madison); note
the year in any UI copy or tooltip.

**Fallback model (no survey):** LODES Residence Area Characteristics (RAC, employed residents
by home block) inside the town's Census place or county subdivision, distance to the nearest
station (not just the one the commute starts from; 17 NYC towns have a closer station for many
residents). Street distance factor and speeds must come from routed samples (OSRM:
`routing.openstreetmap.de/routed-foot|routed-car/table`), not assumptions.

---

## Step 7. Ship

1. Add the metro's hubs to `frontend/lib/workZones.json` (the picker only shows hubs that have data).
2. Copy `data/*.composites_recomputed.jsonl` and `data/catalog_climate_profiles.jsonl` to `frontend/data/`.
3. Verify locally: snap a known office address, filter counts match the data, card shows both modes.
4. Commit, push, `cd frontend && vercel --prod`.
5. Verify live: `/api/catalog-map?metro=<metro>` rows carry `work_commute`.

---

## Per-metro checklist

- [ ] LODES WAC + crosswalk downloaded for all states in the CBSA
- [ ] Hubs chosen by greedy coverage; pinned to interchanges; `transitOnly` decided
- [ ] Station coordinates from GTFS or OSM (not text); excluded towns carried over
- [ ] Sampling mode chosen (arrival vs departure) per existing CBD convention
- [ ] Element budget computed; free allowance read from Billing -> Reports
- [ ] Dry run reviewed, pilot matches stored CBD times, full run, origin check
- [ ] Station access: survey located and parsed, or fallback model calibrated
- [ ] Deployed and verified live

## Known gaps / follow-ups (NYC)

- Station origins for Ridgewood, Morristown, Mount Kisco (and likely Chatham) resolved to town
  or ZIP centers in both `work_commute` and the older `cbd_transit_minutes`. Re-run those
  station passes with OSM coordinates.
- Hub-selection and station-access analysis currently run as ad-hoc scratch scripts; promote
  them to `scripts/work_commute/` (hub coverage, station coords, survey parsing) before the
  next metro.
