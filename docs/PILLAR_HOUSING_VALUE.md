# Pillar Deep-Dive: Housing Value

How `pillars/housing_value.py` scores a location.

## What it measures
Housing **value** — affordability, space you get, and cost efficiency — NOT desirability.
Expensive areas score *low* here (low affordability); that's by design.

## Inputs & model
- Home-value data (Zillow ZHVI by ZIP) + local cost/space signals.
- Area-type **fallback scores** when granular data is missing (`fallback_scores` keyed by
  area_type — urban_core / urban_residential / suburban / ...), so a place without ZHVI still
  gets a sensible bucketed value rather than a gap.

## Reading the score
- Low housing_value = expensive / low affordability (Manhattan, Stamford). High = affordable.
- Optional **household-income personalization**: the Explorer applies `applyUserIncomeToScore`
  client-side so the affordability reads relative to the user's income; the live API has the
  equivalent server-side. (Another Live/Explorer transform — see LIVE_SCORER_VS_EXPLORER.)

## Gotcha
- Don't read low housing_value as "bad place" — it means costly. It's an affordability axis,
  intentionally inverse to price.
