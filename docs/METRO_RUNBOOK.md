# Metro Runbook

The short version. Everything runs on your laptop from the repo root with the venv active:

```
cd ~/Dev/home-fit && git pull origin main && source .venv/bin/activate
```

All commands are `PYTHONPATH=. python -m scripts.metro_agent <command>`. Details for a brand-new state or city are in `METRO_EXPANSION_PLAYBOOK.md`.

## 1. Launch a new metro

Before the first run, the metro needs its place list (`data/<metro>_metro_place_catalog.csv`), baselines, precinct file for its state, a crime source, and an entry in `frontend/lib/catalogMetros.ts` and `frontend/next.config.js`. `preflight` tells you exactly which of these is missing.

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
git add data/<metro>_metro_place_catalog_scores_merged.composites_recomputed.jsonl
git commit -m "<Metro> metro scores" && git push origin main
```

Vercel redeploys from main. Or use `run --metro <metro> --push`.

## Rules of thumb

- Offline first. If a fix can be computed from numbers already stored in the catalog, do it offline. The API is for data that is not stored.
- Never rescore on an error flag alone; look at the stored breakdown first.
- Recompute composites with `--no-census` unless the status-signal formula or baselines changed on purpose.
- Do not run several scoring jobs at once; the public Overpass servers throttle.
- Never add a city exception; fix the area-type classification or the curve.

## Other commands

`preflight --metro X` (checks only), `diagnose --input F` (what is wrong, by cause), `resolve --input F` (retry), `validate --input F --apply` (cross-checks), `probe --input F` (ask upstream services directly), `fbi --input F --suggest` (crime agency candidates), `accept` (sign off a real gap).
