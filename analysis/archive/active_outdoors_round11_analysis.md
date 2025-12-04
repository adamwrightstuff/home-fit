# Active Outdoors Round 11 Analysis

## Summary Stats

### Fit vs Target Categories
- **Low**: 11 locations (scoring below target)
- **High**: 6 locations (scoring above target)  
- **Within range/Target**: 2 locations (on target)

### Key Observations

#### Low Scores (Below Target):
1. **Bethesda MD** - Score: 66.3, Target: 80, Gap: -13.7
   - Daily: 25/30 ✓, Wild: 17.6/50 ✗, Water: 3.6/20 ✗
   - Issue: Very low wild adventure (trails/camping/canopy) and water

2. **Boulder CO** - Score: 79.1, Target: 95, Gap: -15.9
   - Daily: 23.4/30, Wild: 31.4/50, Water: 7.7/20
   - Note: Duplicate row (same as Boston Back Bay)? Need to verify actual Boulder data

3. **Downtown Chicago IL** - Score: 65.3, Target: 83, Gap: -17.7
   - Daily: 20.8/30, Wild: 14.3/50 ✗, Water: 15.2/20 ✓
   - Issue: Low wild adventure despite urban core expectations

4. **Downtown Denver CO** - Score: 67.7, Target: 92, Gap: -24.3
   - Daily: 20.7/30, Wild: 15.2/50 ✗, Water: 20/20 ✓
   - Issue: Low wild adventure

5. **Downtown Portland OR** - Score: 79.3, Target: 88, Gap: -8.7
   - Daily: 24/30 ✓, Wild: 26.3/50, Water: 20/20 ✓
   - Note: Small gap, might be calibration issue

6. **Downtown Seattle WA** - Score: 74.6, Target: 92, Gap: -17.4
   - Daily: 21.7/30, Wild: 25.2/50, Water: 12.8/20
   - Issue: Water access could be higher given Puget Sound

7. **Park City UT** - Score: 81.6, Target: 92, Gap: -10.4
   - Daily: 24.8/30 ✓, Wild: 32.6/50, Water: 9.7/20
   - Note: Mountain town, wild adventure should be higher

8. **Santa Monica CA** - Score: 62.1, Target: 78, Gap: -15.9
   - Daily: 6.8/30 ✗, Wild: 17.1/50 ✗, Water: 20/20 ✓
   - Issue: Very low daily urban outdoors despite being beachside

#### High Scores (Above Target):
1. **Downtown Las Vegas NV** - Score: 50.6, Target: 42, Gap: +8.6
   - Daily: 6.7/30 ✗, Wild: 9.2/50 ✗, Water: 7.8/20 ✗
   - Note: All components low but score still above target (low target)

2. **Downtown Phoenix AZ** - Score: 68.7, Target: 48, Gap: +20.7
   - Daily: 22.2/30, Wild: 17.6/50, Water: 14.4/20
   - Issue: Significantly over-scoring

3. **Miami Beach FL** - Score: 87.3, Target: 60, Gap: +27.3
   - Daily: 24.1/30 ✓, Wild: 35.3/50, Water: 20/20 ✓
   - Issue: Very high score vs low target (rural classification issue?)

4. **Park Slope Brooklyn NY** - Score: 85.9, Target: 70, Gap: +15.9
   - Daily: 25/30 ✓, Wild: 34.4/50, Water: 16.9/20 ✓
   - Issue: Over-scoring for urban_core

5. **Times Square NY** - Score: 64.3, Target: 35, Gap: +29.3
   - Daily: 18.2/30, Wild: 15.7/50, Water: 12.8/20
   - Issue: Major over-scoring

6. **Upper West Side New York NY** - Score: 80.5, Target: 72, Gap: +8.5
   - Daily: 25/30 ✓, Wild: 27.9/50, Water: 18/20 ✓
   - Note: Moderate over-scoring

#### On Target:
1. **Boston Back Bay MA** - Score: 79.1, Target: 75, Gap: +4.1 ✓
2. **Truckee CA** - Score: 90.4, Target: 95, Gap: -4.6 ✓

## Patterns

### 1. Urban Core Over-scoring
- Times Square, Park Slope, Upper West Side all scoring higher than targets
- Wild adventure component may be too generous for dense urban areas
- Tree canopy in urban cores might be contributing too much to wild score

### 2. Mountain Towns Under-scoring
- Boulder, Park City, Downtown Denver, Downtown Seattle all below target
- Wild adventure component may not be recognizing trail density adequately
- Camping proximity might need better weighting

### 3. Water Access Inconsistencies
- Santa Monica: Has water but very low daily score (likely data issue)
- Downtown Seattle: Lower water score than expected for Puget Sound
- Downtown Phoenix: Has water but shouldn't score that high overall

### 4. Daily Urban Outdoors Issues
- Santa Monica: 6.8/30 is suspiciously low for a beachside area
- Bethesda: 25/30 is good but other components dragging it down

## Recommendations

1. **Review Wild Adventure Backbone scoring for urban_core**
   - Tree canopy contribution might be too high
   - Trail count expectations might need area-type adjustment
   
2. **Adjust water access scoring**
   - Distance decay might be too aggressive
   - Type weighting (beach vs lake) might need refinement

3. **Calibration recalibration needed**
   - Current CAL_A=1.768, CAL_B=36.202 may need adjustment
   - Mean absolute error appears to be >10 points based on gaps

4. **Data quality checks**
   - Santa Monica daily score suggests missing park data
   - Boulder row appears duplicate (same as Boston Back Bay)

5. **Area type classification review**
   - Miami Beach classified as "rural" seems wrong
   - Some locations might need re-classification
