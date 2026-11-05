# Status signal Level 2 checks: brief for an independent runner

Written 2026-11-04 by the builder. The runner must be a different agent or session from the builder. Pass criteria below are fixed before any result and may be edited by the owner, not by the runner.
Code under test: branch `status-signal-dpv2` (`pillars/status_signal.py`, `class_position_score`). Spec: `docs/STATUS_SIGNAL.md`.
Run Python with `-I`. Downloads need owner permission, go in their own empty folder, and scripts live elsewhere. No Overpass reads are needed. Do not push, commit to main, or edit scoring.

## Data the checks need (owner must approve before any call)
- Check 1: Census geocoder tract lookups at shifted pins (API, free, about 240 calls) plus ACS 2022 B19013, B25105 and B25077 for the shifted tracts (about 180 calls).
- Check 4: ACS 2022 B19001 income bins for each place's stored geography (about 1,470 calls, same geography as `housing_value.summary.geo_level`).
- Checks 2 and 3 are offline from `data/status_class_position/*.jsonl`.

## Check 1: pin-shift
Sample 60 places, 12 per class (Struggling has 13; take 12), seeded random (seed 20261104). Shift each pin 500 m north, south, east, west. Recompute class and score with `compute_status_signal_with_breakdown` using the tract and geography at the shifted pin (the same geo level as stored). 
Pass: median absolute score change at most 5 points and 95th percentile at most 20; class unchanged for at least 80% of shifts. Report the places that fail and their geo level. The thresholds are a judgment fixed before results, not a published standard.

## Check 2: all-places check (offline)
Over all 1,476 stored places: class inversions between any two places must be 0; report spread by area type (10th, median, 90th percentile) and the count at floor (at most 10) and at 100. 
Pass: 0 inversions, and no area type with more than 25% of its places tied at one value. Known and accepted ties: Affluent places over the p90 income line that miss the p90 home value line tie at 80, Elite places at or above the $250,001 topcode tie at 100.

## Check 3: launch pairs (offline)
Pairs fixed now. Verify each name exists in the catalog; if one is missing, use the listed backup and say so.
- Should differ by at least 25 points, in this direction: Scarsdale NY above Mount Vernon NY; Atherton CA above East Palo Alto CA; Palo Alto CA above East Palo Alto CA (backup: Beverly Hills CA above Compton CA); Highland Park IL above Englewood (Chicago) IL.
- Should be within 15 points: Park Slope and Carroll Gardens (Brooklyn); Brookline MA and Newton MA (backup: Cambridge MA); Wicker Park and Bucktown (Chicago).
Pass: all differ-pairs separate by 25 or more in the stated direction; at least 2 of 3 similar-pairs within 15.

## Check 4: independent validation
Independent statistic: the share of households with income of $200,000 or more in the place's own B19001 distribution (not an input to the score, which uses the median and metro cutoffs). 
Pass: Spearman between the score and that share at least 0.80 across all places with data; and the median share rises strictly from Struggling through Working, Middle, Affluent, Elite.
Limit to write down: this tests the cutoff construction against another statistic from the same Census table family, not the class construct itself. No external source for "class" that we did not build from exists in the repo; say so in the write-up.

## Report format
One table per check with n, the numbers, pass or fail against the criteria above, and the failing places. State what was not run. Do not propose scoring changes in the report.
