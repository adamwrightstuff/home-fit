# Metro Runbook

The short version. Everything runs on your laptop from the repo root with the venv active:

```
cd ~/Dev/home-fit && git pull origin main && source .venv/bin/activate
```

All commands are `PYTHONPATH=. python -m scripts.metro_agent <command>`. Details for a brand-new state or city are in `METRO_EXPANSION_PLAYBOOK.md`.

## 1. Launch a new metro

Before the first run, `state --metro <metro>` shows whether each state's election data is built (`--build` creates it), and the metro needs its place list (`data/<metro>_metro_place_catalog.csv`), baselines (including the status-signal class cutoffs: `PYTHONPATH=. python3 scripts/baselines/build_class_cuts.py --only <metro>_metro`), precinct file for its state, a crime source, and an entry in `frontend/lib/catalogMetros.ts` and `frontend/next.config.js`. `preflight` tells you exactly which of these is missing. A suburb pin far from its Census town center now blocks the run until it is fixed or listed with a reason in `data/pin_exceptions.json`.

```
run --metro <metro>
```

It runs preflight, scores every place, retries what failed, checks the results against Census and neighbouring places, and stops at a gate. If the gate passes it prints the publish command; add `--push` to publish automatically.

If it prints **BLOCKED**, read the "WHY IT IS BLOCKED" section. Typical fixes:

| Blocked on | Fix |
|---|---|
| Overpass down (preflight FAIL) | Wait for `overpass.openstreetmap.fr` to answer, then run the same command again |
| Crime data missing for a place | Add its agency to `data/crime_agency_map.json`, run `run --metro <metro> --skip-score` |
| A gap that is genuinely real (no transit, no data) | `accept --input <file> --place "<name>" --pillar <pillar> --reason "<why>"`, then run again |
| Contradicted by Census | The lookup returned empty. `health --fix`, or run again |
| Place scored at an old pin | `run --metro <metro>` (it rescores changed pins automatically) |

Running the same command again is always safe; scoring is resumable.

## 1b. Climate and education (now part of `run`)

`run` does these itself right after scoring (step 2b), before anything that needs Overpass, so they finish even when Overpass is down. Education stops at the SchoolDigger daily quota; run the same command again the next day and it resumes. To do them by hand:

1. **Education.** SchoolDigger has a daily quota, so it is its own job. With the local API running and `SCHOOLDIGGER_APPID/APPKEY` set: `PYTHONPATH=. python3 scripts/catalog/daily_education_rescore.py` (repeat daily until done; it stops at the quota). Then refresh composites with `scripts/catalog/recompute_catalog_composites.py --no-census --input FILE --output FILE` and confirm with `python3 scripts/catalog/check_education.py --metro <metro>`. The health check flags the metro until this passes.
2. **Climate.** `PYTHONPATH=. python3 scripts/catalog/batch_climate_profiles.py` (every metro is picked up automatically; resumable).
3. **Optional.** Work-commute hubs (`docs/WORK_COMMUTE_PLAYBOOK.md`).

Commit the education and climate files together with the metro, then publish.

## 2. Health check

```
health                     # audit all launched metros
health --metro austin      # one metro
health --fix               # retry what can be retried, then re-audit
health --offline           # skip the Census cross-checks
```

Verdicts: **HEALTHY** (publish), **ATTENTION** (publishable; notes to read), **UNHEALTHY** (the publish gate would block it). It checks coverage of the place list, pins, prerequisites, every failed or empty pillar by cause, composite consistency, and the Census cross-checks.

For per-pillar detail on one file: `python scripts/catalog/check_catalog_health.py --no-unversioned --input <file>`.

## 3. Publish

Only a HEALTHY or ATTENTION metro. Add just that metro's file, never `git add .`:

```
PYTHONPATH=. python3 scripts/catalog/batch_climate_profiles.py   # climate for the new places (resumable, ~3 s each)
git add data/<metro>_metro_place_catalog_scores_merged.composites_recomputed.jsonl data/catalog_climate_profiles.jsonl
git commit -m "<Metro> metro scores" && git push origin main
```

Vercel redeploys from main. Or use `run --metro <metro> --push`.

## Batch scoring behaviour (set automatically by `run` and `health --fix`)

- **Strict lookups** (`HOMEFIT_STRICT_LOOKUPS=true`): a pillar whose lookup failed comes back as unknown instead of a number built on partial data. The live site is unaffected.
- **Raw Overpass cache** (`HOMEFIT_OSM_CACHE_DIR`, default `.osm_cache/`, git-ignored): good answers are saved and replayed, so a rescore re-asks only what failed and a logic change needs no network. Empty or error answers are never saved. Set `HOMEFIT_OSM_CACHE_MODE=replay` to run fully offline, or delete `.osm_cache/` to refresh. Both need the API restarted by the agent (kill a leftover server first: `lsof -ti:8000 | xargs kill`).

## Rules of thumb

- Offline first. If a fix can be computed from numbers already stored in the catalog, do it offline. The API is for data that is not stored.
- Never rescore on an error flag alone; look at the stored breakdown first.
- Recompute composites with `--no-census` unless the status-signal formula or baselines changed on purpose.
- Do not run several scoring jobs at once; the public Overpass servers throttle.
- Never add a city exception; fix the area-type classification or the curve.

## Other commands

`preflight --metro X` (checks only), `diagnose --input F` (what is wrong, by cause), `resolve --input F` (retry), `validate --input F --apply` (cross-checks), `probe --input F` (ask upstream services directly), `fbi --input F --suggest` (crime agency candidates), `accept` (sign off a real gap).
