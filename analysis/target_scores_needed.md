# Target Scores Needed

## Summary

### active_outdoors
- **Total locations**: 177
- **Already have target scores**: 56 locations (from `active_outdoors_tuning_from_ridge.json`)
- **Need target scores**: **121 locations**

### natural_beauty
- **Total locations**: 177
- **Already have target scores**: 0 locations (none exist)
- **Need target scores**: **177 locations**

## Priority Recommendation

### Option 1: Start with active_outdoors (121 missing)
- **Why**: Already have 56 locations, can use as reference
- **Benefit**: Improves calibration from 56 → 177 locations
- **Effort**: Medium (121 locations)

### Option 2: Start with natural_beauty (177 needed)
- **Why**: Currently has no calibration
- **Benefit**: Adds calibration for first time
- **Effort**: High (all 177 locations)

### Option 3: Do Both (298 total)
- **Why**: Complete calibration for both pillars
- **Benefit**: Best calibration accuracy
- **Effort**: High (298 target scores)

## Locations List

See `analysis/calibration_data_177_locations.json` for full list of 177 locations.

To get the list of locations needing target scores, run:
```bash
python3 scripts/list_locations_needing_target_scores.py
```

## Next Steps

1. **Decide priority**: Which pillar first? (recommend: active_outdoors)
2. **Collect target scores**: Use LLM evaluation or manual review
3. **Update JSON**: Add target scores to `calibration_data_177_locations.json`
4. **Calculate calibration**: Run regression on raw vs target scores
5. **Apply calibration**: Update pillar files
