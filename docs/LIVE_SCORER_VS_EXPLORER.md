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
- **built_beauty:** ~34% of catalog places carry stale coverage-0 scores; live has the
  reliability guard. See [[built-beauty-backfill-todo]].
- **built_beauty confidence — RESOLVED 2026-06-16:** catalog `confidence` was frozen at
  build time (mostly 90) and never re-derived after `assess_pillar_data_quality()` added
  its `data_warning`-based discount (3% for `suspiciously_low_height_diversity` /
  `low_building_coverage`, 12% for real failures like `api_error`). Recomputed from
  already-stored `architectural_analysis` data (no OSM re-fetch) via
  `scripts/recompute_built_beauty_confidence.py`: 282/292 places corrected (179 NYC, 103 LA).
  Confidence is metadata only — doesn't cascade into score/total_score.

### 6. Offline-rescore approximations
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
