# Live Scorer vs. Catalog Explorer — Known Differences

The same place can show a different score in the **Live Scorer** (scoring an arbitrary
address through the API) and the **Catalog Explorer** (the `/catalog` map/list). This doc
tracks the known divergences so they're not rediscovered each time. Two classes:

- **Design** — intentional, structural differences between the two paths.
- **Drift** — incidental: stale precomputed data, noisy fetches, or two implementations of
  the same logic getting out of sync.

> Maintenance: when you change a pillar's *scoring*, ask "does this also need to change in
> the Explorer's client-side code (`frontend/lib/*`) and/or be re-applied to the catalog
> data?" Most divergences below come from forgetting one of those.

## Architecture (why they differ at all)

| | Live Scorer | Catalog Explorer |
|---|---|---|
| Entry | `main.py` `get_livability_score` → full pillar computation per request (Python) | `/api/catalog-map` reads the precomputed `*_merged.jsonl` and returns it raw; the browser reranks (TypeScript) |
| Scores | computed fresh from live data sources each request | precomputed at catalog-build time, then offline-rescored in places (see Drift) |
| Weights | server-side token allocation (`main.py`) | client-side `reweightScoreResponseFromPriorities` (`frontend/lib/reweight.ts`) from the user's priorities |
| Personalization | server-side (preferences, income) | client-side transforms in `frontend/app/catalog/catalog-page-client.tsx` |

Note the **catalog fast-path** (`main.py:~1430`): even a *live API* lookup whose lat/lon
matches a catalog entry skips pillar recomputation and serves the stored score (re-applying
weights + NB preference only). So "live" and "Explorer" agree for catalog coords *except*
where the client-side path diverges below.

## Design differences (intentional)

### 1. Education / schools weighting — RESOLVED 2026-06-16
- **Live (default):** `ENABLE_SCHOOL_SCORING=True` (`main.py:94`, flipped from `False` now that
  SchoolDigger is a paid plan). `_apply_schools_disabled_weight_override` only zeros
  `quality_education` when a request explicitly opts out — so a default live score **does**
  count schools, matching the Explorer.
- **Explorer:** unchanged — catalog stores real education scores (status=success, confidence=85).
- Rate limiting in `data_sources/schools_api.py` was also unhardcoded from the old free-tier
  20/day, 1/min limits: `RATE_LIMIT_SECONDS` now defaults to 1.0s (env-tunable via
  `SCHOOLDIGGER_RATE_LIMIT_SECONDS`) and `QUOTA_WARNING_THRESHOLD` to 500 (via
  `SCHOOLDIGGER_QUOTA_WARNING_THRESHOLD`) — tune both once the actual paid-plan limits are
  confirmed.
- No longer a divergence. Was previously the biggest Design gap (good-school suburbs ranked
  higher in the Explorer than in a default live score).

### 2. Personalization is computed client-side in the Explorer
All applied in `catalog-page-client.tsx`'s `adjustedPlaces` memo, on the stored data:
- **Natural-beauty preference:** `applyNbPreferenceV9` (`frontend/lib/nbPreference.ts`) — a TS
  mirror of the Python `apply_v9_preference`. Verified bit-identical, but **two
  implementations to keep in sync** if the V9 preference math changes.
- **Household income:** `applyUserIncomeToScore`.
- **Political lean:** recomputed client-side from `breakdown.lean_2024`.
The Live Scorer has its own server-side equivalents. Any change to one must be mirrored.

### 10. neighborhood_beauty split in Explorer (2026-06-24)
The Explorer weight panel splits `neighborhood_beauty` into two independently weighted pillars:
- **`natural_beauty`** — the stored `natural_beauty_score` sub-score from the NB breakdown,
  optionally re-biased by scenery preference (mountains/ocean/etc.). Feeds Longevity and
  Happiness indices.
- **`built_environment`** — a client-computed area-type **match score** (0–100) based on how
  closely the place's `effective_area_type` matches the user's preferred neighborhood type
  (Urban Core / Urban Neighborhood / Suburban / Exurban / Rural). Uses an asymmetric distance
  penalty: being denser than preferred is penalized harder (60/30/5) than being sparser
  (75/50/20). `historic_urban` maps to index 4 (same as `urban_core`).
- The original `neighborhood_beauty` pillar is zeroed out in the catalog composite so it
  doesn't double-count. The live scorer still returns the merged `neighborhood_beauty` score
  and is unaffected.
- Longevity and Happiness indices now reference `natural_beauty` (client-side catalog only);
  the backend Python indices still use `neighborhood_beauty`. Mirror when the live scorer
  is updated.

### 3. total_score recomputation
Explorer recomputes `total_score` in the browser (`reweight.ts`); live computes it in Python.
Same intended math, two implementations.

### 4. LODES job-access coverage (economic_security)
Live `job_accessibility` falls back to market-quality outside NY/NJ/CT/CA (the parquet's
coverage). The catalog only contains NY/NJ/CT/CA places, so they're consistent there; a live
lookup elsewhere gets the fallback. See [[economic-security-design]].

## Drift (incidental — precomputed/stale or noisy)

### 5. Catalog staleness vs live recompute
Catalog pillar scores are precomputed; several were **offline-rescored** this cycle (transit
v3, air-travel commute bands, diversity fixes, NB V9, economic_security job-access, commuter
floor). A full live run can differ because:
- **economic_security:** catalog stores an older *market_quality* (e.g. Greenwich 46) while
  live recomputes it (~54) → catalog 69.0 vs live 72.7. Same blend formula, different input.
- **public_transit_access:** the live Transitland fetch is **noisy** — it can undercount
  routes (Astoria → 2 subway lines on a bad fetch). The catalog uses stable stored counts.
  See [[transit-fetch-noisy]]. So live transit can differ run-to-run and from the catalog.
- **built_environment:** ~34% of catalog places carry stale coverage-0 scores; live has the
  reliability guard. See [[built-beauty-backfill-todo]].
- **built_environment confidence — RESOLVED 2026-06-16:** catalog `confidence` was frozen at
  build time (mostly 90) and never re-derived after `assess_pillar_data_quality()` added
  its `data_warning`-based discount (3% for `suspiciously_low_height_diversity` /
  `low_building_coverage`, 12% for real failures like `api_error`). Recomputed from
  already-stored `architectural_analysis` data (no OSM re-fetch) via
  `scripts/recompute_built_environment_confidence.py`: 282/292 places corrected (179 NYC, 103 LA).
  Confidence is metadata only — doesn't cascade into score/total_score.

### 6. Built Beauty form-metric non-determinism — RESOLVED 2026-06-21
`compute_block_grain` had `@cached(ttl_seconds=CACHE_TTL['osm_queries'])`; `compute_
streetwall_continuity`, `compute_setback_consistency`, and `compute_facade_rhythm` did not,
despite a comment at the call site stating the 15s timeout relied on "caching handles
retries." Verified: calling the same place twice with caches cleared produced different
built_environment scores minutes apart (Bronxville 71.4 → 86.6) purely from live OSM/Overpass
timing variance on the uncached calls. Fixed by adding the missing decorator to all three
(matching `compute_block_grain`'s existing pattern). Live scores for a fixed place should now
be stable across requests within the 6h TTL.

### 7. Built Beauty height_diversity fabrication trigger — RESOLVED 2026-06-21
The GHSL height-substitution fallback (`get_building_height_diversity_ghsl`, already wired
into `compute_arch_diversity`) only fired when `levels_entropy < 5.0 AND >85%` of buildings
were untagged. The entropy threshold tested the unreliable *outcome*, not the actual cause —
a handful of real outlier buildings among mostly-untagged ones can push the fabricated entropy
to a misleadingly "plausible" value (7-9) that's still mostly fabrication, so borderline cases
slipped past the fix. Confirmed live for Bronxville/Manhattan Beach (~97% of buildings
untagged in both, entropy landing at 9.0/10.9 — both above the old 5.0 cutoff). Fixed by
dropping the entropy condition; trigger is now the untagged-ratio alone.

### 8. Built Beauty form-metric confidence formula — fixed, but does not affect score
`coverage_confidence` for setback/facade_rhythm multiplied two fractional ratios (segment
coverage × per-segment building-count validity), which compounds punitively — verified
catalog-wide this reads ~0.02 on 100% of places, every area type, a structural property of
the formula rather than a real reflection of data quality anywhere. Fixed to a single
completeness ratio. **Caveat discovered during verification:** the production scoring path
(`HOMEFIT_USE_CALIBRATED_BUILT_BEAUTY=1`, default on) never reads this confidence value at
all — only the raw setback/facade/block_grain/streetwall *values* feed the calibrated model,
never their confidence. The fix is correct and real, but it only affects an internal
diagnostic field today; it does not move any live score unless the legacy (non-calibrated)
path is ever re-enabled.

### 9. active_outdoors scored under stale pre-pillar area_type — RESOLVED 2026-06-21
Pillars run on a pre-pillar area_type estimate (OSM-only business count, 35s timeout); the
*reported* area_type is corrected post-pillar using `neighborhood_amenities`'s own
(possibly Places-augmented) count. `active_outdoors` expectations swing sharply by area_type
(`expected_parks_within_1km`: 8 for urban_core vs 380 for urban_residential), so a stale
pre-pillar classification can score it under the wrong curve entirely — isolated testing
showed ±30pt swings on the same place/instant depending only on which area_type it ran
under. Fixed: `active_outdoors` is now re-scored when the post-pillar reclassification
disagrees with what it ran under (no-op on healthy-OSM requests; a real correction on
thin-OSM ones). Catalog data predating this fix is NOT automatically corrected — places whose
`area_type` was relabeled by the 2026-06-21 area-type fix still carry the *old* area_type's
`active_outdoors` score until rescored.

### 10. Diversity fabricated zero for villages with no Census tract — RESOLVED 2026-06-21
`get_diversity_score()` returned `(0.0, details)` whenever `census_api.get_diversity_data()`
found no tract match (common for small villages/unincorporated areas) — indistinguishable
from a place with real Census data showing genuinely zero entropy. That fabricated 0 carried
full weight in the headline total as a confidently-measured "least diverse possible" score.
Fixed: now raises, routing through the existing pillar-failure path (`status='failed'`,
excluded from the headline total) instead of fabricating a number.

### 11. neighborhood_beauty catalog merge — offline, verified surgical
The built_environment/natural_beauty → neighborhood_beauty schema merge was applied to all 292
LA/NYC catalog places offline (no live scoring), blending each row's already-stored sub-scores
with the validated density+area-type formula. Verified zero pillar-score drift on every other
pillar. A first pass also accidentally over-recomputed `status_signal`/`happiness_index` for
*every* row (via an unconditional `recompute_composites_from_payload` call) even though
`status_signal` doesn't depend on built_environment/natural_beauty/neighborhood_beauty at all —
reverted to last-known-good except for the rows whose `area_type` genuinely changed (where
recomputing is legitimate, since `status_signal` does consume `area_type`).

### 12. Offline-rescore approximations
Catalog rescores used stored sub-components rather than a full live run, e.g.:
- Commuter-access floor: catalog uses the stored Happiness `commute` value + a Census
  transit-share fetch; live fetches commute time live. Both deterministic-ish but can drift.
  See [[transit-commuter-access-floor]].

## How to reconcile (the real fix)
The clean way to eliminate Drift is to **rebuild the catalog by running places through the
live `main.py` scorer** (the "faithful backfill through main.py context" — same caveat noted
for Built Beauty in [[built-beauty-backfill-todo]]). Offline rescores are faster but
accumulate drift. Until then, treat live as source of truth for scoring *logic* and the
catalog as a precomputed snapshot.

## Open items
- [x] Decide whether the Explorer default should match live on **schools** — both ON as of 2026-06-16.
- [ ] Single-source the NB-preference math (currently Python + a TS mirror).
- [ ] Faithful catalog rebuild through main.py to clear accumulated offline-rescore drift.
- [ ] Built Beauty catalog backfill (stale coverage-0 places).
- [ ] 5 places with broken/stale density (Fort Greene, Maspeth, Southport, Glendale [Queens],
  Pelham Bay) — Fort Greene's stored `density=0.0` is confirmed stale (fresh Census lookup
  returned 61,732/sq mi); the other 4 need the same check. Feeds wrong input into both
  `active_outdoors` expectations and the `neighborhood_beauty` blend weight for these 5.
- [ ] Catalog active_outdoors rescore for the 186 places whose area_type changed 2026-06-21
  (see #9 above) — labels are correct, active_outdoors score is not, until rescored.
