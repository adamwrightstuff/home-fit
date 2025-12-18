# Low Variance Pillars Diagnosis

## Summary

Three pillars have extremely low variance, making them unsuitable for regression analysis:

1. **quality_education**: std=0.00, mean=0.00 - All scores are 0 (pillar not implemented)
2. **natural_beauty**: std=0.00, mean=98.61, range=0.02 - Almost no variation (all scores ~98.6)
3. **active_outdoors**: std=0.13, mean=75.98, range=0.60 - Very little variation (only 7 unique values)

## 1. Quality Education (std=0.00)

### Problem
All locations score 0.0 - the pillar is not implemented or always returns 0.

### Root Cause
- Pillar function likely not implemented or disabled
- No school quality data being scored
- All locations receive default score of 0

### Impact
- Cannot use for regression analysis
- Provides no differentiation between locations
- Should be implemented or removed from scoring

---

## 2. Natural Beauty (std=0.00, mean=98.61)

### Problem
All locations score ~98.6 with almost no variation (range: 0.02 points).

### Root Cause Analysis

**Component Scores Have Variation:**
- Tree scores: 0.00 - 50.00 (good variation)
- Enhancer bonuses: 1.72 - 19.12 (good variation)

**But Final Scores Converge:**
- All final scores: 98.5985 - 98.6163 (almost identical)
- Raw scores before normalization: also ~98.6

### Technical Cause

The pillar uses **ridge regression with tanh bounding**:

```python
# Formula: tanh((intercept + sum(weight * normalized_feature)) / 50) * 100
ridge_score = tanh(linear_prediction / 50.0) * 100.0
```

**Issue**: The tanh function saturates at high values:
- `tanh(1.5) ≈ 0.905 → 90.5 points`
- `tanh(2.0) ≈ 0.964 → 96.4 points`
- `tanh(2.5) ≈ 0.987 → 98.7 points`
- `tanh(3.0) ≈ 0.995 → 99.5 points`

**The Problem:**
1. Ridge regression intercept: 74.4512
2. Feature weights are very small (0.062, -0.0149, etc.)
3. Most linear predictions end up around 74-80
4. After tanh bounding: `tanh(75/50) = tanh(1.5) ≈ 0.905 → 90.5`
5. But scores are ~98.6, suggesting linear predictions are much higher (~123-125)
6. At these high values, tanh is in saturation zone where small changes in input produce tiny changes in output

**Why Scores Converge:**
- When linear predictions are high (e.g., 120-130), tanh is near saturation
- Small differences in linear predictions (e.g., 120 vs 125) produce almost identical tanh outputs
- Example: `tanh(120/50) = tanh(2.4) ≈ 0.984` vs `tanh(125/50) = tanh(2.5) ≈ 0.987`
- Difference of 5 in linear prediction → difference of only 0.3 points in final score

### Ridge Regression Model Issues

From the code:
- **R² (full)**: 0.2168 (poor fit - only 21.68% variance explained)
- **R² (CV)**: -0.1886 (negative cross-validation R² - model performs worse than baseline)
- **RMSE**: 13.1295 (high error)
- **Optimal alpha**: 19952.6231 (extremely high regularization - model is heavily regularized)
- **n_samples**: 56 (small training set)

**High regularization (alpha=19952) suggests:**
- Model is overfitting or features are poorly predictive
- Heavy regularization shrinks weights toward zero
- This causes predictions to cluster around the intercept

### Recommendations

1. **Reduce tanh saturation**: Increase scaling factor or use different bounding function
2. **Improve ridge regression**: 
   - Collect more training data (n=56 is small)
   - Reduce regularization (alpha too high)
   - Feature engineering to improve predictive power
3. **Alternative scoring**: Consider using component scores directly instead of ridge regression
4. **Investigate linear predictions**: Check why they're so high (120-130 range)

---

## 3. Active Outdoors (std=0.13, mean=75.98)

### Problem
Only 7 unique values between 75.7-76.3, despite component scores having good variation.

### Component Score Variation

| Component | Min | Max | Unique Values | Variation |
|-----------|-----|-----|---------------|-----------|
| Daily Urban Outdoors | 0.0 | 30.0 | 21 | ✅ Good |
| Wild Adventure | 2.6 | 50.0 | 114 | ✅ Excellent |
| Waterfront Lifestyle | 0.0 | 20.0 | 62 | ✅ Good |

### Root Cause

**The system uses v2 scoring with Ridge Regression:**

```python
# Component scores (have good variation):
daily_score = 0-30 (mean=21.8, std=8.0)
wild_score = 2.6-50 (mean=25.6, std=12.0)
water_score = 0-20 (mean=12.2, std=6.0)

# Raw weighted sum (varies):
raw_total = 0.30 * daily + 0.50 * wild + 0.20 * water
# Example: 47.6, 63.5, 74.7 (good variation)

# But then Ridge Regression is applied:
RIDGE_INTERCEPT = 75.6429
RIDGE_WEIGHTS = [-0.0484, 0.0915, 0.0813, ...]  # Small weights
calibrated_total = RIDGE_INTERCEPT + sum(weight * normalized_feature)

# Final scores converge to ~75.98
```

**The Problem:**
1. **Ridge regression intercept is 75.6429** - very close to final scores (~75.98)
2. **Weights are very small** (0.0484, 0.0915, etc.) - normalized features contribute little
3. **Normalized features compress variation** - min-max normalization reduces differences
4. **High intercept dominates** - small weight contributions mean scores cluster around intercept

### Why Scores Converge

**Component scores vary:**
- Daily: 0-30 (good variation)
- Wild: 2.6-50 (excellent variation)
- Water: 0-20 (good variation)
- Component sums: 47.6, 63.5, 74.7 (good variation)

**But ridge regression causes convergence:**
- Intercept: 75.6429 (dominates)
- Normalized features: Small contributions due to small weights
- Example: If normalized features sum to ~0.3, final score = 75.64 + 0.3 = 75.94
- Small variations in normalized features (e.g., 0.3 vs 0.4) produce similar final scores (75.94 vs 76.04)

**Ridge Regression Model Issues:**
- **R² (full)**: 0.333 (only 33.3% variance explained)
- **R² (CV)**: -0.8581 (negative cross-validation R² - model performs worse than baseline!)
- **n_samples**: 56 (small training set)

### Recommendations

1. **Remove or fix ridge regression**: 
   - Use raw weighted sum (`raw_total`) instead of ridge regression
   - Or improve ridge regression model (more data, better features, less regularization)
2. **Reduce intercept dominance**: Lower intercept or increase feature weights
3. **Improve model quality**: 
   - Collect more training data (n=56 is small)
   - Fix negative CV R² (model performs worse than baseline)
   - Feature engineering to improve predictive power
4. **Alternative**: Use simple weighted sum of component scores (already computed as `raw_total`)

---

## Summary of Issues

| Pillar | Issue | Root Cause | Impact |
|--------|-------|------------|--------|
| **quality_education** | All zeros | Not implemented | Cannot use |
| **natural_beauty** | Scores converge to ~98.6 | Tanh saturation + high regularization | No differentiation |
| **active_outdoors** | Scores converge to ~76 | Camping weight too high (50%) | Minimal differentiation |

## Next Steps

1. **quality_education**: Implement pillar or remove from scoring
2. **natural_beauty**: 
   - Investigate why linear predictions are so high
   - Reduce tanh saturation (increase scaling factor)
   - Improve ridge regression model (more data, less regularization)
3. **active_outdoors**:
   - Re-balance component weights (reduce camping, increase others)
   - Check camping score distribution
   - Consider removing normalization
