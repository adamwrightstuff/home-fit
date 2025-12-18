# Data-Backed Scoring Audit

## Executive Summary

This audit identifies pillars that have drifted from pure data-backed scoring to model-driven approaches, violating the core design principle: **"Objective, Data-Driven Scoring"** (from `pillars/beauty_design_principles.md`).

## Current State Analysis

### ✅ Pure Data-Backed Pillars (No Models)

These pillars score directly from measurable data:

1. **air_travel_access**: Distance-based scoring to airports (km)
2. **healthcare_access**: Count/distance-based scoring from OSM + fallback databases
3. **built_beauty**: Component-based scoring (architecture diversity, tree canopy)
4. **public_transit_access**: Route count/distance-based scoring (with fallback for data gaps)
5. **housing_value**: Census data-based scoring (with fallback for data gaps)
6. **neighborhood_amenities**: Business count/distance-based scoring with linear calibration (calibration is acceptable - it's a transform on data-backed scores)

### ⚠️ Model-Driven Pillars (Drifting from Data-Backed)

These pillars use statistical models (ridge regression) as their PRIMARY scoring method:

1. **natural_beauty**: Uses ridge regression with tanh bounding
   - **Problem**: Causes convergence (std=0.00, all scores ~98.6)
   - **Root Cause**: Tanh saturation + high intercept (74.45) + small feature weights
   - **Model Quality**: Poor (R²=0.22, CV R²=-0.19, n=56)
   - **Location**: `pillars/natural_beauty.py:1729` - `_compute_ridge_regression_score()`

2. **active_outdoors**: Uses ridge regression (v2 scoring)
   - **Problem**: Causes convergence (std=0.13, scores ~76)
   - **Root Cause**: High intercept (75.64) dominates, small feature weights contribute little
   - **Model Quality**: Poor (R²=0.33, CV R²=-0.86, n=56)
   - **Location**: `pillars/active_outdoors.py:750-776` - inline ridge regression formula

## Design Principle Violation

From `pillars/beauty_design_principles.md`:

> **Principle 5: Objective, Data-Driven Scoring**
> 
> **Principle:** All scoring must be based on objective metrics, not subjective judgments.
> 
> **Rationale:**
> - Reproducible and verifiable
> - Scalable across all locations
> - No location-specific tuning

**Ridge regression violates this principle because:**
- It's a statistical model trained on a small dataset (n=56)
- It introduces non-transparent weighting that's not directly tied to measurable data
- It causes convergence (low variance), making scores meaningless
- It's not reproducible without the training data and model parameters

## Recommended Fixes

### 1. natural_beauty: Replace Ridge Regression with Direct Component Scoring

**Current Approach:**
```python
# Ridge regression with tanh bounding
ridge_score = _compute_ridge_regression_score(normalized_features)
natural_score_raw = ridge_score  # PRIMARY SCORING METHOD
```

**Proposed Approach:**
```python
# Direct component-based scoring (data-backed)
# Tree score (0-50) + Context bonus (0-18) = Raw score (0-68)
# Scale to 0-100: (tree_score + context_bonus) * (100/68)
natural_score_raw = (tree_score + natural_bonus_scaled) * (100.0 / 68.0)
natural_score_raw = min(100.0, natural_score_raw)
```

**Rationale:**
- Tree score is directly measurable (GEE canopy, OSM parks, Census data)
- Context bonus is directly measurable (water %, topography, landcover)
- No statistical model needed - pure data transformation
- Maintains variance and differentiation between locations

### 2. active_outdoors: Replace Ridge Regression with Weighted Component Sum

**Current Approach:**
```python
# Ridge regression formula
calibrated_total = RIDGE_INTERCEPT + sum(weight * feature for weight, feature in zip(RIDGE_WEIGHTS, normalized_features))
```

**Proposed Approach:**
```python
# Direct weighted sum of component scores (data-backed)
# Components are already data-backed: parks, trails, water, camping from OSM/GEE
W_DAILY = 0.30
W_WILD = 0.50
W_WATER = 0.20
calibrated_total = W_DAILY * daily_score + W_WILD * wild_score + W_WATER * water_score
```

**Rationale:**
- Component scores (`daily_score`, `wild_score`, `water_score`) are already data-backed
- They're computed from OSM features, GEE tree canopy, etc.
- Weighted sum is transparent and explainable
- Removes model dependency and convergence issues

## Implementation Plan

### Phase 1: natural_beauty
1. Replace `_compute_ridge_regression_score()` call with direct component sum
2. Remove ridge regression constants and normalization
3. Test on 20+ locations to verify variance restored
4. Document change in `analysis/natural_beauty_data_backed_migration.md`

### Phase 2: active_outdoors
1. Replace inline ridge regression (lines 750-776) with weighted component sum
2. Keep `raw_total` calculation (already correct) as primary score
3. Remove ridge regression constants (keep as advisory only)
4. Test on 20+ locations to verify variance restored
5. Document change in `analysis/active_outdoors_data_backed_migration.md`

### Phase 3: Validation
1. Run regression analysis on all pillars
2. Verify variance restored (std > 1.0 for both pillars)
3. Verify no regressions >10 points without documented reason
4. Update design principles document to explicitly prohibit ML models

## Expected Outcomes

1. **Variance Restored**: Both pillars should have std > 1.0 (currently 0.00 and 0.13)
2. **Transparency**: Scores directly traceable to measurable data
3. **Reproducibility**: No dependency on training data or model parameters
4. **Design Compliance**: Aligns with "Objective, Data-Driven Scoring" principle

## Fallback Scoring Note

Fallback scoring (used in `healthcare_access`, `public_transit_access`, `housing_value`) is **NOT** model-driven. It's:
- Conservative estimates when primary data unavailable
- Based on area type and density (measurable proxies)
- Clearly marked with `fallback_applied: true` flag
- Compliant with design principles (graceful degradation)

The issue is **ridge regression models**, not fallback scoring.
