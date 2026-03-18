# Longevity Index

**Date:** 2026-02-28  
**Status:** Implemented. Separate from the user-priority total score.

---

## Overview

The **Longevity Index** is a fixed weighted score over six pillars (Social Fabric, Neighborhood Amenities, Active Outdoors, Natural Beauty, Climate Risk, Quality Education), designed to signal “living longer, healthier.” It is **independent of HomeFit pillar weights** and appears alongside the main score. **User-facing tooltips/modal:** `LONGEVITY_COPY` in `frontend/lib/pillars.ts`.

- **Total score** = weighted average of all 12 pillars using the user’s priority allocation (tokens/priorities).
- **Longevity Index** = fixed weights over 6 pillars only; same 0–100 scale.

---

## Pillar weights

| Pillar                  | Weight | Rationale |
|-------------------------|--------|-----------|
| Social Fabric           | 40%    | Single strongest longevity predictor; core Blue Zone factor |
| Neighborhood Amenities  | 25%    | Walkable daily life enables movement + social connection |
| Active Outdoors         | 15%    | Natural movement and access to outdoor activity |
| Natural Beauty          | 10%    | Stress reduction, restorative environment |
| Climate Risk            | 8%     | Direct health impact, Blue Zone climate correlation |
| Quality Education       | 2%     | Purpose, cognitive engagement |

Total: 100%. All other pillars (e.g. built beauty, air travel, transit, healthcare, economic security, housing) are not included in the Longevity Index.

---

## Implementation

- **Backend:** `pillars/composite_indices.py` defines `LONGEVITY_INDEX_WEIGHTS` and `compute_longevity_index(...)`. The index is added to score responses as:
  - `longevity_index`: number (0–100)
  - `longevity_index_contributions`: `Record<pillar_name, contribution>`

**Partial pillars / same logic as total score:** When `token_allocation` is provided (normal for all score responses), only longevity pillars that **have a score** (already run) **and are selected** (non-zero weight in the current allocation) are used. The fixed Longevity weights are **renormalized** over that subset so the index stays 0–100. You do not need to run all 6 pillars to see a Longevity Index. When you change priorities (weights), both total score and Longevity Index are recomputed from the same cached pillar scores—no rerun required.

- **Frontend:** `ScoreDisplay` shows a “Longevity Index” panel when `longevity_index` is present; types in `frontend/types/api.ts` extend `ScoreResponse` with optional `longevity_index` and `longevity_index_contributions`.

---

## Data

Uses the same pillar scores as the main livability score (no extra API or pillar runs). Only longevity pillars that have been run and are currently selected (non-zero weight) are included; their fixed weights are renormalized to sum to 100% so the index remains 0–100.
