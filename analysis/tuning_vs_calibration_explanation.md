# Tuning vs Calibration: Why Some Pillars Didn't Need Target Scores

## Key Distinction

### Tuning (Problem-Based Fixes)
- **Uses**: Statistics from 177 locations (mean, std, distribution patterns)
- **Identifies**: Problems (zeros, low variance, bimodal distributions)
- **Fixes**: Scoring logic directly (thresholds, fallbacks, radius extensions)
- **No target scores needed**: We fix the problem, not calibrate to targets

### Calibration (Regression-Based Parameters)
- **Uses**: Target scores (ground truth) + raw component scores
- **Identifies**: Optimal calibration parameters (CAL_A, CAL_B)
- **Fixes**: Applies linear transform to align scores with targets
- **Target scores required**: Need to know what scores "should be"

## How We Tuned Other Pillars (Without Target Scores)

### 1. air_travel_access

**Problem Identified from 177 Locations:**
- Statistics showed: 36.7% scored 0, 46.9% scored ≥90 (bimodal)
- Mean 53.77 vs Median 84.1 (many zeros pulling down average)
- **No target scores needed** - the problem was clear from distribution

**Fix Applied:**
- Extended search radius from 100km → 150km
- Added decay curves for 100-150km range
- **Direct fix to scoring logic** - no calibration parameters

**Why No Target Scores Needed:**
- Problem was obvious: hard cutoff at 100km causing zeros
- Fix was clear: extend radius and add decay
- No need to know "correct" scores - just fix the bug

### 2. healthcare_access

**Problem Identified from 177 Locations:**
- Statistics showed: Many urban locations scoring very low (2.1-18.9)
- Analysis revealed: OSM data gaps causing zeros
- **No target scores needed** - the problem was clear from low scores

**Fix Applied:**
- Added fallback scoring for urban/suburban areas
- Lowered threshold from 0.05 to 0.0
- Added minimum score floors
- **Direct fix to scoring logic** - no calibration parameters

**Why No Target Scores Needed:**
- Problem was obvious: zeros in urban areas (shouldn't happen)
- Fix was clear: add fallback when OSM fails
- No need to know "correct" scores - just fix the bug

### 3. public_transit_access

**Problem Identified from 177 Locations:**
- Statistics showed: Many urban locations scoring 0
- Analysis revealed: Transitland API failures causing zeros
- **No target scores needed** - the problem was clear from zeros

**Fix Applied:**
- Added fallback scoring based on commute_time
- Conservative minimum floors for urban areas
- **Direct fix to scoring logic** - no calibration parameters

**Why No Target Scores Needed:**
- Problem was obvious: zeros in urban areas (shouldn't happen)
- Fix was clear: add fallback when Transitland fails
- No need to know "correct" scores - just fix the bug

### 4. housing_value

**Problem Identified from 177 Locations:**
- Statistics showed: Many urban locations scoring 0
- Analysis revealed: Census API data gaps causing zeros
- **No target scores needed** - the problem was clear from zeros

**Fix Applied:**
- Added fallback scoring for urban/suburban areas
- Conservative minimum floors based on area type
- **Direct fix to scoring logic** - no calibration parameters

**Why No Target Scores Needed:**
- Problem was obvious: zeros in urban areas (shouldn't happen)
- Fix was clear: add fallback when Census fails
- No need to know "correct" scores - just fix the bug

## Why Calibration Needs Target Scores

### For active_outdoors and natural_beauty:

**Problem Identified:**
- Statistics showed: Low variance (convergence) - std=0.13, std=0.00
- **But**: Scores aren't "wrong" - they're just converging
- **Fix needed**: Not a bug fix, but a calibration adjustment

**Why Target Scores Needed:**
- Can't fix convergence by changing logic (logic is correct)
- Need to know what scores "should be" to calibrate
- Regression analysis finds optimal CAL_A, CAL_B to align with targets
- **Without targets**: Can't calculate calibration parameters

## Summary Table

| Pillar | Problem Type | Fix Type | Target Scores Needed? | Why |
|--------|-------------|----------|----------------------|-----|
| air_travel_access | Hard cutoff bug | Logic fix (radius extension) | ❌ No | Problem obvious, fix clear |
| healthcare_access | Data gap bug | Logic fix (fallback scoring) | ❌ No | Problem obvious, fix clear |
| public_transit_access | Data gap bug | Logic fix (fallback scoring) | ❌ No | Problem obvious, fix clear |
| housing_value | Data gap bug | Logic fix (fallback scoring) | ❌ No | Problem obvious, fix clear |
| neighborhood_amenities | Calibration needed | Regression calibration | ✅ Yes | Need to align with targets |
| active_outdoors | Convergence issue | Regression calibration | ✅ Yes | Need to align with targets |
| natural_beauty | Convergence issue | Regression calibration | ✅ Yes | Need to align with targets |

## Key Insight

**Tuning (bug fixes)**: Uses statistics to identify problems → Fix logic directly
- Example: "Many zeros in urban areas" → Add fallback scoring
- No target scores needed - we know zeros are wrong

**Calibration (parameter optimization)**: Uses target scores → Find optimal parameters
- Example: "Scores converging" → Need to know what they should be
- Target scores required - need ground truth to calibrate

## Conclusion

The 177 locations regression analysis was used for:
- ✅ **Problem identification** (statistics, distributions, patterns)
- ✅ **Tuning** (fixing bugs, adding fallbacks, adjusting thresholds)
- ❌ **NOT for calibration** (calibration requires target scores)

For calibration, we need target scores because we're optimizing parameters to match ground truth, not fixing bugs.
