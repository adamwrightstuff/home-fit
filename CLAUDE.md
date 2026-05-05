# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication

Answer in one sentence. Lead with the fix, not the explanation. No code snippets unless asked. No bullet points. No file names or function names unless asked. One cause, not a list of possibilities — trace the actual code path before responding. If something doesn't add up, say so directly and say what you'd need to verify.

## What This Is

HomeFit is a personalized livability scoring API that evaluates any location across 13 research-backed pillars (active outdoors, built beauty, natural beauty, neighborhood amenities, air travel, public transit, healthcare, education, housing value, economic security, climate risk, social fabric, diversity) to produce a weighted 0–100 score. Production backend runs on Railway; frontend on Vercel.

## Running Locally

```bash
# Backend
PYTHONPATH=. python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Tests
pytest tests/

# Score a location
curl "http://localhost:8000/score?location=Seattle,WA"
```

## Architecture

**Request flow:** geocode → cache check → parallel pillar collection (13 pillars via `ThreadPoolExecutor`) → composite indices (status_signal, happiness_index) → weight allocation → JSON response.

Set `HOMEFIT_PILLARS_SEQUENTIAL=true` to run pillars one-at-a-time (useful for rate-limit testing).

**Pillar structure:** each pillar in `pillars/` independently collects data from external APIs, detects area type (urban_core/suburban/exurban/rural), computes metrics, and applies research-backed scoring curves. No pillar has knowledge of others.

**Area-type adaptation** drives radii, thresholds, and expectations — there are no hardcoded city exceptions. If a scoring result seems off for a specific city, the fix is always in the area-type classification or the curve, never a special case.

**Google Places fallback** supplements sparse OSM data for three pillars when enabled via feature flags (`HOMEFIT_PLACES_FALLBACK_ENABLED`, `HOMEFIT_PLACES_AO_FALLBACK_ENABLED`, `HOMEFIT_PLACES_SF_FALLBACK_ENABLED`).

**Agent recommendations** (`POST /agent/recommend`): loads a pre-scored catalog JSONL, pre-ranks candidates, calls Claude (Haiku by default) for explanations, returns `results_url` links that hydrate the frontend without a fresh score run.

## Required API Keys

`SCHOOLDIGGER_APPID`/`APPKEY`, `GEOCITY_APPID`/`APPKEY`, `CENSUS_API_KEY`, `TRANSITLAND_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS_JSON` (GEE), `ANTHROPIC_API_KEY` (agent recommendations). Copy `.env.example` to `.env`.

## Key Feature Flags

`ENABLE_SCHOOL_SCORING` (default off — low free quota), `HOMEFIT_PILLARS_SEQUENTIAL` (default off), `HOMEFIT_CATALOG_CONTRIBUTIONS_ENABLED` (Supabase catalog aggregates, default off).

## Baselines & Normalization

Pre-computed JSON files in `data/` provide metro-specific and area-type-specific baselines for economic, status signal, stability, IRS engagement, voter turnout, and social fabric scoring. Rebuild them via scripts in `scripts/baselines/` when underlying data changes.

## Batch / Catalog Workflows

Scripts in `scripts/catalog/` handle batch scoring of place catalogs to JSONL, re-running failed pillars, rescoring single pillars, recomputing composites, and exporting CSVs. These are not production code — they're admin tools. See `scripts/README.md` for the full inventory.

## Design Rules (read before changing scoring logic)

`DESIGN_PRINCIPLES.md` is the authoritative checklist. The core constraint: expected values must come from empirical research, not target scores. Never add hardcoded city exceptions — use area-type classification instead.

## Commit Behavior

At the end of any session where you made changes: stage only files relevant to the current work (not `.venv`, `analysis/*.jsonl`, or other local artifacts), commit with a clear message, and push to `origin main`.
