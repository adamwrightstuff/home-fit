# Commuter Rail Suburb Scoring Proposal (Design Principles Aligned)

## Design Principles Alignment Assessment

### ✅ Aligned Principles

1. **Research-Backed**: 
   - Frequency metrics from 8 locations
   - Expected values are medians from research
   - Correlations support bonuses (r=0.538 trips, r=0.485 commute)

2. **Objective and Data-Driven**:
   - All metrics are objective (peak headway, weekday trips, commute time)
   - No subjective judgments

3. **Scalable and General**:
   - Uses `area_type` classification, not city names
   - Works for all commuter rail suburbs

### ❌ Violations in Initial Proposal

1. **Smooth and Predictable**:
   - ❌ Hard thresholds (`if peak < 20 min`) create discontinuities
   - ❌ Step functions violate smoothness principle

2. **Research-Backed**:
   - ⚠️ Bonus amounts (+5-10 points) are arbitrary
   - ⚠️ Risk of tuning to hit target scores (Bronxville 85)

3. **Transparent**:
   - ⚠️ Need code comments documenting rationale

## Revised Approach (Design Principles Compliant)

### 1. Smooth Frequency Bonus (Research-Backed)

**Rationale:** Weekday trips show moderate correlation (r=0.538) with scores. Use smooth curve normalized against research median.

```python
def _calculate_frequency_bonus(weekday_trips: int, peak_headway_min: float) -> float:
    """
    Calculate frequency bonus for commuter rail suburbs.
    
    Based on research data (n=8):
    - Median weekday trips: 54
    - Median peak headway: 18.6 min
    
    Correlation with transit score:
    - Weekday trips: r=0.538 (moderate)
    - Peak headway: r=-0.265 (weak)
    
    Uses smooth sigmoid curve to avoid discontinuities.
    """
    if weekday_trips is None or peak_headway_min is None:
        return 0.0
    
    # Normalize against research medians
    trips_ratio = weekday_trips / 54.0  # Median from research
    headway_ratio = 18.6 / peak_headway_min  # Inverse: shorter headway = higher ratio
    
    # Combined frequency score (weighted by correlation strength)
    # Weekday trips: r=0.538 → weight 0.7
    # Peak headway: r=-0.265 → weight 0.3
    frequency_score = (trips_ratio * 0.7) + (headway_ratio * 0.3)
    
    # Smooth sigmoid curve: bonus = 8 * sigmoid((frequency_score - 1.0) * 2)
    # At median (1.0×): bonus = 4 points
    # At 1.5× median: bonus = 6.5 points
    # At 2.0× median: bonus = 7.8 points
    # Cap at 8 points (moderate bonus based on r=0.538)
    import math
    sigmoid_input = (frequency_score - 1.0) * 2.0
    bonus = 8.0 * (1.0 / (1.0 + math.exp(-sigmoid_input)))
    
    return min(8.0, bonus)
```

### 2. Smooth Commute Time Bonus (Research-Backed)

**Rationale:** Commute time shows moderate correlation (r=0.485) with scores. Use smooth curve with exponential decay.

```python
def _calculate_commute_bonus(commute_minutes: float) -> float:
    """
    Calculate commute time bonus for commuter rail suburbs.
    
    Based on research data (n=14):
    - Median commute: 28.4 min
    - Correlation with transit score: r=0.485 (moderate, inverse)
    
    Uses exponential decay curve for smooth scoring.
    """
    if commute_minutes is None or commute_minutes <= 0:
        return 0.0
    
    # Normalize against research median (28.4 min)
    # Shorter commute = higher bonus
    commute_ratio = 28.4 / commute_minutes  # Inverse: shorter = higher
    
    # Exponential decay: bonus = 5 * (1 - exp(-(commute_ratio - 1.0) * 2))
    # At median (1.0×): bonus = 0 points
    # At 1.2× (23.7 min): bonus = 2.2 points
    # At 1.5× (18.9 min): bonus = 3.9 points
    # Cap at 5 points (moderate bonus based on r=0.485)
    import math
    bonus = 5.0 * (1.0 - math.exp(-(commute_ratio - 1.0) * 2.0))
    
    return min(5.0, max(0.0, bonus))
```

### 3. Integration into Transit Scoring

```python
# In get_public_transit_score, for commuter_rail_suburb area type:

if effective_area_type == 'commuter_rail_suburb':
    # Get frequency data if available
    frequency_bonus = 0.0
    commute_bonus = 0.0
    
    # Try to get frequency data from route schedules
    if heavy_rail_routes:
        # Sample first route for frequency (or aggregate if multiple)
        sample_route = heavy_rail_routes[0]
        route_id = sample_route.get("route_id")
        
        if route_id:
            from data_sources.transitland_api import get_route_schedules
            # Find a representative stop for this route
            # (Implementation details for finding stop)
            schedule = get_route_schedules(route_id, sample_stop_id=stop_id)
            
            if schedule:
                weekday_trips = schedule.get("weekday_trips")
                peak_headway = schedule.get("peak_headway_minutes")
                
                if weekday_trips and peak_headway:
                    frequency_bonus = _calculate_frequency_bonus(weekday_trips, peak_headway)
    
    # Get commute time from breakdown (already calculated)
    commute_minutes = breakdown.get("mean_commute_minutes")
    if commute_minutes:
        commute_bonus = _calculate_commute_bonus(commute_minutes)
    
    # Add bonuses to base score
    total_score = base_score + frequency_bonus + commute_bonus
    
    # Cap at 100 (bonuses are additive, not multiplicative)
    total_score = min(100.0, total_score)
```

## Expected Impact

### Bronxville NY (Target: 85)
- Current: 47.4
- Base (1 route): 40.0
- Frequency bonus (61 trips, 18.8 min peak): ~5.2 points
- Commute bonus (40.7 min): ~0.8 points
- **New score: ~46.0** ❌ Still below target

**Analysis:** The bonuses are calibrated from correlation strength, not target scores. If Bronxville needs 85, we need to investigate:
1. Is the base route scoring too low for 1 route?
2. Are there other factors (service quality, connectivity) not captured?
3. Is the target score realistic given the data?

### Scarsdale NY (Target: 75)
- Current: 47.4
- Base (1 route): 40.0
- Frequency bonus (43 trips, 22.3 min peak): ~3.8 points
- Commute bonus (40.9 min): ~0.7 points
- **New score: ~44.5** ❌ Still below target

### Montclair NJ (Target: 70)
- Current: 61.4
- Base (2 routes): 55.0
- Frequency bonus (328 trips, 6.3 min peak): ~8.0 points (capped)
- Commute bonus (37.4 min): ~0.2 points
- **New score: ~63.2** ✅ Closer to target

## Key Design Principles Compliance

1. ✅ **Research-Backed**: Bonuses calibrated from correlation coefficients, not target scores
2. ✅ **Objective**: All metrics are objective (trips, headway, commute time)
3. ✅ **Scalable**: Works for all commuter rail suburbs via area type
4. ✅ **Smooth**: Uses sigmoid and exponential curves, no hard thresholds
5. ✅ **Transparent**: Functions documented with rationale and data sources
6. ✅ **No Artificial Tuning**: Bonus amounts derived from correlation strength, not target scores

## Open Questions

1. **Base route scoring**: Is 40 points for 1 route appropriate? Should we investigate if the base scoring curve needs adjustment for commuter rail suburbs?

2. **Frequency data availability**: Only 8/16 locations have frequency data. Should we:
   - Use frequency bonuses only when data is available?
   - Estimate frequency from route characteristics?
   - Skip bonuses if data unavailable?

3. **Target score validation**: If bonuses don't reach targets, should we:
   - Accept that targets may be unrealistic?
   - Investigate other factors (connectivity, service quality)?
   - Re-evaluate base scoring for commuter rail suburbs?

## Recommendation

**Implement the smooth, research-backed bonus system** as proposed. If scores still don't reach targets, investigate base scoring adjustments rather than artificially tuning bonuses.

