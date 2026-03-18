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

**Full score (no `only=`):** When `token_allocation` is provided, eligible longevity pillars (non-zero weight in the request or full run) are used; weights renormalize over that subset.

**Partial `only=` requests:** `longevity_index` and `longevity_index_contributions` are **omitted (null)** unless **all six** longevity pillars were included in that request (`should_emit_longevity_index` in `pillars/composite_indices.py`). Otherwise a single pillar (e.g. schools at 100) would incorrectly dominate the index. The client recomputes longevity from merged pillar scores using `computeLongevityIndex` / `longevityIndexFromLivabilityPillars`.

- **Frontend:** Prefers longevity computed from current `livability_pillars` over stale `longevity_index` on the payload. Saved-score merges recompute from merged pillars. `ScoreDisplay` shows the index when the derived value is present.

---

## Data

Uses the same pillar scores as the main livability score (no extra API or pillar runs). Only longevity pillars that have been run and are currently selected (non-zero weight) are included; their fixed weights are renormalized to sum to 100% so the index remains 0–100.
