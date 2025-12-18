# Natural Beauty Drift Analysis: What Went Wrong

## The Problem

Natural beauty scores are no longer working across urban, suburban, and rural environments. We've been **drifting away from data-backed principles** by adding calibrations that patch symptoms rather than fixing root causes.

## What We're Currently Measuring

### Current Raw Score Formula:
```
tree_weighted = tree_score * 0.4  # Max 20 points
scenic_weighted = min(30.0, natural_bonus_scaled * 1.67)  # Max 30 points
raw_score = (tree_weighted + scenic_weighted) * 2.0  # Scale to 0-100
```

### Components:
1. **Tree Score (0-50)**: Tree canopy percentage, street trees, GVI
2. **Enhancer Bonus (0-18)**: Topography, water, landcover (capped at 18)
3. **Context Bonus**: Topography (max 12), Water (max 40), Landcover (max 8)
   - But context bonus is weighted by 0.3 in enhancer calculation
   - So topography effectively maxes at 3.6 points (12 * 0.3)

## What's Actually Wrong

### 1. RURAL Areas: Measuring Trees, Not Scenic Beauty

**The Gap:**
- Avg Target: 85.9
- Avg Raw: 41.46
- **Gap: 44.49 points**

**Examples:**
- Jackson WY (Target 98, Raw 20.91): Mountain town, but topography = 0.00
- Taos NM (Target 90, Raw 21.82): Scenic mountain town, but topography = 0.00
- Whitefish MT (Target 92, Raw 30.90): Mountain resort, but topography = 0.00

**Root Cause:**
- Topography scoring requires 600m relief for full credit (too strict)
- Topography is weighted by 0.3, so max contribution is only 3.6 points
- We're measuring tree coverage, not scenic beauty

### 2. URBAN Areas: Two Incompatible Patterns

**Pattern 1: Scenic Downtowns** (mountain/coastal towns)
- High target (80-92), LOW raw (15-60)
- Examples: Downtown Coeur d'Alene (92/58), Downtown Santa Barbara (90/26)

**Pattern 2: Urban Parks** (neighborhoods with major parks)
- High target (80-92), HIGH raw (70-90)
- Examples: Park Slope (91/73), Queen Anne Seattle (80/90)

**Root Cause:**
- Urban_core calibration tries to fit both patterns → R² = 0.017 (random)
- We're not explicitly measuring proximity to major parks
- Tree score captures some of it, but not the full value

### 3. SUBURBAN Areas: Moderate Gap

**The Gap:**
- Avg Target: 52.3
- Avg Raw: 36.02
- **Gap: 16.26 points**

**Root Cause:**
- Moderate tree coverage, moderate enhancer bonus
- Missing: Proximity to natural areas, green space quality

## The Real Issue: We're Not Measuring Natural Beauty

**What makes natural beauty?**

1. **RURAL**: Scenic views, mountains, wilderness, dramatic landscapes
   - ❌ We measure: Tree coverage (low in mountains)
   - ✅ Should measure: Topography, scenic vistas, wilderness

2. **URBAN**: Major parks, tree-lined streets, water access, visual appeal
   - ❌ We measure: Tree coverage (good), but not park proximity
   - ✅ Should measure: Proximity to major parks, park quality, water access

3. **SUBURBAN**: Green space, proximity to nature, tree canopy
   - ❌ We measure: Tree coverage (moderate)
   - ✅ Should measure: Green space quality, proximity to natural areas

## What Happened: The Drift

1. **Started with data-backed approach**: Measure trees, topography, water, landcover
2. **Discovered gaps**: Raw scores don't match targets
3. **Added calibration**: Tried to fix with math (CAL_A, CAL_B)
4. **Calibration failed**: Low R² values (0.017-0.317) show poor fit
5. **Added patches**: Special cases, area-type-specific calibrations
6. **Result**: Complex, fragile system that doesn't actually measure natural beauty

## The Fix: Back to Data-Backed Principles

### 1. Fix Topography Scoring
- **Current**: 600m relief for full credit (too strict)
- **Fix**: Lower threshold (300m?), better weighting
- **Impact**: Rural scenic areas get proper credit

### 2. Increase Scenic Component Weight
- **Current**: Enhancer bonus capped at 18, weighted by 0.3
- **Fix**: Increase topography/water/landcover weight
- **Impact**: Scenic features matter more than tree coverage

### 3. Measure What Matters
- **Rural**: Topography, scenic vistas, wilderness (not just trees)
- **Urban**: Major park proximity, park quality (not just tree canopy)
- **Suburban**: Green space quality, proximity to nature

### 4. Remove Calibration (or make it minimal)
- **Current**: Complex area-type-specific calibrations
- **Fix**: Fix raw score calculation, then minimal/no calibration
- **Impact**: Pure data-backed scoring

## Next Steps

1. ✅ **Identify root cause**: We're measuring trees, not scenic beauty
2. ⏳ **Fix topography scoring**: Lower thresholds, better weighting
3. ⏳ **Increase scenic component weight**: Topography/water/landcover matter more
4. ⏳ **Measure park proximity**: For urban areas with major parks
5. ⏳ **Remove complex calibration**: Fix raw score, then minimal calibration if needed
