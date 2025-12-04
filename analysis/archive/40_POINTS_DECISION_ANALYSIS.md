# 40 Points Decision Analysis

## Question

**How did we determine the original 40 points decision? Is this data-backed?**

## Findings

### Calibration Script Recommendation

The calibration script (`scripts/calibrate_transit_scoring.py`) was run and recommended:

```json
{
  "at_expected": 60.0,  // 60 points at 1× expected
  "at_good": 80.0,      // 80 points at 2× expected
  "at_excellent": 90.0, // 90 points at 3× expected
  "at_exceptional": 95.0 // 95 points at 5× expected
}
```

**Calibration Metrics:**
- Average error: 18.1 points
- Maximum error: 45.0 points
- RMSE: 23.3 points

### Current Implementation

The current code uses **40 points at 1× expected**, not 60 points.

```python
# At expected (1×) → 40 points (more conservative)
if ratio < 1.0:
    return 40.0 * ratio
```

### When Did This Change?

Based on git history:
1. **Initial calibration** (commit `843e82b`): Calibrated curve with 60 points at 1×
2. **Later change** (commit `ec194da`): Changed to "more conservative" with 40 points at 1×

The commit message says: "Make transit scoring curve more conservative"

### Why Was It Changed?

The documentation says:
- "At expected (1×) → 40 points (**more conservative**)" (emphasis added)
- The comment indicates this was a deliberate decision to be "more conservative"

However, **there is no documented rationale** for why 40 was chosen over the calibrated 60.

### Is This Data-Backed?

**Answer: ⚠️ PARTIALLY**

1. ✅ **Calibration script was data-backed**: The 60-point recommendation came from analyzing target scores vs route ratios
2. ❌ **40-point decision was NOT data-backed**: The change from 60 to 40 appears to be a manual adjustment labeled "more conservative" without:
   - New calibration data
   - Validation against targets
   - Documented rationale

### Impact on Bronxville NY

**Bronxville NY:**
- 1 heavy rail route
- Expected: 1 route (for commuter_rail_suburb)
- Ratio: 1.0×
- **Current score: 40 points** (from 1× = 40)
- **If using calibrated 60: would be 60 points**

**Gap to target (85):**
- Current: 40 → need +45 points
- If 60: 60 → need +25 points

### Recommendation

**The 40-point decision violates Design Principles:**

1. ❌ **Not Research-Backed**: Changed from calibrated 60 to arbitrary 40 without new data
2. ❌ **Not Transparent**: No documented rationale for the change
3. ❌ **Potentially Artificially Tuned**: May have been adjusted to match specific target scores

**Options:**

1. **Revert to calibrated 60 points** (data-backed)
2. **Re-calibrate with updated target scores** (if targets changed)
3. **Document rationale** if 40 was chosen for a specific reason

### Next Steps

1. Check if there was a specific reason for the 40-point decision
2. If not, consider reverting to 60 points (calibrated value)
3. If targets have changed, re-run calibration script with new targets
4. Document the decision-making process

