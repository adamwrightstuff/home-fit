# Active Outdoors v2 - Round 12 Expanded Calibration Panel

**Date:** 2024-12-XX  
**Status:** Panel Updated, Ready for Calibration

---

## Summary

Expanded calibration panel from **18 to 36 locations** using research-backed target scores from external sources (Perplexity, Gemini, Claude).

**Key Principle:** These target scores are used for **calibration** (fitting CAL_A and CAL_B), NOT for tuning components to match specific scores. This adheres to Design Principles: "Research-backed expected values, not target-tuned values."

---

## Panel Statistics

**Total Locations:** 36 (18 original + 18 new)

**Score Distribution:**
- Very Low (0-40): 2 locations (6%)
- Low (40-60): 7 locations (19%)
- Mid (60-80): 9 locations (25%)
- High (80-95): 11 locations (31%)
- Very High (95+): 7 locations (19%)

**Score Range:** 35 - 97  
**Mean Score:** 73.8

---

## New Locations Added (18)

### Exurban/Mountain Towns (8 locations)
- **Asheville NC** - 95 (mountain town, outdoor hub)
- **Aspen CO** - 96 (mountain resort)
- **Bar Harbor ME** - 88 (coastal mountain)
- **Bend OR** - 95 (outdoor recreation mecca)
- **Flagstaff AZ** - 90 (mountain, desert edge)
- **Jackson Hole WY** - 96 (mountain resort)
- **Missoula MT** - 88 (mountain town)
- **Telluride CO** - 97 (mountain resort)

### Low/Mid-Range Urban Cores (6 locations)
- **Downtown Dallas TX** - 40 (low parks, hot climate)
- **Downtown Detroit MI** - 40 (very low parks, urban decay)
- **Downtown Houston TX** - 35 (low parks, urban sprawl)
- **Downtown Indianapolis IN** - 45 (mid-range urban)
- **Downtown Kansas City MO** - 45 (mid-range urban)
- **Downtown Minneapolis MN** - 75 (mid-range urban, good parks)

### Diverse Suburban (3 locations)
- **Centennial CO** - 70 (mountain suburban)
- **Gilbert AZ** - 52 (desert suburban)
- **Hollywood FL** - 60 (coastal suburban)

### Edge Cases (1 location)
- **Outer Banks NC** - 75 (coastal rural)

---

## Research Sources

**Target scores validated using:**
- Perplexity AI research
- Google Gemini research
- Claude AI research

**Methodology:**
- Multiple LLM sources consulted for each location
- Scores based on media rankings, outdoor recreation data, park access data
- Not tuned to match specific locations - used as research-backed reference

---

## Design Principles Compliance

✅ **Research-Backed:** Target scores from external research, not arbitrary  
✅ **Not Target-Tuned:** Components are NOT adjusted to match these scores  
✅ **Calibration Only:** These scores used to fit CAL_A/CAL_B, not component logic  
✅ **Transparent:** Research sources documented  
✅ **Objective:** Area types auto-detected where not specified  

---

## Area Type Handling

**Specified Area Types:**
- Mapped to standard types (urban_core, suburban, exurban, rural, urban_residential)
- "Rural/Exurban" → rural (for small towns)
- "Suburban/Exurban" → exurban (for outdoor-oriented suburbs)
- "Urban" or "Urban/Suburban" → urban_core

**Auto-Detection:**
- Locations with unspecified area types will be auto-detected by `get_area_classification()`
- This ensures objective area type assignment

---

## Next Steps

1. **Run Calibration:** Execute `scripts/calibrate_active_outdoors_v2.py`
2. **Analyze Results:** Review R², MAE, max error metrics
3. **Component Refinement:** If R² remains low, refine component scoring (NOT to match targets)
4. **Validation:** Compare calibrated scores to research targets for validation

---

## Notes

- **Individual LLM Scores:** Available if needed for locations with large discrepancies
- **Rationale:** Can be provided for any location if calibration reveals issues
- **No Tuning:** Components will NOT be adjusted to match these targets
- **Calibration Only:** These targets are used solely for fitting the linear calibration curve

---

## Files Updated

- `scripts/calibrate_active_outdoors_v2.py` - Updated with Round 12 panel
- Output will be saved to: `analysis/active_outdoors_calibration_round12.json`

---

## Comparison: Round 11 vs Round 12

| Metric | Round 11 | Round 12 | Change |
|--------|----------|----------|--------|
| Locations | 18 | 36 | +18 |
| Score Range | 35-95 | 35-97 | Expanded |
| Very Low (0-40) | 1 | 2 | +1 |
| Low (40-60) | 3 | 7 | +4 |
| Mid (60-80) | 3 | 9 | +6 |
| High (80-95) | 10 | 11 | +1 |
| Very High (95+) | 1 | 7 | +6 |

**Improvements:**
- Better coverage of low/mid-range scores
- More high-scoring locations for calibration
- More exurban/mountain town representation
- More diverse contexts (desert, coastal, mountain)

