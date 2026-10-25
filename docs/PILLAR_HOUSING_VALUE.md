# Pillar Deep-Dive: Housing Value

How `pillars/housing_value.py` scores a location.

## What it measures
Housing **value** — affordability, space you get, and cost efficiency — NOT desirability.
Expensive areas score *low* here (low affordability); that's by design.

## Inputs & model
- Home-value data (Zillow ZHVI by ZIP) + local cost/space signals.
- **No invented values (changed 2026-10-24).** The hard-coded area-type fallback scores (45 to 65) are gone. If
  the Census has no median household income for the tract (the ACS suppresses it in some dense rental tracts) the
  pillar has no data and drops out of the total. A missing room count leaves the space and value-efficiency
  components out; affordability plus at least one other component is required, otherwise there is no score, and a
  partial score is marked degraded. Value efficiency is 0 by the formula where there is no owner-occupied value (a
  design choice, tracker D11).
- Known weakness: city neighborhoods rest on a single tract, and adjacent tracts can differ by 20 to 40 points
  (tracker D14).

## Reading the score
- Low housing_value = expensive / low affordability (Manhattan, Stamford). High = affordable.
- Optional **household-income personalization**: the Explorer applies `applyUserIncomeToScore`
  client-side so the affordability reads relative to the user's income; the live API has the
  equivalent server-side. (Another Live/Explorer transform — see LIVE_SCORER_VS_EXPLORER.)

## Gotcha
- Don't read low housing_value as "bad place" — it means costly. It's an affordability axis,
  intentionally inverse to price.
