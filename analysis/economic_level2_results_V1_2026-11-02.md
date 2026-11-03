# Economic security Level 2, check V1: EPA Smart Location Database comparison

Date: 2026-11-02. Independent checker run. Criteria are taken unchanged from `docs/ECONOMIC_SECURITY_LEVEL2_BRIEF.md` (V1 row). No scoring code, catalog file or spec value was changed. No commits, pushes, network calls, downloads or API calls.

## Result table

| Criterion | Result | PASS or FAIL | n |
|---|---|---|---|
| Spearman of log10(D5AR+1) vs log10(gravity+1), all places (threshold 0.80) | 0.909 | PASS | 1,476 |
| Within-metro Spearman, metro mean removed from both, pooled (threshold 0.60) | 0.930 | PASS | 1,476 |
| Median of per-metro Spearman, metros with 30 or more places (threshold 0.60) | 0.939 (20 metros; range 0.716 SF to 0.973 Chicago) | PASS | 20 metros |
| Share of places whose percentile rank differs by more than 30 points (threshold at most 5%) | 33 places, 2.24% | PASS | 1,476 |

Overall V1: PASS on all four sub-criteria.

## Places differing by more than 30 percentile points (all listed, as the brief requires)

Percentile = (average rank − 1) / (n − 1) × 100 over the 1,476 matched places, computed separately for D5AR and gravity. Gravity is the raw `gravity_jobs` value from `data_sources/job_accessibility.py`.

| Place | Metro | D5AR | Gravity | Pct D5AR | Pct gravity | Gap |
|---|---|---|---|---|---|---|
| Rancho Palos Verdes | la | 44,669 | 1,013,693 | 12.5 | 63.2 | 50.6 |
| Palos Verdes Estates | la | 84,015 | 1,219,879 | 25.1 | 75.1 | 50.0 |
| Belvedere | sf | 22,457 | 865,638 | 5.6 | 53.8 | 48.1 |
| Tiburon | sf | 18,749 | 810,868 | 4.4 | 50.3 | 45.9 |
| Cow Hollow | sf | 84,135 | 1,103,947 | 25.3 | 68.3 | 43.1 |
| Dover | boston | 53,862 | 911,959 | 15.4 | 57.5 | 42.1 |
| Palo Alto | sf | 59,956 | 952,651 | 17.8 | 59.5 | 41.7 |
| Portola Valley | sf | 21,750 | 757,687 | 5.4 | 47.0 | 41.6 |
| Outer Sunset | sf | 57,550 | 907,040 | 17.0 | 57.0 | 40.1 |
| Pacific Heights | sf | 95,947 | 1,111,976 | 29.6 | 69.1 | 39.5 |
| Menlo Park | sf | 68,092 | 938,423 | 20.3 | 58.6 | 38.2 |
| Marina District | sf | 96,607 | 1,096,731 | 30.0 | 68.1 | 38.2 |
| North Berkeley | sf | 74,263 | 948,307 | 22.0 | 59.1 | 37.0 |
| Moraga | sf | 60,468 | 854,713 | 17.9 | 53.2 | 35.3 |
| Los Altos Hills | sf | 66,185 | 878,651 | 19.6 | 54.6 | 35.1 |
| Bainbridge Island | seattle | 2,902 | 613,880 | 0.6 | 35.0 | 34.4 |
| Sausalito | sf | 59,927 | 836,657 | 17.7 | 52.0 | 34.3 |
| Paradise Valley | phoenix | 81,917 | 935,157 | 24.5 | 58.5 | 34.0 |
| Presidio Heights | sf | 107,470 | 1,084,223 | 34.2 | 67.7 | 33.5 |
| Bel Air | la | 167,109 | 1,797,393 | 53.0 | 86.4 | 33.4 |
| Outer Richmond | sf | 81,396 | 903,270 | 24.1 | 56.8 | 32.6 |
| Los Altos | sf | 85,016 | 929,120 | 25.6 | 58.2 | 32.6 |
| Inner Richmond | sf | 100,969 | 1,027,292 | 31.9 | 64.3 | 32.5 |
| Gainey Ranch | phoenix | 65,073 | 834,153 | 19.5 | 51.9 | 32.4 |
| Monte Vista | san_antonio | 207,914 | 556,293 | 62.5 | 30.4 | 32.1 |
| Government Hill | san_antonio | 191,627 | 527,862 | 59.3 | 27.3 | 32.0 |
| Balcones Heights | san_antonio | 213,536 | 569,983 | 63.7 | 31.7 | 31.9 |
| La Porte | houston | 168,278 | 456,434 | 53.2 | 21.4 | 31.8 |
| Tobin Hill | san_antonio | 201,782 | 548,004 | 61.3 | 29.7 | 31.6 |
| Beacon Hill | san_antonio | 202,424 | 558,252 | 61.5 | 30.9 | 30.6 |
| Southport | nyc | 0 | 556,407 | 0.0 | 30.6 | 30.6 |
| Inner Sunset | sf | 108,514 | 1,036,942 | 34.6 | 65.0 | 30.4 |
| Windcrest | san_antonio | 164,515 | 462,266 | 52.1 | 21.9 | 30.2 |

Pattern: 18 of 33 are in the SF metro file, 6 in San Antonio, 3 in LA, 2 in Phoenix. The SLD ranks the SF-area block groups well below the job-access gravity, and San Antonio the other way round.

Southport (nyc file, the Connecticut place) sits in a block group with D5AR exactly 0 (GEOID20 90019900000). That code pattern suggests an unpopulated or non-residential block group. It was kept as a real value, not excluded. Not investigated further.

## Method notes

- All 1,476 places matched by point-in-polygon (covers) against the 50 m candidate box. No place needed the 500 m nearest fallback. No place hit two polygons. No unmatched places. No null D5AR. One zero D5AR (Southport).
- Coordinates: `score.coordinates` (WGS84), transformed with pyproj to the layer CRS (USA Contiguous Albers Equal Area, NAD83). Gravity from `gravity_jobs(lat, lon)`, which returned a value for every place (no nulls, no zeros).
- Spearman uses average ranks for ties. Within-metro uses the metro mean of the logged values, subtracted from each place, then pooled. scipy is not installed, so ranks were computed with pandas and correlation with numpy.
- Percentile definition is my choice (the brief does not define it). Sensitivity: (r−1)/(n−1), r/n and (r−0.5)/n all give 33 places, 2.24%. The result does not depend on the definition.
- Metro counts: nyc 193, sf 113, la 105, chicago 103, philadelphia 92, boston 81, dallas 81, atlanta 76, houston 74, miami 67, phoenix 64, denver 62, austin 58, sacramento 58, tampa 50, san_antonio 49, orlando 43, charlotte 41, raleigh 31, las_vegas 30, seattle 5 (seattle excluded from the per-metro median).
- Per-metro Spearman: atlanta 0.937, austin 0.936, boston 0.939, charlotte 0.972, chicago 0.973, dallas 0.938, denver 0.819, houston 0.967, la 0.906, las_vegas 0.969, miami 0.917, nyc 0.913, orlando 0.952, philadelphia 0.921, phoenix 0.951, raleigh 0.962, sacramento 0.968, san_antonio 0.968, sf 0.716, tampa 0.931.

Scripts and intermediate outputs (scratch, not in the repo): `/private/tmp/claude-501/-Users-adamwright-Dev-home-fit/9841ed0f-a5a0-4ca5-b5d3-3542012c3299/scratchpad/l2v1/run_v1.py`, `.../l2v1/v1_summary.json`, `.../l2v1/v1_analysis_set.json`.

## Independence and data vintage

- Independence: the SLD is built from LODES jobs too. D5AR is an independent travel-time (network, time-decay) method over those jobs, not an independent jobs source. The gravity measure is also LODES (2022 grid). The comparison therefore tests method and processing, not the underlying jobs data.
- D5AR vintage: not stated in D5AR's own alias ("Jobs within 45 minutes auto travel time, time-decay (network travel time) weighted"). The geodatabase catalog (a00000004.gdbtable) shows the SLD update was created 2021-04-30 and uses 2019 Census block group boundaries. Employment fields in the same layer are labelled 2017 (for example TotEmp, 2017). The GEOID20 alias says 2018 while the field name says 2020. D5AR's own year is not found. Inferred, not confirmed: it is likely 2017-era LODES.
- Vintage mismatch: gravity uses LODES 2022, D5AR is about 2017-era. Part of the gap could be job change between those years. Not separated out.

## Criteria I think are wrong (not applied, for the owner to decide)

1. The 5 percent cap is national. It does not catch concentration. 18 of the 33 flagged places are in one metro (SF). A per-metro share of flagged places, reported with the cap, would show that better. Proposed, not applied.
2. The per-metro median (0.60) can pass while one metro is well below. SF's per-metro Spearman is 0.716, the weakest of the 20 metros. Consider a per-metro floor (for example 0.60 applied to every metro with 30 or more places, not only the median). Proposed, not applied.

## What was not verified

- Pin accuracy: V1 uses the stored score coordinates. Memory notes that metro pins can sit 5 to 15 miles off for large cities, which would move both the gravity value and the block group. Not tested.
- Block-group geometry is the SLD's 2019 boundaries, matched on point containment. No GEOID crosswalk to the catalog's Census vintage was run.
- The Southport zero and whether the other flagged block groups are data artifacts (unpopulated, water-heavy, or boundary changes) were not inspected.
- The vintage gap between D5AR (about 2017) and gravity (LODES 2022) was not controlled for.
- The per-metro and pooled results depend on the 20 metros of 30 or more places; Seattle (5 places) is in the pooled within-metro figure but not in the per-metro median.
- No check of D5AR against any other source. D5AR was read only, and nothing in the geodatabase was executed.
