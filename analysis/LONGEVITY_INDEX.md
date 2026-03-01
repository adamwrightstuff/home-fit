# Longevity Index

**Date:** 2026-02-28  
**Status:** Implemented. Separate from the user-priority total score.

---

## Overview

The **Longevity Index** is a fixed weighted score over six pillars, designed to signal “living longer, healthier” without requiring users to know the Blue Zones brand. It is **independent of user priorities** and appears alongside the main HomeFit total score in API responses and the UI.

- **Total score** = weighted average of all 12 pillars using the user’s priority allocation (tokens/priorities).
- **Longevity Index** = fixed weights over 6 pillars only; same 0–100 scale.

---

## Pillar weights

| Pillar                  | Weight | Rationale |
|-------------------------|--------|-----------|
| Social Fabric           | 30%    | Single strongest longevity predictor |
| Active Outdoors         | 25%    | Natural movement is foundational |
| Neighborhood Amenities | 20%    | Walkability enables daily movement + social connection |
| Natural Beauty          | 10%    | Stress reduction, restorative environment |
| Climate Risk            | 10%    | Direct health impact, Blue Zone climate correlation |
| Quality Education       | 5%     | Purpose, cognitive engagement |

Total: 100%. All other pillars (e.g. built beauty, air travel, transit, healthcare, economic security, housing) are not included in the Longevity Index.

---

## Implementation

- **Backend:** `main.py` defines `LONGEVITY_INDEX_WEIGHTS` and `_compute_longevity_index(livability_pillars)`. The index is computed after `livability_pillars` is built and added to every score response as:
  - `longevity_index`: number (0–100)
  - `longevity_index_contributions`: `Record<pillar_name, contribution>`
- **Frontend:** `ScoreDisplay` shows a “Longevity Index” panel when `longevity_index` is present; types in `frontend/types/api.ts` extend `ScoreResponse` with optional `longevity_index` and `longevity_index_contributions`.

---

## Data

Uses the same pillar scores as the main livability score (no extra API or pillar runs). If a pillar is missing (e.g. quality_education when schools are disabled), its contribution is 0.
