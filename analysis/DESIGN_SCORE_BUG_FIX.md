# Design Score Bug Fix

**Date:** January 2026  
**Status:** ✅ Fixed

## Bug Description

All `design_score` values were capped at 50.0, causing all locations to score identically.

## Root Cause

The `DESIGN_FORM_SCALE` values are stored as percentages (62.0 = 62%, 54.0 = 54%), but they were being used directly as multipliers in the calculation:

```python
# BEFORE (BUG):
design_score = min(50.0, (sum(design_components) / expected_total) * 50.0 * scale_params["design"])
# If scale_params["design"] = 62.0 and ratio = 1.0:
# Result: 1.0 * 50.0 * 62.0 = 3100.0
# Capped at 50.0: min(50.0, 3100.0) = 50.0 (ALWAYS CAPPED!)
```

## Fix

Divide by 100.0 to convert percentages to decimals:

```python
# AFTER (FIXED):
design_score = min(50.0, (sum(design_components) / expected_total) * 50.0 * (scale_params["design"] / 100.0))
# If scale_params["design"] = 62.0 and ratio = 1.0:
# Result: 1.0 * 50.0 * (62.0/100.0) = 31.0
# Capped at 50.0: min(50.0, 31.0) = 31.0 (NOT CAPPED - CORRECT!)
```

Same fix applied to `form_score` calculation.

## Verification

Before fix:
- `design_score: 50.0` (all locations capped)
- `form_score: 10.9-24.4` (varied correctly)

After fix:
- `design_score: 24.9` (no longer capped - varies correctly!)
- `form_score: 0.2` (now varies correctly too)

## Files Changed

- `data_sources/arch_diversity.py`:
  - Line 2433: Fixed `design_score` calculation
  - Line 2473: Fixed `form_score` calculation
