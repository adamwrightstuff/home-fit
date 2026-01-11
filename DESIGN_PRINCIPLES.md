# HomeFit Design Principles

**Purpose:** Core principles that guide all scoring logic and system design decisions.

---

## Core Principles

### 1. Research-Backed, Not Artificially Tuned
✅ **DO:**
- Use research data (medians, percentiles) from empirical collection
- Calibrate curves based on real-world data analysis
- Document data sources and methodology

❌ **DON'T:**
- Tune parameters to match target scores for specific locations
- Add hardcoded exceptions for individual cities/neighborhoods
- Adjust expected values to hit desired scores

**Example:**
```python
# ✅ Good: Research-backed
expected_bus_routes = 8  # Median from 16 commuter rail suburbs

# ❌ Bad: Artificially tuned
expected_bus_routes = 34  # Calibrated to make Uptown Charlotte score 55
```

---

### 2. Objective and Data-Driven
✅ **DO:**
- Base scoring on objective metrics (counts, distances, areas, ratios)
- Use reproducible functions that work for all locations
- Document the rationale for all scoring decisions

❌ **DON'T:**
- Use subjective judgments or location-specific overrides
- Hardcode city names in scoring logic
- Create special-case paths for calibration locations

**Example:**
```python
# ✅ Good: Objective metric
score = f(parks_count / expected_parks)

# ❌ Bad: Subjective override
if city == "Boulder":
    score += 5.0  # Don't do this
```

---

### 3. Scalable and General
✅ **DO:**
- Solutions that work for all locations, not just test cases
- Use area type classification, not city name matching
- Improve classification logic rather than adding exceptions

❌ **DON'T:**
- Create special-case paths for individual locations
- Use hardcoded location-to-area-type mappings
- Bypass classification with override dictionaries

**Example:**
```python
# ✅ Good: Scalable classification
area_type = classify_morphology(density, coverage, business_count)

# ❌ Bad: Hardcoded overrides
TARGET_AREA_TYPES = {"bronxville ny": "suburban", ...}
```

---

### 4. Transparent and Documented
✅ **DO:**
- Document rationale for all decisions
- Expose detailed breakdowns in API responses
- Include TODO comments for future research needs

❌ **DON'T:**
- Hide tuning logic in comments
- Use vague or misleading comments
- Leave undocumented assumptions

**Example:**
```python
# ✅ Good: Clear documentation
# Research data not yet available. Conservative estimate based on area type description.
# TODO: Run research script for urban_residential locations
expected_bus_routes = 15

# ❌ Bad: Vague or misleading
# Calibrated to match target scores
expected_bus_routes = 34
```

---

### 5. Smooth and Predictable
✅ **DO:**
- Use smooth mathematical functions (exponential decay, sigmoid curves)
- Ensure predictable behavior across the full score range
- Document breakpoints and their rationale

❌ **DON'T:**
- Use artificial post-normalization shifts (`score * 0.8 + 10`)
- Add caps without clear justification
- Create discontinuous jumps in scoring

**Example:**
```python
# ✅ Good: Smooth function
score = 40.0 + (ratio - 1.0) * 15.0  # Linear interpolation

# ❌ Bad: Artificial shift
score = base_score * 0.8 + 10.0  # Hides real performance
```

---

### 6. Context-Aware Expectations
✅ **DO:**
- Use area type to set appropriate expectations
- Base expected values on research data (medians/percentiles)
- Adjust expectations for climate/regional context where relevant

❌ **DON'T:**
- Use arbitrary expected values
- Tune expectations to match target scores
- Ignore area type context

**Example:**
```python
# ✅ Good: Research-backed expectations
expected_parks = research_medians.get(area_type, {}).get("parks_1km", 5)

# ❌ Bad: Arbitrary values
expected_parks = 8  # No source, no rationale
```

---

## Decision Checklist

Before making **ANY** scoring change, ask:

1. ✅ **Is this research-backed?** (data, not target scores)
2. ✅ **Is this objective?** (metrics, not judgments)
3. ✅ **Is this scalable?** (works for all locations)
4. ✅ **Is this transparent?** (documented rationale)
5. ✅ **Does this avoid artificial tuning?** (no location-specific exceptions)
6. ✅ **Have I validated against human perception?** (rank-order correlation ≥ 0.7 with 15+ locations)
7. ✅ **Have I run regression tests?** (prevent breaking changes, but NOT primary validation)
8. ✅ **Does this follow pillar-specific principles?** (check pillar docs)

### Validation Priority Order

**PRIMARY (Required before any change):**
- **Rank-order correlation with human ratings** (Spearman ≥ 0.7)
  - Validates that scores align with human perception
  - Most data-backed validation approach
  - Run: `python scripts/validate_natural_beauty_scoring.py`

**SECONDARY (Verify research data used):**
- Research-backed expected values
  - Check that expected values come from research, not arbitrary tuning
  - Verify climate adjustments are based on empirical data

**DEFENSIVE (Prevent breaking changes):**
- Regression tests (20+ locations)
  - Prevents unintended changes
  - Assumes baseline is correct (may lock in wrong behavior if baseline is wrong)
  - Should complement, not replace, correctness validation
  - Run: `python tests/test_natural_beauty_regression.py`

**Note:** Regression testing ensures stability but doesn't validate correctness. The most data-backed approach is rank-order correlation with human ratings, which tests if scores align with how people actually perceive natural beauty.

---

## Anti-Patterns (NEVER DO)

❌ **Hardcoded city exceptions**
```python
if city == "X": score += 5
```

❌ **Tuning to target scores**
```python
# Calibrated to make Location Y score 85
expected_value = 34
```

❌ **Artificial caps without justification**
```python
score = min(score, 80)  # Why 80? No rationale
```

❌ **Location-specific logic**
```python
if location in SPECIAL_LIST: apply_special_logic()
```

❌ **Multiplicative stacking**
```python
score = base * mult1 * mult2 * mult3  # Unpredictable
```

❌ **Post-normalization shifts**
```python
normalized = score * 0.8 + 10.0  # Hides real performance
```

---

## Pillar-Specific Principles

### Active Outdoors
- See: `analysis/ACTIVE_OUTDOORS_DESIGN_PRINCIPLES.md`

### Beauty Pillars (Built & Natural)
- See: `pillars/beauty_design_principles.md`

### Public Transit Access
- Best single mode score + small multimodal bonus
- Research-backed expected route counts per area type
- Smooth ratio-based scoring curve (calibrated from data)
- No artificial fallback scales

---

## When Principles Conflict

If principles conflict (e.g., "research-backed" vs "scalable" when data is limited):

1. **Prioritize research-backed** - Use conservative estimates with TODO for future research
2. **Document the conflict** - Explain why a principle was relaxed
3. **Plan remediation** - Add TODO to collect research data

**Example:**
```python
# Research data not yet available. Using conservative estimate.
# TODO: Run research script for urban_residential locations
expected_bus_routes = 15  # Conservative, not research-backed
```

---

## Addendum: Approved Method for Deriving Feature Weights

**Connection to Principle #1 (Research-Backed):** HomeFit may use statistical modeling to determine feature weights when the modeling process is objective, data-driven, transparent, reproducible, and applied consistently across area types. This is not considered artificial tuning—it is a research-backed method for calibrating how normalized features contribute to pillar scores.

### What's Allowed

HomeFit can derive feature weights using statistical techniques such as Ridge regression, Lasso, OLS (when appropriate), or similar models **as long as**:

1. Inputs are objective normalized metrics (e.g., Norm Height Div, Norm Facade, etc.).
2. Modeling is performed per area type, not per location.
3. The model's coefficients are used directly as the source of weights.
4. No manual adjustments are made to force scores for specific places.
5. Weights are validated on a holdout set or through cross-validation to ensure generalization.

**When to Use:** Statistical modeling is appropriate when you have sufficient data (e.g., 20+ samples per area type) and multiple correlated features. For simpler cases with clear research data, direct median-based expectations may be sufficient.

### What This Enables

- Context-aware scoring (each area type gets weights that reflect its real patterns).
- Fully data-driven calibration without subjective overrides.
- Scalable logic that works everywhere using the same process.

### What's Still Not Allowed

- Adjusting model outputs by hand.
- Fitting weights to make individual cities or locations "look right."
- Creating special-case logic or exceptions for specific places.
- Using models without validation or documentation.

### Documentation Requirement

Whenever statistical modeling is used, HomeFit must record:

- The dataset used (sample size, area types covered).
- The method (e.g., Ridge α=5, Lasso α=0.1, OLS).
- Rationale (why this method, why these features).
- Resulting weights (coefficients per area type).
- Validation results (holdout error, cross-validation scores).
- Any limitations or TODOs.

**Note:** This method still requires going through the Decision Checklist (Principle #1-7) before implementation.

---

## Version History

- **v1.0** (2024): Initial principles based on audit findings
- Principles should be reviewed quarterly and updated as system evolves

