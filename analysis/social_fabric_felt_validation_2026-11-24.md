# Social Fabric against measured felt connection (2026-11-24, offline, nothing in scoring changed)

Script: `/tmp/claude-0/-home-user-home-fit/8e58f870-675d-5e0a-9287-bb5eddc329b2/scratchpad/validate.py`. Outcome file: CDC PLACES ZCTA 2025 release (data.cdc.gov qnzd-25i4, data year 2023), LONELINESS and EMOTIONSPT, crude prevalence, downloaded into the scratchpad (outside the repo, not committed). Sign flipped so higher is better. Place ZIP joined to ZCTA.

## What makes this less circular, and what does not

Less circular: the outcome comes from a different source than any pillar input and was not used to choose the weights. The Atlas mobility outcome was deliberately not used (it is the same research program as the pillar's Atlas inputs; the file download also returned 404). I also test the inputs that are not Atlas-derived (tenure, OSM civic nodes, IRS nonprofits) separately, and fit weights on the outcome with whole metros held out.

Still limited: PLACES ZIP values are modeled from survey responses and census demographics, so part of any match with an affluence-linked score is built in. Income partials are reported but do not remove that channel. The outcome is ZIP-wide, so it cannot see differences between blocks inside a ZIP. No dataset in the repo measures how connected one neighborhood feels to its residents.

Sample: 612 places with all five components, income and PLACES values (117 urban_residential, 278 suburban, 160 exurban, 56 rural). Coverage is limited by states missing from PLACES.

## Whole score and components against felt connection (Spearman, flipped; income-partial in brackets)

| Measure | Lack of support | Loneliness |
|---|---|---|
| Income alone | 0.564 | 0.481 |
| v18 pillar | 0.633 (0.482) | 0.522 (0.363) |
| economic connectedness (Atlas) | 0.665 (0.472) | 0.537 (0.335) |
| participation | 0.453 (0.372) | 0.359 (0.266) |
| cohesion (Atlas) | 0.305 (0.202) | 0.275 (0.180) |
| rootedness (ACS tenure) | 0.016 (0.019) | 0.174 (0.198) |
| civic nodes (OSM) | 0.063 (0.025) | -0.064 (-0.114) |

Inputs that are not Atlas-derived (n = 425 with the IRS slot derivable): the blend of rootedness, civic nodes and IRS slot correlates 0.058 with lack of support and -0.005 with loneliness; the IRS slot alone is -0.117 and -0.179. v18 on those same places is 0.682 and 0.518.

urban_residential only (n = 117): v18 0.657 (0.590) and 0.453 (0.342); economic connectedness 0.742 and 0.409; cohesion 0.474 and 0.167; rootedness -0.139 and 0.136; civic nodes 0.349 and 0.150.

## Weights fitted on the outcome (whole metros held out)

Relative influence, fitted on rank-transformed outcomes: against lack of support, economic connectedness is about 99, participation 31, rootedness 18, cohesion 12, civic nodes 8; against loneliness, economic connectedness 79, rootedness 39, participation 28, cohesion 17, civic nodes -5. Held-out Spearman of the fitted blend: 0.643 against lack of support (v18 weights 0.633) and 0.471 against loneliness (v18 0.522). The current v18 weights do about as well as fitted weights, so this data gives no reason to change them.

## The four places, measured

| Place | ZIP | Lack of support | Loneliness | v18 pillar | Median income |
|---|---|---|---|---|---|
| Carroll Gardens | 11231 | 24.7% (better than 29% of US ZIPs) | 32.7% (better than 45%) | 52.1 | $178,041 |
| Pelham | 10803 | 18.8% (93%) | 28.3% (91%) | 68.0 | $172,692 |
| Larchmont | 10538 | 17.1% (99%) | 26.9% (97%) | 59.1 | $220,714 |
| Bronxville | 10708 | 19.4% (89%) | 29.3% (83%) | 53.8 | $206,850 |

NYC-metro urban_residential ZIPs: pillar against felt support, Spearman 0.68 (n = 67).

## Reading

The pillar as a whole does track measured felt connection (0.63 and 0.52, 0.48 and 0.36 after income), but only because of its Atlas inputs, mainly economic connectedness. Rootedness, civic nodes and IRS nonprofits show no relation to the felt measures at ZIP level, so this data cannot support them as measures of felt connection. It also cannot refute them for a specific neighborhood, because the outcome is a ZIP-wide modeled value. For ZIP 11231 the modeled felt measures are worse than the three suburbs and about average nationally, consistent with the pillar's 52, but that does not say how connected Carroll Gardens' own blocks feel.
