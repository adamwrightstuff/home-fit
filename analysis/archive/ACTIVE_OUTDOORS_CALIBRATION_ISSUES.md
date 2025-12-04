# Active Outdoors v2 Calibration Issues Analysis

## Summary

Round 12 calibration completed with **16/36 locations** (44% success rate). Many locations failed geocoding due to network timeouts. Calibration metrics show poor fit:
- **R²: 0.16** (very poor)
- **MAE: 16.0 points**
- **Max Error: 33.9 points**

## Key Issues Identified

### 1. Geocoding Failures (20 locations)

**Root Cause:** Network timeouts on Nominatim API during calibration run.

**Failed Locations:**
- Bethesda MD, Boulder CO, Times Square NY, Telluride CO, Jackson Hole WY
- Bend OR, Flagstaff AZ, Asheville NC, Miami Beach FL
- Park Slope Brooklyn NY, Upper West Side New York NY, Truckee CA, Walnut Creek CA
- Downtown Detroit MI, Downtown Houston TX, Downtown Indianapolis IN, Downtown Minneapolis MN
- Centennial CO, Hollywood FL, Outer Banks NC

**Fix Applied:**
- ✅ Added retry logic with exponential backoff (3 attempts)
- ✅ Added fallback coordinates for all 20 failed locations
- ✅ Improved error handling in `geocode_location()` function

### 2. Urban Cores Over-Scoring

**Pattern:** Urban cores with low target scores (35-48) are significantly over-scoring.

**Examples:**
- **Downtown Phoenix AZ**: Target 48, Score 79.2 (error +31.2)
  - Daily Urban: 25.0/30 (maxed out - likely OSM data artifacts)
  - Wild Adventure: 25.6/50 (very high for urban core)
  - Waterfront: 16.2/20
  - **Issue**: Classified as "suburban" instead of "urban_core" → missing urban core penalties

- **Downtown Dallas TX**: Target 40, Score 62.4 (error +22.4)
  - Daily Urban: 17.0/30
  - Wild Adventure: 7.3/50
  - Waterfront: 4.3/20

- **Downtown Kansas City MO**: Target 45, Score 67.9 (error +22.9)
  - Daily Urban: 17.0/30
  - Wild Adventure: 17.1/50 (high for urban core)
  - Waterfront: 2.5/20

**Root Causes:**
1. **Area Type Misclassification**: Phoenix classified as "suburban" instead of "urban_core" → missing urban core penalties
2. **Daily Urban Overflow Penalty Too Weak**: Current max penalty (8.0) may not be sufficient for extreme cases
3. **Wild Adventure Trail Cap Too High**: 2x expected may still allow too many trails for urban cores
4. **Waterfront Downweight Too Weak**: 0.5 multiplier for non-beach water may not be sufficient

### 3. Mountain Towns Under-Scoring

**Pattern:** Mountain towns with high target scores (92-97) are significantly under-scoring.

**Examples:**
- **Downtown Denver CO**: Target 92, Score 59.4 (error -32.6)
  - Daily Urban: 0.0/30 (**no parks detected!**)
  - Wild Adventure: 6.1/50 (very low despite being mountain town)
  - Waterfront: 20.0/20
  - **Issue**: Classified as "urban_core" → mountain town detection may not be working

- **Park City UT**: Target 92, Score 65.9 (error -26.1)
  - Daily Urban: 0.0/30 (**no parks detected!**)
  - Wild Adventure: 19.6/50 (low for mountain town)
  - Waterfront: 13.7/20
  - **Issue**: Classified as "exurban" → mountain town detection may not be working

**Root Causes:**
1. **Daily Urban = 0.0**: No parks detected for Denver and Park City → likely data collection issue or area type mismatch
2. **Mountain Town Detection Not Working**: Denver (urban_core) and Park City (exurban) may not be triggering mountain town detection
3. **Wild Adventure Expectations Too High**: Mountain town expectations may be too high, preventing proper scoring

## Proposed Fixes

### Fix 1: Strengthen Urban Core Penalties

**Daily Urban Outdoors:**
- Increase max overflow penalty from 8.0 to 12.0
- Strengthen penalty multipliers: `(overflow_ratio * 8.0) + (area_overflow * 4.0)`
- Apply penalty more aggressively (reduce threshold from 1.5x to 1.2x)

**Wild Adventure:**
- Reduce trail cap from 2x to 1.5x expected for urban cores
- Reduce max contributions: `max_trails_total: 8.0 → 6.0`, `max_trails_near: 4.0 → 3.0`

**Waterfront:**
- Strengthen downweight from 0.5 to 0.4 for non-beach water in urban cores

### Fix 2: Fix Mountain Town Detection

**Detection Logic:**
- Ensure Denver (urban_core with high trail count) triggers mountain town detection
- Ensure Park City (exurban) triggers mountain town detection
- Review detection thresholds: may need to lower canopy requirement for urban cores with very high trail counts

**Wild Adventure Expectations:**
- Review mountain town expectations - may be too high
- Consider lowering expectations or increasing max contributions

### Fix 3: Fix Daily Urban = 0.0 Issue

**Investigation Needed:**
- Check if Denver and Park City have parks in OSM
- Verify area type classification
- Check if radius profiles are correct
- May need to adjust expectations or add fallback scoring

### Fix 4: Area Type Classification

**Phoenix:**
- Ensure Phoenix is classified as "urban_core" not "suburban"
- May need to adjust area classification logic or manually override in calibration panel

## Next Steps

1. ✅ **Geocoding Fixes**: Applied retry logic and fallback coordinates
2. ✅ **Scoring Fixes**: Applied fixes to component scoring:
   - Strengthened Daily Urban overflow penalty (8.0 → 12.0, earlier threshold)
   - Reduced Wild Adventure max contributions for urban cores (8.0 → 6.0, 4.0 → 3.0)
   - Reduced Wild Adventure trail cap (2x → 1.5x expected)
   - Strengthened Waterfront downweight (0.5 → 0.4 for non-beach water)
3. ⏳ **Re-run Calibration**: With full 36-location panel
4. ⏳ **Analyze Results**: Check if R² improves and errors decrease
5. ⏳ **Investigate Daily Urban = 0.0**: Check Denver and Park City data collection
6. ⏳ **Fix Area Type Classification**: Ensure Phoenix is classified as "urban_core"

## Design Principles Compliance

All fixes follow HomeFit Design Principles:
- **Research-Backed**: Based on calibration data analysis, not arbitrary tuning
- **Objective Criteria**: Using area type, trail counts, canopy % - no city-name exceptions
- **Data Quality**: Addressing OSM data artifacts (urban paths tagged as trails)
- **Context-Aware**: Strengthening penalties for urban cores, improving mountain town detection

