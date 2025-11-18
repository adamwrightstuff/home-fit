# Natural Beauty Baseline Scores - Updated

## ✅ Baseline Scores Captured

The regression test suite has been updated with actual baseline scores from production testing.

### Updated Locations (9 locations with actual scores):

| Location | Area Type | Baseline Score | Tolerance | Key Metrics |
|----------|-----------|----------------|-----------|-------------|
| **Old Town Scottsdale AZ** | urban_residential | 13.3 | ±3.0 | Arid, 0.4% water, 1.63% canopy |
| **Sedona AZ** | rural | 61.16 | ±5.0 | Arid, 0% water, 18.48% canopy, 14.54° slope |
| **Coconut Grove Miami FL** | suburban | 51.92 | ±8.0 | Tropical, 25.63% water, 17.37% canopy |
| **Manhattan Beach CA** | suburban | 30.5 | ±6.0 | Coastal, 11.63% water, 7.87% canopy |
| **Carmel-by-the-Sea CA** | suburban | 91.09 | ±5.0 | Coastal, 25.1% water, 25.5% canopy |
| **Garden District New Orleans LA** | suburban | 20.07 | ±5.0 | 2% canopy, 13.3% water, mature street trees |
| **Beacon Hill Boston MA** | historic_urban | 35.71 | ±5.0 | 7.65% canopy, 16.33% water |
| **Pearl District Portland OR** | historic_urban | 100.0 | ±5.0 | 5.06% canopy, 63.04% GVI (very high) |
| **Georgetown DC** | historic_urban | 100.0 | ±5.0 | 16.64% canopy, 69.99% GVI (very high) |

### Locations with Approximate Scores (4 locations):

These locations were not in the provided baseline data, so approximate scores are maintained:
- **Bronxville NY**: 75.0 (suburban, high canopy, historic)
- **The Woodlands TX**: 60.0 (suburban, planned community)
- **Stowe VT**: 70.0 (rural, scenic)
- **Venice Beach Los Angeles CA**: 20.0 (coastal but low natural beauty)

---

## Observations from Baseline Data

### High Performers (90+):
- **Pearl District Portland OR** (100.0): Very high GVI (63.04%) despite moderate canopy (5.06%)
- **Georgetown DC** (100.0): Very high GVI (69.99%) with good canopy (16.64%)
- **Carmel-by-the-Sea CA** (91.09): High water (25.1%) + high canopy (25.5%) + moderate topography

### Mid-Range Performers (30-60):
- **Coconut Grove Miami FL** (51.92): High water (25.63%) but moderate canopy (17.37%)
- **Beacon Hill Boston MA** (35.71): Low canopy (7.65%) but good water (16.33%)
- **Manhattan Beach CA** (30.5): Moderate water (11.63%) but low canopy (7.87%)

### Low Performers (<30):
- **Garden District New Orleans LA** (20.07): Very low canopy (2%) despite water (13.3%)
- **Old Town Scottsdale AZ** (13.3): Arid, minimal water (0.4%) and canopy (1.63%)

### Notable Patterns:
1. **GVI Impact**: Pearl District and Georgetown both score 100 despite moderate canopy, suggesting GVI is a major factor
2. **Water + Canopy Combination**: Carmel-by-the-Sea has both high water (25.1%) and high canopy (25.5%), scoring 91.09
3. **Low Canopy Penalty**: Garden District (2% canopy) scores only 20.07 despite having water (13.3%)
4. **Arid Regions**: Old Town Scottsdale (13.3) and Sedona (61.16) show that topography can compensate for low water/canopy in arid regions

---

## Regression Test Usage

### Run All Tests:
```bash
python3 tests/test_natural_beauty_regression.py
```

### Test Specific Location:
```bash
python3 tests/test_natural_beauty_regression.py --location "Coconut Grove"
```

### Update Baseline (After Intentional Changes):
```bash
python3 tests/test_natural_beauty_regression.py --update-baseline --save
```

---

## Next Steps

1. ✅ Baseline scores captured and updated
2. ⏳ Run regression tests before making calibration changes
3. ⏳ Monitor for regressions after each change
4. ⏳ Update baseline scores when intentional improvements are validated

---

## Files Modified

- `tests/test_natural_beauty_regression.py`: Updated baseline scores for 9 locations with actual production data

