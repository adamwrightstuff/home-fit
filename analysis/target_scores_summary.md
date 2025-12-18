# Target Scores Needed - Summary

## Quick Answer

### active_outdoors
- **Need**: 172 locations
- **Have**: 56 locations (already calibrated)
- **Total**: 177 locations

### natural_beauty  
- **Need**: 177 locations
- **Have**: 0 locations (no calibration exists)
- **Total**: 177 locations

## Detailed Breakdown

### active_outdoors (172 locations need target scores)

**Already have target scores (56 locations):**
- Altadena CA, Ann Arbor MI, Arlington VA, Babylon NY, Back Bay Boston MA, Bar Harbor ME, Beacon Hill Boston MA, Beaufort SC, Bend OR, Bethesda MD, Big Bear Lake CA, Bozeman MT, Bronxville NY, Brooklyn Heights Brooklyn NY, Burlington VT, Carmel-by-the-Sea CA, Celebration FL, Centennial CO, Chicago IL (Downtown), Cleveland OH, Coconut Grove Miami FL, Downtown Austin TX, Downtown Boston MA, Downtown Chicago IL, Downtown Denver CO, Downtown Los Angeles CA, Downtown Minneapolis MN, Downtown Philadelphia PA, Downtown Portland ME, Downtown Portland OR, Downtown San Diego CA, Downtown San Francisco CA, Downtown Seattle WA, Durham NC, Federal Triangle Washington DC, Fells Point Baltimore MD, Fishtown Philadelphia PA, Fitler Square Philadelphia PA, Forest Grove OR, French Quarter New Orleans LA, Garden District New Orleans LA, Georgetown Washington DC, Hermosa Beach CA, Hood River OR, Houston Medical Center TX, Hudson OH, Inner Harbor Baltimore MD, Irvine CA, Jackson Wyoming, Kiawah Island SC, Lake Placid NY

**Need target scores (172 locations):**
See `analysis/locations_needing_target_scores.txt` for full list.

### natural_beauty (177 locations need target scores)

**All 177 locations need target scores** (none exist currently):
- See `analysis/locations_needing_target_scores.txt` for full list.

## Priority Recommendation

### Option 1: Complete active_outdoors First (Recommended)
- **Why**: Already have 56 locations, can improve calibration from 56 → 177
- **Effort**: 172 target scores
- **Benefit**: Better calibration accuracy

### Option 2: Start natural_beauty
- **Why**: Currently has no calibration at all
- **Effort**: 177 target scores  
- **Benefit**: Adds calibration for first time

### Option 3: Do Both
- **Effort**: 349 total target scores (172 + 177)
- **Benefit**: Complete calibration for both pillars

## How to Add Target Scores

### Method 1: LLM Evaluation (Recommended)

For each location, ask LLM:
- "What should the active_outdoors score be (0-100) for [location]?"
- "What should the natural_beauty score be (0-100) for [location]?"

Use multiple LLMs (Claude, Gemini, Perplexity) and take average.

### Method 2: Manual Review

1. Review current score and component breakdown
2. Evaluate if current score is correct
3. Set target score based on expert judgment

### Update Process

1. Open `analysis/calibration_data_177_locations.json`
2. Find location in `locations` array
3. Update `target_scores` field:
   ```json
   "target_scores": {
     "active_outdoors": 75.0,  // Add target score
     "natural_beauty": 85.0    // Add target score
   }
   ```
4. Save file

## Files

- `analysis/calibration_data_177_locations.json`: All 177 locations with current scores (ready for target scores)
- `analysis/locations_needing_target_scores.txt`: Full list of locations needing target scores
- `scripts/list_locations_needing_target_scores.py`: Script to list locations

## Next Steps

1. **Decide priority**: Which pillar first? (recommend: active_outdoors)
2. **Collect target scores**: Use LLM evaluation or manual review
3. **Update JSON**: Add target scores to `calibration_data_177_locations.json`
4. **Calculate calibration**: Run regression on raw vs target scores
5. **Apply calibration**: Update pillar files with new parameters
