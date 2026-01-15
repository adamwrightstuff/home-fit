---
name: Product Hunt Launch Hardening
overview: Make the UI fully public on Vercel while protecting the Railway API with a Vercel proxy, strong per-IP rate limits (Upstash), and disabling high-risk features (SSE + public admin endpoints) for launch week.
todos:
  - id: proxy-auth-backend
    content: Add proxy-secret auth for sensitive FastAPI routes; protect/disable admin endpoints
    status: completed
  - id: vercel-proxy-routes
    content: Add Next.js API route(s) that forward to Railway and attach secret header
    status: completed
  - id: rate-limit
    content: Implement per-IP rate limiting in Vercel middleware using Upstash Redis
    status: completed
  - id: disable-sse
    content: Disable `/score/stream` path for launch week; update UI to use non-streaming score call
    status: completed
  - id: gate-schooling
    content: Disable SchoolDigger by default and add premium gating/waitlist UX
    status: completed
  - id: batch-hard-cap
    content: Enforce server-side max batch size; remove client-controlled limit field from validation path
    status: completed
  - id: cors-tighten
    content: Restrict CORS to Vercel origins (or remove need via proxy-only access)
    status: completed
  - id: launch-ops
    content: Add lightweight metrics/logging + incident toggles via env
    status: completed
---

### Goals

- Keep the app **public-facing** (Product Hunt friendly) while making the backend **non-abusable** under sudden traffic.
- Avoid quota blowups (SchoolDigger / OSM / Nominatim / GEE) and prevent cheap DoS vectors.

### Key decisions (locked)

- **API exposure**: proxy through Vercel API routes (browser never calls Railway directly).
- **Rate limiting**: Vercel middleware + Upstash Redis.
- **Streaming**: disable SSE for launch week; use non-streaming `/score` only.

### Proposed request flow

```mermaid
sequenceDiagram
participant Browser
participant VercelUI
participant VercelAPI
participant Upstash
participant RailwayAPI

Browser->>VercelUI: Load public app
Browser->>VercelAPI: GET /api/score?location=...
VercelAPI->>Upstash: RateLimit(ip, route)
alt allowed
VercelAPI->>RailwayAPI: GET /score (adds X-HomeFit-Proxy-Secret)
RailwayAPI-->>VercelAPI: JSON score
VercelAPI-->>Browser: JSON score
else limited
VercelAPI-->>Browser: 429 + retryAfter
end
```

### Backend hardening on Railway (FastAPI)

- **Add a proxy-secret check** for sensitive routes so only Vercel can call them.
  - Apply to: `/score`, `/batch` (if kept), `/cache/clear`, `/cache/stats`, `/telemetry`.
  - Implement as a small dependency/middleware in [`/Users/adamwright/home-fit/main.py`](/Users/adamwright/home-fit/main.py).
- **Disable or protect admin/diagnostic endpoints** for launch week.
  - Today they’re open (e.g. `/cache/clear`, `/telemetry`).
- **Fix batch size validation**.
  - Current model lets the client supply `max_batch_size` (see `BatchLocationRequest` in [`/Users/adamwright/home-fit/main.py`](/Users/adamwright/home-fit/main.py)).
  - Enforce a server constant (e.g. `MAX_BATCH_SIZE = 10`) regardless of request body.
- **Gate schooling**.
  - Default `ENABLE_SCHOOL_SCORING = False` for launch week and require an explicit server-side “premium allow” flag/code.
  - This avoids SchoolDigger’s free-plan collapse.
- **Tighten CORS**.
  - Currently `allow_origins=["*"] `and `allow_credentials=True` (see [`/Users/adamwright/home-fit/main.py`](/Users/adamwright/home-fit/main.py)).
  - For proxy mode, CORS can be restricted to your Vercel domain(s) or removed for protected routes.

### Vercel proxy + rate limiting

- **Create Vercel API routes** (Next.js) that forward to Railway:
  - `/api/score` → Railway `/score`
  - (Optional later) `/api/batch` → Railway `/batch`
- **Store secrets in env**:
  - Vercel: `RAILWAY_API_BASE_URL`, `HOMEFIT_PROXY_SECRET`, Upstash credentials.
  - Railway: `HOMEFIT_PROXY_SECRET` (same value).
- **Add rate limiting in Vercel middleware**:
  - Per-IP limits by route (example targets for launch week):
    - `/api/score`: 10/min/IP with short burst, plus a tighter concurrent-inflight cap.
    - Block obvious bots via UA/ASN heuristics where possible.

### Frontend adjustments

- Update API calls in [`/Users/adamwright/home-fit/frontend/lib/api.ts`](/Users/adamwright/home-fit/frontend/lib/api.ts) to hit **`/api/score`** (same-origin) instead of `NEXT_PUBLIC_API_URL`.
- Remove/disable the SSE path in UI for launch week; keep the loading UX but drive it from a single `/api/score` call.
- Add “Premium waitlist” UX copy for schooling:
  - If `enable_schools=true` is requested, show a gated message and do not call the premium backend path.

### Observability + launch operations

- Add a minimal **request log** at the proxy layer (counts, latency, 429s, upstream errors), not full addresses.
- Define an incident playbook:
  - Flip switches via env: disable batch, disable premium, raise rate limits, or hard-block by IP.

### Pre-launch validation

- Load test at the proxy layer (light): confirm 429 behavior and that Railway is unreachable directly.
- Validate that `/cache/clear` and `/telemetry` are inaccessible without the proxy secret.

### Files likely touched

- Backend: [`/Users/adamwright/home-fit/main.py`](/Users/adamwright/home-fit/main.py)
- Frontend: [`/Users/adamwright/home-fit/frontend/lib/api.ts`](/Users/adamwright/home-fit/frontend/lib/api.ts)
- New in frontend (Vercel): `frontend/pages/api/score.ts` or `frontend/app/api/score/route.ts` (depending on your Next.js structure), plus `frontend/middleware.ts`.