# HomeFit frontend (Next.js) for Railway. Build context is the repo root so the build can read ../data
# (the neighborhood pages and sitemap are generated from the catalog at build time).
#
# Railway: add the service variable RAILWAY_DOCKERFILE_PATH=frontend.Dockerfile, plus these variables.
# The three marked "build" are read while the app is built, so they must be set before the first deploy:
#   RAILWAY_API_BASE_URL   (build) URL of the API service; /api/catalog-map* is rewritten to it
#   NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY   (build, optional) sign-in
#   HOMEFIT_PROXY_SECRET   must equal the API's secret or scoring is rejected
#   HOMEFIT_DISABLE_SCORE  set to 1 to pause live scoring (shows a "coming soon" message)
#   UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN, GOOGLE_PLACES_API_KEY   optional
FROM node:20-slim

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci --no-audit --no-fund

COPY frontend frontend
# Catalog files needed at build time (kept out of the final server's runtime path; nothing serves them from here).
COPY data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl data/
COPY data/catalog_climate_profiles.jsonl data/catalog_housing_costs.json data/

ARG RAILWAY_API_BASE_URL
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV RAILWAY_API_BASE_URL=$RAILWAY_API_BASE_URL \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_TELEMETRY_DISABLED=1

RUN cd frontend && npm run build

ENV NODE_ENV=production
EXPOSE 3000
# Railway sets PORT at runtime.
CMD ["sh", "-c", "cd frontend && npx next start -H 0.0.0.0 -p ${PORT:-3000}"]
