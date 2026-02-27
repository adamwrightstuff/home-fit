# HomeFit Admin & Diagnostic Tools

Quick reference for backend admin endpoints and scripts.  
**Backend URL:** `https://home-fit-production.up.railway.app`

If `HOMEFIT_PROXY_SECRET` is not set in Railway, these endpoints accept requests without a header. If it is set, add:  
`-H "X-HomeFit-Proxy-Secret: $HOMEFIT_PROXY_SECRET"` (with the variable in your env or sourced from `.env`).

---

## 1. API endpoints

### Liveness (public, no auth)
```bash
curl -s "https://home-fit-production.up.railway.app/healthz" | jq .
```

### Health (credentials, cache, GEE, pillar list)
```bash
curl -s "https://home-fit-production.up.railway.app/health" | jq .
```

### Cache stats (Redis + in-memory)
```bash
curl -s "https://home-fit-production.up.railway.app/cache/stats" | jq .
```

### Clear score cache only
```bash
curl -s -X POST "https://home-fit-production.up.railway.app/cache/clear?cache_type=scores" | jq .
```

### Clear all caches
```bash
curl -s -X POST "https://home-fit-production.up.railway.app/cache/clear" | jq .
```

### Telemetry (request/error stats)
```bash
curl -s "https://home-fit-production.up.railway.app/telemetry" | jq .
```

### Score one place (with optional diagnostics)
```bash
curl -s "https://home-fit-production.up.railway.app/score?location=Seattle%2C%20WA&diagnostics=true" | jq .
```

### Score one pillar only (e.g. economic_security)
```bash
curl -s "https://home-fit-production.up.railway.app/score?location=Seattle%2C%20WA&only=economic_security" | jq .
```

---

## 2. Scripts (run from project root)

### Check backend score (create job, poll, print score)
Uses `.env` for `RAILWAY_API_BASE_URL` and `HOMEFIT_PROXY_SECRET` if present.
```bash
./scripts/check_backend_score.sh
# Or with a location:
./scripts/check_backend_score.sh "Austin, TX"
```

### Score all locations in data/locations.csv
Prints `location,total_score`. Set `HOMEFIT_API_URL` to hit Railway.
```bash
export HOMEFIT_API_URL="https://home-fit-production.up.railway.app"
PYTHONPATH=. python3 scripts/score_locations.py
# Save to file:
PYTHONPATH=. python3 scripts/score_locations.py > scores.csv
```

### Validate economic security pillar (16 locations)
Distribution check + resilience spot-check. Optional `--api` to use backend; optional `--quick` to skip heavy area_type detection.
```bash
PYTHONPATH=. python3 scripts/validate_economic_security.py --quick --delay 0.3
```

### API health check (local or set base_url)
Hits `/`, `/health`, `/score`; checks calibration. Default: localhost:8000.
```bash
python3 scripts/test_api_health.py
# Or with Railway:
python3 scripts/test_api_health.py --base-url https://home-fit-production.up.railway.app
```

### Rebuild economic baselines (long run)
Recalibrates mean/std from locations in CSV. Writes `data/economic_baselines.json`. Restart API or wait for mtime-based reload to use new baselines.
```bash
PYTHONPATH=. python3 scripts/build_economic_baselines.py \
  --input data/locations.csv \
  --output data/economic_baselines.json \
  --limit 0 \
  --min-samples 5 \
  --sleep 0.12
```

---

## 3. Using a proxy secret (if set on Railway)

If `HOMEFIT_PROXY_SECRET` is set in Railway, get its value from Railway → Project → Service → Variables, then either:

**Option A – export once, then run curls**
```bash
export HOMEFIT_PROXY_SECRET='your-secret-here'
curl -s "https://home-fit-production.up.railway.app/health" \
  -H "X-HomeFit-Proxy-Secret: $HOMEFIT_PROXY_SECRET" | jq .
```

**Option B – use a .env in project root**
```bash
# In project root, create or edit .env with:
# HOMEFIT_PROXY_SECRET=your-secret-here
# RAILWAY_API_BASE_URL=https://home-fit-production.up.railway.app (optional)

source .env
curl -s "https://home-fit-production.up.railway.app/cache/clear?cache_type=scores" \
  -H "X-HomeFit-Proxy-Secret: $HOMEFIT_PROXY_SECRET" | jq .
```

---

## 4. Summary table

| Action              | Command / script |
|---------------------|------------------|
| Liveness            | `GET /healthz`   |
| Health + credentials| `GET /health`    |
| Cache stats         | `GET /cache/stats` |
| Clear score cache   | `POST /cache/clear?cache_type=scores` |
| Clear all cache     | `POST /cache/clear` |
| Telemetry           | `GET /telemetry` |
| Score one place     | `GET /score?location=...` |
| Score + diagnostics | `GET /score?location=...&diagnostics=true` |
| One pillar          | `GET /score?location=...&only=economic_security` |
| Backend score check | `./scripts/check_backend_score.sh` |
| Score 40 locations  | `scripts/score_locations.py` |
| Validate econ pillar| `scripts/validate_economic_security.py` |
| API health check    | `scripts/test_api_health.py` |
| Rebuild baselines   | `scripts/build_economic_baselines.py` |
