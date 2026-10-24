# Pillar Deep-Dive: Community Safety

How `pillars/community_safety.py` scores a location (`get_community_safety_score`).

## What it measures
Crime safety from **agency-reported** rates — violent and property crimes per 1,000, scored
relative to area-type expectations, nudged by the recent trend.

## Inputs
- `get_crime_rates(lat, lon, city, state_abbr, area_type, population)` → FBI CDE
  (Crime Data Explorer), agency-level where available. `state` (2-letter) is required for CDE
  routing; population defaults to 10,000 for per-1k conversion.

## Scoring flow
1. **Rates per 1,000 people present.** Violent (murder, rape, robbery, aggravated assault) and
   property (burglary, larceny-theft, motor vehicle theft) offenses divided by residents plus
   workers for the share of the week they are at work (`data_sources/people_present.py`).
   Cities with an incident feed (NYC, LA, SF, Chicago, Philadelphia, Austin, Dallas, Boston) are
   measured in a circle around the place; everywhere else uses the police department's yearly total.
2. **Slots** (`_score_rates`): each rate becomes `100 - percentile` against the national scale
   (`data/community_safety_national_scale.json`, FBI per-agency data, population weighted).
3. **Blend:** `score = (1 - w) x violent slot + w x property slot`, with **w = 0.098**. One weight
   for every place; there is no retail-hub exception.
4. **Trend delta** (`_trend_delta`): a small +/- nudge from the recent violent-crime trend.
   `final = clamp(raw_score + trend_delta)`.

## Why property is weighted at about 10%
The weight is the property share of total harm from crime, so it is a formula with published
inputs, not a chosen number (`scripts/baselines/derive_community_safety_weight.py` writes
`data/community_safety_harm_weights.json`):

    w = H_property / (H_violent + H_property),   H = sum(national rate x cost per offense)

- **Cost per offense:** McCollister, French & Fang (2010), *The cost of crime to society*, Drug and
  Alcohol Dependence 108, Table 5 (total cost, 2008 US dollars): murder $8.98M, rape $241K,
  aggravated assault $107K, robbery $42K, burglary $6.5K, vehicle theft $10.8K, larceny $3.5K.
- **Offense rates:** BJS NIBRS-based national estimates for 2023, per 100,000 (violent 387.8,
  property 2,015.2).
- **Result:** property offenses are 5.2x as frequent as violent ones but 9.8% of total harm.

**Sensitivity (the answer depends on how murder and suffering are valued):** murder excluded 19.7%;
direct victim costs only (no pain and suffering) 29.9%, or 51.9% without murder. The previous
35% / 15% weights with an 8x retail-hub switch had no documented source; they match only the
narrowest direct-cost view. The standard in cost-benefit work is total social cost, hence 9.8%.

**Supporting research:** residents' perception of neighborhood crime tracks violent crime rates
most strongly (census-tract analysis of American Housing Survey data); Statistics Canada's Crime
Severity Index and the Cambridge Crime Harm Index also weight by seriousness (sentencing), which
ranks violent crime far above theft.

**Known limits:** costs are 2008 dollars from one study and rates are one year; the violent slot
counts offenses (murder is 1.5% of violent offenses by count but 56% of violent harm), so murder
is under-represented inside the violent slot. Re-run the derivation script when better inputs exist.

## Area of measure
For cities with an incident feed the circle is the smallest of 600, 800, 1000, 1200, 1500, 2000 m
holding at least 10,000 people (`MIN_NEIGHBORHOOD_RESIDENTS`). Tested alternatives (a minimum
radius of 800 or 1,000 m) reduce score movement when the pin moves but did not agree better with
third-party ratings, and the distance research (resident-drawn neighborhoods are smaller than a
census tract; crime effects on home prices act within about 0.1-0.25 mile) argues for the smallest
area with enough people, so 600 m stays.

## When it returns None (excluded from the composite)
The pillar deliberately returns `None` (rather than a misleading number) in three cases —
the catalog then drops it from the weight set:

| status | when | note |
|---|---|---|
| `DEGRADED` | no crime data at all | confidence 0 |
| `COMING_SOON` | jurisdiction not wired up in CDE yet | ⚠️ **coverage gap, NOT bad data** (Sleepy Hollow, Summit, Belmont Shore, Lakewood) |
| `DEGRADED` (state-aggregate) | only `fbi_cde_state` available | zero-tolerance: a state average is meaningless for one place, so it's withheld |

So a null community_safety is usually a **coverage gap**, not an error. Don't treat it as a
score of 0; the place is correctly weighted over its remaining pillars.

## Catalog / weighting
The 4 COMING_SOON places have `community_safety` weight 0; their other pillars renormalize to
sum to 100 (`repair_diversity_and_weights.py` ensured this). See CATALOG_RESCORE_RUNBOOK and
PILLAR_DATA_QUALITY.

## Gotchas
- Scores are **area-type-relative** — a low-crime urban core can score similarly to a quiet
  suburb because expectations differ; don't compare raw per-1k across area types.
- A place legitimately scoring low (Compton 6, Watts) reflects real reported crime, not a bug.
- The commuter-denominator boost relies on the LODES grid (same data as economic_security's
  job-accessibility); coverage gaps there fall back to no boost.
