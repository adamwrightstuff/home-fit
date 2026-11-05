# Proposal: redesign the active outdoors baselines so they do not depend on the area type (2026-10-27)

Status: PROPOSAL FOR DECISION. Nothing is implemented. Evidence: `analysis/active_outdoors_continuous_baseline_pilot_2026-10-27.md` (parts 1 to 3), `analysis/area_type_activity_density_proposal_2026-10-27.md`.

## Why

Active outdoors uses the area type in four places, and each one produces jumps when a place crosses a type line:

1. The park and playground expectations (a table of values per type). For places of nearly equal density that land in different types, the daily outdoors score differs by 18.2 points between exurban and suburban and 6.0 between suburban and urban residential. The table does not match the catalog: the exurban bar is 0.08 parks per km2, the suburban 9.05 and the urban residential 28.65, while the catalog medians rise smoothly from 0.4 to 18.8 with density.
2. The trail expectations and point budgets per type. For the same counts of 5 trails and none near, the wild adventure score is 39.8 as exurban and 11.1 as suburban.
3. A "mountain town" flag that switches branches. It flags 77% of the catalog (91% of suburban places) and, for dense places, switches the scoring type to exurban (59 of 197 dense places, 30%). The thresholds rest on three example cities in the comments.
4. Small water multipliers (0.9 to 1.0, 0.75 for urban core). Their effect is a mean of -0.18 points and they carry no source.

The shared area type is also being redefined. Removing the pillar's dependence on it means the pillar no longer moves when the type rule changes.

## Principles (from DESIGN_PRINCIPLES.md)

- Expected values come from empirical data, not from target scores. Unsourced numbers stay marked TODO.
- No special cases by city or by a hidden second area type.
- Offline recompute from stored data before any rescore.

## Proposed design, term by term

| Term (points) | Today | Proposal |
|---|---|---|
| Park count (22) | Expected count per type, at each type's own radius | Expected parks per km2 as a smooth, monotone function of people plus jobs per acre, fitted to the catalog; expected count = density times the area of the radius the count was taken at. The score barely depends on the radius. |
| Playgrounds (5) and facilities (3) | Same, per type | Same method; facilities need a stored count (not in the catalog today) |
| Nearest meaningful park (8) | Exponential decay, no type | Unchanged |
| Trails within 15 km (up to 25 to 35) and within 5 km (up to 12 to 20) | Per-type expectations, budgets and a 2.6 times urban discount, plus the mountain-town branch | One scale for all places. Remove the mountain-town flag and its type override. Choose the expectation from the catalog's distribution of counts (medians about 58 within 15 km and 7 within 5 km), not by type. Decision needed: an absolute scale or a metro-level expectation. |
| Camping (10) | Three decay curves by type | One curve |
| Water (25) | Type multipliers | Drop the multipliers (largest effect 1.8 points) or keep and source them |

## What it would change

- Cliffs at type lines disappear for parks (exurban versus suburban gap from +18.2 to -0.4 points, suburban versus urban residential from +6.0 to -1.7 in the pilot).
- Over all 1,468 places, the park-term change moves the whole active outdoors score by a mean of -0.8 (10th percentile -13.7, 90th percentile +8.5), rank correlation with the stored scores 0.817. The trail change would add to this; it has not been computed.
- The 441 places whose type changes see a smaller shock: mean absolute change of the whole score 6.5 points against 10.6 under the type table.
- The catalog's active outdoors scores are mostly consistent with today's code (94% of stored wild adventure scores reproduce), but 125 places (8%) still carry the old canopy term and 89 (6%) are unexplained. Those 214 should be cleaned up first, offline for the 125.

## Can it be done without new data?

Parks and playgrounds: yes. The expected value is per km2, so the stored counts, taken at each place's own radius, can be rescored without querying again. Trails: the 15 km window is already the same for everyone, so yes once the flag is dropped. Facilities: not unless the count is stored (it is not). So most of the change can be an offline recompute, with a rescore only for facilities and for any place whose data was flagged as a failed read.

## Validation before anything ships

1. An external check of the fitted park baseline (candidates to evaluate, not yet verified: a national park-access dataset such as the Trust for Public Land's ParkServe, or USGS PAD-US, which is already a carry-over item).
2. A reviewed sample of about 40 places across metros, scored under the old and new rules, with the reviewer asked which ordering matches the real world.
3. Compare the new scores with commute behavior or other independent signals where they exist.

## Rollout

1. Clean up the 214 stale or unexplained wild adventure scores (offline).
2. Fit the density baseline and write the recomputed scores to a side file (no catalog change). Show the diff for owner review.
3. Change the pillar on a branch, with tests, keeping the area type as an input only for display.
4. Apply to the catalog, then push, after sign-off.

## Open questions for the owner

1. Trails: an absolute scale ("everyone should have this much trail access") or a metro-level expectation ("relative to what is nearby")?
2. Is recentering all active outdoors scores acceptable (mean -0.8, 10th to 90th percentile -13.7 to +8.5 from parks alone)?
3. Which external dataset should check the park baseline?
4. Keep or drop the water multipliers?
5. Should the same approach be piloted next for transit and healthcare, which also have radii and expectations tied to the type?

## Risks

- The baseline is a median of this catalog (neighborhoods and close-in suburbs), fitted to the places it scores, so it needs the external check above.
- Few places sit below 3 activity units per acre, so the low end of the curve is the least certain.
- Counts come from OSM and Google Places and vary in completeness by region.
- The rule for what counts as a park is unchanged, so errors in park tagging carry through.

---

# Owner decisions and recommendations (added 2026-10-27)

1. Trails, absolute versus metro-level. Owner asked for help. Recommendation: an ABSOLUTE scale, with a cap. Reasons: 44% of the variation in trail counts is between metros (medians within 15 km range from 34 in Orlando to 657 in Boston), so a metro-level expectation would give Orlando and Boston places the same credit and hide real differences in access; HomeFit compares places across the country, so the scale should be shared. Boston's 657 is mostly OSM mapping practice (many separately mapped route relations), not 20 times the hiking; a saturating curve with a cap limits that artifact because anything above the target counts as full credit. Proposed target from the catalog's distribution, not from the type table: about 56 trails within 15 km (median; 25th percentile 30, 75th percentile 116) and about 8 within 5 km (median; 25th percentile 3, 75th percentile 15). Still to decide: whether the target is the median or the 75th percentile (a higher target gives fewer places full credit).
2. Recentering all scores: approved by the owner, on the condition that the result is directionally correct for an empirical model that matches the real world. The validation plan below is the condition.
3. External check of the park baseline: approved in principle. Candidates found: the Trust for Public Land's ParkServe (park polygons, 10-minute walk service areas, trails and playgrounds in parks; downloads as a shapefile or geodatabase; license terms not confirmed, some layers noted as needing an Esri license) and USGS PAD-US 4.x (free; local park coverage reported at roughly 50% to 60% complete, so better for large protected lands than for neighborhood parks). Plan: ParkServe for the park density check in cities, PAD-US for the trail and large-land check. Needs: read the terms, then ask the owner before downloading, with file names and sizes.
4. Water multipliers. Owner asked for help. Recommendation: DROP them. They carry no source in the code, they are the only type dependence in the term, and removing them raises the waterfront score for places with a water feature by a mean of +0.30 points (median 0, maximum +2.0; 1% of places change by more than 1 point).
5. Transit and healthcare pilots: approved. First look (stored counts by activity per acre, offline):
   - Transit: bus routes within the pillar's radius rise smoothly with density (median 0, 2, 4, 8, 13, 23, 58 across the activity bands; heavy-rail routes 0 until 25 per acre, then 1, 2, 16), against table values of 35 (urban residential), 13 (suburban) and 2 (exurban). The urban residential bar of 35 sits above the catalog median until well past 45 per acre. The radius also changes with the type (3,000, 1,500 and 2,000 m), so counts are not comparable across types. A per-km2 baseline is a natural fit, with a caution that route counts do not scale with area.
   - Healthcare: counts within the pillar's radius rise with density (hospitals 3 to 47, urgent care 3 to 67), but the score saturates: the median is 100 from 25 per acre up and 90% of urban residential places score 95 or more, so the pillar separates only low-density places. The expected values are named for fixed windows (10 km, 5 km, 2 km) while the counts are taken within the type's radius (5 to 20 km), so the comparison mixes windows. The density term in the code (`pop_density / 10000`) also makes the score depend on tract density directly. Next: read the scoring in detail before piloting.

---

# External check of the park measure: NYC, Chicago, Los Angeles (added 2026-10-27)

Status: check, offline, report only. Files downloaded with the owner's approval into the session scratch area (not the repo): NYC Parks Properties `enfh-gkve` (7.96 MB, 2,061 polygons; license field empty on the portal, NYC Open Data general terms apply, to be confirmed), Chicago Park District `ejsh-fztr` (2.80 MB, 617 polygons; public domain), City of Los Angeles Recreation and Parks `4jt3-efvk` (4.28 MB, 566 polygons; CC0). The LA file is labeled GeoJSON but its coordinates are California State Plane feet (EPSG:2229); it had to be reprojected.

## Method
For the 197 catalog places that lie inside each city (point in the Census place outline: New York city, Chicago city, Los Angeles city), count the city's park polygons whose centroid lies within the radius the pillar used for that place, and sum the parkland area inside the circle; compare with the stored OSM count and area.

## Result: the stored OSM park measures track formal park data weakly
| City | Places | OSM parks per km2 (median) | City parks per km2 (median) | Rank correlation, OSM count vs city count |
|---|---|---|---|---|
| New York | 95 | 18.8 | 3.8 | 0.27 |
| Chicago | 46 | 7.4 | 1.6 | 0.50 |
| Los Angeles | 56 | 9.3 | 0.6 | -0.15 |

- Stored OSM counts are about 5 times the city's counts in New York and Chicago and about 15 times in Los Angeles. Across all 197 places the rank correlation between the two counts is 0.20.
- By density: parks per km2 (OSM / city) at 15 to 25 activity units per acre 5.9 / 0.6; 25 to 45: 12.4 / 1.1; 45 to 100: 9.9 / 1.9; 100 and up: 20.1 / 4.5.
- The city counts rise with density (rank correlation 0.55 with activity per acre); the OSM counts rise much less cleanly (0.25).
- Parkland area: the stored OSM area and the city area inside the same circle correlate 0.29 overall (Chicago 0.74, New York 0.16, Los Angeles 0.17). OSM count versus city area: 0.01.

## What it does and does not show
- The city files hold formal public parks only. OSM also tags gardens, pitches, small playgrounds, school grounds and plazas, so a higher OSM count is expected. The cities' definitions differ (NYC includes triangles, malls and strips; the LA file includes school joint-use areas).
- It does show that the stored count is a measure of how finely OSM is mapped as much as of park access. A baseline fitted to it would encode the mapping style. Today's table value for urban residential (28.65 parks per km2) sits near the OSM level, not the city level.
- Only the dense end was tested (15 activity units per acre and up, three cities).

## Change to the redesign
Add a step before fitting any baseline: choose and validate the park measure. Candidates to test: a count of parks above a minimum size (the pillar already uses 0.5 ha for the nearest-park term), parkland area within the radius clipped to the circle, or share of the circle in park. Validate each against the city polygons (and ParkServe if the owner accepts its terms), then fit the density baseline on the validated measure.

---

# Park measure test and a correction (added 2026-10-27)

Status: offline analysis plus one bounded query run (197 places, private Overpass server, approved by the owner). Report only.

## What was run
For the 197 catalog places inside New York, Chicago and Los Angeles, the pillar's own park query (`osm_api.query_green_spaces`, same radius the pillar used) was run again on the private Overpass server. All 197 returned `overpass_ok`. Candidate park measures were computed from the fresh result and compared with the cities' own park polygons (park count and clipped parkland area inside the same circle) and with density.

## Correction to the earlier city check
The earlier section ("External check of the park measure") concluded that the stored OSM park counts are 5 to 15 times the city counts and weakly related to them (rank correlation 0.20). That conclusion was largely an artifact of stale stored counts, not of OSM. Comparing stored and fresh counts for the same places and radii:
- In 122 of 197 places the stored count is within 10% of the fresh count.
- The 75 places that differ are all in New York (30) and Los Angeles (45), and in 72 of them the stored count is larger, by up to 172 times (Borough Park: stored 345, fresh 2; Mar Vista 259 vs 3; Flatlands 318 vs 8). Chicago matches in all 46 places.
- The NYC and LA catalog files were scored at an earlier time, with an earlier version of the park query and its filtering (the current query reduces, for example, 2,526 raw elements to 127 parks). Their stored park counts, and the daily outdoors scores built on them, are on a different and inflated measure.

## Candidate measures, fresh counts (rank correlation, 197 places)
| Measure | With the city's park count | With the city's parkland area | With density |
|---|---|---|---|
| All parks (the current measure) | 0.71 | 0.30 | 0.62 |
| Parks of 0.1 ha or more | 0.70 | 0.35 | 0.56 |
| Parks of 0.25 ha or more | 0.68 | 0.39 | 0.53 |
| Parks of 0.5 ha or more | 0.67 | 0.42 | 0.48 |
| Parks of 1 ha or more | 0.57 | 0.49 | 0.34 |
| Total area, each park capped at 10 ha | 0.57 | 0.59 | 0.34 |
| Total area, uncapped | 0.38 | 0.71 | 0.20 |
| The city's own count (reference) | | 0.32 | 0.55 |

Fresh OSM parks per km2 (median 6.2) are about 4 times the cities' (1.6); the cities list formal public parks only.

## Conclusion
- Keep the current measure, the park count. With current data it tracks the cities' park counts (0.71) and density (0.62) well; a minimum size does not improve the match to counts, and area measures track area but not counts or density. Area stays out of the count term, as the pillar intends.
- The thing to fix is the data, not the measure: the stored catalog counts are on mixed versions of the query (NYC and LA inflated). A baseline must be fitted on counts from one version of the query.
- The private server covers 11 of the 18 catalog states (NY NJ CT CA WA TX IL IN PA DE MD). A refresh of every place in those states at its own radius is about 1 second per place with 4 workers (the 197 took about 3 minutes). Places in the other 7 states (AZ CO FL GA MA NC NV) cannot be refreshed until the server is extended; their stored counts match the current query where tested but only NYC, Chicago and LA were tested here.

## Revised next step for the parks term
1. Refresh the park query for the catalog places in the covered states (private server, no cost beyond the server), store the fresh list sizes next to the existing fields.
2. Fit the density baseline (median parks per km2 by activity per acre) on the fresh counts.
3. Recompute the daily outdoors park and playground terms offline and show the diff for sign-off.

---

# Refresh and fit results for the parks term (added 2026-10-27)

Status: offline analysis on fresh data, report only. Park query run for 931 catalog places in the 11 states the private server covers (NY NJ CT CA WA TX IL IN PA DE MD), one query per place at 2,000 m on the private Overpass server (929 distinct place names; 2 duplicate names merged), all `overpass_ok`, median 2.0 seconds per query. Counts at 800, 1,000, 1,500 and 2,000 m were derived from each park's distance. Raw results are in the scratch area, not the repo.

## Fitted baseline (fresh counts)
Median parks per km2 (count within 1,000 m divided by pi), made monotone over people plus jobs per acre. As a count within 1,000 m: 2.0 at 2 per acre, 5.0 at 5, 7.0 at 10, 8.0 at 15, 11.0 at 25, 16.5 at 45, 37.2 at 100, 43.0 at 200. The fit from the earlier stale counts was slightly higher (16.4 at 25 and 27.3 at 45 within 1,000 m), so the stale NYC and LA counts did inflate the earlier curve. The current table's values are 90 within 1,000 m for urban residential, 64 within 1,500 m for suburban and 1 within 2,000 m for exurban.

## Cliffs and shape of the park and playground terms (0 to 27 points), 931 places
Median term by people plus jobs per acre, new types with their table versus the continuous baseline:

| Activity per acre | Places | Type table | Continuous |
|---|---|---|---|
| 0 to 5 | 115 | 26.3 | 15.4 |
| 5 to 10 | 154 | 12.2 | 17.0 |
| 10 to 15 | 154 | 9.1 | 16.5 |
| 15 to 25 | 180 | 7.3 | 16.9 |
| 25 to 45 | 140 | 6.6 | 16.7 |
| 45 to 100 | 103 | 7.1 | 16.9 |
| 100 and up | 85 | 12.7 | 18.5 |

The type table makes the term U-shaped: the sparsest places score highest (the exurban bar is one park) and typical suburban and urban places score about 7 of 27, because their bars (64 and 90 parks) are several times what the catalog medians show. The continuous baseline is flat at about 17 of 27 by construction, because each place is judged against places of the same density.

Cliffs, mean gap between places of nearly equal density (within 10%) in different types: exurban versus suburban +20.3 points under the type table and +3.7 under the continuous baseline; suburban versus urban residential +5.0 and -1.4.

For the 288 places whose type changes, moving from the old type's table to the new type's table changes the park terms by a mean of -8.2 points (92% move by more than 3). Against the old-type table, the continuous baseline changes them by a mean of -0.6 (mean absolute 7.0), but that is because it re-levels everyone, not only the places that changed type.

## A design choice this exposes
A baseline set to the peer median is a RELATIVE measure: a dense neighborhood with 10 parks nearby scores below average and an exurban place with 2 scores about average, so the term no longer rewards density or sparseness; it rewards being better supplied than similar places. This matches the stated principle (area-type adaptation drives expectations) and removes the cliffs, but an ABSOLUTE target for all places (as the amenities pillar now uses) would keep the term rising with the count. Decision for the owner, the same question as for trails.

## Not covered
The 7 catalog states outside the private server (AZ CO FL GA MA NC NV, about 545 places) could not be refreshed. Their stored counts agree with the current query in the places tested (Chicago) but were not checked here.

---

# Parks term conversion proposal, relative to density peers (added 2026-10-28)

Status: PROPOSAL FOR SIGN-OFF. Owner chose "relative to peers" for the parks term on 2026-10-28. Nothing is changed in code or the catalog. Numbers are offline, from the fresh counts of 931 places in the 11 covered states.

## What would change
Only the park count term of Daily Urban Outdoors (0 to 22 points). Today it is `22 * (1 - exp(-parks / expected))`, with expected set by the type table (90 within 1,000 m, 64 within 1,500 m, 1 within 2,000 m). The proposal keeps the same curve and replaces the table lookup with a baseline that is a function of people plus jobs per acre around the pin (the place context's activity_per_acre), counted within one fixed radius of 1,000 m for every place. The radius no longer depends on the type, so a place's count and its baseline are always on the same footing. The nearest-park, playground and facilities terms stay as they are; the playground term (0 to 5) needs the same treatment with its own fit and is a follow-up, not part of this sign-off.

## The baseline
Median count of parks within 1,000 m by activity per acre, monotone, interpolated in log-log: 2.0 at 2, 5.0 at 5, 7.0 at 10, 8.0 at 15, 11.0 at 25, 16.5 at 45, 37.2 at 100, 43.0 at 200. Below 2 per acre the value is held at 2.0, above 200 at 43.0. It is stored as a small data file with its build script (the way the other baselines are), not typed into code, and the build script is the only place the numbers come from.

## Evidence
- Source: OpenStreetMap park query as the pillar runs it, one version of the query for all 931 places, so the old NYC and LA inflation is gone.
- Stability: split the places at random into two halves; the band medians agree closely (for example 0 to 3 per acre 1 and 1.5; 25 to 45 13 and 13; 100 and up 46 and 52). Band sizes run from 61 to 180 places.
- A place at its baseline scores 13.9 of 22 (22 times 1 minus 1/e). Half the places sit above their baseline (49%), by construction.
- Status under the design rules: this is a measured peer median, not a published standard. It is "relative to what this catalog's similar places have", so it carries two limits. It is only as national as the catalog (neighborhoods and close-in suburbs; 61 places below 3 per acre), and it is circular in the sense that the places it scores define it. The external check against city open data (NYC, Chicago, LA) supports the count as a measure (rank correlation 0.71) but does not validate the level. I would mark the level as an empirical peer median in the code and docs, not as a research standard.

## Effect on scores (park count term, 0 to 22)
| | Type table | Density baseline |
|---|---|---|
| Mean | 8.9 | 13.1 |
| Standard deviation | 7.5 | 5.8 |
| 10th / median / 90th percentile | 1.4 / 6.1 / 22.0 | 4.8 / 13.9 / 20.4 |

By activity per acre, mean term under the table versus the baseline: 0 to 3: 17.5 vs 10.3; 3 to 6: 20.5 vs 12.0; 6 to 10: 10.9 vs 13.8; 10 to 15: 7.6 vs 13.1; 15 to 100: about 5 vs 13; 100 and up: 10.2 vs 15.4. Sparse places lose points (they were scoring on a bar of one park), mid and dense places gain. The spread is narrower, so the term separates places less than before; that is the cost of judging each place against its peers.

## Decisions and risks for sign-off
1. The term becomes relative. A dense place with 10 parks nearby scores below average and an exurban place with 2 scores about average. Dense places lose the reward for density; this is the intended trade of the peers choice.
2. Recentering. Sparse places move down by 7 to 8 points on a 22-point term, dense places up. Whole-pillar change is smaller (the term is 22 of 100) but the active outdoors rank order shifts; I have not recomputed the whole pillar and total rank correlation with the stored scores.
3. Coverage. The baseline was fit on 11 states. The other 7 (AZ CO FL GA MA NC NV, about 545 places) would use the same function without a local check of their counts; the stored counts there are on the current query version where tested, but only partly tested.
4. Counts must be on the same radius and query version everywhere. The catalog needs the 1,000 m count for every place. For the 11 covered states the fresh queries already hold it; for the other 7 it comes from the stored park lists if they contain distances out to 1,000 m (to be verified before any step), otherwise a rescore on the public server.
5. Live scoring: the live pillar must read the context's activity_per_acre. That needs the area-type branch (5 commits ahead, not pushed) and its cache version bump to ship first or together.

## Proposed steps if approved
1. Write the baseline build script and data file under the baselines folder, with the fit points above and the split-half check.
2. Add the term behind the context's activity_per_acre, keeping the old table as fallback only when the factor is missing, with tests (monotone, reproduces the fitted points, the median place scores 13.9).
3. Offline recompute of the park term for the 11 covered states from the stored fresh counts, and a diff file for review before anything is written to a catalog file.
4. Then the playground term, then trails (absolute scale, separate sign-off).
No rescore, no push, no catalog change before your approval of each step.

## Step 1 result and correction (2026-10-28)
Build script and data file written and committed locally on branch area-type-circle-density (9e3487f, not pushed). The script is the single source of the numbers. It uses a rolling median of 100 places per knot and a running maximum for monotonicity, and it records a split-half check in the data file. It does not reproduce the earlier ad hoc fit exactly, so the script's values replace the ones quoted above: parks within 1,000 m at 2, 5, 10, 15, 25, 45, 100, 200 activity per acre are 2.0, 5.0, 7.0, 8.5, 9.0, 16.5, 37.0, 47.5 (earlier: 2.0, 5.0, 7.0, 8.0, 11.0, 16.5, 37.2, 43.0). Park term on the 931 places with these values: mean 13.3, standard deviation 5.8, 10th/median/90th percentile 4.8 / 14.0 / 20.4 (earlier 13.1, 5.8, 4.8 / 13.9 / 20.4), so the conclusions are unchanged. Split halves agree except at the 25 per acre knot (12.5 versus 9.0) and the densest knot (45.5 versus 50.0), the least stable parts of the fit.

## Decayed count adopted (2026-10-28)
Owner approved the distance-decayed count. Each park within 2,000 m counts exp(-0.0012 x metres), the decay the pillar already uses for its nearest-park term. Baseline refit on the weighted counts: 2.0, 4.3, 7.1, 8.1, 8.9, 18.1, 34.1, 44.4 at 2, 5, 10, 15, 25, 45, 100, 200 per acre. Offline diff versus stored: pillar score mean -0.9, 14% of places move more than 10 points, rank correlation 0.875 (file analysis/active_outdoors_parks_term_recompute_decay_2026-10-28.csv). Committed locally on area-type-circle-density, not pushed. Live: when the density factor is available the pillar reads parks out to 2,000 m for this term only; the nearest-park, playground and facilities terms still see the type's own radius. Still open: the playground term, trails, the 7 states outside the private server, and a catalog write.

## Playground term adopted (2026-10-28)
Owner approved. Same method as parks: distance-weighted count within 2,000 m against a density-peer baseline, stored in the same data file (expected_playgrounds: 0.6, 1.2, 2.2, 2.7, 3.1, 4.7, 7.3, 8.9 at 2 to 200 per acre; the pillar floors the expected value at 1). Offline effect on the pillar score: mean -0.7, at most 3.8, 11% of places move more than 2 points (analysis/active_outdoors_playground_term_pilot_2026-10-28.csv). Committed locally, not pushed. Still on type tables: nearest-park proximity is already continuous; facilities (3 points) and trails (50 points).

---

# Trails term proposal, absolute scale (added 2026-10-28)

Status: PROPOSAL FOR SIGN-OFF. Offline only, from stored catalog fields (1,476 places with a clean trail read, all 21 metros including the 7 states the private server does not cover). Nothing changed in code or the catalog.

## What changes
Wild adventure (0 to 50) today: trail count within 15 km and within 5 km, each `max * (1 - exp(-count / expected))`, plus camping. The expected values, maximum points, the 2.6 times fragmentation discount (urban residential only) and the camping distance limits all depend on the area type, and a mountain-town flag switches most places to a second branch (77% of the catalog). Proposed: one scale for every place, no type, no flag, no discount.
- Trails within 15 km: 25 points, expected 56.5 (the catalog median).
- Trails within 5 km: 15 points, expected 8 (the catalog median).
- Camping: 10 points, full inside 25 km, decaying beyond as today's exurban branch does (0.00005 per metre).
The three budgets add to 50, so the old clip at 50 goes away (28% of stored wild scores sit at exactly 50 today).

## Evidence status
- The two expected values are medians of this catalog, so the scale is "relative to the places we score", not a published standard. The budgets (25, 15, 10), the camping limit and the decay are not sourced; they should be marked TODO in code, as the existing ones should have been.
- Trail access depends on regional geography, not local density (earlier finding), which is why density peers were rejected for this term.

## Effect (offline, all 1,476 places)
| | Stored | Proposed |
|---|---|---|
| Wild adventure mean | 38.6 | 32.2 |
| Standard deviation | 11.6 | 11.1 |
| At the 50 cap | 28% | 0% (17% at 45 or more) |
| Rank correlation with stored | | 0.690 |

Pillar score (0 to 100): mean change -5.8, 10th/90th percentile -20.5 / +2.7, 38% of places move more than 5 points. This is a large recalibration, larger than the parks and playground changes combined.

By stored type, mean wild score stored versus proposed: urban residential 39.4 vs 30.7, suburban 33.3 vs 33.8, exurban 47.4 vs 32.3, rural 42.9 vs 25.4. The drop is concentrated in exurban and rural places, which today are held to a bar of one trail. The largest drops (about -28 wild points, about -25 on the pillar) are places with 4 to 5 trails within 15 km and none within 5 km (Winters CA, Moapa Town NV, Spring Branch TX, Esparto CA, Anna TX). The largest gains are only about +6 (places with 32 to 39 trails, 6 to 11 within 5 km).

Metro means, stored versus proposed: Seattle 50 to 45, Boston 49 to 48, Denver 45 to 41, NYC 43 to 36, Philadelphia 43 to 40, LA 33 to 31, Miami 25 to 25, Houston 31 to 20, Atlanta 41 to 27, Charlotte 38 to 24, Raleigh 45 to 33. The order (mountain and northeastern metros high, Gulf and Florida low) matches what one would expect; Houston, Atlanta and Charlotte fall most.

Sensitivity to the expected values: halving both gives a wild mean of 38.6 (same as stored, standard deviation 10.1); doubling gives 25.2. The level is a choice; the shape is not.

## Decisions for sign-off
1. Single absolute scale at the catalog medians (above), or lower targets (half the medians reproduces today's average level and softens the drop for sparse places).
2. Drop the fragmentation discount for dense places. It rests on 8 NYC neighborhoods; dense places have few trails within 15 km anyway (median 30 at 45+ per acre), but OSM fragmentation in NYC and LA could inflate counts. I would drop it and check NYC and LA after.
3. Drop the mountain-town flag and the exurban override for dense places (the flag is unsourced beyond three example cities).
4. The 125 stale wild scores (old canopy term) and 89 unexplained ones are cleaned up by this recompute anyway.
5. Trail counts in NYC and LA may be stale like the park counts were; a fresh trail read for the 11 covered states would check that before any write.

File: analysis/active_outdoors_trails_absolute_pilot_2026-10-28.csv (place, stored and proposed wild score, pillar change).

## Trails scale adopted at catalog medians (2026-10-28)
Owner approved the catalog medians (56.5 trails within 15 km, 8 within 5 km). Built locally, not pushed: data/active_outdoors_trails_scale.json from scripts/baselines/build_active_outdoors_trails_scale.py, used by the wild adventure term for every place. Side effects to know: (1) the mountain-town rule no longer affects scoring, so the vacation "mountain trip" override has no effect on the trail terms; (2) the exurban override for dense mountain-flag places is gone, so those places keep the shared area type for the water multipliers and the park fallback; (3) the urban-path trail filter now always runs for dense types (before, mountain-flag places skipped it); (4) dense and suburban places only read camping out to 15 km (regional radius) while exurban and rural read to 25 km, so the 25 km camping limit is only reachable for the latter. Open: trail counts for NYC and LA may be stale; the facilities term; the 7 uncovered states; the catalog write.

---

# Catalog write plan (proposal only, 2026-10-28)

Status: nothing in the catalog has been changed. No live calls are needed for any step below.

## What each new term needs, and whether the catalog holds it
| Term | Needs | Stored in catalog? | Fresh data on hand |
|---|---|---|---|
| Parks (22) | decayed count: park distances | No, only the count | Yes, 929 places |
| Playgrounds (5) | decayed count: playground distances | No, only the count | Yes, 929 places |
| Trails wild score (50 pts scale) | trail counts at 15 km and 5 km, nearest camping distance | Yes | Not needed |
| Facilities (3) | facility count | No | No (left on type table, to-do) |

The catalog has 1,476 places, so 547 places (the 7 states AZ CO FL GA MA NC NV, plus a few strays) have no distances and cannot get the new park or playground terms offline.

## Proposed write, in two stages
1. Trails for all 1,476 places, from stored trail counts and camping distance. This also removes the stale canopy term from the 125 places that still carry it.
2. Parks and playgrounds for the 929 covered places, using the stored daily score minus the old park and playground terms plus the new ones (the method used in the pilots). The 547 uncovered places keep their old park and playground terms for now.

Then recompute the pillar score (points x 100/110), the composites and the happiness index for every changed place, run the health check on all metro files, and write the result to new files before replacing anything.

## Known side effects to accept or reject
- The two stages leave the catalog in a mixed state: 547 places on old park terms, 929 on new. Rank comparisons across the two groups are slightly inconsistent until the uncovered states are filled.
- Trails: exurban and rural places drop most (wild mean 38.6 to 32.2, rank correlation 0.69 with stored).
- The area-type branch and the cache schema bump to 3 must ship together with these scores.
- The facilities term stays on the type table with its TODO.

## Decisions needed
1. Accept the mixed state for the 547 uncovered places, or hold the park and playground write until they are covered.
2. Approve the trails write for all places.
3. Approve pushing the branch (about 10 local commits) with the cache schema bump.
