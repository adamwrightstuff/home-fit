# HomeFit deployment

Single reference for backend (Railway) and frontend (Vercel or alternatives). Environment variable for the browser-facing app: **`NEXT_PUBLIC_API_URL`** → your production API base (e.g. `https://home-fit-production.up.railway.app`).

---

## Backend API (Railway)

### GitHub push → Railway

Every push to `main` can trigger a Railway deploy for the backend API:

**A. Connect GitHub in Railway (recommended)**

1. Railway dashboard → your **project** → **Service** running `uvicorn main:app`.
2. **Settings** → **Source** / **GitHub** → **Connect repo**, branch `main`.

**B. GitHub Actions**

This repo may include `.github/workflows/railway-deploy.yml` using `railway up` on push to `main`. Configure a GitHub secret **`RAILWAY_TOKEN`** (and optionally **`RAILWAY_SERVICE_ID`** for multi-service projects).

### Dockerfile and `python3: command not found`

The repo has a **root `Dockerfile`**. Railway should build from it automatically. If logs show `python3: command not found`, trigger a **Redeploy** so the image rebuilds. If the service **Root Directory** points at a subfolder, set it to the repo root so the Dockerfile is visible.

### NRHP dataset (historic register)

- `scripts/baselines/build_nrhp_db.py` builds `data_cache/nrhp.sqlite`.
- `railway.json` can run the NRHP build during deploy; see that file for the exact build command.
- Override path with env **`NRHP_DB_PATH`** if needed.

### Logs

- Railway dashboard → project → API **service** → **Deployments** (build) / **View** / **Logs** (runtime).

---

## Frontend

### Vercel (recommended)

**Dashboard (one-time)**

1. [vercel.com](https://vercel.com) → Add New Project → import this repo.
2. **Root Directory**: `frontend`
3. **Environment variable**: `NEXT_PUBLIC_API_URL` = your Railway API URL.
4. Deploy; later pushes to the connected branch redeploy automatically.

**CLI (token-based, no browser)**

1. Create a token: [vercel.com/account/tokens](https://vercel.com/account/tokens)
2. Deploy:
   ```bash
   cd frontend
   vercel --token YOUR_TOKEN_HERE --yes
   vercel env add NEXT_PUBLIC_API_URL production
   # When prompted, enter your API base URL
   ```

**Quick script from repo root** (interactive `vercel login`):

```bash
cd frontend && vercel login && vercel --prod
```

Set **Root Directory** to `frontend` and **`NEXT_PUBLIC_API_URL`** when linking the project.

### Railway (frontend on same platform as API)

```bash
npm i -g @railway/cli
railway login
cd frontend
railway init
railway variables set NEXT_PUBLIC_API_URL=https://home-fit-production.up.railway.app
railway up
```

Configure build/start per Railway UI if needed (`npm run build` / `npm start`).

### Netlify

- Base directory: `frontend`
- Build: `npm run build`
- Publish: `frontend/.next` (or per Netlify Next.js docs)
- Env: `NEXT_PUBLIC_API_URL`

### Self-hosted (Docker)

Example pattern: multi-stage Node build, `output: 'standalone'` in `next.config` if required. Set `NEXT_PUBLIC_API_URL` at run time. See `frontend/` for `package.json` scripts.

---

## Environment variables

| Where | Variable | Purpose |
|-------|----------|---------|
| Frontend | `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend |

---

## Viewing logs

- **Vercel**: Project → **Deployments** (build) / **Logs** (runtime, e.g. `/api/score` proxy).
- **Railway**: As above for the API service.

---

## Smoke test after deploy

1. Search for a location in the UI.
2. Confirm scores load; try priorities and optional flags (chains, schools) as you use in production.

---

## Troubleshooting (frontend)

- **Build fails**: Run `npm run build` locally in `frontend/`.
- **API errors**: Check `NEXT_PUBLIC_API_URL`, CORS, and that the Railway API is up.
- **Styles**: Confirm Tailwind and `globals.css` in `layout.tsx`.


## Catalog served by the API (since 2026-11-24)

The ~111 MB catalog is no longer bundled into the Vercel frontend. `catalog_api.py` serves it from the API:

- `GET /catalog/list` returns the slimmed list of every live-metro place (what `/api/catalog-map?metro=all` used to return). It is built at image build time by `scripts/catalog/build_catalog_list.py` into `data_cache/catalog_list.json` and `.json.gz` (about 18 MB, 1.9 MB gzipped) and served as a static file; if the build step did not run, the first request builds it.
- `GET /catalog/place?metro=nyc&key=<name>|<county>|<state>` returns the full detail for one place.
- The frontend keeps calling `/api/catalog-map/all` and `/api/catalog-map?metro=X&key=Y`; `frontend/next.config.js` rewrites them to the API using `RAILWAY_API_BASE_URL` (falling back to `NEXT_PUBLIC_API_URL`). **That variable must be set for the Vercel build, not only at runtime**, because rewrites are resolved when the app is built.
- The API image needs the catalog files: `data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl`, `data/catalog_climate_profiles.jsonl`, `data/catalog_housing_costs.json` and `data/metro_registry.json`. When the catalog changes, redeploy the API so the list is rebuilt.
- The slimming rules (heavy per-pillar detail, and key names nothing in the frontend reads) live in `catalog_api.py` (`UNUSED_KEYS`, `KEEP_PATHS`). Before adding a read of one of those names in a list-level view, remove it from `UNUSED_KEYS`.
- Static neighborhood pages and the sitemap still read the catalog at build time (`frontend/vercel.json` copies it into `frontend/data` before `next build`), but no deployed server function bundles it.
