# Climate-Based Canopy Expectation Analysis

## Objective

Determine data-driven canopy expectations by climate zone to implement a **climate-first, area-type-second** architecture for natural beauty scoring.

## Current Problem

The system currently:
1. Gets base expectation from area type (e.g., suburban = 32%)
2. Applies climate as a multiplier (e.g., 1.0x for coastal CA)
3. Result: Climate doesn't meaningfully adjust expectations

**Example:** Manhattan Beach (coastal SoCal, Mediterranean climate)
- Current: 32% expectation (suburban base × 1.0 climate)
- Actual: 3.4% canopy
- Result: Massive penalty (-6.0 points) for being 89% below expectation

## Proposed Solution

**Climate-first architecture:**
1. Climate determines base expectation (e.g., Mediterranean = 18-22% base)
2. Area type adjusts within climate (e.g., suburban = +4%, urban_core = -4%)
3. Result: Realistic expectations that scale globally

## Data Collection

**Script:** `scripts/analyze_canopy_by_climate.py`

**Process:**
- Samples 50 diverse US locations across climate zones
- Queries GEE/NLCD for actual canopy percentages
- Classifies each location by climate zone
- Aggregates statistics (mean, median, percentiles) by climate zone

**Output:**
- `analysis/canopy_by_climate.csv` - Raw data for all locations
- `analysis/canopy_by_climate_summary.txt` - Statistics by climate zone

## Research Component (Perplexity)

**Query:** "What are typical urban tree canopy percentages by Köppen-Geiger climate classification?"

**Focus:**
- Arid/Desert (BWh, BWk, BSh, BSk)
- Mediterranean (Csa, Csb)
- Temperate (Cfa, Cfb, Cwa, Cwb)
- Tropical (Af, Am, Aw)
- Continental (Dfa, Dfb, Dwa, Dwb)

**Extract:**
- Urban vs. suburban canopy percentages
- Source citations
- Regional standards or targets

## Next Steps

1. ✅ Run data collection script (in progress)
2. ⏳ Review research findings from Perplexity
3. ⏳ Analyze data to determine climate base expectations
4. ⏳ Design area-type adjustments within climate zones
5. ⏳ Implement climate-first architecture
6. ⏳ Validate against test locations

## Expected Outcomes

- Climate base expectations derived from actual data
- Area-type adjustments that work within any climate
- Scalable system that works globally
- No location-specific tuning required

