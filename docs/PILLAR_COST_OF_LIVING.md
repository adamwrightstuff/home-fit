# Pillar Deep-Dive: Cost of Living

How `pillars/cost_of_living.py` scores a household in a place.

**Status:** built and scored offline; NOT wired into catalog totals, the live API, or the
frontend. Offline output: `data/cost_of_living_scores.jsonl`.

## What it measures
The non-housing cost burden: income tax plus groceries, as a share of household income.
Housing is excluded on purpose (see `PILLAR_HOUSING_VALUE.md`), and so are other costs we
could not source reliably (below). High score = lighter burden. It is a price-and-tax-law
axis, not a measure of how wealthy a place is.

## Inputs
- **Household income.** If the caller gives one (a user's profile), that income is used.
  **If no income is given, the pillar prices the US median household ($78,538, ACS 2023)**
  and the result says so (`income_basis: "us_median_reference"`; a supplied income shows
  `"caller"`). A place's own median income is deliberately never used: groceries are a fixed
  dollar amount, so a place-income denominator turns the score into an income ranking and
  repeats economic_opportunity and status_signal.
- **State income tax** at that income, married filing jointly, from the Tax Foundation 2026
  brackets (`data/cost_of_living_state_tax.json`, hand-entered; re-verify a state before
  relying on it alone). City income tax is added where we have a citable rate: NYC (3.8%),
  Philadelphia (3.75%), Yonkers (16.75% of state tax).
- **Groceries:** US average food-at-home spend ($6,224, BLS Consumer Expenditure Survey 2024)
  times BEA's Regional Price Parity for goods in the place's metro (US = 100; state value
  when the metro is unknown, with lower confidence). The BEA goods index bundles food with
  other goods, so it is a proxy for grocery prices, not a measure of them.

## Scoring
1. `burden = (state tax + city tax + grocery cost) / income`.
2. Price the same household in every US place (about 10,000 places of 2,500+ people, grouped
   by state and city-tax jurisdiction, population-weighted) and take the 5th and 95th
   percentile burden at that income.
3. `score = 100 x (p95 - burden) / (p95 - p5)`, clipped to 0-100. Linear, so a small price
   gap is a small score gap. The 5th/95th anchors are a judgment call, not derived from
   research; they are exposed in the breakdown (`burden_best_anchor_pct`,
   `burden_worst_anchor_pct`).

The reference distribution is recomputed for the household's income, so the score always
means "versus other US places, for a household like yours". Higher incomes shift scores in
steep-bracket states (California) and barely at all in flat or zero-tax states.

## What varies, and what does not
Taxes vary by state and a few cities; grocery prices vary by metro. Towns in the same metro,
state and city score identically. This pillar separates metros, states and some cities, not
neighbouring towns (the same property economic_opportunity has, which is accepted there).

## Not covered (known gaps)
- **Property tax:** the Census median is top-coded at $10,001; 17% of catalog places hit it,
  all in the wealthy suburbs, so the figure would understate cost exactly there.
- **Childcare:** the Labor Department county data has no values for Pennsylvania, Indiana or
  Connecticut and one repeated value for all seven Houston counties.
- **Transportation, car insurance, health insurance:** no reliable free national source.
- **Sales tax; local income taxes** outside NYC, Philadelphia and Yonkers (Pennsylvania
  suburban earned-income taxes, Maryland and Indiana county taxes, Delaware).
- **Grocery prices below metro level.** Feeding America's county meal-cost data exists but is
  only available through a request form, so it cannot be refreshed by script.

## Data and refresh
| File | Built by |
|---|---|
| `data/cost_of_living_state_tax.json` | hand-entered from Tax Foundation (yearly) |
| `data/cost_of_living_bea_goods_rpp.json` | `scripts/baselines/build_cost_of_living_national_scale.py` (BEA MARPP/SARPP, yearly) |
| `data/cost_of_living_national_scale.json` | same script (needs `CENSUS_API_KEY`) |
| `data/cost_of_living_scores.jsonl` | `scripts/catalog/compute_cost_of_living.py` |

```bash
cd /Users/adamwright/Dev/home-fit
set -a && . ./.env && set +a
PYTHONPATH=. python3 scripts/baselines/build_cost_of_living_national_scale.py
PYTHONPATH=. python3 scripts/catalog/compute_cost_of_living.py
```

The catalog script maps each catalog metro to one BEA metro (Connecticut places in the NYC
catalog use Bridgeport-Stamford-Danbury, which BEA prices separately). Places elsewhere in a
catalog's wider region are priced at the catalog metro's level, which is approximate.

## Validation
`tests/test_cost_of_living.py` checks state tax against hand calculations (PA, IL, NY, no-tax
states), monotonic tax in income, the NYC metro goods index against the FRED value read
independently (110.261 for 2024), the no-income default, city-tax effect, independence from
place income, anchor ordering, and degraded output on missing inputs. There is no
human-rating rank correlation (the principles' primary check) because there are no human
ratings of cost of living.

## Before wiring into totals (open decisions)
- Weight: at equal weight (1/14), place totals moved from -5.6 to +3.2 (median -1.4) at the
  median income; NYC 71.5 to 67.9, Chicago 67.1 to 64.1, Austin 63.6 to 66.2.
- Live API needs a metro lookup per address to get the grocery price.
- The Explorer needs the same income personalization as housing_value (see
  LIVE_SCORER_VS_EXPLORER.md).

## Gotchas
- A low score at low incomes in a flat-tax state (Chicago at $40k) is the fixed grocery
  dollars plus a flat tax, not bad data.
- Rank among cost-of-living scores is mostly state tax law; groceries move it only a few
  points.
