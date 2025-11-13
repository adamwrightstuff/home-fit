## Built Beauty Ideals by Area Type

This reference describes what “beautiful” should mean for each `area_type` and subtype in the built beauty pillar. Values reference existing metrics exposed through `data_sources/arch_diversity.py` and downstream scoring logic.

### Urban Core
- Cohesive skyline with purposeful variation: `height_diversity` high (20–35) but anchored by consistent streetwalls.
- High `type_diversity` (15–30) reflecting mixed-use towers, civic icons, and premium commercial design.
- `footprint_area_cv` moderate (60–85) signalling articulated podiums without chaotic massing.
- `built_coverage_ratio` 0.4–0.65; blank lots or over-built superblocks should both penalize.
- Phase 2/3 metrics — `streetwall_continuity`, `setback_consistency`, `facade_rhythm` — should sit 60+; large canyons or disruptive plazas subtract.
- Materials showcase glass/steel/stone; modern form quality matters more than age. `age_percentile` is secondary unless paired with heritage nodes.

### Urban Core Lowrise
- Similar density expectations but cap `height_diversity` near 25 to reward consistent 3–6 story fabric.
- `type_diversity` 12–25: stacked flats, loft conversions, civic anchors.
- `footprint_area_cv` 70–95 capturing fine-grained parcels.
- `built_coverage_ratio` 0.35–0.55 with minimal voids.
- Phase 2/3 metrics should exceed 65; rhythm/stoop cadence is central.
- Materials: mixed masonry, modern infill; heritage boosts apply only when landmark clusters exist.

### Historic Urban
- Strong coherence: `height_diversity` moderate (10–20); excessive tower intrusion should penalize.
- `type_diversity` 10–20 balancing rowhouses, carriage houses, historic apartments.
- `footprint_area_cv` 80–110 capturing narrow lots and alley structures.
- `built_coverage_ratio` 0.45–0.6.
- Phase 2/3 metrics expected 70–85; lapses imply erosion of the historic fabric.
- `median_year_built` < 1950 and `heritage_significance` + `landmark_count` > 50 trigger top bonuses. Material entropy should not punish single-material excellence (e.g., brick brownstones).

### Urban Residential
- Emphasis on rowhouse or courtyard consistency: target `height_diversity` 5–15, `type_diversity` 6–15.
- `footprint_area_cv` 80–120; extremely high variance may indicate teardown churn.
- `built_coverage_ratio` 0.35–0.55.
- Phase 2/3 metrics must anchor the score: `streetwall_continuity` 65+, `setback_consistency` 70+, `facade_rhythm` 65+. These compensate for low skyline variety.
- `enhancer_bonus` should trigger on coherent materials, preserved stoops, or documented design review districts even with few OSM landmarks.
- `median_year_built` < 1940 or percentile > 75 with high coherence should grant heritage credit.

### Suburban
- Quality comes from master-planned coherence and landscaping.
- `height_diversity` 8–18 (mix of 1–3 story structures).
- `type_diversity` 6–18; too high often signals sprawl strip mix, too low indicates monotony.
- `footprint_area_cv` 45–70 capturing varied lot sizes with cul-de-sacs.
- `built_coverage_ratio` 0.2–0.35; big parking fields penalize via low coverage or facade continuity.
- Phase 2/3 expectations: `streetwall_continuity` 40–60 (expect gaps), but `setback_consistency` should still reach 60+ in premium subdivisions.
- Materials should reflect premium finishes (stone, stucco, composite). Heritage is rarer; modern form bonuses should trigger for well-executed contemporary town centers.

### Exurban
- Scenic integration outweighs diversity; coherence is key.
- `height_diversity` 5–12, `type_diversity` 4–10. High diversity without coverage should penalize.
- `footprint_area_cv` 35–60; large custom lots should not automatically inflate beauty.
- `built_coverage_ratio` 0.05–0.2 with penalties for <0.08 unless tied to historic hamlets.
- Phase 2/3 metrics often sparse; fallback should favor coherence heuristics (roofline alignment, clustered village cores) over random variety.
- `enhancer_bonus` only when authentic heritage or curated resort elements exist; avoid synthetic boosts.

### Rural
- Beauty defined by intact village centers or historic main streets rather than scattered development.
- `height_diversity` 4–10; values >15 usually indicate sprawl.
- `type_diversity` 3–8; cohesive vernacular is preferable.
- `footprint_area_cv` 30–55 for small-town grids; outliers indicate big-box intrusion.
- `built_coverage_ratio` 0.05–0.15; penalize when <0.04 (isolated farmsteads) or >0.2 (auto-oriented strips).
- Phase 2/3 metrics seldom available; scoring should rely on fallback coherence plus actual landmark/heritage signals.
- Material expectations: wood siding, brick storefronts; require corroborating tags to award bonuses.

## Metric Coverage and Gaps

| Area Type | Signals Already Strong | Signals Underweighted | Data Reliability Risks | Candidate Adjustments |
|-----------|-----------------------|------------------------|------------------------|-----------------------|
| Urban Core | Skyline variety, mixed-use diversity (`height_diversity`, `type_diversity`), phase 2/3 cadence when coverage is high | Modern form bonus limited to select heuristics | Landmark tagging over-upgrades to `historic_urban`; material tags sparse for glass/steel | Add explicit modern urban form boost tied to FAR + facade rhythm; tighten historic upgrade guardrails |
| Urban Core Lowrise | Facade rhythm, setbacks, heritage scoring when landmarks present | Podium coherence vs. main street consistency split | Material entropy conflates brick dominance with monotony; block grain noisy in low coverage | Introduce lowrise skyline guardrail to penalize intrusive towers; fallback for missing materials based on rhythm + age |
| Historic Urban | Heritage / median year percentile, phase 2/3 cadence (after confidence gate) | Rowhouse material recognition, stoop/porch signals | OSM landmarks missing for many districts; material share undercounts brick | Add brownstone heuristic (coherence + age) to stand in for missing landmarks; prefer coherence over diversity in normalization |
| Urban Residential | Setback + facade rhythm improved with gate; coverage expectations good | Type/height diversity penalties still too strong; enhancer bonus rarely triggers | Material share low due to tagging; landmark counts small | Reweight diversity penalties downward when phase 2/3 scores are 65+; create design review bonus using municipal overlays if available |
| Suburban | Coverage + streetwall detect strip malls; modern form bonus handles town centers | Coherence in planned communities not surfaced; streetscape quality relies on sparse phase 2/3 | Block grain often missing; material tags limited to “roof:shingle” | Add cul-de-sac coherence heuristic (consistent setbacks + low diversity) as positive; penalize big-box parcels via footprint kurtosis |
| Exurban | Current phase 2/3 fallback avoids zeros; can detect hamlet block grain | High diversity falsely inflates scores; low coverage not punished enough | OSM building data incomplete; landmarks rare, leading to flat enhancer | Introduce negative “sprawl dispersion” bonus when coverage <0.08 and diversity high; require real heritage evidence before enhancer |
| Rural | Heritage logic works when courthouse/main street tagged | Scenic fallback absent; type diversity still inflates | Building footprints missing; phase 2/3 absent | Add rural village heuristic (coverage 0.08–0.15 + consistent setbacks) for positive signal; down-rank when big-box footprints detected |

### Cross-Cutting Observations
- **Phase 2/3 confidence gate** prevents zeroing but we still need alternate positives when coverage is sparse (suburban, rural). Consider a separate “coherence proxy” using variance ratios.
- **Material entropy** remains unreliable; use a guarded multiplier informed by rhythm + age rather than raw tag counts.
- **Enhancer bonuses** must rely on verifiable data: landmarks, documented design districts, or validated municipal overlays. Avoid population/density fallbacks.
- **Coverage ratio** should be context-sensitive: exurban/rural require minimum thresholds to validate “village” status; urban types should penalize both under-coverage (parking lots) and over-coverage (superblocks).

## Tuning & Validation Sequence

1. **Urban Residential Focus**
   - Objectives: finalize rowhouse/brownstone heuristics, rebalance diversity penalties vs. phase 2/3 coherence.
   - Representative Tests: Park Slope (NY), Society Hill (PA), Fells Point (MD), Georgetown (DC), Silver Lake (CA).
   - Success Criteria: Scores align with qualitative expectations (mid/high 80s for cohesive districts, 60s–70s for mixed-quality corridors); no artificial boosts relying on density alone.

2. **Historic Urban Refinement**
   - Objectives: tighten landmark + age requirements to prevent modern cores from upgrading; ensure heritage boosts require both age percentile and landmark density.
   - Representative Tests: South End (MA), Capitol Hill (DC), French Quarter (LA), Charlestown (MA), Old San Juan (PR).
   - Success Criteria: Modern districts like Brickell remain `urban_core`; authentic historic districts reach high 90s only with strong landmark evidence.

3. **Urban Core / Urban Core Lowrise**
   - Objectives: calibrate modern form bonus, introduce skyline guardrails for lowrise cores, prevent over-scoring superblocks.
   - Representative Tests: Brickell (FL), Downtown Seattle (WA), Pearl District (OR), Pearl Brewery (TX), Downtown Vancouver (WA).
   - Success Criteria: Contemporary high-design areas score 80–90 without heritage; lowrise cores maintain 85–95 when cohesive; penalties trigger for blank superblocks.

4. **Suburban Pass**
   - Objectives: detect master-planned coherence, penalize strip-mall sprawl, validate modern town centers.
   - Representative Tests: The Woodlands (TX), Reston (VA), Irvine Villages (CA), Plano Legacy (TX), Highland Park (IL).
   - Success Criteria: Planned communities settle in 70–85 with bonuses for design review districts; strip-commercial corridors fall to 40–60.

5. **Exurban Calibration**
   - Objectives: add sprawl dispersion penalty, ensure low coverage without heritage drops scores, validate hamlet positives.
   - Representative Tests: Plainview (TX), Bend Outskirts (OR), Sonoma hamlets (CA), Hudson NY periphery, Bozeman outskirts (MT).
   - Success Criteria: Plainview-like cases fall into 50–65 unless real heritage present; curated resort villages can reach 75–80 with evidence.

6. **Rural Refinement**
   - Objectives: implement village-center heuristic, guard against big-box intrusion, rely on actual heritage data.
   - Representative Tests: Woodstock (VT), Stowe (VT), Marfa (TX), Livingston (MT), rural non-scenic example (e.g., Dumas TX).
   - Success Criteria: Picturesque towns reach 70–80; non-scenic rural strips stay <50; bonuses only fire with verifiable landmarks.

7. **Cross-Type Regression Sweep**
   - Objectives: run broad regression set across all pillars to catch unintended shifts; verify telemetry coverage.
   - Representative Tests: Prior list + Bronxville (NY), Venice Beach (CA), Wynwood (FL), suburban DC communities, sample rural Midwest towns.
   - Success Criteria: No area type drifts outside target bands; telemetry coverage/phase 2 confidence remains stable.

