# Docs Index

Documentation for the home-fit scoring backend and catalog. Start here.

## Scoring system — how it behaves & where it diverges
- **[LIVE_SCORER_VS_EXPLORER.md](LIVE_SCORER_VS_EXPLORER.md)** — why the same place can score
  differently in the live API vs the catalog Explorer (design vs drift). Read this first when a
  score "doesn't match."
- **[CATALOG_RESCORE_RUNBOOK.md](CATALOG_RESCORE_RUNBOOK.md)** — the offline rescores layered on
  the catalog, their `_rescore_version` audit tags, and the **re-apply order after a rebuild**.
  These aren't in the build; a rebuild drops them.
- **[PILLAR_DATA_QUALITY.md](PILLAR_DATA_QUALITY.md)** — per-pillar register of known bugs,
  coverage gaps, and saturation (what's fixed, open, or by-design).

## Pillar deep-dives (full scoring flow)
- **[PILLAR_TRANSIT.md](PILLAR_TRANSIT.md)** — public transit access: supply split (subway vs
  commuter), v3 absolute model, and the ridership-weighted commuter-access floor.
- **[PILLAR_ECONOMIC_SECURITY.md](PILLAR_ECONOMIC_SECURITY.md)** — reachable job-market
  (LODES gravity) + market quality; why it excludes resident outcomes.
- **[PILLAR_NATURAL_BEAUTY.md](PILLAR_NATURAL_BEAUTY.md)** — V9 ordered-weighted-average +
  the scenery-preference lead-slot mechanism (Python + TS mirror).
- **[PILLAR_AIR_TRAVEL.md](PILLAR_AIR_TRAVEL.md)** — drive-time bands to the best hub
  (fixed the everything-scores-100 saturation).
- **[PILLAR_DIVERSITY.md](PILLAR_DIVERSITY.md)** — entropy across race/income/age; the
  tract geo-fallback fabricated-0 bug.
- **[PILLAR_COMMUNITY_SAFETY.md](PILLAR_COMMUNITY_SAFETY.md)** — FBI CDE crime rates,
  area-relative scoring, and the COMING_SOON coverage gap (null ≠ unsafe).
- **[PILLAR_BUILT_BEAUTY.md](PILLAR_BUILT_BEAUTY.md)** — architectural diversity + historic
  coherence; the coverage-0 fabricated-floor issue and pending backfill.
- **[PILLAR_HEALTHCARE_ACCESS.md](PILLAR_HEALTHCARE_ACCESS.md)** — facility count + proximity; saturates at the ceiling in dense metros.
- **[PILLAR_QUALITY_EDUCATION.md](PILLAR_QUALITY_EDUCATION.md)** — nearby school ratings; the schools-gating Live-vs-Explorer divergence.

## Pillar references (data sources & methodology)
- [economic_security_pillar_data_reference.md](economic_security_pillar_data_reference.md)
- [beauty_area_type_reference.md](beauty_area_type_reference.md)
- [SOCIAL_FABRIC_PRD.md](SOCIAL_FABRIC_PRD.md)
- [HOMEFIT_LONGEVITY_IMPLEMENTATION_PLAN.md](HOMEFIT_LONGEVITY_IMPLEMENTATION_PLAN.md) ·
  [LONGEVITY_PRD_ERRATA.md](LONGEVITY_PRD_ERRATA.md)
- [pillar_details_show_spec.md](pillar_details_show_spec.md) — UI spec for pillar detail display
- [scope_active_outdoors_places_augmentation.md](scope_active_outdoors_places_augmentation.md)

## Ops
- [DEPLOYMENT.md](DEPLOYMENT.md) — deploy (backend → Railway from `main`)
- [ADMIN_TOOLS.md](ADMIN_TOOLS.md)
- [CLEANUP_CHECKLIST.md](CLEANUP_CHECKLIST.md)

## Conventions worth knowing
- **Weights** must sum to 100 over a place's *scored* pillars (non-null score, excluding
  `political_lean`). Any reweight renormalizes over scored pillars only.
- **Coarse-geo fingerprint:** identical pillar values across places in *different counties*
  usually means a CBSA/county fetch applied as if per-place — fix with a tract-level fetch.
- **Live transit fetch is noisy** — don't trust a single-pass re-fetch as ground truth.
- The clean cure for catalog↔live drift is a **faithful rebuild through `main.py`**, not more
  offline rescores.
