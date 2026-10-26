# Amenities launch-check pairs (DPv2 P10), approved 2026-10-26

Pairs were proposed from public reputation and approved by the owner. Caveat: the stored scores were looked up before the pairs were written, so this is a check, not a blind pre-registration. Thresholds (20 points apart, within 10) are judgment, no source. The repo's launch_check.py needs 10 or more places per group, so one-place pairs are recorded here instead of in data/launch_check_contrasts.json. Scores from the amenities branch (catalog at commit after c7a2e9a).

## Should differ (gap of 20 points or more)

| Pair | Stored scores | Gap | Result |
|---|---|---|---|
| West Village (NYC) vs Plano (Dallas) | 100 vs 35.5 | 64.5 | pass |
| Park Slope (NYC) vs Sherborn (Boston) | 99.1 vs 0 | 99.1 | pass |
| Back Bay vs Hamilton (Boston) | 99.5 vs 0 | 99.5 | pass |
| Hayes Valley vs Los Altos Hills (SF) | 97.6 vs 0 | 97.6 | pass |
| Lincoln Park (Chicago) vs Lakeway (Austin) | 88.3 vs 0 | 88.3 | pass |

## Should match (within 10 points)

| Pair | Stored scores | Gap | Result |
|---|---|---|---|
| West Village vs Greenwich Village (NYC) | 100 vs 100 | 0 | pass |
| Back Bay vs Beacon Hill (Boston) | 99.5 vs 91.5 | 8.0 | pass |
| Mission District vs Hayes Valley (SF) | 98.8 vs 97.6 | 1.2 | pass |

## Limits
Five of the "differ" pairs compare a dense city neighborhood with a place that scores 0, so almost any formula passes. They would not catch a subtle fault such as Darien (stored 81.3) scoring above Brookline (75.1), which the owner may want added as a hard pair. Los Altos Hills, Sherborn, Hamilton and Lakeway score 0 because no tracked business lies within 1,500 m of the pin (verified), which is a pin and construct fact, not a sign the towns lack amenities.
