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

## Results (run 2026-11-05; 495 tract-level places, 71 neighbor pairs within 1,000 m, 1,930 to 1,980 pin shifts)
| | P (pin tract) | R350 | R700 (shipped) |
|---|---|---|---|
| C1 neighbor score difference, median / 95th percentile | 11.5 / 40.0 | 8.0 / 26.6 | 5.9 / 21.3 |
| C1 neighbors in the same class | 43.7% | 54.9% | 54.9% |
| C1 verdict (limits 5, 20, 80%) | FAIL | FAIL | FAIL |
| C2 pin shift, median / 95th percentile | 1.4 / 26.8 | 1.5 / 16.2 | 1.2 / 12.5 |
| C2 class unchanged | 81.8% | 89.2% | 91.2% |
| C2 verdict (limits 5, 20, 80%) | FAIL (95th percentile) | PASS | PASS |
| C3 pairs within 15 points (4) | 1 | 3 | 1 |
| C3 pairs 25 apart (2) | 1 | 1 | 1 |

C3 detail (score and class): Park Slope and Carroll Gardens 84 and 82 (P), 90 and 84 (R350), 85 and 60 (R700); Carroll Gardens and Gowanus 82 and 60 (P), 84 and 82 (R350), 60 and 81 (R700); Wicker Park and Bucktown 86 and 59 (P), 85 and 82 (R350), 83 and 79 (R700); Brookline and Newton 60 and 80 under all three (20 apart); Palo Alto above East Palo Alto 24.9 under all three (limit 25), Atherton above East Palo Alto 53 under all three. Carroll Gardens, Gowanus, Park Slope and Cobble Hill are all Elite under R350.

Decision rule result: no candidate passes C1, so R700 stays. Findings that matter:
- Every geography fails the neighbor-spread proxy: only 44 to 55 percent of neighbors within 1,000 m share a class. The cause is structural, hard lines on a continuous variable where many catalog places cluster close to the p80 and p90 lines, so near-equal neighbors split. Shrinking the pool does not remove it.
- R350 is much better on the named pairs (3 of 4 within 15 against 1 of 4) and still passes the pin-shift check, but its 95th percentile shift is 16.2 against 12.5 and its neighbor spread is worse than R700 on the median and 95th percentile.
- The household route did not cause the Carroll Gardens and Gowanus split; the pooled income sat $1,296 under the p80 line and $4,511 over the p90 line.
- Pin tract alone (P) fails pin shift and is the least stable, so it is not an option.
This test does not change the label rule, the lines, or the pool; any of those is a decision for the owner.
