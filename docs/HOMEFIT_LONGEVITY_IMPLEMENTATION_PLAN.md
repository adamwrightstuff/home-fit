# HomeFit Longevity — Implementation Plan

**Purpose:** Turn the Longevity PRD into an executable roadmap with feasibility corrections and performance considerations.  
**Assumptions:** Existing HomeFit stack (FastAPI, Next.js, Census, OSM, GEE, Redis cache). No PostGIS or FEMA today.

---

## Part A: PRD Corrections (Document First)

Before implementation, update the PRD so the plan and estimates are accurate.

| Correction | PRD currently says | Change to |
|------------|--------------------|-----------|
| FEMA | "HomeFit already … ingests FEMA data" | "FEMA NFHL is a **new** data source. Phase 1A can ship with GEE-only (LST + TROPOMI); FEMA in a follow-on phase." |
| PostGIS | "Load into PostGIS" / "spatial join on score request" | "HomeFit has no spatial DB today. Specify integration approach: (a) introduce PostGIS for IRS BMF + FEMA, or (b) tract/radius lookup from preprocessed files (no PostGIS)." |
| Census B07003 / B02001 | "Already in pipeline, just not yet queried" | "Census pipeline exists; **add** B07003 (mobility) and B02001 (race) variables and parsing." |
| Data dependency table (6.1) | FEMA listed without "New" | Add note: FEMA NFHL = **New**; PostGIS (or alternative) = **New** if chosen. |

**Deliverable:** Revised PRD section 0, 2.6, 6.1, and 6.5 reflecting the above.

---

## Part B: Data & Infra Decisions (Before Phase 1)

1. **Spatial lookup strategy**
   - **Option A — PostGIS:** New service; load IRS BMF + FEMA NFHL; spatial joins.
   - **Option B — No PostGIS:** Precompute tract/polygon IDs or lat/lon grids; point-in-polygon or radius search in app or a small service.
   - **Recommendation:** Start with **Option B** for IRS BMF (tract or radius from geocoded CSV) and FEMA (tract-level or centroid lookup from preprocessed NFHL). Add PostGIS later if scale or more spatial layers justify it.

2. **FEMA scope for Phase 1**
   - Ship **Phase 1A without FEMA** (GEE LST + TROPOMI only). Add FEMA in **Phase 2** or a dedicated "1A'" after spatial strategy is in place.

3. **IRS EO BMF**
   - Bulk CSV → geocode → store by tract or lat/lon bucket; monthly refresh. Filter active, optionally by NTEE at query time.

---

## Part C: Phased Implementation Plan

### Phase 0: Prep
- [ ] Apply Part A PRD corrections and get sign-off.
- [ ] Confirm Part B choices (spatial strategy, FEMA phasing, IRS BMF approach).
- [ ] Add new env/config needs: First Street API key (optional, Phase 4), any FEMA/IRS ingest jobs.
- [ ] Ensure GEE quota/billing can support LST + TROPOMI.

### Phase 1A: Climate & Flood Risk (GEE only) — 1–2 weeks
- [ ] Backend: New pillar `climate_risk`; GEE LST (heat excess); GEE TROPOMI (air quality); return sub-scores; no FEMA/First Street.
- [ ] API: Extend `/score` with `climate_risk` pillar and sub-score keys; mark optional in schema.
- [ ] Caching: Cache GEE LST/TROPOMI by (lat, lon) with TTL similar to existing GEE (e.g. 48h).

### Phase 1B: Score bands + richer pillar copy — 3–5 days
- [ ] Score bands (80–100 Excellent, etc.); pillar long copy; data source badges.

### Phase 2A: Accordion sub-criteria expansion — 1–2 weeks
- [ ] Backend: Every pillar returns structured breakdown.
- [ ] Frontend: Accordion per pillar card with sub-criteria rows.

### Phase 2B: Social Fabric pillar — 2–3 weeks
- [ ] Census B07003, B02001; OSM third places; IRS BMF (or defer to 2B').

### Phase 2C: Purpose Density pillar — 1–2 weeks
- [ ] OSM, IMLS, IPEDS, IRS BMF (volunteer org density).

### Phase 2D (or 1A'): FEMA NFHL integration — 1–2 weeks
- [ ] After spatial strategy: FEMA ingest + flood_zone_score.

### Phase 3A: Radar chart + side-by-side comparison — 1–2 weeks
- [ ] Frontend: Radar SVG; compare 2–3 locations.

### Phase 3B: Longevity Index — 3–5 days
- [ ] Composite of Blue Zone–relevant pillars; return in score response.

### Phase 4 (optional): First Street API — 1 week + budget

---

## Part D: Performance Checklist
- GEE: Reuse one client; parallel LST + TROPOMI; cache by geometry.
- Census: Batch new variables with existing calls.
- OSM: Extend existing Overpass queries; avoid duplicate radius queries.
- API: New keys optional; avoid N+1; async where I/O-bound.
- Frontend: Lazy expansion; no duplicate score fetches for compare.

---

## Part E: Dependencies
```
Phase 0 → Phase 1A (Climate GEE) → Phase 1B (Bands + copy)
Phase 2A (Accordion) ← requires sub-scores from 1A and existing pillars
Phase 2B / 2C can run in parallel after 2A.
Phase 2D (FEMA) in parallel with 2B/2C once spatial strategy is fixed.
Phase 3A / 3B after 2B/2C (and optionally 2D) are live.
```

---

## Part F: Success Criteria
- All new pillars return 0–100 with documented sub-scores.
- PRD corrections reflected in official PRD.
- No regression in existing pillar latency.
- Longevity Index and new pillars visible in UI with bands and accordion.
