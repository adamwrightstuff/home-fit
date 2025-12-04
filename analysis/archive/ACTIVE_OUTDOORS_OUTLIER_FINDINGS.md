# Active Outdoors v2 Outlier Investigation Findings

**Date:** 2024-12-XX  
**Diagnostic Script:** `scripts/diagnose_active_outdoors_outliers.py`  
**Diagnostic Data:** `analysis/active_outdoors_outlier_diagnostics.json`

---

## Key Findings

### Times Square NY (Over-scoring: +34.0 points)

**Issue:** Dense urban core scoring 69.0 when target is 35.0

**Root Causes:**
1. **Too many parks detected:** 17 parks within 800m (expected: 8)
   - Total park area: 11.13 hectares (expected: 3 ha)
   - This inflates Daily Urban Outdoors score to 23.4/30
   
2. **Water access over-scoring:** 308 water features detected, closest at 430m
   - Many are likely false positives (coastline segments, small water features)
   - Waterfront Lifestyle: 12.8/20 (too high for dense urban core)
   
3. **Trail data issue:** Summary shows 95 trails total, 25 within 5km
   - But diagnostic shows only 1 hiking trail in 2km radius
   - Discrepancy suggests data aggregation issue
   - Wild Adventure: 16.8/50 (reasonable, but combined with other issues)

**Recommendations:**
- **Reduce Daily Urban Outdoors for dense cores:** Add penalty or cap for urban_core when park count/area exceeds expectations significantly
- **Filter water features:** Exclude small/coastline segments for dense urban cores, or reduce weight
- **Investigate trail data aggregation:** Check why summary shows 95 trails but query shows 1

---

### Boulder CO (Under-scoring: -19.5 points)

**Issue:** Mountain town scoring 74.8 when target is 95.0

**Root Causes:**
1. **Trail detection issue:** Only 1 hiking trail found within 2km radius
   - Closest trail: "Boulder Open Space and Mountain Parks" at 6,080m
   - But summary shows 95 trails total, 25 within 5km
   - **Wild Adventure: 23.1/50** (too low for mountain town)
   
2. **Wrong area type:** Classified as `urban_core` but should be treated as mountain town
   - Uses urban_core expectations (2 trails expected within 15km)
   - Mountain towns need higher trail expectations
   
3. **Tree canopy reasonable:** 18.5% (contributes to wild adventure)
4. **Water access reasonable:** 13 water features, closest at 1.3km

**Recommendations:**
- **Mountain town detection:** Add objective criteria (elevation + trail density) to detect mountain towns
- **Increase trail expectations for mountain towns:** Similar to commuter_rail_suburb pattern in transit
- **Fix trail query radius:** 2km may be too small; should use 15km for trail detection
- **Investigate OSM trail data:** Boulder has extensive trail network that may not be properly tagged in OSM

---

### Downtown Las Vegas NV (Over-scoring: +24.9 points)

**Issue:** Desert location scoring 60.0 when target is 42.0

**Root Causes:**
1. **Water features detected:** OSM query returned empty, but water component still scored
   - May be coastline fallback or false positive
   - Need to check actual water features found
   
2. **Desert location:** Should have very low outdoor access expectations
   - No climate/desert detection currently
   - Uses standard suburban expectations

**Recommendations:**
- **Add desert/climate detection:** Reduce water access expectations for desert locations
- **Review water feature filtering:** Ensure false positives are excluded
- **Area-type-specific water expectations:** Desert locations should have near-zero water expectations

---

### Downtown Denver CO (Under-scoring: -20.0 points)

**Issue:** Mountain city scoring 67.7 when target is 92.0

**Root Causes:**
1. **Similar to Boulder:** Classified as `urban_core` but is a mountain city
   - Needs mountain town detection
   - Trail expectations too low
   
2. **OSM data quality:** May have incomplete trail data

**Recommendations:**
- **Same as Boulder:** Mountain town detection and higher trail expectations
- **Investigate OSM trail coverage:** Denver area may need better trail tagging

---

## Common Patterns

### 1. Urban Core Over-Scoring
- **Times Square:** Too many parks detected (17 vs 8 expected)
- **Water features:** False positives from coastline/small features
- **Solution:** Add urban core penalties or caps for excessive park counts

### 2. Mountain Town Under-Scoring
- **Boulder, Denver:** Classified as urban_core but are mountain towns
- **Trail expectations too low:** Using urban_core expectations (2 trails) instead of mountain town (40+ trails)
- **Solution:** Add mountain town detection with higher trail expectations

### 3. Trail Query Issues
- **Radius mismatch:** Using 2km for trail query but 15km for expectations
- **Data aggregation:** Summary shows different trail counts than query results
- **Solution:** Align trail query radius with expectations, investigate data aggregation

### 4. Water Feature False Positives
- **Times Square:** 308 water features (many likely coastline segments)
- **Desert locations:** May have false positives
- **Solution:** Filter small/coastline features for dense urban cores, add climate detection

---

## Immediate Action Items

### High Priority

1. **Fix Trail Query Radius**
   - Current: 2km for trail query, 15km for expectations
   - Should: Use 15km for trail query to match expectations
   - File: `pillars/active_outdoors.py` - `get_active_outdoors_score_v2()`

2. **Add Urban Core Penalty for Excessive Parks**
   - When park count > 2× expected, apply penalty or cap
   - Prevents Times Square from over-scoring on park count
   - File: `pillars/active_outdoors.py` - `_score_daily_urban_outdoors_v2()`

3. **Filter Water Features for Urban Cores**
   - Exclude small/coastline segments for dense urban cores
   - Or reduce water component weight for urban_core
   - File: `pillars/active_outdoors.py` - `_score_water_lifestyle_v2()`

### Medium Priority

4. **Add Mountain Town Detection**
   - Criteria: Elevation > threshold AND trail density > threshold
   - Use higher trail expectations (similar to commuter_rail_suburb pattern)
   - File: `pillars/active_outdoors.py` - `get_active_outdoors_score_v2()`

5. **Investigate Trail Data Aggregation**
   - Why summary shows 95 trails but query shows 1?
   - Check data aggregation logic
   - File: `pillars/active_outdoors.py` - `_build_summary_v2()`

6. **Add Desert/Climate Detection**
   - Reduce water access expectations for desert locations
   - File: `pillars/active_outdoors.py` - `_score_water_lifestyle_v2()`

---

## Next Steps

1. ✅ **Diagnostic completed** - Root causes identified
2. ⏳ **Implement fixes** - Address high-priority items
3. ⏳ **Re-run calibration** - After fixes are implemented
4. ⏳ **Validate improvements** - Check if outliers are resolved

---

**End of Findings**

