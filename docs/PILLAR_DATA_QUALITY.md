# Pillar Data-Quality Register

Known data-quality issues, coverage gaps, and saturation per pillar — from the 2026-06
anomaly sweep across the NYC + LA catalogs. Distinguishes **bugs** (wrong/fabricated values),
**coverage gaps** (legitimately missing data), and **saturation** (a real ceiling that just
doesn't differentiate). Status: ✅ fixed, ⚠️ open, ℹ️ by-design.

## economic_security
- ✅ **Coarse-geography (was the worst).** Resolved to CBSA (whole metro), so 47% of NYC
  places shared 71.5 and 83% of LA shared 58.8, and it mis-anchored edge towns
  (Greenwich→Bridgeport scored 46). Fixed by blending in LODES job-accessibility
  (reachable-market gravity). Now NYC 78 / LA 51 distinct values. See [LIVE_SCORER_VS_EXPLORER]
  and design note in memory.
- ⚠️ **Residual:** the *market_quality* half still uses CBSA labor-market data, so Greenwich's
  quality term is still Bridgeport's. Minor now that job-access dominates; revisit if needed.

## diversity
- ⚠️ **Geography-fallback can fabricate 0.** When tract lookup fails, the fallback can resolve
  to a zero-population `county_subdivision`, yielding diversity=0 (impossible). Confirmed
  persistent for **Southport** (marked no-data). **Maspeth** was a transient 0, now 72.5.
  Likely affects other small villages/CDPs not in this catalog. Fix = harden the fallback chain
  (tract→block group→place→county) so it never returns a zero-pop geography.

## community_safety
- ℹ️ **COMING_SOON for some jurisdictions** (Sleepy Hollow, Summit, Belmont Shore, Lakewood) —
  FBI CDE crime data isn't wired up there yet. Pillar correctly returns None; weight drops.
  NOT bad data — do not treat these nulls as broken.

## built_environment
- ⚠️ **~34% of catalog carries stale coverage-0 scores** (transient Overpass timeouts at build
  time → fabricated ~57 floor). Live has a reliability guard; the catalog backfill is pending.
  Concrete example: Short Hills built_environment=21 (confidence 90 ≠ stale, but other low-confidence
  ones are). See built-beauty-backfill memory.

## public_transit_access
- ✅ Subway/commuter split + commuter-access floor (ridership-weighted) shipped.
- ⚠️ **Live fetch is noisy.** Transitland under load undercounts routes (Astoria → 2 subway
  lines on a bad fetch); a single live pass is unreliable. Catalog uses stable stored counts.
  Do NOT trust a single-pass live transit re-fetch as ground truth.

## air_travel_access
- ✅ **Was saturated** (every LA place = exactly 100, std 0) due to a 25km flat-100 plateau +
  summing 3 airports. Fixed with drive-time bands; LA std 0 → 11.

## quality_education
- ℹ️ **Gated behind `ENABLE_SCHOOL_SCORING` (default off, quota-limited).** Catalog was built
  with it on and now weights it; a default *live* score does not. Real Live-vs-Explorer
  divergence (documented).
- ℹ️ **95-ceiling for elite districts** (Chappaqua, Darien, Short Hills, Westport, Great Neck,
  ... 23 places). A legitimate ceiling — schools are district-administered, so a district's
  towns share a score. Means top districts don't separate from each other.

## healthcare_access
- ℹ️ **Saturates at 100** for ~58 NYC places across 10 counties. Genuine: dense metro near many
  major hospitals. Not coarse-geo, but it doesn't differentiate in the urban core.

## neighborhood_amenities
- ℹ️ Possible **point-placement undercount** for some walkable strips — e.g. Larchmont Village
  amenities=47.7 despite the famous Larchmont Blvd (catalog coordinate may sit in the
  residential interior, missing the commercial strip). Spot-check if a specific place looks off.

## political_lean
- ℹ️ **All null / disabled** (weight 0). Intentional.

## social_fabric — ⚠️ OPEN: density proxy overrides real civic strength (needs data-backed fix)
`infrastructure_density` is largely a **population-density proxy**, and it dominates the
score — penalizing low-density suburbs even when their *actual* civic life is strong. Worked
example: **Larchmont 49.6 vs Bronxville 62.6**, yet Larchmont **beats** Bronxville on civic
nodes (40 vs 19), civic gathering (100 vs 66), orgs/1k (1.4 vs 1.0), engagement (47 vs 43),
stability (48 vs 41), rootedness (94 vs 89). The entire 13-pt gap is `infrastructure_density`
(43 vs 70), driven only by density (5,977 vs 11,636 /sq mi). The pillar equates "fewer people
per sq mi" with "weaker community" — wrong for affluent suburbs with strong club/org/civic
fabric. **TODO (data-backed, not hand-waved):** investigate suburban & neighborhood social
fabric — should `infrastructure_density` be down-weighted, or credited by civic-node /
org / gathering strength when density is low? Derive the weighting from evidence, per place
morphology, not intuition.

## public_transit_access — ⚠️ OPEN: commuter floor leaks car commutes
The commuter-access floor is `commute_score × ridership_ramp(transit_share)`, but
`commute_score` is the mean commute of **all** workers (drivers included). In corporate-corridor
suburbs (Harrison: ~24-min mean commute from local Purchase/White Plains office parks), short
*driving* commutes inflate the transit score. **Harrison ranks #1 of all suburbs (83.4)** partly
for this reason — it's the only town maxing both terms (commute 83.4 × full ramp at 35% share),
but the commute term is driver-inflated. **TODO:** isolate transit-commuters' commute time
(ACS B08134 by mode, if available) rather than all-worker mean.

## climate_risk, active_outdoors, natural_beauty, housing_value
- No coarse-geo or fabricated-value issues found.

## Cross-cutting reminders
- **Data-backed logic per pillar:** when a pillar mis-ranks a place, fix the *logic* with
  evidence (what the metric should measure and why), not a one-off nudge. Every weighting/
  threshold should trace to a rationale, not a hand-wave.
- **Weight normalization:** a place's weights must sum to 100 over its *scored* pillars
  (non-null score, excluding `political_lean`). Any reweight must renormalize over scored
  pillars only (the education-enable bug left 4 places at 92.86 until repaired).
- **Coarse-geo fingerprint:** if a pillar's value is identical across places in *different
  counties*, suspect a CBSA/county/division fetch being applied as if per-place (the
  economic_security and transit-share bug pattern). Tract-level fetch is the fix.
