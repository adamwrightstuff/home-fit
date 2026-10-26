# Education pillar, v2 audit (2026-10-25)

Read-only and offline. No code, tests or catalog files changed, nothing committed, no external calls (sockets were blocked in the one replay I ran; the script lives in the session scratchpad, not the repo). Stored values come from the 21 `*_metro_place_catalog_scores_merged.composites_recomputed.jsonl` files (1,476 places). Principles are in `docs/DESIGN_PRINCIPLES_V2_DRAFT.md`. I did not edit the tracker.

## Headline

The "105 SF places at 0" problem no longer exists: all 113 SF places carry a real score (min 9.1, median 68.7, max 100). The memory note `project_sf_schools_rescore_needed` is stale and should be corrected. The real zero-as-data problem is 4 places (1 Las Vegas, 3 Phoenix). The bigger findings are that the early-education bonus rests on a query that cannot be trusted (78% of places store 0, 96% in NYC and LA), and that a 0.5 mile pin shift moves the score a median 5.8 points.

## What is sourced and what is judgment

Sourced or validated:
- Rating = SchoolDigger statewide percentile. Checked against federal EDFacts proficiency (2017-18, the newest school-level year available): Spearman 0.66 to 0.92 within districts (doc, 2026-10-16). Tier: validation against an independent source, but old and school-level, not place-level.
- Elementary radius ratio 2.1 : 3.2 : 3.6 miles from the 2017 NHTS median school trip.
- Frame (relative standing) leans on capitalization studies using standardized scores (Black 1999 and later work, from the Part 4 table, tier 2). I did not re-verify those papers.
- Zone-map school assignment (district-published maps; NCES 2015-16 survey as fallback, 90% agreement with current maps at 143 overlap checks).

Judgment, no source (these are TODOs under P4):
- Education weight 7.69% (an equal 1/13 share). The doc says "equal share of the default pillars". 7 places carry 8.33%.
- Early-education bonus: 1, 2, 3 points at 1, 2, 3+ facilities; 2 km radius; 0.7 multiplier beyond 1 km; the 3-point cap.
- Radii 1.5 / 2 / 3 miles by area type (the doc itself says "our own conservative choice, not an empirical neighborhood boundary").
- Nearest-3 per level, 3 mile widening cap, 15 mile district-far fallback, choice pool = enrollment-weighted district average, equal weighting of elementary, middle and high.
- Access bonus (+2 per school at 85 or above, cap 5) survives only in the legacy path; zoned_v1 sets it to 0. Fine, but the legacy path is still reachable.

## Per principle

| Principle | Status | Evidence |
|---|---|---|
| P1 reference frame | Open decision | Part 4 provisionally says relative (state rank), tier 2. Part 1 says school proficiency should default to a fixed standard. These conflict and the audit order says the owner decides. A statewide percentile is not comparable across states: place means run from CT 84.7 and WA 91.8 (5 places) to FL 51.9, AZ 48.6 and DE 42.0. Part of that is which places are in the catalog, so I cannot split it. |
| P2 construct | Does not meet | The doc says "school quality near a location". The code measures the test-score percentile of the assigned (or nearest, or district-pool) schools, which is a level, not growth, and it also feeds a longevity weight of 3.0 sourced to years of schooling (Cutler and Lleras-Muney), a different construct. No one-sentence construct, and nothing separates school, district and early education. I did not search whether score level or growth is what residents pay for beyond the capitalization studies already cited; that is a TODO. |
| P3 measurement area | Partly | Pin plus Census district polygon, then zone by pin, else nearest 3 within a radius. Reason given for the elementary ratio only. See P6 for what this costs. |
| P4 sourced weights | Does not meet | Weight, early-ed bonus and tiers, radii, nearest-3, caps are all unsourced and have no recorded range. |
| P5 double counting | Not checked here, one note | Education also enters the longevity composite. Overlap with housing value (home prices capitalize schools) not tested. |
| P6 sensitivity | Fails | Replay of 1,472 scoreable places with the pin moved 0.5 mile N, S, E, W (largest of the four): median change 5.8 points, p90 32.0, p95 42.9, max 80.9; 53% move more than 5 points and 38% more than 10. By metro, median runs from 1.0 (SF) to 12.5 (NYC). Caveat: some large movers land in another district or off land (Houston Seabrook went to 0), so the tail is partly boundary effects, which is the point of the test. The unshifted replay reproduced stored scores (mean difference 0.10; 36 places differ by more than 0.05, max 25.6, so some stored values are stale and I did not trace them). No weight perturbation was run on the pillar itself; at composite level (approximate, my recomposition from stored pillar scores and weights does not match stored totals exactly, mean gap -0.36) dropping the education weight to 0 moves the total a mean 1.6 points (max 4.9), halving it 0.8, doubling it 1.4. |
| P7 validation | Partly | EDFacts rank check is good for ratings, 2017-18 data, within district. Nothing validates the place-level score, the zone assignment (except the 143-check 2015-16 comparison), or the choice-pool averages. |
| P8 all-places check | Partly | Backlog records full-catalog rescoring and a check script (`check_education.py`). No all-places run of the early-ed query. |
| P9 fail-loud | Does not meet | See defects D1 and D2. |
| P10 launch pairs | Not defined | Spread exists (decile counts from 0-9 to 100: 27, 105, 110, 136, 143, 158, 208, 170, 174, 239, 2) but no pairs written down. 102 of 1,472 score 95 or above, 239 are in the 90s, so the top is crowded. |
| P11 data limits | Partly | Docs list known limits (thin districts, stale Austin zones). Vintage is not surfaced as confidence: 80% of zoned levels (2,746 of 3,433) come from the 2015-16 survey. |
| P12 re-validate | Partly | Yearly snapshot refresh is planned in the doc; no dated schedule for the validation. Austin zones stale, Philadelphia/Houston/Dallas newer. |

## Defects, with stored evidence

D1. Zero shown as a score where there is no data (P9). Las Vegas, Indian Springs: score 0.0, weight 7.69, status success, not degraded, all three levels have no source. The stored total (41.01) already equals the total without education, so the composite is right but the pillar displays a believable 0. Phoenix Rio Verde, Sun City, Sun City West: score 0.0, weight 0, status fallback, no model, no levels, shown as 0.0. Expected impact: 4 places change from 0 to no data; composite for those places unchanged. Also 3 places are marked thin (1 to 2 levels) and one has 0 of 3 levels thin; these are flagged in the summary but not in `degraded`.

D2. Early-education bonus cannot be trusted (P9, P4, P5).
- Stored evidence: 1,157 of 1,476 places (78%) store 0; NYC 96%, LA 96%, SF 93%, Chicago 94%. Those are the densest places in the catalog (Andersonville, Albany Park, Avondale store 0). Not one place has `early_ed_missing` true (1,472 false, 4 null), and no amenities pillar overpass flag overlaps. A stored 0 cannot be told apart from a failed query.
- Code: the request function only checks for HTTP 200 and reads `elements`. A 200 that carries an Overpass runtime remark (empty elements) is read as "queried, nothing found", the exact failure the flag was added for (commit 2063661, 2026-10-16). Rows scored before that date have no flag at all.
- Code: the tag filter is `kindergarten|preschool|nursery`. As far as I know OSM daycare is mostly `amenity=childcare`, which the filter misses (from general knowledge, not checked here, and I cannot check it offline).
- Code: the count is every returned `node`, `way` and `relation` element, and the query adds `>` (member nodes). One preschool mapped as a polygon returns its vertex nodes too, so a single facility can reach the 3-facility tier. The distance step also takes the minimum over nodes only, so a polygon-only result has distance infinity and always gets the 0.7 penalty. Stored tiers fit this: 125 places at 2.1 (3.0 x 0.7), 58 at 0.7, 7 at 1.4, only 106 at the full 3.0, 17 at 1.0, 6 at 2.0.
- Net: it is a 0-to-3 point add-on built on an unreliable count, unsourced tiers, and it is the one Overpass-dependent input in an otherwise offline pillar (the offline rescore reuses the stored value).
- Expected impact of removing it, from stored values: 319 places lose points (237 lose 2 or more); mean pillar change -0.45 (max -3.0); composite mean -0.03 (max -0.25). Fixing the query instead cannot be quantified offline.

D3. Pin sensitivity (P6): see table row. A place's score depends on which side of a district or zone line the centroid pin falls.

D4. Zone vintage (P11): 80% of zoned levels use 2015-16 boundaries; the doc estimates about 10% of those have changed. Not surfaced as a confidence or degraded reason on the place.

D5. SF County choice scoring (P3): 33 SF County places are scored from the district-wide lottery pool average at every level and therefore receive only three distinct values (61.16, 63.26, 64.16; the difference is the early-ed bonus). This is a deliberate, documented honest-over-coverage choice (2026-10-16), and it is district-level resolution, not a bug. The other 80 SF-metro places (Oakland, Marin, Peninsula and so on) are zoned or nearest-3. The risk is only that the pillar looks like an address-level score where it is not; the summary text does say "by lottery".

D6. Documentation drift: `docs/PILLAR_QUALITY_EDUCATION.md` still opens its "What it measures" and "Scoring" sections with the old radius model, and `_get_school_data_legacy` is still reachable; the 3 places with no model show it.

## Answers to the specific questions

Construct: not stated. School quality (assigned or nearby schools' test percentile) is what is scored; district enters only through the home district polygon and the lottery pool; early education is a separate 0-3 add-on. These should be separated in the spec sheet.

Data source order: boundaries and zone maps are Census and NCES and district files, ratings come from one SchoolDigger snapshot (`data/school_snapshot`, 18 states now, fetched once; zero per-place calls). Nothing here needs new SchoolDigger calls and I propose none. The remaining SchoolDigger exposure is the yearly refresh; the no-API alternative for ratings would be state test data (EDFacts is only 2017-18), which is a larger project.

The 105 SF places: resolved (see headline). If you want the zero-as-data rule enforced generally, D1 is the open instance.

Measurement area: single point plus district polygon plus zone polygon; sensitivity above. A second reasonable design is the place or tract footprint, but that needs a decision before testing.

## Proposed fixes and expected impact (all unapplied)

1. Show no data and degraded for the 4 zero places; return null instead of 0.0 from the legacy path. Impact: 4 displays change, composites unchanged.
2. Early-education bonus: either remove it (impact above) or keep it and fix the query (count facilities not elements, add `childcare`, treat empty 200 with a remark as failure, reread rows without a flag), with a source for the tiers. A source for the size is a TODO either way. I recommend removal until sourced, because I found no evidence in the repo for the 1/2/3 tiers or the 2 km radius.
3. Record a source and range for the 7.69% weight, or mark it a TODO in the spec sheet; compute composite sensitivity properly with the real composite function.
4. Report a place-level confidence that includes zone vintage and nearest-3 versus zoned versus choice.
5. Pin-shift: report p95 as a data limit now; a place-footprint design is the real fix and needs your call.

## Decision for you

Remove the early-education bonus now (319 places lose about 2.1 points on average, composite change under 0.25) or keep it and rebuild its query and sourcing first?
