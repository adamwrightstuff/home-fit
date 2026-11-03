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
