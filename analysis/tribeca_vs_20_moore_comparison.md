# Tribeca vs 20 Moore St — status signal comparison

Comparison of two points in the same neighborhood to show why address-level scores can differ.

## Locations

| | Tribeca (centroid) | 20 Moore St |
|---|-------------------|-------------|
| **Input** | Tribeca, NY 40.7154, -74.0093 | 20 Moore St, New York NY |
| **Coordinates** | 40.7154, -74.0093 | 40.7030, -74.0126 |
| **Zip** | 10007 | 10004 |

Different zips → almost certainly **different census tracts**. 20 Moore St is ~1.4 km south of the Tribeca centroid.

## Census tract–level data (from housing_value summary)

| Metric | Tribeca | 20 Moore St |
|--------|---------|-------------|
| Median home value | $2,000,001 | $1,796,900 |
| Median household income | $250,001 | $222,167 |
| Median rooms | 3.5 | 2.7 |
| Wealth character | unequal | typical |

## Status signal breakdown

| Component | Tribeca | 20 Moore St |
|-----------|---------|-------------|
| **wealth** | 100.0 | 100.0 |
| **home_cost** | 100.0 | 100.0 |
| **education** | 97.7 | 90.2 |
| **occupation** | 75.0 | 75.0 |
| **luxury_presence** | 62.0 | 47.5 |
| **wealth_character** | unequal | typical |
| **Status signal (total)** | **94.9** | **92.5** |

## Why the scores differ

1. **Different tract** — Different census tract (10007 vs 10004) with lower income, lower home value, and lower education % in 20 Moore St’s tract.
2. **Luxury footprint** — Different lat/lon → different nearby businesses from OSM. Tribeca centroid gets a higher luxury_presence (62 vs 47.5).
3. **Wealth character** — Tribeca tract is “unequal” (super-wealthy among very high earners); 20 Moore St’s tract is “typical” for the division. This is a QC label, not a direct score driver, but it reflects different tract income distributions.

**Note:** A local run of the current formula for 20 Moore St produced **92.5**. If you saw **72.4** on the frontend, that was likely (1) the deployed API using an older formula or cached response, or (2) a run where OSM failed and luxury_presence was 0, which would pull the score down into the 70s.
