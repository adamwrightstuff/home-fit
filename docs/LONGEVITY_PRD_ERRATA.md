# HomeFit Longevity PRD — Errata and Feasibility Corrections

This document records corrections to the Longevity PRD (homefit-longevity-prd) for accuracy and feasibility. Apply these when revising the PRD or implementing.

---

## 1. FEMA and GEE

**PRD claim:** "HomeFit already uses GEE and ingests FEMA data."

**Correction:** HomeFit **does** use GEE (tree canopy, topography, landcover in `data_sources/gee_api.py`). HomeFit **does not** currently ingest or use FEMA NFHL data. There is no FEMA-related code in the repository.

**Action:** In the PRD:
- Remove or replace the sentence that says HomeFit ingests FEMA data.
- State that **FEMA NFHL is a new data source** for the Climate & Flood Risk pillar.
- Phase 1A should be described as **"Climate & Flood Risk (GEE only: LST + TROPOMI)"** so it is shippable without FEMA. Add a follow-on phase (e.g. 1A' or 2D) for FEMA NFHL integration once spatial lookup strategy is decided.

---

## 2. PostGIS and spatial data

**PRD assumption:** Load IRS EO BMF and FEMA NFHL into PostGIS; spatial join on score request.

**Correction:** HomeFit has **no spatial database** today. The stack is FastAPI + Redis cache + in-memory/API data (Census, OSM, GEE). There is no PostGIS or other spatial DB in the codebase.

**Action:** In the PRD:
- Specify the **integration approach** for spatial data:
  - **Option A:** Introduce PostGIS (or equivalent) for IRS BMF and FEMA NFHL, with notes on deployment, updates, and query pattern; or
  - **Option B:** Use tract-boundary or radius-based lookup from preprocessed files (no PostGIS), describing format and update cadence.
- In the data dependency table (e.g. §6.1), add a row or note that **PostGIS (or alternative)** is a **new** dependency if Option A is chosen.

---

## 3. Census variables B07003 and B02001

**PRD claim:** "Census ACS B07003: Mobility table — already in HomeFit's Census pipeline, just not yet queried."

**Correction:** The **Census API pipeline** exists (`data_sources/census_api.py`, `economic_security_data.py`, subject/detailed tables). The specific variables **B07003** (mobility / same house 1 year ago) and **B02001** (race) are **not** currently requested or parsed anywhere. They are new variables to add, not “already queried.”

**Action:** In the PRD, replace “already in pipeline, just not yet queried” with: **“Census pipeline exists; add B07003 (mobility) and B02001 (race) variables and parsing.”** Effort remains small (add variable IDs and parsing).

---

## 4. Data dependency table (§6.1)

**Action:** In the “New Data Dependencies Summary” table:
- Mark **FEMA NFHL** as **New** (not “already in HomeFit”).
- If Option A (PostGIS) is chosen, add **PostGIS (or equivalent)** as a **new** dependency with format, update cadence, and integration notes.

---

## 5. Phasing (§6.5)

**Recommended adjustments:**
- **Phase 1A:** Label explicitly as **"Climate & Flood Risk (GEE only: LST + TROPOMI)"** so it is clear that FEMA is out of scope for 1A.
- Add **Phase 1A'** or **2D:** “FEMA NFHL integration” after the spatial lookup strategy is decided.
- Optionally, in Phase 2B (Social Fabric), split **IRS BMF** into a sub-phase **2B'** so that Social Fabric can ship first with Census + OSM only (residential stability, third places, diversity), and add IRS BMF once ingest and lookup are in place.

---

## 6. Backend / API (§6.2, §6.3)

**Recommendations:**
- Clarify that new ScoreBundle keys (e.g. `residential_stability`, `flood_zone_score`) are **optional** until each pillar is live, so existing clients do not break.
- Add a sentence that the **Longevity Index** is computed only when all required pillars are present (or define a minimum set), to avoid half-computed or misleading composite scores.

---

*Document version: 1.0 — February 2026*
