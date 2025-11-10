# Neighborhood Beauty Calibration (Offline)

Using cached baseline data we evaluated the latest tuning (area-type weights, softened canopy curve, relaxed coverage caps). The table below shows the resulting total scores after reweighting tree vs. architecture contributions; architecture scores are the cached values.

| Location | Area Type | Old Beauty | New Beauty (offline) | Δ Beauty | New Architecture | Design/Form |
|----------|-----------|------------|-----------------------|---------|-------------------|-------------|
| Beacon Hill Boston MA | historic_urban | 63.40 | 65.34 | +1.94 | 36.45 | 46.2 / 13.4 |
| Savannah GA Historic District | historic_urban | 57.50 | 66.45 | +8.95 | 38.14 | 43.4 / 16.3 |
| Carmel-by-the-Sea CA | suburban | 67.50 | 89.28 | +21.78 | 43.42 | 50.0 / 15.5 |
| Larchmont NY | suburban | 63.60 | 78.75 | +15.15 | 36.97 | 40.8 / 14.5 |
| Bronxville NY | suburban | 81.80 | 99.78 | +17.98 | 42.91 | 50.0 / 14.6 |
| Park Slope Brooklyn NY | urban_residential | 97.80 | 92.12 | -5.68 | 38.43 | 46.4 / 20.8 |
| Taos NM | rural | 42.20 | 45.67 | +3.47 | 22.27 | 0.0 / 0.3 |

Observations:
- Design/Form split now surfaces why suburban icons jump: Carmel and Bronxville hit the 50-point design ceiling while form stays measured. The serenity bonus and area normalization lift them into the 90s range the user expects.
- Historic urban cores get a 2–9 point lift without losing their tight street rhythm signals; Savannah gains the most thanks to higher design and serenity scores.
- Park Slope drops slightly because the offline run lacks NYC street-tree overrides; live API runs will continue to cap the tree score at 50 via census overrides.
- Rural/exurban contexts still depend heavily on tree inputs—Taos remains low because canopy data is sparse; next iteration should explore supplementing rural architecture with context cues or dedicated serenity factors.

