# Longevity Index

**Version:** 5 (2026-10-08)
**Status:** Implemented. Separate from the user-priority total score.

---

## Overview

The **Longevity Index** is a fixed weighted score over seven pillars, designed to signal "living longer, healthier." It is **independent of HomeFit pillar weights** and appears alongside the main score. User-facing copy lives in `LONGEVITY_COPY` (`frontend/lib/pillars.ts`) and `INDEX_COPY.longevity` (`frontend/lib/catalogInfoCopy.ts`).

- **Total score** = weighted average of all pillars using the user's priority allocation.
- **Longevity Index** = fixed weights over the pillars below; same 0-100 scale.

---

## Pillar weights

| Pillar                 | Weight | Rationale |
|------------------------|--------|-----------|
| Social Fabric          | 35%    | Holt-Lunstad (2015): social isolation linked to 29% higher mortality |
| Active Outdoors        | 22%    | Li (2019 JAMA): greenspace linked to 12-24% lower all-cause mortality; fitness is a top longevity predictor |
| Neighborhood Amenities | 15%    | Walkable daily life (movement without a gym) and food access |
| Climate Risk (air + heat only) | 8% | Pope (2009): fine particles and life expectancy; heat and excess summer mortality |
| Community Safety       | 8%     | Chronic stress and trauma from crime |
| Natural Beauty         | 5%     | Stress-reduction pathway; partly overlaps Active Outdoors |
| Quality Education      | 3%     | Cutler and Lleras-Muney (2008): education and lower mortality |

Weights are judgment calls grounded in the cited effects, not fitted to outcome data. Renormalized over pillars that are eligible and scored.

**Climate slot:** scored from air quality (5/8) and heat exposure (3/8) using the stored `aqi_score` and `lst_score` in the climate_risk breakdown. Flood zone and the 30-year temperature trend are excluded (property and forward risk, not mortality drivers). If the sub-scores are absent, the full climate_risk score is used.

**Removed:** Healthcare Access (v3). Its evidence is county-level rural vs urban; within a metro the pillar measures OSM clinic and pharmacy density on commercial corridors, which does not predict longevity differences between nearby neighborhoods.

All other pillars (transit, air travel, housing, economic opportunity, diversity, built environment, political lean) are not included.

---

## Implementation

- **Backend:** `pillars/composite_indices.py` defines `LONGEVITY_INDEX_WEIGHTS`, `_longevity_pillar_score`, and `compute_longevity_index`. Responses carry `longevity_index` and `longevity_index_contributions`.
- **Failed pillars (v5):** a pillar with status `failed` or `no_data`, an error, or confidence 0 is dropped and the remaining weights renormalize, instead of being scored as its placeholder 0. The frontend applies the same rule (`failed` flag in `computeLongevityIndex`).
- **Eligibility:** with a token allocation, only pillars with a non-zero weight (or requested in a partial run) and a score are used; weights renormalize over that subset. Catalog rows use the stored allocation, so pillars weighted 0 there (e.g. natural beauty, education) drop out.
- **Partial `only=` requests:** the index is omitted unless all seven longevity pillars were requested (`should_emit_longevity_index`).
- **Frontend:** `LONGEVITY_INDEX_WEIGHTS`, `longevityPillarScore`, and `computeLongevityIndex` in `frontend/lib/pillars.ts` mirror the backend and must be kept in sync. Saved-score merges (`mergeSavedScores.ts`) and `PlaceView` recompute from merged pillars.
- **Catalog:** recompute offline with `scripts/catalog/recompute_catalog_composites.py --no-census`. No API calls needed.
