# Transit Scoring Diagnosis - Round 6 Results

## Executive Summary

Analysis of Round 6 transit scores reveals **three primary issues**:

1. **Missing/Undercounted Routes** - Several locations show suspiciously low route counts
2. **Expected Value Mismatches** - Some area types have expectations that don't match actual transit reality
3. **Scoring Curve Conservatism** - The curve may be too conservative for locations with extensive single-mode systems

---

## Issue 1: Missing/Undercounted Routes (Causing Low Scores)

### Koreatown LA (36.8 vs 73 target) - **CRITICAL**
- **Heavy rail**: 2 routes (expected 5) → 0.4× ratio → 16 points
- **Bus**: 16 routes (expected 18) → 0.89× ratio → 35.6 points
- **Data quality**: **poor (32 confidence)** ⚠️
- **Diagnosis**: Only 18 total routes is suspiciously low for Koreatown. Metro has 6 lines, many bus routes. **Routes are likely missing from Transitland API.**
- **Impact**: Missing routes → low ratios → low scores

### Back Bay Boston (69 vs 95 target)
- **Heavy rail**: 10 routes (expected 5) → 2× ratio → 55 points ✓
- **Light rail**: 4 routes (expected 4) → 1× ratio → 40 points ✓
- **Bus**: 44 routes (expected 18) → 2.44× ratio → 59.4 points ✓
- **Issue**: Despite having all 3 modes with good counts, score is only 69. **Multimodal bonus (+8) is too small** for truly exceptional systems.
- **Impact**: Best mode (59.4) + multimodal bonus (8) = 67.4, but commute time weighting brings it to 69. The system is penalized for not having a single dominant mode.

### The Loop Chicago (84.4 vs 97 target)
- **Heavy rail**: 38 routes (expected 5) → 7.6× ratio → 78.9 points ✓
- **Bus**: 46 routes (expected 18) → 2.56× ratio → 60.6 points ✓
- **Issue**: Heavy rail is excellent (78.9), but total score is capped by multimodal bonus structure. **Chicago's extensive system should score higher.**
- **Impact**: Best mode (78.9) + multimodal bonus (5) = 83.9 ≈ 84.4. The system is working correctly, but **the cap at 95 may be too low** for exceptional systems.

---

## Issue 2: Expected Value Mismatches

### Midtown Atlanta (59.3 vs 78 target)
- **Heavy rail**: 2 routes (expected 5) → 0.4× ratio → 16 points
- **Bus**: 39 routes (expected 18) → 2.17× ratio → 56.7 points
- **Issue**: MARTA has 4 heavy rail lines, but only 2 routes detected. **Either routes are missing OR the expected value of 5 is too high** for Atlanta's actual system size.
- **Diagnosis**: Need to verify if MARTA's 4 lines are being counted as 2 routes (maybe some lines share route IDs?), or if routes are genuinely missing.

### Uptown Charlotte (72.9 vs 55 target) - **OVER-SCORING**
- **Light rail**: 2 routes (expected 0 for urban_residential) → **fallback logic** → 55 points
- **Bus**: 47 routes (expected 15) → 3.13× ratio → 65.5 points
- **Issue**: Light rail uses fallback (55 points) because `expected_light_rail_routes = 0` for urban_residential. **Fallback is too generous for 2 routes.**
- **Impact**: Best mode (65.5) + multimodal bonus (5) = 70.5, but commute time (95) boosts it to 72.9. **The fallback logic for unexpected modes is inflating scores.**

### Bronxville NY (61 vs 85 target)
- **Heavy rail**: 1 route (expected 0 for suburban) → **fallback logic** → 40 points
- **Bus**: 6 routes (expected 13) → 0.46× ratio → 18.4 points
- **Issue**: Commuter rail (1 route) uses fallback (40 points) because suburban has `expected_heavy_rail_routes = 0`. **Should be detected as commuter_rail_suburb** (expected 1), which would give proper ratio-based scoring.
- **Diagnosis**: Commuter rail suburb detection may be failing. Bronxville should use `commuter_rail_suburb` expectations (expected_heavy=1), not suburban fallback.

---

## Issue 3: Scoring Curve Conservatism

### Locations with Extensive Single-Mode Systems

**Midtown Manhattan (99.1 vs 100 target)** - Working correctly
- Heavy rail: 64 routes (expected 5) → 12.8× ratio → 88 points
- Bus: 392 routes (expected 18) → 21.8× ratio → 95 points (cap)
- **This is working as intended** - NYC's exceptional system scores appropriately.

**The Loop Chicago (84.4 vs 97 target)**
- Heavy rail: 38 routes → 7.6× ratio → 78.9 points
- **Issue**: Chicago's heavy rail system is extensive (38 routes), but only scores 78.9. The curve may be **too conservative between 5× and 12× expected**.
- **Current curve**: 5× → 72, 8× → 80, 12× → 88
- **Suggestion**: Consider steeper growth between 5× and 12× for exceptional systems.

---

## Issue 4: Data Quality Problems

### Koreatown LA
- **Data quality: poor (32 confidence)**
- **Total routes: 18** (suspiciously low)
- **Diagnosis**: Transitland API may be missing routes, or the query radius (1500m for urban_core) may be too small for Koreatown's sprawl.

### Shaker Heights OH
- **Data quality: very_poor (23 confidence)**
- **Area type: rural** (incorrect - should be suburban or commuter_rail_suburb)
- **Issue**: Area type misclassification is causing wrong expected values.

---

## Root Causes Summary

### 1. Missing Route Data (High Priority)
- **Koreatown LA**: Only 18 routes detected (should be 50+)
- **Midtown Atlanta**: Only 2 heavy rail routes (MARTA has 4 lines)
- **Possible causes**:
  - Transitland API coverage gaps
  - Query radius too small (1500m for urban_core)
  - Route deduplication too aggressive
  - GTFS feed quality issues

### 2. Expected Value Calibration (Medium Priority)
- **urban_core heavy rail**: Expected 5 may be too high for some cities (Atlanta)
- **urban_residential light rail**: Expected 0 causes fallback logic, which is too generous
- **suburban heavy rail**: Expected 0 causes fallback, but should use commuter_rail_suburb detection

### 3. Scoring Curve Shape (Low Priority)
- Curve may be too conservative between 5× and 12× expected
- Multimodal bonus (+5/+8) may be too small for truly exceptional systems
- Cap at 95 may be too low for world-class systems (NYC, Chicago)

### 4. Area Type Misclassification (Medium Priority)
- **Shaker Heights**: Classified as "rural" but should be "suburban" or "commuter_rail_suburb"
- Causes wrong expected values and scoring

---

## Recommendations

### Immediate Fixes (P0)

1. **Investigate route counting for Koreatown LA**
   - Check Transitland API coverage
   - Verify query radius (1500m may be too small)
   - Check route deduplication logic

2. **Fix commuter rail suburb detection**
   - Bronxville NY should be detected as commuter_rail_suburb
   - Verify detection logic (metro distance, population check)

3. **Review fallback logic for unexpected modes**
   - Uptown Charlotte's light rail fallback (55 points for 2 routes) is too high
   - Consider using ratio-based scoring even when expected=0, with a lower baseline

### Short-term Fixes (P1)

4. **Adjust expected values based on research**
   - Review urban_core heavy rail expected (5 may be too high for some metros)
   - Consider area-type-specific expected values for light rail

5. **Improve area type classification**
   - Fix Shaker Heights misclassification (rural → suburban/commuter_rail_suburb)

6. **Enhance multimodal bonus**
   - Consider larger bonus for systems with 3 strong modes (Back Bay Boston)
   - Or adjust curve to reward exceptional single-mode systems more

### Long-term Improvements (P2)

7. **Review scoring curve conservatism**
   - Consider steeper growth between 5× and 12× expected
   - Evaluate if cap at 95 should be higher for world-class systems

8. **Add route quality metrics**
   - Frequency, coverage, connectivity (not just count)
   - Would help distinguish between extensive but poor systems vs. excellent systems

---

## Data Quality Indicators

| Location | Data Quality | Confidence | Issue |
|----------|-------------|------------|-------|
| Koreatown LA | poor | 32 | Missing routes |
| Midtown Atlanta | good | 73 | Routes may be undercounted |
| Back Bay Boston | excellent | 90 | Scoring curve too conservative |
| The Loop Chicago | excellent | 90 | Scoring curve too conservative |
| Shaker Heights | very_poor | 23 | Area type misclassification |

---

## Next Steps

1. **Verify route counts** for Koreatown LA and Midtown Atlanta against official transit agency data
2. **Test commuter rail suburb detection** for Bronxville NY
3. **Review fallback logic** for unexpected modes (light rail in urban_residential)
4. **Consider research pass** to validate expected values for urban_core heavy rail

