# Rule-Based Built Beauty Scoring System Summary

**Status:** Currently calculated but NOT used (Ridge regression is used instead)  
**Date:** December 2024

## Overview

The rule-based system calculates two main scores that combine into the final architectural diversity score (0-50 points native range):

1. **Design Score** (0-50 points): Architectural diversity components
2. **Form Score** (0-50 points): Street geometry and urban form components

Final score = `design_score + form_score` (scaled by area-type-specific multipliers)

---

## 1. Design Score Components

### Base Components (Each worth 16.67 points max)

1. **Height Diversity** (`height_raw`)
   - Scored using `_score_band()` against area-type-specific targets
   - Targets adjusted dynamically based on historic context, coastal patterns, etc.

2. **Type Diversity** (`type_raw`)
   - Building type diversity (residential, commercial, mixed-use, etc.)
   - Also scored using `_score_band()` with contextual adjustments

3. **Footprint Variation** (`foot_raw`)
   - Coefficient of Variation (CV) of building footprint areas
   - Higher variation = more organic/interesting (for most contexts)

### Variable Weight Components

4. **Setback Consistency** (16.67-22.0 points based on area type)
   - **Urban Core / Urban Core Lowrise:** 22.0 points (increased from 16.67)
   - **Urban Residential:** 20.0 points (increased from 16.67)
   - **All others:** 16.67 points
   - Critical for streetwall quality in urban areas

5. **Facade Rhythm** (16.67 points)
   - Regular spacing and rhythm of building facades
   - Standard weight for all area types

6. **Built Coverage** (12.0-15.0 points based on area type)
   - **Urban Core / Urban Core Lowrise:** 15.0 points (most important)
   - **Urban Residential:** 13.0 points
   - **All others:** 12.0 points
   - Scored using `_score_band()` with area-type-specific coverage targets

### Optional Bonus Components

7. **Coherence Component** (0-16.0+ points)
   - Only for `urban_residential` or historic areas
   - Based on `coherence_signal` (setback + facade + streetwall + material + height alignment)
   - Formula: `coherence_signal * 16.0 * (1.0 + confidence_gate * 0.15)`
   - Provides floor for type diversity if coherence ≥ 0.6

8. **Material Component** (0-16.67 points)
   - Material entropy (diversity of building materials)
   - Weighted by area type (historic_urban: 1.5x, urban_core: 1.2x, etc.)
   - Reduced by 35% if material tagging coverage < 15%

---

## 2. Form Score Components

### Base Components (Each worth 16.67 points max)

1. **Block Grain** (16.67 points)
   - Block size and grain pattern
   - Scored as: `(block_grain_value / 100.0) * 16.67`

2. **Streetwall Continuity** (16.67 points)
   - Continuous building frontage along streets
   - Scored as: `(streetwall_value / 100.0) * 16.67`
   - Has special rowhouse proxy for urban_residential/historic_urban

---

## 3. Area-Type-Specific Contextual Adjustments

### A. Base Target Bands (`CONTEXT_TARGETS`)

Each area type has ideal ranges for height, type, and footprint diversity:

| Area Type | Height Target | Type Target | Footprint Target |
|-----------|---------------|--------------|------------------|
| **urban_residential** | 0-30 (uniform best) | 0-40 (uniform best) | 20-85 (low/moderate best) |
| **urban_core** | 30-80 (moderate variation) | 50-95 (high diversity) | 30-70 (moderate variation) |
| **urban_core_lowrise** | 10-80 (lower min for coastal) | 40-95 | 30-90 (more forgiving) |
| **historic_urban** | 15-70 (moderate, organic) | 25-85 (mixed-use historic) | 35-85 (organic variation) |
| **suburban** | 0-50 (lower variation) | 18-70 (moderate) | 30-80 (moderate-high) |
| **exurban** | 0-40 (very uniform) | 0-50 (very uniform) | 50-100 (high variation OK) |
| **rural** | 0-40 (very uniform) | 0-50 (very uniform) | 50-100 (high variation OK) |

### B. Built Coverage Targets (`COVERAGE_TARGETS`)

Target bands for built coverage (as percentage 0-100):

| Area Type | Coverage Target Band | Max Points |
|-----------|----------------------|------------|
| **urban_core** | 15-50% (25-40% plateau) | 15.0 |
| **urban_core_lowrise** | 15-50% (25-40% plateau) | 15.0 |
| **urban_residential** | 12-45% (20-35% plateau) | 13.0 |
| **historic_urban** | 10-45% (20-35% plateau) | 12.0 |
| **suburban** | 8-30% (12-20% plateau) | 12.0 |
| **exurban** | 5-25% (8-15% plateau) | 12.0 |
| **rural** | 2-15% (3-8% plateau) | 12.0 |

**Special Case:** Spacious historic districts (e.g., Garden District, Old San Juan)
- Coverage targets: 8-40% (15-30% plateau)
- Detected by: low coverage (<25%) + historic context + uniform materials/footprints

### C. Design/Form Scale Multipliers (`DESIGN_FORM_SCALE`)

Final scaling factors applied to design_score and form_score:

| Area Type | Design Scale | Form Scale |
|-----------|--------------|------------|
| **historic_urban** | 92.0% | 68.0% |
| **urban_core** | 62.0% | 54.0% |
| **urban_residential** | 54.0% | 46.0% |
| **urban_core_lowrise** | 60.0% | 50.0% |
| **suburban** | 66.0% | 48.0% |
| **exurban** | 78.0% | 55.0% |
| **rural** | 74.0% | 56.0% |

**Note:** These multipliers reduce the final score, with historic_urban getting the highest design weight (92%) and urban_residential getting the lowest (54%).

---

## 4. Dynamic Contextual Adjustments

The system applies **7 contextual adjustment functions** that modify target bands based on specific patterns:

### Adjustment 1: Historic Organic Growth
- **Trigger:** Median year built < 1940 OR (historic tag + footprint CV > 70)
- **Effect:** Widens footprint targets to (50, 65, 95, 100) - HIGH CV is GOOD for historic
- **Also adjusts:** Height and type targets for urban_core/lowrise/historic areas

### Adjustment 2: Very Historic Urban Residential
- **Trigger:** Very historic (pre-1940) + urban_residential
- **Effect:** Allows higher type diversity: (0, 0, 35, 50) instead of (0, 0, 20, 40)

### Adjustment 3: Historic Urban Core with Moderate Diversity
- **Trigger:** Historic + (urban_core OR urban_core_lowrise) + moderate diversity metrics
- **Effect:** Adjusts all three targets to accommodate organic historic patterns

### Adjustment 4: Historic Suburban/Exurban Uniformity
- **Trigger:** Historic + (suburban OR exurban) + very uniform metrics
- **Effect:** Tightens all targets to reward intentional uniformity (e.g., Carmel-by-the-Sea)

### Adjustment 5: Coastal Uniformity (Urban Core Lowrise)
- **Trigger:** urban_core_lowrise + very uniform metrics
- **Effect:** Rewards uniform coastal beach towns (e.g., Redondo Beach)

### Adjustment 6: Coastal Town Uniformity (Suburban/Exurban)
- **Trigger:** (suburban OR exurban) + uniform architecture + low footprint CV
- **Effect:** Rewards cohesive coastal towns

### Adjustment 7: Residential Varied Lots (Urban Core Lowrise)
- **Trigger:** urban_core_lowrise + uniform architecture + high footprint CV + density > 5000
- **Effect:** Rewards uniform residential with varied lot sizes (parks/green space pattern)

---

## 5. Special Scoring Logic

### Coherence Floor for Type Diversity
- **Condition:** `urban_residential` OR historic tag + coherence_signal ≥ 0.6
- **Effect:** Provides minimum type diversity score: `max(type_raw, 8.5 + (coherence_floor * 7.0))`
- **Rationale:** High coherence (unified materials, setbacks, streetwall) compensates for low type diversity

### Material Component Penalty
- **Condition:** Material tagging coverage < 15%
- **Effect:** Material component reduced by 35% (multiplied by 0.65)
- **Rationale:** Low tagging coverage = unreliable material entropy

### Height Diversity Adjustments
- **Bonus:** If height_std > 1.2, add up to 2.5 points
- **Penalty:** If single_story_share > 65%, multiply by 0.88

### Type Diversity Adjustments
- **Bonus:** If type_category_diversity > building_type_diversity, add up to 2.0 points

---

## 6. Score Calculation Flow

```
1. Get base area type → effective area type
2. Get base CONTEXT_TARGETS for effective area type
3. Apply 7 contextual adjustments (historic, coastal, etc.)
4. Score height_raw, type_raw, foot_raw using adjusted targets
5. Calculate design_components:
   - height_raw, type_raw, foot_raw (each 16.67 max)
   - setback_value * setback_weight (16.67-22.0)
   - facade_rhythm_value * 16.67
   - coverage_raw (12.0-15.0)
   - coherence_component (if applicable, 0-16.0+)
   - material_component (if applicable, 0-16.67)
6. Calculate expected_total (sum of all component max points)
7. Normalize: design_score = (sum(design_components) / expected_total) * 50.0 * scale_params["design"]
8. Calculate form_components:
   - block_grain_value * 16.67
   - streetwall_value * 16.67
9. Normalize: form_score = (sum(form_components) / (len * 16.67)) * 50.0 * scale_params["form"]
10. Final score = design_score + form_score (0-50 native range)
```

---

## 7. Key Differences from Ridge Regression

| Aspect | Rule-Based System | Ridge Regression |
|--------|------------------|------------------|
| **Transparency** | ✅ Clear thresholds and bands | ❌ Black box coefficients |
| **Differentiation** | ✅ Features contribute 10-20 points each | ❌ Intercept dominates (75.7 points) |
| **Contextual Adjustments** | ✅ 7 dynamic adjustments | ❌ Global model only |
| **Area-Type Specificity** | ✅ Different targets/weights per area type | ❌ Single global model |
| **Interpretability** | ✅ Can explain why score changed | ❌ Hard to explain |
| **Research Backing** | ✅ Based on research data (60 locations) | ⚠️ Trained on 56 locations (R²=0.16) |

---

## 8. Current Status

**The rule-based system is fully implemented and calculated**, but:
- ❌ **NOT used for final score** (line 2321: "REPLACED: Use Ridge regression")
- ❌ **design_score and form_score set to 0.0 in metadata** (lines 2395-2396)
- ✅ **All components calculated correctly** with recent improvements:
  - Built coverage scoring (12-15 points)
  - Increased setback weights for urban areas (22.0/20.0)
  - Spacious historic district detection
  - Coherence component for urban_residential/historic

---

## 9. Recommendations

To switch to rule-based scoring:

1. **Replace Ridge regression call** (line 2344) with:
   ```python
   final_score = min(50.0, design_score + form_score)
   ```

2. **Update metadata** (lines 2395-2396) to return actual values:
   ```python
   "design_score": round(design_score, 1),
   "form_score": round(form_score, 1),
   ```

3. **Remove or comment out** Ridge regression call and feature contributions

4. **Test** on diverse locations to verify differentiation improves

---

## 10. Expected Score Range

With rule-based system:
- **Design Score:** 0-50 points (scaled by area-type multiplier: 54%-92%)
- **Form Score:** 0-50 points (scaled by area-type multiplier: 46%-68%)
- **Combined:** 0-50 points native range
- **Differentiation:** Features can contribute 10-20 points each, leading to wider score distribution

**Example:**
- Urban Core with excellent coverage (15 pts) + high setback (22 pts) + good form (30 pts) = ~67 points
- Suburban with low coverage (8 pts) + missing form metrics (0 pts) = ~26 points
- **Range:** ~26-67 points (much wider than Ridge's 72-85 clustering)
