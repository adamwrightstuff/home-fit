# Diversity: a preference, not a pillar

Status 2026-10-28 (owner decisions). Diversity is no longer a scored pillar. It is an opt-in life-stage preference plus a
neutral description. `pillar_registry.py` lists it under `FILTER_PILLARS`, not `SCORED_PILLARS` (12 scored pillars).

## Why
No evidence supports "more diverse is better" (maximum entropy, equal thirds). The age term and equal weights had no source, income
overlapped with class and housing cost, and cohesion evidence is mixed. The old entropy headline (mean of race, income and age
entropy) is retired. Nothing filters, ranks, scores or displays by race or income.

## What it does now
- **Life-stage preference.** `diversity_preference` is a list of `children`, `working_age`, `older`. A place scores the percentile of
  its share of that age cohort among US tracts (`data/age_share_percentiles.json`, ACS 2022, tracts with 500+ residents), averaged over the
  chosen cohorts. No preference means no score and no contribution (default weight 0, `parse_token_allocation`). The weight is the user's
  (None, Low, Medium, High; choosing a cohort sets Medium).
- **One setting.** The catalog "Life stage" filter and the search options use the same saved value
  (`homefit_search_options.diversity_preference`). The catalog filter keeps places in the top third of US tracts (percentile 67 or more)
  for any chosen cohort.
- **Neutral description.** Neighborhood pages show the age mix (under 18, 18 to 64, 65 and over) with no score.
- **Data kept.** Each catalog record keeps `diversity.raw_shares` (race and Hispanic origin, 16 income brackets, age, geography, total
  population), `diversity.age_percentiles`, the legacy entropy fields, and the education and self-employment values status signal reads.

## Geography
Place data unless the place has more than 200,000 adults (unsourced), then the tract. A failed place lookup or fetch is no data, not a
silent fall back to the tract (2026-10-28). Each live record stores `measured_area` (geography and total population). Catalog geography was
identified by matching stored values to the Census cache (1,473 of 1,476 places).

## Known limits
- Age percentiles are tract-level, so pin sensitivity applies (the retired entropy headline moved a median 1.7 points and a 95th percentile of
  13.4 for a 500 m pin shift at tract-level places; pooling tracts within 0.44 mile cut that to 8.8 but is not shipped).
- The 200,000 ceiling is unsourced. ACS 2022 5-year estimates carry sampling error that is not shown.
- Catalog rewrites keyed by place name collide for same-name places (nyc Ridgewood NJ and NY); key by coordinates.
- The top-third filter cutoff is a product choice, not a sourced number.

## History (retired)
Entropy score with race (B02001, seven groups), then race plus Hispanic origin (B03002, eight groups), income over 16 brackets, age over three
buckets; weight set to 0 and removed from the weight panel, cards and pillar list. Backups are in `data/backups_diversity_*` (untracked).
Audit: `analysis/audit_diversity_d3_d5_2026-10-27.md`. Scripts: `scripts/catalog/` (identify, raw shares, age percentiles, weight zero).

## DPv2 checks for the life-stage preference (2026-10-28)
- **P6 sensitivity (500 m pin shift, 582 tract-level places, nearest-tract-center approximation).** One tract: median 2 to 4, 95th percentile
  55 to 63 percentile points (30 to 41 percent of shifts over 10). Pooled over 0.44 mile: 95th percentile about 38. Pooled over 0.87 mile
  (shipped, `AGE_POOL_RADIUS_M` = 1,400 m): median 1.5 to 3.6, 95th percentile 19 to 22, 13 to 19 percent over 10 points. Not under a
  5-point gate; a percentile scale makes that gate unreachable, so the residual is disclosed. Place-level places (the other 890) do not pool.
- **P8 all places.** 1,472 places carry `age_percentiles` (582 pooled, 890 own geography); Ybor City and the 3 no-data places are skipped.
  Top-third filter pass rates: families with kids 29 percent, working-age adults 44 percent, older adults 25 percent.
- **Live and catalog parity.** Both use the 101-point table; before pooling the live table and exact ranks differed by a mean 0.33 and a max 0.98
  percentile points. The catalog now uses the live function itself.
- **P10 launch check** (`scripts/qa/launch_check.py`): 1 FAIL (healthcare 40 percent at 100) and 21 WARN, unchanged from 2026-10-25; none involve diversity.
- **P7 independent validation:** not applicable to the score (a direct Census share, not a proxy); the race and income entropy it replaced were never validated.
- **P12 schedule:** re-run these checks when the ACS vintage or tract boundaries change, and at least once a year. Data is ACS 2022 5-year.
