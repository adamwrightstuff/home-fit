# How to Get Calibration Scores for 177 Locations

## Quick Answer

You need **target scores** (ground truth) for each location + pillar combination. Here's how to get them:

## Option 1: Use LLM Evaluation (Like Previous Calibration)

**Process** (same as `neighborhood_amenities_calibration_panel.json`):

1. **For each location**, provide context:
   - Location name and description
   - Area type (urban_core, suburban, etc.)
   - Key features (parks, trails, water access, etc.)

2. **Ask LLM** (Claude, Gemini, Perplexity) to evaluate:
   - "What should the active_outdoors score be (0-100) for [location]?"
   - "What should the natural_beauty score be (0-100) for [location]?"

3. **Take median/average** of multiple LLM responses for robustness

4. **Save target scores** in calibration data file

**Example** (from `neighborhood_amenities_calibration_panel.json`):
```json
{
  "location": "Midtown Manhattan NY",
  "area_type": "urban_core",
  "target_score": 98,
  "llm_scores": {
    "perplexity": 95,
    "gemini": 98,
    "claude": 100,
    "average": 98
  }
}
```

## Option 2: Extract from Existing Data

**If you have API results** (`data/results.csv`):

1. **Parse JSON responses** to get current scores
2. **Use current scores as baseline** (may need adjustment)
3. **Manually adjust** based on known issues or expert knowledge

**Pros**: Fast, uses existing data
**Cons**: Current scores may have issues (that's why we need calibration!)

## Option 3: Use Existing Calibration Data + Interpolation

**For active_outdoors**:
- You have 56 locations with target scores
- Use those as seed data
- For remaining 121 locations:
  - Find similar locations (same area type, similar features)
  - Interpolate target scores
  - Or collect new target scores only for dissimilar locations

**Pros**: Leverages existing work
**Cons**: Less accurate for dissimilar locations

## Recommended Approach

### Step 1: Collect Current Scores (No Target Scores Needed Yet)

**Use existing collector or API**:
```bash
# If you have collector.py
python scripts/collector.py

# Or call API directly for each location
# This gives you current scores + component breakdowns
```

**Output**: JSON file with:
- Current scores for each pillar
- Raw component scores
- Area types
- Coordinates

### Step 2: Add Target Scores

**For each location + pillar**:

1. **Review current score** and component breakdown
2. **Evaluate**: Is the current score correct?
3. **Set target score**: What should it be?
4. **Source**: LLM evaluation, expert judgment, or user feedback

### Step 3: Calculate Calibration

**Run linear regression**:
```python
# For active_outdoors
from scipy import stats
raw_scores = [location['raw_total'] for location in locations]
target_scores = [location['target_score'] for location in locations]

slope, intercept, r_value, p_value, std_err = stats.linregress(raw_scores, target_scores)

CAL_A = slope
CAL_B = intercept
```

## Files You Need

1. **Input**: List of 177 locations (from `data/locations.csv` or `pillar_regression_data.json`)
2. **Current Scores**: API responses with pillar breakdowns
3. **Target Scores**: LLM evaluations or expert judgments
4. **Output**: Calibration parameters (`CAL_A`, `CAL_B`)

## Scripts Created

- `scripts/collect_calibration_data.py`: Template for collecting current scores
- `analysis/calibration_data_collection_plan.md`: Detailed plan
- `analysis/how_to_get_calibration_scores.md`: This document

## Next Steps

1. **Check if you have API results** for 177 locations (`data/results.csv`)
2. **If yes**: Extract pillar scores and components
3. **If no**: Run collector or API calls to get scores
4. **Add target scores**: Use LLM evaluation (like previous calibration)
5. **Calculate calibration**: Run regression to get parameters
6. **Apply calibration**: Update pillars with new parameters

## Questions?

- **Where do target scores come from?** LLM evaluation (like `neighborhood_amenities_calibration_panel.json`)
- **Do I need all 177?** Ideally yes, but can start with subset and expand
- **Which pillars?** Priority: `natural_beauty` (no calibration), then improve `active_outdoors` (currently 56 locations)
