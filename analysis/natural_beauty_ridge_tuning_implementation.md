# Natural Beauty Ridge Regression Tuning Implementation Guide

## Current Status

✅ Ridge regression weights applied to Natural Beauty pillar code
✅ Ridge regression score computed as advisory metric
✅ Analysis of negative CV R² completed
✅ Comparison with Built Beauty completed

## Tuning Recommendations Implementation

### 1. Feature Selection (Reduce Multicollinearity)

**Problem**: Multiple bonus features are highly correlated:
- Enhancer Bonus Raw
- Context Bonus Raw
- Enhancer Bonus Scaled
- Total Context Bonus

**Solution**: Keep only Total Context Bonus (most comprehensive)

**Implementation**:
```python
# In natural_beauty.py, modify _compute_natural_beauty_ridge_features()
# Remove these features:
# - "Enhancer Bonus Raw"
# - "Context Bonus Raw"  
# - "Enhancer Bonus Scaled"
# Keep only: "Total Context Bonus"

# Also remove "Natural Beauty Score" (circular feature - it's the target)
```

**Expected Impact**: 
- Reduces features from 11 to 7
- Eliminates multicollinearity
- May reduce optimal alpha significantly
- Should improve CV R²

### 2. Stratified Cross-Validation by Area Type

**Problem**: Current 5-fold CV may have imbalanced area types in each fold

**Solution**: Use stratified CV to ensure each fold has representative area types

**Implementation** (for future ridge regression training):
```python
from sklearn.model_selection import StratifiedKFold

# Use area_type as stratification variable
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=skf, groups=area_types)
```

**Expected Impact**:
- More stable CV estimates
- Better representation of area types in each fold
- May improve CV R²

### 3. Interaction Terms

**Problem**: Features may have synergistic effects (e.g., Tree Score × Water %)

**Solution**: Add interaction terms to capture non-linear relationships

**Implementation** (for future ridge regression training):
```python
# Add interaction features
X['tree_water_interaction'] = X['tree_score'] * X['water_pct']
X['tree_canopy_interaction'] = X['tree_score'] * X['neighborhood_canopy_pct']
X['water_slope_interaction'] = X['water_pct'] * X['slope_mean_deg']

# Then fit ridge regression with expanded feature set
```

**Expected Impact**:
- May capture synergistic effects
- Could improve model fit (R²)
- Need to test if interaction terms are significant

### 4. Refine Alpha Grid

**Problem**: Optimal alpha (10k) is at the edge of the grid

**Solution**: Test more values around 1k-10k range, and potentially higher

**Implementation** (for future ridge regression training):
```python
# Refined alpha grid
alpha_grid = [
    100, 200, 500, 750, 1000, 2000, 3000, 5000, 
    7500, 10000, 15000, 20000, 30000, 50000
]

# Or use log scale
alpha_grid = np.logspace(2, 5, 20)  # 100 to 100000
```

**Expected Impact**:
- May find better alpha value
- More precise regularization tuning

### 5. Area-Type-Specific Models

**Problem**: Different area types may have different relationships

**Solution**: Train separate models for each area type (if sample size allows)

**Implementation** (for future ridge regression training):
```python
# Train separate models by area type
area_type_models = {}
for area_type in ['urban_core', 'suburban', 'rural', ...]:
    mask = area_types == area_type
    if mask.sum() >= 10:  # Need at least 10 samples
        X_subset = X[mask]
        y_subset = y[mask]
        model = Ridge(alpha=optimal_alpha)
        model.fit(X_subset, y_subset)
        area_type_models[area_type] = model
```

**Expected Impact**:
- May improve predictions for specific area types
- But requires sufficient samples per area type (≥10)
- Current data: some area types have too few samples

## Code Changes Needed

### Immediate (Can implement now)

1. **Remove circular feature**: "Natural Beauty Score"
   - File: `pillars/natural_beauty.py`
   - Function: `_compute_natural_beauty_ridge_features()`
   - Change: Remove "Natural Beauty Score" from features

2. **Remove redundant bonus features**
   - Keep only: "Total Context Bonus"
   - Remove: "Enhancer Bonus Raw", "Context Bonus Raw", "Enhancer Bonus Scaled"

### Future (Requires retraining model)

1. **Stratified CV**: Implement when retraining
2. **Interaction terms**: Add when retraining
3. **Refined alpha grid**: Use when retraining
4. **Area-type-specific models**: Consider if sample size increases

## Data Collection Priorities

### Current Sample Distribution
- urban_core: 17 samples ✅ (good)
- suburban: 10 samples ✅ (adequate)
- urban_residential: 9 samples ✅ (adequate)
- historic_urban: 8 samples ✅ (adequate)
- urban_core_lowrise: 5 samples ⚠️ (borderline)
- rural: 5 samples ⚠️ (borderline)
- exurban: 2 samples ❌ (too few)

### Target Sample Distribution
- **Total**: 100+ locations (currently 56)
- **Per area type**: 10+ samples minimum
- **Priority**: Collect more rural and exurban samples

## Testing Plan

### Phase 1: Feature Selection (Immediate)
1. Remove circular "Natural Beauty Score" feature
2. Remove redundant bonus features (keep only Total Context Bonus)
3. Retrain model with 7 features instead of 11
4. Compare CV R² and RMSE

### Phase 2: Improved CV (Next)
1. Implement stratified CV by area_type
2. Retrain model with stratified CV
3. Compare CV R² stability

### Phase 3: Interaction Terms (Future)
1. Add Tree Score × Water % interaction
2. Test other interaction terms
3. Retrain and compare performance

### Phase 4: Area-Type-Specific Models (Future)
1. Collect more data (target 100+ locations)
2. Train separate models for each area type
3. Compare with global model

## Success Metrics

### Target Improvements
- **CV R²**: From -0.241 to >0.0 (positive)
- **RMSE**: From 12.97 to <10.0 (closer to Built Beauty's 7.43)
- **Optimal Alpha**: From 10,000 to <1,000 (less regularization needed)
- **Feature Count**: From 11 to 7-8 (remove redundant features)

### Comparison Targets
- Match Built Beauty's CV R² (0.163)
- Match Built Beauty's RMSE (7.43)
- Match Built Beauty's alpha (10.0)

## Notes

- Current implementation uses ridge regression as **advisory only**
- Primary scoring still uses original method
- Ridge regression score available in `details.ridge_regression.predicted_score`
- Changes to feature selection require retraining the model
- All tuning recommendations should be tested with new calibration data
