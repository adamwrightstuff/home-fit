# Trajectory: research findings (2026-10-08)

Question: can Trajectory be rebuilt from leading indicators (spillover, tenure and education shifts, permits, crime) instead of trailing price? Analysis only. No scoring was changed.

## What Trajectory does today

`_classify_trajectory` in `pillars/status_signal.py` assigns a badge (Arrived, Up-and-Coming, Stable, Cooling, Declining). Its only direction input is Zillow ZIP-level 3-year appreciation (6-month velocity as fallback), gated by socioeconomic standing, renter share, and area type. Cutoffs (5% and 10%) were set by eye and have never been validated. Without Zillow data the only fallback is a stability heuristic.

## Literature check

| Claim | Verdict |
|---|---|
| Spillover from rich neighbors (Guerrieri, Hartley, Hurst, J. Public Econ. 2013) | Confirmed. Poor tracts bordering rich ones appreciate most in booms. |
| Falling crime draws affluent households (Ellen, Horn, Reed, J. Housing Econ. 2019) | Confirmed, but metro-level plus five cities. No national tract-level crime series exists for us. |
| Education and income shifts mark gentrifying tracts (Freeman 2005) | Plausible, checked only through secondary descriptions. |
| Permits as a leading indicator | Not supported. Only descriptive theses and blogs, no predictive test. |
| "Urban Institute neighborhood change model" | No such model found. Urban Institute called for early-warning systems; Steif et al. tested feasibility in 29 cities. |

## Data reality

The catalog stores one 2022 ACS snapshot per place, no tract IDs, no neighbor data, and no earlier vintages. Any leading-indicator build needs fresh Census pulls. Permits and crime deltas are not available nationally.

## Backtest

Design: ACS 5-year windows 2012, 2017, 2022 (non-overlapping), tracts with identical IDs across all three. Predictors from 2012 to 2017 plus 2017 spillover (gap between a tract's income and the 80th percentile of tracts within 2 miles). Outcome: 2017 to 2022 change in relative income, college share, and relative home value. 13 metros, about 12,000 tracts. Leave-one-metro-out, out-of-sample.

Results:

- Spillover gap correlates positively with later income gain in all 13 metros (rank correlation 0.21 to 0.37, median 0.30), including in lower-income tracts alone.
- Incremental value is small. Adding spillover to a model that already knows current relative income and college share raised out-of-sample R² on income change from 0.134 to 0.143.
- Prior price change does not predict income change. It does help predict later home-value change (R² 0.090 to 0.128, 11 of 13 metros).
- Prior education and income shifts have negative coefficients (reversal), partly a shared-endpoint artifact of ACS noise. Not usable as momentum. Tenure shift is noise.
- Home-value change is barely predictable from any of these signals.

Pilot (20 NYC and SF places): the new signals disagreed with the badge in plausible ways (Bay Ridge badged Up-and-Coming on price alone, Bayview badged Arrived despite large composition change), but n is too small to conclude anything.

## Limits

Tracts with top-coded income or home value are excluded, which drops some of the strongest gentrifiers. Tracts renumbered in 2020 are excluded. Only three non-overlapping ACS windows exist. Atlanta kept only 129 tracts. Backtest used tract-level ACS home values, not the Zillow ZIP series the badge runs on.

## Conclusion

Confidence in the existing badge as a forecast is low: unvalidated cutoffs, ZIP-level price as the only driver, and prior price change adds nothing for people-composition change. Spillover is real but mostly restates current income level, so it does not justify a new index. Suggested low-cost change: describe the badge as recent ZIP price change, not direction, and optionally show the spillover gap as a supporting detail.
