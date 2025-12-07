# Natural Beauty vs Built Beauty Ridge Regression Comparison

## Model Performance Comparison

| Metric | Natural Beauty | Built Beauty | Difference |
|--------|---------------|--------------|------------|
| **Full R²** | 0.235 | 0.163 | +0.072 (Natural Beauty better) |
| **CV R²** | -0.241 | 0.163 | -0.404 (Built Beauty much better) |
| **RMSE** | 12.97 | 7.43 | +5.54 (Built Beauty better) |
| **Optimal Alpha** | 10,000 | 10.0 | 1000x higher (Natural Beauty needs much more regularization) |
| **N Samples** | 56 | 56 | Same |
| **N Features** | 11 | 13 | Built Beauty has 2 more features |

## Key Findings

### 1. Cross-Validation Performance

**Built Beauty**: Positive CV R² (0.163) indicates the model generalizes well to new data.

**Natural Beauty**: Negative CV R² (-0.241) indicates the model performs worse than a baseline on held-out data. This is a critical issue.

**Conclusion**: Built Beauty model is more reliable and generalizable.

### 2. Regularization Needs

**Built Beauty**: Alpha = 10.0 (moderate regularization)
- Model is relatively stable
- Features are less correlated
- Less overfitting risk

**Natural Beauty**: Alpha = 10,000 (extreme regularization)
- Model requires extreme regularization to prevent overfitting
- Strong indication of multicollinearity
- Features are highly correlated (especially bonus features)

**Conclusion**: Natural Beauty has severe multicollinearity issues that Built Beauty does not have.

### 3. Prediction Accuracy

**Built Beauty**: RMSE = 7.43 (lower is better)
- Predictions are within ~7.4 points on average
- More accurate predictions

**Natural Beauty**: RMSE = 12.97 (higher is worse)
- Predictions are within ~13 points on average
- Less accurate predictions
- Nearly 2x the error of Built Beauty

**Conclusion**: Built Beauty provides more accurate predictions.

### 4. Feature Importance Comparison

#### Built Beauty Top Features (by absolute weight):
1. Material Share (Brick %): +2.626 (very strong positive)
2. Streetwall Continuity: +2.307 (very strong positive)
3. Setback Consistency: +1.870 (strong positive)
4. Block Grain: -1.428 (strong negative)
5. Enhancer Bonus: -0.978 (moderate negative)

#### Natural Beauty Top Features (by absolute weight):
1. Developed %: -0.155 (moderate negative)
2. Tree Score (0-50): +0.091 (moderate positive)
3. Total Context Bonus: -0.042 (weak negative)
4. Green View Index: -0.042 (weak negative)
5. Context Bonus Raw: -0.030 (weak negative)

**Key Differences**:
- Built Beauty features have much larger weights (2-3x range vs 0.01-0.15 range)
- Built Beauty has clear positive signals (Material, Streetwall, Setback)
- Natural Beauty weights are all small, suggesting features are less predictive
- Natural Beauty has unexpected negative coefficients (GVI, Context Bonus)

### 5. Area Type Breakdowns

#### Built Beauty Area Type Performance:
- **urban_core**: n=18, MAE=1.91 (excellent)
- **urban_core_lowrise**: n=7, MAE=1.37 (excellent)
- **suburban**: n=8, MAE=2.56 (good)
- **urban_residential**: n=8, MAE=3.37 (good)
- **historic_urban**: n=9, MAE=4.52 (moderate)
- **rural**: n=5, MAE=0.8 (excellent, but small sample)

#### Natural Beauty Area Type Targets:
- **rural**: n=5, mean_target=94.2 (highest)
- **exurban**: n=2, mean_target=81.0
- **urban_core_lowrise**: n=5, mean_target=75.8
- **historic_urban**: n=8, mean_target=71.9
- **urban_residential**: n=9, mean_target=67.2
- **suburban**: n=10, mean_target=66.5
- **urban_core**: n=17, mean_target=59.4 (lowest)

**Key Differences**:
- Built Beauty has MAE metrics (prediction accuracy by area type)
- Natural Beauty only has mean targets (no MAE breakdown)
- Built Beauty shows consistent low MAE across area types
- Natural Beauty shows expected pattern (rural > urban)

## Root Cause Analysis

### Why Natural Beauty Has Issues

1. **Multicollinearity**: Multiple bonus features are highly correlated
   - Enhancer Bonus Raw, Context Bonus Raw, Enhancer Bonus Scaled, Total Context Bonus
   - These likely measure similar things
   - High alpha (10k) needed to regularize these away

2. **Feature Redundancy**: "Natural Beauty Score" as a feature is circular
   - Using the target as a feature creates leakage
   - Weight is very small (0.013), suggesting it's not helpful

3. **Small Sample Size**: 56 samples for 11 features is borderline
   - Rule of thumb: 10-20 samples per feature
   - Current: ~5 samples per feature (insufficient)
   - CV folds are very small (~11 samples per fold)

4. **Negative Coefficients**: GVI and Context Bonus have negative weights
   - Counterintuitive: more green view should = more beauty
   - Suggests data quality issues or measurement problems
   - Or multicollinearity artifacts

### Why Built Beauty Works Better

1. **Less Multicollinearity**: Features are more independent
   - Architectural metrics (height, type, footprint) are distinct
   - Material and heritage features are separate signals
   - Lower alpha (10) needed

2. **Clearer Signals**: Strong positive features (Material, Streetwall)
   - Large, interpretable coefficients
   - Align with architectural theory

3. **Better Feature Engineering**: Features are well-designed
   - No circular features
   - Each feature captures distinct aspect of built beauty

## Recommendations for Natural Beauty

### Immediate Fixes

1. **Remove Circular Feature**: Drop "Natural Beauty Score" from features
   - It's the target, not a predictor
   - Weight is tiny anyway (0.013)

2. **Feature Selection**: Keep only one bonus feature
   - Drop: Enhancer Bonus Raw, Context Bonus Raw, Enhancer Bonus Scaled
   - Keep: Total Context Bonus (most comprehensive)
   - Reduces from 11 to 8 features

3. **Investigate Negative Coefficients**: 
   - Check GVI calculation and data quality
   - Verify Context Bonus logic
   - May need to fix feature extraction

### Model Improvements

1. **Stratified CV**: Use area_type stratification
   - Ensures each fold has representative area types
   - May improve CV stability

2. **Interaction Terms**: Test Tree Score × Water %
   - May capture synergistic effects
   - Could improve model fit

3. **Area-Type-Specific Models**: Consider separate models
   - Different area types may have different relationships
   - But need more data per area type

### Data Collection

1. **Increase Sample Size**: Target 100+ locations
   - More stable estimates
   - Better CV performance
   - Can support more complex models

2. **Balance Area Types**: Ensure good representation
   - Current: urban_core has 17 samples (good)
   - Current: exurban has only 2 samples (too few)
   - Need more rural and exurban samples

## Conclusion

Built Beauty ridge regression is **significantly better** than Natural Beauty:
- ✅ Positive CV R² (generalizes well)
- ✅ Lower RMSE (more accurate)
- ✅ Lower regularization needed (less multicollinearity)
- ✅ Clearer feature signals

Natural Beauty needs **significant improvements**:
- ❌ Negative CV R² (doesn't generalize)
- ❌ High RMSE (less accurate)
- ❌ Extreme regularization needed (multicollinearity)
- ❌ Unclear feature signals

**Priority Actions**:
1. Remove circular "Natural Beauty Score" feature
2. Drop redundant bonus features (keep only Total Context Bonus)
3. Investigate negative GVI and Context Bonus coefficients
4. Collect more calibration data (target 100+ locations)
5. Implement stratified CV by area_type
