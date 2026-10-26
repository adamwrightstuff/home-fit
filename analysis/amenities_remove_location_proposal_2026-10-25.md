# Proposal: amenities pillar fixes (draft, not applied)

Supersedes the earlier version of this file, which argued for removing location quality. That was wrong: a good nearby town center is part of the pillar's intended construct. Companion to `analysis/audit_amenities_2026-10-25.md`. Nothing was changed, rescored, committed or pushed.

## Construct (to adopt in the pillar doc)
Walk-time access to daily life from home (density, variety, essentials proximity within 800 m), plus access to a nearby business center. Frame: fixed walk-time access (v2 P1), evidence tier 1 for the walking-time density and variety part only (Couture and Handbury, young graduates).

## A. Location quality: keep, document, then fix the measurement
1. Now, no score change: keep the 60/40 blend. Record the 0.6 multiplier, the 400/800/1,200/1,600 m steps and the density divisors as unsourced judgment, with measured ranges (home multiplier 0.5 to 0.7 moves the mean about 5 points; replacing area-type divisors with one moves it 0.3).
2. Later: replace the current measure (distance from the pin to the median coordinate of all nearby businesses) with a real one: the densest business cluster within reach of the pin, scored on size and variety, with decay by distance. The weight and reach remain a TODO until a study or revealed-preference source is found. Do not adopt new numbers without one.
3. Known weakness until then: the term double counts the same business list as the home score (correlation 0.86) and lifts car-dependent towns (Darien 75.9 vs Brookline 72.5).

## B. Fail loudly (no score impact except La Crescenta)
- Store the 49 null places as no data with a reason and degraded. No totals change.
- La Crescenta's imputed 15.0 becomes no data: total 69.05 to 73.55.
- Live path: an empty Overpass read must be confirmed by a second endpoint before it is scored as an empty area; otherwise no data with a reason. Replace the test that locks in the current behavior.
- Mark degraded when the Places fallback was needed and failed.
- Retry the 49 and La Crescenta from the private Overpass server. New scores cannot be estimated offline.

## C. Grocery check: supermarkets and greengrocers only
Convenience stores stop earning the grocery credit in essentials proximity (they still count toward density and variety). Impact, from stored values: mean -1.3 on the amenities score, 125 places lose more than 5 points. By area type the mean is -1.06 to -1.36 (urban residential -1.18, suburban -1.36), so dense areas are not hit harder; by metro -0.3 (Seattle) to -1.9 (Las Vegas), NYC -1.6. Worst drops are about -6.8 (full grocery credit lost), e.g. East New York, Flushing, Fort Greene, Ridgewood 72-90 to roughly 66-84. Spot-check one or two bodega-reliant NYC places before adopting. The category definition is a judgment; no source retrieved.

## D. Cleanups (no score impact beyond 3.6 points)
- Delete the unused `vibrant_threshold`, the dead functions (`_score_density`, `_score_variety`, `_score_proximity`, `_empty_breakdown`, `_empty_breakdown_with_fallback`) and the stale "NO LONGER inflates the score" comments.
- Fix the version string and the live versus catalog key mismatch (`businesses_within_1km` vs `businesses_within_walk`).

## E. Documentation
Rewrite `docs/PILLAR_NEIGHBORHOOD_AMENITIES.md` with the v2 spec sheet: construct, frame, 800 m window as judgment with its sensitivity (600 m mean -3.9, 1,000 m +2.5, 400 m -9.0), pin tolerance (a 200 m shift moves about 400 places by more than 5 points), Places fallback limits, chain inclusion. Update the pillar-coverage-gaps memory note.

## Order
B and D first (small, safe), then C after the NYC spot-check, then A.2 as its own design task. Each code change gets a full-catalog impact check before any catalog rewrite, offline from stored fields, backups first.
