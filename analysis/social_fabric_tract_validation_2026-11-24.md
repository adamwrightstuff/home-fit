# Social Fabric at census-tract scale (2026-11-24, offline, nothing in scoring changed)

Script: `/tmp/claude-0/-home-user-home-fit/8e58f870-675d-5e0a-9287-bb5eddc329b2/scratchpad/tract.py`. Outcome: CDC PLACES census-tract data, 2025 release (data.cdc.gov cwsq-ngmh, BRFSS data year 2023), LONELINESS and EMOTIONSPT, crude prevalence, 60,419 tracts. Downloaded to the scratchpad, not committed. Values are modeled from survey responses and census demographics. Places are matched to the nearest tract centroid within 3 km (602 places with all components).

## Carroll Gardens at tract scale (16 tracts within 1.2 km of the catalog point)

Lack of social and emotional support ranges from 20.2% to 37.8%, loneliness from 29.4% to 42.2%. The five tracts within 0.5 km of the point (36047006500, 006300, 005100, 006700, 007700) sit at 20.2% to 21.5% lack of support and 29.4% to 30.6% loneliness. The highest tract (36047008500, 6,673 people, southwest of the point toward Red Hook, 37.8% and 42.2%) pulls the ZIP-wide 24.7% / 32.7% up. Medians within about 1.2 to 2.5 km: Carroll Gardens 21.6% / 30.6%, Pelham 23.5% / 32.0%, Larchmont 20.2% / 29.3%, Bronxville 18.7% / 27.7%. So the core Carroll Gardens tracts look similar to Pelham and Larchmont on these modeled measures, and the ZIP-level figure understated them.

## Pillar and components against tract-level felt connection (Spearman, income-partial in brackets)

| Measure | Lack of support | Loneliness |
|---|---|---|
| income | 0.625 (-0.050) | 0.556 (-0.073) |
| v20 pillar | 0.579 (0.373) | 0.504 (0.296) |
| v18 pillar | 0.573 (0.370) | 0.490 (0.281) |
| economic connectedness (ZIP) | 0.589 (0.303) | 0.506 (0.223) |
| participation (ZIP) | 0.452 (0.368) | 0.359 (0.253) |
| cohesion (ZIP) | 0.213 (0.065) | 0.206 (0.075) |
| rootedness (tract tenure) | -0.004 (-0.005) | 0.157 (0.189) |
| civic nodes (OSM) | 0.106 (0.080) | -0.015 (-0.064) |

urban_residential only (n = 119): civic nodes 0.402 (0.222) and 0.280 (0.087); economic connectedness 0.630 (0.407) and 0.401 (0.109); participation 0.325 (0.288) and 0.319 (0.271); cohesion 0.369 (0.352) and 0.133 (0.037); rootedness -0.137 (0.076) and 0.037 (0.253).

Median spread of lack of support across tracts within 1.2 km of a place is 2.1 points, against a between-place standard deviation of 5.2.

## Reading

The v20 pillar is marginally better than v18 at tract scale. The civic-node null that led to weight 0 holds across all area types but not in urban_residential, where civic nodes correlate 0.40 and 0.28 with felt connection. v20 gave civic spots weight 0 for every area type, which may be wrong for urban places; this has not been tested with held-out metros. Limits: modeled outcome, nearest-tract matching, and the Atlas inputs remain ZIP-level.

## Follow-up: restoring civic spots for urban_residential only (tested, not adopted)

Script: `/tmp/claude-0/-home-user-home-fit/8e58f870-675d-5e0a-9287-bb5eddc329b2/scratchpad/civic_test.py`. 119 urban_residential places (NYC 67, Chicago 27, Boston 14, six others 11), tract-level PLACES outcome. Civic weight 0 to 0.16 with the other weights scaled: Spearman with lack of support 0.588 / 0.593 / 0.595 / 0.597 / 0.592 and with loneliness 0.437 / 0.437 / 0.438 / 0.439 / 0.434. Choosing the weight on the other metros and testing on the held-out one: +0.608 vs +0.588 (support, bootstrap 95% interval for the difference -0.004 to +0.048) and +0.441 vs +0.437 (loneliness, -0.054 to +0.064). A fixed 0.08 against 0: +0.006 (-0.012 to +0.025) and +0.002 (-0.019 to +0.023). Civic spots on their own correlate 0.57 with lack of support within NYC, 0.34 in Chicago and 0.33 in Boston. Every interval includes zero: no evidence that restoring civic spots helps or hurts, and the sample is dominated by New York. Restoring 0.04 of weight would add about 2 points to Carroll Gardens; v20 stays as is.
