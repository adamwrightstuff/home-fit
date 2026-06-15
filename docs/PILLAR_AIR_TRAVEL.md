# Pillar Deep-Dive: Air Travel Access

How `pillars/air_travel_access.py` scores a location today (the commute-time band model).

## What it measures
How easily you can reach a useful airport — by **estimated drive time** to the best reachable
hub, capped by the hub's service level, with a small bonus for a genuinely separate second hub.

## Inputs
- `data_sources/static/airports.json` — 53 US commercial airports with `lat/lon`, `type`
  (large/medium), and `service_level` (international_hub / major_hub / regional_hub).
- Haversine distance to each (no routing API). Drive time is *estimated*, area-type-aware.

## Scoring flow
1. **Distance → estimated drive time** (`_drive_minutes`):
   ```
   minutes = haversine_km · ROAD_CIRCUITY(1.3) / speed_kmh · 60
   ```
   Speed by area type (denser = slower, traffic): historic_urban 34, urban_residential 40,
   suburban 52, exurban 65, rural 72 km/h.
2. **Drive time → band**, capped by service level (`_airport_band_score`):
   ```
   bands(min→score): ≤20→100, ≤35→88, ≤50→74, ≤70→58, ≤95→42, ≤120→26, else decay
   ceiling: international_hub 100, major_hub 92, regional_hub 76
   final = min(band, ceiling)
   ```
3. **Best hub wins; +bounded second-hub bonus** (`_calculate_multi_airport_score`): take the
   max single-airport score, then add up to ~7 for a *distinct* second hub reachable within
   ~60 min. Capped at 100.

## Why it was rewritten
The old model **plateaued at 100 within 25 km** of a hub AND **summed the best 3 airports**,
so in any multi-airport metro nearly everywhere maxed out — **every LA place scored exactly
100 (std 0)**, differentiating nothing while consuming a full pillar's weight. The drive-time
bands + best-hub (not sum) fixed it: LA std 0 → 11, NYC std → 22. Manhattan 98, Santa Monica
95, far exurbs (Bedford) ~42 — a real gradient.

## Catalog
`scripts/rescore_air_travel.py` recomputes offline — static airports + haversine, **no network,
deterministic**. Cascades total_score. Safe to re-run (uses the live pillar logic).

## Known limits / gotchas
- Drive time is a **straight-line estimate × circuity**, not real routing — fine for ranking,
  not turn-by-turn. A real routing API would refine traffic-heavy corridors.
- Area-type speed table is the main lever; unknown area types fall back to ~50 km/h.
- The old dead `_score_*_airport_smooth` helpers were removed in the rewrite.
