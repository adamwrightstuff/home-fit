# Regional bias audit: written questions and pass rules (fixed 2026-11-08, before any outside-measure result was read)

Scope: measurement only, no scoring change. Region A = NYC, Boston, Philadelphia, Chicago (469 places). Region B = the other 17 metros (1,007 places). Catalog: data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl at origin/main 8c7d7bb8. Default equal weights, 12 pillars.

## Question (same for every pillar)
Does the regional gap in our pillar score match the regional gap in an independent outside measure of the same thing, after standardizing both?

## Standardization
Both measures are converted to ranks over the 1,476 places, then to z-scores (rank-normal). Gap in SD = mean z in A minus mean z in B. Using ranks removes unit and scale differences and curve shape; it cannot tell us whether our curve is steeper than the world, only whether the ordering by region agrees.

## Pass rules (all numbers are judgments, not sourced; set before results, owner may change them before the run)
R1. Pooled Spearman between our pillar and the outside measure is at least 0.50.
R2. Mean within-metro Spearman (metros with 20 or more places) is at least 0.40.
R3. Overstatement: our gap in SD minus the outside gap in SD is at most 0.25 SD. (We fail only for overstating the regional gap; understating is reported but not a failure.)
R4. Residual region effect: regress our z on the outside z plus log(people plus jobs per acre); the Region A coefficient must be at most 0.25 SD.
R5. Same-density check: repeat R3 inside each of three activity-density terciles; the overstatement must be at most 0.25 SD in at least two of three.

Verdict: REAL if R3 and R4 pass. PARTLY REAL if overstatement is above 0.25 and at most 0.50 SD, or R4 coefficient is above 0.25 and at most 0.50. ARTIFACT if either exceeds 0.50. R1, R2 and R5 qualify confidence in the verdict: an outside measure that fails R1 or R2 is too weak to judge the pillar, and the verdict is reported as UNTESTABLE with that measure.

## Artifact checks (offline, stored data only)
A1. Active outdoors park baseline: recompute the daily term with the baseline replaced by a different anchor is NOT allowed (no constants invented). Instead report, from stored breakdowns, how the expected-parks value at each place's density compares with the parks the place has, split by region, and how much of the regional gap in the daily term is already present in raw counts versus the ratio to the baseline.
A2. Area type and density: compare pillar means for A versus B within the same stored area type and within the same activity-density tercile.
A3. OSM coverage by region: compare data-source flags, degraded flags, empty-read flags and Places-fallback use by region and pillar. Which states the private Overpass server covers, and which fed the baseline fit, is read from data/overpass_states.json and the baseline file.
A4. Typed-park change: compare the pre-DPv2 file (parent of 847d1995) with the current file by active outdoors component, by region.
A5. Missingness: places with null pillar scores, by region.

## Not testable offline (said now, not after)
Whether any outside measure is a better truth than our score. A regional difference in our score that also appears in an outside measure can still be a shared artifact (for example density driving both). R4 and R5 reduce that risk but do not remove it.

## Trail check (locked 2026-11-09 before any download or result)
Sample: analysis/regional_bias_trail_sample_2026-11-09.csv, 40 places, seed 20261109, 20 in NYC/Boston/Philadelphia/Chicago metros in NY, MA, IL, PA and 20 in other metros in CO, GA, FL, NC, AZ; 7/7/6 per catalog-wide activity-density tercile in each group. NJ, CT, IN, DE, CA, TX, WA, NV and others are not in the sample (files not downloaded).
Independent source: USGS National Transportation Dataset trails layer, state GeoPackages (prd-tnm.s3.amazonaws.com/StagedProducts/Tran/GPKG/).
Measure: number of distinct named trail features in the USGS layer within 15 km of the pin (same radius as the stored count).
Caveat fixed now: the stored clean count is trail DESTINATIONS (hiking routes plus parks and protected land of at least 100 ha), not trail segments. USGS trails can only stand in for the routes part, so this tests a component. Also, USGS trail coverage depends on partner agencies by state, which can itself differ by region.
Pass rule: regress log(1+stored clean count) on log(1+USGS named trails) and Region A. Region A multiplier exp(coef) must be at most 1.5 (it was 3.64 against protected land). Also report the raw A vs B median of USGS named trails and of the stored count, with bootstrap 95% intervals (n is small). The 1.5 cutoff is a judgment, not sourced.
If USGS shows A and B differ by a similar factor to the stored count, the gap is not an OSM mapping artifact. If USGS shows no regional difference while the stored count shows 4x, OSM mapping or the destination definition is the cause (the check cannot say which).
Coverage guard: before reading the A vs B result, report USGS trail feature count per state per 1,000 km2 of land (state totals only) to see whether coverage is uneven.

## Destination split (locked 2026-11-09 before any read)
Question: of the stored trail destinations within 15 km, how much of the Northeast and Chicago excess is hiking-route relations versus named parks, reserves and protected areas of at least 100 ha?
Sample: analysis/regional_bias_destination_sample_2026-11-09.csv, 60 places (30 A, 30 B), 10 per catalog-wide activity-density tercile in each group, seed 20261109, only the 11 states on the first private Overpass server (port 12345; the second server on 12346 was unreachable, so AZ CO FL GA MA NC NV are not sampled and the other-metros group is CA, TX and WA only: no Southeast, no Mountain West). Sample re-drawn before any read for that reason. Same query and same build_trail_destinations code as the pillar (data_sources/osm_api.py), 15 km radius, no code change.
Validity gate: the re-read total must match the stored count_total within 3 for the median place and rank-correlate at 0.95 or more; if not, the split is not reported as representative.
Reading rule (judgment, unsourced): excess_A_minus_B = mean(A) minus mean(B) of each component. If routes carry at least 60% of the total excess, route mapping is the main driver; if areas carry at least 60%, parks and protected land are; otherwise mixed. Also report the same split per density tercile and the share of routes whose name is empty.
Not allowed to change: query, cutoff, word list. No scoring change is made by this step.

### Destination split extension (locked 2026-11-10 before any read; owner reopened the second Overpass server, port 12346)
Sample 2: analysis/regional_bias_destination_sample2_2026-11-10.csv, seed 20261110, states on the second server (AZ CO FL GA MA NC NV): 10 Massachusetts places from A (3/3/4 by density tercile) and 30 other-metro places from B (10 per tercile). Same query, code, validity gate and 60% reading rule. Report sample 1, sample 2 and the pooled 100 places, and the excess split with B restricted to the Southeast and Mountain West states (sample 2 B) against A.

## PAD-US destination count (locked 2026-11-10 before any download; owner approved steps 1 and 2, human check excluded)
Purpose: test the parks and protected land part (43% of the excess) against a source that is not OpenStreetMap and covers every place the same way.
Source: PAD-US 4.0 state geodatabases, ScienceBase item 652d4f80d34e44db0e2ee45c, 18 states (AZ CA CO CT DE FL GA IL IN MA MD NC NJ NV NY PA TX WA), MD5 checked against ScienceBase, each in its own folder, read with Python -I, deleted after.
Measure P: number of distinct named protected-area units (distinct Unit_Nm within a manager) with total area of at least 100 ha (same cutoff as the stored count), with public access Open or Restricted (Pub_Access OA or RA), whose polygon lies within 15 km of the pin (distance to nearest polygon edge, equal-area projection). Easement-only designations are kept if they meet the rules (flagged, sensitivity run without them).
Tests, all 1,476 places unless noted:
P1. Validity on the 100 re-read places: Spearman of P with the OSM area count (the parks and protected part only) is at least 0.5.
P2. Regional agreement on the 100 re-read places: standardized (rank-normal) gap in the OSM area count minus the gap in P is at most 0.25 SD. If larger, the parks part of the excess is not confirmed by an outside source.
P3. All 1,476: regress rank-normal stored trail-destination count on rank-normal P, log activity density and Region A; Region A coefficient at most 0.25 SD to call the total real, 0.25 to 0.50 partly real, above 0.50 artifact. Stored total mixes routes with areas, so a failure here is expected where routes drive the excess; report beside P2.
P4. Median P for A and B and the ratio, against the ratio of OSM area counts (100 places).
The 100 ha cutoff and name rule are the same as the pillar's; no constant is tuned to the result. Thresholds are judgments, set before the data was read.
Step 2 (routes, USGS in states with usable coverage) is NOT downloaded yet: it needs a re-download of NY PA MA CO FL NC (1.86 GB), to be requested separately.

## Routes check against USGS trails (locked 2026-11-10 before download or read; owner approved)
Sample: analysis/regional_bias_routes_sample_2026-11-10.csv, seed 20261111, 30 A places (NY, PA, MA) and 30 B places (CO, FL, NC), 10 per catalog-wide activity-density tercile per group. States chosen because USGS had usable coverage (several state and federal partners). Illinois, Georgia and Arizona are excluded for near-zero coverage (see the earlier trail check).
OSM side: hiking_route count within 15 km, from a fresh read on the private Overpass servers with the pillar's own query and build_trail_destinations code (routes only; areas are covered by the PAD-US step).
USGS side: distinct named trail features within 15 km (trail layer of the National Transportation Dataset, state GeoPackages NY PA MA CO FL NC, 1.86 GB, sizes checked against the bucket listing), same method as the first trail check.
Tests: R-1 Spearman of OSM route count with USGS named trails at least 0.40 (named segments are a rough stand-in for routes). R-2 standardized (rank-normal) gap, A minus B: OSM routes gap minus USGS gap at most 0.25 SD. R-3 region multiplier: regress log(1+OSM routes) on log(1+USGS named trails) plus Region A; multiplier at most 1.5. Also report the medians and the same by state. If R-1 fails the check is reported as untestable, not as a pass or a fail on the gap.
Not tested: whether USGS coverage itself differs by region within these six states (partners differ: NY and PA state agencies, MassGIS, Colorado Parks and Wildlife, FL DEP). Thresholds are judgments set before the data was read.

## PAD-US 5 km count (2026-11-10, owner approved re-download for the wild term proposal)
Same files, same unit rule as the 15 km count P (distinct manager plus unit name, at least 100 ha total, Open or Restricted access, easements kept with a no-easement variant), measured to 5 km of the pin. Also saves each place's unit list (name, manager, distance, designation) so places can be inspected. No scoring file is changed.

## Option C, all-places re-read (locked 2026-11-10 before any read; owner approved)
Read: pillar's own query_trail_destinations and build_trail_destinations (no code change), 15 km, all 1,476 catalog places, state routed to its private server (12345: NY NJ CT CA WA TX IL IN PA DE MD; 12346: AZ CO FL GA MA NC NV). Saved per place: every destination with type (hiking_route or trail_area), name and distance to nearest bounding box edge, written as one line per place so the run can resume. Read only, no catalog file or code is touched.
Validity gate: re-read total (routes plus areas) equals the stored count_total within 3 for at least 95% of places, and within 5 km likewise; if not, differences are listed before any other result.
Option C definition for the estimate: count only trail_area destinations in both terms (15 km and 5 km), expected values refit as the catalog medians of the new counts (same rule the pillar uses), budgets 25 and 15 unchanged, camping as stored, saturation curve unchanged.
Reported, not pass/fail: wild and active outdoors regional gap before and after; places moving more than 5 and more than 10 active outdoors points, by region and the 15 largest movers each way; Connecticut places; effect on the total score.
Checks that decide whether C is worth proposing for adoption (judgment thresholds, set now): (1) Spearman of the new 15 km area count with the PAD-US all-access count at least 0.60 across all places; (2) standardized regional gap of the new area count minus the PAD-US all-access gap at most 0.25 SD; (3) within-metro mean Spearman with PAD-US at least 0.45. These tests the parks part only; the route removal itself rests on the USGS and 100-place evidence and is not testable here.
Not decided here: any change to code or data. A proposal with these numbers comes back for approval.

## CDC PLACES physical inactivity check on active outdoors (locked 2026-11-10 before any data was read; owner approved)
Replaces the human check (owner: raters cannot know enough places) and the ParkScore fact sheets (about 10 MB each, city-wide only, TPL site blocks scripted access).
Source: CDC PLACES ZCTA data, GIS-friendly format, latest release found on data.cdc.gov via the Socrata API, only the ZCTA id, total population and the no-leisure-time-physical-activity crude prevalence (LPA) for the ZIPs of the catalog places (stored in score.location_info.zip). A few hundred KB, no bulk file.
Outcome: activity = 100 minus LPA (share of adults with any leisure-time physical activity). Model-based small-area estimates, partly built from demographics, so they track income and age and are not independent of them.
Controls from the catalog: households_150k_plus_share (income proxy, status signal) and log of activity per acre (density). Age is not controlled (no per-ZIP age on disk); this is a limit.
Tests (all places with a ZIP match, judgment thresholds):
L1. Pooled Spearman of active outdoors score with activity: report, no threshold. Same for daily, wild and water.
L2. Partial Spearman of active outdoors score with activity controlling for income share and density (rank residuals): at least 0.10 with a bootstrap 95% interval excluding 0 is "consistent with the score"; between 0 and 0.10 is weak; at or below 0 is not supported. Report the same within region A and B separately and within-metro mean.
L3. Region check: regress rank-normal active outdoors score on rank-normal activity, income share, log density and Region A. Report the Region A coefficient before and after adding activity. If activity explains none of the regional gap while the score gap stays, that is consistent with the score overstating A.
Not a validation of the score: a pass means places with higher scores have more physically active adults beyond what income and density predict. A fail is inconclusive because PLACES estimates are modeled and confounded.
