# Education P4 research pass: sources and ranges (2026-10-26)

Method: one standard web search per topic, read from search summaries only, not the full papers. "Not seen" means the figure came from a secondary summary. Tiers: 1 published study, 2 revealed-preference proxy, 3 survey. A number with no source stays a TODO; nothing below is invented. Stored-data tests use origin/main (commit 21497d8), offline.

## Summary

Two things got a source: the construct (the market prices test-score levels, not value-added) and the elementary-to-middle-to-high radius ratio. Nothing sourced the weight, the equal level weights, the nearest-3 rule or the pool average, so those get a recorded sensitivity range instead. One finding cuts against the owner decision of an equal weight for everyone: the only survey evidence found says school quality matters far more to households with children.

## By parameter

| Parameter | What the sources say | Tier | What it supports | Recorded range or action |
|---|---|---|---|---|
| Construct: test-score level, not growth | Imberman and Lovenheim (2016, Journal of Urban Economics, LA): test-score levels are capitalized into home prices, school and teacher value-added rankings are not. Not seen: full paper. | 2 | Scoring the level of test results matches what buyers pay for, in one city. | Closes the "level versus growth" TODO for P2, with the caveat of a single city. |
| Frame: relative standing | Price premium of about 1 to 3% per standard deviation of school quality (a consensus figure in a 2018 Collateral Analytics report), about 3% per SD (Machin 2011 review, via a secondary summary), 2 to 5% in older test-score-only studies (an MSU summary), about 3% in Helsinki. Not seen: Black 1999 and Bayer, Ferreira and McMillan 2007 coefficients (the search did not return them). | 2 | Prices move with standardized score rank, which supports a relative scale. | Already recorded. The premium is a price effect, not a weight. |
| Education weight 7.69% | No study gives a weight in a composite. NAR 2019 "Moving with Kids" (reported secondhand, 50 to 53% of buyers with children say school district quality shaped their neighborhood choice, against 10 to 11% of buyers without children; the figures differ across outlets). | 3 | Survey evidence that importance depends on whether the household has children. It does not give a number for the default weight. | No sourced number. Test range for sensitivity: 0 to 2 times the current weight, a judgment. Weight 0 moves composite totals a mean 1.6 points (earlier test, approximate). Open conflict with the owner decision "everyone equally": see below. |
| Equal weighting of elementary, middle, high | Mixed. Collateral Analytics: elementary may matter more than high school. Durham NC student paper: larger effect at elementary and middle than high school. Wuhan: junior high larger. Montgomery County PA (Philadelphia Fed): buyers judged quality at district level, and high school results survived the boundary test while elementary did not. | 2 | No consistent basis for any specific unequal weights; direction varies by place. | Equal weights stay a judgment. Stored-data sensitivity for 1,347 places with all three levels: elementary doubled changes the score a mean 2.5 points (p95 7.3, max 13.1); high school doubled a mean 2.5 (p95 7.9, max 16.0); elementary and middle doubled a mean 2.0 (p95 6.3); elementary only a mean 9.8 (p95 29.1, max 52.4). |
| Radii by level: 2.1 / 3.2 / 3.6 miles | PBIC brief on the 2017 NHTS: median distance to school 2.7 miles overall, elementary 2.1, middle 3.2, high 3.6 (re-confirmed in this search). | 1 | The ratio between levels. The medians are the distance children actually travel to the school they attend, not a "reachable" radius. | Ratio stays sourced. The base radii by area type (1.5, 2.0, 3.0 miles) are still unsourced; NHTS gives national medians, not area-type medians (none found). |
| Radius, nearest-3, 3 mile cap, 15 mile fallback | No source found. | none | n/a | These only act where no zone map covers the point: 366 of 1,476 places (25%) have at least one level scored this way. Test the scores across a range of radii on those places before changing anything. |
| Choice pool average (lottery districts) | No source found. | none | n/a | Applies to SF and some NYC levels (about 126 places with at least one pooled level in the earlier count). Document as a judgment. |
| Early-education points | No source found for a size. | none | n/a | Stays 0 points. Access recorded as data. |

## What this means for the owner decisions of 2026-10-26

1. Equal weight for everyone: the NAR survey (tier 3, not read in full) says about half of buyers with children cite school district quality versus about one in ten without. That points to a household-dependent weight, not an equal one. It does not give a default number, so any lower default would also be a judgment. The owner may keep the equal weight as recorded judgment.
2. Level weights, radii and pools stay judgment with recorded sensitivity.

## Honest limits

Search summaries only. Black 1999 and Bayer, Ferreira and McMillan 2007 were not retrieved. The Durham and Fremont figures come from student and secondary papers and I would not rely on them for a coefficient. Elasticities are region-specific. No source was found for how much of an overall "livability" score schools should carry.

## Sources

- Imberman and Lovenheim, NBER w19157: https://www.nber.org/papers/w19157
- PBIC InfoBrief on NHTS 2017: https://www.pedbikeinfo.org/cms/downloads/PBIC_InfoBrief_NHTS.pdf
- Collateral Analytics, housing values and school quality (2018): https://www.collateralanalytics.com/housing-values-school-quality/
- Philadelphia Fed, capitalization of the quality of local public schools: https://www.philadelphiafed.org/the-economy/capitalization-of-the-quality-of-local-public-schools
- MSU summary of Imberman and Lovenheim: https://education.msu.edu/news/2015/09/new-school-evaluation-method-fails-to-affect-housing-prices
- NAR "Moving with Kids" coverage: https://ace.rismedia.com/2019/08/13/homebuyers-kids-schools/
