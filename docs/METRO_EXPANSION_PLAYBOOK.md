# Metro Expansion Playbook

How to add a new city to HomeFit. Every step is mandatory. Missing any produces a partially-scored catalog like SF did (no housing-type filter, wrong status signal normalization, stale safety baselines, etc.).

---

## The 30-second version

The flow is automated: see [METRO_AUTOMATION.md](METRO_AUTOMATION.md). In short:

```bash
PYTHONPATH=. python -m scripts.metro_agent prereqs --state XX --fetch --yes   # per new state: election, Census outlines, school snapshot
PYTHONPATH=. python -m scripts.metro_agent init   --metro xx                  # spec -> place list with checked pins, registry entry, baselines
PYTHONPATH=. python -m scripts.metro_agent run    --metro xx                  # score (resumable)
PYTHONPATH=. python -m scripts.metro_agent finish --metro xx                  # education, crime agencies, retries, rule-based gap acceptance
PYTHONPATH=. python -m scripts.metro_agent ship   --metro xx                  # gate, go live, commit and push only this metro
```

The phases and per-pillar notes below explain what each step does and why; the steps themselves no longer need hand edits.

---

## The one-command launch

```bash
PYTHONPATH=. python -m scripts.metro_agent run --metro chicago          # stops for review at the gate
PYTHONPATH=. python -m scripts.metro_agent run --metro chicago --push   # commits + pushes only if the gate passes

If the gate is BLOCKED, `run` automatically runs the probe (and the FBI agency probe when an FBI key is set) and prints raw upstream evidence for every remaining gap, so no separate diagnostic commands are needed.
```

### Auditing launched metros

`PYTHONPATH=. python -m scripts.metro_agent health` audits every launched metro with the same checks as the launch gate (coverage of the place list, pins, prerequisites, per-pillar diagnosis, Census cross-checks) and gives each a HEALTHY / ATTENTION / UNHEALTHY verdict. `--fix` runs the resolver on the retryable problems and re-audits; `--metro X` limits it; `--offline` skips the Census calls.

`run` starts the local API if it is not running, runs preflight (a blocking failure stops it before any
scoring), scores the place list (resumable: if interrupted, run the same command again), retries upstream
failures, and ends with `PUBLISH: OK` or `PUBLISH: BLOCKED`. Exit codes: 0 published/ready, 1 blocked by a
material gap, 2 preflight failed, 3 places that never score. Before the first launch of a new metro, finish the
checklist at the bottom (CBSA, place list, precinct files, frontend registry); preflight will tell you what is missing.
The stages below can also be run one at a time.

## Before and after every run: the metro agent

```bash
# Before scoring: checks Python, keys, a healthy Overpass server, Census, Transitland, the API,
# the place list, baselines, precinct files, crime source, and frontend registration.
PYTHONPATH=. python -m scripts.metro_agent preflight --metro xx

# After scoring: classifies every failed or empty pillar by cause and says what fixes it.
PYTHONPATH=. python -m scripts.metro_agent diagnose --input data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl --json

# Fix what can be fixed: retries only the affected pillars for only the affected places (needs the
# API running), keeps the better result, hands off what retrying cannot fix, recomputes composites.
PYTHONPATH=. python -m scripts.metro_agent resolve --input data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl --dry-run
PYTHONPATH=. python -m scripts.metro_agent resolve --input data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl
```

`resolve` exits non-zero while any place has a material gap, so it doubles as the publish gate.

For gaps retrying cannot fix, ask the sources directly:

```bash
PYTHONPATH=. python -m scripts.metro_agent probe    --input FILE   # raw Overpass / Transitland data for unresolved amenities and transit
PYTHONPATH=. python -m scripts.metro_agent validate --input FILE --apply   # Census business counts, commuting, peers; records genuine gaps
PYTHONPATH=. python -m scripts.metro_agent fbi      --input FILE --suggest # which police agency could serve a place with no crime data
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
4. Required: climate profiles. Run `PYTHONPATH=. python3 scripts/catalog/batch_climate_profiles.py` (picks up every metro catalog automatically, resumable, ~3 s per place) and commit `data/catalog_climate_profiles.jsonl`. Optional: `frontend/lib/workZones.json` hubs (see `docs/WORK_COMMUTE_PLAYBOOK.md`).
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
| **Incident-level crime source for the core city** | Is the city in `open_data_city()` / `_OPEN_DATA_CITY_GEOID` in `data_sources/crime_api.py`? Currently NYC, LA, SF, Chicago, Philadelphia, Austin, Dallas (NIBRS code, point per offense), Denver (ArcGIS offense category; the public file omits rape/sexual assault) and Boston (BPD offense codes; the public file omits rape/sexual assault, so violent counts run slightly low; the portal firewall rejects arithmetic and NULLIF in SQL, so the circle is applied in Python). | Add a fetcher returning FBI Part I violent/property counts within a circle, a bbox, the city's Census place GEOID, a `_PRECISION_MAP` entry in `pillars/community_safety.py`, and a test. Use the portal's FBI/NIBRS code column (Chicago `fbi_code`, Austin `ucr_category`, Philadelphia `ucr_general`), never free-text offense names. If the portal has no coordinates (Austin: block group only), apportion by polygon overlap (`scripts/baselines/build_austin_block_groups.py`). If the city publishes nothing, every place in that police department gets one city-wide rate, which is acceptable only for small suburbs. |
| **Airports, hospitals, transit centers** | `grep` the metro's main airport code in `pillars/air_travel_access.py`, major hospitals in `pillars/healthcare_access.py`, city in `MAJOR_METROS` in `pillars/public_transit_access.py` | Add to the static lists (these are data, not city exceptions). |
| **Regional / street-tree / NPI city lists** | Check `data_sources/regional_baselines.py`, `street_tree_api.py`, `npi_specialty_client.py` for the city | Add an entry or confirm the generic fallback is acceptable. |
| **NCES charter flag** | `data/nces_schools.csv` exists and covers the state | Phase 8 skips without it. |
| **Schools (all of Phase A3)** | `ls data/school_snapshot/<ST>.json.gz` for every state in the CBSA; Census district and place files for the state in `data/school_geo/` | See Phase A3: fetch the state snapshot (3 to 28 SchoolDigger calls), add the zone maps if the district publishes them, rebuild the bundle. |

---

## Phase A3 — Schools (`quality_education`), per new metro

Full model and rules: [PILLAR_QUALITY_EDUCATION.md](PILLAR_QUALITY_EDUCATION.md). SchoolDigger is **not** called per place any more: each state is pulled once into a local snapshot, and everything else is local.

1. **State snapshot** (the only SchoolDigger spend; 500 schools per call, so 3 to 28 calls per state, billed as overage beyond 2,000 calls a month, about $0.008 each): `PYTHONPATH=. python3 scripts/catalog/fetch_school_snapshot.py --states PA,NJ,DE`. A state already in `data/school_snapshot/` is skipped, so a second metro in the same state costs nothing. Refresh yearly.
2. **Census district and place outlines** for each new state: download TIGER/Line `UNSD`, `ELSD`, `SCSD` (district) and `PLACE` for the state FIPS into `data_cache/tiger_sd_2024/` and `data_cache/tiger_place_2024/` (same folder layout as the existing states), and add the FIPS to `STATES` in `scripts/catalog/build_school_data_bundle.py`.
3. **Zone maps** (optional but better): look for the core district's current attendance-zone layers (district GIS page, city open-data portal). Download each level into `data_cache/zone_maps/<metro>_<level>_<year>/` and add a `ZoneLayer` per level in `data_sources/school_zones.py` (name field, id field, vintage, a caveat). A level the district does not zone (lottery or application) needs no layer: the scorer shows it as "choice, not scored" whenever the district has any zone layer.
4. **Rebuild the bundle** (`PYTHONPATH=. python3 scripts/catalog/build_school_data_bundle.py`) and commit `data/school_geo/` (about 11 MB total). Production reads the bundle and the snapshot, not `data_cache/`.
5. **Score**: the normal `score_metro.py` run scores education through the API (the live scorer uses the same code). To re-score an existing catalog offline in seconds with no API calls: `PYTHONPATH=. python3 scripts/catalog/rescore_education_offline.py`.
6. **After any education re-score**, in this order: `python3 scripts/catalog/enable_education_weight.py` (a live `only=` rescore zeroes the weight), `recompute_catalog_composites.py --in-place --no-census` per metro, `check_education.py`. The education check must PASS before publishing; known data gaps go in `data/education_check_exceptions.json` with a reason.
7. **Add the metro** to `scripts/catalog/rescore_education_offline.py` (`METROS`), `scripts/catalog/check_education.py` (`METROS`) and `scripts/catalog/enable_education_weight.py` (`CATALOGS`).

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
- `quality_education` — local SchoolDigger state snapshot + Census district/place outlines + district zone maps (Phase A3)
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
- `quality_education`: SchoolDigger API keys only for `fetch_school_snapshot.py` (Phase A3); scoring reads the committed snapshot and bundle
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

- [ ] Write `data/metro_specs/xx.json` (CBSA code, states, neighborhoods by parent city, suburbs); the CBSA and county list come from the Census delineation file
- [ ] `prereqs --state XX` for every state the CBSA spans (election data, Census outlines, school snapshot) and make sure the private Overpass server covers it (`data/overpass_states.json`)
- [ ] `init --metro xx`: place list (OSM place-center pins, neighborhoods inside their parent city, counties inside the CBSA), pin exceptions, registry entry, baselines
- [ ] Core-city crime source (Phase A2) and airport, hospital, transit lists: check, add if missing
- [ ] Zone maps for the core district (Phase A3, optional but better)
- [ ] `run --metro xx` (or `scripts/catalog/run_metros_batch.sh` for several), one at a time
- [ ] `finish --metro xx`, then read what it left open
- [ ] Verify coverage of housing_stock, political_lean, local_scene_bucket; spot-check community_safety is not one flat value in the core city
- [ ] `check_catalog_health.py --no-unversioned` against all metros
- [ ] `ship --metro xx` (commits and pushes only this metro; status becomes `live`)
- [ ] Work commute feature (optional): `docs/WORK_COMMUTE_PLAYBOOK.md`

Superseded by the registry (no longer edited by hand): the CBSA dictionaries, `frontend/lib/catalogMetros.ts`, `next.config.js`, `catalogServer.ts`, the county rules in `catalogMapTypes.ts`, and the metro lists in the education scripts.
