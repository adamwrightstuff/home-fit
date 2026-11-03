# Active outdoors: Level 2 verification results (2026-11-02)

Run by the independent verifier (did not build the pillar), against `docs/ACTIVE_OUTDOORS_LEVEL2_BRIEF.md` with the criteria as fixed there
and approved by the owner on 2026-11-02. No criterion was changed after results were seen. No scoring, code or catalog file was changed.
Pillar code as on this branch's base; catalog files `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` (1,476 places).
Distances in miles. One CSV per check is in `analysis/` (`ao_level2_check*.csv`).

## Summary

| Check | Result | n |
|---|---|---|
| 1 Pin-shift sensitivity | PASS | 60 places, 480 shifted reads |
| 2 All-places | FAIL (criterion c; a and b pass) | 1,476 |
| 3 Launch pairs | FAIL (pair 4) | 5 pairs |
| 3 Cross-type test | FAIL | 1,317 pairs |
| 4a City park polygons | PASS | 198 places |
| 4b PAD-US protected land | FAIL | 1,476 (1,395 without Boston) |
| 4c Water layer | not run (owner did not provide a layer; report-only) | 0 |
| 5 Live scorer vs catalog | FAIL (total difference over 10 in 4 of 20) | 20 |

Proposed level: **Level 1**, not Level 2 (five of the criteria fail).

## Check 1: pin-shift sensitivity: PASS
Sample: seed 20261102, 15 places per stored area type (urban residential, suburban, exurban, rural), drawn from the 11 states on the private Overpass server (NY NJ CT CA WA TX IL IN PA DE MD), sorted by name then state before sampling. Each pin was shifted 500 m and 1,000 m (0.3 and 0.6 miles) north, east, south, west: 480 shifted reads plus 60 fresh unshifted reads, all on the owner's private server, no paid calls. Each shifted pin was scored with `get_active_outdoors_score_v2` as it is. Change is measured against the fresh unshifted score of the same place (same data age), not the stored one.

| Shift | n | median | 95th pct | share over 10 | largest |
|---|---|---|---|---|---|
| 500 m (0.3 mi) | 240 | 1.7 (limit 3) | 5.5 (limit 10) | 0.4% | 13.7 Atherton CA |
| 1,000 m (0.6 mi) | 240 | 2.7 (limit 5) | 8.4 (limit 15) | 2.9% | 18.6 Atherton CA |

- Over 10 points: Atherton CA (4 reads, all four of them at 1,000 m or the west 500 m shift), Morningside Heights NY (2 reads at 1,000 m).
- Reads that returned an empty park read where the unshifted one did not: 4, all Von Ormy TX (rural, 0 parks within the radius either way; daily 0.0 in the unshifted and shifted runs, score change 0 to 0.4). Rerun once: still empty. None was an all-empty read, so none counts as a pillar failure. No read errors or timeouts.
- Fresh unshifted score vs stored score, 60 places: median absolute difference 0.1.
- Disclosed method choices: the stored area type was held fixed for shifted pins; people-plus-jobs density was recomputed at each shifted pin from the repo's local tables; tree canopy was passed as 0 to avoid an Earth Engine call. Canopy enters the score only through the special-context flags; I did not test whether that changes any score.

## Check 2: all-places check: FAIL on (c)
Descriptive numbers over all 1,476 places (mean / median / p10 / p90; share within 0.5 of cap; share at or below 1):

| Component | mean | median | p10 | p90 | at cap | at or below 1 |
|---|---|---|---|---|---|---|
| daily (cap 35) | 22.9 | 23.5 | 13.3 | 31.9 | 1.76% | 0.47% |
| wild (cap 50) | 33.5 | 34.0 | 18.9 | 48.2 | 5.96% | 0.20% |
| water (cap 25) | 17.6 | 17.0 | 12.6 | 25.0 | 14.09% | 0.20% |
| total | 67.3 | 68.9 | 47.1 | 85.1 | 0.0% | 0.0% |

By stored area type (total, median): urban residential 70.8 (n=197), suburban 71.5 (764), exurban 65.7 (363), rural 52.4 (148), unknown 78.9 (4). By density band (total, median): 0-5 58.1 (253), 5-10 67.6 (292), 10-25 70.1 (511), 25-100 71.4 (317), 100+ 71.8 (99), no density 73.6 (4). Full table with every component in `ao_level2_check2_distribution.csv`.

- (a) total at or above 99.5: 0 (0%); at or below 10: 0 (0%). PASS.
- (b) no component at its cap for more than 15%: water is highest at 14.09% (208 places); daily 1.76%, wild 5.96%. PASS, with little margin on water. Surprising: in the 100+ band 48% of places sit at the water cap, and 26% in the 25-100 band.
- (c) places with an `overpass_empty` park read: 1 (Moapa Town NV, rural). Its daily term is 0.0, not left out (`components_missing` is empty) and the pillar is not flagged degraded. FAIL, n=1. The builder expected 4; the stored data holds 1. Five places have daily 0: Moapa Town (empty read) and Perry Park CO, Georgetown CA, Pollock Pines CA, Von Ormy TX (all rural, read `overpass_ok`, 0 parks; these are real zeros by the criterion's wording, not failures).
- Not required, not run: the area-type-label swap needs a code run.

## Check 3: launch pairs: FAIL
| # | Pair | Scores | Difference | Rule | Result | Decided by |
|---|---|---|---|---|---|---|
| 1 | Mill Valley CA vs Katy TX | 83.7 vs 42.7 | 41.0 | at least 10 | pass | wild 47.4 vs 13.9 |
| 2 | Santa Monica CA vs Sugar Land TX | 86.4 vs 55.2 | 31.2 | at least 10 | pass | wild 47.4 vs 17.4 |
| 3 | Lincoln Park IL vs Katy TX | 72.4 vs 42.7 | 29.7 | at least 10 | pass | wild 33.7 vs 13.9 |
| 4 | Park Slope NY vs Brooklyn Heights NY | 69.9 vs 83.4 | 13.5 | within 8 | **FAIL** | daily 20.9 vs 31.9 (11.0), wild 31.0 vs 34.8 |
| 5 | Winnetka IL vs Evanston IL | 89.7 vs 83.2 | 6.5 | within 8 | pass | wild 47.9 vs 42.2 |

One miss fails the check.

Cross-type test: pairs within a metro, people plus jobs per acre within 10% of each other (relative to the larger), different stored area types (the 4 places with type `unknown` or no density excluded; decided before running). n = 1,317 pairs over 932 places. Median absolute total difference 9.9 (limit 5); share above 10 points 49.4% (limit 20%); 90th percentile 23.2. FAIL. The pairs overlap (a place appears in many pairs), so they are not independent; the criteria did not account for that.

## Check 4a: parks against city polygons: PASS
Downloaded 2026-11-02 into separate new folders: NYC Parks Properties `enfh-gkve.geojson` 7.96 MB (2,061 polygons), Chicago Park District `ejsh-fztr.geojson` 2.72 MB (617), City of Los Angeles Recreation and Parks `4jt3-efvk.geojson` 4.21 MB (566; State Plane feet EPSG:2229, reprojected). Counts match the 2026-10-27 download. City park polygon centroids within 2,000 m (1.2 miles), weighted exp(-0.0012 x metres); places inside each city by the repo's Census place outlines (`data/principal_city_places.parquet`).

| Scope | n | Spearman, OSM weighted count vs city weighted count | Spearman, stored daily vs city weighted count |
|---|---|---|---|
| All | 198 | 0.820 (need 0.6) | 0.451 (need 0.3) |
| New York | 96 | 0.775 | 0.547 |
| Chicago | 46 | 0.584 | 0.400 |
| Los Angeles | 56 | 0.220 | 0.147 |

Positive in every city. Both criteria met. Deviations: (1) the place count is 198, not 197 (one more New York place falls inside the outline; I did not find which one the builder dropped); (2) the brief names `analysis/ao_fresh_parks_uncovered/` for the weighted OSM count, but that folder only holds the 545 places in states outside the private server, none in these cities. I used the `decay_weighted_count` column of `analysis/active_outdoors_parks_term_recompute_decay_2026-10-28.csv` (builder's stored fresh read of 926 places), at the radius that file used per place, which I could not confirm is exactly 2,000 m. Surprising: Los Angeles alone is weak (0.22, 0.15); the overall pass leans on New York and Chicago.

## Check 4b: trails against PAD-US: FAIL
PAD-US 4.1 state files sit behind a ScienceBase login (cloud storage), which I cannot create or use, so I used the PAD-US 4.0 state geodatabases (public, 18 catalog states, 18 zip files, 1.37 GB total, from item "PAD-US 4.0 State Downloads"; for example CA 131.7 MB, PA 127.3 MB, NY 77.2 MB, AZ 30.2 MB). Layer: the combined fee/designation/easement/proclamation layer. Protected land area = union of all polygons (every public-access category, as the brief reads) clipped to a 15 km (9.3 mile) circle. Land in states not downloaded (for example SC, WI, NH, RI) is missing near those borders.

| Scope | n | trail count (15 km) vs area | wild score vs area |
|---|---|---|---|
| All places | 1,476 | 0.310 (need 0.4) | 0.290 (need 0.4) |
| Without Boston metro | 1,395 | 0.284 | 0.263 |
| Open or restricted access only (not a criterion) | 1,476 | 0.298 | 0.279 |

FAIL on both. Removing Boston did not help.

## Check 4c: not run
No coastline or lake layer was provided and the brief makes it report-only.

## Check 5: live scorer against the catalog: FAIL
20 places (seed 20261102, 5 per stored area type) drawn from the check 1 sample; their fresh unshifted reads from check 1 are the live runs (same method choices as check 1). Median absolute differences: daily 0.15 (limit 2), wild 0.0 (limit 2), water 0.0 (limit 2): pass. Largest total differences: Mar Vista CA +16.9, Atherton CA +14.4, Santa Clara CA +14.1, Berwyn IL -11.4 (limit 10): four places over, FAIL. Others over 3: Monrovia CA +9.0, Windsor Terrace NY +6.9, Excelsior CA +4.3. Wild accounts for most of the large gaps (Berwyn -13.1, Mar Vista +10.0, Atherton +8.7, Monrovia +6.5); Mar Vista also water +7.3. I did not establish whether this is stored data age or a code difference; the live read is of 2026-11-02 and the catalog was scored earlier, which is consistent with data age but unproven. Atherton was also the least stable place in check 1.

## Open and unsourced parameters
All thresholds in checks 1, 2(a,b), 3, 4a, 4b and 5 are unsourced (builder's choice, owner accepted). Check 2 was not blind. Items needing an owner decision beyond the criteria: whether 4b should use open-access land only; whether the stored `overpass_empty` handling of Moapa Town is a bug; the weighted OSM radius in 4a.

## Proposed level
Level 1. Level 2 would need checks 2(c), 3, 4b and 5 to pass; I did not recommend scoring changes.

## Files
Downloaded files were deleted after use at the owner's request. The verifier scripts and raw read logs were temporary and have been deleted; the CSVs in `analysis/` hold the per-place results.

## Follow-up investigation (same day, after the owner asked to look into the failures)
The check results above stand; nothing below changes a verdict, and no catalog, code or scoring file was changed.

- **Moapa Town (check 2c).** A fresh read on the second private server (AZ CO FL GA MA NC NV) returns `overpass_empty`, 0 parks and 0 playgrounds within 2,000 m (1.2 miles), so the empty read is not a failed read. Outside sources: Clark County's park locator lists Ron Lewis Park (1255 Patriots Way, Moapa; playground, ball field, spray park, community center), and OSM holds a park with a playground about 1.9 miles from the stored pin and the Moapa Recreation Center park about 2.9 miles away. The stored pin is about 1.5 miles west of the town's centre (Wikipedia coordinates 36.692, -114.608 against pin 36.6925, -114.6356). So the zero is true to the pillar's 1.2 mile radius and comes from the pin position. Whether such a zero should count as "no data" is an owner rule decision; check 2(c) as written treats it as no data and the pillar treats it as zero.
- **Berwyn IL (check 5, -11.4).** The live pillar caps trails at about 30 for urban area types (urban core, urban residential, urban lowrise). The catalog holds 151 trails for Berwyn (no cap applied when scored); the live run with its stored label keeps 30 and wild falls from 48.0 to 34.9. Why the catalog was scored without the cap was not established.
- **Mar Vista CA (check 5, +16.9).** Stored data is stale: stored 259 parks vs 2 live, 43 camping sites vs 4, 10 trails vs 30 (the builder had flagged New York and Los Angeles counts as stale).
- **Atherton CA (check 5, +14.4).** Stale catalog. A rescore through the local API into a separate file (`/tmp`, not the catalog) gave 76.9 (daily 30.4, wild 37.6, water 16.6), identical to the check 5 live run; stored is 62.5.
- **Santa Clara CA (check 5, +14.1).** The stored area classification density is 2.3 people per square mile (wrong for a city of that size) and gives the label rural. The local density tables give 25.6 people plus jobs per acre, and the API labels it urban residential. Check 5's live run kept the stored label rural and scored 77.0 (83 trails, 42 parks); the API rescore scored 68.5 (30 trails after the urban cap, 12 parks). Same place, same data, 8.5 points apart by label.
- **Size of the label mismatch.** 24 of 1,472 places with a density value are labeled rural or exurban at 25 or more people plus jobs per acre; 5 have a stored density under 100 per square mile and 10 or more per acre (Santa Clara CA, Clarksburg CA, Glendale NY, Maspeth NY, Pelham Bay NY).
- **Not investigated:** why SF-metro trail counts are about 24 higher live than stored for Atherton and Santa Clara beyond data age; check 4b (trail and wild score vs protected land) and the check 3 pair 4 gap (Park Slope vs Brooklyn Heights).

## Rerun 2026-11-03 (independent verifier)
Checks 2 and 3 rerun on stored data only, after commits 5bb9b2f6 (label-based trail cap removed, pillar flags degraded on an empty park read) and fba4bc9e (8 rows refreshed, Moapa Town flagged degraded). Same brief, same thresholds and pairs, none changed. I did not build the pillar. Input: `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl`, 1,476 places. No code, scoring or catalog file changed; no live call, no Overpass tunnel, no download. Checks 4b and 5 were not run (see below). Script is outside the repo (session scratchpad); CSVs are `analysis/ao_level2_rerun_*.csv`.

| Check | Result | n |
|---|---|---|
| 2a total at or above 99.5 / at or below 10 | PASS (0 and 0) | 1,476 |
| 2b component at cap | PASS (highest: water 14.09%) | 1,476 |
| 2c empty park read has daily left out or pillar degraded | PASS (1 place, flagged degraded) | 1 |
| 3 pair 1 Mill Valley over Katy | PASS, 83.7 vs 42.7 (41.0) | 1 |
| 3 pair 2 Santa Monica over Sugar Land | PASS, 86.4 vs 55.2 (31.2) | 1 |
| 3 pair 3 Lincoln Park over Katy | PASS, 72.4 vs 42.7 (29.7) | 1 |
| 3 pair 4 Park Slope vs Brooklyn Heights | FAIL, 69.9 vs 83.4 (13.5, limit 8) | 1 |
| 3 pair 5 Winnetka vs Evanston | PASS, 89.7 vs 83.2 (6.5) | 1 |
| 3 launch pairs overall | FAIL (one miss) | 5 |
| 3 cross-type test | FAIL (median 9.7, limit 5; share over 10 points 49.0%, limit 20%) | 1,273 pairs |

### Check 2
Mean / median / p10 / p90: daily 22.9 / 23.5 / 13.4 / 31.9; wild 33.6 / 34.2 / 18.9 / 48.2; water 17.6 / 17.0 / 12.6 / 25.0; total 67.3 / 69.1 / 47.1 / 85.1. Within 0.5 of cap: daily 1.76% (26), wild 5.96% (88), water 14.09% (208), total 0%. At or below 1: daily 0.47% (7), wild 0.20%, water 0.20%, total 0%. By stored area type, total median: urban residential 71.2 (n=200), suburban 71.5 (765), exurban 65.9 (363), rural 52.3 (145), unknown 78.2 (3). By density band (people plus jobs per acre, stored field): 0-5 58.1 (252), 5-10 67.6 (292), 10-25 70.2 (510), 25-100 71.4 (311), 100+ 71.8 (99), no density 75.9 (12). Per-group component table in `ao_level2_rerun_check2_distribution.csv`.
- (c): the only `overpass_empty` local read is Moapa Town NV (rural). Daily is still 0.0 and `components_missing` is empty, but `data_quality.degraded` is now true with reason "active_outdoors_empty_park_read: daily term scored as zero". The criterion accepts "pillar flagged degraded", so PASS. It is the only degraded active_outdoors row in the file (1 of 1,476). Five places have daily 0: Moapa Town (empty read, degraded) and Perry Park CO, Georgetown CA, Pollock Pines CA, Von Ormy TX (read `overpass_ok`, 0 parks, not flagged). Per the brief those four are real zeros, not empty reads.
- Caveat carried over: check 2 was not blind.

### Check 3
Names matched uniquely on `catalog.name` plus state. Deciding component: pairs 1 to 3 are decided by wild (47.4 vs 13.9; 47.4 vs 17.4; 33.7 vs 13.9). Pair 5 is decided by wild (47.9 vs 42.2).

Pair 4 still fails, unchanged from the first run (69.9 vs 83.4). Park Slope: daily 20.9, wild 31.0, water 25.0. Brooklyn Heights: daily 31.9, wild 34.8, water 25.0. Of the 13.5 point gap, daily is 11.0 (deciding), wild 3.8, water 0. Neither row was among the refreshed ones.

Cross-type test: within each metro, pairs with different stored area types and activity (people plus jobs per acre, stored `dpv2_recompute.activity_per_acre`) within 10% of the larger. Excluded: places with type `unknown` (3) and places with no stored activity density (12; the 8 refreshed rows Berwyn, Mar Vista, Glendale, Maspeth, Pelham Bay, Clarksburg, Atherton and Santa Clara lost that field when refreshed, plus Moapa Town, Larkspur, Orinda, Woodside which had none). Up to 15 places are excluded against 4 in the first run (the exact overlap between the two exclusions was not counted), so n is 1,273 pairs over 924 places, not 1,317 over 932. Median absolute total difference 9.7, share above 10 points 49.0%, 90th percentile 23.0. FAIL. The pairs overlap, so they are not independent. Because the eight refreshed rows are missing from the test, the result is not exactly comparable to the first run; the shift (median 9.9 to 9.7, share 49.4% to 49.0%) is small and no direction would reach the limits.

### Checks not run
- 4b (trails and wild vs PAD-US protected land within 9.3 miles): needs a download of PAD-US state geodatabases. The first run used PAD-US 4.0 because the 4.1 state files sit behind a ScienceBase login. It needs 18 zip files, about 1.37 GB in total (for example CA 131.7 MB, PA 127.3 MB, NY 77.2 MB, AZ 30.2 MB), each into its own new empty folder, scripts kept elsewhere and Python run with `-I`. The owner must approve the download again. Note the stored trail and wild fields changed for refreshed rows and by earlier offline recomputes, so the result could move, but a trail cap change alone is not expected to lift a 0.31 and 0.29 correlation to 0.4.
- 5 (live scorer vs catalog, 20 places): needs live pillar calls on the owner's private Overpass servers (NY NJ CT CA WA TX IL IN PA DE MD server, plus the AZ CO FL GA MA NC NV server if a place falls there), no paid Google calls, tree canopy passed as 0 as before, and the same 20 places (seed 20261102, 5 per stored area type). The owner must approve opening the tunnel. Of the four places that failed before (Mar Vista, Atherton, Santa Clara, Berwyn), all four were refreshed in fba4bc9e, so a rerun is where the fix would show.

### Proposed level
Still Level 1. Checks 3 (pair 4 and the cross-type test), 4b and 5 are open or failing; check 2 now passes in full.

### Follow-up 2026-11-03: cause of pair 4 and cross-type failures (builder, stored data)

Pair 4: 31 old-format rows (5 LA, 26 NYC) came from a failed or empty original park read (parks_count 0), so their stored park area was near zero (Park Slope 1.6 ha beside Prospect Park). All 31 were re-read; the new daily terms were merged (Park Slope daily 20.9 to 25.4, total 69.9 to 74.0). The re-read also lifted wild by 15 to 20 points for about 20 inner NYC places because the removed trail cap lets every inner NYC place count 175 to 188 greenway route relations; those wild values were NOT merged (owner decision 2026-11-03: daily only). Pair 4 needs a verifier rerun.

Cross-type test: places at the same density with the same area type differ by a median 8.5 points in total (n=2,754 pairs), with different types by 9.7 (n=1,273). The label adds about 1 point; the rest is real variation in trails, water and parks. The criterion as written cannot be met by a score that responds to geography. A replacement ("cross-type median no more than 2 points above same-type median") would apply to the next round only.
