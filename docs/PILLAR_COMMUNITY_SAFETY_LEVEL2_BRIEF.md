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

## Check 4 addendum (2026-11-01, owner chose precinct maps; criteria fixed before any data is read, pending owner approval of the downloads)

Source: NYPD precinct crime statistics PDFs, 2024 annual column (murder, rape, robbery, felony assault), `nyc.gov/assets/nypd/downloads/pdf/crime_statistics/cs-en-us-<NNN>pct.pdf`, plus the NYPD precinct boundary file from NYC Open Data. NYC only, because 96 of the 369 circle places are there and it is the one city with a precinct publication that carries annual totals. Chicago, Philadelphia and others are not covered.
What it tests: our circle method (600 to 2,000 m, people-present denominator, stored violent_per_1k) against a precinct-wide published tally. It does NOT test the incident records themselves: NYPD publishes both from the same record system. Say this in the spec sheet.
Selection, before any precinct number is read: assign the 96 stored NYC places to precincts by point in polygon; keep one place per precinct; pick 15 to 20 precincts spread across the stored score range (by score quintile). Precinct residents come from the offline ACS tract tables (tract centroids inside the polygon).
Pass, fixed: n at least 15 precincts; Spearman of the precinct's violent rate per 1,000 residents (four offenses, 2024) against our stored violent_per_1k for the matched place at least 0.7; median absolute rank difference under 20 percentile points. Fail otherwise. Report n, Spearman, the five largest rank gaps.
Access: a scripted HEAD request to the NYPD PDF returned 403 on 2026-11-01. Do not work around the block (no header spoofing). If blocked, download through the owner's browser into an empty folder, or stop and report.

## Check 4b: FBI agency cross-check (2026-11-01, owner chose "NYC + FBI"; criteria fixed before any FBI number is read)
Scope: the parent police agencies of the circle places (about 11). Our stored circle-level violent_per_1k, averaged per agency over its circle places, against that agency's FBI CDE 2024 violent offenses per 1,000 residents (summarized/agency, violent-crime, 12 months, population from the same response). About 22 requests, existing key, under 100 KB.
Weakness, stated up front: a 600 to 2,000 m circle is compared with a whole-city rate, and n is about 11, below the 15 fixed for 4a. This check is supplementary and does not decide the 4a pass. Criteria, fixed now: Spearman at least 0.7 and Pearson on log rates at least 0.7 across the agencies available; report n, both statistics, and the agencies where the gap is largest. Because circle neighborhoods can differ from their city, a fail here is reported as "inconclusive about the circle method", not as a pillar failure; a pass is reported as agreement only.
