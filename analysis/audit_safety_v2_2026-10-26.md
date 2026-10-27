# Audit: community safety against design principles v2 (2026-10-26)

Status update (2026-10-27): the fail-loud fixes F1 to F3, F5, F6 and the revised F4 below were implemented and pushed to main in 0ecac19, with tests. No stored score changed (0 of 1,420 differ when recomputed from stored rates). The text below was written before that and describes them as proposed. Still open: 56 of 1,420 catalog places have no safety score because only a state-wide average was found for them (they now carry a "state aggregate only" reason; whether the agencies did not report or our name matching missed them is not yet checked, and that needs a live FBI check on a few places); Sunnyside and Windsor Terrace tract gaps are unresolved; the pin-shift limit is disclosed but not shown in the API; P7 validation and P10 launch pairs do not exist yet.

Scope assumption: you did not name a pillar, so this is community safety, P1 to P12, the pillar we were already in. Read-only and offline. No code, test, catalog or tracker file changed. Nothing committed.

Caveats on what was read. The principles file is a local-only draft, and its own Part 4 says its frame evidence came from search summaries and was not checked against the papers. I did not check any citation (offline). Code and docs are from origin/main (read with `git show`, because local main is 9 commits behind and lacks the 0.098 weight change). Stored data is from this checkout's `*.composites_recomputed.jsonl` files, which still hold the old 0.35 and 0.15 weights, so score levels below are pre-change. Slot, source, trend and confidence fields are unaffected by the weight change.

## Finding

The pillar meets P8 and most of P9. It does not meet P4 for the trend modifier, the 10,000-person circle, the 600 m to 2,000 m radii, the work-week share and the confidence values (all unsourced), it fails P9 in two places, and it has no P7 validation of its score. The largest gap is spatial: a pin shift moves the score a median of 13.7 points in the one test run (P6, P3).

## Per principle

| P | Status | Evidence |
|---|---|---|
| P1 reference frame | Partial | National percentile, one scale for all area types, which matches the draft's "fixed standard" default for harm pillars as a norm-based proxy. The draft itself rates this tier 2 and says it did not confirm absolute versus relative rates. The pillar docs' "Gotchas" and "What it measures" sections still describe area-type-relative scoring (stale; they contradict the code and the opening of the same file). |
| P2 construct | Partial | Module docstring: "how safe a place is compared with US cities". The 0.098 weight measures social cost of crime, which is a different quantity from risk to a resident or price paid. The score is an offense-rate rank, not a harm measure. Not stated as one sentence. |
| P3 measurement area | Does not meet | Two different areas inside one pillar. 369 places (HYPER_LOCAL) use a circle of 600 to 2,000 m holding at least 10,000 people. 893 (AGENCY_VERIFIED) and 158 (PRECINCT_PROXY) use the whole police agency or county sheriff rate. Mean stored score is 42.9 for circles versus 58.6 and 58.4. That gap mixes real difference (the circles are big-city neighborhoods) with a method difference; I cannot separate them from stored data. The docs give a reason for the smallest-radius choice (resident-drawn neighborhoods, price effects within 0.1 to 0.25 mile) but I did not verify those sources. |
| P4 sources and ranges | Does not meet | See table below. Only the property weight (0.098) has a source and a recorded sensitivity. |
| P5 double counting | Partial | The commuter and people-present denominator uses the LODES grid, the same data economic security uses (the old docs say so). Not tested for overlap. No other pillar's crime use was found. |
| P6 sensitivity | Partial | Weight: done (see audit_safety_weight_2026-10-25.md). Pin shift and radius: one run exists (`analysis/safety_radius_floor_results.json`, 96 big-city places, 3 pins each). Spread of the score across pins at 600 m: median 13.7 points, 95th percentile 34.3, max 46.3. Raising the radius floor to 800 m changes the score median 3.0, p95 12.2; to 1,000 m median 5.0, p95 16.9. Not tested: trend cap, 10,000-person minimum, work-week share. |
| P7 independent validation | Does not meet | The docs say radius floors "did not agree better with third-party ratings" but name no source and I found none in scripts or analysis. No precinct-data or rating check of the score itself. The 2026-10-09 longevity result in memory covers a different index. |
| P8 test across all places | Meets | 1,420 of 1,476 scored, 56 no data, all weight and radius work run on the whole catalog. |
| P9 fail loud | Partial | Good: no crime data returns None (56 places, all DEGRADED, none stored as zero), and state-aggregate data is withheld. Two failures below. |
| P10 launch check | Does not meet | No pairs defined. Clumping: 114 places at 95 or higher, 24 at 100, 4 at 0; 37 places have a violent slot of exactly 100. Spread by area type could not be reported because stored records carry no area type under the keys I could find. |
| P11 disclose limits | Partial | Confidence and precision level are stored per place (mean 93 circle, 82 agency, 69 proxy). The FBI sample and national-scale limits are in the scale file. Trend missing and low-coverage cases are not surfaced as degraded. |
| P12 re-validate | Does not meet | Rebuild commands exist; no schedule. |

## Parameters (P4)

| Parameter | Value | Source | Range recorded |
|---|---|---|---|
| Property weight | 0.098 | McCollister et al. 2010 costs and BJS 2023 rates, per commit 1b6df81 (unverified here) | Sensitivity 0.197 to 0.519, no plausible range stated |
| Violent weight | 0.902 | Derived from the above | Same |
| Trend cap | plus or minus 5 points, reached at plus or minus 100 percent year-over-year change | None | None |
| Minimum residents in circle | 10,000 | None found (the docs argue for the smallest area with enough people but do not source 10,000) | None |
| Radius ladder | 600, 800, 1,000, 1,200, 1,500, 2,000 m | Docs cite distance research for 600 m, unverified | None |
| Work-week share | 45 of 168 hours | Comment only, no citation | None |
| Confidence by precision level | 93, 82, 69 and penalties 3 and 6 | None | None |
| National scale | 561 agencies, 2024, sample of cities and counties, population weighted | Documented in the scale file | Sampling limits recorded |

## Defect list, with stored-data evidence

1. Trend modifier is unsourced and larger than it looks. 1,320 of 1,420 places have a nonzero trend delta. Mean absolute 1.14 points, 614 places move 1 point or more and 226 move 2 or more, max 5. It rests on one agency's year-over-year violent count change, which is noisy for small places. The code comment says "plus or minus 30 percent = plus or minus 3 points" but the formula gives 1.5 points for 30 percent, so the comment is wrong.
2. Fail-loud violation, scale: `_national_percentile` returns 50.0 when the national scale has no points, and a failed scale load only logs a warning. If the file were missing, every place would score a neutral percentile instead of no data. Not triggered in stored data (scale loaded, 561 agencies); this is a code-path finding.
3. Fail-loud violation, population: when no population is supplied the code assumes 10,000 residents. I did not trace which sources use that value for a rate; for agency-level sources the agency's own population is likely used. Needs a trace before calling it live.
4. Missing optional input not flagged for trend: 87 places have no trend (stored without a degraded reason). The only degraded reason stored is the missing commuter grid (86 places). P9 asks for degraded with a reason.
5. Mixed measurement area (P3) with no stated reason that circle and whole-agency scores should be comparable.
6. Pin sensitivity (P6): median 13.7 points across three pins in 96 big-city places. This is the largest single uncertainty in the pillar and is larger than any weight effect (0.098 versus 0.299 moves a typical place 2.6 points).
7. No independent validation (P7) and no launch pairs (P10).
8. Stale docs: "What it measures" and "Gotchas" still say area-type-relative, contradicting the national scale.

## Proposed fixes and expected impact

Do not apply any of these yet.

1. Decide the pin-shift problem first. Candidate: score the circle as the average of several nearby pins (smooths, costs more Overpass-free calls because open-data incidents are local). Expected impact: reduces pin spread, moves scores for the 369 circle places; magnitude not computable offline from stored values because it needs incident data per pin. The radius file has per-pin scores for only 96 places.
2. Record the trend cap, 10,000 minimum, radii and work-week share as judgments with ranges, or run a sensitivity. The trend cap can be tested offline from stored trend_pct: set it to 0, 2.5 and 5 and report movement (up to 5 points for 226 places by construction). The 10,000 minimum cannot be tested offline.
3. Replace the 50.0 fallback and the 10,000 default with no data, and flag missing trend as degraded. No score change for stored places; changes behavior only on failure.
4. Define launch pairs (for example the places already used in the radius test) and a precinct comparison for a sample.
5. Fix the stale docs and the trend comment.
6. Obtain the sources the draft did not retrieve (Gibbons 2004, crime-severity index weights) before leaning on them.

## Decision for you

Should the next step be a pin-shift fix (item 1), since it moves scores more than anything else here, or the cheaper fail-loud fixes (item 3) first?

## Update 2026-10-26: pin-shift root cause (offline, from the stored radius test)

Source: `analysis/safety_radius_floor_results.json` (shared checkout, untracked), produced by `scripts/catalog/test_safety_radius_floor.py`. It scores each place at the catalog pin and at pins shifted 500 m north and 500 m east, 96 big-city places. The shift is large compared with a 600 m circle, so most of the circle changes.

Spread of the score across the three pins, per place:

| Radius floor | Median spread | 95th percentile | Median violent offenses in the smallest circle |
|---|---|---|---|
| 600 m | 13.7 | 34.3 | 69 |
| 800 m | 9.6 | 29.5 | 127 |
| 1,000 m | 9.1 | 25.5 | 198 |

Places whose smallest circle holds under 30 violent offenses (11 places) have a median spread of 19.1; places with 60 or more (56 places) have 11.5.

Reading it: small counts make it worse, but even with 60 or more offenses the median spread is 11.5, and a larger radius stops helping after 800 m. So most of the spread is real variation in crime over 500 m (the circle covers a different set of blocks and census tracts), not count noise, and a bigger circle buys little. This is a property of scoring a neighborhood-sized circle, not a code bug. The radius-floor note on origin/main says larger floors did not agree better with third-party ratings (source not found), so enlarging the circle trades pin stability for local accuracy and has no validation either way. Averaging several nearby pins would reduce the spread for the same reason a larger circle does, so it cannot be expected to beat the 800 m row (median 9.6) by much, and it needs per-pin incident data not stored in the catalog. Expected score impact is therefore not computable offline for any option beyond the radius floors above.

## Decision 2026-10-26: pin shift accepted as a disclosed limit (no scoring change)

Text for the pillar spec sheet, to be copied into `docs/PILLAR_COMMUNITY_SAFETY.md` when approved:

    Pin-shift sensitivity (500 m shift, 96 big-city places with incident feeds, 600 m circle):
      median score change across three pins 13.7 points, 95th percentile 34.3, max 46.3.
      With an 800 m floor, median 9.6; with 1,000 m, median 9.1.
    Cause: real variation in crime over 500 m, not count noise or a defect.
    Applies to: the 369 places scored from a circle. The 1,051 agency-level places are not
      circle-based and were not tested.
    Decision: no change to the circle. Larger floors steady the score little and have no validation.

Not done: showing this as lower confidence in the API response. That is a code change and needs its own approval.

## Proposal 2026-10-26: fail-loud fixes (NOT applied; nothing changed)

Checked in code on origin/main (087fc26) and in stored data (1,420 scored places).

| # | Change | Where | Stored places affected | Score impact |
|---|---|---|---|---|
| F1 | Empty or failed-to-load national scale returns no data, not percentile 50. The module load failure becomes an error, not a warning. | `pillars/community_safety.py`, `_national_percentile` and the scale load | 0 (scale loads, 561 agencies) | None on stored scores |
| F2 | Replace `population or 10_000` with no data when no population is supplied. Live path always passes a population, so this only matters on a caller error. Several crime paths use `population` as a fallback denominator (NY UCR village fallback, CA DOJ), which is where a neutral 10,000 could leak in. | `pillars/community_safety.py` line 281; `data_sources/crime_api.py` fallbacks | Not detectable from stored data | None found; behavior changes only on failure |
| F3 | Remove hard-coded denominator substitutions or flag them: default density 3,000 per sq mi, 500-person floor, and the "blend up 35 percent" fragment rule. | `data_sources/census_api.py`, `estimate_community_safety_disk_population` | 0 used (all 1,420 have an areal estimate; fragment blend 0, floor 0). In the 369 circle places the method label is overwritten with "ambient_residents_plus_workers", but the weighted estimate is present on all of them, so the areal path ran | None on stored scores |
| F4 | Flag tracts with no population as degraded with a reason. Today they are skipped silently, which shrinks the denominator and overstates crime rates. | `data_sources/census_api.py`, `pillars/community_safety.py` degraded_reasons | 192 places have at least one such tract; only the 42 circle places use this denominator for the score | Flagging alone: none. If instead the missing tracts were filled, a rough estimate for the 42 (assuming each tract holds equal population and ignoring workers) raises scores by mean 4.0, median 3.8, max 11.3; 37 would move over 2 points, 10 over 5. Largest: Glendale 64.9 to 76.2, City Island 64.6 to 73.9, Turtle Bay 63.0 to 70.4, Maspeth 55.0 to 61.9. This is an estimate to size the problem, not a proposed value. |
| F5 | Missing violent trend becomes a degraded reason ("trend unavailable, no trend adjustment"). | `pillars/community_safety.py` | 87 places | None (trend delta is already 0.0 for them) |
| F6 | Note when a tract population came from the older ACS 2019 same-code lookup. | `data_sources/census_api.py` | 129 places | None; disclosure only |

Totals if F1 to F3, F5 and F6 are applied and F4 is flag-only: no stored score changes. 192 places gain a degraded flag (F4), 87 more for trend (F5; some overlap), 129 get a vintage note. If F4 is changed to fill or reject the 42 circle places, scores move as shown above and would need a decision per place source (an older-vintage lookup already exists and fills 129 tracts).

Note on F4 and the earlier audit: the earlier audit listed only one stored degraded reason (missing commuter grid, 86 places). This finding adds a silent distortion for 42 places that is not flagged anywhere.

Open question for the owner: for the 42 places, is flagging enough, or should the missing tract be filled from the older-vintage lookup the code already uses elsewhere? Filling changes scores; flagging does not.

## Result 2026-10-26: what the 42 "missing tract population" places actually are

Method: for the 42 circle places, re-ran the pillar's own tract lookup against the Census API (read-only, about 60 small requests, no files downloaded) and recorded, for each tract that counted as missing, whether ACS returned a population of 0 or no row at all. Script and raw results are in the session scratchpad, not the repo.

Result: of 49 missing tracts, 47 have an ACS population of exactly 0 (parks, water, industrial land). Skipping those is correct, so 40 of the 42 places have no distortion and the earlier "scores too low by about 4 points" estimate does not apply to them. That estimate was wrong for those places because it treated every missing tract as populated.

Two places are unresolved: Sunnyside (36.2) and Windsor Terrace (79.6), both NYC. Their tracts show no ACS row today. The live lookup is also not repeatable: Sunnyside returns 5 missing tracts now versus 1 stored, and across all 42 places only 21 reproduce the stored estimate exactly (median difference 0.6 percent, max 14.7 percent). Whether those two are truly empty or hit a Census gap is not settled.

Revised F4: do not fill or flag the 40. Treat a tract with population 0 as valid, and report "no row" separately from "zero population" in the stored metadata so the two can be told apart. Flag degraded only for no-row tracts. Open item: look up Sunnyside and Windsor Terrace tracts by hand. Also the 192-place count in F4 mixes zero-population and no-row tracts and should be re-split before any flag is added.
