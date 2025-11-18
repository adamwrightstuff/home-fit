# Beauty Pillar Design Principles

This document outlines shared design principles for the `built_beauty` and `natural_beauty` pillars to ensure consistency, maintainability, and scalability.

## Core Principles

### 1. Additive Bonus Structure
**Principle:** Use additive bonuses, not multiplicative multipliers.

**Rationale:**
- More predictable and debuggable
- Easier to tune individual components
- Prevents compounding effects that lead to extreme values
- Consistent with built beauty's approach

**Implementation:**
```python
# ✅ Good: Additive
final_score = base_score + bonus_1 + bonus_2 + bonus_3

# ❌ Bad: Multiplicative
final_score = base_score * multiplier_1 * multiplier_2 * multiplier_3
```

**Exception:** Climate adjustments to expectations (base values) are acceptable, as they adjust the reference point, not the scoring formula.

---

### 2. Independent Component Caps
**Principle:** Each component should have an independent maximum cap.

**Rationale:**
- Prevents any single component from dominating
- Makes tuning more predictable
- Easier to understand score breakdowns

**Implementation:**
```python
# Each component capped independently
water_bonus = min(WATER_BONUS_MAX, base_water_score + coastal_bonus + ...)
topography_bonus = min(TOPOGRAPHY_BONUS_MAX, ...)
landcover_bonus = min(LANDCOVER_BONUS_MAX, ...)

# Total context bonus also capped
context_bonus = min(NATURAL_CONTEXT_BONUS_CAP, water_bonus + topography_bonus + landcover_bonus)
```

---

### 3. Climate Context Awareness
**Principle:** Adjust expectations based on climate, not scores.

**Rationale:**
- Natural beauty is inherently climate-dependent (vegetation, water availability)
- Fairness: places should be evaluated relative to what's achievable in their climate
- Scalability: works globally without hardcoded metro lists

**Implementation:**
```python
# ✅ Good: Adjust expectations
expected_canopy = base_expectation * climate_multiplier
score = f(observed_canopy / expected_canopy)

# ❌ Bad: Adjust scores directly
score = base_score * climate_multiplier
```

**Note:** Built beauty may not need climate adjustments (architecture is more universal), but the principle applies where relevant.

---

### 4. Identity Normalization
**Principle:** Use identity normalization (shift=0, scale=1, max=100) by default.

**Rationale:**
- No artificial inflation/deflation
- Raw scores reflect actual metric performance
- Easier to debug and understand

**Implementation:**
```python
# Current: All area types use identity
AREA_NORMALIZATION = {
    "urban_core": {"shift": 0.0, "scale": 1.0, "max": 100.0},
    "suburban": {"shift": 0.0, "scale": 1.0, "max": 100.0},
    # ... all identity
}
```

**Exception:** If area-type specific adjustments are needed, they should be in the raw scoring logic, not normalization.

---

### 5. Objective, Data-Driven Scoring
**Principle:** All scoring must be based on objective metrics, not subjective judgments.

**Rationale:**
- Reproducible and verifiable
- Scalable across all locations
- No location-specific tuning

**Implementation:**
```python
# ✅ Good: Objective metric
water_bonus = f(water_pct, water_expectation, elevation, developed_pct)

# ❌ Bad: Subjective override
if location == "Coconut Grove":
    water_bonus = 10.0  # Hardcoded
```

---

### 6. Graceful Degradation
**Principle:** Missing or poor-quality data should not break scoring.

**Rationale:**
- Robust to data availability issues
- Better user experience
- Prevents cascading failures

**Implementation:**
```python
# Always have fallbacks
water_type = landcover_metrics.get("water_type")
if water_type is None:
    # Fallback: use generic water bonus (no penalty)
    water_type_bonus = 0.0
else:
    water_type_bonus = get_type_specific_bonus(water_type)
```

---

### 7. Transparent Metadata
**Principle:** Expose detailed breakdowns in API responses.

**Rationale:**
- Enables debugging and validation
- Builds trust through transparency
- Helps identify data quality issues

**Implementation:**
```python
details = {
    "base_score": ...,
    "bonus_breakdown": {
        "coastal_bonus": ...,
        "rarity_bonus": ...,
        "visibility_bonus": ...
    },
    "component_scores": {...},
    "data_quality": {...}
}
```

---

## Bonus Magnitude Guidelines

### Built Beauty
- **Component score:** 0-50 (native range)
- **Enhancer bonus:** 0-8.0 (BUILT_ENHANCER_CAP)
- **Total raw:** 0-100 (component * 2.0 + enhancer)

### Natural Beauty
- **Component score:** 0-50 (native range)
- **Enhancer bonus:** 0-18.0 (NATURAL_ENHANCER_CAP)
- **Total raw:** 0-100 (component * 2.0 + enhancer)

**Note:** Natural beauty has higher enhancer cap (18.0 vs 8.0) because natural features (water, topography, scenic views) can contribute more to beauty than built features (artwork, fountains).

---

## Component Balance Guidelines

### Prevent Dominance
- No single component should exceed 60% of total context bonus
- If dominance detected, apply 0.9x scaling factor
- Document when dominance occurs for analysis

### Climate-Adjusted Expectations
- Arid regions: Lower canopy/water expectations, higher topography weight
- Tropical regions: Higher canopy/water expectations, standard topography
- Temperate regions: Baseline expectations

---

## Validation Requirements

Before deploying any calibration changes:

1. ✅ Run regression test suite (20+ locations)
2. ✅ Verify no regressions >10 points without documented reason
3. ✅ Check component balance (no single component >60% of total)
4. ✅ Validate data quality (coverage >80% for new data sources)
5. ✅ Document changes with clear rationale
6. ✅ Test edge cases (very high/low scores)

---

## Change Approval Process

1. **Proposal:** Document proposed change with rationale
2. **Risk Assessment:** Identify potential regressions and edge cases
3. **Implementation:** Add feature flag, implement change
4. **Testing:** Run regression suite, validate edge cases
5. **Review:** Check against design principles
6. **Deployment:** Enable feature flag, monitor for issues
7. **Rollback Plan:** Document how to revert if issues arise

---

## Anti-Patterns to Avoid

❌ **Hardcoded location adjustments**
```python
if city == "Scottsdale":
    score += 5.0  # Don't do this
```

❌ **Multiplicative multiplier stacking**
```python
score = base * mult1 * mult2 * mult3  # Unpredictable
```

❌ **Artificial normalization shifts**
```python
normalized = score * 0.8 + 10.0  # Hides real performance
```

❌ **Location-specific tuning**
```python
if location in SPECIAL_LOCATIONS:
    apply_special_logic()  # Not scalable
```

---

## Questions to Ask Before Making Changes

1. Does this follow the additive bonus principle?
2. Is this based on objective metrics?
3. Will this work for all locations (not just specific ones)?
4. Does this have a rollback plan?
5. Is this documented with clear rationale?
6. Have regression tests been run?
7. Does this maintain consistency with built beauty?

