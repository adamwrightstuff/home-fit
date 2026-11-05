# Natural beauty: two-part design proposal (2026-10-24)

Status: PROPOSAL. Nothing implemented, nothing committed. Scoring changes need explicit approval.

## What changes
Natural beauty becomes two named sub-scores, blended 50/50 by default (the scenery quiz tilts it per user):

- **Streets and greenery**: green view and tree canopy, same curves and same regional normalization as today, combined as 0.7 x better + 0.3 x worse.
- **Scenic setting**: terrain and water, same curves as today, combined 0.7 x better + 0.3 x worse.
- Landcover and biodiversity are dropped (0.95 correlated with each other, 0 to 3% of the weight today, no third-party test supports them).
- The blend is rescaled so the catalog mean and spread stay where they are today (mean 64.6, SD 18.9): new = 64.6 + (blend - 46.8) x 1.27, clamped 0 to 100. This is a presentation choice, not a measured quantity.

## Effect on the catalog (1,476 places, rescaled)
Average change by metro: Raleigh -7.5, Charlotte -3.8, Houston -3.1, Sacramento -2.9, Atlanta -2.7, San Antonio -2.2, Orlando -2.2, Philadelphia -2.1, Dallas -1.3, Chicago -1.2, Tampa -1.1, Boston -0.8, Las Vegas -0.3, Phoenix +0.1, Miami +0.1, Austin +1.1, NYC +1.9, Denver +1.9, LA +4.0, SF +4.2, Seattle +4.8 (5 places).
44% of places move more than 5 points, 9% more than 10. Biggest drops: Sandy Oaks 87 to 64, Franklinton 89 to 68, Blue Diamond 57 to 37, Wendell 84 to 65. Biggest rises: Ossining 82 to 100, Burlingame 82 to 100, Belmont 67 to 83, Juno Beach 84 to 98.

## Evidence (what each part was tested against)
| Part | Third-party test | Result |
|---|---|---|
| Streets (green view, canopy) | MIT Place Pulse 2.0 street-scene beauty ratings, 1,320 photos, 13 US cities | r about 0.37 to 0.38 each; both matter |
| Scenery: terrain | ScenicOrNot landscape ratings, 598 points in Great Britain | r 0.41 |
| Scenery: terrain | USDA Natural Amenities Scale topography, 126 counties | r 0.66 |
| Scenery: water | USDA Natural Amenities Scale water area | r 0.30 (weak); ScenicOrNot 0.18 (crude water measure) |
| Today's V9 formula | ScenicOrNot | r -0.06 (fails for landscapes) |
| Regional normalization | Place Pulse | no change in match (+0.005, 90% range -0.03 to +0.04) |
| Either part vs resident health (CDC PLACES) | tract fair/poor health, mental health, depression, controlling income, education, age, within metro | null once controlled; today's score is also null |

Published precedent: Seresinhe et al. 2015 and 2019 (Scientific Reports): scenic beauty predicts health and happiness beyond green land cover.

## What is judgment, not evidence (say so in the methodology)
1. The 50/50 blend. No dataset rates streets plus setting together; the health test was null.
2. Regional normalization of green view and canopy. Baselines have no traceable source (commit 776e778 cites none); Place Pulse shows it neither helps nor hurts matching; literature leans toward absolute greenery but nothing tests Phoenix against Raleigh. Kept for now because removing it drops Phoenix about 18 rank points and Las Vegas about 12 on indirect evidence.
3. Water: weakest measure, kept in scenery because it describes what you see, not what you do (Active Outdoors waterfront measures swimming and access).
4. The 0.7/0.3 combination within each part (carried over from today's strongest-feature-counts-most idea).
5. The rescale constants.

## Known gaps
- True desert (Phoenix, Las Vegas) has no human rating data. Neither Place Pulse nor ScenicOrNot covers it; the USDA test had only 3 desert counties. Plan: add a photo-rating question to the product to collect it.
- Place Pulse photos are 2007 to 2012; ScenicOrNot is Britain only; stored green view runs 2 to 3x the street-view literature baselines (instrument mismatch).
- Both canopy sources in gee_api.py are flagged deprecated by Google Earth Engine.

## Implementation checklist (if approved)
1. pillars/natural_beauty.py: add the two sub-scores and blend in `_apply_v9_formula`; keep `v9_breakdown` fields so stored data still reads; expose `streets_score`, `scenery_score`.
2. Mirror to the frontend TS scorer (see docs/LIVE_SCORER_VS_EXPLORER.md) and the explorer detail view.
3. Recompute the 21 metro files offline from stored component scores (no API calls), then `recompute_catalog_composites.py --in-place --no-census`.
4. Tests: formula, rescale bounds, preference tilt, regression on stored breakdowns.
5. Methodology copy with the judgment list above. Update memory and DESIGN_PRINCIPLES notes.
6. Show the final diff; commit and push only on explicit approval (pushes auto-deploy).
