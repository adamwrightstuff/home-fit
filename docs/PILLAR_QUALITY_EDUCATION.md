# Pillar Deep-Dive: Quality Education

How `pillars/schools.py` and `data_sources/schools_api.py` feed the `quality_education` pillar,
and how to score a new metro with it. Written 2026-10-14 after the SchoolDigger Pro re-score of
all six catalog metros. Sections marked **(interim)** are heuristics we expect to replace with the
Census district-boundary lookup (see "Planned: boundary lookup").

## What it measures
School quality near a location: the rating of nearby public and charter schools, with small
bonuses for elite options and early-education availability.

## Scoring (`pillars/schools.py`)
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

## Planned: boundary lookup (replaces the interim heuristics)
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

## Zone maps (attendance zones), built 2026-10-15, not yet wired into scoring
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
| LA | downloaded, not enabled | 2018 / 2020 | layers carry numeric keys only; needs the LAUSD key table |

Pilot (8 places, 1 SchoolDigger call each): 15 of 17 zoned schools matched to a rated school
(Chicago, Austin, SF, NYC elementary all matched). Misses: NYC middle schools that SchoolDigger
names without a number (e.g. "Albert Shanker School For Visual A..." vs dbn 30Q126); a dbn to
name crosswalk is needed (NCES `ST_SCHID` ends with the school number and could serve).
Zones give the zoned school only: charters and choice schools still come from the radius search,
and each place should carry the map vintage. Combination rule (zoned + choice) is undecided.

## Backlog (as of 2026-10-14, after commit 0d4ce7c)
Priority order, none blocking the current catalog.

1. ~~Public vs charter split~~ built 2026-10-14 (see section above). Left: show the `thin`
   confidence in the Explorer UI when a filtered side has fewer than 3 rated schools.
2. **Hamlet coordinates.** Cold Spring Harbor, Mamaroneck, Woodmere, Valley Stream and Los Altos
   Hills have catalog coordinates inside the neighboring district's polygon, so the Census lookup
   would pick the wrong district. Fix: use the Census place (village/CDP) outline and take the
   district covering most of it; keep the point for neighborhoods that have no outline.
3. **Ship the Census boundary files to production** (80 MB raw in `data_cache/tiger_sd_2024`, not
   in git; override with `HOMEFIT_TIGER_SD_DIR`). Until then production uses the SchoolDigger
   fallback chain. Consider a slimmed file (GEOID, NAME, simplified geometry) and a
   `.gitignore` entry for `data_cache/`.
4. **Seattle:** Ballard and Kirkland rows failed (API was down) and need their failed pillars
   re-run; the Seattle catalog has only 5 places.
5. **Austin:** Dripping Springs has no ZIP (78620).
6. **Belvedere CA:** no rated school within the radius (its schools are in Tiburon, just past 2 mi).
   Candidate fix: with the boundary lookup, take the place's district regardless of radius when
   the district is small.
7. **Validate low scores** (Lawrence NY, Englewood Chicago, Gary, Hammond, East Palo Alto, Elgin TX)
   against state test proficiency; SchoolDigger ratings are the only source so far.
8. **Large-district neighborhoods** (Montclair/Oakland, LA, Chicago) rely on the radius, which
   pulls in schools that are not the address's zoned schools. Real fix is attendance zones
   (SchoolDigger Enterprise `boundaryAddress`). Ask for a quote.
9. **Tests:** no unit tests cover the lookup chain, `school_districts.py`, or the home-district
   filter. Add fixtures for Bronxville, Cedarhurst, Studio City, Cupertino, Oak Park.
10. **Offline verification** (`offline_check`, NCES CCD 2023-24 school directory, 41 MB in
    `data_cache/nces_ccd_2324`): 425 of 457 places fully inside their Census district. Turn the
    check into a script in `scripts/catalog/` and run it after any education rescore. Known noise:
    name collisions (Chicago), NYC boroughs (NCES splits them into 32 districts).
11. **Housekeeping:** `.bak` / `.bakEdu` files in `data/`, `scripts/cron/daily_school_cache.sh`
    (written for the old Developer quota; decide whether to retire), `metro_agent health --fix`
    starts its own API on port 8000 and will kill a runner using that port.
12. **Playbook:** fold the "Re-scoring a metro" runbook above into
    `docs/METRO_EXPANSION_PLAYBOOK.md` and `docs/CATALOG_TOOLKIT.md`.
