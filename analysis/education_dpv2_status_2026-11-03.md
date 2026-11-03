# Education pillar, DPv2 status per requirement (2026-11-03)

Offline, from stored catalog data on origin/main (86c66afe, 1,476 places). No live API, no SchoolDigger call, no Overpass read. Scoring unchanged. Decisions of 2026-10-26 (assigned-school construct, state percentile, equal weight, early education 0 points) are not reopened. Spec sheet: end of `docs/PILLAR_QUALITY_EDUCATION.md`.

## Level 1 (Converted)

| Requirement | Status | Evidence |
|---|---|---|
| Spec sheet filled | Done (this session) | Written into the pillar doc; it supersedes `analysis/education_spec_sheet_2026-10-26.md`, which had stale lines (pin flag "TODO", live scorer defect). |
| Reference frame with evidence tier | Done (this session) | State norm, tier 2 plus owner decision (tier 3). The evidence supports ranking by test score, not state as the reference group; state is used because tests differ by state. Deviation from the Part 1 default (fixed standard) recorded. Sources read from search summaries only. |
| Shared place facts from the place context (P13 to P17) | Partial | The pillar takes `place_context.area_type` when passed and uses no density factor. The catalog offline rescore reads the stored area type, not the helper. Nothing in the pillar re-derives a shared fact. |
| No scoring value keys on the area-type label, or each use listed with a reason | Partial | One use remains: the search radius on the nearest-school path (351 places). Listed with a reason (it moves scores a mean 0.2 to 0.6 across a x0.5 to x2 range). New defect found: the profile keys on `urban_core` but the classifier emits `urban_residential`, so urban residential places get 3.0 mi, not the documented 1.5. 30 places affected. |
| Failed or unmeasurable data is left out or flagged, never neutral (P9) | Done | 4 no data, 32 degraded for a missing level, 541 `early_ed_missing`, live scorer keeps no data. |

## Level 2 (Verified)

| Requirement | Status | Evidence |
|---|---|---|
| Pin-shift sensitivity | Done, rechecked | Stored per place since 2026-10-26. Recomputed from the stored values: median 5.8, p95 42.6, 387 over 15 points. New: by area type, urban residential median 20.9, p95 54.7, 124 of 200 flagged; rural median 0.0. Not rerun from scratch (no code change since). |
| All-places check with spread by area type and floor/ceiling clumping | Done this session | n 1,476 (1,472 scored). By-area-type spread and clumping were missing before and are now in the spec sheet. No ceiling at 100; 6.5% at 95 or above; 0.7% at 5 or below; urban residential 90th percentile 79.6. |
| Launch pairs | Done, rechecked | Six approved pairs pass; the mid-range pair Babylon vs Tarrytown fails and is recorded as a known limit. All seven stored scores reproduce exactly today. Pairs were named after the scores were seen. |
| Independent validation, pass criteria fixed first | Partial, does not count yet | EDFacts runs exist (Spearman 0.66 to 0.92 for ratings; 0.93 to 0.94 weighted for places) but: no pass criteria were fixed before results, coverage is 798 of 1,438 places (about 54%), the place-level script and data were never committed so it cannot be rerun offline, and three disagreements are undiagnosed. Brief for another agent: `analysis/education_validation_brief_2026-11-03.md`. |
| Unsourced parameters listed as TODO with a range or "unknown" | Done with gaps | Weight, level weights, radii, cap and pool average have measured ranges. Nearest-3, the 15 mi fallback and the hamlet 25%/50% rule have no range ("unknown", not tested). |

## Level 3 (Sourced)

Not met and not a gate. Only the radius ratio (NHTS 2017) and the 2015-16 zone fallback comparison are sourced.

## Proposed level for sign-off

Level 1. Level 2 stays open on one item (independent validation), which another agent should run per the brief, since the adoption draft says the builder does not grade their own work. Accepted TODOs to list at sign-off: weight, level weights, base radii, nearest-3, 3 mi cap, 15 mi fallback, pool average, hamlet rule, pin-flag cutoff.

## One decision for you

The `urban_core` vs `urban_residential` radius mismatch is a scoring-adjacent code defect. Options: (a) leave it and keep it documented, since the radius barely moves scores; (b) key the radius on nothing (one radius for all) or fix the label; either changes about 30 places by a small amount and needs your approval and an all-places run first. I recommend (a) for now, recorded as a known defect.
