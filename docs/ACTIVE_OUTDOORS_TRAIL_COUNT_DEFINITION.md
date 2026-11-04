# Active outdoors: proposed clean trail count (DRAFT for owner approval, 2026-11-03)

Status: proposal only. No code, scoring or catalog change. Every number marked TODO has no source. Area type is not an input.

## Why
The stored trail count is a mix: hiking routes, large park-tagged features (including greenways and cycleways), and area boundaries (nature reserves, protected areas, historic districts). In 6 of 20 sampled places boundaries are more than half of it; in inner NYC about a third of the large-park entries are street or bike paths. The trail term then saturates (scale 56.5 per 15 km is the median of the same mixed count), so Park Slope and Brooklyn Heights score alike on trails, and an LA place beside the Santa Monica Mountains scores on 189 boundaries but 1 real route. Evidence: `docs/ACTIVE_OUTDOORS_TRAIL_COUNT_FINDINGS.md`.

## Proposed count (what counts as one "trail destination")
1. Hiking routes: route=hiking relations, cycle routes excluded as now (bicycle yes, designated or official; networks icn, ncn, rcn, lcn). One each. Evidence: counts match the existing read exactly.
2. Large parks and reserves with trails: leisure=park or nature_reserve features with a bounding box of at least TODO ha (the pillar uses 50 ha today; unsourced), counted once per name, within 15 km. Excluded by name or tag: golf courses and clubs, piers, beaches, bridges, and linear street or bike features (greenway, cycleway, bike path, promenade, esplanade, avenue, boulevard) TODO word list.
3. Protected land: boundary=protected_area or national_park, and leisure=nature_reserve, of at least TODO ha, once per name, historic districts and heritage areas excluded (tags historic and heritage, names with "Historic District"). protect_class is missing on about 75% of features, so it is not used.
Items 2 and 3 are de-duplicated against each other by name so one park is not counted twice.

## What stays as is
Within 5 km term (same definition, same distance rule), camping term, point budgets (25, 15, 10: unsourced), and the 15 km radius. One scale for every place.

## Rebuild steps (after approval)
1. Trimmed read for all 1,476 places (about 4 seconds each; about 1.6 hours; second server needed for 545 places). Save raw features with type, name, bounding box and distance so the rule can change without re-reading.
2. Count per the rules above; refit the scale (median clean count at 15 km and 5 km, over places with an ok read).
3. Recompute wild for all places offline, then totals and composites from stored daily and water (no rescore of daily or water). Remove the 136 stored counts that equal the old cap of 30 as a side effect.
4. Health check on all metro files.
5. Independent verifier reruns checks 3, 4b and 5 with the criteria unchanged.

## How we will know it helped (decided before results)
Compared with today, report: Spearman between clean trail count and PAD-US protected area within 15 km (check 4b; was 0.31, need 0.4); Park Slope vs Brooklyn Heights gap (was 9.4, need 8); share of places at or near the trail term maximum; and the places that move more than 10 points in total, listed. Pass or fail is the existing Level 2 criteria; these extra numbers are descriptive.

## Decisions needed from the owner
1. Approve the three-part definition, or a simpler one (routes plus protected land of at least TODO ha, dropping park entries entirely).
2. The size cutoff TODO ha (the data shows real wild land at 100 ha and above; nothing sourced).
3. Open the second server for the 545 places in AZ CO FL GA MA NC NV.
4. Confirm that a refit scale (still relative to the catalog) is acceptable until budgets are sourced.

## Trial result on the 931 places read (2026-11-03; `analysis/ao_clean_count_trial.csv`; nothing merged)
Approved definition applied offline to the raw read, with the unsourced size cutoff tried at 50, 100 and 500 ha. Scale refit on these 931 places only (the other 545 need the second server), camping term taken from stored values (it comes out between 0 and 10 for every place, so the stored wild splits cleanly).
- The cutoff drives the result. Places moving more than 10 points in total: 118 (50 ha), 216 (100 ha), 365 (500 ha) of 931. Refit scale: 44 / 33 / 14 destinations per 15 km.
- Pair 4 improves at every cutoff because the wild gap closes (Park Slope 84.9, Brooklyn Heights 92.7 at 50 ha, gap 7.8; 87.2 vs 93.9 at 100 ha, gap 6.7). The remaining gap is the daily part.
- Inner NYC does not come down; it goes up: Financial District 81.1 to 92.7 (50 ha) or 94.9 (100 ha), Windsor Terrace 77.9 to 89.6 or 91.9, because the refit scale is lower and NYC still has 60 to 85 distinct named destinations within 9.3 miles. Under this definition that is a true count, so the "too many trails" result is now about the scale, not the data.
- Lakeshore and western places fall, and by a lot, depending on the cutoff: Evanston 83.2 to 72.4 / 65.3 / 61.8, Winnetka 89.7 to 83.0 / 82.8 / 64.2, Mar Vista 75.1 to 61.6 / 64.7 / 67.9.
- Launch pairs 1 to 3 still pass at every cutoff (Mill Valley about 84 vs Katy 33 to 39; Santa Monica 76 to 81 vs Sugar Land 49 to 52; Lincoln Park 67 to 73 vs Katy).
- Not computed: the check 4b correlation (PAD-US files were deleted after the earlier run; the cutoff could be chosen by that correlation on the first-server places and checked on the second-server places, an empirical rather than target-based choice).

## Cutoff versus PAD-US protected land (2026-11-03; `analysis/ao_clean_count_vs_padus.csv`)
PAD-US 4.0 state files for the 11 first-server states (905 MB, MD5 verified, deleted afterwards). Protected land (every public-access category) within 15 km of each of the 931 places, in hectares, against the clean trail count and the resulting wild score. Spearman:
| Measure | Old stored count | Clean, 50 ha | Clean, 100 ha | Clean, 500 ha |
|---|---|---|---|---|
| Trail count vs protected land (need 0.4) | 0.217 | 0.347 | 0.395 | 0.435 |
| Wild score vs protected land (need 0.4) | 0.194 | 0.327 | 0.372 | 0.399 |
| Trail count, without the NYC metro (n=738) | 0.283 | 0.390 | 0.452 | 0.508 |
Reading: any clean count beats the old one on this yardstick, and the correlation rises with the cutoff. That rise is partly built in, because PAD-US measures large protected land, so a rule that counts only big features will track it better. It does not show that 500 ha is the right cutoff. At 500 ha the wild score reaches 0.399 (limit 0.4) on these 931 places only; the criterion covers all 1,476, and the 545 second-server places are unread. NYC totals stay at 92 to 95 at every cutoff, and 365 of 931 places move more than 10 points at 500 ha.
Plan: read the 545 second-server places (trimmed read, about 40 minutes), fit the cutoff on the first-server places and judge it on the second-server places as a holdout, then decide.

## Holdout and pooled result (2026-11-03; `analysis/ao_clean_count_pooled.csv`, `ao_clean_count_vs_padus.csv`)
Second server read: 545 places (AZ CO FL GA MA NC NV), all with data. PAD-US 4.0 files for those 7 states (466 MB, MD5 verified, deleted afterwards). Spearman with protected land within 15 km:
| Set | Old count / old wild | Clean 50 ha, count / wild | Clean 100 ha, count / wild |
|---|---|---|---|
| Fit, first server (n=931) | 0.217 / 0.194 | 0.347 / 0.325 | 0.395 / 0.375 |
| Holdout, second server (n=545) | 0.390 / 0.372 | 0.409 / 0.343 | 0.487 / 0.405 |
| Pooled, all (n=1,476) | 0.310 / 0.292 | 0.370 / 0.338 | 0.425 / 0.383 |
| Pooled without Boston (n=1,395) | 0.284 / 0.264 | 0.351 / 0.313 | 0.412 / 0.364 |
- 500 ha is unusable with a median-based scale: the pooled median 5 km count is 0, which breaks the 5 km term. Dropped.
- At 100 ha the holdout confirms the fit direction (count 0.487, wild 0.405). Pooled, the count criterion (0.4) passes and the wild criterion (0.4) misses by 0.017 (0.383); without Boston both are lower on wild (0.364). The wild score also carries a camping term of up to 10 points that has nothing to do with protected land.
- Places moving more than 10 points in total: 174 of 1,476 (50 ha), 274 (100 ha).
- Inner NYC still ends at 92 to 95 total at 50 and 100 ha (a true count of 60 to 85 named destinations, scored against a lower refit scale). Pair 4 passes (gap 6.7 at 100 ha, from the first-server trial).
- The cutoff of 100 ha is chosen on the correlation only and has no independent source (TODO). Using the correlation as both the guide and the pass test is partly circular; the holdout is the only part that is not.
- Merging also needs the live scorer to use the same count (the trimmed read, about 4 seconds instead of about 90), the refit scale file, and a code change in the pillar and osm_api; none of that is done.
