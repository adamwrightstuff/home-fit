# Tuning Data Sources Summary

## Overview

Different datasets were used for different purposes:

1. **177 locations** (`pillar_regression_data.json`): Used for **statistical analysis** (identifying variance issues)
2. **56 locations** (`active_outdoors_tuning_from_ridge.json`): Used for **calibration** (determining CAL_A, CAL_B)
3. **Various locations** (`neighborhood_amenities_calibration_results.json`): Used for **calibration** (determining area-type-specific parameters)

## Dataset Breakdown

### 177 Locations - Statistical Analysis Only

**File**: `analysis/pillar_regression_data.json`

**Purpose**: 
- Identify pillars with low variance
- Calculate statistics (mean, std, min, max) for each pillar
- Detect convergence issues

**Contains**:
- Summary statistics for each pillar (count=177)
- Correlation matrices
- **NOT individual location data with target scores**

**Used For**:
- ✅ Diagnosing low variance issues (`natural_beauty`, `active_outdoors`)
- ✅ Identifying which pillars need tuning
- ❌ **NOT used for calibration** (no target scores available)

### 56 Locations - Active Outdoors Calibration

**File**: `analysis/active_outdoors_tuning_from_ridge.json`

**Purpose**:
- Determine calibration parameters for `active_outdoors`
- Calculate optimal `CAL_A` and `CAL_B` for linear calibration

**Contains**:
- 56 individual locations with:
  - Target scores ("actual")
  - Raw component scores
  - Area types
  - Coordinates
- Calibration parameters: `CAL_A = 0.3445`, `CAL_B = 67.8642`
- Calibration statistics: MAE=6.97, n_samples=56

**Used For**:
- ✅ **Calibration** of `active_outdoors` pillar
- ✅ Determining linear transform parameters

**Source**: Ridge regression CSV (from `/Users/adamwright/Downloads/ridge_regression_predictions.csv`)

### Neighborhood Amenities Calibration

**File**: `analysis/neighborhood_amenities_calibration_results.json`

**Purpose**:
- Determine area-type-specific calibration parameters
- Calculate optimal `a` and `b` per area type

**Contains**:
- Individual locations with target scores
- Area-type-specific calibration parameters
- Calibration statistics

**Used For**:
- ✅ **Calibration** of `neighborhood_amenities` pillar
- ✅ Area-type-specific linear transforms

## Answer: Were 177 Locations Used for Tuning?

### Short Answer: **NO**

The 177 locations were used for:
- ✅ **Statistical analysis** (identifying problems)
- ✅ **Diagnosis** (finding low variance)
- ❌ **NOT for calibration** (no target scores in that dataset)

### Calibration Used:
- **active_outdoors**: 56 locations (from `active_outdoors_tuning_from_ridge.json`)
- **neighborhood_amenities**: Separate calibration dataset (from `neighborhood_amenities_calibration_results.json`)

## Why Not Use 177 Locations for Calibration?

The `pillar_regression_data.json` file contains:
- ✅ Summary statistics (mean, std, etc.)
- ✅ Correlation matrices
- ❌ **No individual location target scores**
- ❌ **No raw component scores per location**

Without target scores and raw scores per location, we cannot calculate calibration parameters.

## Recommendation: Use 177 Locations for Future Calibration

If we want to use all 177 locations for calibration:

1. **Need to collect**:
   - Target scores for all 177 locations
   - Raw component scores for all 177 locations
   - Area types for all 177 locations

2. **Then calculate**:
   - Global calibration parameters (like active_outdoors)
   - Area-type-specific parameters (like neighborhood_amenities)

3. **Benefits**:
   - Larger sample size (177 vs 56)
   - More representative of full dataset
   - Better statistical power

## Current Status

| Pillar | Tuning Dataset | Sample Size | Status |
|--------|---------------|-------------|--------|
| active_outdoors | `active_outdoors_tuning_from_ridge.json` | 56 locations | ✅ Calibrated |
| neighborhood_amenities | `neighborhood_amenities_calibration_results.json` | Various | ✅ Calibrated |
| natural_beauty | None | N/A | ⚠️ No calibration data available |
| Other pillars | N/A | N/A | ✅ No calibration needed (pure data-backed) |

## Next Steps

1. **For natural_beauty**: Collect target scores for calibration (if needed)
2. **For future improvements**: Consider collecting target scores for all 177 locations to improve calibration
3. **For validation**: Use 177 locations to validate calibrated scores (not for calibration itself)
