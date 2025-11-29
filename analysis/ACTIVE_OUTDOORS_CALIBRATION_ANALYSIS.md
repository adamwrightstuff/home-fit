# Active Outdoors v2 Calibration Analysis
## Round 11 Calibration Results

**Date:** 2024-12-XX  
**Calibration Script:** `scripts/calibrate_active_outdoors_v2.py`  
**Calibration Panel:** 18 locations (Round 11)  
**Calibration Data:** `analysis/active_outdoors_calibration_round11.json`

---

## Calibration Parameters

**Linear Fit:** `target_score ≈ CAL_A * raw_total + CAL_B`

- **CAL_A:** 1.940838
- **CAL_B:** 34.096903

**Updated in:** `pillars/active_outdoors.py`

---

## Calibration Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Mean Error** | -0.00 | ≈ 0 | ✅ Excellent |
| **Mean Absolute Error** | 12.35 | ≤ 10 | ⚠️ Above target |
| **Max Absolute Error** | 34.03 | ≤ 20 | ❌ Well above target |
| **R²** | 0.3225 | > 0.7 | ❌ Poor fit |

---

## Overall Assessment

### ✅ Strengths
- Mean error is essentially zero (perfectly balanced)
- Several locations have very good fits (Walnut Creek: 0.0, Upper West Side: -0.3, Park Slope: +1.8)

### ⚠️ Concerns
1. **Low R² (0.32):** Indicates linear calibration may not fully capture the score distribution
2. **High Mean Absolute Error (12.35):** Above the 10-point target
3. **Large Outliers:** Several locations have errors >20 points

---

## Outlier Analysis

### Major Over-Scoring (Score > Target + 20)

| Location | Target | Score | Error | Area Type | Issue |
|----------|--------|-------|-------|-----------|-------|
| **Times Square NY** | 35 | 72.0 | **+37.0** | urban_core | Severe over-scoring - dense urban core should score much lower |
| **Downtown Las Vegas NV** | 42 | 66.9 | **+24.9** | suburban | Over-scoring - desert location with limited outdoor access |
| **Downtown Phoenix AZ** | 48 | 69.7 | **+21.7** | suburban | Over-scoring - desert location with limited outdoor access |

**Common Pattern:** Dense urban cores and desert locations are over-scoring. This suggests:
- Urban core penalty may not be strong enough
- Daily urban outdoors component may be too generous for dense cores
- Water access scoring may be too generous (even for non-coastal locations)

### Major Under-Scoring (Score < Target - 15)

| Location | Target | Score | Error | Area Type | Issue |
|----------|--------|-------|-------|-----------|-------|
| **Boulder CO** | 95 | 75.5 | **-19.5** | urban_core | Under-scoring - mountain town with excellent outdoor access |
| **Downtown Denver CO** | 92 | 72.0 | **-20.0** | urban_core | Under-scoring - mountain city with good outdoor access |
| **Downtown Seattle WA** | 92 | 75.8 | **-16.2** | urban_core | Under-scoring - coastal city with good outdoor access |

**Common Pattern:** Mountain towns and outdoor-oriented cities are under-scoring. This suggests:
- Wild adventure component may not be capturing trail richness adequately
- Mountain town detection may be needed (similar to commuter_rail_suburb for transit)
- Trail expectations may be too low for these locations

---

## Component Score Analysis

### Times Square (Target: 35, Score: 72.0, Error: +37.0)
- **Daily Urban Outdoors:** 23.4 (max 30) - High for dense core
- **Wild Adventure:** 16.8 (max 50) - Too high for urban core
- **Waterfront Lifestyle:** 12.8 (max 20) - Reasonable

**Issue:** Times Square is a dense urban core with minimal outdoor access, but it's scoring 72.0. The daily urban outdoors and wild adventure components are too high.

**Recommendation:** 
- Reduce daily urban outdoors scoring for dense urban cores
- Further reduce wild adventure scoring for urban cores (canopy max already reduced to 12.0, may need more)

### Boulder (Target: 95, Score: 75.5, Error: -19.5)
- **Daily Urban Outdoors:** 21.8 (max 30) - Reasonable
- **Wild Adventure:** 23.1 (max 50) - Too low for mountain town
- **Waterfront Lifestyle:** 14.4 (max 20) - Reasonable

**Issue:** Boulder is a mountain town with excellent trail access, but wild adventure is only 23.1/50.

**Recommendation:**
- Investigate why trail scoring is low (may be OSM data quality issue)
- Consider mountain town detection with higher trail expectations
- Review trail proximity scoring (may need adjustment for mountain towns)

### Downtown Las Vegas (Target: 42, Score: 66.9, Error: +24.9)
- **Daily Urban Outdoors:** 17.2 (max 30) - Reasonable
- **Wild Adventure:** 10.8 (max 50) - Reasonable for desert
- **Waterfront Lifestyle:** 15.4 (max 20) - Too high for desert location

**Issue:** Las Vegas is a desert location with minimal outdoor access, but waterfront lifestyle is 15.4/20.

**Recommendation:**
- Investigate why water access is scoring high (may be false positive from OSM data)
- Add desert/climate detection to reduce water access expectations
- Review water access distance decay (may be too generous)

---

## Recommendations

### Immediate Actions

1. **Investigate Outliers**
   - Review OSM data quality for Times Square, Las Vegas, Phoenix
   - Check if water access is being incorrectly detected
   - Verify trail data for Boulder, Denver, Seattle

2. **Component Scoring Adjustments**
   - **Daily Urban Outdoors:** Reduce scoring for dense urban cores (Times Square)
   - **Wild Adventure:** Further reduce for urban cores, increase for mountain towns
   - **Waterfront Lifestyle:** Add climate/desert detection to reduce false positives

3. **Area Type Detection**
   - Consider "mountain_town" detection (elevation + trail density)
   - Consider "desert" detection (climate data) to adjust expectations

### Medium-Term Improvements

4. **Non-Linear Calibration**
   - Consider piecewise linear or polynomial calibration instead of simple linear
   - May improve R² and reduce outliers

5. **Component Weight Rebalancing**
   - Current weights: Daily 30%, Wild 50%, Water 20%
   - May need adjustment based on correlation analysis

6. **Expected Values Review**
   - Verify expected values for urban_core (may be too high)
   - Expand research for mountain towns and desert locations

---

## Comparison to Previous Calibration

**Previous (Round 9):**
- CAL_A: 1.768
- CAL_B: 36.202

**Current (Round 11):**
- CAL_A: 1.940838 (+9.8%)
- CAL_B: 34.096903 (-5.8%)

**Change:** Higher slope (CAL_A) and lower intercept (CAL_B) suggests raw scores are generally lower, requiring more aggressive scaling.

---

## Next Steps

1. ✅ **Update calibration parameters** - DONE
2. ⏳ **Investigate outliers** - Review OSM data and component scoring
3. ⏳ **Component adjustments** - Address over-scoring in urban cores and under-scoring in mountain towns
4. ⏳ **Re-run calibration** - After component adjustments
5. ⏳ **Document findings** - Update methodology documentation

---

## Validation Status

| Criterion | Status | Notes |
|----------|--------|-------|
| Mean absolute error ≤ 10 | ❌ | 12.35 (above target) |
| Max absolute error ≤ 20 | ❌ | 34.03 (Times Square outlier) |
| R² > 0.7 | ❌ | 0.32 (poor fit) |
| Relative ordering maintained | ⚠️ | Mostly maintained, but outliers exist |

**Overall:** Calibration needs improvement. The low R² and large outliers suggest systematic issues with component scoring that should be addressed before finalizing calibration.

---

**End of Analysis**

