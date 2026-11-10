# Happiness index Level 2 plan v2, independent run (2026-11-05)

Conclusion: PASS. V1 to V4 all pass under plan v2, so Level 2 holds, with the label "checked on a subset". Run by the independent session; no scoring, weights, criteria, pairs or data files changed. Script: scratchpad v2.py (python -I), written fresh.

## Setup
Catalog: 1,476 places, 21 metros, composites_recomputed files. Outcomes: CDC PLACES ZCTA 2025, crude prevalence, sign flipped so higher is better. Join: score.location_info.zip (zero padded). Income: housing_value summary median_household_income as stored. Index recomputed from stored happiness_index_breakdown with v5 weights (mean absolute difference from stored happiness_index 0.025, max 0.055, rounding). V1 index drops social and renormalizes. Spearman on ranks; partial is Spearman partial after income rank.

## V1 and V2 (n 850 places with both outcomes and income)
| Outcome | n | Raw | Partial | Equal raw | Equal partial | Gap raw | Gap partial | V1 | V2 |
|---|---|---|---|---|---|---|---|---|---|
| LONELINESS | 850 | 0.577 | 0.416 | 0.489 | 0.276 | +0.087 | +0.140 | PASS | PASS |
| EMOTIONSPT | 850 | 0.610 | 0.405 | 0.568 | 0.325 | +0.042 | +0.081 | PASS | PASS |

Neither partial is under half the raw, so neither is flagged as tracking affluence. Income alone: 0.454 (LONELINESS), 0.539 (EMOTIONSPT), below the index on both.

## V3 (metros with 30 or more places holding both outcomes)
| Metro | n | LONELINESS raw | EMOTIONSPT raw |
|---|---|---|---|
| atlanta | 73 | +0.379 | +0.252 |
| boston | 77 | +0.742 | +0.630 |
| charlotte | 35 | +0.217 | +0.325 |
| chicago | 100 | +0.754 | +0.654 |
| la | 94 | +0.627 | +0.558 |
| nyc | 183 | +0.794 | +0.813 |
| phoenix | 60 | +0.440 | +0.429 |
| sacramento | 56 | +0.643 | +0.496 |
| sf | 100 | +0.633 | +0.587 |

V3: PASS, all 9 positive on both outcomes. Not tested (under 30 with both outcomes): austin 0, dallas 0, denver 0, houston 1, las_vegas 26, miami 0, orlando 0, philadelphia 16, raleigh 28, san_antonio 1, seattle 0, tampa 0. Charlotte is the weakest (+0.217).

## V4 launch pairs
Each name matched exactly one catalog row (state and metro below), so no ambiguity and no row choice.

| Pair | Metro | Scores | Diff | Rule | Result |
|---|---|---|---|---|---|
| Bronxville NY over Yonkers NY | nyc | 73.1 vs 48.4 | 24.7 | 6 or more | PASS |
| Manhattan Beach CA over Inglewood CA | la | 64.9 vs 47.9 | 17.0 | 6 or more | PASS |
| Wellesley MA over Chelsea MA | boston | 72.4 vs 41.0 | 31.4 | 6 or more | PASS |
| Wilmette IL, Winnetka IL | chicago | 75.1 vs 76.9 | -1.8 | within 7 | PASS |
| Glen Rock NJ, Ridgewood NJ | nyc | 79.4 vs 78.0 | 1.4 | within 7 | PASS |
| Needham MA, Lexington MA | boston | 73.8 vs 76.8 | -3.0 | within 7 | PASS |

6 of 6 (needs 5). Pair scores are the stored full happiness_index.

## Informational only (not a criterion): GHLTH, a health outcome
Full index vs GHLTH, n 1,314: raw 0.550, partial 0.196. Partial is under half of raw and income alone is 0.678, so this tracks affluence. Not used for any verdict.

## Not verified
- PLACES ZIP values are modeled small-area estimates, which can borrow from income-linked demographics and inflate correlation.
- Crude prevalence, not age-adjusted.
- Coverage: V1 n 850 of 1,476 (57.6 percent). LONELINESS and EMOTIONSPT are absent for Colorado, Florida, Washington, Pennsylvania, Maryland and nearly all of Texas, so 12 metros are untested in V3.
- Shared ZIPs: many matched places share a ZIP and so share an outcome value (304 of 1,314 in the first run; not recounted for the 850 here). Observations are not independent; no significance tests computed.
- Income is place level, outcomes are ZIP level.
- The index is partly built from the same affluence-linked data; partial correlations of 0.4 show signal beyond income, not causation.
