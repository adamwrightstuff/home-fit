# Data-Backed Scoring Migration - Complete

## Summary

Successfully migrated two pillars from model-driven (ridge regression) to pure data-backed scoring, ensuring compliance with design principles.

## Changes Made

### 1. natural_beauty (`pillars/natural_beauty.py`)

**Before:** Used ridge regression with tanh bounding as primary scoring method
```python
ridge_score = _compute_ridge_regression_score(normalized_features)
natural_score_raw = ridge_score  # Model-driven
```

**After:** Direct component-based scoring
```python
natural_native = max(0.0, tree_score + natural_bonus_scaled)
natural_score_raw = min(100.0, natural_native * (100.0 / 68.0))  # Data-backed
```

**Components:**
- `tree_score` (0-50): Measured from GEE canopy, OSM parks, Census data
- `natural_bonus_scaled` (0-18): Measured from water %, topography, landcover

**Rationale:** Tree score and context bonus are directly measurable. No statistical model needed.

### 2. active_outdoors (`pillars/active_outdoors.py`)

**Before:** Used ridge regression formula as primary scoring
```python
calibrated_total = RIDGE_INTERCEPT + sum(weight * feature for weight, feature in zip(RIDGE_WEIGHTS, normalized_features))
```

**After:** Direct weighted sum of component scores
```python
calibrated_total = W_DAILY * daily_score + W_WILD * wild_score + W_WATER * water_score
```

**Components:**
- `daily_score` (0-30): Parks, playgrounds, recreational facilities from OSM
- `wild_score` (0-50): Hiking trails, camping from OSM
- `water_score` (0-20): Swimming locations from OSM

**Rationale:** All components are directly measurable from OSM/GEE data. Weighted sum is transparent and explainable.

## Design Principle Compliance

✅ **Principle 5: Objective, Data-Driven Scoring**
- All scoring now based on objective metrics (OSM features, GEE canopy, Census data)
- No statistical models or training data dependencies
- Reproducible and verifiable
- Scalable across all locations

## Expected Impact

1. **Variance Restored**: Both pillars should now have std > 1.0 (previously 0.00 and 0.13)
2. **Transparency**: Scores directly traceable to measurable data
3. **Reproducibility**: No dependency on training data or model parameters
4. **No Convergence**: Scores will differentiate between locations

## Testing Required

1. Run regression analysis on 20+ locations
2. Verify variance restored (std > 1.0 for both pillars)
3. Verify no regressions >10 points without documented reason
4. Check that scores differentiate between locations (no convergence)

## Ridge Regression Status

Ridge regression coefficients are now **advisory only**:
- Still computed and included in breakdown for reference
- Not used for primary scoring
- Can be removed in future cleanup if desired

## Next Steps

1. Test changes on sample locations
2. Run full regression analysis
3. Verify variance metrics improved
4. Update design principles document to explicitly prohibit ML models as primary scoring
