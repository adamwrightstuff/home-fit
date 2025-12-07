# Natural Beauty Ridge Regression Analysis

## Model Performance Summary

- **Full R²**: 0.235 (23.5% variance explained)
- **CV R²**: -0.241 (negative cross-validation R²)
- **RMSE**: 12.97
- **Optimal Alpha**: 10,000 (very high regularization)
- **N Samples**: 56 locations
- **N Features**: 11 features

## Negative CV R² Analysis

### What Negative CV R² Means

A negative cross-validation R² indicates that the model performs **worse than a simple baseline** (predicting the mean) on held-out data. This is a serious warning sign.

### Possible Causes

1. **Overfitting**: The model fits the training data too closely and fails to generalize
   - Evidence: Full R² (0.235) is positive, but CV R² (-0.241) is negative
   - High alpha (10k) suggests strong regularization was needed, indicating potential overfitting without it

2. **Small Sample Size**: With only 56 samples and 11 features, the model has limited data
   - Rule of thumb: Need ~10-20 samples per feature for stable models
   - Current ratio: 56/11 ≈ 5 samples per feature (insufficient)

3. **Multicollinearity**: High correlation between features (especially bonus features)
   - Evidence: High alpha (10k) needed for regularization
   - Key insight from results: "Bonus features show multicollinearity (shrunk coefficients)"
   - Multiple bonus features (Enhancer Bonus Raw, Context Bonus Raw, Enhancer Bonus Scaled, Total Context Bonus) are likely highly correlated

4. **Data Quality Issues**: 
   - Potential outliers or measurement errors
   - Inconsistent feature extraction across locations
   - Missing data handling issues

5. **Cross-Validation Strategy**: 
   - 5-fold CV on 56 samples = ~11 samples per fold
   - With high variance in small folds, CV estimates can be unstable
   - Stratified CV by area_type might help (recommended in tuning_recommendations)

### Comparison with Built Beauty

Built Beauty ridge regression:
- **CV R²**: 0.1626 (positive, much better)
- **Full R²**: 0.1626
- **Optimal Alpha**: 10.0 (much lower)
- **RMSE**: 7.43 (lower)
- **N Features**: 13 features

**Key Differences**:
- Built Beauty has positive CV R², indicating better generalization
- Built Beauty uses lower regularization (alpha=10 vs 10k)
- Built Beauty has lower RMSE (7.43 vs 12.97)
- Natural Beauty has more multicollinearity issues (higher alpha needed)

## Feature Analysis

### Strongest Predictors (by absolute weight)

1. **Developed %**: -0.155 (strongest negative impact)
   - Less developed = more natural beauty (expected)
   - This makes intuitive sense

2. **Tree Score (0-50)**: +0.091 (strongest positive predictor)
   - Trees are key to natural beauty (expected)
   - This aligns with the pillar's focus

3. **Total Context Bonus**: -0.042 (negative, unexpected)
   - Higher context bonus associated with lower scores?
   - Possible multicollinearity artifact

4. **Green View Index**: -0.042 (negative, unexpected)
   - Higher GVI associated with lower scores?
   - Counterintuitive - needs investigation

5. **Context Bonus Raw**: -0.030 (negative)
   - Similar to Total Context Bonus issue

### Multicollinearity Issues

The following features are likely highly correlated:
- Enhancer Bonus Raw
- Context Bonus Raw  
- Enhancer Bonus Scaled
- Total Context Bonus

**Recommendation**: Consider feature selection to drop redundant bonus variables.

## Recommendations

### Immediate Actions

1. **Feature Selection**: Remove highly collinear bonus features
   - Test models with only: Tree Score, Water %, Slope, Developed %, Canopy %, GVI
   - Keep only one bonus feature (e.g., Total Context Bonus)

2. **Stratified Cross-Validation**: Use area_type stratification
   - Ensures each fold has representative area types
   - May improve CV stability

3. **Increase Sample Size**: Collect more calibration data
   - Target: 100+ locations for more stable estimates
   - Ensure balanced representation across area types

4. **Investigate Negative Coefficients**: 
   - Why are GVI and Context Bonus negative?
   - Check for data quality issues or measurement errors
   - Verify feature extraction logic

### Model Improvements

1. **Interaction Terms**: Test Tree Score × Water % interaction
   - Recommended in tuning_recommendations
   - May capture synergistic effects

2. **Refine Alpha Grid**: Focus on 1k-10k range
   - Current optimal is at edge of grid (10k)
   - May need to test higher values or different regularization

3. **Area-Type-Specific Models**: Consider separate models by area_type
   - Different area types may have different relationships
   - Built Beauty uses area_type breakdowns

### Data Quality

1. **Outlier Detection**: Identify and investigate outliers
   - Check for locations with large residuals
   - Verify data quality for those locations

2. **Feature Validation**: Verify feature extraction
   - Ensure all features are calculated consistently
   - Check for missing data patterns

## Implementation Status

✅ Ridge regression weights applied to Natural Beauty pillar code
- Features extracted and normalized
- Ridge score computed as advisory metric
- Metadata included in API response

⚠️ **Note**: Current implementation uses ridge regression as advisory only
- Primary scoring still uses original method
- Ridge regression score available in `details.ridge_regression.predicted_score`

## Next Steps

1. Collect more calibration data (target: 100+ locations)
2. Implement feature selection to reduce multicollinearity
3. Test stratified CV by area_type
4. Investigate negative coefficients for GVI and Context Bonus
5. Consider area-type-specific models if sample size allows
