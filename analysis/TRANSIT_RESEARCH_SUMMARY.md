# Transit Contextual Scoring Research - Summary

## Status: Phase 1 Complete ✅

**Date:** November 24, 2024  
**Research Pass:** Commuter Rail Suburbs (16 locations)

## Executive Summary

We've successfully collected research data for 16 commuter rail suburb locations. The data confirms our expected values (heavy rail median=1, bus median=8) and validates that **route count alone is insufficient** for scoring commuter rail suburbs. However, **service frequency data is not yet available** due to Transitland API limitations.

## Key Findings

### ✅ Validated Metrics

1. **Route Counts Match Expected Values:**
   - Heavy rail: median = 1 route (matches `expected_heavy_rail_routes = 1`)
   - Bus: median = 8 routes (matches `expected_bus_routes = 8`)

2. **Commute Time is Important:**
   - Median commute: 28.4 minutes (reasonable for commuter suburbs)
   - Commute scores: median = 85.0 (high, indicating good commute times)
   - **Correlation:** Shorter commutes → higher transit scores

3. **Route Count Alone Insufficient:**
   - Locations with 1 heavy rail route score 40-72 points (wide range)
   - Overall scores vary 0-83.7 despite similar route counts
   - **Conclusion:** Other factors (frequency, reliability, commute time) matter significantly

### ❌ Missing Critical Data

**Service Frequency Metrics (Not Available from Transitland API):**
- Peak/off-peak headways
- Service span (first/last departure)
- Weekday trip counts
- On-time performance

**Impact:** Cannot validate the hypothesis that "quantity of routes is not the metric but rather commute time and number of times the train runs per day" without frequency data.

## Top Performing Locations

| Location | Score | Heavy Rail | Bus | Commute | Notes |
|----------|-------|------------|-----|---------|-------|
| Greenwich CT | 83.7 | 0 routes | 60 routes | N/A | Excellent bus service |
| Brookline MA | 78.2 | 0 routes | 25 routes | 29.2 min | Strong bus network |
| Palo Alto CA | 74.2 | 4 routes | 33 routes | 35.9 min | Multiple rail lines |
| Naperville IL | 73.3 | 5 routes | 3 routes | 22.2 min | Many rail routes, short commute |
| Shaker Heights OH | 70.2 | 0 routes | 2 routes | 24.0 min | Limited routes but good commute |

**Observation:** Top scores come from either:
1. Excellent bus service (Greenwich, Brookline)
2. Multiple rail routes (Palo Alto, Naperville)
3. Short commute times (Naperville, Shaker Heights)

## Hypothesis Validation

### ✅ Partially Supported

**Hypothesis:** "For commuter rail towns, quantity of routes is not the metric but rather commute time and number of times the train runs per day."

**Supported:**
- ✅ Commute time correlates with transit scores
- ✅ Route count alone insufficient (wide score range for same route count)

**Not Yet Validated:**
- ❌ "Number of times the train runs per day" - **No frequency data available**
- ❌ Service quality (headways, reliability) - **Not measurable yet**

## Next Steps

### Immediate (Use Available Data)

1. **Enhance commute time weighting:**
   - Current: 10% weight
   - Proposal: Increase to 15-20% for commuter rail suburbs
   - Rationale: Commute time is primary concern for commuter rail users

2. **Add route quality proxy:**
   - Combine route count + commute time as service quality indicator
   - Formula: `service_quality = route_count_score * (1 + commute_bonus)`
   - Where `commute_bonus` scales with commute score

### Short-Term (Get Frequency Data)

1. **GTFS Feed Integration:**
   - Download GTFS feeds for major commuter rail operators
   - Parse `stop_times.txt` to calculate:
     - Peak headways (7-9 AM, 5-7 PM)
     - Off-peak headways
     - Service span (first/last departure)
     - Weekday trip counts
   - Store in local database/cache

2. **Priority Operators:**
   - Metro-North (NYC area - Bronxville, Scarsdale, etc.)
   - Metra (Chicago area - Naperville, etc.)
   - Caltrain (SF Bay area - Palo Alto, etc.)
   - MBTA Commuter Rail (Boston area - Brookline, etc.)

### Medium-Term (Full Contextual Scoring)

1. **Frequency-Based Scoring:**
   - For commuter rail suburbs, weight frequency more than route count
   - Example: 1 route with 15-min peak headway > 2 routes with 60-min headway
   - Use research data to calibrate breakpoints

2. **Reliability Integration:**
   - GTFS-RT for on-time performance
   - Weight reliability heavily (as per hypothesis)

3. **Service Quality Assessment:**
   - Travel time to major hub vs. car travel time
   - Score based on transit competitiveness

## Data Gaps & Solutions

| Gap | Solution | Priority |
|-----|----------|----------|
| Service frequency | GTFS feed integration | **HIGH** |
| On-time performance | GTFS-RT or agency APIs | Medium |
| Service span | GTFS feed integration | **HIGH** |
| Travel time to hub | Google Maps API or GTFS routing | Medium |

## Recommendations

### For Immediate Implementation

1. **Increase commute time weight** for commuter rail suburbs (15-20% vs. 10%)
2. **Add commute-based bonus** to route count scores
3. **Document limitations** in API responses (frequency data unavailable)

### For Full Hypothesis Validation

1. **Integrate GTFS feeds** for top 5-10 commuter rail operators
2. **Calculate frequency metrics** from schedule data
3. **Re-run research** with frequency data included
4. **Design contextual scoring** based on complete dataset

## Files Generated

- `analysis/research_data/expected_values_statistics.json` - Statistical summaries
- `analysis/research_data/expected_values_raw_data.json` - Raw location data
- `analysis/COMMUTER_RAIL_ANALYSIS.md` - Detailed analysis
- `analysis/TRANSIT_CONTEXTUAL_SCORING_PLAN.md` - Implementation plan
- `analysis/TRANSIT_RESEARCH_SUMMARY.md` - This summary

## Conclusion

The research confirms that route count alone is insufficient for commuter rail suburbs. Commute time is an important factor (already captured). However, **service frequency data is critical but not yet available** from Transitland API.

**To fully validate the hypothesis, we need GTFS feed integration to calculate service frequency metrics.**

