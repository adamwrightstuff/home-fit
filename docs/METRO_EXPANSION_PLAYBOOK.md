# Metro Expansion Playbook

How to add a new city to HomeFit. Every step is mandatory. Missing any produces a partially-scored catalog like SF did (no housing-type filter, wrong status signal normalization, stale safety baselines, etc.).

---

## The 30-second version

```bash
# 1. Register CBSA in the baseline builder (one code change, see Phase A)
# 2. Register files in the frontend (three files, see Phase B)
# 3. Run everything:
HOMEFIT_API_BASE=https://home-fit-production.up.railway.app \
HOMEFIT_PROXY_SECRET=<secret> \
HOMEFIT_TRANSIT_STABLE_COMMUTE=true \
ANTHROPIC_API_KEY=<key> \
PYTHONPATH=. python3 scripts/catalog/score_metro.py \
  --csv  data/xx_metro_place_catalog.csv \
  --out  data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl \
  --metro xx
```

`score_metro.py` handles phases 0–10 in order. It's resumable — re-run if interrupted.

---

## Before and after every run: the metro agent

```bash
# Before scoring: checks Python, keys, a healthy Overpass server, Census, Transitland, the API,
# the place list, baselines, precinct files, crime source, and frontend registration.
PYTHONPATH=. python -m scripts.metro_agent preflight --metro xx

# After scoring: classifies every failed or empty pillar by cause and says what fixes it.
PYTHONPATH=. python -m scripts.metro_agent diagnose --input data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl --json
```

Do not start scoring while `preflight` reports a blocking failure. `diagnose` groups findings as
`RETRY_PILLAR` (an upstream lookup failed; re-run just that pillar), `RETRY_THEN_VERIFY`, and
`NEEDS_DATA_SOURCE` (retrying will not help). If one pillar fails for 40%+ of places it is called
out as systemic: fix the dependency first, then retry. A place with a material gap should not be
published.

---

## Phase A — Add the CBSA to the status signal baseline builder

**Why this comes first:** The status signal pillar normalizes income/home value/education against metro-specific p5/p95 bands. Without a CBSA entry, every place in the new metro falls back to a generic Census division average, producing flat, meaningless status signal scores.

SF had no CBSA entry when it was scored, which is why status signal scores were all near the division mean.

### For a known CBSA, add it to `build_metro_baselines_from_cbsa.py`:

```python
# In CBSA_COUNTIES:
"XXXXX": {  # Metro Name, ST
    "SS": ["001", "003", ...],  # state FIPS → list of county FIPS
},

# In CBSA_TO_KEY:
"XXXXX": "xx_metro",
```

CBSA codes and county FIPS: https://www.census.gov/geographies/reference-files/time-series/demo/metro-micro/delineation-files.html

**Built-in CBSAs** (already registered, no action needed):
| Metro | CBSA | Key | Counties |
|-------|------|-----|---------|
| LA | 31080 | `la_metro` | Los Angeles + Orange |
| NYC | 35620 | `nyc_metro` | 5 boroughs + NJ suburbs + Pike PA |
| SF | 41860 + 41940 | `sf_metro` | Alameda, Contra Costa, Marin, SF, San Mateo + Santa Clara, San Benito |
| Seattle | 42660 | `seattle_metro` | King, Kitsap, Pierce, Snohomish |
| Austin | 12420 | `austin_metro` | Bastrop, Caldwell, Hays, Travis, Williamson |
| Chicago | 16980 | `chicago_metro` | 9 IL counties + Jasper, Lake, Newton, Porter IN |
| Philadelphia | 37980 | `philadelphia_metro` | 5 PA + 4 NJ counties + New Castle DE + Cecil MD |

### Or pass it at runtime without touching the file:

```bash
PYTHONPATH=. python3 scripts/baselines/build_metro_baselines_from_cbsa.py \
  --add-metro xx_metro CBSA1 SS:001,003,005 CBSA2 SS:007,009
```

`score_metro.py` calls this automatically for known metros (`--metro nyc|la|sf`). For a new metro, run it manually first then use `--skip-baselines`.

---

## Phase B — Frontend registration (before first deploy)

The metro list lives in one registry; everything else derives from it.

1. `frontend/lib/catalogMetros.ts` — add the slug to `CATALOG_METROS` and an entry in `CATALOG_METRO_META` (short label, picker name, dot color, map bounds). The route, filter chips, map, dots, work-hub picker and `WorkZoneMetro` type all follow.
2. `frontend/next.config.js` — add `data/<slug>_metro_place_catalog_scores_merged.composites_recomputed.jsonl` to `outputFileTracingIncludes` so Vercel bundles it. (The API route finds the file by that naming convention, so name the output file exactly that.)
3. `frontend/lib/catalogMapTypes.ts` — `inferCatalogMetro` is only a fallback for untagged rows, but add the metro's states (and county split if a state is shared, like CA and NJ) so it never defaults to `nyc`.
4. Optional: `frontend/lib/workZones.json` hubs (see `docs/WORK_COMMUTE_PLAYBOOK.md`); `catalog_climate_profiles.jsonl` rows with `source: "<slug>_metro"` via `scripts/catalog/batch_climate_profiles.py`.
5. Optional server speedups, not required for correctness: `main.py` `_load_catalog_index` (catalog fast path; SF and Seattle are not in it either), `agent_recommend.py` (`HOMEFIT_AGENT_CATALOG_JSONL`, NYC by default) and `catalog_contribution.py` (NYC CSV only, off by default).

Check: `cd frontend && npx tsc --noEmit`.

---

## What `score_metro.py` does (phases 0–10)

| Phase | What it does | Data source | Pillar(s) affected |
|-------|-------------|-------------|-------------------|
| 0 | Status signal CBSA baselines | Census ACS (Census API) | `status_signal` |
| 1 | Batch score all places | HomeFit API (all 13 pillars) | All |
| 2 | Retry failed pillars | HomeFit API | Any that failed |
| 3 | Housing stock | Census ACS B25024 (Census API) | Explorer housing-type filter |
| 4 | ZIP codes | Nominatim reverse geocode | Agent recommendations |
| 5 | Political lean | Local precinct JSON files | `political_lean` |
| 6 | Local scene bucket | Stored business_list data | Explorer local-scene filter |
| 7 | Best-fit preference labels | Stored NB/built_env data | NB + built_environment UI |
| 8 | Charter school flag | NCES school data | Education filter |
| 9 | Archetype summaries | Claude API (~$5–15) | Agent recommendations |
| 10 | Composite recompute | Stored pillar scores (no API) | `total_score`, longevity, happiness |

---

## Phase A2 — Per-state and per-city data (check for EVERY new metro)

`score_metro.py` does not create these. Each one fails silently (empty or flat values), so check them before Phase 1, for every state the metro touches, not only the core city's.

| Need | How to check | If missing |
|------|--------------|-----------|
| **Political lean precinct file per state** | `ls data/election/<state>_precincts.json` for each state in the CBSA (a metro can span 3–4 states) | Register the state's Dataverse file IDs in `download_vest_shapefiles.py`, run it with `--states XX --build`. The builder joins 2024 results to 2020 geometry by exact key (TX, MD), by county rank order (PA), and validates every join by requiring 2020 vs 2024 precinct lean to correlate ≥0.90; a failing join (DE, Chicago after its 2022 ward remap) is discarded and the lookup reports the 2020 lean with `lean_2024_estimated: true`. Phase 5 writes empty lean without the file. |
| **Incident-level crime source for the core city** | Is the city in `open_data_city()` / `_OPEN_DATA_CITY_GEOID` in `data_sources/crime_api.py`? Currently NYC, LA, SF, Chicago, Philadelphia, Austin. | Add a fetcher returning FBI Part I violent/property counts within a circle, a bbox, the city's Census place GEOID, a `_PRECISION_MAP` entry in `pillars/community_safety.py`, and a test. Use the portal's FBI/NIBRS code column (Chicago `fbi_code`, Austin `ucr_category`, Philadelphia `ucr_general`), never free-text offense names. If the portal has no coordinates (Austin: block group only), apportion by polygon overlap (`scripts/baselines/build_austin_block_groups.py`). If the city publishes nothing, every place in that police department gets one city-wide rate, which is acceptable only for small suburbs. |
| **Airports, hospitals, transit centers** | `grep` the metro's main airport code in `pillars/air_travel_access.py`, major hospitals in `pillars/healthcare_access.py`, city in `MAJOR_METROS` in `pillars/public_transit_access.py` | Add to the static lists (these are data, not city exceptions). |
| **Regional / street-tree / NPI city lists** | Check `data_sources/regional_baselines.py`, `street_tree_api.py`, `npi_specialty_client.py` for the city | Add an entry or confirm the generic fallback is acceptable. |
| **NCES charter flag** | `data/nces_schools.csv` exists and covers the state | Phase 8 skips without it. |

---

## Pillar-by-pillar dependencies

### Pillars that need no special setup per metro
These work anywhere with no baseline updates:
- `active_outdoors` — Overpass OSM queries
- `natural_beauty` — GEE satellite + Overpass water
- `housing_value` — Zillow ZHVI (ZIP-level, national) + Census ACS
- `healthcare_access` — Overpass + CMS
- `air_travel_access` — static airport DB + geocode
- `neighborhood_amenities` — Overpass + Google Places fallback
- `public_transit_access` — Transitland API + Census commute
- `diversity` — Census ACS
- `quality_education` — SchoolDigger API (requires `ENABLE_SCHOOL_SCORING=true`)
- `natural_beauty` — GEE + Overpass

### Pillars that need metro-specific baselines

**`status_signal`**
- Needs `status_signal_baselines.json` with a CBSA entry for this metro
- Without it: falls back to Census division mean → all places score near 50, no differentiation
- Fix: Phase A above
- Builder: `scripts/baselines/build_metro_baselines_from_cbsa.py --only xx_metro`

**`community_safety`**
- Scores against one national scale (`community_safety_national_scale.json`, a random sample of US city/town police departments), so no per-metro rebuild is needed
- If the metro's core city publishes incident-level open data, add it as a bbox source in `data_sources/crime_api.py` (Part I offenses only, last full calendar year); otherwise places fall through to FBI per-agency data
- Builder: `scripts/baselines/build_community_safety_national_scale.py` (rebuild when a newer FBI data year is out)

**`social_fabric` (stability component)**
- Needs `stability_baselines.json` with the right Census division for this metro
- These are national/division-level and already cover all US metros
- No action needed unless adding a market outside US Census divisions

**`economic_opportunity`**
- Uses `economic_baselines.json` (Census division × area_type × metric)
- National, already covers all US Census divisions
- No action needed unless the metro is in a division not yet sampled
- Rebuild only if scoring reveals all economic scores are 50 flat: `scripts/baselines/build_economic_baselines_from_results.py`

### Pillars with env var requirements
- `quality_education`: needs `ENABLE_SCHOOL_SCORING=true` + SchoolDigger API keys
- `public_transit_access` (catalog mode): needs `HOMEFIT_TRANSIT_STABLE_COMMUTE=true` for accurate scores (single-pin census lookup is tract-boundary-sensitive)
- `economic_opportunity` (historical): needs BLS OEWS data (`data/oews_metro_wage_distribution.json`)

---

## Baseline files — what they are and when to rebuild

| File | Built by | Scope | When to rebuild |
|------|---------|-------|----------------|
| `data/status_signal_baselines.json` | `build_metro_baselines_from_cbsa.py` | Per CBSA | Adding a new metro (Phase A) |
| `data/community_safety_national_scale.json` | `build_community_safety_national_scale.py` | National sample of US city/town police departments | When a newer FBI data year is released (~annually) |
| `data/stability_baselines.json` | `build_stability_baselines_from_results.py` | Census division | If stability scores are flat — already national |
| `data/economic_baselines.json` | `build_economic_baselines_from_results.py` | Census division × area_type | If economic scores are 50 flat for a new region |
| `data/zillow_zhvi_zip.json` | `build_zillow_zhvi.py` | ZIP code, national | When Zillow releases new ZHVI data (~annually) |
| `data/oews_metro_wage_distribution.json` | `build_oews_metro_wages.py` | CBSA, national | When adding a metro with unusual wage distribution; also missing — run once |
| `data_cache/nrhp.sqlite` | `build_nrhp_db.py` | National NRHP register | When NRHP adds significant new listings |
| `data/voter_registration_tract_rates.json` | `build_voter_registration_baselines.py` | Tract, national | If voter turnout scores are wrong for a new state |

---

## Post-launch checklist

After `score_metro.py` completes:

```bash
# 1. Coverage check (printed automatically by score_metro.py, but run manually to verify)
PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py \
  --no-unversioned \
  --input data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl

# 2. Sanity check a few well-known places
python3 -c "
import json
targets = ['Mill Valley', 'Palo Alto', 'Berkeley']  # adjust for new metro
with open('data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl') as f:
    for line in f:
        p = json.loads(line)
        if p.get('catalog',{}).get('name') in targets:
            s = p.get('score',{})
            print(p['catalog']['name'], '→', s.get('total_score'), '|',
                  'ss:', (s.get('status_signal_breakdown') or {}).get('total'),
                  '| transit:', (s.get('livability_pillars') or {}).get('public_transit_access',{}).get('score'))
"

# 3. Health check all three metros (not just the new one)
PYTHONPATH=. python3 scripts/catalog/check_catalog_health.py --no-unversioned
```

---

## Adding a new metro (checklist summary)

- [ ] Look up CBSA code(s) and county FIPS (Census delineation file); list every state the CBSA spans
- [ ] Add CBSA to `CBSA_COUNTIES`, `CBSA_TO_KEY` in `build_metro_baselines_from_cbsa.py`
- [ ] Phase A2: precinct file for each state, crime source for the core city, airport/hospital/transit lists, NCES file
- [ ] Phase B: add the metro to `frontend/lib/catalogMetros.ts` and `next.config.js`; `npx tsc --noEmit`
- [ ] Grep `scripts/` for hardcoded metro lists (`"nyc", "la", "sf"`, e.g. `recompute_ses_baseline_fix.py`, `daily_education_rescore.py`, `map_catalog_to_usaleep.py`) and add the new metro
- [ ] Create place catalog CSV (`data/xx_metro_place_catalog.csv`) with columns: `name, county_borough, state_abbr, search_query, lat, lon`
- [ ] Run `score_metro.py` with all env vars set
- [ ] Verify coverage ≥95% for housing_stock, political_lean, local_scene_bucket, built_environment
- [ ] Spot-check community_safety spread across the core city (not one flat value) and political_lean is non-empty in every state
- [ ] Run `check_catalog_health.py --no-unversioned` against all metros
- [ ] Work commute feature: follow `docs/WORK_COMMUTE_PLAYBOOK.md` (job hubs, precomputed commutes, station access)
