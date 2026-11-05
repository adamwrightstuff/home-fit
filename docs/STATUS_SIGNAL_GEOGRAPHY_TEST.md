# Status signal: which geography should the label read? (criteria fixed before running, 2026-11-05)

Why: Carroll Gardens (pooled income $141,308, $1,296 under the NYC p80 line) is Affluent only through the household route at 60.0, and Gowanus (pooled $175,281, $4,511 over the p90 line) is Elite at 81.1, while on the pin tract alone the order reverses ($178,041 against $134,167). The Level 2 launch pair Park Slope and Carroll Gardens already failed and was accepted as a TODO on 2026-11-04; this test is the work on that TODO. Read-only, offline, 495 tract-level places (the 981 place-level places do not change with the pool). No label, score or catalog is changed.

## Candidates (income and home value for tract-level places; burden ratio and household share held as stored, class rule and scoring unchanged)
- P: the pin tract alone (stored single-tract values).
- R350: pool of the tracts under the pin and 8 points at 350 m (occupied-unit weighted, tract shape as a disk, same machinery as the shipped pool).
- R700: the shipped pool (700 m). Rebuilt here and identical to the shipped file.

## Criteria (thresholds are the Level 2 brief's, judgment limits, inherited, not published standards)
1. Neighbor spread: every pair of tract-level catalog places within 1,000 m. Pass: median absolute score difference at most 5, 95th percentile at most 20, same class for at least 80% of pairs.
2. Pin shift: each tract-level place shifted 500 m north, south, east, west (approximate, nearest tract disk). Pass: median absolute score change at most 5, 95th percentile at most 20, class unchanged for at least 80% of shifts.
3. Named pairs. Within 15 points: Park Slope and Carroll Gardens, Carroll Gardens and Gowanus (added after the owner's complaint, not in the 2026-11-04 brief), Brookline and Newton, Wicker Park and Bucktown. At least 25 points apart in the stated direction: Palo Alto above East Palo Alto, Atherton above East Palo Alto. Reported as a count met.
Decision rule: a candidate replaces R700 only if it passes 1 and 2 outright, meets at least as many pairs in 3, and does not lower the same-class share in 1 or the class-unchanged share in 2. Otherwise R700 stays and the failure is recorded as known.
