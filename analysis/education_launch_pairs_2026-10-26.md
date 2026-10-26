# Education launch-check pairs (DPv2 P10), approved 2026-10-26

Pairs were proposed from public reputation and approved by the owner. Caveat: the stored scores were looked up before the pairs were written, so this is a check, not a blind pre-registration. Thresholds (20 points apart, within 10) are judgment, no source. Scores from origin/main (commit f53aecd).

## Should differ (gap of 20 points or more)

| Pair | Stored scores | Gap | Result |
|---|---|---|---|
| Palo Alto vs East Palo Alto, CA | 95.7 vs 30.5 | 65 | pass |
| Great Neck vs Hempstead, NY | 93.8 vs 21.1 | 73 | pass |
| Brookline vs Chelsea, MA | 93.6 vs 14.8 | 79 | pass |

## Should match (within 10 points)

| Pair | Stored scores | Gap | Result |
|---|---|---|---|
| Darien vs Westport, CT | 97.6 vs 96.5 | 1.1 | pass |
| Winnetka vs Lake Forest, IL | 97.3 vs 98.4 | 1.1 | pass |
| University Park vs Highland Park, TX (same district) | 99.0 vs 99.1 | 0.1 | pass |

## Mid-range pair added by the owner (2026-10-26)

| Pair | Stored scores | Gap | Result |
|---|---|---|---|
| Babylon vs Tarrytown, NY (should match, within 10) | 64.7 vs 49.4 | 15.3 | FAIL |

Why it fails, from stored data (not tuned away): Babylon's score rests on one level only. Its junior-senior high has no SchoolDigger rating, so middle and high are missing (a documented exception, flagged degraded) and the score is its elementary school alone (64.7). Tarrytown is scored from three levels (elementary 40.6, middle 48.9, high 58.7), and its elementary level is a single rated school (grades 3 to 5) because the zoned K-2 school has no rating. Like for like at elementary, the two differ by 24 points. A one-level score and a three-level score are not comparable, and this pair shows the cost of scoring from one level. Per P10, a failed pair means investigate the data or logic, not tune a parameter. Decision (owner, 2026-10-26): keep scoring from the levels that have ratings, flagged degraded; do not hide the rating. The failed pair is recorded as a known limit: a place scored from fewer than 3 levels is not directly comparable with a 3-level place (2 places are 1 of 3, 30 are 2 of 3).

## Limits

The first three matching pairs sit near the top of the scale and test the ceiling; the mid-range pair above is the only mid-range test, and it fails. Re-run after any change to education scoring or the yearly snapshot refresh.
