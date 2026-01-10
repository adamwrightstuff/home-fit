# Natural Beauty Scoring: What Factors Drive High Scores?

## Score Structure

The Natural Beauty score (0-100) uses a **weighted component sum** that scales to 100:

### Components (Max Total: 93.75 points, scaled to 100)

**1. Base Tree Score (15 points max)**
- Weight: 30% of base canopy score (0-50 scale)
- Formula: `(base_canopy_with_expectation) * 0.30`
- Includes expectation adjustments (climate/area-type adjustments)
- Max: 50 * 0.30 = **15 points**

**2. Green View Index (20 points max)**
- Weight: 20% of GVI (0-100 scale)
- Formula: `(green_view_index / 100.0) * 20.0`
- Visible greenery from street level (eye-level beauty)
- Max: **20 points**

**3. Street Trees (5 points max)**
- Weight: Direct (0-5 scale)
- Formula: `street_tree_bonus * 1.0`
- For urban areas with street trees but low satellite canopy
- Max: **5 points**

**4. Local Green Spaces (10 points max)**
- Weight: Direct (0-10 scale)
- Formula: `local_green_score * 1.0`
- Parks within 400m walking distance
- Max: **10 points**

**5. Context Bonus / Scenic Features (70 points max)**
- Weight: Context bonus (0-40 scale) multiplied by 1.75x
- Formula: `min(70.0, context_bonus * 1.75)`
- **Scenic beauty features beyond trees:**

**Context Bonus Components (capped at 25 points total):**

- **Topography** (max 20 points raw, then weighted):
  - Relief (elevation range): 300m relief = 1.0 factor, 400m+ relief = 1.2 factor (exceptional relief rewarded)
  - Slope (steepness): 20° mean slope = full credit
  - Prominence (peak height above surroundings): >200m = highly scenic
  - Ruggedness (elevation variation): 90m = 1.0 factor, 100m+ = 1.1 factor (exceptional ruggedness rewarded)
  - **Weight varies by landscape**: Mountain areas get 30% boost (0.627 weight for rural+mountain)
  - **Enhanced scoring**: Areas with relief >350m, ruggedness >80m, or prominence >180m get 45% enhanced weight (vs 40%)

- **Landcover** (max ~18 points raw, then weighted):
  - Forest coverage: 40% forest = full credit
  - Wetland coverage: 10% wetland = full credit
  - Shrub/grass diversity: Natural vegetation mix
  - **Weight**: ~0.20-0.30 depending on area type

- **Water** (max 40 points raw, then weighted):
  - Water coverage: Climate-adjusted (arid regions score higher for rare water)
  - Water proximity: Distance to major waterbodies (rivers, lakes, oceans)
    - <1km: 10.0 points
    - <3km: 8.0 points
    - <5km: 6.0 points
    - <10km: 4.0-5.0 points (5.0 for very large lakes >50km²)
    - <15km: 2.0-3.0 points (3.0 for very large lakes >50km²)
  - Large lake bonus: >50km² lakes get 1.4x multiplier and higher proximity bonuses
  - Coastal bonus: Ocean proximity adds extra points
  - Proximity bonus cap: 18.0 points (increased from 16.0 for exceptional water features)
  - **Weight**: ~0.15-0.20 depending on area type and landscape tags

- **Viewshed** (max 4 points):
  - Visible natural area: Percentage of visible landscape that's natural (forests, mountains, water)
  - >30% visible natural = full 4 points
  - Measures scenic backdrop/views (mountain backdrop, forests visible)

**Context Bonus Weight Application:**
Context bonus components are weighted by area type and landscape tags:
- **Mountain tag**: +30% topography weight, -10% landcover weight
- **Coastal tag**: +20% water weight, -15% landcover weight
- **Forest tag**: +15% landcover weight, -10% water weight
- **Desert tag**: +25% topography weight, -20% landcover weight

### Final Score Calculation

**Total Components**: 15 + 20 + 5 + 10 + 70 = **120 points max**
**Scaling**: Multiply by `(100.0 / 120.0)` to scale to 100

This means:
- Context bonus of 40 points → 40 * 1.75 = 70.0 weighted points (maximum)
- Context bonus of 25 points → 25 * 1.75 = 43.75 weighted points
- Context bonus of 11.08 points → 11.08 * 1.75 = 19.39 weighted points

## What Makes a High Natural Beauty Score (80-100)?

### Perfect Score Examples:

**1. Mountain Town with Lake (e.g., Aspen, CO)**
- Base Tree Score: 45-50 points (moderate-to-high canopy: 35-50%)
- Context Bonus: 20-25 points (capped)
  - Topography: 15-20 points (high relief 400m+, prominent peaks)
  - Water: 5-8 points (lake proximity <5km, large lake bonus)
  - Viewshed: 3-4 points (mountain backdrop visible)
  - Landcover: 2-4 points (mountain forests, meadows)
- **Total: 70-75 points**

**2. Coastal Forest (e.g., Pacific Northwest)**
- Base Tree Score: 48-50 points (very high canopy: 50-70%)
- Context Bonus: 18-25 points
  - Topography: 8-12 points (coastal mountains, moderate relief)
  - Water: 8-12 points (ocean proximity, coastal bonus)
  - Viewshed: 3-4 points (ocean views, forest backdrop)
  - Landcover: 4-6 points (dense temperate forests)
- **Total: 66-75 points**

**3. Urban Park City (e.g., Portland, OR)**
- Base Tree Score: 40-45 points (good canopy: 30-40%)
- Context Bonus: 12-18 points
  - Topography: 4-8 points (hills, moderate relief)
  - Water: 4-6 points (river proximity)
  - Viewshed: 2-3 points (visible greenery)
  - Landcover: 4-6 points (parks, street trees, local green spaces)
- **Total: 52-63 points**

## What Truckee, CA is Showing (Score: 41.2)

### Current Performance:

**Base Tree Score: 35.36 points** ✅ Good
- Weighted Canopy: 27.4% (neighborhood 40.3%, local 14.2%)
- Tree Base Score: 27.19 points
- Green View Index: 25.45 (eye-level greenery)
- Local Green Score: 6.0 points (parks nearby)

**Context Bonus: 11.08 points** ⚠️ **Too Low** (capped at 25.0)

**Why Context Bonus is Low:**

1. **Topography: 4.95 points (from raw 7.08)** ⚠️ **Underperforming**
   - Raw score: 7.08 out of 20.0 max
   - Relief: 394m (should be ~13.2 points alone at 300m threshold)
   - Ruggedness: 73.8m (good, but below 100m threshold for full credit)
   - Prominence: 0m (no prominent peak detected)
   - **Issue**: Topography scoring may be too conservative for 394m relief

2. **Water: 1.46 points (from raw 10.36)** ⚠️ **Severely Underperforming**
   - Raw score: 10.36 out of 40.0 max (good!)
   - Distance to Lake Tahoe: ~12-15km
   - **Issue**: Water weight too low (0.14 instead of expected 0.175-0.20)
   - Mountain tag should preserve water weight better with significant water

3. **Landcover: 0.66 points (from raw 4.16)** ⚠️ **Underperforming**
   - Raw score: 4.16 out of ~18.0 max
   - **Issue**: Low forest/vegetation coverage detected (mountain towns may have sparse vegetation)

4. **Viewshed: 4.00 points** ✅ Excellent
   - Visible Natural: 55.9% (excellent mountain backdrop visibility)

### Expected vs Actual:

**Expected for Mountain Town (Truckee):**
- Base Tree Score: 35-40 points ✅ **On target**
- Context Bonus: 18-25 points ❌ **Getting only 11.08** (should improve with new scoring)
  - Topography should be: 12-16 points (394m relief = 1.31 factor, 73.8m ruggedness = 0.82 factor, enhanced weights)
  - Water should be: 4-6 points (Lake Tahoe proximity with mountain tag, improved proximity bonuses for large lakes)
  - Viewshed: 4.0 points ✅ **Perfect**
  - Landcover: 2-3 points (acceptable for mountain towns)

**Total Expected: 55-65 points**
**Current: 41.2 points**
**Gap: -14 to -24 points**

### Why the Math Works Out:

For Truckee's current score of 41.2:
- Base Tree (weighted): ~10.5 points (35% of 15 max)
- GVI (weighted): ~5.1 points (25.45% of 20 max)
- Street Trees: 0 points
- Local Green: 6.0 points
- Context Bonus (weighted): ~19.4 points (11.08 * 1.75)

**Total weighted**: ~40.9 points → scaled to **41.2** (multiplied by 1.0667 to reach 100 scale)

The context bonus contribution is actually **19.4 points** (not 11.08) because it's weighted 1.75x before scaling.

## Why the Score is Low

1. **Topography Raw Score Too Low**: 7.08 points for 394m relief suggests the scoring function needs adjustment for high-relief mountain areas
2. **Water Weight Too Low**: Despite having significant water (Lake Tahoe 12-15km away), the water weight is only 0.14, giving only 1.46 points instead of expected 4-6 points
3. **Mountain Tag Weighting**: While mountain tag increases topography weight, the raw topography score itself is too low to benefit fully

## Recommendations

1. **Adjust Topography Scoring**: Increase raw score for relief >300m (current 394m relief should score higher)
2. **Preserve Water Weight**: Ensure mountain tag preserves water weight better when significant water is present (15km threshold is correct, but weight preservation needs work)
3. **Prominence Detection**: Improve prominence detection for mountain towns (Truckee has 0m prominence but should have some)
