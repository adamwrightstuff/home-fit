# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

HomeFit is a personalized livability scoring API (Python/FastAPI backend) with a Next.js 14 frontend. See `README.md` for full details.

### Services

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| Backend API | `uvicorn main:app --host 0.0.0.0 --port 8000` | 8000 | Python FastAPI. Requires `~/.local/bin` on PATH. |
| Frontend | `RAILWAY_API_BASE_URL=http://localhost:8000 npm run dev` | 3000 | Next.js. Run from `frontend/`. Set env var to use local backend. |

### Running services locally

- Start the backend first, then the frontend.
- Without `RAILWAY_API_BASE_URL=http://localhost:8000`, the frontend proxies to the production Railway API by default.
- No `HOMEFIT_PROXY_SECRET` is needed for local dev — the auth check is skipped when the env var is unset.
- Redis is optional; the backend falls back to in-memory caching if `REDIS_URL` is not set.
- Google Earth Engine (`GOOGLE_APPLICATION_CREDENTIALS_JSON`) is optional; satellite-based scoring is skipped if unavailable.
- `CENSUS_API_KEY` is strongly recommended for meaningful pillar scores; most pillars degrade without it.

### Lint / Test / Build

- **Frontend lint**: `npm run lint` (from `frontend/`)
- **Frontend build**: `npm run build` (from `frontend/`)
- **Backend unit tests**: `python3 -m pytest tests/test_radius_profiles.py tests/test_economic_security_pillar.py -v` (from repo root). Some test assertions are stale relative to current production code — pre-existing failures.
- **Live integration tests**: `test_built_beauty_golden_set.py` requires `RUN_LIVE_GOLDEN_BUILT_BEAUTY=1`. `test_coverage.py` requires a running backend. These hit external APIs and can be slow.

### Gotchas

- pip installs to `~/.local/bin` (user install). Ensure `export PATH="$HOME/.local/bin:$PATH"` is set before running `uvicorn` or `pytest`.
- Scoring a location takes 30-90 seconds due to real external API calls (OSM Overpass, Census, etc.).
- The frontend uses `package-lock.json` — use `npm` (not yarn/pnpm).
- Natural Beauty pillar scores 0 without Google Earth Engine credentials — this is expected.
