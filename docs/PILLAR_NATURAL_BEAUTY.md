# Pillar Deep-Dive: Natural Beauty

How `pillars/natural_beauty.py` scores a location today: the two-part model (2026-10) plus the scenery preference.
Evidence, judgment calls and open gaps are in `analysis/natural_beauty_two_part_proposal_2026-10-24.md` (local file).

## What it measures
Two kinds of beauty, scored separately and then blended:

- **Streets and greenery**: tree canopy and eye-level green view around the pin.
- **Scenic setting**: terrain (relief, slope, ruggedness) and nearby water.

Landcover and biodiversity are still computed and stored in `details.v9_breakdown`, but they are not scored
(0.95 correlated with each other, no third-party test supports them).

## Model
Per-dimension scores (`gvi_score`, `canopy_score`, `topo_score`, `water_score`) are unchanged curves of the raw
inputs. Green view and canopy are normalized against a regional median first (see judgment calls below).

```
streets = 0.7 x stronger(gvi, canopy) + 0.3 x weaker(gvi, canopy)
scenery = 0.7 x stronger(topo, water) + 0.3 x weaker(topo, water)
blend   = streets_share x streets + (1 - streets_share) x scenery        # streets_share = 0.5 with no preference
score   = quantile map of blend onto the old V9 score distribution       # data/natural_beauty_two_part_scale.json
```

`nb_two_part()` returns `streets`, `scenery`, `blend`, `score`, `streets_share`. The stored breakdown carries
`method = "two_part_v10"`, `streets_score`, `scenery_score`, `blend_raw`.

### Versioning
`details.scoring_formula` is `"v10"` (constant `NATURAL_BEAUTY_SCORING_FORMULA`; `"v9"` was the six-component OWA, `"v7"` the legacy path
when `ENABLE_NATURAL_BEAUTY_V9` is off, a flag name kept for compatibility). `check_catalog_health.py` treats v10 as current and flags v9 as an
old version. Older NYC and LA rows also keep the stamp at the pillar root; the offline recompute updates both.

### Score scale
The blend runs lower than the old six-component score (mean 47 vs 65), so each blend value is mapped to the old-score
value at the same percentile of the catalog (21 metros, 1,476 places). This keeps the catalog mean and spread (64.6 and
18.9), has no cap and no invented constants. It is a calibration to the previous score, **not evidence about beauty**, and
it is relative to the catalog it was built from. Rebuild with `scripts/baselines/build_natural_beauty_two_part_scale.py`
only when the catalog changes materially. The same table is generated into `frontend/lib/nbTwoPartScale.ts`.

### Missing data (fail loud, shipped 2026-10-26)
A part (streets, scenery) is available if at least one of its two components was measured. The pillar needs both
parts; otherwise `NaturalBeautyNoData` is raised, the pillar shows no data and drops out of the headline with its
weight redistributed. One missing component inside an available part is scored from the other and marked degraded
(`canopy_unavailable`, `green_view_unavailable`, `green_view_fallback`, `topography_unavailable`,
`water_read_unavailable`). Water has three states: `measured`, `none_within_15km` (the read succeeded and found
nothing; scored at the curve floor of 3.0) and `unavailable` (the read failed; no water score). No neutral or zero
value is ever substituted.

## Scenery preference
The preference tilts the blend toward one part instead of forcing a component into a lead slot:

| preference | favors | streets share |
|---|---|---|
| `canopy` | streets | 0.75 |
| `mountains`, `ocean`, `lakes_rivers` | scenery | 0.25 |
| none, or picks from both sides | neither | 0.5 (picks average out) |

An `ocean` or `lakes_rivers` pick that does not match the place's water type cuts its water score to a quarter.

### `v9_score_from_components`
Recomputes the score from the stored component scores (preference-independent) and applies any preference. Used by the
serving fast-path so the served score is always correct regardless of what was cached.

## Where the preference is applied (served, not stored)
The neutral score is stored. The preference is applied at serve time in three mirrored places:
- **Live API:** `nb_two_part` inside the pillar, and the catalog/cache fast-path in `main.py`.
- **Explorer:** `applyNbPreferencesV9` in `frontend/lib/nbPreference.ts`.
- **Catalog filters:** `apply_nb_preferences_v9` in `scripts/catalog/apply_preference_filters.py`.

**Three implementations to keep in sync** if the math changes (`tests/test_natural_beauty_two_part.py` checks the
Python pair).

## Evidence (what each part was tested against)
| Part | Third-party test | Result |
|---|---|---|
| Streets | MIT Place Pulse 2.0 street ratings, 1,320 photos, 13 US cities | r about 0.37 to 0.38 |
| Scenery: terrain | ScenicOrNot landscape ratings, 598 points in Great Britain | r 0.41 (Scotland 0.53, Wales 0.29, England 0.16) |
| Scenery: terrain | USDA Natural Amenities Scale topography, 126 counties | r 0.66 |
| Scenery: water | USDA scale water area / ScenicOrNot | r 0.30 / 0.18 (weakest measure) |
| Old six-component score | ScenicOrNot | r -0.06 |

## Judgment calls (not evidence; say so in any methodology)
1. The 50/50 blend, and the 0.75 / 0.25 preference tilt.
2. The 0.7 / 0.3 pairing inside each part (rank order is stable across 0.6 to 0.8).
3. Regional normalization of green view and canopy: the baselines in `_NB_REGIONAL_BASELINES` have no traceable source and
   showed no effect on matching Place Pulse. **Kept by owner decision 2026-10-27 as an unsourced judgment** (design
   principles v2, P1 and P4: a peer-norm choice with no tier 1 to 3 evidence). Dropping it would move scores a mean of
   5.9 points (p95 17, max 34.7; Phoenix -19.9, Las Vegas -11.7, Denver -10.0, Seattle +14.0, Orlando +7.5), and
   nothing can check the desert cases because no human rating covers them. Revisit when desert ratings exist.
4. Water as part of scenery (it describes what you see; Active Outdoors waterfront covers what you do).
5. The percentile scale (calibration to the old score).

## Spec sheet (design principles v2, filled 2026-10-27)

```
Pillar: natural_beauty
Construct (one sentence): How beautiful the surroundings look, from the greenery seen along streets and from
  the landscape setting (terrain and water), as a perceptual score, not access to nature (Active Outdoors) and
  not a built-environment score.
Reference frame: mixed. Terrain and water are an absolute national scale. Green view and canopy are scored
  against a regional median (area-type-style peer norm by US region), then mapped onto the old catalog
  distribution by percentile.
  Evidence for the frame: tier 1 supports a shared absolute scale for landscape preference (cross-cultural
  agreement r 0.76 to 0.89, draft Part 4). There is no tier 1 to 3 evidence for the regional peer norm
  (Place Pulse test: +0.005 with or without it). The peer norm is an owner-approved judgment (2026-10-27).
Measurement area: pin + radius, per input (green view 1.2 km, canopy 0.4/1/2 km weighted 0.5/0.35/0.15,
  terrain 5 km, water nearest body within 15 km).
  Reason: perceptual, so a viewing area, not a walk-time. The radii are carried over from earlier versions; no
  recorded source for any of them (P3 open). Area type reaches the score only here: the primary canopy read radius
  is 800 m (urban residential/historic), 1,000 m (urban core, or neighborhood scope) or 2,000 m (suburban,
  exurban, rural) via `radius_profiles`, and an urban-core place with low canopy widens to 2 to 3 km. That is a
  step at category boundaries; everything else in the score (curves, regional baselines by region box, terrain,
  water, blend) uses no area type. To retire area type, replace the step with a continuous place-context
  factor or one fixed radius, tested as a P3/P6 change. Canopy radius is a minor driver (swapping to a single radius moves
  scores 0.8 to 1.6 points on average, p95 2.5 to 4.9).
Inputs and data sources (with vintage): GEE canopy (both sources flagged deprecated by Google), GEE green view
  (semantic GVI, NDVI fallback), terrain relief from elevation data, OSM water features (Overpass), NYC tree
  census and OSM street trees (green view boost). Place Pulse photos used for testing are 2007 to 2012.
Parameters: see table below.
Shared inputs with other pillars: water and parks are also read by Active Outdoors (different construct: what
  you see vs what you do). Overlap tested 2026-10-28 on 1,475 stored places (Spearman): natural beauty total vs
  Active Outdoors total 0.17; water score vs Active Outdoors waterfront 0.49 (the real overlap: both read the
  nearest water); terrain vs wild adventure 0.28; streets vs daily urban outdoors -0.04. Within the pillar, green
  view vs canopy score 0.71 and streets vs green-view-only streets 0.92, so canopy adds little beyond green view
  (the 0.7/0.3 pairing already down-weights the weaker). Overlap is documented, not removed; no score changes. Green view and canopy share satellite canopy/NDVI inputs
  (handled by the 0.7/0.3 pairing, not tested). No overlap found with Climate Risk.
Pin-shift sensitivity: RUN 2026-10-28 (live, 12 places across area types, shifted north and east, scored in the
  same run as the unshifted pin; `scripts/qa/natural_beauty_pin_shift.py`, results in
  `analysis/natural_beauty_pin_shift_results.json`). 250 m: n=24, median 1.2, p95 4.5, max 9.3 (passes the 5-point
  gate; 250 m is the P6 test distance for this pillar, owner decision 2026-10-29: it matches realistic pin error, while
  500 m lands in a different part of the neighborhood and mixes in real scenery change). 500 m: n=24, median 2.6, p95 20.2, max 27.3 (reported, not the gate; its one real defect is the water type flipping river to ocean at Midtown, a known limit). Largest 500 m moves: Midtown NYC east
  +27.3, Southport north +20.2, Andersonville north +8.6. Diagnosed 2026-10-28 (`scripts/qa/natural_beauty_pin_shift_diagnose.py`): Midtown east 500 m is the
  nearest-water type flipping from river (score 16.6) to ocean (79.8), scenery 23.7 to 63.9, green view
  unchanged; Southport north is real change in measured green view (15.0, 23.4, 32.4% at 0, 250, 500 m) and
  canopy (3.7, 6.7, 9.9%) through a steep part of the green view curve (15 to 25%: 3.5 points per point). So the
  500 m failure comes from a step in water classification and from the green view curve's slope over real
  spatial variation, not from noise. Small sample, and some reads hit Earth Engine and USFS timeouts, so treat
  as indicative. The 4 NYC places that read 5 to 12 points lower live than stored were a test-harness omission,
  not a live/catalog divergence: the NYC street-tree census boost (+11 to +16 points of green view) only runs
  when a city name containing New York, NYC or Brooklyn is passed, and the harness passed none; the stored rows
  all carry the boost.
  Water pilot 2026-10-29 (11 live reads, `scripts/qa/natural_beauty_water_pilot.py`; a first run had 5 transient
  water-read failures that did not reproduce, so the second run is the valid one): scoring the best water type
  within reach (flag `NB_WATER_BEST_TYPE`, off) removes the Midtown pin-shift flip (25.8 base vs 60.9 at 500 m east
  becomes 48.0 vs 49.9) but works by making Manhattan count as ocean; Midtown East already scores 69.4 live under
  the current rule because OSM tags the East River bank as coastline. Other effects: The Woodlands 79.1 to 90.0,
  Culver City 61.3 to 76.4, Loomis 78.5 to 84.8, Bel Air 92.5 to 95.4; ocean-nearest places unchanged. Not
  adopted: whether a tidal strait is "ocean" is unresolved. The 192 stored water-unavailable places read cleanly
  when re-read (Midtown East 32.4 to 69.4, Maspeth 38.5 to 48.2, Culver City 62.7 to 61.3), so a re-read of those
  192 under the current rule is the larger effect.
  DONE 2026-10-29 (`scripts/catalog/reread_natural_beauty_water.py`, Overpass only): water re-read for the 192
  water-unavailable places in the private server's states (NYC 37, Philadelphia 74, SF 51, LA 29, Seattle 1),
  rescored from stored GEE reads (164 new-shape from stored inputs, which now also carry the fresh water fields and
  reproduce; 28 older-shape from stored per-dimension scores), composites recomputed. Mean +0.34, range -13.8
  (Hollywood) to +36.3, 18 places moved more than 10; degraded flags for these cleared (health check: 0 degraded
  in NYC, SF, Philadelphia, Seattle; LA keeps 1, San Fernando no data). Backups in
  `data/backups_nb_water_reread_2026-10-29/` and `..._sync_2026-10-29/`. 53 places in Denver, Phoenix and Las Vegas
  stay water-unavailable: the private server lacks CO, AZ and NV and returns an empty result there, which would
  score as "no water", so they must not be read through it. Offline proxy: neighbouring catalog places in
  the same metro differ by a median 5.4 points within 0.5 mi (n=50) and 8.7 within 1.5 mi (n=795); this includes
  real differences between places, so it is an upper bound.
Independent validation source and result: partial, none at the 0.7 gate. Streets vs Place Pulse r 0.37;
  terrain vs ScenicOrNot (Britain) 0.41 and vs USDA Natural Amenities topography 0.66; water vs USDA 0.30.
  The blended score has no validation; deserts have no rating data. (P7 open.)
All-places check (date, n, summary): 2026-10-24 two-part rebuild and 2026-10-26 fail-loud rewrite, both across all
  1,476 stored places with per-metro deltas (fail-loud: 220 scores changed, 191 water-flagged places +5.1 mean,
  San Fernando no data).
Fail-loud conditions: see Missing data above. Rejected: both streets inputs missing, both scenery inputs
  missing. Flagged degraded: one component missing, composite-fallback green view, failed water read.
Launch check pairs: two pre-registered natural beauty contrasts in data/launch_check_contrasts.json, passing.
  Spread is forced by the percentile scale, so the spread check tests little.
Known data limits (returned in `data_quality.data_limits` on every live response since 2026-10-29, constant `NATURAL_BEAUTY_DATA_LIMITS`; not added to stored catalog rows): Place Pulse photos 2007 to 2012; ScenicOrNot is Britain only and mostly rural; satellite green
  view reads 2 to 3 times above street-view literature; 238 older-shape NYC/LA places store no confidence;
  deserts and the final blend unvalidated; GEE canopy sources deprecated. Pillar confidence is a field-presence
  completeness measure (flat 89 for all 1,235 new-shape places) and does not drop for degraded places; the
  degraded flag and `degraded_reasons` in `data_quality` are the disclosure (owner decision 2026-10-27, capping
  would need an unsourced number). Do not read confidence as a measure of natural beauty data quality.
Last re-validated: 2026-10-28 first scheduled pass (see Re-validation below): natural beauty tests pass,
  TS mirror matches, health check on all 21 metros clean except 238 older-shape NYC/LA places rated "poor"
  quality tier (no stored confidence, known) and 192 degraded (known water flags), launch check shows 0 natural
  beauty FAILs (1 FAIL overall, healthcare, known). No validation against an independent source has ever been
  run on the blended score.
```

### Re-validation (P12)
Rule from design principles v2: when a source changes, or quarterly, whichever comes first. Next due 2027-01-27.
Each pass:
1. Run `tests/test_natural_beauty_fail_loud.py` and `tests/test_natural_beauty_two_part.py`.
2. Check the TypeScript mirror against Python: the constants in `frontend/lib/nbPreference.ts` (`PART_LEAD` 0.7,
   `BLEND_TILT_STREETS` 0.75, water mismatch factor 0.25) and that `frontend/lib/nbTwoPartScale.ts` equals
   `data/natural_beauty_two_part_scale.json`. Checked 2026-10-27: all match. The mirror covers only the blend,
   preference and scale; green view, canopy and the regional normalization run in Python and reach the Explorer as
   stored scores.
3. Run `check_catalog_health.py --no-unversioned` on all metros and `scripts/qa/launch_check.py`; read the natural
   beauty rows.
4. Recompute stored scores from stored components and confirm they reproduce (0 mismatches expected).
5. Source triggers: either GEE canopy source is retired or replaced; the Place Pulse or ScenicOrNot test sets are
   refreshed; the catalog changes materially (rebuild the percentile scale only then).

### Parameters (P4): source, plausible range, sensitivity

Source column: "none" means a number with no source, a TODO under P4. "Evidence" means a test in this repo, not a
citation. Ranges are what the existing sensitivity runs covered, not evidence-derived plausible ranges.

| Parameter | Value | Source | Range tested | Sensitivity |
|---|---|---|---|---|
| Within-part lead weight (`_V9_PART_LEAD`) | 0.7 stronger, 0.3 weaker | none (judgment) | 0.5 to 1.0 | 0.6 or 0.8: mean 4 pts (p95 7 to 8, max 10); 0.5 or 1.0: 8.5 to 10.4 (max 20 to 21). Rank correlation 0.89 to 0.99 |
| Streets vs scenery blend (`_V9_BLEND_NEUTRAL`) | 0.5 | none (judgment) | 0.3 to 0.7 | 0.4 or 0.6: mean 5 pts (p95 9 to 10, max 13); 0.3 or 0.7: 9 to 10 (p95 16 to 20, max 22 to 25). Rank correlation 0.89 to 0.98 |
| Preference tilt (`_V9_BLEND_TILT_STREETS`) | 0.75 streets for canopy, 0.25 for scenery picks | none (judgment) | not tested | Serve-time only; not in stored scores |
| Water mismatch penalty | water x 0.25 when an ocean or lakes pick does not match | none (judgment) | not tested | Serve-time only |
| Green view curve (`_v9_score_gvi`) | breakpoints 5/15/25/40/50 %, plateau from 50 % | none | not tested | 34% of places (505) score 95+ on green view |
| Canopy curve (`_v9_score_canopy`) | breakpoints 5/15/25/40/60 % | none | not tested | |
| Terrain curve (`_v9_score_topo`) | breakpoints 2/5/10 on raw relief score | none for the curve; the input has evidence (USDA 0.66, ScenicOrNot 0.41) | not tested | |
| Water curve (`_v9_score_water`) | ocean max 100 decay 0.20/km; lake 70 / 0.30; river 40 / 0.35; floor 3.0 | none (code comment cites "blue-space wellbeing literature", no citation) | not tested | Water is the weakest measure (USDA 0.30) and leads scenery in 769 of 1,476 places |
| Regional baselines (`_NB_REGIONAL_BASELINES`) | gvi/canopy medians for 12 regions plus a fallback (e.g. Pacific NW 33/40, southwest arid 8/9, northeast 26/32) | none traceable (comment names Treepedia, NLCD and "literature", no per-number source) | on / off | Off: mean 5.9 pts, p95 17, max 34.7, Spearman 0.906 against current. Pipeline canopy medians run 2 to 3 times below the baselines in most regions, so "regional average" is not average in this data |
| Global references (`_V9_GVI_GLOBAL_REF`, `_V9_CANOPY_GLOBAL_REF`) | 20 % green view, 24 % canopy | none ("national urban median") | not tested | |
| Region boxes and California polygon | 12 hand-drawn boxes plus an outline | none (geometry choice; fixed for Las Vegas 2026-10-22) | not tested | A region boundary change moves places across baselines |
| Street-tree boost | min(20, log1p(count / 500) x 8) percentage points of green view, capped at 50 % | none (judgment) | not tested | Adds up to 20 points of green view in 94 places |
| Visible-green-fraction floor | 0.85 x visible green fraction, applied when more than 2x green view and above 5 % | none (judgment) | not tested | Fires in 379 places (26%) |
| Percentile scale | 101-point quantile table mapping the blend onto the old V9 distribution | calibration to the previous score, not evidence | rebuild only on a material catalog change | Fixes catalog mean (64.6) and SD (18.9) by construction; a new place is scored against this catalog's distribution |
| Water none-within-15 km floor | 3.0 | the curve's own floor | not tested | Applies when the read succeeded and found nothing |

### Sourcing pass (2026-10-28, five web searches, read from search summaries only, papers not opened)

Verdicts: **shape supported** means published evidence agrees with the form of the parameter; no value is fitted
from it, so the number itself stays a judgment with its tested range. **No source** means nothing usable was found.

| Parameter | What the search found | Verdict |
|---|---|---|
| Water curve ordering and shape | Elliott et al. 2020 (Landscape and Urban Planning 198, 18-country BlueHealth survey): visit likelihood falls exponentially with distance, and people travel further to coast (up to about 50 km) than lakes (about 5 km) or rivers (about 2.5 km). A 2024 Belfast price study (4,985 sales) reports premiums for coast (about 7.3%) and lakes (about 5.3%) and a discount near large rivers (about 3.8%), with distance decay | Shape and ocean > lake > river ordering supported. Decay constants (0.20, 0.30, 0.35 per km) and maxima (100, 70, 40) have no fit; the survey measures visits and the Belfast study prices, not beauty ratings. Our 3.5, 2.3 and 2.0 km half-distances do not match 50, 5 and 2.5 km travel distances |
| Canopy curve (5/15/25/40/60 %) | American Forests dropped its universal 40% goal in 2017; its older land-use goals were 15% city center, 25% urban residential, 50% suburban. These are planning goals, not perceived-beauty curves | Supports that expectation differs by land use (a peer-norm direction); breakpoints themselves: no source |
| Green view curve (5/15/25/40/50 %) and regional baselines | Treepedia reports single-city green view values (for example Miami 19.4%, New York 13.5%); no perception threshold or cross-region median found | No source. Treepedia city values could seed a documented baseline check but are single cities, not regional medians |
| Terrain curve | No effect size for relief or ruggedness on ScenicOrNot ratings found; European models using the GB data rank land cover and naturalness as the strongest predictors; Stadler, Purves and Tomko 2011: foreground features outweigh background | No source for the curve; suggests terrain alone is a limited scenic predictor |
| Measurement radii | A greenness-exposure review found buffers up to 2,000 m predicted physical health better than smaller ones (nested buffers advised); street-view green view is measured at points with small buffers (15 to 25 m); the VGVI viewshed study finds eye-level and top-down greenness are distinct measures (r 0.48) | Supports a multi-radius up to 2 km for exposure (a health result, not beauty). No source for 800/1,000/2,000 m by area type, the 1.2 km green view radius, 5 km terrain or 15 km water; no study ties a perceptual viewing distance to a radius |

Sources: [Elliott et al. 2020 research note](https://bluehealth2020.eu/publications/residential-distance/),
[Belfast green and blue space price study](https://pure.ulster.ac.uk/en/publications/the-value-of-green-and-blue-space-walkability-and-house-prices/),
[American Forests on the 40% goal](https://www.americanforests.org/article/why-we-no-longer-recommend-a-40-percent-urban-tree-canopy-goal/),
[Treepedia overview](https://geoawesomeness.com/treepedia-mapping-project-mit-will-tell-green-city/),
[Seresinhe, natural beauty mapping](https://arxiv.org/pdf/1612.03142),
[eye-level greenness visibility (VGVI)](https://repositorioslatinoamericanos.uchile.cl/handle/2250/3505050).
None of the papers was opened; confirm the figures in them before quoting externally.

### P3 and P4 sign-off (owner decision 2026-10-29): documented judgments, tiered

Signed off as JUDGMENT (form is sourced, values are not; each has a recorded tested range, so low stakes):
water curve shape (exponential decay, ocean > lake > river), canopy expectation varying by land use, the 0.7/0.3
within-part weights and 50/50 blend (move scores about 4 to 5 points at the tested ranges), and the measurement
radii (canopy radius swaps move scores 0.8 to 1.6 points). Water curve constants and maxima remain unfitted.

Signed off WITH A LIMITATION, not closed:
- **Green view curve saturates.** 505 of 1,476 places (34.2%, checked 2026-10-29) score 95 or more on green view,
  so the component stops separating the top third of the catalog and its effective weight collapses for them.
  Known ceiling; options when revisited are rescaling the curve or reducing its weight (a scoring change,
  needs approval).
- **Regional baselines are judgment baselines.** They run 2 to 3 times above this pipeline's own regional canopy
  medians in most regions, and desert scores depend on them (dropping them moves scores 5.9 points on average,
  Phoenix about -20, Las Vegas about -12, Seattle +14). A desert score is not an objective reading; say so in any
  methodology.
- **The percentile scale is anchoring, not evidence.** It maps the blend onto the old score distribution for
  continuity, so it inherits whatever the old score got wrong and fixes the catalog mean and spread by
  construction.

Known debt (P3): the area-type step in the canopy radius (800, 1,000 or 2,000 m) is a discontinuity at category
boundaries. If area type is retired it must be replaced with a continuous function of density or canopy, not
dropped, or scores will cliff at the old boundaries.

P7 face-validity kit built 2026-10-29 (`scripts/qa/natural_beauty_face_validity.py`, offline): 24 places drawn by
metro and area type (never by score; 6 arid places oversampled), 60 pairs at least 12 points apart (23 pair an arid
place with a non-arid one), blind sheet for raters and a private score key. Scored as the share of decided pairs
where the rater agrees with the blend's order; 75% is a judgment pass line, not a sourced threshold. Results: not
yet run.
First result 2026-10-29, ONE AI rater (not human, so not a P7 close): 40 of 58 decided pairs agree with the blend
(69%; 3 pairs marked "?"), arid-versus-other pairs 16 of 22 (73%), both below the 75% judgment line. The 18
disagreements cluster in three places: Downtown Tampa (stored 25: streets 5.6, scenery 30.5 from flat terrain and
a river at 34.7) rated above 8 higher-scored places; South Beach (55, ocean water 93 but streets 8) rated above
three inland green suburbs; and desert exurbs lifted by the regional baseline (Buckeye stored 61 with 1.25%
canopy and green view 19.3% scoring 93 after normalization; Anthem, Southern Highlands) rated below urban
places. Morrison CO (81, water read unavailable) rated below two urban places, which may be rater error. Treat as
places to investigate, not proof. Second rater, supplied by the owner 2026-10-29 (provenance not stated; the owner said no human rater is
available, so treat as non-human): 46 of 58 decided pairs agree (79%), arid pairs 19 of 22 (86%), above the 75%
judgment line; 2 pairs marked "?". Its 12 disagreements overlap the first rater's: Downtown Tampa (5), South
Beach (4) and North Las Vegas vs Buckeye, so waterfront urban places scored low by the blend (low streets, river
or flat terrain) are the one pattern both raters reject. Across both raters 86 of 116 decided pairs agree (74%).
No human rater is available and the owner accepts LLM raters as the validation for this pillar (2026-10-29), so P7 is accepted as an LLM face-validity screen, not a human validation, and is a
stated limit of this pillar: the blend and deserts are validated only by this AI screen and the component tests
above (Place Pulse 0.37, ScenicOrNot 0.41, USDA 0.66 and 0.30), none at the 0.7 gate.

Not closed by this sign-off: P6 (fails the 5-point gate at 500 m, causes diagnosed above) and P7 (blend
unvalidated). For P7 with no desert rating data, the proposed close is a face-validity test: pairwise rankings
of known places (for example a leafy suburb, Phoenix, a dense urban core) by a small expert or user panel, to
catch an obviously wrong blend; it gives no effect size.

Sourced (evidence only, no citation behind any parameter): streets inputs vs Place Pulse, terrain vs ScenicOrNot and
USDA, water vs USDA. Everything else above is a judgment call or a TODO. P4 stays open until a citation or an explicit
"judgment, range X" decision exists for each row; this table records the state, it does not close the principle.

## Related studies (supporting context only, none validates a parameter)
- Yin et al. 2022, Journal of Environmental Psychology 81:101775: VR desert scenes lowered cortisol and blood pressure against an office control in 95 El Paso men. Measures restoration, not beauty ratings, and the authors point to familiarity as a likely factor.
- García-Llorente et al., semi-arid watersheds in southeastern Spain (survey): favorite views mostly had steeper relief, water flows and traditional land use; place attachment went with willingness to pay for conservation. Supports terrain and water as beauty cues in dry landscapes; a local survey, not a rating dataset.

## Known gaps
- Deserts have no human rating data (Phoenix, Las Vegas). Plan: an in-product photo-rating question.
- No pin-shift test yet (green view reads 1.2 km, canopy 0.4 to 2 km, terrain 5 km, water nearest body within 15 km around the pin).
- Place Pulse photos are 2007 to 2012; ScenicOrNot is Britain only and almost all rural.
- Both canopy sources in `gee_api.py` are flagged deprecated by Google Earth Engine.

## Catalog
The catalog stores the neutral score plus `details.v9_breakdown` (component scores, `streets_score`, `scenery_score`).
`scripts/catalog/recompute_natural_beauty_two_part_offline.py` rewrites stored places from the stored component scores
(no API calls); run `recompute_catalog_composites.py --in-place --no-census` afterwards. The pre-change score is kept in
`details.score_before_two_part`.

## Gotchas
- The stored pillar `score` is the **neutral** score. Don't assume a preference is baked in.
- `ocean` vs `lakes_rivers` both target water; the per-type distinction is only as good as the stored water type.
- Older catalog rows (NYC, LA) keep `v9_breakdown` at the pillar root, not under `details`.
- History: the V7 to V9 upgrade once silently orphaned the preference, so picking one changed nothing for a while.
