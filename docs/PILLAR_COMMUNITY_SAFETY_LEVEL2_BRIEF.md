# Community safety: Level 2 checks, brief for an independent agent (2026-10-31)

Status: APPROVED by the owner 2026-11-01. Pass criteria below are fixed before any result exists; do not edit them after seeing data. The runner must not be the session that built or audited the pillar.

Scope: no scoring, catalog or code changes. Work in a new git worktree off origin/main. Read stored scores from `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` (`score.livability_pillars.community_safety`). Any download goes in its own empty folder, Python runs with `-I`. Say what data a step needs before any live call and ask. No em dashes.

## Check 1: launch pairs (offline, stored scores)
Should differ by at least 30 points: Compton CA vs Palo Alto CA; Camden NJ vs Newton MA; Compton CA vs Naperville IL.
Should be within 10 points: Newton MA vs Naperville IL; Park Slope NY vs Brooklyn Heights NY (both HYPER_LOCAL; stored today 71.9 vs 46.9, so this pair is expected to FAIL and is kept to show the pin-shift limit).
Result per pair: pass or fail with the two scores. The pillar passes if every differ pair passes and at least one similar pair passes. Report the Park Slope pair failure either way.

## Check 2: all-places distribution (offline)
Report n scored, counts at 95 or higher, exactly 100, exactly 0, 5 or lower. Spread by area type: take area type from the place context helper (`data_sources/place_context.py`, offline functions only), not the stored rows, and report 10th, median, 90th percentile per type. Pass: every area type has a 10th to 90th spread of at least 30 points, and no single value holds more than 3 percent of scored places. Report, do not fix.

## Check 3: pin-shift
Circle places (HYPER_LOCAL, 369): already measured 2026-10-26, median 13.7, p95 34.3 at 600 m. No rerun. Agency-level places (1,051): list how many sit within 1 km of their agency boundary using stored coordinates only if a boundary file is already in the repo; otherwise record "not testable offline". No pass criterion; disclosure only.

## Check 4: independent validation
Needs a data read; ask the owner before any download or API call. Source we did not build from: city open-data incident counts for at least 15 circle places where the stored incident feed is NOT the source, or, if none, the FBI NIBRS agency violent rate versus our stored violent rate for the 369 circle cities' parent agencies. Criteria, fixed now: Spearman rank correlation of our stored violent_per_1k against the independent source of at least 0.7 on n of at least 15, and median absolute rank difference under 20 percentile points. Fail otherwise. A second, independent source acceptable to the owner (a published precinct or tract crime map) replaces the first if the first cannot be obtained; say which was used.

## Output
A short report in `analysis/` with each check, its numbers, pass or fail against the criteria above, and what was not verified. Do not edit the spec sheet; the owner enters results and sets the level.
