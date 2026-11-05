# Diversity pillar: fix proposals for approval (2026-10-24)

Status: proposals only. No code, stored scores, or catalog files have been changed. Local only, not pushed.

Evidence base: raw ACS counts pulled for 22 randomly sampled catalog places (seed 7); recomputing the current formula from those counts matched the stored race_entropy in all 22. Headline diversity = mean of race, income, and age entropy, so a race change moves the headline by one third of its size. Diversity carries about 7.7% of the composite, so a 3-point headline change is about 0.23 points of total score on average.

## Defect 1: overlapping race categories

Problem: the query counts B02001_008 (two or more races) and also its subsets _009 and _010, so multiracial residents are counted twice.

Proposal 1: drop _009 and _010 and keep _008. Six single-race groups plus one multiracial group, seven categories total. This is a data-definition correction, not a judgment call.

Expected impact (22-place sample): race entropy falls 4.4 points on average (range 0.5 to 9.2); headline falls 1.5 on average (up to 3.1); rank order nearly unchanged (Spearman 0.985). Largest drops: Tarzana, Stapleton, Round Rock, Gainey Ranch, Allandale.

Recommendation: approve. Independent of Defect 2.

## Defect 2: entropy normalized by the number of non-empty categories

Problem: the denominator is ln(count of non-empty groups), so the score is a cliff in tiny group presence. After the Defect 1 fix, 14 of 22 sampled places have fewer than 7 non-empty groups (as few as 3), so this affects most places, not edge cases.

| Option | What it does | Race change vs today (mean, range) | Headline change (mean, range) | Rank agreement with today (race / headline) |
|---|---|---|---|---|
| A: Defect 1 fix only | Keeps the non-empty-category denominator | -4.4 (-9.2 to -0.5) | -1.5 (-3.1 to -0.2) | 0.985 / 0.983 |
| B: Defect 1 fix + fixed 7-group entropy | Normalizes by ln(7) always; smooth in counts | -9.0 (-29.1 to -0.8) | -3.0 (-9.7 to -0.3) | 0.897 / 0.966 |
| C: Defect 1 fix + Simpson index scaled to 7 groups | Probability two residents differ, scaled by 1 - 1/7 | -3.5 (-22.1 to +10.1) | -1.2 (-7.4 to +3.4) | 0.916 / 0.957 |

Examples (race / headline): Seaport District, today 61.5 / 49.5, option B 32.4 / 39.8; Tarzana, today 60.3 / 76.5, option B 42.3 / 70.5; Allandale, today 46.4 / 69.5, option B 28.4 / 63.5; Morningside Heights, today 70.9 / 66.1, option B 70.1 / 65.8.

Trade-offs:
- A leaves the cliff in place. It fixes the double count only.
- B removes the cliff and is simple to explain (spread across the seven Census groups), but it scores places with few groups as less diverse, which lowers the whole pillar by about 3 headline points and cuts a few places by up to about 10.
- C is less sensitive to tiny groups but moves some places up, which is harder to explain, and has the weakest rank agreement.
- The data cannot decide between entropy and Simpson. That is a judgment call; the research on how people perceive diversity (Bruch and Mare) is about preferences by group share, not about index choice.

Recommendation: approve B. Reason: it is the only option that removes the cliff while staying close to the existing index and staying explainable. The level drop is real and should be stated in release notes.

## All-places result (dedupe + option B, 1,451 of 1,470 places, raw ACS counts pulled 2026-10-24)

Approved by owner as the fix to evaluate; no catalog change made yet.

- Race entropy: mean -8.9 points (median -8.1, 5th to 95th percentile -17.9 to -2.3, range +2.2 to -62.1).
- Diversity headline: mean -3.0 (median -2.7, 5th to 95th percentile -6.0 to -0.8). Mean 73.6 to 70.6; spread 7.8 to 8.0, so the pillar shifts down without compressing.
- Rank order: Spearman 0.972 overall for the headline (0.944 for race); within metro 0.91 to 0.99 (lowest: San Antonio, Tampa, Raleigh, Las Vegas, Miami).
- 70% of places have fewer than 7 non-empty groups; 166 places (11.4%) lose more than 5 headline points, 18 lose more than 8.
- By metro: San Antonio -4.9, Austin -4.0, Miami -3.6 largest; Seattle -1.7 and SF -2.4 smallest. By area type: rural -3.95, others about -2.8 to -3.1. By geography: tract -3.5, place -2.7.
- Largest drops are few-group tracts the old formula scored as near-perfectly diverse (Pelham Bay 92.4 to 72.0, Glendale 85.2 to 64.5, both with 2 non-empty groups and labeled rural in the NYC file).
- Data issues: 19 places returned no Census data now; 17 places (1.2%) do not reproduce their stored race entropy, mostly place-level suburbs. Likely cause (not verified): area type or geography choice changed since they were scored. Neither set is explained yet.
- Total-score effect: diversity is about 7.7% of the composite, so about 0.23 points on average.

## Related decisions not included here

- Hispanic ethnicity is not in B02001. Adding it needs table B03002 and is a bigger change to what the pillar measures.
- Geography: non-urban-core places use place or county-subdivision data while urban-core uses tract data. A single measurement-area rule needs its own proposal.
- Frame: the v2 provisional frame says diversity is preference-dependent, which may mean an opt-in or preference-weighted design instead of a single higher-is-better score.
- Age entropy rewards equal thirds of youth, prime, and seniors with no source; income entropy uses 16 brackets normalized by non-empty brackets, which has the same cliff as race.

## What implementation would require (after approval)

1. Raw ACS counts are not stored, so the fix cannot be derived from stored catalog scores. A re-pull of free Census data (three queries per place) is required, not a paid or rate-limited rescore. Roughly 1,470 places.
2. Update `get_diversity_data` category list and `_normalized_entropy` call, mirror to the TypeScript scorer and catalog per `docs/LIVE_SCORER_VS_EXPLORER.md`, and recompute composites for all 21 metro files.
3. Before adopting: all-places comparison (not only the sample), pin-shift test on a subset, health check across all metro files, and a note in the methodology copy.
4. Rollback: keep the previous diversity values in a side file before overwriting.
