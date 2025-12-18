# Pillar Design Principles Audit

## Summary

**VIOLATIONS FOUND:**
1. ❌ **healthcare_access.py**: Uses CALIBRATED_CURVE_PARAMS tuned from target scores
2. ❌ **public_transit_access.py**: Uses calibrated breakpoints tuned from target scores

**CLEAN (No Violations):**
- ✅ active_outdoors.py - Calibration removed
- ✅ neighborhood_amenities.py - Calibration removed  
- ✅ natural_beauty.py - Calibration removed
- ✅ built_beauty.py - No calibration
- ✅ air_travel_access.py - No calibration
- ✅ housing_value.py - No calibration
- ✅ schools.py - No calibration
- ✅ neighborhood_beauty.py - Only has guardrail checks, not calibration

## Detailed Findings

### ❌ healthcare_access.py - VIOLATION

**Issue**: Uses `CALIBRATED_CURVE_PARAMS` that are "calibrated from 12 locations with LLM-researched target scores"

**Code**:
```python
CALIBRATED_CURVE_PARAMS = {
    'at_expected': 50.0,      # Score at 1.0× expected
    'at_good': 85.0,          # Score at 1.5× expected
    'at_excellent': 85.0,     # Score at 2.5× expected
    'at_exceptional': 95.0,   # Score at 3.0× expected
    ...
}
```

**Used in**: `_calibrated_ratio_score()` function, called for:
- Hospital count scoring
- Primary care scoring
- Specialty care scoring
- Emergency services scoring
- Pharmacy scoring

**Violation**: Tuning toward target scores violates "No tuning toward target scores" principle.

**Fix**: Replace calibrated curve with data-backed scoring curve based on objective metrics (ratio thresholds), not target scores.

### ❌ public_transit_access.py - VIOLATION

**Issue**: Uses calibrated breakpoints "Calibrated using target scores vs route ratios"

**Code**:
```python
# Research-backed calibrated breakpoints derived from empirical analysis
# Calibrated using target scores vs route ratios.
# Calibration metrics: Avg error=18.1, Max error=45.0, RMSE=23.3

# Breakpoints:
# - At expected (1×) → 60 points ("meets expectations")
# - At 2× expected → 80 points ("good")
# - At 3× expected → 90 points ("excellent")
# - At 5× expected → 95 points ("exceptional")
```

**Violation**: Breakpoints are "calibrated using target scores" - this is tuning toward targets.

**Fix**: Replace with data-backed breakpoints based on objective transit quality metrics, not target scores.

### ✅ neighborhood_beauty.py - CLEAN

**Issue**: Has `_check_calibration_guardrails()` function

**Analysis**: This is a **guardrail check**, not calibration. It checks if scores are outside expected ranges and alerts, but doesn't modify scores. This is acceptable per design principles (transparent metadata, debugging).

## Recommended Fixes

1. **healthcare_access.py**: Replace `CALIBRATED_CURVE_PARAMS` with data-backed ratio thresholds
2. **public_transit_access.py**: Replace calibrated breakpoints with data-backed transit quality thresholds

Both should use objective metrics (e.g., "2× expected = good service") not target scores.
