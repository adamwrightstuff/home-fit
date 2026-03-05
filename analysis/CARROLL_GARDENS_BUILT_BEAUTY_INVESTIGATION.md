# Carroll Gardens Built Beauty: Data and Preference Permutations

**Purpose:** Confirm what data comes back for Carroll Gardens built beauty and how the score is calculated for each preference permutation (historic/contemporary × spread_out/walkable).

**Script:** `scripts/investigate_built_beauty_preferences.py` — run with no args for Carroll Gardens, or `--lat/--lon/--name` or `--location "..."`. Use `--json` for machine-readable output; use `--save path.json` to write that JSON to a file. First run can take 2+ minutes (OSM/Census APIs).

---

## 1. What data comes back (single request)

For any location, the built beauty pipeline returns:

| Field | Source | Meaning |
|-------|--------|--------|
| **area_type** | `detect_area_type(lat, lon, density, business_count, built_coverage, ...)` | Morphology: `urban_core`, `suburban`, `exurban`, `urban_residential`, etc. |
| **form_context** | `get_form_context(area_type, density, levels_entropy, ...)` (multinomial) | Architectural classification: `historic_urban`, `urban_residential`, `urban_core`, `suburban`, `exurban`, etc. |
| **effective_area_type** | Same as `form_context` when passed into built_beauty | Used for (1) character mismatch penalty and (2) normalization. **Does not change** with density preference. |
| **area_type_for_scoring** | Derived from **built_density_preference** only | `spread_out_residential` → `exurban`; `walkable_residential` → `suburban`; `dense_urban_living` → `urban_core`. This is what is passed into `score_architectural_diversity_as_beauty()` as `area_type` for **target bands**. |

So for Carroll Gardens:

- **Detected** `area_type` is typically `urban_residential` or `urban_core` (dense, walkable Brooklyn).
- **form_context / effective_area_type** is from multinomial regression; for a historic, uniform brownstone area it is often `historic_urban` or `urban_residential`. This is **constant** across the three preference permutations.
- **area_type_for_scoring** varies by user choice: exurban (spread out), suburban (walkable), or urban_core (dense).

---

## 2. Carroll Gardens reference data (from research run)

From `analysis/research_data/built_beauty_raw_data.json` (one run; no preference split):

| Metric | Value |
|--------|--------|
| name | Carroll Gardens, Brooklyn NY |
| lat, lon | 40.679, -73.991 |
| expected_area_type | urban_residential |
| actual_area_type (that run) | urban_core |
| density | ~44,082 / km² |
| height_diversity (levels_entropy) | 6.7 |
| type_diversity | 11.7 |
| footprint_variation (footprint_area_cv) | 95.3 |
| built_coverage_ratio | 0.317 |
| block_grain | 51.2 |
| streetwall_continuity | 78.0 |
| setback_consistency | 82.0 |
| facade_rhythm | 78.0 |
| component_score (0–50) | 39.1 |
| final_score (that run) | 87.8 |

So Carroll Gardens is low height/type diversity, high footprint variation, high form metrics — a uniform historic residential fabric.

---

## 3. How the score is calculated (per permutation)

Same location and shared data; only **built_character_preference** and **built_density_preference** change.

### Step 1: Architectural score (0–50)

- **Input:** `area_type_for_scoring` = exurban | suburban | urban_core (from density preference).
- **Logic:** `score_architectural_diversity_as_beauty(..., area_type=area_type_for_scoring, ...)` uses `CONTEXT_TARGETS[area_type_for_scoring]` and historic adjustments. So:
  - **historic + spread_out** → targets = **exurban** (very low height/type diversity and high footprint CV are good).
  - **historic + walkable** and **contemporary + walkable** → targets = **suburban** (same raw arch score for both).

Result: `arch_component` (0–50) can be **higher** for exurban than for suburban for Carroll Gardens (exurban expectations more forgiving for uniform historic areas).

### Step 2: Raw score 0–100

- `built_native = arch_component + enhancer_bonus` (artwork/fountains, small).
- `built_score_raw = min(100, built_native * 2)` (scale 0–50 → 0–100).

### Step 3: Character mismatch penalty

- **effective_area_type** comes from form_context (unchanged by preference).
- If `effective_area_type == "historic_urban"`:
  - User **historic** → no penalty.
  - User **contemporary** → **-8** points.
- If place is not historic_urban and user **historic** → -8.

So for Carroll Gardens (if classified historic_urban):

- **historic + spread_out** → no penalty.
- **historic + walkable** → no penalty.
- **contemporary + walkable** → **-8**.

### Step 4: Normalization

- `normalize_beauty_score(score_before_normalization, effective_area_type)` — currently all types use scale 1.0, shift 0, max 100, so output = min(100, score_before_normalization).

### Step 5: Final score

- Final built beauty score = normalized value (0–100).

---

## 4. Expected order for Carroll Gardens

| Permutation | area_type_for_scoring | effective_area_type | Arch (0–50) | Penalty | Score before norm | Final |
|-------------|------------------------|----------------------|-------------|---------|--------------------|-------|
| historic + spread_out | exurban | e.g. historic_urban | **higher** (exurban targets) | 0 | **highest** | **highest** |
| historic + walkable | suburban | same | lower (suburban targets) | 0 | middle | **middle** |
| contemporary + walkable | suburban | same | same as above | -8 | **lowest** | **lowest** |

So the **expected** order is:

1. **historic + spread_out** (highest)
2. **historic + walkable** (middle)
3. **contemporary + walkable** (lowest)

If you observe **contemporary + walkable** > **historic + walkable**, that contradicted the intended logic. **Fix (2026-03):** The multinomial was sometimes predicting `urban_core` instead of `historic_urban` for dense historic neighborhoods (e.g. Carroll Gardens), so the character penalty was applied to "historic" and not "contemporary". A post-multinomial override in `get_effective_area_type` now forces `historic_urban` when the model predicts urban_core/urban_residential and Census shows strong historic signal (median_year_built &lt; 1940 or pre_1940_pct ≥ 10%). Things to check if the issue reappears:

- Confirm **effective_area_type** in the API response for Carroll Gardens (e.g. in `details.architectural_analysis.classification.effective_area_type`). If it is not `historic_urban`, the -8 penalty would not apply for “contemporary.”
- Confirm you are comparing **built beauty** scores (or total livability with same pillar weights), not a different metric.

---

## 5. How to confirm with the script

```bash
# Full run (2+ min with APIs)
python3 scripts/investigate_built_beauty_preferences.py

# JSON only (e.g. to save or diff)
python3 scripts/investigate_built_beauty_preferences.py --json > carroll_gardens_built_beauty.json

# Save JSON to a file directly
python3 scripts/investigate_built_beauty_preferences.py --save analysis/carroll_gardens_built_beauty.json
```

The script prints for each permutation:

- `area_type_for_scoring` (exurban / suburban / urban_core)
- `effective_area_type` (from form_context)
- `arch_component_0_50`
- `score_before_normalization` (after penalty)
- `character_penalty_applied` (true/false)
- `final_score`

That confirms what data comes back and how each permutation is calculated.
