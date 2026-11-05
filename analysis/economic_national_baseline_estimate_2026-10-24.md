# Economic security: national baseline estimate and validation proposal (2026-10-24)

Status: offline estimate only. No scorer, baseline file, or catalog value was changed. Local only, not pushed.

## What was built

A national reference distribution for the five metrics that use a mean and standard deviation baseline today (employment-to-population, establishments per 1,000 residents, net establishment entry per 1,000, industry concentration, anchored-versus-cyclical balance). Source: the same Census ACS 2022 profile and Census BDS 2022 data the pillar uses, pulled for every metropolitan and micropolitan area (873 areas with all metrics: 378 metro, 495 micro) in three wildcard API calls. Values are in `analysis/economic_cbsa_national_baseline_2026-10-24.json`.

Why: today's baselines have 120 cells with median n = 8 (78 cells under 10, smallest 3), and the file has no national block. The pooled version I estimated earlier used only 191 reference areas.

Not rebuilt: the wage, job-growth, and market-size metrics (they need BLS QCEW and OEWS pulls per area). They stay on today's hard-coded scale in this estimate. Also, `scripts/baselines/build_economic_baselines.py` is broken (it imports a module that does not exist, `data_sources.economic_opportunity_data`), so the baselines cannot be regenerated with it as is.

## Result on the 1,476 catalog places

| Reference population | Market quality mean (was 65.2, sd 10.1) | Final score mean (was 74.9, sd 7.1) | Places moving over 3 points | Rank agreement with today | Largest metro shifts |
|---|---|---|---|---|---|
| All areas, unweighted | 74.2, sd 5.2 | 78.9, sd 5.2 | 866 | 0.79 | Las Vegas +10.4, SF +9.4; NYC +0.7 |
| All areas, population-weighted | 67.0, sd 7.8 | 75.7, sd 5.7 | 607 | 0.75 | LA +5.9, SF +5.8; NYC -3.2, Chicago -3.0, Boston -2.8 |
| Metro areas only | 73.3, sd 6.0 | 78.5, sd 5.4 | 891 | 0.78 | Las Vegas +9.2, SF +9.2; NYC +0.6 |

What this says:
1. The answer depends on an arbitrary choice. Weighting by people instead of counting each area once changes the average shift from +4.0 to +0.8 and flips the sign for NYC, Boston, and Chicago. No version can be adopted from this evidence alone.
2. A national scale lifts big-metro places (they sit above the typical area) and compresses the spread of market quality from 10.1 to 5.2 to 7.8. Differences between the catalog's metros are small against the national spread.
3. Rankings reorder substantially in every version (0.75 to 0.79), so this is a real design decision, not a rounding change.

## Proposed validation outcome

Question to answer: which scoring design better predicts where people and jobs actually go?

Primary outcome (revealed preference, evidence tier 2): net domestic migration rate of each metro and micro area, 2022 to 2024, from Census Population Estimates components of change (bulk files; the 2019 API vintage does not cover later years). Predictors: market quality under (a) today's peer norm, (b) each national variant, built from 2022 data so the outcome is after the measurement.

Secondary outcome: employment growth 2022 to 2024 from BLS QCEW, tested only against the components that do not already contain growth, to avoid circularity.

Method, set before looking at results:
- Unit: all 873 areas, not only the catalog's metros.
- Control for housing cost (median rent or home value to income), since people move for cost as well as jobs.
- Score: Spearman and partial correlation, with the 873 areas split in two so the weighting is chosen on one half and tested on the other.
- Decision rule: adopt a national baseline only if it beats today's peer norm on the held-out half by a margin you set in advance; otherwise keep today's and document it as a judgment call.

Known limits: migration is also driven by climate and amenities; Population Estimates are modeled; peer-norm scores for non-catalog areas need approximate division and area-type buckets.

## What is needed from the owner

1. Approve the validation design above (outcome, controls, split, decision rule).
2. Pick the reference population before seeing the test (unweighted areas, population-weighted, or metro only), or allow the test to compare all three.

## Validation result (run 2026-10-24, offline, no catalog changes)

Data: Census Population Estimates CBSA components of change (`cbsa-est2024-alldata.csv`, 718 KB, downloaded to an isolated scratch folder) for net domestic migration July 2022 to July 2024 per 1,000 residents; ACS 2022 median home value over median household income as the housing cost control. Test score: a market-quality proxy from the five metrics with national or peer baselines (wage, job growth, and market-size metrics were not available for all areas, so they are left out).

Decision rule fixed before running: adopt a national baseline only if, on the held-out half, its partial Spearman correlation beats today's by at least 0.05 and the 95% bootstrap interval excludes zero.

Findings:
1. Today's peer baselines cannot score 235 of the 873 areas (27%), because many division by area-type cells are empty (for example East South Central rural has none). The comparison below uses the 638 areas every design could score. In the live scorer those places fall back to the hard-coded scale; that fallback is now flagged as degraded.
2. No design predicts migration. Partial Spearman correlations on all 638 areas range from -0.02 to +0.04 (today's peer norm 0.03 or -0.02 depending on how areas are bucketed; national versions 0.02 to 0.04). None is distinguishable from zero.
3. Split-half: the best national design on the tuning half (metro areas only) minus today's on the held-out half is -0.002 (interval -0.077 to +0.073) against one bucketing and +0.056 (interval -0.007 to +0.127) against the other. Verdict under the rule: KEEP today's. Over 200 random splits the national version is better in 63% of splits but reaches the 0.05 margin in only 6%.
4. The three national versions are nearly interchangeable for ranking (0.98 to 0.995 agreement), so weighting changes levels but not order. Today's design and the national ones agree at only 0.69 to 0.75, so the peer-versus-national choice is the one that matters, and this outcome cannot tell them apart.

What this does and does not show: it does not show that the peer norm is valid; it shows migration over two years cannot discriminate between these designs, partly because domestic migration in 2022 to 2024 followed housing, remote work, and Sun Belt shifts more than these labor-market measures. A correlation test also cannot validate the level or scale of scores.

Recommendation: keep today's baselines and weights, record them as an unvalidated judgment call, and do not rebuild on this evidence. Separate, smaller items: (a) fill the 235-area baseline coverage hole or document the fallback; (b) if validation of the whole pillar is still wanted, test the other 55% (job access) and the market-size metrics against an outcome they should predict, such as wage growth or employment growth, instead of migration.

## Full national baseline with restored inputs (offline estimate, 2026-10-24)

Built `analysis/economic_national_baseline_full_2026-10-24.json`: population-weighted mean and standard deviation for all 11 baseline metrics over 873 metro and micro areas (wages: 379 metro areas only, from the OEWS May 2024 workbook; job growth 2022 to 2023 and employment level from Census County Business Patterns; other metrics from ACS 2022 and BDS 2022). Not wired into the scorer; `data/economic_baselines.json` is unchanged.

Catalog effect (1,473 places, all matched to their metro or micro area): market quality mean 65.2 to 62.4 (sd 10.1 to 7.2); final economic score mean 74.8 to 73.6 (sd 7.1 to 6.2); rank agreement with today 0.765; 797 places move more than 3 points, 399 more than 5. By metro: Seattle +4.2, SF +4.8, Denver +3.5, LA +2.2; Orlando -4.5, Chicago -3.9, Dallas -3.8, NYC -3.6, Houston -3.5. The mobility part now uses job growth, business entry, and 75th percentile wages instead of business entry alone (mean 63.5, sd 10.1).

Migration validation of the full version: partial Spearman -0.057 for all 873 areas, no better than the five-metric version (-0.055), held-out difference 0.000 (95% interval -0.028 to +0.028). Single metrics point in opposite directions: business entry (+0.18) and job growth (+0.10) go with more migration, while wages (-0.36 for the 25th percentile, -0.41 for the 75th), employment ratio (-0.20), and anchored-industry share (-0.22) go with less. High-wage, high-cost metros lost domestic migrants in 2022 to 2024, so migration measures affordability-driven movement and cannot validate a level-of-opportunity score. It is not a usable validation target for this pillar.

Status: the national baseline is sourced, reproducible, and covers every area (today's regional cells have a median of 8 areas and miss 27% of areas), but it is not outcome-validated. The choice to adopt it is a judgment call.
