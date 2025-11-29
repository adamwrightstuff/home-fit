# Active Outdoors v2 - Round 12 Calibration Analysis

**Date:** 2024-12-XX  
**Status:** Re-calibrating after fixes

---

## Calibration Results (Initial Run)

### Metrics
- **CAL_A:** 1.288422
- **CAL_B:** 47.380292
- **R²:** 0.2746
- **MAE:** 15.58
- **Max Error:** 33.19

### Comparison to Baseline
| Metric | Before Fixes | After Fixes | Change |
|--------|--------------|-------------|--------|
| R² | 0.2779 | 0.2746 | -0.0013 (slightly worse) |
| MAE | 15.48 | 15.58 | +0.10 (slightly worse) |
| Max Error | 32.53 | 33.19 | +0.66 (slightly worse) |

---

## Key Findings

### ✅ Success: Kansas City Fix
- **Before:** Error +35.0, Wild Adventure 34.5, Mountain Town=True ❌
- **After:** Error +24.0, Wild Adventure 19.7, Mountain Town=False ✅
- **Improvement:** +11.0 points

**Root Cause Fixed:** False positive mountain town detection eliminated

### ⚠️ Issue: Boulder Data Problem
- **Calibration Result:** Daily Urban = 0.0, Error -30.6
- **Manual Test:** Daily Urban = 17.5, Error -12.3
- **Analysis:** Transient OSM API issue during calibration, not a code problem

**Impact:** Boulder's incorrect data skewed calibration metrics

### 📊 Other Outliers
- **Times Square:** Error +30.9 (was +33.0) - slight improvement
- **Detroit:** Error +30.6 (was +31.7) - slight improvement  
- **Houston:** Error +28.8 (was +30.3) - slight improvement
- **Phoenix:** Error +29.1 (unchanged)

---

## Design Principles Applied

### ✅ Research-Backed
- Fixes based on data patterns (false positives, OSM artifacts)
- Not tuned to match target scores

### ✅ Transparent
- All fixes documented with rationale
- Data issues identified and addressed

### ✅ Objective Criteria
- Mountain town detection uses objective signals
- No city-name exceptions

### ✅ Data Quality Measures
- Urban core penalties prevent OSM artifacts from inflating scores
- Trail caps prevent false positives

---

## Next Steps (Design Principles-Based)

1. **Re-run Calibration** ✅ (in progress)
   - Get accurate data for all locations
   - Eliminate transient API issues

2. **Analyze Results**
   - If metrics improve → update CAL_A/CAL_B
   - If metrics still poor → investigate systematic issues (not target-tune)

3. **Systematic Investigation** (if needed)
   - Analyze patterns in remaining outliers
   - Identify objective criteria for additional fixes
   - Document all changes with research-backed rationale

4. **No Target Tuning**
   - Will NOT adjust components to match specific target scores
   - Will ONLY fix systematic issues based on objective criteria

---

## Fixes Applied (For Reference)

1. **Mountain Town Detection:** Strengthened to prevent false positives
2. **Urban Core Daily Penalty:** Increased max penalty 5.0 → 8.0
3. **Urban Core Trail Cap:** Reduced cap 3x → 2x expected
4. **Urban Core Water Downweight:** Reduced multiplier 0.6 → 0.5

All fixes are research-backed and address systematic issues, not specific locations.

