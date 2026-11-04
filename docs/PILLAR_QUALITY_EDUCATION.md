# Pillar Deep-Dive: Quality Education

How `pillars/schools.py` and `data_sources/schools_api.py` feed the `quality_education` pillar,
and how to score a new metro with it. Written 2026-10-14 after the SchoolDigger Pro re-score of
all six catalog metros. Sections marked **(interim)** are heuristics we expect to replace with the
Census district-boundary lookup (see "Planned: boundary lookup").

## Access model: how each level is scored (2026-10-18) - read this first
`zoned_v1` scores each level by how that level is actually admitted. All inputs are real ratings, enrollment and published
admission rules; nothing is tuned to a target score.
- **Assigned** (zone map or guaranteed resident school): the zoned school's rating.
- **Choice / lottery** (`source: choice_avg`): the enrollment-weighted average rating of the rated district-run schools of that
  level in the pool (at least 3 schools, else the level stays `choice` and is not scored). It describes the schools in the pool, not
  where a given child is placed. The pool is:
  - NYC middle: the home community district's programs from the DOE directory (`data/school_geo/nyc_middle_directory.json`,
    built by `scripts/catalog/build_nyc_middle_directory.py` from the InfoHub "Directory Data" file; refresh every admissions cycle).
    Includes 6-12 and K-8 schools that SchoolDigger files under another level. Schools whose programs are all screened (grades, test,
    audition) are kept out of the average and listed under `selective`. Special-education-only programs are ignored. Home district
    comes from the zoned elementary school's code (fallback: nearest district centroid).
  - NYC high school: every rated NYC school (citywide application). Shown, but left out of the overall score because every
    neighborhood gets the same number (`pool.scope == "citywide"`).
  - Any other level where no zone applies at the point: the district's schools of that level.
- **Lottery districts with attendance-area maps** (`data/school_geo/district_access.json`, read by
  `data_sources/district_access.py`): levels the district fills by application even though it publishes zones. Today only San Francisco
  (all levels; attendance area is a tiebreaker, not a guarantee; source and date are in the file). The level scores as the pool
  average and `attendance_area` keeps the zoned school for display. Add a district only from its own published rules and re-check yearly.
  Consequence: every SF place now gets the same education score; address matters only through the displayed attendance-area school.
- **K-8 schools** also count at the middle level (middle-level copy, same rating) when district-run and not a magnet.
  The zone-less resident-campus averaging (LA) ignores these copies.
- **Panel text**: `summary.level_access` (how each level is admitted) and `summary.best_options` (the four best-rated schools of each
  choice pool with distance, plus screened schools). The best options are a display list, not a score input.
- **Known limits**: the pool treats every school in a district as reachable (District 15 spans Park Slope to Sunset Park); unrated
  new schools are left out; no placement or lottery-odds data, so no claim is made about what a child gets. Metros not yet audited
  against their district rules: Philadelphia high school (38 city places use the 2024-25 catchments, which is a guaranteed seat),
  Seattle, Austin, Chicago, LA (zoned or resident-school logic, unchanged).
- **Not inferred**: a level is `choice` only where the district publishes a current map and none covers the point; a missing or old
  map is never read as a lottery.

## Current model: zoned_v1 (2026-10-15) - read this first
The sections below the Backlog describe the older radius model (kept as the fallback for places with no
Census district data). All six catalog metros are scored with `zoned_v1`:
- **Rating** = SchoolDigger statewide percentile (0-100); stars x 20 only if a school has no percentile.
- **Per level** (elementary, middle, high): the **zoned school** from the district's attendance map
  (`data_sources/school_zones.py`) when the map assigns one and it is rated; otherwise the nearest 3 rated
  non-charter schools of that level in the home district (Census polygon), widening 1x/1.5x/2x the area
  radius up to 3 mi (elementary uses 2.1/3.2 of the radius); then the district's own nearest school up to
  15 mi (small elementary-only / high-school-only districts); then the nearest rated charters.
- **Choice levels** (added 2026-10-16): where a district publishes zone maps but there is no zone for a level at the
  point (NYC high schools and choice-based middle schools, SF middle and high), students apply, so nearby schools say
  little about where a child goes. The level is `source: choice`, not scored (score None), and the nearest 3 are kept as
  `reference` only. The headline averages the levels that are assigned by address; `summary.levels_scored` says
  e.g. "1 of 3 levels (2 by choice, not scored)". `check_education.py` treats choice levels as intentional.
- **Resident campus** (LA): LAUSD guarantees a seat at the resident school; Zones of Choice, magnets and permits are by
  application. Large LA high schools are several small schools in one building sharing one zone, so every school on the
  resident campus is averaged. Zones listing two schools (NYC '10X363,10X447') average both.
- **NYC**: the zone's own community school district is loaded too (`_nyc_csd_ids_by_number`), because a zone often
  assigns a school in the neighboring district.
- **Headline** = mean of the scored level scores. No bonuses: the early-education bonus carries 0 points (see "Early-education access" below). A place with no rated school at any level is **no data** (score null, status no_data, degraded), never 0.
- **Charters and choice** are listed in `breakdown.choice` and scored separately: `split.public` is the
  headline, `split.charter` the mean of the nearby rated charters (thin below 3). The Explorer filter
  (any / public_only / charter) switches between them.
- **Stored**: `breakdown.levels` (source, score, schools, zone name + vintage), `choice`, `rated_schools`,
  `districts`, `split`, `model`.
- **Data** (2026-10-16): no per-place SchoolDigger calls. `data/school_snapshot/<ST>.json.gz` holds every school in
  9 states (CA, CT, IL, IN, NJ, NY, PA, TX, WA; 54,000 schools, 2.8 MB, 112 calls, fetched 2026-10-16). SchoolDigger
  returns 500 schools per request, so a state is 3 to 28 calls. Districts, charters and distances are computed locally.
  Refresh once a year (ratings update yearly): `scripts/catalog/fetch_school_snapshot.py --states NY,NJ,...`; a new
  metro in a covered state costs 0 calls, a new state costs about 3 to 28.
- **Geography** (production reads the slim bundle `data/school_geo/`, 10.8 MB, built from the raw downloads by
  `scripts/catalog/build_school_data_bundle.py`): Census school district polygons (which district), Census place outlines
  (hamlet fix: when the point's district covers 25% or less of a small named place and another district covers 50% or
  more, the place's district wins; Cold Spring Harbor, Mamaroneck, Southport), zone maps, NYC school-code names.
  Raw downloads live in the git-ignored `data_cache/`.
- **Zone maps** (`data_sources/school_zones.py`): Chicago (elementary 2025-26, high 2024-25), Austin (2021-22 / 2020-21,
  likely stale), SF elementary (2024-25), NYC (2024-25; high school only the few catchment zones), LA (2018 / 2020,
  no names: the school is found by the campus inside the zone), Seattle (2023-24). A zone's school is matched by name,
  then by location (campus inside the polygon), so naming differences do not matter.
- **Re-score offline** (5 seconds, 0 calls): `PYTHONPATH=. python3 scripts/catalog/rescore_education_offline.py`, then
  `enable_education_weight.py`, `recompute_catalog_composites.py --no-census`, `check_education.py`. Only re-run the
  API-based `daily_education_rescore.py` when the snapshot or the formula changed in a way the offline path cannot reach.
- **Explorer**: the school deal-breaker is now 50 (the 3-star band is exactly the 50th to 70th percentile); the details
  show which schools count, levels covered and zone map year.
- **Known exceptions** (data gaps, `data/education_check_exceptions.json`): Babylon (no rated high school), Edgewater
  (K-8 district), Belvedere.
- **State names**: the API passes "New York"; `normalize_state` makes it "NY" (this once sent every place to the legacy lookup).

## What it measures (owner decisions 2026-10-26, DPv2)
**Construct:** the quality of the school a child at this address would be assigned to (the zoned school, else the nearest
rated schools of the home district; lottery levels show the district pool average), measured by statewide test-score percentile.
**Frame:** within-state percentile (relative). It is comparable only inside a state, not between, say, CT and FL.
**Weight:** an equal 1/13 share for everyone, an owner judgment with no source. **Pin sensitivity:** a 0.5 mile pin shift moves the
score a median 5.8 points (p95 42.9, 2026-10-25). Each place stores `breakdown.pin_sensitivity` (largest and mean change over
0.5 mile shifts north, south, east and west) and a place whose largest change exceeds 15 points (owner judgment, no source;
387 of 1,472 places) carries `data_warnings` "pin_sensitive" and `summary.pin_sensitive`. Build or refresh it with
`scripts/catalog/compute_education_pin_sensitivity.py` (offline); re-run it after any `rescore_education_offline.py`, which drops it.
Spec sheet: see "DPv2 spec sheet" at the end of this doc (supersedes `analysis/education_spec_sheet_2026-10-26.md`). Unsourced parameters (radii, nearest-3, caps, pool average) are TODOs.

## Data-limit flags (2026-10-26)
`scripts/catalog/flag_education_data_limits.py` (offline, idempotent, scores unchanged) writes, from the stored levels:
`degraded` with `quality_education_levels_missing` where a level has no rated school and the score comes from the other levels
(32 places); `zone_map_2015_16` warning where a level uses the 2015-16 attendance survey, about 10% of whose zones may have
changed (1,023 places); `no_zone_map` warning where a level is scored from the nearest schools (364 places). Re-run it after
any `rescore_education_offline.py`, which replaces the breakdown.

## Early-education access (2026-10-25)
`breakdown.early_ed` stores kindergarten and childcare facilities within 2 km and 800 m of the pin and the nearest distance
(OpenStreetMap, distinct facilities, `amenity` kindergarten, childcare, preschool, nursery). It carries **0 points** until a published
source sizes it. A failed lookup, or a state outside the private Overpass server, is `early_ed_missing`, never a count of 0.
Fill it with `scripts/catalog/requery_early_ed.py`, then `rescore_education_offline.py --no-osm`.

## Legacy radius scoring (`pillars/schools.py`, `_get_school_data_legacy`; only for places with no Census district data)
The numbered rules below are the older model, kept as the fallback. The early-ed bonus in rule 4 is no longer applied (0 points).
1. Every school SchoolDigger returns for the place is rated from `rankHistory[0]`:
   `rankStars * 20`; a 0-star school falls back to its statewide percentile. Schools with no
   rating (most private schools, brand-new schools) are ignored. Ratings of 20 or less are
   dropped when better-rated schools exist in the same set (bleed from outside the area).
2. **Base** = mean of the lower two thirds of ratings. This keeps a few selective or screened
   schools from inflating the score.
3. **Access bonus** = +2 per school rated 85 or more in the upper third, capped at +5.
4. **Early-ed bonus** = 1 / 2 / 3 points for 1 / 2 / 3+ preschools or kindergartens within 2 km
   (OSM), times 0.7 if the nearest is over 1 km away.
5. Total = min(100, base + access + early_ed).

No exceptions for specific cities. Radii and thresholds adapt to area type only.

### What is stored
- `breakdown.rated_schools`: **every** rated school that fed the score, as
  `{name, level, rating, is_charter_school}`. This is the source of truth for any re-slicing
  (public only, charter only) without another API call.
- `by_level`: top 3 per level, for display only. Do not derive scores from it: the base score
  is built from the lower two thirds, which are exactly the schools `by_level` drops.
- `is_charter_school` comes from SchoolDigger's `isCharterSchool` flag. Independent charters
  have their own district ID; charters run by a district carry that district's ID.

## Which schools count (`schools_api.get_schools`, **interim**)
The goal is schools that serve the place, not every school nearby. SchoolDigger cannot say
which district contains an address on the Pro plan (the address lookup, `boundaryAddress`, is
Enterprise only), so the lookup is a priority chain. A result is accepted when it has at
least `MIN_RATED_SCHOOLS` (3) rated schools; a thinner result is kept as a fallback candidate
and only used if nothing better is found.

| Step | Rule |
|---|---|
| 0. NYC | Place inside the five boroughs: nearest Community School District by centroid, query by `districtID`. |
| 0.5 Named district | If the geocoder's city differs from the requested place name (Cold Spring Harbor is labelled "Huntington"), use the K-12 district whose name contains the place name. K-8 only and high-school-only districts are skipped because they cover half the schools. |
| 1. City query | SchoolDigger `city=` query, filtered to the modal district. Rejected if the nearest district to the coordinates differs (hamlet guard). If thin, widen to that town's **own district only** by `districtID`. Never widen by distance and never to a neighboring district. |
| 2. ZIP query | Schools in the ZIP, distance filtered, then home-district filtered. Skipped for Los Angeles proper (LAUSD returns the same schools for every neighborhood). |
| 3. Coordinate query | Schools within the area radius, **sorted nearest first** (`sortBy=distance`; the default is alphabetical and a 50-school page in a dense area is just the A to C names), then home-district filtered. |

- **Home district** = most common district among the 5 nearest rated public schools. Independent
  charters and private schools are kept; everything else outside the home district is dropped.
- **District lookup** uses the v2.1 districts endpoint with `sortBy=distance`, districts with
  boundaries first. The v1 endpoint ignores distance and returns an alphabetical page of the
  state, so index 0 was never the nearest district.
- **Radius by area type**: urban_core 1.5 mi, suburban 2.0 mi, exurban/rural 3.0 mi
  (`radius_profiles`). **Elementary schools use 2.1/3.2 of that radius** (about 0.66), from the
  2017 NHTS median school trip: elementary 2.1 mi, middle 3.2 mi, high 3.6 mi
  ([PBIC brief](https://www.pedbikeinfo.org/cms/downloads/PBIC_InfoBrief_NHTS.pdf)).
  Middle and high keep the full area radius. These radii are our own conservative choice, not
  an empirical neighborhood boundary; the research supports the level ratio, not a tighter radius.

## Weight and the Live-vs-Explorer divergence
- The catalog carries education at an equal share of the default 13 pillars (about 7.7%).
  The live `/score?only=quality_education` call returns weight 0, so **every rescore that
  merges a live pillar response zeroes the weight**. After any education rescore run
  `scripts/catalog/enable_education_weight.py`.
- A default pillar with no data keeps its weight at contribution 0 and the total is scaled by
  100/(100 - gap weight), the same convention the health check uses. Education itself is left
  out (weight 0) when it has no usable score.
- Live default: confirm `ENABLE_SCHOOL_SCORING` in `main.py` and
  `docs/LIVE_SCORER_VS_EXPLORER.md`; commit 0c90ad5 turned the live default on once SchoolDigger
  became paid, which older text in this repo still contradicts.

## Re-scoring a metro: runbook
1. Run a dedicated API on its own port so nothing else restarts it:
   `PYTHONPATH=. nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 8010 > api.log 2>&1 &`
   The preview server is stopped by the desktop app after about 35 minutes, and
   `metro_agent health --fix` starts and stops its own API on port 8000. Both killed runs.
2. **Clear stale lookups first.** `get_schools` is cached for 30 days (disk `.disk_cache/` and
   in memory). A bad result (for example a list with no rated schools) is cached and served
   forever, and looks like a quota stop. Delete `.disk_cache` files whose value is a list of
   schools, then restart the API (the in-memory copy survives otherwise).
3. Score: `PYTHONPATH=. python3 scripts/catalog/daily_education_rescore.py --delay 3 --base-url http://127.0.0.1:8010`
   Add metros to `METRO_ORDER`. Places with no `rated_schools` are treated as pending.
   `--force-keys FILE` (JSON list of `metro:key`) re-runs specific places regardless of state.
   A place with no result keeps its old value; the run stops only after 3 failures in a row.
4. `scripts/catalog/enable_education_weight.py`, then
   `recompute_catalog_composites.py --in-place --no-census` per metro file, then
   `check_catalog_health.py --no-unversioned` on every metro file.
5. Compare old and new scores keyed by `(name, search_query)`, **not name alone** (the NYC
   catalog has Ridgewood NJ and Ridgewood Queens). Review the largest movers by hand.
6. The run leaves `.bak`, `.bakEdu` files in `data/`; do not commit them.

## Known limits
- Places in small districts or with mostly private schools can rest on 1 or 2 rated schools
  (51 of 577 after the 2026-10 re-score). They are real, not errors. Low scores in weak
  districts (Lawrence NY, Englewood Chicago, Gary, East Palo Alto) are SchoolDigger ratings
  and have not been validated against an outside source.
- Split elementary and high-school districts (Cupertino plus Fremont Union High, Oak Park) are
  only handled by the radius paths, not by district.
- Belvedere CA has no rated school in range; its schools are in Tiburon just past the radius.
- Enterprise `boundaryAddress` exists on SchoolDigger v3.0 and would return the schools
  assigned to an address. Not available on Pro.

## Boundary lookup (built 2026-10-15; replaced the interim heuristics)
The Census TIGER/Line school district polygons (unified, elementary, secondary) are free and
give the exact district or district pair for any point. SchoolDigger `districtID` values look
like NCES LEA IDs (state FIPS plus 5 digits), which would let the polygon IDs be used directly;
**this match is unconfirmed**. With it, steps 0.5 to 3 reduce to: find the district(s)
containing the point, fetch their schools by `districtID`, apply the area radius only inside
very large districts. That removes nearest-office, name-match and modal-district guesses.

## Public vs charter split
`breakdown.split` = `{public: {score, n_rated, confidence}, charter: {...}}`, computed from every
rated school with the same formula as the total (`pillars.schools.split_scores`, which shares
`score_from_ratings` with the live scorer). The combined score is unchanged and stays the
headline. `confidence`: `ok` (3+ rated), `thin` (1-2), `none` (0, score null).
- Live scorer writes it for new scores. For the catalog run
  `PYTHONPATH=. python3 scripts/catalog/add_education_split.py` (offline, also re-derives every
  stored combined score from `rated_schools` and reports mismatches; 0 of 574 differ).
- Explorer: the existing school-type filter (`any` / `public_only` / `charter`) in
  `frontend/lib/explorerScoreAdjust.ts` now reads the split; payloads without it fall back to
  the old top-3-per-level approximation.
- "Public" means schools without the charter flag. Independent charters are public schools in law
  but admit by lottery, so they are separated here. 91 of 574 places have a charter in their set.
  Re-run `add_education_split.py` after any education rescore.

## Elite-district ceiling
About 23 catalog places score exactly 95 (Chappaqua, Darien, Short Hills, Westport, Great Neck,
...). Schools are district-administered, so a top district's towns share the same capped
rating. Elite districts do not separate from each other.

## Gotchas
- A default live API score may have education at weight 0; do not compare it to a catalog score
  that weights education.
- District-level resolution means neighboring towns in one district get the same school score
  by design; it is not a per-place signal.
- A run that "stops on quota" is usually the cache, a dead API server, or a place with no rated
  schools. Check the API log before assuming the quota.

## Education check (pass/fail, offline)
`PYTHONPATH=. python3 scripts/catalog/check_education.py [--metro la]` (exit 1 on any failure).
Also runs inside `check_catalog_health.py` and `metro_agent health` (a failing education check
makes the metro UNHEALTHY there). "Done" for this pillar means every metro passes.

| Check | Fails when |
|---|---|
| no_score | no usable education score and not an accepted exception |
| no_school_list | scored but `breakdown.rated_schools` missing |
| weight_zero | usable score but weight 0 while other pillars are weighted |
| no_split / formula_mismatch | split missing, or score/split differs from the formula on `rated_schools` |
| thin_big_district | fewer than 3 rated schools although its Census district has 6+ schools (radius limit, not a real shortage) |
| mostly_outside_district | half or more of matched stored schools are in other districts |

Warnings (do not fail): `thin_small_district` (real shortage), `thin_unverified` (no Census/NCES
files), `some_outside_district` (25% or more; noisy because of school-name collisions).
Accepted gaps go in `data/education_check_exceptions.json` as `"<metro>:<place>": "reason"`.
The district checks need `data_cache/tiger_sd_2024` (Census) and `data_cache/nces_ccd_2324` (NCES
school directory); without them they are skipped.
First run (2026-10-14): all six metros FAIL, which is the real remaining work: 33 thin places in
big districts (Humboldt Park, Windsor Park, Leimert Park...), 9 places with stored schools mostly
in another district (5 are hamlet coordinates, see backlog), Seattle Ballard and Kirkland unscored.

## Zone maps (attendance zones), wired into scoring 2026-10-15
`data_sources/school_zones.py`: `zoned_schools(lat, lon)` returns the zoned elementary / middle /
high school for a point from district-published maps in `data_cache/zone_maps/` (not in git;
override with `HOMEFIT_ZONE_MAPS_DIR`); `match_zoned_to_schools` finds the SchoolDigger school
(rating, charter flag) for a zone by name tokens + level. Add a metro by adding a `ZoneLayer`.

| Metro | Layers | Vintage | Notes |
|---|---|---|---|
| Chicago | elementary (K-8), high | 2025-26, 2024-25 | no middle layer; selective/magnet/charter have no zone |
| Austin | elementary, middle, high | file names say 2021-22 / 2020-21 | AISD consolidated schools for 2026-27; likely stale |
| SF | elementary | 2024-25 | middle/high are choice, no zones |
| NYC | elementary, middle, high | 2024-25 | high school: only `catchment=1` zones (28 schools); some districts choice-based |
| LA | elementary/high 2018, middle 2020 | 2018 / 2020 | no school names: the school is found by the campus inside the zone; shared campuses averaged |
| Suburbs and other districts with no current map | NCES 2015-16 survey (fallback) | 2015-16 | used only where no current map covers the point; matched by exact NCES school ID; about 10% of zones may have changed (see below) |
| Philadelphia | 2024-25 (added 2026-10-16) | 2024-25 | 160 elementary, 126 middle, 22 high school catchments; not in the catalog yet (add the metro to the script `METROS` lists) |

Pilot (8 places, 1 SchoolDigger call each): 15 of 17 zoned schools matched to a rated school
(Chicago, Austin, SF, NYC elementary all matched). Misses: NYC middle schools that SchoolDigger
names without a number (e.g. "Albert Shanker School For Visual A..." vs dbn 30Q126); a dbn to
name crosswalk is needed (NCES `ST_SCHID` ends with the school number and could serve).
Zones give the zoned school only: charters and choice schools still come from the radius search,
and each place should carry the map vintage. Combination rule (zoned + choice) is undecided.

## Validation against test proficiency (2026-10-16)
`scripts/catalog/validate_education_vs_edfacts.py` compares SchoolDigger's statewide percentile (the rating we score)
with federal EDFacts reading+math proficiency from the Urban Institute Education Data API (free, no SchoolDigger
calls; SchoolDigger school IDs are NCES IDs). Newest school-level year available is 2017-18, so it tests the
ranking, not this year's values. Spearman rank correlation, by district: Chicago elementary 0.75, middle 0.67, high
0.83; Austin 0.75 / 0.91 / 0.92; SFUSD 0.86 / 0.85 / 0.92; LAUSD 0.73 / 0.86 / 0.80; NYC 0.76 / 0.73 / 0.66.
Pooled across states the high school figure falls to 0.39 because high school tests differ by state, so compare
within a district or state, never across states. The lowest-scoring places hold up: Bayview's Carver Elementary
(0.7th percentile) was 10% proficient; Garfield Park, Englewood and Gary schools 5 to 22%. Austin's lowest schools
(Allison, Pickle, Webb) were 20 to 37% proficient in 2018, low for Texas, so the percentile is plausible but the gap
between 0.3th percentile and 37% shows that a percentile is relative to the state.

## 2015-16 national zone fallback (decided 2026-10-16)
Where no current district map covers a point (most suburbs), the NCES School Attendance Boundary Survey 2015-16 supplies the
zoned school (`sabs_*_1516` layers in the bundle, 9 states, 19 MB). Rules: a current district map always wins and the old
layers are not even consulted; fallback zones never make a level "choice" (a level they miss uses nearest-3); open-enrollment
zones are dropped; where zones overlap the smallest wins; the school is matched by its exact NCES ID (= SchoolDigger school ID)
and the map year shows as 2015-16 in the details. Basis for adopting it: at places covered by both a current map and the
2015-16 survey, the same school came out 90% of the time (128 of 143 checks; SF and Chicago 100%, NYC 83%), which beats
nearest-3. Limits: coverage is partial (it has nothing for Austin ISD), and the 10% that changed will be wrong until a
current map exists. Effect on the catalog: about 230 places change, by 2.5 to 8.4 points on average per metro.

## Backlog (as of 2026-10-16)
Done 2026-10-15/16: percentile scale, zone maps for 6 metros (LA via campus-in-zone), hamlet fix, Seattle zones,
state snapshot, offline re-score, production bundle, Explorer labels, deal-breaker 50, public/charter split.

1. **Austin zones are stale** (2021-22 / 2020-21; AISD closed 10 schools for 2026-27). Decided 2026-10-16 not to ask AISD for
   newer files: only 3 of 93 zoned Austin levels point to a closing school. Revisit if AISD publishes a new map.
2. ~~Philadelphia zone maps~~ added 2026-10-16 (SDP 2024-25 catchments, PA districts and places in the bundle). Left: score the
   Philadelphia catalog and add it to the `METROS` lists in the education scripts (playbook Phase A3).
3. **SF middle/high** are choice (no zones), **NYC high school** is mostly choice, **Chicago high school** only neighborhood
   schools have zones: they use the nearest-3 rule. Revisit if a choice-system model is wanted.
4. **Explorer**: the public/charter filter should show the "thin" flag; check the new detail rows on a real place page.
5. ~~Validate low scores~~ done 2026-10-16 (section above). Left: a newer year when EDFacts publishes one.
6. **Large-district neighborhoods without zones** rely on nearest-3 per level; attendance zones are the real fix.
7. **Snapshot refresh** once a year (about 112 calls, under $1) and rebuild the bundle when zone maps change.
8. **Choice-school handling** (magnet/lottery seats) is only the charter list; magnets are not modeled.
9. Housekeeping: fold the re-score recipe into `docs/METRO_EXPANSION_PLAYBOOK.md` and `docs/CATALOG_TOOLKIT.md`.

---

## DPv2 spec sheet (2026-11-03)

Level: 2 (Verified), signed off by the owner 2026-11-03 (Level 1 earlier the same day), with the gaps recorded in the sign-off line. The independent
validation in `analysis/education_validation_brief_2026-11-03.md` was run by another agent against criteria fixed in that brief.
Status per requirement: `analysis/education_dpv2_status_2026-11-03.md`. Everything below is from stored data on origin/main
(86c66afe, 1,476 places), offline, except the independent validation, which used the EDFacts API (2018) and official state files (CA, TX 2023-24) with owner approval. Owner decisions of 2026-10-26 are tier 3 and are not reopened.

```
Pillar: quality_education
Construct (one sentence): Quality of the school a child at this address would be assigned to (zoned school, else the nearest
  rated schools of the home district; lottery levels show the district pool average), measured by statewide test-score percentile.
Reference frame: state norm (within-state percentile of test results). Not a fixed standard and not a national norm.
  Evidence for the frame: tier 2 (revealed-preference proxy) plus owner decision (tier 3).
    Tier 2: home prices move with standardized test-score rank, about 1 to 3 percent per standard deviation of school quality
    (Collateral Analytics 2018 consensus figure; Machin 2011 review; Imberman and Lovenheim 2016 for test-score levels over
    value-added, one city). Read from search summaries only. Black 1999 and Bayer, Ferreira and McMillan 2007 were not retrieved.
    What the evidence does and does not support: it supports ranking by test-score level. It does not test whether the reference
    group should be the state, the metro or the nation. State is used because the tests differ by state, so scores from different
    states are not on one scale and a national frame cannot be computed from stored data.
  Deviation from DPv2 Part 1: Part 1 defaults school proficiency to a fixed standard. This pillar uses a relative frame by owner
    decision (2026-10-26). Consequence, disclosed: a 70 in one state is not the same school quality as a 70 in another
    (place means run from CT 84.7 to DE 42.0 in the 2026-10-25 audit, partly which places are in the catalog).
Measurement area: pin + Census district polygon + attendance-zone polygon; nearest 3 rated schools within a radius when no zone.
  Reason: the assigned school is what a resident means by "my school". Radii apply only where no zone covers the point
  (351 of 1,472 scored places have at least one nearest-school level).
Place context inputs used (fields) and remaining area-type uses (with reason):
  Reads place_context.area_type when a context is passed (pillars/schools.py get_school_data). Uses none of the density factors.
  The catalog offline rescore reads the stored area type, not the context helper.
  Remaining use of the label: the search radius for the nearest-school path (data_sources/radius_profiles.py, 1.5 / 2.0 / 3.0 mi).
  Reason it stays: it does not move scores (radius x0.5 mean change 0.21, x2 mean 0.60, on the places that use it) and
  nothing sourced replaces it. KNOWN DEFECT: the profile keys on "urban_core", but the classifier emits "urban_residential",
  so urban residential places get the 3.0 mi radius, not the documented 1.5. Affects 30 places with a nearest level; same
  small sensitivity. Not changed; proposed fix is in the status file.
Inputs and data sources (with vintage): SchoolDigger statewide percentile snapshot (18 states in data/school_snapshot, first
  fetched 2026-10-16, refresh yearly); Census TIGER school districts (2024); district zone maps (2018 to 2026-27); NCES 2015-16 attendance
  survey as fallback; NYC middle-school directory; SF lottery rules. Early-education counts from OpenStreetMap (0 points).
Parameters:
  name | value | source | plausible range | sensitivity result
  education weight | 7.69% (equal 1/13) | owner decision, no study gives a weight | 0 to 2 times (judgment) | weight 0 moves totals a mean 1.6 (max 4.9), approximate. TODO source
  level weights elementary / middle / high | equal | judgment, research mixed | unknown | doubling one level: mean 2.5 (p95 7.3 to 7.9, max 16.0); elementary alone: mean 9.8 (p95 29.1). TODO source
  radius ratio 2.1 / 3.2 / 3.6 mi | NHTS 2017 median school trip (PBIC brief), tier 1 | n/a | n/a | sourced
  base radii 1.5 / 2.0 / 3.0 mi | judgment, no source | unknown | x0.5 mean 0.21 (4 places over 0.5); x2 mean 0.60 (52 places over 0.5). TODO source
  nearest 3 schools | judgment | unknown | not tested. TODO
  widening cap 3 mi | judgment | 2 to 5 mi tested | cap 2: mean 0.68; cap 4: 0.38; cap 5: 0.52 (364 places). TODO source
  district-far fallback 15 mi | judgment | unknown | 31 levels use it; not tested. TODO
  choice pool average | enrollment-weighted mean of rated district-run schools, at least 3 | judgment, no source | alternatives tested | unweighted mean mean change 3.15; median 1.30; weighted median 3.28 (max 10.9; 126 places). Owner kept the weighted mean. TODO source
  hamlet rule 25% / 50% | judgment | unknown | not tested. TODO
  pin-sensitivity flag cutoff 15 points | owner judgment | unknown | flags 387 of 1,472 places
  early-education points | 0 | no source for a size | n/a | data only
  2015-16 zone fallback | adopted on 90% agreement with current maps (128 of 143 checks) | tier 1 comparison, own test | n/a | 77.7% of zoned levels use it; about 10% of those zones may have changed
Shared inputs with other pillars: none raw (SchoolDigger only; housing value has no school input). Spearman with other pillars
  (1,472 places): community safety 0.48, natural beauty 0.44, diversity -0.42, social fabric 0.38, housing value 0.20, others
  under 0.2: shared affluence, not shared inputs. Education feeds the longevity and happiness indices, not the headline total.
Pin-shift sensitivity (shift distance, median and p95 score change): 0.5 mi, largest of four directions, 1,472 places,
  recomputed 2026-11-03 from the stored per-place measurement: median 5.8, p90 31.9, p95 42.6, max 80.9; 53% move more than 5;
  387 move more than 15. By area type (median / p95 / count over 15): urban residential 20.9 / 54.7 / 124 of 200; suburban 6.6 /
  39.5 / 203 of 765; exurban 3.5 / 29.8 / 52 of 361; rural 0.0 / 15.9 / 8 of 143. The swing is not reduced; it is flagged on
  the place (pin_sensitive). Largest in dense places, where a half mile crosses attendance zones and districts.
Independent validation source and result: recorded as PARTIAL, not Level 2 evidence yet. Ran 2026-10-16 and 2026-10-26 against
  EDFacts proficiency (Urban Institute API, 2018 data): school ratings vs proficiency, Spearman 0.66 to 0.92 within districts;
  place score vs mean proficiency of the same schools, within state, 798 of 1,438 places with named schools (about 54%),
  weighted mean 0.93 (all-grades version 0.94). Why it does not close Level 2: pass criteria were not fixed before the results
  (no bar was set for education); coverage is a subset (DPv2 allows "validated" copy only on the full catalog); the place-level
  script and its data were never committed, so it cannot be rerun offline; ratings are 2025 and proficiency 2018; SchoolDigger
  percentiles come from the same state tests, so this checks aggregation fidelity, not an independent view of quality; it does
  not test whether the right schools were chosen. Three disagreements stay unexplained (Sausalito, Anna, Clarksburg). The rerun
  is the brief in `analysis/education_validation_brief_2026-11-03.md`.
  INDEPENDENT RUN 2026-11-03 (separate agent, EDFacts 2018 via Urban Institute API, grade 99 all grades, read+math midpoint mean;
  `scripts/catalog/validate_education_edfacts.py`, per-place `analysis/education_validation_edfacts2018_places.csv`, cells
  `analysis/education_validation_edfacts2018_cells.csv`; bars fixed in the brief). No recent-year state file was approved, so the 2018 gap
  is the main confound. Result against the fixed bars:
  Test A FAIL: 54 of 54 state-level cells conclusive, 53 pass (98%, bar 80%), but NY high is 0.494 (bar: no cell below 0.50). Other
    cell minimum 0.743 (IN high 0.749, TX elementary 0.742). Likely cause, not proven: NY high-school 2018 proficiency is saturated
    (49% of NY rated high schools at 90 or above, Regents-style pass rates), so the proficiency side has little rank information.
  Test B: 12 states with 30 or more matched places all at or above 0.70 (lowest FL 0.859, NY 0.886, highest MA 0.965); weighted mean
    0.919 (bar 0.80). Coverage 1,449 of 1,472 scored places (98%); every state at or above 94% (NY 98% after mapping NYC DOE to its
    geographic districts in the script). INCONCLUSIVE for the rule "every state": CT 13, NV 29, IN 6, DE 3, WA 5, MD 1 matched places,
    below the 30 needed, so "validated" copy is not allowed on this evidence. 23 unmatched places (MA 5, IL 3, PA 3, FL 2, NJ 2, NY 3,
    CA 2, GA, TX, CO 1 each) are listed in the CSV with matched=False.
  Test C NOT RUN: needs manual district-finder reads, not approved. The seed-2026 sample (20 current zone map, 10 survey 2015-16,
    10 nearest) is in `analysis/education_validation_testC_sample.csv` with the read column empty.
  Test D UNEXPLAINED for all five, no recent-year source. Stored ratings vs 2018 proficiency: Sausalito King Academy rating 70.7 vs
    proficiency 19.8 (the school is the zoned elementary and the nearest middle); Anna TX ratings 3, 27, 45 vs proficiency 54, 47, 56
    (zones 2015-16, fast-growing district); Clarksburg CA Walnut Grove (district_far, 12.5 mi) 33 vs 54.5; New Braunfels TX high
    school rating 79.6 vs proficiency 11.0 (looks like a 2018 source problem, unverified); EaDo TX ratings 62, 47, 40 vs
    proficiency 42, 28, 26 (zones 2026-27, mild). Need a 2023-25 state file to close.
  Verdict: Level 2 independent validation FAILED on the Test A floor and is INCONCLUSIVE on Test B state coverage, Test C and Test D.
  Caveat: SchoolDigger percentiles come from the same state tests, so this checks aggregation and school matching, not independent quality.
  RECENT-YEAR RERUN 2026-11-03 (2023-24, same fixed bars; the 2018 result above is kept). Official files, owner approved: NYSED
    SRC2024.zip (data.nysed.gov, 354,144,686 bytes, Regents table "Annual Regents Exams", mdbtools export) and CDE CAASPP 2023-24 research
    files sb_ca2024_1_csv_v1.zip (7.8 MB) and sb_ca2024entities_csv.zip (0.2 MB) from caaspp-elpac.ets.org (the CDE CAASPP site, run by
    its contractor; the zip links need a session cookie from the file list page). No Texas file was found or approved. Script
    `scripts/catalog/validate_education_recent.py`.
  Test A, NY high school, recent year: PASS the floor. Spearman 0.968 on the 686 of 1,102 rated NY high schools whose name is unique
    in both sources (no zip or NCES id in the Regents table, so the 38% not matched are unmatched by name rule, not tested). Tested-weighted
    Regents percent proficient, 2024. The 2018 NY high 0.494 was therefore a saturated 2018 source, not a rating problem. Not a full
    re-run of all cells: only NY high was rerun on the new source.
  Test A, CA, extra (not a fixed-bar cell set, shown for scale): elementary 0.949 (4,875 matched), middle 0.966 (1,135), high 0.939 (1,383).
  Test D with 2023-24 (CA only; TX Anna, New Braunfels, EaDo remain unexplained, no source): Clarksburg EXPLAINED: Walnut Grove Elem
    rating 33 vs proficiency 19, Clarksburg Middle 9 vs 11, Delta High 50 vs 31, so ratings agree and the 2018 gap (54.5 and 44.5)
    was the old source. Sausalito MOSTLY EXPLAINED: King Academy proficiency 19.8 (2018) is 41.4 in 2024 (ELA 42.4, math 40.4, 172 tested),
    Tamalpais High 66.7 vs rating 95; residual: a rating of 70.7 for 41% proficient is near the 90th percentile of schools at that proficiency
    (median rating 56), so the King Academy rating stays a possible rating issue; not resolved from these files.
  TEXAS 2023-24 (added same day; owner approved): TEA TAPR advanced download, campus level, from rptsvr1.tea.texas.gov (REF 1.2 MB,
    STAAR1 39 MB, STAAR2 31 MB; official TEA form output, no login), Meets Grade Level rate, all students. Test A by level, TX:
    elementary 0.863 (3,926 matched of 4,292 rated), middle 0.906 (1,397 of 1,530), high 0.908 (1,513 of 1,749), all above 0.70.
    Matching is district name plus fuzzy campus name (ratio 0.80 or more, unique best), so unmatched schools are untested.
    Test D, TX: New Braunfels EXPLAINED (high school rating 79.6 vs 69.2 meets in 2024; the 2018 value 11.0 was a 2018 source artifact;
    elementary 77 vs 55, middle 80 vs 56, ratings run above proficiency but rank consistently). EaDo EXPLAINED (Lantrip 62 vs 57,
    Navarro 47 vs 27, Wheatley 40 vs 33: ratings agree within the state-percentile scale). Anna NOT EXPLAINED, report to owner as a
    possible rating error: Joe K Bryant Elementary rating 3.4 vs 44.0% meets (44th percentile of TX elementary schools; only 0.3% of
    schools at 41-47% meets have a rating of 5 or below; median rating at that proficiency 44), Slayter Creek Middle 27 vs 36.8,
    Anna High 45 vs 63.2; the other Anna elementary schools are mixed (Rattan 19.8 vs 58, Harlow 35.6 vs 50, Rosamond-Sherley 46.5 vs 29).
    Not a data-file problem, since the zoned schools match. Anna's score of 25.1 stands on those ratings.
  TEST C RUN 2026-11-03 (district-finder reads supplied by the owner from an outside browsing agent; 39 of the 40 sampled places came
    back, Waller TX is missing; reads in `analysis/education_validation_testC_reads.csv`; match labels set by this agent; not re-checked
    by a second reader). Bar: at least 85% for zone-map levels and for 2015-16 levels; nearest has no bar.
    Zone-map stratum: 18 of 19 readable match (94.7%, PASS; City Island unreadable, a tool crash; counting it as a miss 18 of 20 = 90%,
    still pass). One miss: Wicker Park IL, stored Pulaski International vs CPS tool Burr. Caveat: Venice and Hollywood Hills carry a
    2018 map in the catalog, so the "current zone map" stratum includes two 2018 maps; both matched. Stapleton counted a match (stored
    school is one of three schools in a shared zone).
    2015-16 stratum: 4 of 4 readable match (Gold Canyon, Kirkland, Emeryville, Highland Village) but only 4 of 9 returned places could
    be read (Allen, Sandy Oaks, Menlo Park, San Gabriel, Downtown Las Vegas unreadable: no finder, login wall, or image-only map), and
    Emeryville is a single-elementary district, not a finder read. INCONCLUSIVE: passes on the readable reads, fails if unreadable counted as
    misses (4 of 9 = 44%); the 85% bar cannot be judged on this coverage.
    Nearest stratum (no bar): 1 of 3 readable match (Braintree match; Germantown stored Kelly vs finder Mastery Charter at Wister;
    McKinney stored Caldwell vs Finch). Excluded as lottery or no single zoned school: West Roxbury MA (stored Mozart is on the list of 16
    eligible schools), Sleepy Hollow NY (Princeton Plan), Fruitvale CA (OUSD lottery). Unreadable: Granite Bay, Stafford, Pennsauken, Bristol.
  Updated verdict: on 2023-24, Test A passes in every cell run (CA, TX all levels; NY high only; NY elementary and middle not
    rerun), but the fixed-bar Test A result stays FAIL as run on 2018 (bars not edited). Test D: Clarksburg, Sausalito (mostly),
    New Braunfels and EaDo explained; Anna and the King Academy rating are reported to the owner. Test C: zone-map PASS (94.7%), 2015-16
    INCONCLUSIVE (4 of 9 readable), nearest 1 of 3 (no bar). Test B small-state coverage (CT, NV, IN, DE, WA, MD under 30 matched
    places) is open, so the independent validation did not pass in full; the owner signed Level 2 with these gaps accepted (sign-off line below).
All-places check (date, n, summary): 2026-11-03, n=1,476 (1,472 scored, 4 no data). Mean 59.4, sd 25.9, 10th to 90th percentile
  21.3 to 92.9, 98 distinct rounded values, top single value 2.2%. By area type (n, 10th / median / 90th, share at 95 or above):
  urban residential 200, 16.7 / 57.7 / 79.6, 0.5%; suburban 765, 21.5 / 61.4 / 93.2, 6.5%; exurban 361, 21.5 / 65.0 / 93.9, 7.8%;
  rural 143, 21.4 / 68.9 / 94.1, 9.8%; unlabeled 3. Floor: 0.7% at 5 or below. Ceiling: none at 100, 6.5% at 95 or above
  (elite districts share a capped rating, so they do not separate from each other). Urban residential tops out near 80:
  a result of its schools, not a cap. check_education.py passes for all metros (2026-10-26; not rerun here).
Fail-loud conditions (what is rejected, what is flagged): no rated school at any level = no data, degraded (4 places); a level with
  no rated school degrades the pillar (32); failed or uncovered early-education read = early_ed_missing (541), never a zero;
  live scorer keeps a missing score as no data. Flagged on the place, not degraded: zone_map_2015_16 (1,023), no_zone_map (364),
  pin_sensitive (387). Open small gap: places scored from 1 or 2 of 3 levels (32) are comparable only loosely with 3-level places.
Launch check pairs (should differ / should be similar) and result: recomputed 2026-11-03, stored scores unchanged. Differ: Palo Alto
  95.7 vs East Palo Alto 30.5, Great Neck 93.8 vs Hempstead 21.1, Brookline 93.6 vs Chelsea MA 14.8 (all pass, 20 or more apart).
  Similar: Darien 97.6 vs Westport 96.5, Winnetka 97.3 vs Lake Forest 98.4, University Park 99.0 vs Highland Park TX 99.1 (all pass,
  within 10). Mid-range similar pair Babylon 64.7 vs Tarrytown NY 49.4: FAIL (15.3 apart), because Babylon is scored from one
  level. Owner decision 2026-10-26: keep, flagged, recorded as a known limit. Pairs were named after the scores were seen, so
  this is a check, not a blind pre-registration. Thresholds are judgment.
Known data limits: 2015-16 zone maps on 77.7% of zoned levels; Austin zones stale; lottery districts (SF, NYC middle and high)
  score as a district pool so every address gets nearly the same number; early-education data missing for 541 places in states
  the private server does not cover (0 points); ratings are one year (2025) with no earlier history in the snapshot; scores are
  comparable only inside a state; the Texas and California disagreements in validation are undiagnosed.
Last re-validated: 2026-11-03 (all-places, pin-shift, launch pairs, recomputed from stored data). Independent validation run
  2026-11-03 (see above): fixed-bar Test A failed on 2018 data (NY high) and passes on 2023-24 state files; Test B small states and
  the 2015-16 stratum of Test C inconclusive; Level 2 signed off by the owner with these gaps accepted. Next dated check: 2027-01-26 (quarterly), or on the yearly snapshot refresh, a zone-map update or a new EDFacts release.
Sign-off: Level 1 (Converted), owner, 2026-11-03. Accepted TODOs: education weight, level weights, base radii, nearest-3,
  3 mi widening cap, 15 mi district-far fallback, choice pool average, hamlet 25%/50% rule, pin-flag cutoff. Accepted known
  defect: radius profile keys on urban_core, classifier emits urban_residential (30 places, small effect).
Sign-off: Level 2 (Verified), owner, 2026-11-03, with written reasons for what the independent validation did not cover. The fixed-bar
  Test A on EDFacts 2018 failed on NY high (0.494); the 2023-24 rerun on official state files passes in CA, TX and NY high (NY elementary
  and middle not rerun). Test B was conclusive in 12 states; CT, NV, IN, DE, WA and MD have fewer than 30 matched places and cannot be
  tested. Test C: zone-map 94.7% pass, 2015-16 fallback inconclusive (4 of 9 readable), nearest 1 of 3 (no bar). Test D: Anna TX and
  King Academy (Sausalito CA) ratings go to SchoolDigger as possible rating issues. SchoolDigger percentiles come from the same state
  tests, so this checks aggregation and matching, not independent quality. "Validated" copy NOT allowed (full-catalog standard not met).
  Accepted: the small-state and unreadable-finder gaps, the Test A bar as run. Next dated check as above.
```
