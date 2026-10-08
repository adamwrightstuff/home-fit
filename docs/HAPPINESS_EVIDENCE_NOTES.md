# Happiness index: evidence notes and findings (October 2026)

Reference record of what we tested and what the research says, so the weighting decisions can be traced later. Companion to `HAPPINESS_WEIGHTS_PROPOSAL.md`. Research findings below come from search summaries, not full-text reads of every paper; verify against the primary source before citing in product copy.

## 1. What we tested on our own data

### 1a. County commute calibration (v1, v2)
- Scripts: `scripts/baselines/build_commute_calibration.py` (v1), `build_commute_calibration_v2.py`. Results: `data/commute_calibration.json`, `data/commute_calibration_v2.json`. Tests: `tests/test_commute_calibration_v2.py`.
- Method: CDC PLACES age-adjusted county outcomes (frequent mental distress, depression, short sleep) against ACS commute exposures, with controls and state fixed effects, population-weighted. v2 used cumulative shares (30+, 45+, 60+ minutes) and mean commute minutes, strengthened controls (population, density, home value, income and income squared, renter share, 65+ share), leave-one-Census-region-out refits and a 500-resample state-clustered bootstrap.
- Result: no usable commute curve. Longer-commute counties had LOWER distress and depression (more short sleep only), and owner burden stayed strongly negative (about -4 and -16 points). County fits pick up wealth and place type, not commute harm. The joint fit of the three shares zigzagged in sign again.
- Conclusion: county data cannot support a data-derived commute curve.

### 1b. Catalog pillar scores against PLACES ZIP outcomes
- Script: `scripts/baselines/pillar_vs_places_check.py`. 366 places in 3 metros (NYC, LA, SF), PLACES ZCTA crude prevalence (age-adjusted is not published at ZIP level), controls from the status-signal breakdown, metro fixed effects, leave-one-metro-out and ZIP-clustered bootstrap.
- Protective and stable (same sign leaving out each metro, interval excludes zero): community safety in all three outcomes (about -0.9 points per standard deviation); quality education, natural beauty, housing value, social fabric and diversity in two outcomes each.
- Stable but harmful-signed, read as urban-density confounding: public transit, neighborhood amenities, air travel.
- Unstable: climate risk (sign flips), economic opportunity (sign flips), active outdoors and healthcare (at most one outcome).
- Limits: three metros only, ZIP estimates are model-based from demographics (partly circular with affluence), crude not age-adjusted. The education result contradicts individual-level evidence, so it is treated as an affluence proxy.

## 2. Individual-level research, by topic

Commute:
- Stutzer and Frey 2008 (German panel): +18 minutes lowered life satisfaction by about 0.09 on a 10-point scale. [paper](https://wwz.unibas.ch/fileadmin/user_upload/wwz/00_Professuren/Stutzer_Politische_Oekonomie/Publications/Stutzer_Frey_CommutingStress_SJEa.pdf)
- Roberts et al. 2011 (British panel): no effect in fixed-effects models. [paper](https://eprints.whiterose.ac.uk/81608/1/WRRO_81608.pdf)
- Dickerson, Hole and Munford 2014: no general evidence that longer commutes lower wellbeing. [abstract](https://ideas.repec.org:443/a/eee/regeco/v49y2014icp321-329.html)
- Clark et al. 2020 (English panel, 26,000 workers): lower leisure and job satisfaction, more strain, worse GHQ mental health, but not lower life satisfaction unless the commute persisted all six waves. [paper](https://eprints.whiterose.ac.uk/id/eprint/144512/)
- Meta-analysis of 26 studies (conference poster): r = -0.13 with life satisfaction. [summary](https://www.iser.essex.ac.uk/?p=221568)
- Milner et al. (Australian HILDA, fixed effects): small mental-health decline with more weekly commute hours. [abstract](https://findanexpert.unimelb.edu.au/scholarlywork/1227746-time-spent-commuting-to-work-and-mental-health--evidence-from-13-waves-of-an-australian-cohort-study)
- Kahneman et al. 2004 day reconstruction: commuting is the least enjoyable daily activity. [summary](https://www.sciencedaily.com/releases/2004/12/041203082806.htm)
- Verdict: small mood and leisure cost; contested effect on overall life satisfaction. Commute is also a personal score (distance to the user's workplace), not a property of a place.

Green space and outdoors:
- Alcock et al. 2014 (British panel, movers): moving to greener areas improved mental health in all three following years. [abstract](https://ore.exeter.ac.uk/repository/handle/10871/15080)
- White et al. 2019 (19,806 people, cross-sectional): 120+ minutes per week in nature goes with good health and wellbeing, peaking at 200-300. [summary](https://www.physiciansweekly.com/?p=109382)
- Schuch et al. 2018 (49 cohorts): high physical activity, adjusted odds ratio 0.83 for incident depression; exercise also treats depression in trials. [summary](https://www.kcl.ac.uk/news/engaging-in-physical-activity-decreases-peoples-chance-of-developing-depression-2)

Social ties:
- Helliwell and Putnam 2004. [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC1693420)
- Helliwell and Barrington-Leigh 2010, "How much is social capital worth?" [paper](https://www.nber.org/system/files/working_papers/w16025/w16025.pdf)
- Harvard Study of Adult Development (since 1938): relationship quality predicts happiness and health better than income, class or IQ; observational. [Harvard Gazette](https://news.harvard.edu/Gazette/Story/2023/02/Work-Out-Daily-Ok-But-How-Socially-Fit-Are-You/)

Safety:
- Victimization lowers trust and neighborhood satisfaction; effect on life satisfaction inconsistent, mostly recovers within about 18 months. [panel study](https://link.springer.com/article/10.1007/s10940-019-09445-6)
- Perceived safety and neighbor trust associated with life satisfaction (smaller cross-sectional studies; no study found that ranks safety against other neighborhood factors). [Chilean adolescents](https://repositorio.udd.cl/items/661db261-eb50-494b-8944-207bd0ab96be/full), [Statistics Canada](https://www150.statcan.gc.ca/n1/en/pub/11-627-m/11-627-m2023022-eng.pdf)
- Moving to Opportunity (randomized): mental-health effects of leaving high-poverty areas, different for boys and girls. [summary](https://www.calhealthreport.org/2014/03/10/moving-out-of-high-poverty-affects-the-mental-health-of-boys-and-girls-differently/)

Housing:
- Korean fixed-effects panels: housing cost burden raises depressive symptoms; leaving burden reduces them; stronger for renters. [Korea Univ.](https://pure.korea.ac.kr/en/publications/transitions-into-and-out-of-housing-cost-burden-and-their-asymmet/), [PolyU](https://research.polyu.edu.hk/en/publications/housing-cost-burden-and-material-hardship-among-older-adults-how-/)
- Australian HILDA: renters in housing stress lose mental health; little effect for owners with a mortgage.
- Space per person goes with better mental health (British and Chinese studies, mostly cross-sectional; association disappears in one Chinese study once perceived stress is controlled). [Foye](https://discovery.ucl.ac.uk/id/eprint/10078469/)

Economic:
- Unemployment lowers life satisfaction about as much as widowhood, persistently; scarring debated. [Eberl et al. 2022 and related](https://www.cesifo.org/DocDL/cesifo1_wp4784.pdf)
- Life satisfaction rises with log income; Killingsworth, Kahneman and Mellers 2023 reconcile the "plateau" as true only for the least happy 20%. [PNAS 120, e2208661120]
- These are individual-level results; our pillar measures reachable jobs and market quality for a place, so the support is indirect.

Climate and air:
- PM2.5 lowers life satisfaction, about 45% of it through health (UK Understanding Society, ~59,500 people). [paper](https://research-portal.st-andrews.ac.uk/en/publications/air-pollution-reduces-the-individuals-life-satisfaction-through-h/)
- Luechinger 2009 (German panel, SO2): pollution lowers wellbeing. [DIW](https://www.diw.de/de/diw_01.c.775322.de/s_5412.html)
- Extreme heat: incidence rate ratio 1.08 for mental-health emergency visits (JAMA Psychiatry, 2,775 US counties). [paper](https://jamanetwork.com/journals/jamapsychiatry/fullarticle/2789481)

Amenities and walkability:
- Moving to a more walkable area raises walking (2.1 million smartphone users). [study](https://www.frontiersin.org/articles/10.3389/fpubh.2022.1116691/pdf)
- Walkable neighborhoods go with higher life satisfaction cross-sectionally; relocation evidence shows wellbeing gains mainly when the move changes neighborhood type, with no walkability-specific effect found. [England panel](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10929527/)

Education and schools:
- Causal (instrumental-variable) evidence finds essentially no effect of years of schooling on life satisfaction. [IZA DP 16454](https://docs.iza.org/dp16454.pdf)
- No study found on school quality and parents' wellbeing. Treat schools as a family setting, not a general weight.

Diversity:
- Sturgis et al. 2011 (Britain, ~25,000): no link between neighborhood diversity and generalized trust; trivial effect on strategic trust. [IDEAS](https://ideas.repec.org/a/cup/bjposi/v41y2011i01p57-82_00.html)
- Dinesen, Schaeffer and Sønderskov 2020 meta-analysis exists; findings not confirmed in our search.

Healthcare access:
- Access goes with self-rated health; no study found linking distance to care with life satisfaction. [China older adults](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6679116/)

Air travel access:
- Aircraft noise under flight paths lowers wellbeing (Berlin panel-based study); simple distance to an airport shows no correlation. No evidence found that airport access raises residential wellbeing. [DIW](https://www.diw.de/de/diw_01.c.767630.de/s_8812.html)

## 3. Corrections made along the way

- An outside analysis claimed commute is a "massive" and "reliable" destroyer of life satisfaction; the careful panels and meta-analysis do not support that.
- It also rated amenities "high impact" and safety the "strongest predictor"; the first has no wellbeing study behind it and the second was not verified as a ranking, though our catalog data does rank safety first.
- Social Connection ("Social proximity") and Commute Time are personal, client-side scores (closeness to people the user knows; time to the user's workplace), not scores of the place, and are excluded from the general index.
- Economic Security pillar measures reachable jobs and market quality, not residents' income or job security.

## 3b. Outside proposal reviewed (five-pillar index, weights 35/30/20/15)

Taken: housing as financial strain (cost-to-income, renter burden, evictions) instead of square footage; noise from flight paths and highways as a penalty. Not taken: omission of green space (strong panel evidence, stable in our catalog check); 15% for daily friction (commute and walkable amenities have weak individual-level support and bring back urban-density bias); the "nothing else matters" framing for safety and air quality, which is a judgment, not a finding. Inputs it names that HomeFit does not have: lighting density, neighborhood trust surveys, eviction rates, noise maps. Third-place density as the core of social fabric is plausible but we did not verify the evidence.

## 4. Open questions

- Individual-level evidence for school quality, amenities and walkability on life satisfaction, healthcare distance, and a ranking of neighborhood factors in a national panel (Understanding Society, SOEP, HILDA).
- Data sources for noise (flight path and highway maps) and eviction rates.
- Whether Active Outdoors and Natural Beauty double count (both read parks, canopy, water).
- Verify the key papers' effect sizes at source before any public claim.
