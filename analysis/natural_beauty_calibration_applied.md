# Natural Beauty Calibration Applied

## Summary

Calibration has been applied to the `natural_beauty` pillar using target scores from Perplexity (176 locations).

## Calibration Parameters

- **CAL_A**: 0.131710
- **CAL_B**: 53.223394
- **Source**: `analysis/natural_beauty_calibration_results.json`
- **N Samples**: 176 locations

## Implementation

The calibration is applied in `pillars/natural_beauty.py`:

```python
# Apply linear calibration from regression analysis (176 locations)
CAL_A = 0.131710
CAL_B = 53.223394

calibrated_raw = CAL_A * natural_score_raw + CAL_B
calibrated_raw = max(0.0, min(100.0, calibrated_raw))
```

The calibrated score is then normalized using `normalize_beauty_score()`.

## Validation Results

- **Mean Absolute Error**: 17.50 points
- **Max Absolute Error**: 43.34 points
- **R²**: 0.0242 (very low, indicating weak correlation)
- **Mean Error (bias)**: -0.00 (no systematic bias)

## Important Note: Low Correlation

The calibration has a **very low R² (0.0242)**, which indicates that the raw data-backed scores have weak correlation with the target scores. This results in:

1. **Low variance in calibrated scores**: Standard deviation of 3.26 (vs 20.93 for targets)
2. **Calibration mostly adds constant**: Since CAL_A is small (0.131710), the calibration primarily shifts all scores toward ~53-60 points
3. **Large errors for extreme locations**: Locations with very high/low target scores (e.g., Alaska, Hawaii) have errors of 35-43 points

## Possible Causes

1. **Component weights may need adjustment**: The raw score calculation (tree_score + natural_bonus_scaled) may not align with how Perplexity evaluates natural beauty
2. **Missing factors**: Target scores may consider factors not captured in raw scores (e.g., subjective scenic beauty, cultural significance)
3. **Target score methodology**: Perplexity's evaluation criteria may differ from our data-backed approach

## Recommendations

1. **Review component weights**: Consider adjusting the weights for tree_score vs natural_bonus_scaled
2. **Investigate outliers**: Review locations with large errors (e.g., Alaska, Hawaii, urban areas) to understand discrepancies
3. **Consider area-type-specific calibration**: Similar to `active_outdoors`, area-type-specific calibration might improve accuracy
4. **Re-evaluate target scores**: Verify that Perplexity target scores align with our scoring methodology

## Files Modified

- `pillars/natural_beauty.py`: Added calibration application
- `analysis/natural_beauty_calibration_results.json`: Calibration parameters and statistics
- `analysis/calibration_data_177_locations.json`: Updated with target scores

## Next Steps

1. Test calibration on sample locations via API
2. Monitor variance and accuracy in production
3. Consider refining calibration approach if accuracy is insufficient
