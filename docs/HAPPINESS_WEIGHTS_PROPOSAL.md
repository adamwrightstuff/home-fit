# Happiness Index weights (APPLIED, index version 5)

Status: applied October 2026. `pillars/happiness_index.py` now uses these weights, the callers pass economic opportunity, climate risk and active outdoors, the economic modifier on social fabric is removed, and the catalog was recomputed offline with `scripts/catalog/recompute_happiness_only.py`. Pillars stored as failed (score 0, confidence 0) now drop out and renormalize instead of counting as a real zero. Full evidence, links and our own test results are in `HAPPINESS_EVIDENCE_NOTES.md`.

## Why change anything

The current weights (S .30, F .20, C .15, N .05, H .10, G .12, E .08) were tuned against county-level CDC PLACES mental distress (R² 0.305). The v2 commute calibration showed county fits are confounded by wealth and place type, so those weights are not evidence. This proposal keeps a pillar only where individual-level research and our own catalog check agree, and gives zero where there is no support. Weights remain judgment: no study can say what share a pillar deserves.

## Proposed weights (sum 100%)

| Pillar | Today | Proposed | Basis |
|---|---|---|---|
| Social fabric | 30% | 26% | Strong research (Harvard study, Helliwell); stable in catalog check for 2 of 3 outcomes |
| Community safety | 20% | 18% | Strongest in our catalog check (all 3 outcomes); research mixed on life satisfaction, clearer on trust |
| Housing cost burden and space | 10% | 14% | Cost burden raises depression, mostly for renters, so renter and owner burden (Census) should be the main input, with space per person secondary; stable for 2 outcomes |
| Natural beauty | 12% | 12% | Moving to greener areas improved mental health; stable for 2 outcomes |
| Economic opportunity | modifier only | 8% | Measures reachable jobs and market quality; individual-level unemployment and income evidence is indirect; catalog sign unstable |
| Active outdoors | 0% | 7% | Exercise treats depression; 120+ min/week in nature; catalog check held for only 1 outcome |
| Climate and air (heat, air quality, flood, trend) | 0% | 6% | PM2.5 lowers life satisfaction; heat raises mental-health ER visits; catalog sign unstable. Noise is NOT included: we have no noise data, so it is a future addition only |
| Commute time | 15% | 5% | Small mood/leisure cost, no general life-satisfaction effect in careful panels; also a personal score, so may move to a user setting |
| Daily amenities | 5% | 4% | Walkability raises walking; no wellbeing outcome found |
| Healthcare access | 0% | 0% | Links to self-rated health only; no catalog support |
| Schools | 8% | 0% | Schooling has no causal effect on life satisfaction; no school-quality study; treat as a family setting |
| Diversity | 0% | 0% | No link to trust in large British study |
| Air travel access | 0% | 0% | No wellbeing evidence; noise under flight paths lowers wellbeing |
| Built environment, political lean, status signal | 0% | 0% | No evidence or not a residential pillar |
| Social proximity, commute time (personal) | n/a | user setting | Depend on the user's own people and workplace, so they cannot be general weights |

## Rules used

1. Keep a pillar only where individual-level studies and our own catalog check do not contradict each other.
2. Where the catalog check contradicts individual-level evidence (schools, transit, amenities, air travel), treat the catalog result as affluence or urban-density confounding and do not use it.
3. Where the research is strong but the catalog is unstable (economic opportunity, climate, active outdoors), give a modest weight.

## Judgment calls to review

- Economic opportunity at 8% is a judgment; the pillar measures a place's job market, not an individual's job security. The old modifier that scaled social fabric by 0.85-1.15 would be removed, since it had no evidence.
- Active outdoors and natural beauty overlap in the data they read, but they measure different things (doing things outdoors versus scenery) and both have their own evidence. DECISION: keep them separate.
- Safety is held near 18% because our own data ranks it first, even though research on life satisfaction is mixed.
- Commute at 5% only reflects the small mood cost; consider removing it from the general index and keeping it as a personal setting.

## Implementation notes (not done)

- `pillars/happiness_index.py` takes seven pillars; adding economic opportunity, climate risk and active outdoors means extending its signature and the callers in `main.py` and the catalog scripts.
- Pillar scores are already stored in the catalog JSONL files, so recomputing is an offline job (`scripts/catalog/recompute_catalog_composites.py`), not an API rescore.
- Remove or reword the "R²=0.305 vs CDC PLACES" claim in the index docstring.
- Run the catalog health check afterwards to see how many places move and by how much.

## Revision log

- Rev 3: folded in two ideas from an outside proposal: noise as a possible future addition to climate and air (we have no noise data, so nothing is weighted for it now), and renter and owner cost burden as the main housing input. Rejected from it: dropping nature, and a 15% weight for daily friction (commute and walkable amenities have weak individual-level support).
- Rev 1: first draft from literature only (education 3%, healthcare 3%, economic 12%).
- Rev 2: added our own catalog-versus-PLACES check; economic cut to 8% because the pillar measures job-market opportunity; education and healthcare set to 0; safety raised to 18%; commute and social proximity treated as personal settings.

- Rev 4 (applied): keep active outdoors and natural beauty separate; frontend client-side formula (`frontend/lib/pillars.ts`) updated to mirror the backend v5 weights, verified identical on all 411 catalog rows.
