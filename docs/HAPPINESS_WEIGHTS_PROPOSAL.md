# Happiness Index weight proposal (DRAFT, not applied)

Status: proposal only. No scoring code, frontend code or catalog data has been changed. Nothing here is committed.

## Why change anything

The current weights (S .30, F .20, C .15, N .05, H .10, G .12, E .08) were tuned against county-level CDC PLACES mental distress (R² 0.305). The v2 commute calibration (data/commute_calibration_v2.json) showed that county fits are confounded by wealth and place type: longer-commute counties looked *less* depressed, and owner burden came out strongly negative. Weights fitted that way are not evidence. This proposal instead ranks every pillar by the strength of individual-level evidence (people followed over time, or randomized), and gives weight only where such evidence exists. Weights are still judgment: no study can say what share a pillar deserves. Treat the numbers as an ordering with rough magnitudes.

## Evidence tiers

- Strong: fixed-effects panels or randomized evidence, effect on wellbeing or mental health.
- Moderate: consistent individual-level associations, or strong evidence on a close proxy.
- Weak: associations only, mixed results, or evidence on a different outcome.
- None: nothing found that links the pillar to individual wellbeing.

## Every pillar and datapoint

| Pillar / datapoint | In index today | Evidence | Proposed |
|---|---|---|---|
| Social fabric (stability, civic spaces, engagement) | 0.30 | Strong for ties and trust; pillar measures proxies | 0.24 |
| Economic security (jobs, mobility, resilience) | modifier only (x0.85-1.15 on social) | Strong: unemployment about as damaging as widowhood, lasting years; life satisfaction rises with log income | 0.12, and drop the modifier |
| Housing value (affordability, space; renter/owner burden inside) | 0.10 | Moderate: cost burden raises depression in fixed-effects panels, mainly for renters; space per person associated with better mental health | 0.12 |
| Natural beauty (green, tree canopy, scenery) | 0.12 | Strong-ish: moving to greener areas improved mental health; 120+ min/week nature contact | 0.09 |
| Active outdoors (parks, trails, water) | 0 | Moderate: exercise treats depression in trials; active people develop less depression (OR 0.83) | 0.08 |
| Community safety (violent, property, trend) | 0.20 | Weak-moderate: harms trust and neighborhood satisfaction; effect on life satisfaction inconsistent and mostly recovers | 0.12 |
| Climate risk (heat, air quality, flood, trend) | 0 | Moderate: PM2.5 lowers life satisfaction partly through health; extreme heat raises mental-health ER visits about 8% | 0.06 |
| Public transit: commute time | 0.15 | Weak: small drop in daily mood and leisure satisfaction; no general life-satisfaction effect in the careful panel | 0.05 |
| Public transit: stops, frequency (non-commute) | 0 | None | 0 |
| Neighborhood amenities (walkability, business districts) | 0.05 | Weak: moving to walkable places raises walking; no wellbeing outcome found | 0.05 |
| Healthcare access (hospitals, clinics, pharmacies) | 0 | Weak: access linked to self-rated health; no distance-to-life-satisfaction study | 0.03 |
| Quality education (schools) | 0.08 | Weak: causal evidence finds years of schooling has about no effect on life satisfaction; no study on school quality and parents | 0.03 |
| Diversity (race, income, age mix) | 0 | Weak/null: British multilevel study finds no link to trust; small negative in other work | 0 |
| Air travel access | 0 | None | 0 |
| Built environment | 0 | None; not a residential pillar | 0 |
| Political lean (opt-in) | 0 | None; preference, not wellbeing | 0 |
| Status signal (composite) | 0 | None; positional, not wellbeing | 0 |

Proposed weights sum to 1.00: social .24, economic .12, housing .12, safety .12, green .09, active outdoors .08, climate .06, commute .05, neighborhood .05, healthcare .03, education .03.

## Judgment calls to review

1. Economic security gains a real weight and loses its social modifier, because the modifier had no evidence behind it and unemployment is among the best-documented wellbeing effects. The pillar measures place-level job markets, not an individual's job, so keep it at 0.12, not higher.
2. Active outdoors and natural beauty overlap (parks, canopy). Combined 0.17 may double count; consider merging.
3. Education drops hardest. It matters for families with kids, but that is a user preference handled by the quiz weights, not a general happiness driver.
4. Commute stays above zero only because of the small mood and leisure effect and the worse penalty at 60+ minutes; the curve should flatten below 45 minutes.
5. Diversity, air travel, built environment, political lean and status signal stay at 0 for lack of evidence, not because they are unimportant to every user.

## Implementation notes (not done)

- pillars/happiness_index.py takes only seven pillars; adding economic security, climate risk, active outdoors and healthcare means extending its signature and the callers in main.py and the catalog scripts.
- The pillar scores are already stored in the catalog JSONL files, so recomputing the index for every cataloged place is an offline job (scripts/catalog/recompute_catalog_composites.py), not an API rescore.
- The index docstring cites "R²=0.305 vs CDC PLACES"; that claim should be removed or reworded, since it rests on the confounded county approach.
- Run the catalog health check afterwards to see how many places move and by how much before shipping.

## Sources

Commute: Stutzer and Frey 2008 (German panel, -0.09 per 18 min); Roberts et al. 2011 and Dickerson, Hole and Munford 2014 (British panels, no general effect); Clark et al. (Understanding Society); Milner et al. (HILDA). Green: Alcock et al. 2014; White et al. 2019. Social: Helliwell and Putnam 2004; Helliwell and Barrington-Leigh 2010. Safety: Springer Journal of Quantitative Criminology 2019 panel; Moving to Opportunity. Housing: Korean and Australian fixed-effects panels on cost burden; Foye 2017. Education: IZA DP 16454. Economic: Eberl et al. 2022; Killingsworth, Kahneman and Mellers 2023. Climate: UK Understanding Society PM2.5 study; JAMA Psychiatry heat study. Active outdoors: Schuch et al. 2018. Diversity: Sturgis et al. 2011. Findings come from search summaries; verify against the primary papers before citing in product copy.
