# Pillar Deep-Dive: Social Fabric

How `pillars/social_fabric.py` scores a location. Current model: v17 fail-loud blend (base weights unchanged
from v16b). Updated 2026-10-24; replaces the older v14 description.

## What it measures
The strength of local community life: organizational engagement and volunteering, bonding cohesion,
residential stability, and walkable civic gathering places.

## Components and base weights
| Component | Base weight | Source |
|---|---|---|
| Participation | 0.60 | Engagement: IRS BMF nonprofits per 1k (area-type baselines) and volunteering, 50/50 (`community_participation`); then 65/35 with the Social Capital Atlas civic-organization rate |
| Cohesion | 0.20 | Social Capital Atlas ZIP clustering and support ratio, peer-normalized by area type |
| Rootedness | 0.10 | Residential stability: 0.8 x ACS B25038 long-tenure housing + 0.2 x B07003 same-house, blended 0.7 tract / 0.3 place, scored against regional bands. The above-85% penalty is suppressed when median home value is at least $350k (F15) |
| Civic | 0.10 | OSM / Google Places civic nodes (library, community centre, worship, clubs, cafes ...) by type weight, peer-normalized by area type; search radius 600 / 1200 / 3000 m by density |

## Fail-loud blend (changed 2026-10-24)
A component that cannot be measured is left out, the remaining base weights are scaled proportionally to
sum to 1 (`pillars/social_fabric_blend.py`), and the pillar is marked degraded with the reason. Nothing is
scored as zero because it is missing. Before this, a missing component handed its weight to participation
(cohesion missing: participation 0.80; civic nodes zero: 0.70) and a missing stability reading counted as 0.
Civic nodes found to be zero are also left out (reported as `no_civic_nodes_found`, not degraded). Fewer than
two components, or no participation, means no score. The response carries `summary.weights_used` and
`summary.components_missing`. 286 of 1,476 catalog places changed score (mean +0.41).

## IRS nonprofit data coverage (changed 2026-10-24)
The IRS tract-count files have no tracts for DE, DC, IL, IN, IA, KY, MD, MI, MN, NC, OH, PA, SC, VA, WV, WI and
almost none for NE, ND, SD (the IRS regional file for them was never ingested). A state counts as covered only if the
files hold at least 30 tracts for it (`irs_bmf.state_has_coverage`). In an uncovered state the nonprofit rate is "no
data", not zero: participation uses volunteering and the Atlas civic-organization rate only
(`participation_mix: vol_only`), `summary.irs_bmf_status` is `no_state_coverage`, and the pillar is marked degraded.
If both inputs are missing there is no participation and no score (the old code returned a made-up 50). Rebuilding
the IRS files makes these states covered again with no code change. The IRS rate also showed no within-metro link to
loneliness in the CDC test and the baseline is dominated by outliers, so it is a weak input even where it exists.

## Caveats
- About 60% of the score comes from one source, the Social Capital Atlas (Facebook friendships). The base
  weights were chosen by validating against that same Atlas, so that validation is circular. Treat the
  weights as a judgment call. See `analysis/pillar_audit_tracker_v2.md`, D7.
- Our components track the Atlas economic connectedness (the measure that best predicts upward mobility)
  only weakly: cohesion 0.24, civic 0.11, rootedness -0.07; participation 0.36, almost all through Atlas
  volunteering. The registered-nonprofit rate has about zero correlation with any Atlas measure.
- Low-density affluent areas tended to score low under earlier versions (fewer walkable third places).
  That pattern was recorded under v14 and has not been re-checked under the current weights.

## Catalog
Rescored offline by `scripts/catalog/recompute_social_fabric_failloud_offline.py`, then
`recompute_catalog_composites.py --no-census` for longevity, happiness and aura.

## DPv2 spec sheet (Level 1, signed off 2026-11-04)

```
Pillar: social_fabric
Construct (one sentence): PROPOSED, owner to confirm: "How connected and civically active the people of a place are,
  with cross-class connection counted most." Today's code measures community participation and tenure; it does
  not measure the Chetty 2022 predictor of mobility (economic connectedness).
Reference frame: area-type norm for cohesion, IRS nonprofit rate and civic nodes; national norm for volunteering
  and the Atlas civic-organization rate. PROPOSED: national norm for every input.
  Evidence for the frame: tier 1 (Chetty et al. 2022, as summarized in DESIGN_PRINCIPLES_V2_DRAFT Part 4; not re-read
  here) supports an outcome-linked absolute scale. No evidence found for grading cohesion against similar places.
  Peer norms are unsupported (tier none).
Measurement area: mixed. Atlas inputs = ZIP. Rootedness = pin tract 0.7 + place 0.3. IRS rate = pin tract. Civic nodes =
  pin + 600/1200/3000 m circle chosen by tract density.
  Reason: none recorded. ZIP and tract are data-availability choices, not lived-neighborhood choices (principle 3).
Place context inputs used and remaining area-type uses:
  Reads area_type and density from the context. Area type still keys: cohesion bands, IRS baselines, civic band
  tier, civic imputed floor (flag off by default). None has a stated reason yet (principle 14 gap).
Inputs and data sources (with vintage):
  Atlas ZIP file (Facebook friendships, 2018-2022 era), ACS 2022 B25038/B07003 on 2020 tracts (tract layer
  tigerWMS_Census2020, verified in census_api.py), IRS BMF tract counts (uncovered in 16 states), OSM and
  Google Places civic nodes, CPS state volunteering (fallback).
Parameters: name | value | source | plausible range | sensitivity
  participation weight | 0.60 | judgment, validated against the same Atlas (circular) | unknown | not run
  cohesion weight | 0.20 | same | unknown | not run
  rootedness weight | 0.10 | same | unknown | not run
  civic weight | 0.10 | same | unknown | not run
  IRS / volunteering split | 50/50 | none | unknown | not run
  participation / Atlas civic-orgs split | 65/35 | none | unknown | not run
  rooted tract/place blend | 0.7/0.3 and 0.8/0.2 tenure/same-house | none | unknown | not run
  civic node type weights, density knots | 0.4 to 1.5; 2/8/18/40/75 per km2 | none | unknown | not run (knots feed diagnostics only)
  stability cliff | 85%, home value >= $350k | none | unknown | not run
  The "1.2 multipliers" no longer exist in code. They appear only in the retired formula in
  analysis/PILLAR_SCORING_EXPLANATION.md section 12. The live base weights above are the unsourced ones.
Shared inputs with other pillars: home value (rootedness cliff) overlaps housing; ZIP/tract affluence runs through
  Atlas volunteering and EC (overlap with status_signal and economic security, principle 5 test not run).
Pin-shift sensitivity: not run.
Independent validation source and result: none. Existing validation is circular (weights fit to the Atlas).
All-places check: not run for DPv2. Stored state 2026-11-03: n=1,476, 564 degraded, participation vol_only 255,
  cohesion left out 163, civic left out 152, rootedness left out 2, volunteering from state rates (CPS) 189.
Fail-loud conditions: component missing is left out and weights rescale; no participation or fewer than 2 components
  means no score. Gap: 189 places use a state-wide volunteering rate (every place in a state gets the same input).
Launch check pairs: not defined.
Known data limits: about 60% of weight rests on one source (Atlas); Atlas ZIPs not found for some places; IRS gaps in
  16 states; Atlas is Facebook users only.
Last re-validated: never.
```

### Economic connectedness audit (offline, stored catalog joined to Atlas by exact clustering and support values)

Effective weight by input, from the code: Atlas volunteering 19.5%, Atlas civic organizations 21%, Atlas clustering and
support (cohesion) 20%, IRS nonprofits 19.5%, tenure 10%, OSM civic nodes 10%. Economic connectedness itself: 0%.
Atlas-derived share is 60.5%, but none of it is EC. Under Chetty 2022, cohesion and civic engagement are the measures
that did not predict mobility, so 60% of the score sits on inputs the study found weak and 0% on the one it found strong.

Measured here (Spearman against the Atlas EC of the place's ZIP, 1,258 of 1,476 places joined with no ambiguity):
total pillar score 0.45, cohesion score 0.23, Atlas civic orgs 0.23, IRS rate 0.26 (n=1,020), tenure 0.11, civic node
density 0.02. Raw Atlas fields across 18,854 ZIPs with 1,000+ people: volunteering 0.46, civic organizations 0.19,
clustering -0.08, support ratio -0.23. Reading: the total correlates with EC mostly through volunteering, which tracks
affluence, and our area-type normalization turns the raw negative cohesion link positive. This is correlation with EC,
not evidence the score predicts mobility. Not verified: the Chetty paper itself (taken from the DPv2 draft summary).
The older note here says the IRS rate has about zero correlation; this run found 0.26, a difference not yet reconciled.

### Gap table

| # | Gap | Recommended fix | Expected score impact |
|---|---|---|---|
| 1 | No EC input; 60% of weight on inputs Chetty found non-predictive | Add Atlas `ec_zip` (already in `data/social_capital_zip.csv`, no API) as a component on a national scale | Large. Affluent ZIPs rise, low-EC ZIPs fall. Size known only after a recompute |
| 2 | Weights unsourced and fit to the same Atlas | List as TODO with range; cannot be sourced without an outcome that is not the Atlas. Run weight perturbation | None to score. Level 3 not reachable for weights |
| 3 | Area-type norms in cohesion, IRS rate, civic tier with no evidence | Move to national scale or state a reason per use (principle 14) | Moderate: urban cores rise on cohesion and IRS, suburbs fall |
| 4 | Single tract at the pin for rootedness and IRS | Run pin-shift first (needs Census calls, ask); then pool tracts if unstable | Unknown until pin-shift |
| 5 | 189 places use a state-wide volunteering rate | Leave volunteering out for those and rescale, per principle 16 | Small, 189 places move |
| 6 | Atlas inputs overlap affluence (status_signal, economic security) | Run overlap test across pillars (principle 5) | None to score, informs weights |
| 7 | Construct not stated; retired 1.2 formula still in analysis doc | Owner confirms construct; mark retired section stale | None |

### Level 2 pass criteria (fixed 2026-11-03 before the checks were run)

- Launch pairs "should differ": the two places' scores differ by 10 points or more. "Should be similar": 6 points or fewer.
  Differ: Mission District CA vs Homestead FL; Dogpatch CA vs Gary IN; Parker CO vs Clarkston GA.
  Similar: Sunnyvale CA vs Campbell CA; Potrero Hill CA vs Dogpatch CA.
- All-places: no more than 2% of places at or below 5 or at or above 95; spread (SD) in every area type with 30+ places at least 6.
- Weight perturbation (EC weight 0.15 and 0.45 against 0.20): median move 5 points or less, 95th percentile 15 or less.
- Overlap with status_signal: Spearman at or below 0.60 (principle 5).
- Pin-shift: median change 3 points or less and 95th percentile 10 or less at a 400 m shift (needs fresh tract and ZIP lookups; not run).
- Independent validation: see the brief below.

### Level 2 results so far (2026-11-03, stored catalog, n=1,476, no API calls)

Model v18: economic connectedness 0.20, participation 0.48, cohesion 0.16, rootedness 0.08, civic 0.08 (supersedes the
parameter rows above; the EC weight is a judgment call with plausible range 0.15 to 0.45, the others keep their old
proportions). Catalog recomputed into `analysis/dpv2_social_fabric_ec_composites/`; not yet copied over the live files.

| Check | Criterion | Result |
|---|---|---|
| Floor and ceiling | at most 2% at or below 5 or at or above 95 | PASS: 0 and 0 (range 22.4 to 76.8) |
| Spread by area type | SD at least 6 where n is 30 or more | PASS: suburban 10.4, exurban 10.1, rural 9.4, urban_residential 7.3 |
| Weight perturbation | median move at most 5, p95 at most 15 | PASS: EC 0.15 gives 0.7 and 2.5; EC 0.45 gives 3.3 and 10.4 |
| Overlap with status_signal | Spearman at most 0.60 | PASS: 0.46 (0.30 before EC) |
| Launch pairs, similar | gap at most 6 | PASS: Sunnyvale/Campbell 0.0; Potrero Hill/Dogpatch 3.0 |
| Launch pairs, differ | gap at least 10 | PASS: Mission District 55.2 vs Homestead 40.5 (14.7). FAIL: Dogpatch 51.9 vs Gary 44.9 (7.0); Parker 47.8 vs Clarkston 46.0 (1.8) |
| Pin-shift | median at most 3, p95 at most 10 at 400 m | PASS for the tract-based parts only: 60 places, 4 directions. Per-place mean change median 0.18, p95 1.53; worst direction median 0.53, p95 2.63, max 7.2 (Visitacion Valley CA). Highest in urban_residential (median 1.5), near zero in rural. Not covered: ZIP-based Atlas inputs (EC, cohesion, volunteering, about 70% of weight) and civic nodes, held fixed because ZIP and Overpass lookups were not authorized. A shift across a ZIP line would move the score more |
| Independent validation | see brief | NOT RUN |

The two failed pairs are reported, not re-chosen. At 20% weight a large EC gap is diluted by participation and
cohesion, which can run the other way (Parker's EC is high but its other components are not).

### Independent validation brief (for another agent; builder must not run it)

Goal: test whether the v18 score tracks outcomes it was not built from. Fix these before looking at results.
1. Data (downloads need owner permission; each into its own empty folder; run Python with `-I`): Opportunity Atlas
   absolute upward mobility for children from low-income families (county or tract file, Chetty et al.), and one CDC
   PLACES social support or isolation measure (runner confirms the exact field).
2. Inputs: the old and new social_fabric scores from `data/*composites_recomputed.jsonl` and
   `analysis/dpv2_social_fabric_ec_composites/*.jsonl`, joined to the outcome by county or tract FIPS from each place's
   coordinates (no live API; use local tract tables).
3. Pass criteria: (a) Spearman of the v18 score with upward mobility is at least 0.30 and at least 0.05 above the old
   score's; (b) the v18 score's Spearman with the PLACES measure (sign set so higher support is better) is at least 0.20 and
   not lower than the old score's; (c) both on the full catalog, not a subset, with n reported.
4. Caveat to report: upward mobility and EC come from the same research group and EC is correlated with income, so also
   report the partial Spearman after controlling for tract or county median income. A pass on (a) with a zero partial
   is recorded as "tracks affluence", not as validation.
5. Report: n, both Spearman values for old and new, the partial, and which of (a) to (c) passed.

### Proposed level

Level 1 (Converted) for sign-off, with these TODOs accepted: unsourced weights (range recorded), area-type bands still
used by cohesion, IRS rate and civic tier with no stated reason, 189 places on a state-wide volunteering rate. Not Level 2:
pin-shift and independent validation have not run, and two of three "should differ" launch pairs failed.

### Sign-off

Level 1 (Converted), signed off by the owner 2026-11-04. Accepted TODOs: unsourced weights (EC range 0.15 to 0.45 recorded);
cohesion bands, IRS rate and civic tier still keyed on area type with no stated reason; 189 places on a state-wide
volunteering rate; two failed "should differ" launch pairs (Dogpatch/Gary, Parker/Clarkston); pin-shift covers tract parts
only; independent validation not run (brief above); new catalog files in `analysis/dpv2_social_fabric_ec_composites/` not yet
copied over the live files; live `/score` not compared with the catalog. Last re-validated: 2026-11-03 (offline checks).

### v19 sign-off: economic connectedness removed from the blend (owner, 2026-11-04)

Construct: Social Fabric means felt connection and satisfaction in a place, not upward mobility. Economic connectedness
(EC, Chetty 2022) is no longer in the score. It is still computed and stored (`breakdown.economic_connectedness`,
`summary.economic_connectedness_raw`) as a separate measure, Economic Mixing / Bridging, not yet surfaced.
Blend: participation 0.48, cohesion (neighbor bonds) 0.26, rootedness 0.13, civic 0.13 (EC's 0.20 went to cohesion and
rootedness/civic, not to participation). These are design judgments, not fitted to any outcome.

Independent validation (run 2026-11-04, `analysis/social_fabric_dpv2_level2_validation_2026-11-04.md`): (a) Atlas mobility
PASS for v18 (0.426 vs 0.298, n=1,410), no longer a criterion for this pillar. (b) CDC PLACES felt support FAIL for v18 on every
variant (0.05 to 0.21; best coverage 1,266 of 1,476 places, no PA, CO, OR) and (c) not met. No US trust or belonging benchmark
with full coverage exists. Check after removing EC (v19, not used to refit weights): lack of social and emotional support,
sign flipped, Spearman 0.177 (n=856, 2023 file) and 0.177 (mixed-year union, n=1,266) vs 0.225 and 0.219 for the pre-EC blend; isolation 2022 0.134 (unchanged, n=1,019). EC removal did
not help the felt measure and slightly lowers it against the pre-EC blend on the support measure; accepted because the
weights are a design choice and (b) is an unstable yardstick. Catalog recomputed offline into
`analysis/dpv2_social_fabric_noec_composites/` (not yet copied over the live `data/` files). Score change vs v18: median 3.3
points, p95 10.2, max 18.7. Reopen if a felt-support benchmark with full coverage or mover-reported outcomes appear.

#### Level 2 checks rerun on v19 (2026-11-04, `analysis/dpv2_social_fabric_noec_composites/`, n=1,476, offline)

| Check | Criterion | v19 result |
|---|---|---|
| Floor and ceiling | at most 2% at or below 5 or at or above 95 | PASS: 0 and 0 (range 20.8 to 75.1) |
| Spread by area type | SD at least 6 where n is 30 or more | PASS: suburban 10.2, exurban 10.0, rural 9.1, urban_residential 6.5 |
| Overlap with status_signal | Spearman at most 0.60 | PASS: 0.235 (n=1,470) |
| Launch pairs, similar | gap at most 6 | PASS: Sunnyvale/Campbell 0.1; Potrero Hill/Dogpatch 2.4 |
| Launch pairs, differ | gap at least 10 | FAIL: Mission District 43.5 vs Homestead 48.6 (5.1). PASS on size only: Dogpatch 40.0 vs Gary 50.7 (10.7); Parker 36.6 vs Clarkston 53.8 (17.2) |
| Weight perturbation | EC 0.15/0.45 no longer applies | Substitute, not a fixed criterion: participation weight +-0.10 (rest rescaled) moves scores a median 1.3, p95 3.8; rootedness reconstructed from stored score (+-0.5) |
| Pin-shift | tract parts only | Not rerun; v18 result stands for tract parts, ZIP-based inputs never tested |
| Independent validation | see brief | FAIL for felt support (b), coverage unmet (c); see v19 sign-off above |

The written differ rule checks size only. In v19 the Dogpatch/Gary and Parker/Clarkston gaps pass on size but run the other way from the Mission/Homestead direction the earlier run used (the denser, wealthier place scores lower), and Mission/Homestead now fails on size. No expected direction was recorded for these pairs.
