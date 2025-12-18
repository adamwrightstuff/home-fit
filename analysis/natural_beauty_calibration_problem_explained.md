# Natural Beauty Calibration Problem - Clear Explanation

## The Core Problem

**The calibration produces nearly identical scores (53-63) for locations with vastly different target scores (20-99) because:**

1. **CAL_A is too small** (0.131710) - raw scores barely matter
2. **Raw scores don't correlate with target scores** (R² = 0.0242)
3. **The calibration data is from OLD API responses** that used ridge regression, not the new data-backed scoring

## What's Happening

### The Calibration Formula
```
calibrated_score = 0.131710 * raw_score + 53.223394
```

### Why CAL_A is So Small

When linear regression finds **no correlation** between raw scores and target scores, it minimizes error by:
- Making CAL_A very small (so raw scores don't matter much)
- Setting CAL_B to the average target score (~53)
- Result: **Everything gets scored around 53-60**, regardless of the raw score

### Examples Showing the Problem

| Location | Raw Score | Target Score | Calibrated | Error |
|----------|-----------|--------------|------------|-------|
| Bushwick Brooklyn NY | 76.82 | **20** | 63.34 | **43.34** ❌ |
| Jackson WY | 18.91 | **98** | 55.71 | **42.29** ❌ |
| Sedona AZ | 66.71 | **99** | 62.01 | **36.99** ❌ |
| Capitol Hill Seattle WA | 92.68 | 65 | 65.43 | 0.43 ✓ |

**Notice the pattern:**
- **Bushwick**: HIGH raw (76.82) but LOW target (20) → Calibration gives 63 (wrong!)
- **Jackson WY**: LOW raw (18.91) but HIGH target (98) → Calibration gives 56 (wrong!)
- **Sedona**: Medium raw (66.71) but VERY HIGH target (99) → Calibration gives 62 (too low!)

## Root Cause: No Correlation

**R² = 0.0242** means:
- Only **2.4%** of variance in target scores is explained by raw scores
- Raw scores and target scores are **essentially uncorrelated**
- Linear regression can't find a good relationship because there isn't one

### Why There's No Correlation

Looking at the actual data:

**Bushwick (urban, target=20):**
- Has 4,516 street trees → tree_score = 50 (maxed out!)
- But Perplexity sees it as low natural beauty (20)
- **Problem**: Urban tree canopy ≠ natural beauty

**Jackson WY (mountain, target=98):**
- Low tree canopy → low raw score
- But Perplexity sees it as high natural beauty (98)
- **Problem**: Mountains/scenic beauty not captured in tree score

**The fundamental issue**: Our raw score formula is:
```
raw_score = (tree_score + natural_bonus_scaled) * (100/68)
```

But this measures:
- ✅ Tree canopy coverage
- ✅ Water/topography bonuses

It **doesn't** measure:
- ❌ Scenic beauty (mountains, vistas, coastlines)
- ❌ Wilderness quality (pristine vs developed)
- ❌ Subjective aesthetic appeal
- ❌ Cultural significance (national parks, protected areas)

## Additional Problem: Stale Calibration Data

**Important discovery**: The calibration data in `data/results.csv` was collected **before** we migrated to data-backed scoring. The API responses show:
- `score_before_normalization: 98.62` (matches ridge regression)
- Ridge regression was still being used

But we just changed the code to use:
```python
raw_score = (tree_score + natural_bonus_scaled) * (100/68)
```

**So we're calibrating NEW scoring using OLD data!**

## Impact

### Before Calibration
- Raw scores had variance (std dev: 24.73)
- But they were measuring the wrong thing (tree canopy ≠ natural beauty)

### After Calibration
- Calibrated scores have **NO variance** (std dev: 3.26)
- All locations score 53-60
- **Lost all differentiation** between locations
- Mean absolute error: **17.5 points** (still very high)

## What Needs to Happen

### Option 1: Fix Raw Score Calculation (Recommended)
Adjust the raw score to better align with natural beauty:
- **Reduce tree_score weight** (urban trees ≠ natural beauty)
- **Increase scenic/topography weight** (mountains, coastlines matter more)
- **Add wilderness quality factor** (pristine vs developed)
- **Consider area-type-specific scoring** (mountains vs urban need different formulas)

### Option 2: Re-collect Calibration Data
- Collect NEW API responses using the data-backed scoring
- Then calculate calibration parameters from fresh data
- This ensures calibration matches current implementation

### Option 3: Review Target Scores
- Verify Perplexity's evaluation criteria
- Check if target scores have systematic bias
- Consider getting target scores from multiple sources

### Option 4: Non-Linear or Area-Type-Specific Calibration
- If raw scores are fundamentally different, linear calibration won't work
- Might need piecewise linear or area-type-specific calibration
- Or accept that calibration can't fix a fundamental misalignment

## Current Status

✅ **Calibration is applied** (technically works)
❌ **Calibration doesn't improve accuracy** (R² = 0.0242)
❌ **Calibration removes variance** (all scores cluster around 53-60)
❌ **Large errors remain** (17.5 point average error)
❌ **Using stale calibration data** (from old ridge regression implementation)

## Recommendation

**The calibration reveals a deeper problem**: The raw score calculation doesn't measure what Perplexity considers "natural beauty."

**Immediate actions:**
1. **Re-collect calibration data** using the new data-backed scoring
2. **Review and adjust the raw score calculation** to better align with natural beauty
3. **Investigate component weights** (reduce tree_score, increase scenic/topography)
4. **Consider area-type-specific scoring** (mountains vs urban)

The current calibration is a band-aid that doesn't address the root cause. We need to fix the raw score calculation first, then re-calibrate with fresh data.
