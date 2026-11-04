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

## Rerun 2 2026-11-03 (checks 4b, 5, pair 4) (independent verifier)
Same brief, same thresholds, seed and sample; none changed. I did not build the pillar. Owner approved in chat: the PAD-US 4.0 state downloads for 4b and live reads for check 5 on the private Overpass server (no paid Google calls, tree canopy passed as 0, seed 20261102). No code, scoring or catalog file changed. Catalog input: `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` as committed at 31bd24a9 (1,476 places). CSVs: `analysis/ao_level2_rerun2_*.csv`.

| Check | Result | n |
|---|---|---|
| 3 pair 4 Park Slope vs Brooklyn Heights | FAIL, 74.0 vs 83.4 (9.4, limit 8) | 1 pair |
| 4b trail count within 9.3 miles vs protected area, Spearman | FAIL, 0.310 (need 0.4) | 1,476 |
| 4b stored wild score vs protected area, Spearman | FAIL, 0.292 (need 0.4) | 1,476 |
| 4b same, without Boston metro | FAIL, 0.284 and 0.264 | 1,395 |
| 5 median absolute difference, daily / wild / water (limit 2 each) | PASS, 0.05 / 0.0 / 0.0 | 20 |
| 5 no place differing by more than 10 in total | FAIL, 2 places over 10 (Excelsior CA +12.4, Windsor Terrace NY +14.5); 1 of them is the expected refreshed-row case, 1 is not | 20 |

### Pair 4
Stored totals: Park Slope 74.0 (daily 25.4, wild 31.0, water 25.0; daily refreshed 2026-11-03), Brooklyn Heights 83.4 (daily 31.9, wild 34.8, water 25.0; not refreshed). The gap fell from 13.5 to 9.4 but is still over 8. Of the 9.4, daily is 6.5, wild 3.8, water 0. The re-read daily term fixed most of the daily gap; the wild values for Park Slope were kept at capped-era values on purpose, so the gap could narrow further only if wild were merged (not tested, not proposed).

### Check 4b
Downloaded the 18 PAD-US 4.0 state geodatabase zips (AZ CA CO CT DE FL GA IL IN MA MD NC NJ NV NY PA TX WA) from ScienceBase item "PAD-US 4.0 State Downloads" (652d4f80d34e44db0e2ee45c), each into its own new empty folder outside the repo; 1.37 GB; every MD5 matched ScienceBase. Same method as the first run: combined fee/designation/easement/proclamation layer, union of all polygons (every public-access category) clipped to a 15 km (9.3 mile) circle, equal-area projection (EPSG:5070); invalid polygons repaired before clipping; Spearman computed with average ranks (no scipy available, so by hand with pandas ranks). Trail count is `summary.trails.count_total`, wild is the stored wild_adventure, both as they are now. Land in states not downloaded (SC, WI, NH, RI and others) is missing near those borders, as in the first run.
- All places (n = 1,476): trails 0.310, wild 0.292. Without the Boston metro (n = 1,395): 0.284, 0.264. Open-access land only, not a criterion (n = 1,476): 0.299, 0.280.
- First run was 0.310 and 0.290 (same numbers within rounding), so the refreshes and cap removal did not move this check. FAIL on both criteria, as before.
- Downloads and unzipped copies were deleted after use.

### Check 5
20 places from `ao_level2_check5_live_vs_stored.csv` (seed 20261102, 5 per stored area type), live pillar `get_active_outdoors_score_v2` on the owner's private Overpass server (port 12345 holds all 20 states), fresh disk cache, tree canopy 0, stored area-type label held fixed (as in the first run), place context built with the repo's local density tables (`surrounding_factors`), compared with the stored rows as they are now. I called the pillar directly rather than through `/score`, because `/score` would relabel the area type (Santa Clara) and run all pillars; an API already answering on port 8000 belongs to the owner and was not used or stopped.
- Method note: my first attempt called the pillar without a place context. That leaves the people-plus-jobs density empty, the density-peer park baseline is not used, and daily came out up to 22 points off (median 8.6). That was my method error, not a pillar finding; the table below is the corrected run, which matches the check 1 method.
- Median absolute difference: daily 0.05, wild 0.0, water 0.0, total 0.1. PASS (limit 2 each).
- Differences over 3 in total: Windsor Terrace NY +14.5, Excelsior CA +12.4, Monrovia CA +9.0, Chinatown IL +8.8, Woodland Hills CA +3.2. All others are within 0.6. The four places that failed the first run (Mar Vista, Atherton, Santa Clara, Berwyn) now differ by 0.0 in total, so the 2026-11-03 refreshes worked.
- Expected, listed separately: Windsor Terrace is one of the 31 rows whose daily term was refreshed on 2026-11-03 and whose wild value was kept at the capped-era value. Stored trails 30, live 160, wild +15.9, daily 0.0. The live scorer has no trail cap now, so this difference is the intended consequence of the owner decision.
- Not expected: Excelsior CA +12.4 (daily +5.2, wild +8.4). Evidence says data age: stored park area 0.4 ha beside 51.1 ha live (15 vs 16 parks), stored trails 46 vs 82 live, stored camping 3 vs 18. This row was not in the 31 refreshed.
- Chinatown IL +8.8 (wild +9.8): stored trails exactly 30 (the old cap value), live 91; same cause as Windsor Terrace, a row scored while the cap existed and not refreshed. Under the 10 limit.
- Monrovia CA +9.0 (wild +6.5, water +4.5): stored water features 6 vs 87 live, trails 44 vs 68, camping 12 vs 29, parks 34 vs 9: data age (an older, narrower read). Under the limit.
- Woodland Hills CA +3.2: stored water features 43 vs 194 live, park count 104 vs 16: data age.
- Verdict against the criterion as written: FAIL (Excelsior and Windsor Terrace over 10). If the refreshed-row case is excluded as the owner's intended outcome, one place (Excelsior, stale data) still exceeds 10, so the verdict does not change.

### Proposed level
Level 1. Open: check 3 pair 4 (9.4 against 8), check 3 cross-type test (not rerun here; last result median 9.7, share 49.0%), check 4b (0.31 and 0.29 against 0.4) and check 5 (one non-excused place over 10, caused by catalog rows older than the current code). Passing: check 1, check 2 in full, check 3 pairs 1 to 3 and 5, check 4a, and check 5 medians.

### Files
`analysis/ao_level2_rerun2_check3_pair4.csv`, `analysis/ao_level2_rerun2_check4b_protected_land.csv`, `analysis/ao_level2_rerun2_check5_live_vs_stored.csv`. Scripts and logs were kept in the session scratchpad, outside the repo.

## Rerun 3 2026-11-04 (independent verifier, after the clean trail count)
Checks 2, 3, 4b and 5 rerun with the brief's criteria, pairs, sample and seed unchanged. I did not build the pillar. Catalog input: `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` as on branch commit b5248835 (1,476 places), not pushed. No code, scoring, scale or catalog file changed. CSVs: `analysis/ao_level2_rerun3_*.csv`. Scripts were kept in the session scratchpad, outside the repo.

| Check | Result | n |
|---|---|---|
| 2a total at or above 99.5 / at or below 10 | PASS (0 and 0; range 17.9 to 98.1) | 1,476 |
| 2b no component at cap for more than 15% | PASS (water 14.09%, wild 3.46%, daily 1.83%) | 1,476 |
| 2c empty park read has daily left out or pillar degraded | PASS (Moapa Town NV flagged degraded) | 1 |
| 3 pair 1 Mill Valley over Katy | PASS, 85.6 vs 35.8 (49.8) | 1 |
| 3 pair 2 Santa Monica over Sugar Land | PASS, 80.6 vs 49.5 (31.1) | 1 |
| 3 pair 3 Lincoln Park over Katy | PASS, 69.5 vs 35.8 (33.7) | 1 |
| 3 pair 4 Park Slope vs Brooklyn Heights | PASS, 88.6 vs 95.3 (6.7, limit 8) | 1 |
| 3 pair 5 Winnetka vs Evanston | FAIL (expected), 84.9 vs 70.9 (14.0, limit 8) | 1 |
| 3 launch pairs overall | FAIL (one miss) | 5 |
| 3 cross-type test | FAIL: median 7.8 (limit 5), share over 10 points 40.0% (limit 20%), p90 20.9 | 1,273 pairs over 924 places |
| 4b trail count within 9.3 miles vs protected area, Spearman | PASS, 0.424 (need 0.4) | 1,476 |
| 4b stored wild score vs protected area, Spearman | PASS, 0.455 (need 0.4) | 1,476 |
| 4b same, without Boston metro | PASS, 0.412 and 0.442 | 1,395 |
| 5 median absolute difference, daily / wild / water (limit 2) | PASS, 0.05 / 0.0 / 0.0 | 20 |
| 5 no place over 10 in total | PASS, largest +4.7 (Excelsior CA) | 20 |
| 5 live trail count equals stored count_total and count_within_5km | 20 of 20 identical, difference 0 on both | 20 |

### Check 2
Mean / median / p10 / p90: daily 23.0 / 23.7 / 13.5 / 32.0; wild 33.1 / 34.5 / 15.5 / 47.9; water 17.6 / 17.0 / 12.6 / 25.0; total 67.0 / 68.3 / 45.7 / 85.9. Within 0.5 of cap: daily 27 (1.83%), wild 51 (3.46%, was 5.96%), water 208 (14.09%), total 0. At or below 1: daily 7, wild 6, water 3, total 0. Total median by stored area type: urban residential 81.8 (n=200), suburban 69.5 (765), exurban 62.4 (363), rural 51.4 (145), unknown 73.0 (3). By people plus jobs per acre (stored field): 0-5 57.4 (252), 5-10 63.6 (292), 10-25 68.6 (510), 25-100 73.5 (311), 100+ 83.6 (99), no density 78.1 (12). Lowest total Mont Belvieu TX 17.9, highest Charlestown MA 98.1. The only `overpass_empty` local read is Moapa Town NV (rural): daily 0.0, `data_quality.degraded` true with reason "active_outdoors_empty_park_read". Five places have daily 0 (Moapa Town plus Perry Park CO, Georgetown CA, Pollock Pines CA, Von Ormy TX, read ok with 0 parks). Check 2 was not blind (carried over). Not run: area-type label swap.

### Check 3
Names matched uniquely on name plus state. Deciding component: pairs 1 to 3 wild (49.5 vs 6.3; 41.1 vs 11.1; 30.6 vs 6.3). Pair 4: daily 25.4 vs 31.9, wild 47.1 vs 47.9, water 25.0 both; the 6.7 gap is mostly daily (6.5). Pair 5 Winnetka vs Evanston: daily 30.8 vs 29.3, wild 42.6 vs 28.7, water 20.0 both; the 14.0 gap is wild, as the builder's documents explain (Winnetka sits beside forest preserves, 8 destinations within 3.1 miles against 1). One miss fails the launch pairs.
Cross-type test: same method as rerun 1 (within a metro, different stored area type, people plus jobs per acre within 10% of the larger; places with type `unknown` or no stored density excluded, 15 places). n = 1,273 pairs over 924 places; median 7.8, share above 10 points 40.0%, p90 20.9. FAIL on both limits, though both moved a long way from rerun 1 (9.7 and 49.0%). Reference, not a criterion: same-type pairs at the same density (n = 2,754) have median 7.7 and 38.1% above 10, so the label adds about 0.1 point; the spread comes from real geography. Pairs overlap, so they are not independent.

### Check 4b
Downloaded the same 18 PAD-US 4.0 state geodatabase zips (AZ CA CO CT DE FL GA IL IN MA MD NC NJ NV NY PA TX WA) from ScienceBase item 652d4f80d34e44db0e2ee45c, 1,371,336,242 bytes (1.37 GB), each into its own new folder outside the repo, every MD5 matched ScienceBase. Method as before: combined fee/designation/easement/proclamation layer, union of polygons of every public-access category clipped to a 15 km (9.3 mile) circle around the catalog pin, equal-area projection (EPSG:5070), invalid polygons repaired, Spearman by average ranks. Python read the files with `-I`. Trail count is `summary.trails.count_total`, wild is the stored wild_adventure, both as they are now.
- All places (n = 1,476): trails 0.424, wild 0.455. Without Boston (n = 1,395): 0.412, 0.442. Open or restricted access only, not a criterion: 0.478, 0.497. All pass (limit 0.4), up from 0.310 and 0.292.
- Caveats: land in states not downloaded (SC, WI, NH, RI and others) is missing near those borders; the 100 ha cutoff counts only large features, which tracks a large-protected-land layer by construction (the builder's own note); and the cutoff was chosen partly on this correlation, so the pass is not fully independent. Downloads and unzipped copies were deleted.

### Check 5
The 20 places of the earlier runs (seed 20261102, 5 per stored area type), live `get_active_outdoors_score_v2` called directly, OVERPASS_URL on the private server (port 12345 holds all 20: NY IL CA TX; port 12346 not needed; status checked before the run), the module's public fallback endpoints removed so no read could leave the tunnel, fresh disk cache, tree canopy 0, stored area-type label held fixed, place context from `surrounding_factors` and the stored density (as in rerun 2). No paid Google calls. All 20 reads returned ok on local, trail and regional.
- Median absolute difference: daily 0.05, wild 0.0, water 0.0, total 0.05. PASS (limit 2).
- No place over 10 in total. Largest: Excelsior CA +4.7 (daily +5.2), Woodland Hills CA +3.1 (daily +1.8, water +1.6), Monrovia CA +3.1 (water +4.5, daily -1.1). All others within 0.5. PASS.
- Trail counts: live equals stored for all 20 places, on both count_total and count_within_5km (difference 0 in every row). This confirms the live function and the catalog counts agree on these 20 (the catalog counts were built from the same function over saved reads, so the test is of the read, not an independent count).
- Data age, not code: Excelsior's daily gap is the parks read (the row was not among those refreshed on 2026-11-03; rerun 2 found stored park area 0.4 ha against 51.1 ha live). Monrovia and Woodland Hills differences sit in water and daily and match the earlier finding of an older, narrower stored water and park read. The trail term itself shows no difference anywhere.

### Proposed level
Level 1 on the criteria as written, because two items still fail: pair 5 (Winnetka vs Evanston, 14.0 against 8, expected) and the cross-type test (median 7.8 against 5, 40.0% against 20%). Checks 1 (not rerun, earlier PASS), 2 in full, pairs 1 to 4, 4a (not rerun, earlier PASS), 4b and 5 all pass. Level 2 needs an owner decision on pair 5 (the pair was fixed before any result) and on the cross-type criterion, which the builder has already argued cannot be met by a score that follows geography (same-type pairs differ by 7.7). I do not recommend changing either; those are the owner's. Open unsourced parameters: all brief thresholds, the 100 ha cutoff, the name word list, the point budgets 25, 15, 10, and the refit scale (24 per 9.3 miles, 4.0 per 3.1 miles).

### Files
`analysis/ao_level2_rerun3_check2_distribution.csv`, `ao_level2_rerun3_check2_empty_and_zero_daily.csv`, `ao_level2_rerun3_check3_pairs.csv`, `ao_level2_rerun3_check3_crosstype_pairs.csv`, `ao_level2_rerun3_check4b_protected_land.csv`, `ao_level2_rerun3_check5_live_vs_stored.csv`.

## Rerun 4 2026-11-04 (revised checks 3b and 3c, independent verifier)

Stored data only: `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` (21 metros, 1,476 places). No live calls, no code, scoring, scale or catalog change. Criteria are those of "Revision 2026-11-04" in the brief, unchanged. Total is `active_outdoors.score`; pin is `score.coordinates`; stored area type is `active_outdoors.area_classification.area_type`; people plus jobs per acre is `dpv2_recompute.activity_per_acre`. Distances are haversine miles. Pairs are within one metro file and overlap (a place appears in many pairs), so they are not independent. Script is in the session scratchpad, not the repo.

| Check | Result | n |
|---|---|---|
| 3b neighbours within 3 miles, median absolute total difference (limit 8) | PASS: median 4.0, p90 10.2, 18.9% of pairs above 8 | 2,912 pairs (all 1,476 places eligible) |
| 3c label effect (limit 2) | PASS: different-type median 7.8 minus same-type median 7.7 = 0.1 | 1,273 different-type pairs, 2,754 same-type pairs |
| Reference, not pass or fail: old pair 5 Winnetka vs Evanston | 84.9 vs 70.9, difference 14.0 (limit was 8), as in rerun 3 | 1 |
| Reference, not pass or fail: old cross-type test | median 7.8 (limit was 5), 40.0% above 10 (limit was 20%), p90 20.9, as in rerun 3 | 1,273 pairs |

3c exclusions: 3 places with type `unknown` and 12 with no stored `activity_per_acre` (15 places), leaving 1,461. Density pairing: activity within 10 percent of the larger value, same as the earlier cross-type test; the different-type group reproduces rerun 3 exactly (n 1,273, median 7.8, p90 20.9). Same-type pairs: 38.0% above 10 points; different-type 40.0%. The 3c effect is well inside the limit, so the stored area type label is not driving score differences.

10 largest 3b pairs (miles, totals, difference): Idledale and Morrison CO (2.97, 59.5 vs 90.6, 31.1); Flatbush and Fort Greene NY (2.78, 66.4 vs 94.7, 28.3); Ridgewood and Williamsburg NY (2.69, 64.5 vs 92.3, 27.8); Downtown Las Vegas and North Las Vegas (2.41, 67.1 vs 40.2, 26.9); Flatbush and Gowanus (2.66, 66.4 vs 92.5, 26.1); Flatbush and Windsor Terrace (1.69, 66.4 vs 92.5, 26.1); Greenpoint and Ridgewood (2.65, 90.6 vs 64.5, 26.1); Ditmas Park and Gowanus (2.67, 66.5 vs 92.5, 26.0); Ditmas Park and Windsor Terrace (1.41, 66.5 vs 92.5, 26.0); Arcadia and Camelback East AZ (2.48, 76.5 vs 52.0, 24.5). Eight of the ten are Brooklyn, where nearby places differ by about 26 points; not examined further here.

Conclusion: both revised checks pass (3b median 4.0 against 8; 3c 0.1 against 2). Checks 1, 2, 3 pairs 1 to 4, 4a, 4b and 5 are as in rerun 3 and were not rerun. On that basis the pillar meets "Level 2 against criteria revised after the first run": the revision came after the results were seen, so it is not a blind pass, and the thresholds 8 and 2 remain unsourced (TODO).

Files: `analysis/ao_level2_rerun4_check3b_neighbour_pairs.csv`, `analysis/ao_level2_rerun4_check3c_density_pairs.csv`.

### Follow-up 2026-11-04 (builder): Brooklyn neighbour gaps, from stored files and the local density tables, no new reads
The largest check 3b gaps (Flatbush and Ditmas Park about 66 vs Gowanus, Windsor Terrace and Fort Greene about 92 to 95) are not stale reads. Independent evidence from rerun 1 (NYC Parks Properties polygons, distance-weighted count within 1.2 miles, `analysis/ao_level2_check4a_city_parks.csv`): Flatbush 4.3, Ditmas Park 5.1, Ridgewood 5.6 against Park Slope 10.8, Gowanus 13.2, Fort Greene 19.8, Brooklyn Heights 26.5, Williamsburg 31.8. The city's own polygons agree that Flatbush and Ditmas Park have few parks.
The outlier is Windsor Terrace: OSM weighted count 75.7 but city count 10.5 (below Park Slope and Gowanus), yet it has the highest daily term of the group (34.3). Cause: the 0.6 mile disk around its pin holds 15,913 people per square mile against about 65,000 for Park Slope and Flatbush, because the disk includes Prospect Park and Green-Wood Cemetery. Activity per acre is 32 (peer median expectation 11.8 parks) against 125 to 129 (expectation about 40). A park-rich surrounding lowers the measured density, which lowers the bar the park count is judged against, so the same park count scores much higher. This is a consequence of the density-peer design, not a stale row. Nothing changed; a fix is a design decision (for example measuring density without park and water land, or from tracts only) and needs owner approval.

### Scope of a density fix (builder, 2026-11-04, local tables only, no reads; nothing changed)
Candidate: population-weighted density (people per acre as an average resident experiences it, a standard research measure) in place of gross people per acre over the 0.6 mile disk, so a park or cemetery inside the disk no longer lowers the bar. Over the 1,123 places with tract and jobs data the activity measure changes by a median factor 1.01 (90th percentile 1.17, maximum 3.44) and the expected park count by a median 1.00; 43 places move more than 25% and 13 more than 50% (Windsor Terrace 12.2 to 33.8 expected parks, Red Hook 15.9 to 33.9, Pilsen 9.5 to 18.9, Packer Park, Strawberry Mansion, Visitacion Valley, Inwood 30.2 to 44.4, Flushing 22.0 to 35.2). Nobody's baseline falls.
But it would move Windsor Terrace's park count term only from 21.9 to 19.7 of 22 (about 2 points), because its OSM weighted count (75.7) is far above even the corrected expectation. The larger driver of the Brooklyn gap is the count itself: 96 OSM park features within 0.6 miles against 33 city polygons within 1.2 miles (weighted 75.7 vs 10.5), which suggests OSM maps parts of Prospect Park and Green-Wood as many separate parks. Not yet verified, because the stored data keeps only counts, not the feature list.
Also: the activity measure is shared with the area-type classifier, so changing it changes area labels for other pillars unless it is pillar-private, which principle 14 discourages; it would need coordination with the other pillars in flight.

### Windsor Terrace park list (one read, 2026-11-04, owner approved in chat; `analysis/ao_windsor_terrace_park_list.json`)
The 96 "parks" within 0.6 miles are mostly not parks: 65 are under 0.5 ha and 29 under 0.1 ha, and many are named paths in Green-Wood Cemetery (Vine Path, Vernal Path, Landscape Path, Gladiolus Path, Dawn Path, Amaryllis Path, Viburum Path, Canna Path) or streets and cycleways (Cycleway Path four times, Fort Hamilton Parkway twice). This is the same counting problem the trail term had: street, path and cemetery-section features counted as parks, and repeated names counted more than once. The weighted OSM count (75.7) therefore overstates Windsor Terrace; the city polygon count (10.5) is the plainer measure. The park count term (22 points) and the park density baseline (peer medians fitted on these same counts) both inherit it. Nothing changed.

### Scope of a clean park count (builder, 2026-11-04; from the 2026-10-27 fresh park reads, no new reads; nothing changed)
Root cause: `osm_api.query_green_spaces` returns recreational cycleways and footways as park entries (types `greenway_cycleway` and `greenway_footway`; the code comment says cycleways are always included), and the daily park count, its nearest-park term and the park baseline all count them. At Windsor Terrace 75 of the 96 entries within 0.6 miles are of those two types (62 footways such as the Green-Wood Cemetery section paths, 13 cycleways), leaving 21 park-like entries (park 11, garden 6, dog park 3, playground 1).
Size, from `analysis/ao_fresh_parks_uncovered/` (1,464 places with a fresh read; type was not saved, so a name match stands in): 30.6% of park entries within 1.2 miles are path or street named ("Cycleway Path" alone is 9,785 of them, 13% of all entries; "Garden", "Park" and "Recreation Ground" are the other generic names). 609 places lose more than 25% of their entries and 157 more than 50%. A refit of the park baseline on the cleaned counts falls about 25 to 30% (at 100 people plus jobs per acre: 34.1 to 23.1 expected parks; at 45: 18.1 to 12.7). Estimated change in the daily park count and nearest-park terms (playgrounds and facilities unchanged): median +0.4, 167 places move more than 3 points, 53 more than 6, largest drop 21.7 (Steele Creek NC, Johns Creek GA, Senoia GA: places whose "parks" are mostly cycleways). Windsor Terrace about -4.8, Gowanus -2.7, Ditmas Park -3.3, Park Slope -0.5, Flatbush +0.9, so the Brooklyn neighbour gap narrows by about 5 points but does not close.
Proposed rule (type-based, no word list): count only park, garden, dog park, playground, recreation ground and golf course entries; drop the two greenway types; then refit the baseline and recompute the park terms. Live reads needed: no for the estimate; for the build one read per place with type saved (about 2 seconds each, about 50 minutes for 1,476 places) or a 5-place pilot first. Decision for the owner: should recreational cycleways and footways count as parks for daily outdoors? The earlier design said yes (bike paths are recreational); the data says it lets paths and street-named footways outweigh parks.

### Park count options compared (builder, 2026-11-04; saved 2026-10-27 reads, name match stands in for type; nothing changed)
A = as now; B = drop path-like and street-like names; C = keep each distinct path or greenway name once, drop street names. Baseline refit per option. Park count plus nearest-park terms, baseline at 100 people plus jobs per acre: A 32.2, B 21.4, C 23.9 expected parks.
| Place | Entries A / B / C | Park terms A, B, C |
|---|---|---|
| Windsor Terrace NY | 279 / 64 / 238 | 26.9, 22.1, 26.9 |
| Sunset Park NY | 219 / 33 / 201 | 22.0, 12.1, 23.7 |
| Steele Creek NC | 24 / 2 / 3 | 23.2, 1.8, 4.7 |
| Johns Creek GA | 24 / 8 / 10 | 21.8, 5.6, 9.4 |
| Flatbush NY | 46 / 34 / 38 | 8.0, 8.7, 8.6 |
Places moving more than 3 points: B 403, C 144 (more than 6: B 92, C 37). Option C collapses repeated generic segments ("Cycleway Path") but leaves the Green-Wood section paths, which have distinct names, so Windsor Terrace is unchanged.
Independent yardstick (Spearman of the weighted count with city park polygons, 194 in-city places in NYC, Chicago and LA): A 0.822, B 0.836, C 0.833; NYC 0.77 / 0.81 / 0.77, Chicago 0.58 / 0.61 / 0.61, LA 0.22 / 0.23 / 0.20. The city polygons contain no cycleways, so they favour B by construction, and the gain is small. The evidence does not show the current count is badly wrong at the ranking level; the damage is in specific places (suburbs whose only amenity is a cycleway network; cemetery paths).

### Trial of the simple park change (builder, 2026-11-04; `analysis/ao_simple_park_trial.csv`; stored data plus the 2026-10-27 reads; nothing merged)
Change tried: park count from real parks only (path-like and street-like names stand in for the cycleway and footway types, which the saved reads did not keep), density as population-weighted people per acre, park baseline refit (expected parks at 100 per acre: 34.1 to 17.6), no new terms. 1,464 of 1,476 places have a fresh read; the other 12 keep their score. Only the park count and nearest-park terms move.
- Active outdoors total: median +0.4, 10th to 90th percentile -4.3 to +2.8; 347 places move more than 3 points, 75 more than 6; largest drops Morrison CO -20.2, Steele Creek NC -19.3, Johns Creek GA -14.6, Rancho Murieta CA -14.1, Senoia GA -13.9; largest rise +4.2. Range 17.9 to 98.0; none at 99.5 or above or at 10 or below; daily at cap 1.8% to 1.0%.
- Windsor Terrace daily 34.3 to 23.8 (total 92.5 to 83.0); Park Slope 25.4 to 26.1; Windsor Terrace minus Park Slope daily +8.9 to -2.2. Flatbush 12.8 to 13.5, Ditmas Park 11.4 to 8.4, Fort Greene 31.5 to 33.7, Brooklyn Heights 31.9 to 31.3.
- Launch pairs: Mill Valley 86.3 vs Katy 39.0, Santa Monica 80.4 vs Sugar Land 49.4, Lincoln Park 71.7 vs Katy 39.0, Park Slope 89.2 vs Brooklyn Heights 94.7 (gap 5.5): all still pass. Winnetka 84.9 vs Evanston 72.2 (gap 12.7, the retired pair 5).
- Check 3b: median 4.0 (unchanged), 90th percentile 10.3, 19.0% above 8.
- Independent yardstick, daily term vs city park polygons (198 in-city places): Spearman 0.532 before, 0.516 after, so no improvement at the daily-term level.
- Bike paths and park paths: of 796 places with three or more generic cycleway entries, only 21 (3%) have fewer than 5 real parks within 1.2 miles; of 365 with ten or more, 6. Most places with paths also have real parks, which is why the median barely moves; the cost falls on a few dozen path-only places. Whether the paths lie inside the parks cannot be tested from these files (no coordinates).
Open: the build with type saved (about 50 minutes of reads) replaces the name stand-in; the trial's exact numbers will shift.
