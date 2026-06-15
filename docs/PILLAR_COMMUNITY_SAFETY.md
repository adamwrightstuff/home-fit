# Pillar Deep-Dive: Community Safety

How `pillars/community_safety.py` scores a location (`get_community_safety_score`).

## What it measures
Crime safety from **agency-reported** rates — violent and property crimes per 1,000, scored
relative to area-type expectations, nudged by the recent trend.

## Inputs
- `get_crime_rates(lat, lon, city, state_abbr, area_type, population)` → FBI CDE
  (Crime Data Explorer), agency-level where available. `state` (2-letter) is required for CDE
  routing; population defaults to 10,000 for per-1k conversion.

## Scoring flow
1. **Commuter-denominator boost** (`compute_commuter_denominator_boost`, LODES workplace/
   resident ratio): divides the raw per-1k rates by a multiplier so a daytime-commuter hub
   (business district) isn't penalized for crime-per-*resident* when its real denominator
   includes commuters.
2. **Rate → score** (`_score_rates`): violent + property per-1k mapped to a 0–100 score,
   **relative to area-type baselines** (urban cores carry higher expected crime than exurbs).
3. **Trend delta** (`_trend_delta`): a small +/- nudge from the recent crime trend.
   `final = clamp(raw_score + trend_delta)`.

## When it returns None (excluded from the composite)
The pillar deliberately returns `None` (rather than a misleading number) in three cases —
the catalog then drops it from the weight set:

| status | when | note |
|---|---|---|
| `DEGRADED` | no crime data at all | confidence 0 |
| `COMING_SOON` | jurisdiction not wired up in CDE yet | ⚠️ **coverage gap, NOT bad data** (Sleepy Hollow, Summit, Belmont Shore, Lakewood) |
| `DEGRADED` (state-aggregate) | only `fbi_cde_state` available | zero-tolerance: a state average is meaningless for one place, so it's withheld |

So a null community_safety is usually a **coverage gap**, not an error. Don't treat it as a
score of 0; the place is correctly weighted over its remaining pillars.

## Catalog / weighting
The 4 COMING_SOON places have `community_safety` weight 0; their other pillars renormalize to
sum to 100 (`repair_diversity_and_weights.py` ensured this). See CATALOG_RESCORE_RUNBOOK and
PILLAR_DATA_QUALITY.

## Gotchas
- Scores are **area-type-relative** — a low-crime urban core can score similarly to a quiet
  suburb because expectations differ; don't compare raw per-1k across area types.
- A place legitimately scoring low (Compton 6, Watts) reflects real reported crime, not a bug.
- The commuter-denominator boost relies on the LODES grid (same data as economic_security's
  job-accessibility); coverage gaps there fall back to no boost.
