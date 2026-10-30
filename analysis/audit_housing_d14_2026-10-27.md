# Audit: housing value single-tract instability (D14), 2026-10-27

Offline. Stored catalog data only (`data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl`, 21 files, 1,476 places, tracked at origin/main commit e0917b3; the catalog files were last committed 2026-10-26). No scoring code changed, no catalog written, no Census or paid API called. Distances are miles.

## 1. What I reproduced, and what I could not

**Not reproducible offline: the five named examples.** The quoted ranges (Bronzeville 18.6 to 71.5, Westwood 5 to 53, Midtown 12 to 47, Old Town 38 to 65, Hegewisch 57 to 78) came from the seven-place experiment, which read the neighboring tracts live from the Census. Those neighbor tracts are not in the catalog, and Bronzeville, Hegewisch, Old Town, Westwood, NYC Chinatown, NYC Midtown and Downtown LA are now stored as no data (D11). The catalog's "Midtown" in Houston (75.5) is a different place. The catalog stores no tract IDs, so I cannot look up an adjacent tract that is not itself a catalog pin.

**What the catalog does show, in a weaker form.** I used the catalog's own tract-level places as neighbors (two places in the same metro, different tract, found by identical stored inputs). Only 172 of the 495 tract-level places have such a neighbor within 0.87 mile (1.4 km), because catalog pins are sparse. So every count below is a floor, not the true rate.

| Measure (172 places with a neighbor within 0.87 mile) | Result |
|---|---|
| Median gap between a place and the mean of its neighbors | 7.6 points |
| 90th percentile gap | 17.3 |
| Places more than 15 points from their neighbors' mean | **30 of 172 (17%)** |
| More than 10 / more than 20 / more than 30 | 59 / 12 / 3 |
| Neighboring pairs (170): median difference / 90th percentile / maximum | 8.1 / 21.4 / 48.1 |
| Pairs more than 15 / 20 / 30 apart | 36 / 18 / 7 |

So the 20 to 40 point swings are real but they are the tail (about 1 pair in 10 at 20 points or more), not the typical case. The worst pairs: University City vs Graduate Hospital, Philadelphia (5.0 vs 53.1, 0.73 mile), Clinton Hill vs Fort Greene, Brooklyn (19.0 vs 55.0, 0.43 mile), Brewerytown vs Strawberry Mansion (66.8 vs 34.4, 0.44 mile), Francisville vs Spring Garden (73.4 vs 43.4, 0.30 mile).

Caveat on LA: 27 of the 60 LA tract-level rows do not reproduce from their own stored inputs (section 3), so LA's 5 flagged places are partly a stale-score effect. Without LA it is 25 of 162 (15%).

## 2. All-places numbers

**Exposure.** The single-tract issue only touches places whose housing data came from a tract: 495 of 1,476 (34%), of which 450 are neighborhoods and 42 are suburbs. Another 974 places (66%) use place or county subdivision data (incorporated 788, CDP 132, county subdivision 54) and are not exposed to D14 (their issue is the reverse: one place median applied to every pin inside it). Seven are no data. The 495 sit on 488 distinct tracts.

**Share more than 15 points from neighbors' mean, by area type** (stored area type; the pillar itself uses its own `detect_area_type`, so this is approximate):

| Area type | Places with a neighbor | More than 15 | Share |
|---|---|---|---|
| urban_residential | 100 | 15 | 15% |
| suburban | 63 | 12 | 19% |
| exurban | 6 | 3 | 50% |
| rural | 2 | 0 | 0% |
| urban_core | 1 | 0 | 0% |

Area type does not separate the problem: urban and suburban tracts are about equally affected, so an area-type exception would not fix it.

**By metro** (places with a neighbor, more than 15): NYC 10 of 45, Philadelphia 8 of 25, LA 5 of 10, Dallas 3 of 12, San Antonio 2 of 2, Boston 1 of 7, Denver 1 of 5. Zero of 14 Chicago, 26 SF, 8 Austin, 7 Atlanta, 5 Phoenix, 4 Charlotte, 2 Houston. Houston has 26 tract-level places but only 2 with a catalog neighbor, so "zero" there means "untested".

## 3. What the score is built from, and what drives the instability

Score = affordability (0 to 50) + space (0 to 30) + value efficiency (0 to 20), missing parts left out and the rest rescaled to 100.

| Input | Geography |
|---|---|
| Median household income | tract (or place) |
| Median home value (Zillow ZIP value replaces the Census value where Census is capped) | tract (or place); the Zillow override is ZIP level |
| Median gross rent, renter share | tract (or place) |
| Median rooms | tract (or place) |
| Metro multiplier on the value-efficiency thresholds (1.0, 1.3, 1.5) | metro, by city name |

For the 495 places all five measures are single-tract. I rebuilt the stored total from the stored inputs for every scored place: 1,439 of 1,469 match to 0.1 point, so the arithmetic below is the real arithmetic.

**Which sub-score drives it.** Among the 36 pairs more than 15 points apart, affordability is the biggest gap in 28, space in 5, value efficiency in 3. Across all 170 pairs, affordability carries 70% of the squared difference, space 20%, efficiency 10%. The mean affordability difference in the big pairs is 17.2 of 50 points. Affordability is a step function of price-to-income, so a modest change in a tract's income or value can move 5 to 10 points.

**Three causes sit under "single tract", and only one is a pooling problem.**

1. Ordinary tract-to-tract variation in income and price. Pooling smooths this.
2. The rent-only branch. 26 places (24 tract-level, 13 of them NYC) have no median owner value stored, so they score on rent only with value efficiency set to 0 (a stated design choice, D11). Their mean is 34.2 against 49.7 for other tract-level places. Leaving efficiency out and rescaling instead of scoring it 0 would add 1.2 to 15 points (median about 9) to 24 of them. Nine of the 36 big pairs involve a rent-only tract (Fort Greene, Prospect Heights, University City, Near Southside). Without rent-only tracts the pair counts are 27 of 148 above 15. Fort Greene (22% owners) shows the other effect: owners are ignored entirely on this branch. This is the D11 design choice, not a pooling effect, so I list it and do not recommend changing it here.
3. Atypical tracts. University City 5.0 sits in a tract with median income $29,464 and rent $2,630 (student households; mean income is $82,378). This is the Ann Arbor case from `analysis/housing_data_issues_fixes.md`. A median from a few hundred student households is not the neighborhood.

**A separate staleness finding (not D14).** 30 stored scores do not reproduce from their stored inputs: 27 are LA tract-level rows, plus Sedalia (Denver), one NYC and one San Antonio place. Seven LA rows store a value-efficiency sub-score above its 20 point cap (Chatsworth 29.3, El Sereno 27.6, Granada Hills 27.5). The current code would score Chatsworth about 57 not 73.0 and Granada Hills about 45 not 66.6 (the metro multiplier changes these by under 1 point). This is derivable offline from stored inputs, so it needs a recompute, not an API rescore. I checked the breakdowns first: these are not error-flag cases, the stored sub-scores themselves are out of range.

## 4. Fix options, tested on stored values

Every pooled number below pools only the catalog's own tracts within the radius, equal weight, and recomputes the score from the pooled stored inputs with the pillar's own functions (rebuilt exactly as in section 3). That is a proxy: the real pool would include every tract in the disk with population weights, which needs Census reads (section 6). Treat the move sizes as floors.

| Option | What changes | Places affected (stored data) | Size of change | Needs new Census calls |
|---|---|---|---|---|
| (a1) Pool tracts within 0.44 mile (0.7 km) | Inputs averaged across tracts in the disk, then scored | 39 of 495 have at least one other catalog tract in range | Median 3.4 points, 15 move more than 5, 8 more than 10, 5 more than 15, max 19.5. Effect on the 0 to 100 total (weight about 7.7%): median 0.26, max 1.5 | Yes, for the real version |
| (a2) Pool tracts within 0.87 mile (1.4 km) | Same, wider | 172 of 495 | Median 4.4, 76 move more than 5, 29 more than 10, 11 more than 15, max 29.7. Total: median 0.34, 90th percentile 0.97, max 2.29. Neighboring pair gaps: median 8.0 to 1.5, 90th percentile 20.1 to 6.3, pairs above 15 from 37 to 2 | Yes, for the real version |
| (b) Place or county data only when the tract is suppressed | Only the 7 no-data places get a score back | 7 | Not computable offline: the large-city place is already rejected above 200,000 units, so the fallback would be county or a wider pool. Stored neighbors exist within 0.87 mile for 4 of 7 (Old Town, Downtown LA, NYC Chinatown, NYC Midtown); Hegewisch, Bronzeville and Westwood have none within 0.87 mile | Yes (place or county table) |
| (c) Leave as is and disclose | Flag places whose score is far from tract neighbors | 30 of 172 flagged on catalog neighbors alone; the real flag needs tract neighbors | No score change | No for a catalog flag, yes for a true neighbor test |

Biggest movers under pooling (1.4 mile test): University City 5.0 to 34.7, Clinton Hill 19.0 to 45.4, Strawberry Mansion 34.4 to 59.0, Flatiron 18.8 to 39.5, Fairmount (Dallas) 70.0 to 50.0, Spring Garden 43.4 to 62.1.

**Read the pair numbers with care.** The drop in pair differences is partly mechanical: two neighbors that share tracts in their pools must score closer together. It shows pooling reduces instability; it does not show the pooled score is more correct. Nothing stored can show that. Pooling also averages away real differences between a rich and a poor tract 0.5 mile apart, which is part of why a person might choose one side.

Option (a) also solves (b) for most places: a suppressed tract drops out of the pool and the neighbors carry the score, the way `get_commute_time_stable` skips empty tracts.

## 5. Pin-shift test for the pooling option

How: take a sample of tract-level places (30 is what the transit audit used; all 495 is cheap enough here), shift the pin 0.31 mile (500 m) in 8 directions, rebuild the pool at each shifted pin, rescore, and record the change from the unshifted pooled score. Run the same shifts on the current single-tract score as the baseline, so the comparison is like for like. Report median, 95th percentile and maximum, split by area type.

Threshold: the data does not support a number. What exists:

- This audit's baseline: the current neighbor-pair gap is median 8.1, 90th percentile 21.4. A shifted pin that lands in the next tract moves the score by about that much, so pooling should clearly beat it.
- Repo precedent: the transit audit used a 5-point limit on the 95th percentile and recorded it as "set for the audit"; air travel reached a 0.6 point maximum. Neither is a derived threshold.

Judgment calls to label as such: the 5-point limit on the 95th percentile (borrowed from the transit audit), the 0.44 mile radius (copied from the commute lookup's 700 m ring; the transit audit's tested walking catchments run from about 0.47 to 0.73 mile, so a plausible range is 0.25 to 0.75 mile), and equal versus population weights. I would also report, not gate on, the rank correlation between pooled and unpooled scores within each metro, and re-run the nine launch-check contrasts, so pooling cannot quietly erase real differences.

## 6. Data needed that is not stored (listed, not run)

- Tract list inside each pool disk: the nine-point sampling the commute lookup uses is one tract lookup per point, so about 4,500 lookups for 495 places, plus about 2,200 more for a 30 place pin-shift test (30 places, 8 bearings, 9 points). Estimate, free Census geocoder.
- Population or occupied-housing-unit counts per tract (ACS B25003), for population weights. One call per distinct tract; the number of distinct tracts is unknown until the lookups run.
- Margins of error for median income, home value and rent (ACS B19013, B25077, B25064 `_001M`). This tests whether University City style tracts are sampling noise and whether to drop tracts with a large margin from a pool. Not stored anywhere. This is the one input that could tell instability from real difference.
- For option (b): place and county tables for the cities where the place is rejected.

## 7. Recommendation

Do option (a) as a side-by-side test first, not a scoring change: build the pooled score at 0.44 mile with population weights for the 495 tract-level places, store it next to the current score, run the pin-shift test and the launch check, and write nothing to the catalog until it passes. Reasons: (1) the problem is real and bounded: 34% of places are exposed, and of the 172 I could test, 17% are more than 15 points from their neighbors; (2) the one precedent in the code (commute) already pools this way; (3) pooling also restores scores for the suppressed tracts without any invented value, which keeps the fail-loud rule. Do not pick a radius or weight from this audit: both are judgment until the test runs.

Two things to decide separately, because pooling will not fix them: the rent-only branch (24 tract-level places scored with value efficiency at 0, mean 15 points below peers) and the 27 stale LA rows, which can be recomputed offline from stored inputs.

## 8. The one decision

Approve a Census read (tract lookups, population counts and margins of error for the 495 tract-level places, about 4,500 lookups plus a few thousand cached tract calls) to build the pooled score as a side-by-side test, with no catalog write until the pin-shift test and launch check pass.

## 9. Command if approved

The offline analysis in this file is reproducible with the scripts saved next to it:

```bash
cd /Users/adamwright/Dev/home-fit && python3 analysis/audit_housing_d14_scripts/analyze.py . && python3 analysis/audit_housing_d14_scripts/analyze2.py .
```

The Census read and pooled rebuild do not have a script yet. I would write `scripts/catalog/pool_housing_tracts_offline.py` (read-only against the catalog, write a separate `analysis/housing_pooled_sidebyside.jsonl`), then run:

```bash
cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/pool_housing_tracts_offline.py --radius-m 700 --weight population --out analysis/housing_pooled_sidebyside.jsonl --no-catalog-write
```

That script and its flags are a proposal; they do not exist today. (Superseded by section 10: the Census state pull and a pooling script now exist.)

## 10. Follow-up checks, 2026-10-28 (cached Census state pull, no Census calls)

Script: `analysis/audit_housing_d14_scripts/pool_areal_checks.py`. Per-place output: `analysis/audit_housing_d14_areal_places.jsonl`. Inputs: the state pull in `data/census_pull_2026-10-28/` (occupied units and 90% margins for income, value, rent, rooms) and the tract centers table (center and land area). Tract shape is approximated as a disk of the tract's land area, so membership is approximate: the disk rule picks the pin's own tract for only 74% of pins. All 495 pin tracts were identified by matching stored values; the rebuilt single-tract score is within 1 point of stored for 467 of 495. Pooled values are occupied-unit weighted means of tract medians (an approximation).

**Pooling rule.** The earlier script pooled tracts whose center fell inside the radius, which leaves the pin's own tract alone in many places. With the commute lookup's rule (pin plus 8 ring points; a tract is in if a point falls inside it), only 2% of places at 0.43 mile have just their own tract and the median pool is 5 tracts. Pooling is a bigger change than the center-rule run showed.

| Pooled ring | Median change vs single tract | 90th pct | Places moving more than 5 / 10 / 15 (of 495) |
|---|---|---|---|
| 0.25 mile | 3.4 | 12.7 | 176 / 69 / 35 |
| 0.43 mile | 4.4 | 13.1 | 214 / 85 / 39 |
| 0.75 mile | 4.6 | 16.2 | 235 / 107 / 57 |

Equal against occupied-unit weights at 0.43 mile: median 4.4 both, so the weight choice barely matters.

**Pin shift, 0.31 mile, 8 bearings, 495 places (3,960 shifts).**

| Score | Median | 95th pct | Max |
|---|---|---|---|
| Single tract | 2.6 | 23.0 | 50.1 |
| Pooled 0.25 mile | 2.1 | 13.2 | 33.5 |
| Pooled 0.43 mile | 1.9 | 9.9 | 40.8 |
| Pooled 0.75 mile | 1.9 | 8.9 | 40.5 |

Pooling at 0.43 mile cuts the 95th percentile by 57%, but no option meets the 5-point limit (a judgment borrowed from the transit audit). The shifted tract comes from the disk approximation, wrong for about a quarter of pins, so these numbers carry that error. A true test needs the geocoder (one lookup took 57 seconds for the diversity session).

**Margins of error (90% margins, normal draws).** Sampling error alone moves a single-tract score by a median sd of 5.4 points, and 56% of places have sd above 5. Pooled at 0.43 mile: 3.3 and 14%. Of the 37 neighbor pairs more than 15 points apart, 20 are within two standard errors of each other, so about half of the big gaps are consistent with sampling noise. Margins are treated as independent and normal, and renter share is held fixed (its margin was not pulled).

**Rank correlation, single tract against pooled (Spearman).** All places: 0.87, 0.83, 0.79 for the three radii. Within metro (12 metros with 15 or more places): median 0.79, 0.70, 0.64; lowest is SF at 0.44 (0.43 mile). Pooling reorders places inside a metro substantially, which is the cost to weigh against the noise reduction.

**Launch check.** The only housing contrast (rural against urban_core, minimum gap 10) still passes: gap 28.9 to 25.7. Catalog mean 56.9 to 57.3, sd 14.6 to 13.6, distinct values 77 to 73; no gate changes. The pooled effect was added to the stored score (496 rows matched by name; one name appears twice). The other 8 contrasts do not read housing.

**Effect on the recommendation.** Noise explains about half of the big gaps and a 0.43 mile pool cuts sampling error by about 40%, which strengthens the case for pooling. Against it: ranks inside a metro shift a lot, and the pin-shift limit is still missed. Still open: a geocoder-based pin shift on a sample, the radius (0.25 to 0.75 mile behave similarly; a judgment), and whether pooling is decided together with the rent-only branch.
