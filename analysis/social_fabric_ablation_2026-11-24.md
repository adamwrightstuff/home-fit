# Social Fabric ablation check (2026-11-24, offline, nothing changed or committed)

Script: `/tmp/claude-0/-home-user-home-fit/8e58f870-675d-5e0a-9287-bb5eddc329b2/scratchpad/ablate.py` (reads stored `data/*composites_recomputed.jsonl` and `data/social_capital_zip.csv` only).

## What ran and what did not

| Check | Status |
|---|---|
| Task 1 reproduce components, correlations, effective weights | Run |
| Task 2 ablation variants | Run, against a recomputed v18 baseline |
| Task 3 (a) Atlas upward mobility, (b) CDC PLACES ZCTA, (c) income-partial | **Not run**: `county_outcomes_simple.csv` and the PLACES ZCTA file are not on disk. No variant is validated against any outcome |
| Task 4 EC scale (ZIP vs neighborhood) | Run |
| Task 5 overlap with status_signal and economic_opportunity | Run |
| Task 6 decision table | Partial: only the correlation and spread half of the pre-registered rule can be applied |
| Task 7 missing data | See end |

## Data caveat

1,475 scored places loaded from 21 metro files; 1,079 have all five components. Stored pillar scores reproduce from their stored components under v18 weights only for New York (118 of 123) and LA (63 of 67). In the other 19 metros 95% or more do not reproduce under v18 or under the pre-EC weights. Cause not found. All variants below therefore compare against a v18 blend recomputed from the stored components, not against the stored score.

## Task 1: components (n = 1,079)

| Component | Mean | SD | Nominal weight | Weight x SD | Share of total-score variance |
|---|---|---|---|---|---|
| participation | 47.9 | 10.5 | 0.48 | 5.06 | 38% |
| cohesion | 35.7 | 20.0 | 0.16 | 3.20 | 18% |
| rootedness | 91.0 | 8.0 | 0.08 | 0.64 | about 0% |
| civic nodes | 80.0 | 21.6 | 0.08 | 1.73 | 6% |
| economic connectedness | 54.9 | 20.1 | 0.20 | 4.01 | 30% |

Pairwise correlations: cohesion-EC 0.26 (urban_residential 0.43), participation-EC 0.41, rootedness-civic -0.20 (urban -0.38), participation-civic 0.24. Total correlates 0.75 with EC, 0.74 with participation, 0.56 with cohesion.

Correction to my earlier New York-only read (n = 123): participation sd is 10.5 here, not 7, and cohesion-EC is 0.26, not 0.61. The New York numbers do not generalize.

## Task 2: variants against recomputed v18

| Variant | n | Spearman | Mean abs change | p95 | Carroll G. | Pelham | Larchmont | Bronxville |
|---|---|---|---|---|---|---|---|---|
| full v18 | 1079 | 1.000 | 0 | 0 | 52.1 | 68.0 | 59.1 | 53.8 |
| drop participation | 1079 | 0.862 | 6.3 | 15.3 | 52.4 | 72.9 | 70.0 | 64.0 |
| drop cohesion | 1079 | 0.938 | 4.0 | 8.0 | 56.8 | 67.6 | 60.8 | 56.4 |
| drop rootedness | 1079 | 0.997 | 3.3 | 5.0 | 49.6 | 66.8 | 57.4 | 51.5 |
| drop civic nodes | 1079 | 0.982 | 2.6 | 4.5 | 48.0 | 66.8 | 55.5 | 50.5 |
| drop EC | 1079 | 0.915 | 3.0 | 7.1 | 54.6 | 67.9 | 56.1 | 50.7 |
| merge cohesion + EC (average, 0.36) | 1079 | 0.998 | 0.5 | 1.2 | 51.8 | 68.0 | 58.6 | 53.2 |
| participation without IRS (derived, see below) | 870 | 0.975 | 2.1 | 5.6 | 52.9 | 74.4 | 62.5 | 58.6 |

urban_residential only (n = 136): drop participation 0.83, drop cohesion 0.94, drop EC 0.94, drop rootedness 0.995, drop civic 0.99, merge 0.999.

IRS-removed variant: participation = 0.65 x engagement + 0.35 x Atlas civic score and engagement = 0.5 IRS + 0.5 volunteering, so IRS was inferred as 2 x engagement minus volunteering (volunteering recomputed from the Atlas ZIP file). Only places with the full participation mix (870 usable). The derived IRS slot has mean 47.1 and sd 10.3, which does not match the earlier audit's stored-slot sd of 3.2; the inversion rests on the stored participation_mix and may be imprecise. Treat this row as indicative.

## Task 4: economic connectedness scale

ZIP 11231 (Carroll Gardens) has ec_zip 0.795 (standard error 0.017) and nbhd_ec_zip 0.734, so the neighborhood value is lower, not higher. Neighborhood values exist for 885 of the 1,079 places (Spearman with ZIP value 0.88); Pelham, Larchmont and Bronxville have none, so 194 places would lose their value if the neighborhood field were required. It does not help Carroll Gardens.

## Task 5: overlap with other pillars (Spearman)

EC with status_signal 0.62 (n = 1,074): the largest overlap, so EC partly measures affluence. Participation with status_signal 0.23, rootedness with economic_opportunity -0.23, total with status_signal 0.45. Everything else is under 0.2 in absolute value.

## Task 6: decision under the pre-registered rule

The rule needed removal to change Spearman with outcomes (a) and (b) by under 0.02, and the component to correlate over 0.5 with another or have sd under 8. Outcomes could not be run. On the second half alone: no pair of components correlates above 0.5 (largest cohesion-EC 0.26), and rootedness sd is exactly 8.0, not under. So no component is eligible for dropping under the rule.

What the variants do show is a ranking of influence, not of validity. Rootedness and civic nodes barely move rankings (Spearman 0.997 and 0.982), merging cohesion and EC barely moves them (0.998), and participation, EC and cohesion drive the score. Rootedness and civic are also the two components closest to what Carroll Gardens residents describe, and no outcome data here says they are wrong.

## Task 7: still missing for an independent validation

Atlas county outcomes file and CDC PLACES ZCTA file (both outside the repo, re-download needs owner approval, and both share the Atlas or modeled-demographic circularity); resident-rated neighborhood social life for a set of known places; surveyed trust or loneliness at neighborhood scale; tract-level turnout and registration (both data files in the repo are empty); the cause of the stored-score mismatch outside New York and LA.
