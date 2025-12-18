# Healthcare Access Pillar Tuning Changes

## Problem Identified

Several urban/suburban locations were scoring very low (2.1-18.9) on healthcare access, despite being in areas that should have reasonable healthcare infrastructure. Analysis revealed:

1. **OSM Data Gaps**: When OSM queries fail (timeouts, rate limits, network errors), the pillar was scoring 0 for pharmacies, clinics, and doctors, even in urban areas.
2. **Strict Threshold**: The `_calibrated_ratio_score()` function had a threshold of 0.05, meaning locations with minimal facilities relative to high expectations would score 0.0.
3. **Inconsistent OSM Availability**: OSM data availability is inconsistent - same locations score differently on different runs.

## Root Cause

- OSM API failures result in 0 pharmacies/clinics/doctors, even in urban areas
- Only hospitals had a fallback database (`MAJOR_HOSPITALS`)
- No fallback mechanism for pharmacies, clinics, or doctors when OSM fails
- Threshold of 0.05 was too strict for locations with minimal facilities

## Changes Made

### 1. Lowered Ratio Threshold and Added Minimum Score Floor

**File**: `pillars/healthcare_access.py`

- **Lowered threshold**: Changed from 0.05 to 0.0 (only truly zero ratios get 0.0)
- **Added minimum score floor**: Any positive ratio now gets at least 2% of max_score (e.g., 0.3 points for pharmacies, 0.5 for primary care)
- **Improved small ratio handling**: Ratios between 0.01-0.1 now get scaled scores with minimum floor protection

```python
# Minimum score floor: Ensure any positive ratio gets at least 2-5% of max_score
min_score_floor = max_score * 0.02  # 2% minimum
```

### 2. Added Fallback Scoring for Urban/Suburban Areas

**File**: `pillars/healthcare_access.py`

When OSM query fails (`query_failed=True`) and we're in an urban/suburban/high-density area, apply conservative fallback scores:

- **Primary Care**: 10-15 points (based on area type/density)
- **Pharmacies**: 6-10 points (based on area type/density)
- **Specialized Care**: 4-8 points (only if hospitals available from fallback database)

Fallback scores by area type:
- **Urban Core** (density > 5000): Primary Care 15.0, Pharmacies 10.0, Specialized 8.0
- **Urban Residential** (density > 2000): Primary Care 12.0, Pharmacies 8.0, Specialized 6.0
- **Suburban** (density > 1500): Primary Care 10.0, Pharmacies 6.0, Specialized 4.0

### 3. Improved Detection Logic

- Detects OSM query failures via `query_failed` flag
- Checks area type and density to determine if fallback should apply
- Only applies fallback when OSM fails AND location is urban/suburban/high-density
- Preserves normal scoring when OSM data is available

## Expected Impact

1. **Reduced Zero Scores**: Urban/suburban locations will no longer score 0 for pharmacies/primary care when OSM fails
2. **Better Handling of OSM Data Gaps**: Conservative minimum scores account for OSM incompleteness
3. **Smoother Distribution**: Minimum score floors prevent harsh cutoffs for locations with minimal facilities
4. **Maintained Accuracy**: High-scoring locations unaffected; fallback only applies when OSM fails

## Testing Results

### Before Tuning
- **Pilsen Chicago IL** (when OSM failed): 17.1/100 (Hospital: 14.5, Primary Care: 0.0, Pharmacies: 0.0, Specialized: 0.0, Emergency: 2.1)
- **Seminole Heights Tampa FL**: 2.1/100 (when OSM failed)

### After Tuning
- **Pilsen Chicago IL** (when OSM failed): 50.1/100 (Hospital: 14.5, Primary Care: 15.0, Pharmacies: 10.0, Specialized: 8.0, Emergency: 2.1)
  - **Improvement**: +33.0 points when OSM fails
- **Pilsen Chicago IL** (when OSM succeeds): 100.0/100 (normal scoring)
- **Seminole Heights Tampa FL** (when OSM succeeds): 100.0/100 (normal scoring)

**Note**: OSM data availability is inconsistent. The fallback ensures reasonable scores even when OSM fails, while normal scoring applies when OSM data is available.

## Isolation

All changes are confined to `pillars/healthcare_access.py`:
- Modified `_calibrated_ratio_score()` function (threshold and minimum floor)
- Added fallback detection logic after OSM query
- Added fallback score application in primary care, pharmacy, and specialized care scoring sections
- No changes to other pillars or shared infrastructure

## Notes

- Fallback scores are conservative minimums, not full scores
- Fallback only applies when OSM query fails AND location is urban/suburban/high-density
- Rural locations with truly no facilities will still score appropriately low
- Hospital fallback database (`MAJOR_HOSPITALS`) continues to work as before
