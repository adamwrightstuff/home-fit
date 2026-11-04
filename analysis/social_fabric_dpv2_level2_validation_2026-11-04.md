# Social Fabric DPv2 Level 2: independent validation (2026-11-04)

Run by a session that did not build the pillar, exactly as in the brief in `docs/PILLAR_SOCIAL_FABRIC.md`. No scoring, weights, criteria or catalog files were changed.

## Result

| Criterion | n | Old Spearman | v18 Spearman | Threshold | Result |
|---|---|---|---|---|---|
| (a) Atlas absolute upward mobility, low-income origin (`kfr_pooled_pooled_p25`, county) | 1,410 of 1,476 | 0.298 | 0.426 | v18 >= 0.30 and >= old + 0.05 (gap is 0.128) | PASS |
| (b) CDC PLACES lack of social and emotional support (EMOTIONSPT, 2023, age-adjusted, sign flipped) | 856 of 1,476 | 0.225 | 0.196 | v18 >= 0.20 and >= old | FAIL |
| (c) Full catalog on both | 1,410 / 856 of 1,476 | | | all places, n reported | FAIL (b covers 58 percent) |

Partial Spearman controlling for median household income (stored place-level value, n shown):

| Outcome | n | Old partial | v18 partial | v18 raw |
|---|---|---|---|---|
| Atlas upward mobility | 1,403 | 0.199 | 0.289 | 0.426 |
| PLACES support (flipped) | 849 | 0.200 | 0.162 | 0.195 |

For reference, v18 correlates 0.527 with income on the (a) sample. So the (a) pass is not just affluence: the partial is 0.289, clearly non-zero, but about a third of the raw signal goes away with income.

## Follow-up: wider PLACES coverage (owner approved a second download)

Second file: PLACES county data, 2024 release (data.cdc.gov fu4u-a9bh, data year 2022), EMOTIONSPT and ISOLATION, age-adjusted, 1.5 MB, 2,418 counties per measure. It covers Texas, Florida, Washington, Tennessee and Kentucky, which the 2023 file lacks, but not Pennsylvania, Colorado or Oregon, which neither file has.

| PLACES variant (sign flipped) | n | Old | v18 | Result against (b) |
|---|---|---|---|---|
| EMOTIONSPT 2023 only (first run) | 856 | 0.225 | 0.196 | FAIL (below 0.20 and below old) |
| EMOTIONSPT 2022 only | 1,019 | 0.083 | 0.053 | FAIL |
| ISOLATION 2022 only | 1,019 | 0.134 | 0.064 | FAIL |
| EMOTIONSPT, 2023 value else 2022 (two data years mixed) | 1,266 | 0.219 | 0.209 | FAIL (clears 0.20, but below old by 0.010) |

Reading: no variant passes (b). The 2022 vintage correlates much more weakly with both scores, so the union is a blend of two data years with a different set of states in each; its 0.209 against 0.219 is a difference well inside noise at this n, so call it a miss on the "not lower than old" rule, not evidence of regression. Best coverage is 1,266 of 1,476 (86 percent), so (c) is still not met for (b). The partial for the union is 0.191 (old 0.202).

## Method and data

- Atlas: `county_outcomes_simple.csv` from opportunityinsights.org (1.7 MB, saved by the owner from a browser because scripted download was bot-blocked).
- PLACES: county dataset swc5-untb on data.cdc.gov, measure EMOTIONSPT, 2023, age-adjusted prevalence (727 KB, 2,300 counties).
- Join: county FIPS from the first 5 digits of the stored tract geoid where present (582 places), otherwise from the place ZIP via the county column of `data/social_capital_zip.csv` (829 places). 65 places had neither and drop out. 6 places had a ZIP-county that disagreed with the tract-county; the tract value was used.
- Old scores from `data/*.composites_recomputed.jsonl`, v18 from `analysis/dpv2_social_fabric_ec_composites/*.jsonl`, matched by place name and state. All 1,476 places matched.
- Spearman is rank correlation at county resolution (places in the same county share one outcome value). Partial is the correlation of rank residuals after regressing each rank on the income rank. Income is the stored place-level median household income, not county or tract, which is a weaker control than the brief named.
- Scripts and downloads live outside the repo tree; Python ran with `-I`.

## Verified

- (a) passes on 1,410 places across the whole catalog (96%).
- The partial for (a) is non-zero, so the pass is not recorded as "tracks affluence".
- (b) fails: 0.196 is under 0.20 and under the old score's 0.225. The gap to 0.20 is small and the sampling error at n=856 is larger than that, so this is a narrow miss, not a clear regression.

## Not verified

- (b) is not on the full catalog. The 2023 PLACES release carries this measure only for some states (for example it has no Texas, Florida, Pennsylvania, Colorado or Washington counties), so 620 places have no value. Criterion (c) is therefore not met for (b). Other PLACES years or the isolation measure may cover more states; not downloaded, needs owner approval.
- Income control is place-level, not county or tract as written in the brief.
- County resolution only; a tract-level Atlas join was not done (large download).
- Atlas and EC come from the same research group, as the brief notes. This run cannot separate that shared-method effect from real validity.

## Addendum: v19 (EC removed) check, same day

After the owner's sign-off, EC was removed and the blend set to 0.48 / 0.26 / 0.13 / 0.13. Check only, no refit. Spearman with PLACES felt support (sign flipped), pre-EC blend vs v19: EMOTIONSPT 2023 n=856 0.225 vs 0.176; mixed-year union n=1,266 0.219 vs 0.177; ISOLATION 2022 n=1,019 0.134 vs 0.134. So removing EC did not raise the felt measure and lowers it slightly on the support question (the new blend gives participation less weight, and participation tracks support best). Recorded as is; weights stay a design judgment.

## Addendum 2: ZIP-level PLACES (owner approved a third download)

File: PLACES ZCTA data, 2025 release (data.cdc.gov qnzd-25i4, data year 2023), LONELINESS and EMOTIONSPT, crude prevalence, 12 MB, 24,234 ZIP areas. Each place is joined by its own ZIP (not county), sign flipped so higher is better. n = 855 of 1,476 places (58 percent; same state gaps as before, plus ZIPs missing from the file). Spearman with each Social Fabric version:

| Measure | n | pre-EC | v18 (EC 0.20) | v19 (EC out) |
|---|---|---|---|---|
| Loneliness | 855 | 0.393 | 0.467 | 0.341 |
| Lack of social/emotional support | 855 | 0.419 | 0.540 | 0.351 |
| Partial on place median income, loneliness | 850 | 0.276 | 0.285 | 0.219 |
| Partial on place median income, support | 850 | 0.283 | 0.335 | 0.204 |

By area type (support measure): suburban 0.49 / 0.62 / 0.42, exurban 0.49 / 0.61 / 0.44, urban_residential 0.29 / 0.48 / 0.24 (pre-EC / v18 / v19). The same ordering holds for loneliness.

Reading against criterion (b) (at least 0.20 and not lower than the pre-EC score): v18 passes on both measures; v19 clears 0.20 but is below pre-EC, so it fails the "not lower" rule. This reverses the county-level finding: at ZIP resolution economic connectedness raises the felt-support match, and removing it lowers it by about 0.1 to 0.2.

Caveats: ZCTA values are model-based (survey responses modelled from census demographics), so part of any match with a score that tracks affluence is built in; the income-controlled partials stay at 0.20 to 0.34 but do not remove the demographic channel. Coverage is 58 percent, not the full catalog, so (c) is still not met. Places in the same ZIP share a value.
