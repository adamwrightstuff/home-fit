# Community safety: Level 2 checks, independent report (2026-11-01)

Criteria are those in docs/PILLAR_COMMUNITY_SAFETY_LEVEL2_BRIEF.md, unchanged. Offline only: stored scores from the 21 `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` files (1,476 rows). No API, Overpass or tunnel, no code, scoring, catalog or spec sheet edits. Python ran with -I. Scratch scripts are in the session scratchpad, not the repo.

Summary: Check 1 PASS (differ pairs all pass; one similar pair passes; Park Slope pair fails as expected). Check 2 PASS on both criteria. Check 3 disclosure only. Check 4 not run, data needs listed below.

## Check 1: launch pairs

Stored `community_safety.score` (precision level in brackets):

| Place | Score |
|---|---|
| Compton CA | 6.5 (PRECINCT_PROXY, LASD Compton Station) |
| Palo Alto CA | 71.8 (AGENCY_VERIFIED) |
| Camden NJ | 2.8 (PRECINCT_PROXY, Camden County PD) |
| Newton MA | 92.0 (AGENCY_VERIFIED) |
| Naperville IL | 90.3 (AGENCY_VERIFIED) |
| Park Slope NY | 71.9 (HYPER_LOCAL) |
| Brooklyn Heights NY | 46.9 (HYPER_LOCAL) |

Each name matched exactly one row.

| Pair | Rule | Gap | Result |
|---|---|---|---|
| Compton vs Palo Alto | differ by 30 or more | 65.3 | PASS |
| Camden vs Newton | differ by 30 or more | 89.2 | PASS |
| Compton vs Naperville | differ by 30 or more | 83.8 | PASS |
| Newton vs Naperville | within 10 | 1.7 | PASS |
| Park Slope vs Brooklyn Heights | within 10 | 25.0 | FAIL (expected; shows the pin-shift limit) |

Pillar verdict: PASS (every differ pair passes, at least one similar pair passes). The Park Slope pair failure is reported as required: two adjacent HYPER_LOCAL neighborhoods differ by 25 points.

## Check 2: all-places distribution

Scored places: n = 1,420 (1,476 rows; 56 rows have a null score and precision level DEGRADED, excluded). No duplicate place keys across metro files.

Extremes:
- 95 or higher: 114 (8.0%)
- exactly 100: 24 (1.7%)
- exactly 0: 4
- 5 or lower: 38 (2.7%)

Most common single values (share of 1,420): 9.0 holds 25 places (1.76%), 100.0 holds 24 (1.69%), 8.0 holds 22 (1.55%), 18.1 holds 19 (1.34%). Largest single-value share is 1.76%, under the 3% limit. Counts per 10-point bin from 0-10 up to 90-100: 119, 103, 116, 164, 136, 160, 123, 135, 160, 204.

Area type method: not read from stored rows. I used the offline local-table functions that `detect_area_type` uses (`surrounding_stats`, `principal_city_at`, `classify_surrounding`, from `data_sources/surrounding_density.py` and `principal_city.py`), run on each place's stored lat/lon, with the state FIPS taken from the catalog state so principal-city membership resolves as it does in a live request. I did not call `detect_area_type` itself and did not pass a census tract. No place came back "unknown".

| Area type | n | 10th | Median | 90th | 10th to 90th spread |
|---|---|---|---|---|---|
| urban_residential | 470 | 7.5 | 34.9 | 73.4 | 66.0 |
| suburban | 571 | 20.8 | 61.9 | 95.7 | 74.9 |
| exurban | 281 | 31.4 | 74.5 | 96.2 | 64.8 |
| rural | 98 | 39.3 | 70.6 | 98.0 | 58.6 |

Criteria: every type spread of 30 or more (smallest is rural at 58.6): PASS. No single value above 3% (largest 1.76%): PASS. Check 2 verdict: PASS. Observations, not fixes: the 90th percentile is 95.7 or higher in three of four types, and 8.0% of places sit at 95 or above.

## Check 3: pin-shift

Circle places (HYPER_LOCAL, 369 in the stored data): not rerun. Prior measurement 2026-10-26: median 13.7, p95 34.3 at 600 m, as given in the brief.

Agency-level places: 1,051 stored (893 AGENCY_VERIFIED plus 158 PRECINCT_PROXY). No police-agency boundary file exists in the repo, so the strict test as written is not testable offline. The repo does hold Census place polygons (`data/school_geo/place_<state>.geojson.gz`, 18 states), and each stored row carries the place GEOID of its jurisdiction (`people_present.geoid`). As a supplementary proxy only (a Census place is not a police jurisdiction), I measured pin-to-edge distance for the places that could be matched:

- 388 of 1,051 matched a place polygon with a 7-digit GEOID and were measured.
- Not measurable: 509 whose place polygon is not in the repo files, 111 county-agency rows (no county polygon file used), 37 county-subdivision GEOIDs (10 digits), 6 with no GEOID.
- Of the 388 measured: 300 (77%) sit within 1 km of the boundary, 123 within 500 m. Median distance to edge 702 m, 10th percentile 234 m. All 388 pins fall inside their polygon.
- Against all 1,051 agency-level places, 300 (28.5%) are known to be within 1 km; the other 663 are unmeasured, so the true share is not known.

No pass criterion; disclosure only. Caveats: the sample is not random (the matched states and places are those in the school_geo files), and Census place edges differ from the actual agency boundary for sheriff-served or shared-jurisdiction places.

## Check 4: independent validation (not run, no download or call made)

Finding that changes the plan: the first source option requires circle places where the stored incident feed is NOT the source. All 369 HYPER_LOCAL places are fed by a city or county open-data incident feed (stored sources: nyc 96, la 56, chicago 47, philadelphia 39, austin 33, sf 33, boston 17, dallas 16, charlotte 14, lasd 13, las_vegas 5). So no circle place qualifies for option 1 as written, and the brief's fallback applies: FBI NIBRS agency violent rate versus stored violent_per_1k for the circle cities' parent agencies.

Two problems with that fallback that the owner should decide on before any pull:
- The 369 circle places belong to only about 11 parent agencies (NYPD, LAPD, Chicago PD, Philadelphia PD, Austin PD, SFPD, Boston PD, Dallas PD, Charlotte-Mecklenburg PD, Las Vegas Metro PD, LA County Sheriff). A correlation across agencies has n of about 11, below the fixed minimum of 15. Correlating each circle place with its city's rate gives n of 369 but ties within each city and measures the circle-to-city gap, not accuracy.
- Stored circle violent_per_1k is a 600 m circle rate on a people-present denominator; the agency value is whole-city. They are different quantities, so the 0.7 criterion tests neighborhood spread against a city mean.

Data it would need:
- What: FBI CDE summarized agency data (Part I violent counts, 12 months, 2024 or latest full year to match the stored `national_scale.data_year` of 2024) plus agency population, for those 11 agencies.
- Where from: FBI Crime Data Explorer `/summarized/agency` endpoint (the same one `data_sources/crime_api.py` and `scripts/metro_agent/fbi_probe.py` use; needs the `FBI_API_KEY`-type key from the environment). Bulk NIBRS downloads from the FBI are the alternative but are hundreds of MB and unnecessary.
- Size: tiny, 11 rows, under 100 KB.
- Stored files that could serve: none for the 11 agencies. `analysis/safety_crime_type_sample_2026-10-31.jsonl` holds 50 FBI agency rows but only Austin PD overlaps a circle-city parent (1 agency). `data/community_safety_national_scale.json` holds only national percentile arrays (no per-agency rows). `data/lasd_station_crimes.json` is LASD station counts, which is the LASD feed's own input, so not independent. Stored AGENCY_VERIFIED rows are FBI-sourced but belong to non-circle places, so they cannot rank-check the circle places.
- Alternative independent source the owner could accept, replacing it per the brief: published precinct or tract crime maps (for example NYPD precinct complaint counts, which are not the point-level feed used) for at least 15 circle places; that needs a download and is not stored.

## What was not verified

- Check 3 against real police agency boundaries (no such file in the repo); 663 of 1,051 agency-level places are unmeasured even by the Census place proxy.
- Circle pin-shift was not re-measured; the 2026-10-26 figures are quoted from the brief.
- Check 2 area types come from the local-table functions with state FIPS but without a per-place census tract, so a few places may differ from what a live request would assign. Stored-row area types were not compared.
- Check 4 entirely: no correlation or rank-difference criteria were evaluated.
- Whether the stored scores themselves are correct; this report applies the fixed criteria to stored values only.
