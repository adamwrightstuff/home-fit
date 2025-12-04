# Neighborhood Amenities Pillar: Methodology Audit & Alignment

**Purpose:** Audit Neighborhood Amenities pillar against Public Transit methodology principles and identify improvements needed.

**Last Updated:** 2024-12-19

---

## Current State Analysis

### 1. Research-Backed Expected Values

**Status:** [x] Partial / [ ] Complete

**Current Implementation:**

- Expected businesses within 1km: `expected_businesses_within_1km` (from `get_contextual_expectations`)
  - Urban core: 180 businesses
  - Suburban: 65 businesses
  - Exurban: 10 businesses
  - Rural: 3 businesses

- Expected business types: `expected_business_types` (from `get_contextual_expectations`)
  - Urban core: 12 types
  - Suburban: 12 types
  - Exurban: 4 types
  - Rural: 2 types

- Expected restaurants within 1km: `expected_restaurants_within_1km` (from `get_contextual_expectations`)
  - Urban core: 100 restaurants
  - Suburban: 35 restaurants
  - Exurban: 3 restaurants
  - Rural: 1 restaurant

**Issues Found:**

- [x] Expected values exist but may not be fully documented
  - Values in `data_sources/regional_baselines.py` lines 676-682 mention "Median across sampled locations"
  - Need to verify these match research data from CSV

- [ ] Expected values may need verification against research data
  - Research CSV has `amenities.businesses_1km`, `amenities.restaurants_1km`, `amenities.business_types`
  - Should verify medians match expected values

- [ ] Missing expected values for walkable distance (400m, 800m)
  - Current scoring uses hard thresholds (200m, 400m, 600m, 800m)
  - No research-backed expected values for businesses within walkable distances

**Action Items:**

1. Verify expected values match research data from CSV
2. Add expected values for walkable distances (400m, 800m) if research data available
3. Document sample sizes and research methodology

---

### 2. Calibrated Scoring Curves

**Status:** [x] Needs Calibration / [ ] Partial / [ ] Complete

**Current Implementation:**

- **Density Score (0-25 points):** Hard thresholds
  - Urban core: 60+ = 25pts, 36+ = 20pts, 18+ = 12pts, etc.
  - Suburban: 50+ = 25pts, 30+ = 20pts, 15+ = 12pts, etc.
  - Exurban/Rural: 35+ = 25pts, 21+ = 20pts, 11+ = 12pts, etc.
  - Located in `pillars/neighborhood_amenities.py` lines 154-199

- **Variety Score (0-20 points):** Hard thresholds
  - Tier 1: 3+ types = full points, 2 types = 67%, 1 type = 33%
  - Tier 2: 2+ types = full points, 1 type = 60%
  - Tier 3: 2+ types = full points, 1 type = 60%
  - Tier 4: 2+ types = full points, 1 type = 33%
  - Located in `pillars/neighborhood_amenities.py` lines 202-246

- **Proximity Score (0-15 points):** Hard thresholds
  - ≤200m = 15pts, ≤400m = 13pts, ≤600m = 11pts, ≤800m = 10pts, ≤1000m = 7pts, >1000m = 2.5pts
  - Located in `pillars/neighborhood_amenities.py` lines 249-289

- **Location Quality (0-40 points):** Hard thresholds
  - Proximity: ≤400m = 20pts, ≤800m = 15pts, ≤1200m = 10pts, ≤1600m = 5pts
  - Vibrancy: Variety-based scoring with hard thresholds
  - Density bonus: Context-aware but uses hard divisors
  - Located in `pillars/neighborhood_amenities.py` lines 310-431

- **Global Linear Calibration:** Post-hoc adjustment
  - `CAL_A = 0.193`, `CAL_B = 68.087`
  - Applied to raw_total (0-100) → calibrated (0-100)
  - Located in `pillars/neighborhood_amenities.py` lines 84-92

**Issues Found:**

- [x] Hard thresholds (not smooth curves)
  - All components use hard thresholds with discontinuities
  - No smooth saturation functions

- [x] No component-level calibration
  - Uses global linear calibration instead of calibrated curves per component
  - Global calibration is a post-hoc adjustment, not research-backed

- [x] Scoring may not align with real-world quality perception
  - Hard thresholds create discontinuities
  - No validation against known good/bad amenity locations

- [x] Different scoring approaches for different components (inconsistent)
  - Density: Count-based thresholds
  - Variety: Type-count-based thresholds
  - Proximity: Distance-based thresholds
  - Location Quality: Mixed (distance + variety + density)

**Action Items:**

1. Create calibration panel (16+ locations with known amenity quality)
   - Use LLM-researched target scores provided
   - Include urban cores, suburbs, exurban, rural locations
2. Create `scripts/calibrate_neighborhood_amenities_scoring.py`
   - Follow pattern from transit/healthcare calibration
   - Fit smooth curves to minimize error vs target scores
3. Replace hard thresholds with smooth saturation functions
   - Use `_sat_ratio_v2` pattern or calibrated piecewise linear
   - Align all components to use similar scoring methodology
4. Replace global linear calibration with component-level calibrated curves

---

### 3. Context-Aware Architecture

**Status:** [x] Good / [ ] Needs Improvement

**Current Implementation:**

- Uses `area_type` for radius profiles (via `get_radius_profile`)
  - Neighborhood scope: 1000m query, 800m walkable
  - City scope: 1500m query, 1000m walkable
  - Located in `data_sources/radius_profiles.py` lines 66-70

- Uses `area_type` for expected values (via `get_contextual_expectations`)
  - Area-type-specific expectations for businesses, types, restaurants
  - Located in `data_sources/regional_baselines.py` lines 676-682, 705-709, etc.

- Uses `area_type` for context-aware thresholds
  - Density thresholds adjusted by area type (urban_core higher, exurban/rural lower)
  - Proximity thresholds adjusted for suburban/urban_residential
  - Location quality thresholds adjusted by area type
  - Located in `pillars/neighborhood_amenities.py` throughout

**Issues Found:**

- [ ] No special context detection (e.g., tourist districts, college towns)
  - Could detect high tier3 (cultural) density for tourist areas
  - Could detect university proximity for college towns

- [x] Context-aware thresholds are good but use hard cutoffs
  - Should use smooth curves with area-type-specific expectations

**Action Items:**

1. Consider adding context detection (tourist districts, college towns) if correlations support
2. Replace hard context-aware thresholds with smooth curves using expected values

---

### 4. Data Quality & Performance

**Status:** [x] Good / [ ] Needs Improvement

**Current Implementation:**

- OSM query via `osm_api.query_local_businesses()`
- Data quality assessment via `data_quality.assess_pillar_data_quality`
- Radius filtering applied via `get_radius_profile`

**Issues Found:**

- [x] No structured logging (uses `print()` statements)
  - Should use `logger.info()` with structured JSON logging
  - No logging of API responses, query parameters, or data quality metrics

**Action Items:**

1. Add structured logging similar to Active Outdoors
   - Replace `print()` with `logger.info()` and structured JSON
   - Log: query parameters, business counts, tier breakdowns, data quality metrics
   - Include context: lat, lon, area_type, pillar_name

---

### 5. Component Scoring Consistency

**Status:** [x] Inconsistent / [ ] Needs Alignment

**Current Issues:**

- **Density:** Count-based with hard thresholds (lines 154-199)
  - Different thresholds for different area types
  - Hard cutoffs create discontinuities

- **Variety:** Type-count-based with hard thresholds (lines 202-246)
  - Different scoring per tier (40%, 33%, 17%, 10%)
  - Hard cutoffs (3 types, 2 types, 1 type)

- **Proximity:** Distance-based with hard thresholds (lines 249-289)
  - Hard distance cutoffs (200m, 400m, 600m, 800m, 1000m)
  - Some area-type adjustments but still hard cutoffs

- **Location Quality:** Mixed approach (lines 310-431)
  - Proximity: Distance-based hard thresholds
  - Vibrancy: Variety + density with hard thresholds
  - Cultural bonus: Count-based hard threshold

**Action Items:**

1. Standardize all components to use saturation functions
   - Density: Ratio-based saturation (count / expected)
   - Variety: Ratio-based saturation (types / expected_types)
   - Proximity: Distance-based smooth curve (exponential decay)
   - Location Quality: Ratio-based saturation for vibrancy components
2. Align scoring philosophy across all components
   - All components should use: expectations → ratio → saturation function
   - Consistent curve shapes (exponential saturation or calibrated piecewise linear)
   - Consistent max scores and breakpoints
3. Document scoring rationale for each component
   - Why each component uses its current scoring
   - How scores map to real-world quality perception
   - Calibration methodology (once implemented)

---

## Priority Action Items

### High Priority

1. **Verify Expected Values** - Check against research CSV data, update if needed
2. **Create Calibration Panel** - Use LLM-researched target scores (16+ locations)
3. **Calibrate Scoring** - Create calibration script, replace hard thresholds with smooth curves
4. **Standardize Scoring** - Use saturation functions for all components

### Medium Priority

5. **Add Context Detection** - Tourist districts, college towns (if correlations support)
6. **Enhanced Logging** - Structured logging for debugging

### Low Priority

7. **Documentation** - Complete methodology document

---

## Files to Review/Modify

1. `pillars/neighborhood_amenities.py` - Main scoring logic
2. `data_sources/regional_baselines.py` - Expected values
3. `data_sources/radius_profiles.py` - Radius configuration (already good)
4. `scripts/research_expected_values.py` - Research data collection (verify amenities data)
5. `scripts/calibrate_neighborhood_amenities_scoring.py` - [NEW] Calibration script
6. `analysis/NEIGHBORHOOD_AMENITIES_METHODOLOGY.md` - [THIS FILE] Methodology document

---

## Key Questions to Answer

1. Are expected values research-backed or target-tuned?
   - **Answer:** Appear to be research-backed (mentions "Median across sampled locations") but need verification

2. Are scoring curves calibrated or arbitrary?
   - **Answer:** Arbitrary. Hard thresholds appear to be chosen without calibration. Global linear calibration is post-hoc adjustment.

3. Do all components use consistent scoring methodology?
   - **Answer:** No. Density uses count thresholds, variety uses type-count thresholds, proximity uses distance thresholds, location quality uses mixed approach.

4. Is there context-aware logic for special cases?
   - **Answer:** Yes, but uses hard thresholds. Could add tourist/college town detection.

5. Is performance optimized (parallel calls)?
   - **Answer:** Single OSM query (sequential). No parallelization needed currently.

6. Is fallback mechanism comprehensive?
   - **Answer:** N/A - OSM is primary source, no fallback needed.

---

## Alignment with Public Transit Methodology

### ✅ What Neighborhood Amenities Does Well

1. **Area-type-specific radii** - Uses `radius_profiles.py` for context-aware search radii
2. **Area-type-specific expectations** - Uses `get_contextual_expectations()` for context-aware scoring
3. **Area-type-specific thresholds** - Adjusts thresholds by area type
4. **Data quality assessment** - Uses `data_quality.assess_pillar_data_quality()` for confidence scoring

### ❌ What Neighborhood Amenities Needs to Improve

1. **Research-backed expected values** - Need to verify against research CSV
2. **Calibrated scoring curves** - Uses hard thresholds, not calibrated curves
3. **Smooth functions** - All components use hard thresholds with discontinuities
4. **Consistent scoring methodology** - Mixed approaches (count thresholds, type thresholds, distance thresholds)
5. **Component-level calibration** - Uses global linear calibration instead of calibrated curves
6. **Structured logging** - Uses `print()` statements instead of structured JSON logging

### 📋 Recommended Next Steps

1. **Phase 1: Verify & Update Expected Values** (High Priority)
   - Check research CSV data matches expected values
   - Add expected values for walkable distances if available
   - Document sample sizes and methodology

2. **Phase 2: Calibration** (High Priority)
   - Create calibration panel from LLM scores (16+ locations)
   - Build calibration script
   - Replace hard thresholds with smooth calibrated curves
   - Replace global linear calibration with component-level curves

3. **Phase 3: Standardization** (High Priority)
   - Standardize all components to use saturation functions
   - Align scoring philosophy across all components
   - Document scoring rationale

4. **Phase 4: Context & Logging** (Medium Priority)
   - Add context detection (tourist districts, college towns) if correlations support
   - Add structured logging

---

## References

- **Public Transit Methodology:** `analysis/PUBLIC_TRANSIT_PILLAR_METHODOLOGY.md`
- **Healthcare Methodology:** `analysis/HEALTHCARE_ACCESS_METHODOLOGY.md`
- **Design Principles:** `DESIGN_PRINCIPLES.md`
- **Research Data:** `analysis/research_data_expanded/expected_values_summary.csv`

---

**End of Audit Document**

