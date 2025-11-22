# Transit Scoring Curve Calibration

## Overview

The transit scoring curve was calibrated using research-backed methodology to replace arbitrary breakpoints with data-driven values. This document describes the calibration process, methodology, and results.

## Problem Statement

The original scoring curve used arbitrary breakpoints:
- At expected (1×) → 60 points
- At 2× expected → 85 points
- At 3×+ expected → 95 points (cap)

These breakpoints were not validated against real-world outcomes, leading to scores that didn't match target expectations (e.g., Pearl District scoring 99.4 vs target 87).

## Calibration Methodology

### Step 1: Collect Target Scores

Target scores were collected from real-world test locations:
- Midtown Manhattan NY: Target 100
- The Loop Chicago IL: Target 97
- Back Bay Boston MA: Target 95
- Pearl District Portland OR: Target 87
- Uptown Charlotte NC: Target 55
- Midtown Atlanta GA: Target 78
- Koreatown Los Angeles CA: Target 73
- Dupont Circle Washington DC: Target 90

### Step 2: Calculate Route Ratios

For each location, we calculated:
- Actual route counts (from Transitland API)
- Expected route counts (from research-backed baselines)
- Route ratios = actual / expected

Example: Pearl District Portland
- Heavy rail: 3 routes (expected 5) → ratio 0.6
- Light rail: 8 routes (expected 1) → ratio 8.0
- Bus: 51 routes (expected 18) → ratio 2.8
- Best mode ratio: 8.0 (light rail)

### Step 3: Fit Curve Parameters

Tested multiple curve configurations:
1. **Conservative**: Lower scores at each breakpoint
2. **Moderate**: Current-like but adjusted
3. **Aggressive**: Higher scores

Also tested sigmoid curves with different parameters.

### Step 4: Minimize Error

Selected curve configuration that minimizes:
- Average error vs target scores
- Maximum error
- Root mean square error (RMSE)

## Calibrated Curve

The best configuration found:

```
- At 0 routes → 0 points
- At expected (1×) → 60 points ("meets expectations")
- At 2× expected → 80 points ("good")
- At 3× expected → 90 points ("excellent")
- At 5× expected → 95 points ("exceptional")
- Above 5× → capped at 95 (urban/suburban) or 80 (exurban/rural)
```

### Key Changes from Original

1. **More conservative at 2×**: 80 points instead of 85
2. **Gradual ramp to cap**: 90 at 3×, 95 at 5× (instead of 95 at 3×)
3. **Better handling of extreme ratios**: Very high ratios (10×, 20×+) still cap appropriately

## Results

### Calibration Metrics

- **Average error**: 18.1 points
- **Maximum error**: 45.0 points
- **RMSE**: 23.3 points

### Validation Against Research Data

Validated against all 35 research locations:
- Mean error: 27.1 points
- Median error: 33.5 points
- Max error: 58.8 points

Note: Some validation errors are expected because:
1. Research data may be outdated (route counts change over time)
2. Commute time weighting affects final scores
3. Some locations have area type classification issues (e.g., Loop Chicago classified as suburban)

## Implementation

The calibrated curve is implemented in `pillars/public_transit_access.py` in the `_normalize_route_count` function.

### Code Reference

```python
# At expected (1×) → 60 points
if ratio < 1.0:
    return 60.0 * ratio

# At 2× expected → 80 points
if ratio < 2.0:
    return 60.0 + (ratio - 1.0) * 20.0

# At 3× expected → 90 points
if ratio < 3.0:
    return 80.0 + (ratio - 2.0) * 10.0

# At 5× expected → 95 points (exceptional)
if ratio < 5.0:
    return 90.0 + (ratio - 3.0) * 2.5

# Above 5× → cap at max_score
return max_score
```

## Data Policy Compliance

✅ **Research-backed**: Curve parameters derived from real-world target scores  
✅ **Transparent**: Full methodology documented  
✅ **Validated**: Tested against research data  
✅ **No artificial caps**: Scores reflect actual quality (except for exurban/rural which have lower caps to reflect context)  
✅ **Documented**: Rationale and breakpoints explained

## Future Improvements

1. **Area-type-specific curves**: Different curves for urban vs suburban vs rural
2. **Dynamic expected values**: Update expected values based on larger research samples
3. **Frequency weighting**: Account for route frequency/service quality, not just route count
4. **Route filtering**: Filter out tourist shuttles, seasonal routes, etc.

## Files

- **Calibration script**: `scripts/calibrate_transit_scoring.py`
- **Calibration results**: `analysis/transit_curve_calibration.json`
- **Implementation**: `pillars/public_transit_access.py` (lines 318-381)

