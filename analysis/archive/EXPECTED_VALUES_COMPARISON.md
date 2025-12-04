# Expected Values Comparison: Current vs Research

## Summary

**Research Sample Sizes (after filtering failed queries):**
- Urban Core: 10 successful locations ✅ (Good, but could use more)
- Suburban: 4 locations ⚠️ (Low - need more)
- Exurban: 2 locations ❌ (Too low - need more)
- Rural: 2 locations ❌ (Too low - need more)

**Key Finding:** High variance in results (many P25=0) suggests data quality issues or OSM query failures for some locations.

---

## Active Outdoors Pillar

### Parks within 1km

| Area Type | Current Expected | Research Median (Corrected) | P25 | P75 | Range | Sample Size | Status |
|-----------|-----------------|----------------------------|-----|-----|-------|-------------|--------|
| urban_core | **3** | **8.5** ⬆️ | 3.0 | 40.0 | 0-63 | 10 | ✅ Good (filtered failures) |
| suburban | **2** | **6.0** | 0.5 | 11.5 | 0-12 | 4 | ⚠️ Low sample |
| exurban | **1** | **7.5** | 6.75 | 8.25 | 7-8 | 2 | ❌ Too low |
| rural | **0** | **1** | 1 | 1 | 1-1 | 2 | ❌ Too low |

**Analysis:**
- Urban core: **Corrected median (8.5)** is 2.8x current (3) - significant difference
- Suburban: Median (6) is 3x current (2) - significant difference
- Exurban: Median (7.5) is 7.5x current (1) - but only 2 samples
- **Recommendation:** Use corrected median (8.5) for urban_core

### Park Area (hectares)

| Area Type | Current Expected | Research Median | P25 | P75 | Sample Size |
|-----------|-----------------|-----------------|-----|-----|-------------|
| urban_core | **3** | **2.79** | 0.0 | 12.64 | 13 |
| suburban | **5** | **20.98** | 2.06 | 56.14 | 4 |
| exurban | **10** | **4.91** | 3.02 | 6.80 | 2 |
| rural | **10** | **2.48** | 2.48 | 2.48 | 2 |

**Analysis:**
- Urban core: Close match (2.79 vs 3)
- Suburban: Much higher (20.98 vs 5) - but low sample size
- Exurban/Rural: Lower than expected, but very low sample sizes

### Trails within 15km

| Area Type | Current Expected | Research Median | P25 | P75 | Sample Size |
|-----------|-----------------|-----------------|-----|-----|-------------|
| urban_core | **2** | **32** | 4.5 | 99.0 | 13 |
| suburban | **1** | **5.5** | 1.25 | 14.25 | 4 |
| exurban | **1** | **9.0** | 4.5 | 13.5 | 2 |
| rural | **1** | **116** | 116 | 116 | 2 |

**Analysis:**
- Urban core: Median (32) is 16x current (2) - major difference
- Suburban: Median (5.5) is 5.5x current (1)
- **Recommendation:** Current values are significantly too low

---

## Healthcare Access Pillar

### Hospitals within 20km

| Area Type | Current Expected (10km) | Research Median (20km) | P25 | P75 | Sample Size |
|-----------|-------------------------|----------------------|-----|-----|-------------|
| urban_core | **2** | **5** | 0.0 | 20.5 | 13 |
| suburban | **1** | **2.0** | 2.0 | 5.75 | 4 |
| exurban | **0** | **1.5** | -0.75 | 3.75 | 2 |
| rural | **0** | **4** | 4 | 4 | 2 |

**Note:** Research uses 20km radius, current uses 10km - not directly comparable, but shows urban_core has more hospitals than expected.

### Pharmacies within 8km

| Area Type | Current Expected (2km) | Research Median (8km) | P25 | P75 | Sample Size |
|-----------|------------------------|---------------------|-----|-----|-------------|
| urban_core | **3** | **6** | 0.0 | 28.0 | 13 |
| suburban | **2** | **1.5** | 1.0 | 2.0 | 4 |
| exurban | **1** | **0.0** | 0.0 | 0.0 | 2 |
| rural | **0** | **0** | 0 | 0 | 2 |

**Note:** Research uses 8km radius, current uses 2km - not directly comparable.

### Closest Hospital (km)

| Area Type | Research Median | P25 | P75 | Sample Size |
|-----------|----------------|-----|-----|-------------|
| urban_core | **1.55** | 0.479 | 5.271 | 7 |
| suburban | **1.51** | 0.52 | 3.60 | 4 |
| exurban | **5.20** | 5.20 | 5.20 | 1 |
| rural | **6.47** | 6.47 | 6.47 | 1 |

---

## Neighborhood Amenities Pillar

### Businesses within 1km

| Area Type | Current Expected | Research Median (Corrected) | P25 | P75 | Range | Sample Size | Status |
|-----------|-----------------|----------------------------|-----|-----|-------|-------------|--------|
| urban_core | **50** | **188.5** ⬆️ | 4.5 | 494.5 | 0-1182 | 10 | ✅ Good (filtered failures) |
| suburban | **25** | **55.0** | 35.25 | 110.75 | 32-126 | 4 | ⚠️ Low sample |
| exurban | **10** | **67.0** | -33.5 | 167.5 | 0-134 | 2 | ❌ Too low |
| rural | **3** | **3** | 3 | 3 | 3-3 | 2 | ❌ Too low |

**Analysis:**
- Urban core: **Corrected median (188.5)** is 3.8x current (50) - major difference
- Suburban: Median (55) is 2.2x current (25)
- Exurban: Median (67) is 6.7x current (10), but only 2 samples
- **Recommendation:** Use corrected median (188.5) for urban_core

### Business Types

| Area Type | Current Expected | Research Median | P25 | P75 | Sample Size |
|-----------|-----------------|-----------------|-----|-----|-------------|
| urban_core | **12** | **12** | 0.0 | 16.0 | 13 |
| suburban | **8** | **11.5** | 11.0 | 12.0 | 4 |
| exurban | **4** | **5.0** | -2.5 | 12.5 | 2 |
| rural | **2** | **1** | 1 | 1 | 2 |

**Analysis:**
- Urban core: Perfect match (12)
- Suburban: Higher (11.5 vs 8)
- Exurban/Rural: Very low sample sizes

### Restaurants within 1km

| Area Type | Current Expected | Research Median (Corrected) | P25 | P75 | Sample Size |
|-----------|-----------------|----------------------------|-----|-----|-------------|
| urban_core | **15** | **109.5** ⬆️ | 0.0 | 185.5 | 10 |
| suburban | **8** | **20.5** | 14.75 | 51.0 | 4 |
| exurban | **3** | **24.5** | -12.25 | 61.25 | 2 |
| rural | **1** | **3** | 3 | 3 | 2 |

**Analysis:**
- Urban core: **Corrected median (109.5)** is 7.3x current (15) - major difference
- Suburban: Median (20.5) is 2.6x current (8)
- **Recommendation:** Use corrected median (109.5) for urban_core

---

## Key Issues Identified

### 1. High Variance (P25=0) - **CRITICAL ISSUE IDENTIFIED**

**Root Cause:** OSM query failures, not actual data gaps.

**Evidence:**
- 5 out of 13 urban_core locations returned 0 parks and 0 businesses
- Affected locations: Park Slope Brooklyn, Williamsburg Brooklyn, Downtown Charleston, Downtown Savannah, Old Town Alexandria
- These are well-known urban areas that definitely have parks and businesses

**Impact:**
- Research medians are artificially low due to failed queries
- P25=0 is caused by query failures, not real-world data
- Need to filter out failed queries or re-query these locations

**Action Required:**
1. Filter out locations with 0 results from analysis (treat as query failures)
2. Re-query failed locations with better error handling
3. Recalculate medians using only successful queries

### 2. Sample Size Issues
- **Suburban:** Only 4 samples - need 10+ for confidence
- **Exurban:** Only 2 samples - need 10+ for confidence  
- **Rural:** Only 2 samples - need 10+ for confidence

### 3. Significant Differences
Current expected values are consistently **lower** than research medians:
- Parks: 1.7x-7.5x higher
- Businesses: 2x-6.7x higher
- Trails: 5x-16x higher
- Restaurants: 2.6x-3.6x higher

---

## Recommendations

### Immediate Actions

1. **Investigate P25=0 Issue**
   - Check raw data for locations with 0 results
   - Determine if OSM query failures or actual data gaps
   - May need to filter out failed queries from analysis

2. **Collect More Samples**
   - **Suburban:** Need 10+ more samples (target: 15 total)
   - **Exurban:** Need 8+ more samples (target: 10 total)
   - **Rural:** Need 8+ more samples (target: 10 total)
   - **Urban Core:** Could use 5-10 more for higher confidence (target: 20 total)

3. **Update Expected Values (with caution)**
   - Use research medians as starting point
   - Account for high variance (consider using P25 as "minimum acceptable")
   - Document confidence levels based on sample sizes

### Sample Size Targets (Successful Queries)

| Area Type | Current (Successful) | Target | Additional Needed | Est. Time |
|-----------|---------------------|--------|-------------------|-----------|
| urban_core | 10 | 20 | 10 | ~7 min |
| suburban | 4 | 15 | 11 | ~8 min |
| exurban | 2 | 10 | 8 | ~6 min |
| rural | 2 | 10 | 8 | ~6 min |
| **Total** | **18** | **55** | **37** | **~27 min** |

**Note:** Some queries will fail, so we may need to sample more locations to reach target successful queries.

### Proposed Updated Expected Values

Based on research medians (pending more samples and variance investigation):

**Active Outdoors:**
- urban_core: parks_1km = 5 (was 3), park_area_hectares = 3 (was 3) ✅
- suburban: parks_1km = 6 (was 2), park_area_hectares = 5 (was 5) ✅
- exurban: parks_1km = 7.5 (was 1) - but need more samples
- rural: parks_1km = 1 (was 0) - but need more samples

**Amenities:**
- urban_core: businesses_1km = 98 (was 50), restaurants_1km = 54 (was 15)
- suburban: businesses_1km = 55 (was 25), restaurants_1km = 20.5 (was 8)

**Note:** These are preliminary - need to:
1. Investigate P25=0 variance issue
2. Collect more samples for suburban/exurban/rural
3. Cross-reference with external research sources

---

## Next Steps

1. ✅ **Done:** Initial research run (21 samples)
2. ⏳ **Next:** Investigate P25=0 variance issue
3. ⏳ **Next:** Collect more samples (34 additional locations, ~25 min)
4. ⏳ **Next:** Cross-reference with external research (TPL ParkScore, NRPA, etc.)
5. ⏳ **Next:** Update `regional_baselines.py` with research-backed values
6. ⏳ **Next:** Document all sources and methodology

