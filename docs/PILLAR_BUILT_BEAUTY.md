# Pillar Deep-Dive: Built Beauty

How `pillars/built_beauty.py` scores a location (`get_built_beauty_score` →
`calculate_built_beauty`).

## What it measures
The aesthetic quality of the *built* environment — architectural character and diversity,
historic fabric/coherence, and urban form (block grain, streetwall).

## Inputs (fetched in parallel)
- **OSM building footprints** → architectural diversity metrics: `levels_entropy`
  (height diversity), `building_type_diversity`, `footprint_area_cv` (footprint variation),
  plus `built_coverage_ratio` and a model `confidence_0_1`.
- **Historic landmarks** (OSM) + **NRHP** (National Register of Historic Places) counts.
- **Census** median year built + `pre_1940_pct` (age / historic signal).
- Optional charm/enhancer data.

## Score components (combined, coherence can floor the result)
1. **Calibrated architectural beauty** (`compute_calibrated_architectural_beauty_score`) over
   the building-form metrics above — a calibrated 0–100 model.
2. **Historic coherence** — `age_coherence_signal` (0–1 → 0–100), with floors:
   - `historic` contextual tag → ≥ 92
   - genuine **pre-war rowhouse** fabric → ≥ 95, but **gated** on `median_year_built ≤ 1955`
     OR `pre_1940_pct ≥ 10%` OR `nrhp_count ≥ 7`, so postwar neighborhoods tagged "rowhouse"
     by form alone don't get the historic inflation.
3. **Urban form** — block grain → block size, streetwall continuity.

## ⚠️ The reliability issue (and why the catalog backfill is pending)
When the OSM building-footprint fetch **times out**, it returns `coverage = 0` /
`confidence_0_1 = 0`. The calibrated model would otherwise **launder that into a fabricated
~57 floor** — a plausible-looking but meaningless score.

- A reliability guard (commit `03542a4`) retries the building query and **quarantines** any
  place that still comes back zero-coverage/zero-confidence (keeps its old score rather than
  overwriting with a fabricated number). This fixes **live/future** scoring.
- **~34% of the existing catalog still carries stale coverage-0 scores** from before the guard.
  Concrete tell: an affluent leafy suburb scoring oddly low on built_beauty (low-confidence
  ones). Short Hills at 21 was investigated — that one is *confidence 90* (real, suburban
  sprawl genuinely scores low on architectural built form), so not every low score is stale.
- The **catalog backfill is pending** and must run faithfully through `main.py` context (the
  score depends on `form_context` / `location_scope` / density & character preferences /
  `enhancers_data` that `main.py` computes — a standalone loop drifts good-data places by
  ±10-14 pts). See the built-beauty-backfill memory and PILLAR_DATA_QUALITY.

## Gotchas
- **Never relaunder a coverage-0 / confidence-0 result** into a number — quarantine it.
- Suburban sprawl legitimately scores low on architectural built form (low diversity / no
  historic fabric); a low high-confidence score is not necessarily stale.
- The historic-coherence floors are deliberately gated on real age data to avoid inflating
  generic postwar neighborhoods.
