# Status signal class

The class label (Struggling, Working Class, Middle Class, Affluent, Elite) describes the economic standing of the
typical household in a place from **income and housing only**. Education and occupation are not part of the class.
They still feed the legacy 0-100 composite that sits beside the label.

Implementation: `_classify_class` in `pillars/status_signal.py`. Cutoffs: `class_cuts` and `class_national` in
`data/status_signal_baselines.json`, built by `scripts/baselines/build_class_cuts.py` (ACS 2022 5-year, tract level).
Places outside a built metro use the US-wide cutoffs stored under `class_cuts.all` (`build_class_cuts.py --national`), so every place with income data gets this class. The older wealth-band classifier only remains for places with no income at all.

| Class | Rule |
|---|---|
| Struggling | Median household income below the HHS poverty guideline for three ($23,030, 2022), or housing takes more than 50% of income while income is below the national median |
| Working Class | Income under two-thirds of the national median ($75,149, ACS 2022), or housing takes more than 30% of income while income is below the national median |
| Elite | Income in the metro's top 10% of households and median home value in the metro's top 10% (owner-weighted) |
| Affluent | Income in the metro's top 20% of households |
| Middle Class | Everyone else |

Housing share = 12 x median monthly housing cost (ACS B25105, renters and owners) / median household income.

Where the numbers come from, and which parts are judgment:
- Middle band (two-thirds of the national median), the 30% and 50% housing-cost thresholds, and the poverty guideline are
  published conventions (Pew income tiers, HUD cost-burden thresholds, HHS guidelines).
- The 20% Affluent share, and Elite as "top 10% on both income and home value", are product definitions, not research findings.
- The burden tests apply only below the national median so higher earners in expensive metros are not demoted.

Known limits: tract and place median income describes the typical household, not individuals; student areas can show
housing cost above income; ACS caps median income at $250,001 and median home value at $2,000,001.

Offline application to a catalog: `scripts/catalog/recompute_status_class.py --metro <metro> [--write]`.
Live scoring applies the same rule through `compute_status_signal_with_breakdown` (needs `median_monthly_housing_cost`
from `get_housing_data`).

## Trajectory

Trajectory is separate from class and describes direction of change only: Up-and-Coming, Stable, Declining.
- Declining: 3-year home price decline of more than 3%.
- Up-and-Coming: Working or Middle Class, urban, renter-heavy, with price momentum (or the stability fallback when no price history exists).
- Stable: everything else.

The former Arrived and Cooling badges were class restated (Affluent/Elite with no negative signal, or falling prices at Affluent/Elite) and were removed.
The frontend maps Arrived to Stable and Cooling to Declining (`normalizeTrajectory`) so older saved payloads and quizzes still resolve.
