# Active outdoors: Level 2 verification brief (DRAFT, 2026-11-02)

For an agent that did not build or convert the pillar. Pass criteria below are fixed before any result is seen. They are the
builder's proposal, with no external source (marked TODO); the owner approves or edits them before the run, and no criterion
may be changed after results are read. A change to a criterion after the run voids the check.

Scope: `pillars/active_outdoors.py` as on origin/main 3841a87 and the catalog files `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl`
(1,476 places). Read only those files. Do not change scoring, code or any catalog file. Write results to
`docs/ACTIVE_OUTDOORS_LEVEL2_RESULTS.md` and a CSV per check in `analysis/`.

## Owner decisions (2026-11-02)

Criteria approved as written: pin-shift median at most 3 and 95th percentile at most 10 at 500 m (5 / 15 at 1 km); city polygon
Spearman at least 0.6 on the total and 0.3 on the daily part. Thresholds are still unsourced (the owner accepted the builder's
choice); they are now fixed. Permissions given: download city park polygons and PAD-US (public data, each in its own empty
folder, file names and sizes stated first); live Overpass reads on the owner's Hetzner server only, about 80 places, no paid
Google calls. Other thresholds in this brief stand as written.

## Rules

- Say what data a step needs before any live call, Overpass read or download, and ask the owner. Do not open the Overpass tunnel
  or call live APIs unless the owner says yes for that step. Checks 1 and 5 need this; checks 2, 3 and 4a/4b use stored files
  except the downloads in check 4.
- Downloads: owner permission first, with file names and sizes; each into its own new empty folder; run Python with `-I`;
  scripts live elsewhere and receive paths as arguments.
- No em dashes. Distances in miles in the write-up. Report every result, pass or fail, with n. Unsourced numbers stay TODO.
- A skipped check is reported as "not run" with the reason; never as a pass.

## Check 1: pin-shift sensitivity (needs fresh reads; ask first)

Sample: 60 places, 15 per stored area type (urban residential, suburban, exurban, rural), drawn with a fixed seed written in the
results, among places in states the private Overpass server covers. Shift each pin 500 m and 1,000 m (0.3 and 0.6 miles) north,
east, south and west (480 reads). Score each shifted pin with the pillar code as it is.

Pass (all must hold): at 500 m, median change at most 3 points and 95th percentile at most 10; at 1,000 m, median at most
5 and 95th percentile at most 15. TODO: thresholds have no source; healthcare's result (0.9 / 5.5 and 1.9 / 11.4) is context only.
Also report the share of shifted reads that change by more than 10, the largest change with its place, and any read that
returns empty where the unshifted read did not (a failed read recorded as zero, as in the healthcare Spring Branch case).
An all-empty shifted read counts as a failure of the read, not of the pillar; list it separately and rerun it once.

## Check 2: all-places check (stored data only)

Caveat: the builder had already seen the all-places numbers when these criteria were written, so check 2 is not blind. The
owner should set the thresholds for (a) and (b) independently (TODO: unsourced) or accept that this check is descriptive only.

Over all 1,476 places report: mean, median, 10th and 90th percentile, per component (daily, wild, water) and total; by stored
area type and by density band (0-5, 5-10, 10-25, 25-100, 100+ people plus jobs per acre); share at or within 0.5 of each
component cap and share at or below 1 point. Report places with 0 daily and their read outcome.

Pass: (a) share of places with total score at or above 99.5 is at most 2 percent and at or below 10 is at most 2 percent;
(b) no component sits at its cap for more than 15 percent of places; (c) every place with an Overpass park read of `overpass_empty` has the daily
term left out or the pillar flagged degraded, otherwise FAIL (principle 9). The builder expects (c) to fail for 4 places.
Also report, but not as pass/fail: how many places change by more than 5 points if the area-type label is swapped (not required;
skip if it needs a code run).

## Check 3: launch pairs (stored data only)

Pairs fixed here, chosen from general knowledge of the places, before the agent reads their scores. Use the stored total score.
Names must match `catalog.name`; if a name is ambiguous, use the place in the metro stated.

Should differ (first place scores at least 10 points higher than second):
1. Mill Valley CA (SF metro) over Katy TX (Houston metro): mountain trails and bay versus flat inland suburb.
2. Santa Monica CA (LA metro) over Sugar Land TX (Houston metro): beach and mountains versus inland suburb.
3. Lincoln Park IL (Chicago metro) over Katy TX: lakefront and large park versus inland suburb.

Should be similar (within 8 points):
4. Park Slope NY and Brooklyn Heights NY (adjacent, both with a large park or waterfront).
5. Winnetka IL and Evanston IL (adjacent lakeshore suburbs).

Pass: all five behave as stated. One miss is a FAIL of the check; list each pair's two scores and the component that decides it.
TODO: the 10 and 8 point thresholds are builder's choice.

Cross-type test (checks that the area-type label no longer drives the score, principle 14): within each metro, pair places whose
people plus jobs per acre differ by at most 10 percent but whose stored area types differ. Report the number of pairs, median
absolute total difference and share above 10 points. Pass: median at most 5 and share above 10 points at most 20 percent.
TODO: thresholds unsourced.

## Check 4: independent validation (downloads need owner permission)

Criteria fixed now; none is a validation of the level of any baseline, only of ordering.

4a. Parks against city polygons: NYC Parks Properties `enfh-gkve`, Chicago Park District `ejsh-fztr`, City of Los Angeles
Recreation and Parks `4jt3-efvk` (the three files used on 2026-10-27; the owner approved that download, ask again before
re-downloading; the LA file is in California State Plane feet, EPSG:2229, and must be reprojected). For the 197 catalog places
inside the three cities, count city park polygons whose centroid lies within 2,000 m (1.2 miles), distance-weighted with
exp(-0.0012 x metres), and compare with the catalog's park and playground evidence: the weighted OSM park count from
`analysis/ao_fresh_parks_uncovered/` (stored, no new read) and the stored daily score.
Pass: Spearman between the weighted OSM count and the weighted city count at least 0.6 overall and positive in each city
(the 2026-10-27 result was 0.71 on unweighted counts at the pillar's radius); Spearman between stored daily score and the
weighted city count at least 0.3. TODO: both thresholds are builder's choice. If the owner prefers ParkServe (Trust for Public
Land), read its license terms first and report them; do not download before the owner agrees.

4b. Trails against USGS PAD-US 4.x (free; local park coverage is reported at about 50 to 60 percent, so it is a check of large
protected land, not neighborhood parks). Download only with permission. For all 1,476 places compute protected land area
(any public access category) within 15 km (9.3 miles). Pass: Spearman between stored trail count within 15 km and that area at
least 0.4, and between stored wild adventure score and that area at least 0.4. TODO: thresholds are the builder's choice, and
Boston's trail counts are inflated by route-relation mapping, so also report the result without the Boston metro.

4c. Water, report only, no pass criterion: compare the stored best water feature type with a coastline or lake layer if the
owner provides one. Not run unless asked.

## Check 5: live scorer against the catalog (needs live calls; ask first)

For 20 places chosen with a fixed seed across area types, run the live pillar and compare the daily, wild and water components
with the stored catalog values. Pass: median absolute difference at most 2 points per component and no place differing by more
than 10 points in total. TODO: thresholds unsourced. Explain any difference that rests on data age, not code.

## What the builder already knows (do not rely on it)

The builder's all-places run (2026-11-02, in `docs/PILLAR_ACTIVE_OUTDOORS.md`) found 0 places at 99.5 or above, 0 at 10 or below,
and 4 empty park reads scored as zero. The builder did not run checks 1, 3, 4 or 5.

## Report format

For each check: what was run, n, the numbers, pass or fail against the criteria above, and anything surprising. End with a
proposed Level (1, 2) for the owner and a list of unsourced parameters still open. Do not recommend scoring changes; list findings.

## Revision 2026-11-04 (owner ruling, made after rerun 3 results were read; not blind)
Replaces check 3 pair 5 and the cross-type test. Both old criteria stay on record as failed in rerun 3 (pair 5: 84.9 vs 70.9; cross-type: median 7.8, 40.0% above 10). The pass wording for the pillar is "Level 2 against criteria revised after the first run": the revision came after the results were seen, so it is not a blind pass. Thresholds below were fixed before any new number was computed, and are unsourced (TODO).
- Check 3 pair 5 is retired (a hand-picked pair from general knowledge; the data shows the two towns differ). Check 3 pairs 1 to 4 stand as written.
- New check 3b, neighbours: for every pair of catalog places in the same metro whose pins are within 3 miles of each other, the absolute difference in total score. Pass: median at most 8 points. Report n, median, 90th percentile and the 10 largest pairs. TODO: the 8 is the old "similar" threshold, unsourced.
- New check 3c, label effect: among pairs in the same metro whose people plus jobs per acre differ by at most 10 percent, the median absolute total difference for pairs of different stored area type minus the median for pairs of the same stored area type. Pass: at most 2 points. Report n for both groups. TODO: the 2 is unsourced.
Both use stored data only (no live calls, no downloads, no code or catalog change). A verifier who did not build the pillar runs them.
