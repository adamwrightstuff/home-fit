# Calibration Data Extracted Successfully ✅

## Summary

Successfully extracted calibration data for **177 locations** from `data/results.csv`.

## What Was Extracted

### File Created
- `analysis/calibration_data_177_locations.json`

### Data Per Location
- ✅ **Current scores** for `active_outdoors` and `natural_beauty`
- ✅ **Raw component scores** (for calculating calibration)
- ✅ **Area types** (from API responses)
- ⚠️ **Target scores**: Empty (need to add)

### Structure
```json
{
  "name": "Location Name",
  "area_type": "urban_core",
  "pillars": {
    "active_outdoors": {
      "current_score": 76.2,
      "raw_total": 32.5,
      "components": {
        "daily_urban_outdoors": 28.0,
        "wild_adventure": 41.0,
        "waterfront_lifestyle": 18.0
      }
    },
    "natural_beauty": {
      "current_score": 98.6,
      "raw_total": 68.0,
      "components": {
        "tree_score": 50.0,
        "natural_bonus_scaled": 18.0
      }
    }
  },
  "target_scores": {
    "active_outdoors": null,  // ← Need to add
    "natural_beauty": null    // ← Need to add
  }
}
```

## Next Steps: Add Target Scores

### Option 1: LLM Evaluation (Recommended)

**Process** (same as `neighborhood_amenities_calibration_panel.json`):

1. For each location, ask LLM:
   - "What should the active_outdoors score be (0-100) for [location]?"
   - "What should the natural_beauty score be (0-100) for [location]?"

2. Use multiple LLMs (Claude, Gemini, Perplexity) and take average

3. Update `target_scores` field in JSON file

**Example**:
```json
"target_scores": {
  "active_outdoors": 75.0,  // From LLM evaluation
  "natural_beauty": 85.0   // From LLM evaluation
}
```

### Option 2: Manual Review

1. Review current score and component breakdown
2. Evaluate if current score is correct
3. Set target score based on expert judgment
4. Update JSON file

### Option 3: Use Existing Calibration Data

**For active_outdoors**:
- You have 56 locations with target scores in `active_outdoors_tuning_from_ridge.json`
- Match those locations and copy target scores
- Collect remaining 121 locations

**For natural_beauty**:
- No existing target scores
- Need to collect all 177

## After Adding Target Scores

### Calculate Calibration Parameters

```python
import json
from scipy import stats

# Load calibration data
with open('analysis/calibration_data_177_locations.json') as f:
    data = json.load(f)

# Extract data for active_outdoors
locations = data['locations']
raw_scores = []
target_scores = []

for loc in locations:
    ao = loc['pillars'].get('active_outdoors')
    target = loc['target_scores'].get('active_outdoors')
    
    if ao and target is not None:
        raw_scores.append(ao['raw_total'])
        target_scores.append(target)

# Calculate calibration
slope, intercept, r_value, p_value, std_err = stats.linregress(raw_scores, target_scores)

CAL_A = slope
CAL_B = intercept

print(f"CAL_A: {CAL_A}")
print(f"CAL_B: {CAL_B}")
print(f"R²: {r_value**2}")
```

### Apply Calibration

Update `pillars/active_outdoors.py` and `pillars/natural_beauty.py` with new calibration parameters.

## Files Created

- ✅ `analysis/calibration_data_177_locations.json`: Extracted calibration data
- ✅ `scripts/extract_calibration_data_from_results.py`: Extraction script
- ✅ `analysis/calibration_data_extracted.md`: This document

## Status

- ✅ **Current scores**: Extracted for 177 locations
- ✅ **Raw component scores**: Extracted for 177 locations
- ✅ **Area types**: Extracted for 177 locations
- ⚠️ **Target scores**: Need to add (via LLM evaluation or manual)

## Quick Start

1. **Review extracted data**:
   ```bash
   cat analysis/calibration_data_177_locations.json | jq '.locations[0]'
   ```

2. **Add target scores** (use LLM evaluation or manual review)

3. **Calculate calibration** (run regression on raw vs target scores)

4. **Apply calibration** (update pillar files with new parameters)
