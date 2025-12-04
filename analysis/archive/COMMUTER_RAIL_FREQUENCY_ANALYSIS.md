# Commuter Rail Suburb Frequency Analysis

## Overview

This analysis examines the relationship between service frequency metrics and transit scores for commuter rail suburbs, validating the hypothesis that "quantity of routes is not the metric but rather commute time and number of times the train runs per day."

## Data Summary

**Sample Size:** 16 commuter rail suburb locations  
**Locations with Frequency Data:** 8 (locations with heavy rail routes)  
**Data Collection Date:** November 24, 2024

## Key Findings

### 1. Route Count vs Score Correlation

**Correlation: r = 0.933** (very strong positive correlation)

**Observation:** Locations with 2 heavy rail routes consistently score higher (47-63) than locations with 1 route (47-52).

**Examples:**
- **2 routes:** Evanston IL (62.5), Oak Park IL (61.9), Montclair NJ (61.4), Ardmore PA (58.0)
- **1 route:** Pleasanton CA (52.4), Cherry Hill NJ (52.3), Scarsdale NY (47.4), Bronxville NY (47.4)

**Conclusion:** Route count is still a significant factor, but this may be confounded by other factors (commute time, frequency, service quality).

### 2. Peak Headway vs Score Correlation

**Correlation: r = -0.265** (weak negative correlation)

**Observation:** Shorter peak headways (more frequent service) show a weak tendency toward higher scores, but the relationship is not strong.

**Examples:**
- **High Frequency (<15 min):** Montclair NJ (6.3 min → 61.4), Oak Park IL (14.7 min → 61.9), Ardmore PA (14.4 min → 58.0)
- **Lower Frequency (>20 min):** Evanston IL (28.9 min → 62.5), Scarsdale NY (22.3 min → 47.4), Pleasanton CA (60.0 min → 52.4)

**Notable Exception:** Evanston IL has the highest score (62.5) despite having the longest peak headway (28.9 min) among the 2-route locations. This suggests other factors (commute time, service span, route quality) may be more important.

### 3. Weekday Trips vs Score Correlation

**Correlation: r = 0.538** (moderate positive correlation)

**Observation:** More weekday trips correlate with higher scores, but the relationship is moderate.

**Examples:**
- **High Trip Count:** Montclair NJ (328 trips → 61.4), Oak Park IL (130 trips → 61.9)
- **Lower Trip Count:** Pleasanton CA (4 trips → 52.4), Scarsdale NY (43 trips → 47.4), Bronxville NY (61 trips → 47.4)

**Conclusion:** Trip count is a meaningful factor, but not the sole determinant.

### 4. Commute Time vs Score Correlation

**Correlation: r = 0.485** (moderate positive correlation, inverse relationship)

**Observation:** Shorter commute times correlate with higher transit scores.

**Examples:**
- **Short Commute:** Evanston IL (24.7 min → 62.5), Ardmore PA (26.5 min → 58.0)
- **Long Commute:** Scarsdale NY (40.9 min → 47.4), Bronxville NY (40.7 min → 47.4)

**Conclusion:** Commute time is a significant factor, supporting the hypothesis that "commute time" matters for commuter rail suburbs.

## Hypothesis Validation

### Original Hypothesis
> "For commuter rail towns, quantity of routes is not the metric but rather commute time and number of times the train runs per day."

### Validation Results

**✅ Partially Supported:**
1. **Commute time** shows moderate correlation (r=0.485) with scores - **SUPPORTED**
2. **Weekday trips** (number of times train runs) shows moderate correlation (r=0.538) - **SUPPORTED**
3. **Route count** still shows very strong correlation (r=0.933) - **CONTRADICTS** the hypothesis

**Key Insight:** Route count is still the strongest predictor, but this may be because:
- Locations with 2 routes tend to have better service quality overall
- Route count may be a proxy for service coverage and connectivity
- The sample size (8 locations with frequency data) may be too small to fully validate the hypothesis

### Within-Group Analysis (Same Route Count)

**2-Route Locations:**
- Evanston IL: 28.9 min peak, 24.7 min commute → 62.5 score (highest)
- Oak Park IL: 14.7 min peak, 34.0 min commute → 61.9 score
- Montclair NJ: 6.3 min peak, 37.4 min commute → 61.4 score
- Ardmore PA: 14.4 min peak, 26.5 min commute → 58.0 score

**Observation:** Within the 2-route group, commute time appears to be a stronger predictor than frequency:
- Evanston (shortest commute, 24.7 min) scores highest despite longest headway (28.9 min)
- Montclair (most frequent, 6.3 min) scores lower despite shortest headway, likely due to longer commute (37.4 min)

**1-Route Locations:**
- Pleasanton CA: 60.0 min peak, 4 trips, 26.8 min commute → 52.4 score
- Cherry Hill NJ: 18.5 min peak, 46 trips, 30.3 min commute → 52.3 score
- Scarsdale NY: 22.3 min peak, 43 trips, 40.9 min commute → 47.4 score
- Bronxville NY: 18.8 min peak, 61 trips, 40.7 min commute → 47.4 score

**Observation:** Within the 1-route group, commute time appears to be the strongest predictor:
- Pleasanton (shortest commute, 26.8 min) scores highest despite worst frequency (60 min peak, 4 trips)
- Scarsdale/Bronxville (longest commutes, ~40 min) score lowest despite better frequency

## Recommendations

### 1. Multi-Factor Scoring Model

For commuter rail suburbs, transit scores should consider:
- **Route count** (still important, but not sole factor)
- **Commute time** (moderate weight - shorter is better)
- **Service frequency** (moderate weight - more frequent is better)
- **Service span** (all locations have 16-20 hours, so less differentiating)

### 2. Contextual Scoring Approach

**For commuter rail suburbs:**
- Base score from route count (current approach)
- **Frequency bonus:** Add points for peak headway < 20 min and weekday trips > 50
- **Commute bonus:** Add points for commute time < 30 min
- **Service quality bonus:** Combine frequency and commute for exceptional service

### 3. Expected Values Update

Based on research data:
- **Peak headway:** median = 18.6 min (p25=14.5, p75=27.2)
- **Off-peak headway:** median = 24.0 min (p25=18.8, p75=47.3)
- **Service span:** median = 18.0 hours (p25=16.7, p75=19.7)
- **Weekday trips:** median = 54 (p25=44, p75=126)

These can be used to normalize frequency metrics in scoring.

### 4. Weight Adjustments

Consider increasing the weight of `commute_time` component from 10% to 15-20% for commuter rail suburbs, as it shows moderate correlation with overall scores.

## Next Steps

1. **Design frequency-based scoring component** that rewards:
   - Peak headway < 20 min (above median)
   - Weekday trips > 50 (above median)
   - Service span > 18 hours (above median)

2. **Implement commute time bonus** for commuter rail suburbs:
   - Commute < 25 min: +5 points
   - Commute < 30 min: +3 points
   - Commute < 35 min: +1 point

3. **Test against target locations:**
   - Bronxville NY (target: 85) - currently 47.4
   - Scarsdale NY (target: ~75) - currently 47.4
   - Montclair NJ (target: ~70) - currently 61.4

4. **Validate with full dataset** once all 16 locations have frequency data (if possible).

## Data Quality Notes

- **8/16 locations** have frequency data (only those with heavy rail routes)
- **Pleasanton CA** has outlier frequency (60 min peak, 4 trips) - may indicate data quality issue or genuinely infrequent service
- **Montclair NJ** has outlier trip count (328 trips) - may indicate multiple routes or data aggregation issue

## Conclusion

The hypothesis is **partially supported**: commute time and service frequency (weekday trips) do matter for commuter rail suburbs, but route count remains the strongest predictor. A multi-factor scoring model that combines route count, frequency, and commute time would better reflect transit quality in these areas.

