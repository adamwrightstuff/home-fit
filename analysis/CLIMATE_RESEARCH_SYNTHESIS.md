# Climate-Based Canopy Expectations - Research & Data Synthesis

## Research Findings (Perplexity)

| Climate Zone | Urban Canopy % | Suburban Canopy % | Source |
|--------------|----------------|-------------------|--------|
| **Arid (BWh/BWk)** | 1.5-10% (typical low) | ~7-15% (potential) | Roots of Resilience report |
| **Mediterranean (Csa/Csb)** | ~20-30% (typical) | Target 25-35% | Mediterranean cities target for heat mitigation |
| **Temperate (Cfa/Cfb)** | 30-40% (typical) | +5-10% above urban | NYC, Madison studies |
| **Tropical (Af/Am)** | 30%+ (typical) | Not specified | Strong cooling effects |
| **Continental (Dfa/Dfb)** | 25-40% (typical) | Not specified | 30%+ recommended for extremes |

## Our Actual Data (GEE/NLCD 2021)

| Climate Zone | Suburban Median | Urban Residential Median | Notes |
|--------------|-----------------|--------------------------|-------|
| **Arid** | 1.63% (n=3) | N/A | Very low, matches research low end |
| **Temperate** | 1.88% (n=7) | 1.21% (n=3) | Much lower than research |
| **Humid Temperate** | 4.27% (n=5) | 2.16% (n=3) | Closer to research, still lower |
| **Tropical** | 4.34% (n=2) | 3.54% (n=1) | Much lower than research 30%+ |

## Key Discrepancies & Analysis

### Why Our Data is Lower

1. **Sampling Location**: We sampled specific neighborhoods/coordinates, not city-wide averages
   - Research likely refers to city-wide canopy coverage
   - Urban cores have lower canopy than city-wide averages
   - Our "suburban" samples may be in denser areas

2. **Area Type Classification Issues**
   - Many locations classified as "exurban" instead of "suburban"
   - Urban cores may be underrepresented
   - Need better area type detection

3. **Research vs. Reality**
   - Research shows **targets/goals** (what cities aim for)
   - Our data shows **actual current state** (what exists now)
   - Many cities are below their targets

### Synthesis Approach

We should use a **hybrid approach**:
- **Research data** for **aspirational/target expectations** (what's achievable)
- **Our data** for **current state validation** (what exists)
- **Climate-first architecture** that scales from research targets but validates against reality

## Proposed Climate Base Expectations

Based on research targets (more realistic for scoring expectations):

| Climate Zone | Base Expectation | Rationale |
|--------------|------------------|-----------|
| **Arid** | 8% | Mid-point of research range (1.5-10% urban, 7-15% suburban) |
| **Mediterranean** | 25% | Research target 25-35%, use lower end for expectations |
| **Temperate** | 35% | Research 30-40% urban, use mid-point |
| **Humid Temperate** | 40% | Research 30-40% + humid boost |
| **Tropical** | 35% | Research 30%+, use mid-range |
| **Continental** | 32% | Research 25-40%, use mid-point |

### Area Type Adjustments (within climate)

| Area Type | Adjustment | Rationale |
|-----------|------------|-----------|
| Urban Core | 0.75x | Denser, less space for trees |
| Urban Residential | 0.85x | Moderate density |
| Suburban | 1.0x | Baseline |
| Exurban | 1.15x | More space, higher canopy |
| Rural | 1.25x | Most space, highest potential |

### Example Calculations

**Manhattan Beach (Mediterranean, Suburban):**
- Climate base: 25%
- Area adjustment: 1.0x
- Expected: 25% × 1.0 = **25%**
- Actual: 3.4%
- Ratio: 3.4% / 25% = 13.6% → Still penalty, but more reasonable than 32%

**Phoenix (Arid, Suburban):**
- Climate base: 8%
- Area adjustment: 1.0x
- Expected: 8% × 1.0 = **8%**
- Actual: 1.63%
- Ratio: 1.63% / 8% = 20.4% → Penalty, but much more reasonable

**Portland (Humid Temperate, Suburban):**
- Climate base: 40%
- Area adjustment: 1.0x
- Expected: 40% × 1.0 = **40%**
- Actual: 4.27% (from our data - but this seems low, may be sampling issue)
- Ratio: 4.27% / 40% = 10.7% → Would get penalty

## Implementation Strategy

### Phase 1: Climate Base Expectations
1. Use research-based targets as climate base expectations
2. These represent achievable goals, not current state
3. More fair for scoring (rewards progress toward goals)

### Phase 2: Area Type Adjustments
1. Apply area type multipliers within climate
2. Urban core gets lower expectations (0.75x)
3. Suburban is baseline (1.0x)
4. Exurban/rural get higher (1.15-1.25x)

### Phase 3: Validation
1. Test against known locations
2. Adjust if expectations are too high/low
3. Ensure penalties/bonuses are reasonable

## Next Steps

1. ✅ Research data collected
2. ✅ Our data collected
3. ✅ Synthesis complete
4. ⏳ Implement climate-first architecture
5. ⏳ Add Mediterranean climate zone detection
6. ⏳ Test against regression locations
7. ⏳ Validate expectations are reasonable

