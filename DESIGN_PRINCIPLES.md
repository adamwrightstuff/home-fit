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
6. ✅ **Have I tested regressions?** (20+ locations)
7. ✅ **Does this follow pillar-specific principles?** (check pillar docs)

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

## Version History

- **v1.0** (2024): Initial principles based on audit findings
- Principles should be reviewed quarterly and updated as system evolves

