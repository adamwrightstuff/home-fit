# Commuter Rail Suburb Transit Analysis

## Research Data Summary

**Sample Size:** 16 commuter rail suburb locations  
**Data Collection Date:** November 24, 2024  
**Data Source:** Transitland API + Census ACS

## Key Findings

### Route Counts (Validated ✅)

- **Heavy Rail Routes:** median = 1 (p25=0, p75=2, range: 0-5)
- **Bus Routes:** median = 8 (p25=4, p75=12, range: 2-60)
- **Light Rail Routes:** median = 0 (rare in commuter suburbs)

**Validation:** These match our expected values in `regional_baselines.py`:
- `expected_heavy_rail_routes = 1` ✅
- `expected_bus_routes = 8` ✅

### Transit Scores

- **Overall Transit Score:** median = 59.7 (p25=47.5, p75=72.5, range: 0-83.7)
- **Heavy Rail Score:** median = 40.0 (p25=0, p75=55, range: 0-72)
- **Bus Score:** median = 37.5 (p25=16.2, p75=46.6, range: 0-78.7)
- **Commute Time Score:** median = 85.0 (p25=75.6, p75=85.0, range: 68.7-85.0)

### Commute Times

- **Mean Commute Minutes:** median = 28.4 (p25=25.5, p75=36.3, range: 16.3-40.9)
- **Observation:** Commute times are relatively consistent (25-36 min range for most locations)
- **Correlation:** Higher commute scores (shorter commutes) correlate with higher overall transit scores

## Hypothesis Validation Status

### ✅ Supported by Current Data

1. **Route count alone is insufficient:** 
   - Locations with 1 heavy rail route score ~40 points (meets expectation)
   - But overall scores vary significantly (0-83.7) despite similar route counts
   - This suggests other factors (commute time, frequency, reliability) matter

2. **Commute time is important:**
   - Median commute time (28.4 min) is reasonable for commuter rail suburbs
   - Commute scores are high (median 85.0), indicating good commute times
   - Shorter commutes correlate with higher transit scores

### ❓ Needs Additional Data

1. **Service frequency (headways):**
   - **Status:** Not available from Transitland API
   - **Impact:** Cannot validate "number of times the train runs per day" hypothesis
   - **Need:** Alternative data source (GTFS feeds, agency APIs)

2. **Reliability (on-time performance):**
   - **Status:** Not available
   - **Impact:** Cannot validate "reliability is key" hypothesis
   - **Need:** GTFS-RT or agency-specific APIs

3. **Service span:**
   - **Status:** Not available
   - **Impact:** Cannot assess if "sufficient frequency" varies by time of day
   - **Need:** GTFS schedule data

## Current Scoring Behavior

### What Works

- **Route count normalization:** 1 route = 40 points (meets expectation) ✅
- **Commute time weighting:** 10% weight, high scores (median 85.0) ✅
- **Area type detection:** Commuter rail suburbs correctly identified ✅

### What's Missing

- **Frequency-based scoring:** Cannot differentiate between:
  - 1 route with 10-minute peak headway (excellent service)
  - 1 route with 60-minute peak headway (poor service)
  - Both currently score the same (40 points)

- **Service quality metrics:** Cannot assess:
  - Travel time to major hub vs. car travel time
  - On-time performance
  - Service span (first/last train)

## Recommendations

### Short-Term (Use Available Data)

1. **Enhance commute time scoring:**
   - Current: 10% weight, already working well
   - Consider: Increase weight to 15-20% for commuter rail suburbs (commute time is primary concern)

2. **Add route quality proxy:**
   - Use route count + commute time as proxy for service quality
   - Locations with 1 route + short commute (<30 min) = good service
   - Locations with 1 route + long commute (>40 min) = poor service

### Medium-Term (Get Frequency Data)

1. **GTFS Feed Integration:**
   - Download GTFS feeds for major commuter rail operators (Metro-North, Metra, Caltrain, etc.)
   - Parse `stop_times.txt` to calculate:
     - Peak/off-peak headways
     - Service span (first/last departure)
     - Weekday trip counts
   - Store in local database/cache for fast queries

2. **Alternative: Agency APIs:**
   - Some agencies provide schedule APIs (e.g., MTA, MBTA)
   - Query directly for headway/service span data
   - More reliable but requires per-agency integration

### Long-Term (Full Contextual Scoring)

1. **Implement frequency-based scoring:**
   - For commuter rail suburbs, weight frequency more heavily than route count
   - Example: 1 route with 15-min peak headway > 2 routes with 60-min headway

2. **Add reliability metrics:**
   - Integrate GTFS-RT for on-time performance
   - Weight reliability heavily for commuter suburbs (as per hypothesis)

3. **Service quality assessment:**
   - Calculate travel time to major hub
   - Compare to car travel time (Google Maps API)
   - Score based on transit competitiveness

## Next Steps

1. ✅ **Research data collected** (route counts, commute times, scores)
2. 🔄 **Analyze patterns** in current data (this document)
3. ⏭️ **Design frequency data collection** (GTFS feed integration)
4. ⏭️ **Implement contextual scoring** based on research findings
5. ⏭️ **Validate** against benchmark locations

## Data Gaps

| Metric | Status | Source Needed |
|--------|--------|---------------|
| Route counts | ✅ Available | Transitland API |
| Commute times | ✅ Available | Census ACS |
| Peak headways | ❌ Missing | GTFS feeds or agency APIs |
| Off-peak headways | ❌ Missing | GTFS feeds or agency APIs |
| Service span | ❌ Missing | GTFS feeds or agency APIs |
| Weekday trip counts | ❌ Missing | GTFS feeds or agency APIs |
| On-time performance | ❌ Missing | GTFS-RT or agency APIs |
| Travel time to hub | ❌ Missing | Google Maps API or GTFS routing |

## Conclusion

The research data confirms that:
- Route count alone is insufficient for commuter rail suburbs
- Commute time is an important factor (already captured)
- **Service frequency is critical but not yet measurable**

To fully validate the hypothesis that "quantity of routes is not the metric but rather commute time and number of times the train runs per day," we need to integrate GTFS feed data to calculate service frequency metrics.

