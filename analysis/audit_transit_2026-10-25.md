# v2 audit: public transit pillar (2026-10-25)

Scope: `pillars/public_transit_access.py`, `docs/PILLAR_TRANSIT.md` (there is no `PILLAR_PUBLIC_TRANSIT*.md`; this is the only transit doc), `data_sources/radius_profiles.py`, and the stored `livability_pillars.public_transit_access` block of the 21 `*_merged.composites_recomputed.jsonl` files (1,476 places). Read-only and offline. No code, data or tracker changed, nothing committed, no downloads, no web search. Evidence in the "what the evidence says" lines comes from `docs/DESIGN_PRINCIPLES_V2_DRAFT.md` Part 4 (search summaries, not full papers) and is marked unverified where I did not see the source.

## Headline

The 169 places (11.4%) scoring exactly 0 are not a validated finding of "no transit". They are all the same record: 0 routes, confidence 0, quality tier "fair", no data sources, not flagged degraded, and still carrying their full 7.7 to 8.9 percent weight. The code returns `0` for a place with no Transitland routes and for a place where Transitland could not be read (missing key, HTTP error, exception all return an empty list), and the stored record cannot tell them apart. At least 5 of them are almost certainly failed reads: Pelham Bay (6 train terminus, NYC), and Acton, Lincoln, Weston (MBTA commuter rail towns) from my own knowledge of the geography, not from stored data. Separately, 104 other places carry invented fallback scores, and about 578 places sit above the documented supply formula because of an unsourced legacy layer.

## Sourced versus judgment

| Item | Sourced? |
|---|---|
| Frame: fixed standard with distance decay | Provisional, tier 1 (draft Part 4), not yet approved |
| 400 m bus and 800 m rail as walk conventions | Planning convention only; observed 85th percentile walks were about 524 m bus and 1,259 m commuter rail (Montreal, draft Part 4, unverified). The code uses neither |
| Search radius 3000 / 2000 / 1500 m by area type | No source in code or docs. Judgment |
| Mode weights subway 3, light rail 2, commuter 1, bus 0.7 | Comment says "real daily service". No ratio computed from data. Judgment |
| ANCHOR = 120 and the log curve | No source. Docs report MAE about 9.7 against Walk Score Transit Score, which is a fit target, not evidence (P7 says regression and fit checks do not count) |
| Commute blend COMMUTE_WEIGHT = 0.05 | No source. A stale comment says 10 percent |
| `_score_commute_time` breakpoints | urban only: percentiles of 14 catalog places ("calibrated" to the sample, circular). Suburban and exurban breakpoints say TODO in the docstring |
| Commuter floor ramp 5 to 30 percent transit share | No source. Chosen after the user rejected a cap; the idea is sound, the numbers are judgment |
| Commuter bonuses (frequency 8, commute 5, weekend 3, hub 10, destinations 2) | Scaled from correlations on n = 8 to 14 places. Not a published fit |
| Legacy suburban fallback (base 20 to 70, bonuses 6/10/15, bus x3) | Code says "not research-backed" and carries TODOs |
| Hard-coded fallback when Transitland is empty (15/12, 10/10, 5/8) | No source |

## Per principle

**P1 reference frame.** Meets in principle (fixed standard with decay, tier 1, provisional). The code does not implement decay: it counts routes inside a circle, with no weighting by distance to the stop.

**P2 construct.** Partly meets. The doc says "service supply and commute access at a point". Those are two constructs. Supply is access; the commuter floor and commute blend are outcome (resident commute time, which includes car commuters). Recommend stating one: access to useful service.

**P3 measurement area.** Does not meet. The radii (3 km urban core, 2 km suburban, 1.5 km exurban and rural) are 2 to 4 times the 800 m rail convention and roughly 3 to 7 times the 400 m bus convention, with no stated reason. Counting routes within 3 km credits a route that is a 40 minute walk away. Also unverified: whether the Transitland radius filter matches a route by any stop in the circle or by geometry. Evidence: the draft says a decay curve beats a cutoff. TODO: replace with walk-distance decay by mode, using the 524 m and 1,259 m figures only after reading the source.

**P4 sourced weights with ranges.** Does not meet. Every weight in the table above is judgment and none has a recorded range. Frequency, which the evidence says matters, is not in the base score at all: it is a bonus gated to commuter-rail suburbs and usually absent because schedule data is missing (the doc says so). A route count treats a 4 trips/day bus like a 5 minute subway.

**P5 double counting.** Does not meet. Mean commute time enters the same pillar up to four times for a commuter suburb: the 5 percent blend, the commute bonus (up to +5), the commuter floor (commute score times ridership ramp), and, outside the pillar, the Happiness `commute` component (weight about 0.05 in 1,242 places). The docs say the Happiness channel is separate, which is true, but a town gets commute credit in both. Not computed: the size of the overlap in the composite. Stored data cannot give it without a decomposition I did not run.

**P6 sensitivity.** Not tested. No pin-shift or radius test exists for this pillar. Cost note: the catalog cannot run one offline because route counts come from live Transitland.

**P7 independent validation.** Does not meet. The only check is Walk Score Transit Score (MAE about 9.7), which is a third party proxy, not timetables, and was used to tune the model. Draft says timetables. TODO: GTFS stop-time counts for a sample.

**P8 all-places check.** Did it here (below). The stored catalog does not match the documented formula.

**P9 fail loud.** Does not meet (three gaps below).

**P10 launch check.** Fails on the zero cluster and ceiling: 57 places at 95 or above, 38 at 99 or above (anchor saturates with about 120 weighted routes). Zero places by area type: rural 101 of 142, exurban 61 of 385, suburban 5 of 743, none urban.

**P11 data limits.** Does not meet. No coverage or vintage disclosure; the 169 zeros and 104 fallbacks show no degraded flag.

**P12 re-validation.** None scheduled. The doc itself warns the live route fetch is noisy and undercounts under load.

## Defect list with stored-data evidence

**T1. Failed Transitland reads are scored as zero, not as no data.** `_get_nearby_routes` returns `[]` for a missing API key, any non-200 status and any exception; the caller treats `[]` as "no routes" and, outside urban and suburban places, returns `0` with `_empty_breakdown()`. Stored: 169 places, all with `total_routes 0`, `confidence 0`, `degraded false`, no `data_sources`, weight still applied. By area type they are rural 101, exurban 61, suburban 5, unknown 2. Named suspects: Pelham Bay (NYC, classified rural, adjacent to a subway terminus), Acton, Lincoln, Weston (Boston), Bedford (NYC), Oak Brook (Chicago), Surprise and Ahwatukee (Phoenix). Whether each is a failed read or true absence cannot be told from the file; it needs a retry. Impact if all 169 became no data with weight redistributed: total score +5.3 on average (range +3.4 to +6.7). That is an upper bound on a mixed group. Many of the 142 rural places probably do have no service and 0 is then a legitimate reading, but under P9 even that should be "no service found" with a confidence statement, not a silent number.

**T2. Invented fallback scores for 104 places.** When Transitland returns nothing for an urban, suburban or density over 1,500 place, the code assigns fixed heavy-rail and bus points (15 and 12, 10 and 10, or 5 and 8) plus 5 percent of a commute score. Stored: 104 places carry `fallback_applied`, `degraded false`, no `mean_commute_minutes` in the summary. This is the exact pattern P9 forbids. Fix: no fallback; no data, retry.

**T3. 578 places sit above the documented supply formula.** I recomputed v3 (`3*subway + commuter + 2*light + 0.7*bus`, log, anchor 120, 5 percent commute) from stored route counts. 441 of 1,307 non-zero places match within 1 point, 63 are below, 803 are above. Of the 803, 225 are commuter-only places lifted by the floor (mean +11.1 points, up to +3.3 total score). The other 578 (mean +9.0 points, max +28.2; 264 suburban, 223 exurban, 66 urban residential) are not explained by the floor. Bus-only places show the pattern directly: one bus route scores 43, two score 46, three 49, step 3 per route, against 11.1, 18.3, 23.6 from the formula. That matches the legacy suburban fallback layer (base 40 plus 3 per bus route), which the code marks "not research-backed". Average effect on total score for the 511 suburban, exurban and rural places in this group is +0.8, max +2.5. The doc says the layer is "effectively dead"; the stored data says it is live for hundreds of places. One of the two is wrong, and I did not verify which code version produced the file (stored `version` is empty).

**T4. Stored floor results disagree with the documented results.** Doc: Harrison 62, Darien 56.6, Bronxville 58.9, Larchmont 56.1, Scarsdale 59, New Canaan 22.7, Norwalk at supply. Stored: Harrison 76.0, Darien 68.5, Bronxville 58.9, Larchmont 56.1, New Canaan 22.8, Norwalk 45.4 with 0 commuter routes, Scarsdale 32.0 with 0 commuter routes. Harrison and Darien are about +14 and +12 above the doc, and Scarsdale and Norwalk show no commuter route at all, so the floor cannot apply to them. This is the stale-commute drift the memory note warns about, or a route-fetch miss, or the floor was applied from a later script. Not diagnosed; needs a re-run of `scripts/fix_commuter_floor_fresh.py` logic read against stored values.

**T5. Commuter floor design.** It meets the intent of the memory note (credit rail commute towns, ridership weighted, no cap) and I recommend keeping it. Gaps: (a) it fails quietly (`except Exception` sets commute and share to None and skips the floor, no flag); (b) it uses `_score_commute_time` whose suburban breakpoints are unsourced; (c) the ramp 5 to 30 percent is unsourced; (d) it uses the same Census commute as the 5 percent blend, which is T6; (e) the guard `subway_count == 0` excludes mixed PATH and NJ Transit places only by route_type, so a place with one subway route and strong commuter rail gets no floor.

**T6. Commute double counting** (P5 above). 168 of the Happiness commute weights are 0 where transit is 0, so the two channels are missing together for those places, which suggests commute is also unavailable there.

**T7. Neutral values and dead code.** `_score_commute_time` returns 70.0 for missing minutes (a neutral fill). It is not reached today because callers check first, but it is a latent P9 violation. The docstring has a stray "I" and a stale "10%" comment; the commuter bonus code samples `heavy_rail_routes[0]` and the first stop, which the code itself marks TODO ("match stop to route more accurately"), so the frequency bonus can come from an unrelated stop.

**T8. Rank of commute against transit is near zero.** Spearman between final transit score and mean commute minutes across 1,204 places with both is 0.07, so the commute blend is not what drives scores (maximum swing from the 5 percent weight is 4.2 points). It is therefore both small and a double count; dropping it from the base blend loses little.

## Proposed fixes (not applied) and expected impact

Computed from stored values where possible. None is applied.

1. **No data instead of 0 and instead of fallbacks (T1, T2).** Distinguish a failed read from an empty one; retry failures; mark true empties "no service found, degraded". Expected on the catalog: up to 169 zeros plus 104 fallbacks (273 places) leave the headline; the 169 would gain 3.4 to 6.7 total points if they became no data and 0 if retried successfully to real service (unknown). I cannot estimate the split offline. The 104 fallbacks hold scores of about 15 to 30, so dropping them raises their totals by a similar order (not computed).
2. **Decide whether the legacy layer (T3) stays.** Option A: remove it. The 578 unexplained places would fall about 9 points on average (up to 28), total score 0.8 on average for the 511 suburban to rural places, max 2.5. Option B: keep and source it. I recommend A unless the owner has evidence that Transitland misses real service, in which case the right fix is better data (OSM stops or GTFS) not a distance guess.
3. **Replace the circle with walk-distance decay by mode (P3).** Needs reading the Montreal source first and choosing a decay shape. No impact estimate possible offline because route counts are not stored with distances (`distance_km` is null in the stored records for the nearest routes).
4. **Frequency into the base score.** The evidence frame (draft) says frequency matters; the base score ignores it. Needs GTFS stop times, which is a download I have not asked for.
5. **Commute credit once.** Keep the commuter floor (memory note), drop the 5 percent blend and the +5 commute bonus. Impact: at most 4.2 points of pillar score, 0.3 of total, rank unchanged to a first approximation (Spearman 0.07 with commute).
6. **Re-derive T4.** Decide whether the stored Harrison, Darien, Scarsdale and Norwalk values are right before anything else, because the memory note says the floor must follow a fresh commute fetch.

## Not checked

Whether the Transitland radius filter matches by stop or by geometry; whether any of the 169 zeros has real service (needs a live or cached retry); the degraded-flag state of the 578 lifted places; the overlap size between transit commute and Happiness commute in the composite; any published study beyond the draft's search summaries.

## Decision

Retry the 273 zero and fallback places before touching any weights? Each is a Transitland call, so please confirm you want that, since it settles whether the zeros are a data failure or a true reading and decides how much of fixes 1 and 2 is worth doing.

## Outcome of the fail-loud step (2026-10-26)
Fixes 1 and the retry were applied (T1, T2): failed reads raise, the fallback is removed, and the 273 zero and fallback places were re-read live. All reads succeeded: 4 had real service (Pelham Bay 63, Glendale 55, Southport 14, Cedar Park 18), 269 are confirmed no service within the radius. The audit's suspected failed reads (Acton, Lincoln, Weston, Bedford, Oak Brook, Surprise, Ahwatukee) are true zeros under the current radius, not failures; Acton has a route at 2 km and Weston at 5 km. T3 (578 places above the documented formula), T4 (commuter floor drift), P3 radius and the double counting remain open.
