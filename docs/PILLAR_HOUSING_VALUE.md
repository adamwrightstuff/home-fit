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
- Pooled tracts (D14, 2026-10-28): the 495 catalog places whose data came from one tract are scored on the
  occupied-unit weighted pool of the tracts under the pin and an 8-point ring at 700 m (0.43 mile), the commute
  lookup's sampling (`summary.pooling`; sub-scores in the breakdown stay single-tract). Live scoring does the same
  with `HOMEFIT_HOUSING_POOLED=true` (default off). A 0.31 mile pin shift moved the single-tract score by a 95th
  percentile of 27 points and the pooled score by 12 (100 places, real geocoder, 800 shifts; median 3.8 and 1.6); about half of the large neighbor gaps were within sampling
  error. Median catalog change 4.4 points, 88 places over 10; ranks inside a metro reorder (Spearman 0.70). The
  5-point pin-shift limit (borrowed from transit, a judgment) is not met. Open: Explorer income personalization
  still rebuilds from single-tract inputs. Audit: `analysis/audit_housing_d14_2026-10-27.md` (local).

## Reading the score
- Low housing_value = expensive / low affordability (Manhattan, Stamford). High = affordable.
- Optional **household-income personalization**: the Explorer applies `applyUserIncomeToScore`
  client-side so the affordability reads relative to the user's income; the live API has the
  equivalent server-side. (Another Live/Explorer transform — see LIVE_SCORER_VS_EXPLORER.)

## Gotcha
- Don't read low housing_value as "bad place" — it means costly. It's an affordability axis,
  intentionally inverse to price.

## DPv2 spec sheet (2026-10-30)

- **Construct:** how affordable and roomy a home is for the area's own typical income (price or rent against income, rooms, rooms per dollar), not desirability. Expensive places score low by design.
- **Reference frame:** fixed standards. Evidence tier 1 for the anchors only: HUD cost burden at 30% and severe at 50% of income, Demographia price-to-income "affordable" at 3.0 and bands at 4.0 and 5.0. All point values between anchors are judgment (research 2026-10-30, Muse; quotes not independently verified).
- **Measurement area:** tract-level places use the occupied-unit weighted pool of tracts under the pin and an 8-point ring at 0.43 mile (700 m); place-level places use town data. 0.43 mile is a judgment; published anchors are 0.31 mile (pedestrian neighborhood) and 0.5 mile (transit catchment).
- **Inputs:** ACS 2022 5-year tract medians (value, income, gross rent, rooms, renter share), Zillow ZIP value where Census is capped.
- **Parameters (all recorded judgments, none sourced beyond the anchors):** weights 50/30/20; owner price-to-income and renter rent-to-income point steps; rooms steps; rooms per $100k thresholds; metro multipliers 1.3 and 1.5. Weight sensitivity (stored inputs, 1,467 places): 60/30/10 and 40/30/30 move the median place 1.8 points, none over 10, rank correlation 0.97 to 0.98; 70/20/10 moves 119 places over 10 (0.91); affordability only reorders heavily (0.64) and matches measured burden worse (0.57 against 0.67). Plausible range recorded: affordability 40 to 70, space 20 to 30, efficiency 10 to 30.
- **Known construct caveat:** value efficiency is rooms divided by price, so it reuses the space and affordability inputs; scored as a third dimension by judgment.
- **Shared inputs:** ACS tract medians are also used by diversity and social fabric.
- **Pin-shift sensitivity (0.31 mile, 8 bearings):** single tract 95th percentile 27 points (100 places, real geocoder); pooled 12. Against sampling noise (90% margins, normal draws): 11.7% of single-tract shifts exceed what noise alone would produce, 6.6% pooled (pure noise is 5%). Rank correlation between the pin and shifted pin: 0.76 single, 0.91 pooled. Gate (judgment, to be confirmed by the owner): pin swing at most about 1.5 times the sampling-noise floor; pooled meets it (1.3x), single tract fails (2.3x).
- **Independent validation:** share of households not paying 30% or more of income on housing (ACS B25070 and B25091, 495 pin tracts). Rank correlation 0.67 all places, 0.55 within metro; partial independence (same survey). Rent-to-income alone scores 0.72, price-to-income alone 0.52, so the owner price half is the weak part. Suggested further checks (Muse): severe burden, overcrowding, housing quality, vacancy, eviction filings.
- **All-places check:** 1,467 scored places rescored for weights; 495 tract-level places pooled; launch check contrast (rural above urban core) passes (gap 28.9 to 25.7).
- **Fail loud:** no income means no data; missing rooms leave space and efficiency out; no owner value leaves efficiency out and rescales (not degraded); nothing invented.
- **Known data limits:** tract medians are survey estimates (median sampling sd 5.4 points single tract, 3.3 pooled); pooled values are weighted means of tract medians, not a true pooled median; breakdown sub-scores for pooled places stay single-tract (summary.pooling holds the pooled inputs).
- **Last re-validated:** 2026-10-30. **Next re-validation:** 2027-04-30 (rerun the cost-burden validation and the pin-shift test; check for newer ACS releases).
