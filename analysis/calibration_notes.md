# Neighborhood Beauty Calibration (Offline)

Using cached baseline data we evaluated the latest tuning (area-type weights, softened canopy curve, relaxed coverage caps). The table below shows the resulting total scores after reweighting tree vs. architecture contributions; architecture scores are the cached values.

| Location | Area Type | Old Beauty | New Beauty (offline) | Change |
|----------|-----------|------------|-----------------------|--------|
| Beacon Hill Boston MA | historic_urban | 63.40 | 66.60 | +3.20 |
| Savannah GA Historic District | historic_urban | 57.50 | 60.34 | +2.84 |
| Carmel-by-the-Sea CA | suburban | 67.50 | 68.56 | +1.06 |
| Old Town Alexandria VA | historic_urban | 60.00 | 62.11 | +2.11 |
| Back Bay Boston MA | historic_urban | 59.00 | 62.64 | +3.64 |
| Park Slope Brooklyn NY | urban_residential | 97.80 | 97.80 | 0.00 |

Observations:
- The revised tree/architecture blend raises historic urban scores by roughly +3 without touching enhancers. Savanna and Back Bay now land closer to the desired 60–65 range even before any new architecture cap relief is applied.
- Suburban icons (Carmel-by-the-Sea, Larchmont) gain modestly; additional headroom will come from rerunning the architecture component with the lenient coverage caps.
- Park Slope remains near 98 because the NYC street-tree override still supplies a 50-point tree score; the softened canopy curve no longer reduces its total.
- Once the live API is responsive, rerun `/score` to confirm that the architecture recalculation (with new coverage thresholds) delivers the expected lift for low-coverage historic districts.

