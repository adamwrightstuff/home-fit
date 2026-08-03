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

`score_metro.py` handles all 11 phases in order. It's resumable — re-run if interrupted.

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

### Or pass it at runtime without touching the file:

```bash
PYTHONPATH=. python3 scripts/baselines/build_metro_baselines_from_cbsa.py \
  --add-metro xx_metro CBSA1 SS:001,003,005 CBSA2 SS:007,009
```

`score_metro.py` calls this automatically for known metros (`--metro nyc|la|sf`). For a new metro, run it manually first then use `--skip-baselines`.

---

## Phase B — Frontend registration (one-time, before first deploy)

Three files. All three must be done or the catalog page won't load the new metro.

**1. `frontend/app/api/catalog-map/route.ts`** — add the JSONL to `METRO_FILES`:
```typescript
xx: ['xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl'],
```

**2. `frontend/next.config.js`** — add to `outputFileTracingIncludes` so Vercel deploys it:
```javascript
"./data/xx_metro_place_catalog_scores_merged.composites_recomputed.jsonl",
```

**3. `frontend/lib/catalogMapTypes.ts`** — extend `inferCatalogMetro` if the new metro is in a new state:
```typescript
if (p.catalog.state_abbr === 'XX') {
  return XX_COUNTIES.has(p.catalog.county_borough) ? 'xx' : 'other_metro'
}
```

---

## What `score_metro.py` does (all 11 phases)

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
| 11 | Safety baselines rebuild | All metro catalog files | `community_safety` normalization |

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
- Needs `community_safety_baselines.json` computed from scored catalog places
- Without it: falls back to national avg → violent/property crime thresholds are wrong for the market
- Fix: Phase 11 (safety baselines rebuild), runs automatically after scoring
- Builder: `scripts/baselines/build_community_safety_baselines.py --inputs data/nyc... data/la... data/sf... data/xx...`

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
| `data/community_safety_baselines.json` | `build_community_safety_baselines.py` | All scored catalog places grouped by area_type | After adding any new metro |
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

## Adding a 4th metro (checklist summary)

- [ ] Look up CBSA code(s) and county FIPS at census.gov
- [ ] Add CBSA to `CBSA_COUNTIES` and `CBSA_TO_KEY` in `build_metro_baselines_from_cbsa.py`
- [ ] Register JSONL in `frontend/app/api/catalog-map/route.ts`
- [ ] Register JSONL in `frontend/next.config.js` outputFileTracingIncludes
- [ ] Extend `inferCatalogMetro` in `frontend/lib/catalogMapTypes.ts` if new state
- [ ] Create place catalog CSV (`data/xx_metro_place_catalog.csv`) with columns: `name, county_borough, state_abbr, search_query, lat, lon`
- [ ] Run `score_metro.py` with all env vars set
- [ ] Verify coverage ≥95% for housing_stock, political_lean, local_scene_bucket, built_environment
- [ ] Run `check_catalog_health.py --no-unversioned` against all metros
