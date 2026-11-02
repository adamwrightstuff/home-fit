# Pillar Deep-Dive: Active Outdoors

How `pillars/active_outdoors.py` scores a location (`get_active_outdoors_score_v2`).

## What it measures
Access to outdoor recreation, on three objective components (same 0–100 scale as the
Natural-Beauty-style pillars):

| component | signal |
|---|---|
| **daily urban outdoors** | parks, playgrounds, recreational facilities nearby |
| **wild adventure** | trails / wilderness / large natural areas reachable |
| **water lifestyle** | water-based recreation access |

Parks and playgrounds are judged against places of similar density (people plus jobs per acre, from the place context),
trails against one absolute scale, water against fixed feature scores. The area type still sets some read radii and the
water multipliers; every remaining use is listed in the spec sheet below. Inputs are OSM/Places features for parks,
trails, playgrounds, rec facilities, and water.

## Gotchas
- Daily outdoors is flat across density by construction (each place is judged against density peers), so it does not reward
  a dense walkable park network over a sparse one; a trail-rich exurb and a park-rich neighborhood can both score well for different reasons.
- Distinct from Natural Beauty: this is about *doing* things outdoors (recreation access), not
  scenic quality.

## Scaling and failed reads (changed 2026-10-25)
The three component budgets (daily 35, wild 50, water 25) summed to 110 and the total was clipped at 100, so 15% of
catalog places sat at exactly 100. The total is now the sum scaled by 100/110 (no clip), a documented judgment that keeps
the budget ratios. A component whose Overpass read failed (error or timeout; for the local-park read in a populated area
type, also an empty result) is no data, not zero: the score is rescaled from the components that read, the pillar is marked
degraded (`active_outdoors_missing_components`), and fewer than two components means no score. Exurban and rural places with
zero local parks are still treated as a real zero. Catalog: 1,476 rows rescored offline by
`scripts/catalog/recompute_active_outdoors_budget_offline.py` (mean 78.5 to 72.3; share at 100 from 15.2% to 0.5%; 45 places
degraded), then composites recomputed.

The 45 places with a failed read were then re-read through the private Overpass server (all components read) and written back by `scripts/catalog/apply_active_outdoors_retry.py`; none is degraded now.

---

## DPv2 spec sheet and audit (2026-11-02)

Status: **Level 0 until the owner signs off; proposed Level 1 after the fixes in the options below.** Audit done offline from
`data/*_merged.composites_recomputed.jsonl` at origin/main 3841a87 (1,476 places), plus the fresh park reads in
`analysis/ao_fresh_parks_uncovered/` (stored files, no new reads). No live call, no tunnel, no scoring change. The Level 2 checks
are not run; they are written as a brief for another agent (`docs/ACTIVE_OUTDOORS_LEVEL2_BRIEF.md`).

### Catalog state (verified 2026-11-02)
The catalog write was already made on 2026-10-28 (bd9286f, on origin/main): all 1,476 places carry
`dpv2_recompute.version = active_outdoors_dpv2_offline_2026-10-28`. The 545 places in the seven states the private server does
not cover (AZ CO FL GA MA NC NV and strays) were fresh-read the same day, so the catalog is not in a mixed state. That commit
changed only active outdoors, its contribution and the composites (total score, happiness index, longevity index, it_score);
a field-by-field diff of the 21 files against the parent shows no other pillar changed.

```
Pillar: active_outdoors
Construct (one sentence): Access to outdoor recreation near the pin: how well supplied it is with parks and playgrounds
  (judged against places of similar density), how many trails and camp sites lie within driving range, and the best water
  feature within reach.
Reference frame: mixed.
  Parks, playgrounds: density-peer norm (owner decision 2026-10-28; the Part 4 provisional frame was a fixed access standard
    with decay and was not adopted). Nearest park: fixed decay curve. Trails, camping: one absolute scale at catalog medians.
    Water: fixed feature scores.
  Evidence for the frame: parks and playgrounds, peer norm: none found (the only published evidence in Part 4 is an 800 m
    (0.5 mile) benchmark with mixed results, tier 1, which supports a fixed standard, not a peer norm). Trails: none found.
    Camping: none. Water: none. Nearest-park decay: none.
Measurement area: pin + circles of different sizes.
  Parks and playgrounds: 2,000 m (1.2 miles), distance-weighted, one radius for every place. Nearest park and facilities:
    the area type's radius (800, 1,000, 1,500, 2,000 m; 0.5 to 1.2 miles). Trails: 15 km (9.3 miles) and 5 km (3.1 miles).
    Camping and water: 15 km (9.3 miles) for urban and suburban types, 25 km (15.5 miles) for exurban and rural.
  Reason: the 2,000 m park radius is the baseline file's, set for fit and data coverage, not from evidence on how far people
    walk to a park (TODO). The type-dependent radii are legacy (principle 3 needs a stated reason; none is recorded).
Place context inputs used (fields) and remaining area-type uses (with reason):
  Reads: activity_per_acre (park and playground baselines). Missing in 4 places, which fall back to the type table.
  Remaining uses of the area-type label (principle 14 wants each justified; none has a source):
    1. Radius profile for nearest park and facilities (800 to 2,000 m). No reason recorded.
    2. Radius profile for camping and water (15 or 25 km). No reason recorded. It shows in the data: 29 percent of suburban and
       26 percent of urban residential places have no camping, against 8 percent of exurban and rural.
    3. Facilities expected count (3 points), area-type table, unsourced. Count is not stored in the catalog.
    4. Water multipliers (0.75 urban core, 0.95 lake and 0.9 other non-beach, non-bay for suburban and urban residential).
       Unsourced. Owner decided on 2026-10-27 to drop them; still in the code.
    5. Urban path filter on trails (urban types only). Unsourced.
    6. An empty park read is a failure only for populated types; elsewhere it is a real zero.
    7. Fallback to the area-type tables for the park and playground terms when the baseline file or the density factor is missing.
    8. Places fallback trigger and confidence minimums: not checked in this audit.
Inputs and data sources (with vintage): OpenStreetMap parks, playgrounds, recreation facilities, trails, camping, water
  (fresh read 2026-10-27/28 for parks and playgrounds, stored in analysis/ao_fresh_parks_uncovered/; trails, camping, water, facilities as read when each place
  was scored); Google Places supplement in 44 places; people plus jobs per acre from the place context (2020 tract tables).
Parameters:
  name | value | source | plausible range | sensitivity result
  park baseline, 8 knots (2 to 200 per acre) | 2.0 to 44.4 weighted parks | catalog fit, 931 places in 11 states, rolling median of 100 | unknown | x0.75: median 2.2 / p95 2.6 pillar points; x1.25: 1.7 / 2.0 (parks and playgrounds together, 1,472 places)
  park distance decay | 0.0012 per m | reused from the nearest-park term, itself unsourced | unknown | 0.0008: 2.9 / 4.3; 0.0016: 2.7 / 3.9
  park count radius | 2,000 m | baseline file | unknown | 1,500 m: 1.5 / 3.5, max 10.2
  playground baseline, 8 knots | 0.6 to 8.9, floored at 1 | catalog fit, 931 places | unknown | included in the rows above
  park budget 22, nearest park 8, playground 5, facilities 3 | 38 points, clipped at 35 | inherited | unknown | not run; 26 places sit at the 35 clip
  nearest park | 8 x exp(-0.0012 d), parks of 0.5 ha or more | inherited; 0.5 ha is also unsourced | unknown | the code comment says full score within 300 m and half at 800 m; the formula gives 70 percent at 300 m and 38 percent at 800 m (arithmetic, verified)
  trail targets | 56.5 within 15 km, 8 within 5 km | catalog medians, 1,476 places, not a standard | owner considered median vs 75th percentile (116, 15) | halve: median 6.6 / p95 8.9; double: 7.2 / 9.0; 25th percentile targets (30, 3): 7.0 / 9.8; 75th percentile targets: 7.1 / 8.9
  trail budgets 25 and 15 | 40 points | inherited | unknown | not run
  camping | 10 points, full within 25 km, decay 0.00005 per m | inherited exurban branch | unknown | decay x2: median 0, max 2.0
  water feature bases | beach 25, swim area 20, bay 20, coastline 18, lake 17, rocky coast 10 | inherited | unknown | not run
  water distance decay | 0.00025 per m beyond 3 km | inherited | unknown | not run
  water multipliers | 0.75, 0.95, 0.9, desert 0.3 and 0.6 | inherited | unknown | owner decision to drop; proposal estimated +0.30 mean waterfront points (not re-run)
  component budgets | 35 + 50 + 25 = 110, score x 100/110 | judgment, 2026-10-25 | unknown | share of final score 31.8 / 45.5 / 22.7 percent
Shared inputs with other pillars: natural beauty also reads OSM water and green space and the place context; overlap not tested
  (principle 5). Trail and park counts are not used elsewhere to my knowledge (not exhaustively checked).
Pin-shift sensitivity (shift distance, median and p95 score change): not run. Needs fresh reads at shifted pins (private
  Overpass for 11 states only). In the Level 2 brief.
Independent validation source and result: not run for the score. Related result (2026-10-27, report only): the park COUNT
  measure tracks the city park counts of NYC, Chicago and Los Angeles at Spearman 0.71 on 197 places (fresh OSM read); it
  tracks city parkland area at 0.30 and does not validate the level of any baseline. Trails: not validated. In the brief.
All-places check (date, n, summary): 2026-11-02, n = 1,476, run by the builder (so it does not count toward Level 2).
  Score mean 65.8, median 67.0, 10th to 90th percentile 45.6 to 84.4, min 17.9, max 98.7. At or above 99.5: 0. At or below 10: 0.
  By area type (mean, 10th to 90th): urban residential 68.0 (51.9 to 84.6); suburban 67.7 (48.9 to 84.6); exurban 65.0 (45.7 to 83.4);
  rural 54.4 (30.9 to 81.3). Components (mean, 10th / median / 90th): daily 22.8 (13.1 / 23.5 / 31.9) of 35; wild 32.2
  (17.5 / 32.0 / 48.2) of 50; water 17.3 (12.4 / 17.0 / 25.0) of 25. At the cap: daily 26, wild 88, water 208 places.
  Daily is flat across density, as designed: mean 21.0, 23.6, 23.0, 23.2, 23.6, 22.2, 24.2 in the bands 0-5, 5-10, 10-15,
  15-25, 25-45, 45-100, 100+ per acre. Wild is flat too (27.9 to 34.9; 29.5 at 100+).
  Reproducibility: the stored score equals the scaled component sum in all 1,476 places; the stored wild score equals the
  absolute-scale formula applied to the stored trail and camping fields in all 1,476 places (so the 214 stale wild scores noted
  on 2026-10-27 are gone); the residual (stored daily minus the recomputed park and playground terms) lies in the possible
  0 to 11 range of nearest park plus facilities in all 1,472 places with fresh data (necessary, not sufficient).
  Park baseline fit outside its 11 states (median observed / expected weighted count, covered vs uncovered states): 0-5 per
  acre 0.85 / 0.90; 5-10: 1.02 / 1.03; 10-25: 0.88 / 1.02; 25-100: 0.99 / 1.27; 100+: 1.19 / 1.82 (n = 12 uncovered). The baseline
  transfers at low and middle density; the uncovered dense places are better supplied than the curve, which raises their score.
Fail-loud conditions: an Overpass error or timeout on parks, trails or regional features leaves that component out and
  marks the pillar degraded (fewer than two components means no score). An empty park read is a failure only in urban core,
  urban residential and suburban types; in exurban and rural it is a real zero. Places supplement is flagged. Currently: 0
  places with a missing component, 0 degraded, 4 places with an empty park read scored daily = 0 (see gap 9).
Launch check pairs: not run. Proposed pairs and criteria are fixed in the brief.
Known data limits: OSM tagging completeness varies by region and the park measure is a count (mapping style matters);
  trail counts in dense metros reflect how route relations are mapped (Boston 657 median within 15 km vs Orlando 34); facilities
  not stored; water is best-feature-only, every place has at least one water feature within its read radius (min water score
  0.1); the health check flags 93 places conf_36 (poor quality tier) and 6 conf_68, and stored confidence is 36 in 75 places (50
  in the SF metro) and missing in 41; reasons not examined here; 175 places have no winning feature type recorded in the breakdown; 4 places have no area type.
Last re-validated: never.
```

### Audit gap table

Impact is on the 0 to 100 pillar score unless stated. "Offline" means derivable from stored data.

| # | Area | Gap (evidence) | Recommended fix | Expected score impact |
|---|---|---|---|---|
| 1 | Parks (22 pts) | Peer-norm frame has no external evidence; the baseline is a median of the places it scores (circular) and flat by construction (daily mean 21 to 24 in every density band); knots at 25 and 100+ per acre are the least stable; the 545 places outside the fit area sit at 1.02 to 1.27 of the curve at 10+ per acre and 1.82 at 100+ (n = 12). | Keep. Mark TODO. Validate the level against ParkServe or city polygons (Level 2). Ask the owner whether a fixed access standard should replace the peer norm. | None until validated. Parameter sensitivity ±1.7 to 2.9 median, p95 up to 4.3. |
| 2 | Playgrounds (5 pts) | Same method, 5 points; floor of 1 on the expected value is an invented constant. | Keep, mark the floor TODO. | Under 1 point. |
| 3 | Facilities (3 pts) | Still on the area-type table; count not stored, so no offline recompute. Unsourced. | Facility points can be backed out offline as stored daily minus the park, playground and nearest-park terms (all recomputable from the fresh lists, which hold distance and area), so the term can be dropped and the pillar rescaled without a read. Otherwise keep it as a listed TODO. | At most 2.7 points for a place with all 3 points; mean unknown (count not stored). |
| 4 | Nearest park | Radius is the area type's (800 to 2,000 m), so a park 1.0 to 1.2 miles away counts for exurban places and not for suburban ones. The code comment misstates the curve (full within 300 m, half at 800 m). | Use the 2,000 m list for every place (the fresh lists already hold it) and fix the comment. Offline. | 7 of 1,475 places change, mean +1.6, max +2.1. |
| 5 | Trails (50 of 110 points) | Targets are catalog medians with no external benchmark; this is the pillar's largest uncertainty: halving or doubling the targets moves the median place by 6.6 to 7.2 points and the 95th percentile by about 9. Budgets unsourced. | Keep, mark TODO with the sensitivity above. Use PAD-US for relative ordering only (Level 2). Do not claim the level is validated. | None now. Owner choice of 25th / median / 75th percentile targets is a ±7 point decision. |
| 6 | Camping (10 of 110) | Read radius depends on the area type (15 vs 25 km), a cliff: no camping found in 29 percent of suburban and 26 percent of urban residential places vs 8 percent of exurban and rural. 140 exurban and rural places get full credit for camping 9.3 to 15.5 miles away that an urban or suburban place would never see. 22 percent of places have none. | One window for everyone. Feasible offline: full credit within 15 km (9.3 miles) for all, nothing beyond (the alternative, a 25 km read for the other 961 places, needs the private Overpass server brought up from its snapshot, billed hourly). | Lowers up to 140 exurban and rural places by up to 9.1 points each (those with camping 9.3 to 15.5 miles out). Nobody gains. Exact set computed before any write. |
| 7 | Water (25 of 110) | Feature bases, 3 km decay and desert factors unsourced. Multipliers on area type and desert (owner decided to drop on 2026-10-27) still in the code. Best feature only; 844 places win on "lake" with no size filter that I verified. Water is never below 0.1: every place has a feature within its read radius. | Drop the type multipliers (decided). Offline recompute is a lower bound only (winner can change; feature lists are not stored). Mark bases TODO. Check lake size handling in the query before Level 2. | Proposal estimate +0.30 mean waterfront points (about +0.3 pillar points), 1 percent of places move over 1 waterfront point; not re-run. |
| 8 | Scaling by 100/110 | Budgets 35 + 50 + 25 = 110 are inherited and the divisor is a documented judgment, not evidence. Daily budgets sum to 38 and clip at 35 (26 places at the clip). No place reaches 100 (max 98.7) so the earlier ceiling clumping is gone. | Keep. Record as a judgment (TODO). Consider whether the daily clip should go. | None for the divisor. Clip removal: not measured (the stored daily value is already clipped). |
| 9 | Fail-loud | Four places with an empty park read are scored daily = 0: Larkspur CA (59.7), Orinda CA (54.2), Woodside CA (47.9) and Moapa Town NV (24.4). They are typed exurban or rural, so the empty-is-failure rule does not apply. The three Bay Area places are known to have parks and have no fresh read in the stored files. If the term were left out instead, the scores would be 87.6, 79.5, 70.3 and 35.7 (not recommended as a final value). The health check flags 93 places as poor quality tier (conf_36); reason not examined. | Re-read the four places (needs Overpass; ask first) and treat an empty read as failure for every type unless a second source confirms zero. Meanwhile mark the four degraded. | If the term were simply left out the four would rise by 11 to 28 points; the real value after a read is unknown. The rest of the catalog is unchanged. |
| 10 | Area type | Eight remaining uses (listed in the spec sheet); the dpv2 fallback tables apply to 4 places with no density factor. | Remove uses 1, 2, 4, 5, 6 and 7; keep 3 and 8 as listed TODOs. | Uses 4 and 2 are the only ones with measurable score impact (rows 6 and 7). |
| 11 | Live vs catalog | The catalog daily term was built by subtracting the old park and playground terms and adding the new ones, not by running the pillar. The live pillar computes it directly. They are expected to agree; not tested (needs live calls). | Level 2 brief, with the owner's permission for live calls. | Unknown. |
| 12 | Doc drift | This doc described area-type-relative scoring; the nearest-park comment is wrong; the old "Scaling" section does not mention 2026-10-28. | Fixed in this doc; code comment fix in row 4. | None. |

### Options

The 547-place question is closed: all 1,476 places were written on 2026-10-28 and the 545 outside the private server were fresh-read.
The decision now is what to do about the gaps above.

- **A. Sign Level 1 as is.** List the eight area-type uses with "no source" as the reason. Fastest; meets the Level 1 wording but not the intent of principle 14, and keeps rows 6, 7 and 9 unfixed.
- **B. Fix the offline items, then Level 1 (recommended).** Four steps, each needing your approval before it runs: (1) drop the water multipliers (decided in October), (2) one 15 km camping window for all, (3) nearest park from the 2,000 m list, (4) re-read the four empty-park places. Each is recomputed into new files with a diff for you, and the health check and an other-pillars check run before anything replaces a file. Costs: rows 6 and 7 move scores (row 6 only down, up to 9.1 points, for up to 140 places). Only step 4 needs a fresh read (and the alternative to step 2 would).
- **C. Hold everything for Level 2.** Run the brief first, then decide fixes with the results in hand. Slowest; avoids changing scores twice if the validation finds a bigger problem.

Recommendation: B for steps 1, 3 and 4, and decide step 2 after you see the 140-place list. Run the Level 2 brief after.

### Proposed compliance level (for sign-off)

Level 0 now. Level 1 is reachable under option B. Level 2 requires the brief's checks, run by another agent, with the criteria fixed beforehand. Level 3 is not reachable: every budget, base, decay and target is unsourced or a catalog median (listed above). Re-validation date proposed: 2027-02-02 (quarterly), or sooner if the OSM read or the baseline files change.

Open TODOs accepted by the audit (nothing here is sourced): park baseline level, decay, radius, playground floor, all point budgets, nearest-park curve and 0.5 ha rule, trail targets and budgets, camping window and decay, water bases and decay, the 100/110 divisor, facilities term.

### Option B steps 1, 3, 4: status (2026-11-02, owner approved 1, 3 and 4)

Code (this branch, not pushed): the water area-type multipliers are removed; the nearest-park term reads the 2,000 m list for every
place that has the density factor, and its comment is corrected. Two tests added; 66 active outdoors and water tests pass.
Step 2 (camping window) is not started, awaiting the 140-place list decision.

Catalog recompute, new files only (`analysis/ao_recompute_2026-11-02/`, composites in `analysis/ao_recompute_2026-11-02_composites/`;
script `scripts/catalog/recompute_active_outdoors_water_nearest_offline.py`; no data file replaced; nothing live):
- Pillar score: 469 of 1,476 places change, mean +0.23, max +2.1, 23 places by more than 1 point, 2 by more than 2. Nobody falls.
  By area type (mean change): suburban +0.42, urban residential +0.13, exurban 0, rural 0.
- Water: 463 places rise (mean +0.80 among those, max +1.8 waterfront points, 16 by more than 1). This is a LOWER BOUND: the stored
  feature lists are not kept, so a second-best feature that would overtake the winner without its multiplier is not seen. The 36
  places scored under the old mountain-town override are left unchanged (they never carried a multiplier).
- Nearest park: 7 places change (mean +1.8 daily points, max +2.3); the 16 places with no fresh read keep their stored value.
- Composites: total score changes in 465 places (max 0.18), happiness index in 254 (max 0.2), longevity index in 471 (max 1.73).
  The 1.73 is one place, Pelham Bay NY, whose stored longevity contributions had no natural beauty entry; the recompute filled it in,
  unrelated to this change (its active outdoors score is unchanged at 66.2).
- Other pillars: field-by-field diff of the 21 files against the current files shows no change outside active outdoors and the
  composites.
- Health check (active outdoors, all 21 files): the same 99 flagged places as before (93 conf_36, 6 conf_68); plausibility outliers
  41 before, 43 after (near the z cut-offs; not examined).
- Step 4 (re-read Larkspur, Orinda, Woodside, Moapa Town): NOT DONE. It needs the private Overpass server (not reachable now: no
  tunnel is listening, and the server address is kept in the owner's notes, not the repo). Needs: bring the server up from its
  snapshot (billed hourly) or the address if it is running; one park read at 2,000 m for four places; then the daily term is
  recomputed offline with the same method. These four stay at their stored values until then.

