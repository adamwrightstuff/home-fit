# Status signal: DPv2 spec sheet and audit

Level: 2 (Verified), signed off 2026-11-04 with failed checks accepted as TODOs (section 9). Not "validated" for user-facing copy: that needs every check to pass. Branch `status-signal-dpv2`, local only, not pushed.

Status signal is a composite beside the pillars, not a pillar. It has two parts that disagree with each other (see gap G1):
the class label (Struggling to Elite), documented in `docs/STATUS_SIGNAL_CLASS.md`, and the legacy 0 to 100 composite.
Trajectory (Up-and-Coming, Stable, Declining) is recorded in section 4 as kept.

Verified here: code read of `pillars/status_signal.py`, `pillars/composite_indices.py`, `data_sources/place_context.py`, and statistics from the
21 stored `*_composites_recomputed.jsonl` files (1,476 places, read 2026-11-04). Not verified: any external source (Pew, HUD, HHS were read only as
cited in the repo doc), pin-shift, independent validation. No API call or Overpass read was made.

## 1. Spec sheets

### Part A: class label

```
Pillar: status_signal class label
Construct (one sentence): The economic standing of the typical household in the place, from median household income and housing cost share only.
Reference frame: mixed. Struggling and Working Class use a fixed national standard. Affluent and Elite use a metro norm (top 20% and top 10% of the metro).
  Evidence for the frame: Struggling/Working: tier 1 (HHS poverty guideline; Pew two-thirds-of-median middle-income band; HUD 30% and 50% cost-burden
  thresholds, as cited in docs/STATUS_SIGNAL_CLASS.md, not re-read today). Affluent/Elite: none. The 20% and 10% shares are product definitions, and
  I found no study that says people judge affluence against their metro rather than the nation (tier 3 survey evidence on relative income concerns
  happiness, not class). Unknown.
Measurement area: the geography stored with the housing data (tract, incorporated place, CDP or county subdivision, whichever the lookup returned).
  Reason: none stated. 788 of 1,476 catalog places use an incorporated place, 495 a tract, 132 a CDP, 54 a county subdivision.
Place context inputs used and remaining area-type uses: none from the place context. The class does not read area type. The trajectory gate does (section 4).
Inputs and data sources (with vintage): ACS 2022 5-year B19013 median household income, B25105 median monthly housing cost, B25077 median home value;
  cutoffs from tract tables via scripts/baselines/build_class_cuts.py (ACS 2022, 2020 tracts; tract-vintage rule met by the Census2020 layer, census_api.py).
Parameters:
  poverty guideline $23,030 | HHS 2022, household of three | published | fixed | not tested
  two-thirds of national median ($75,149 x 2/3) | Pew convention | published | 0.6 to 0.75 unknown | not tested
  burden 30% and 50%, only below national median | HUD convention | published | contested (CRS: ratio and residual measures disagree) | not tested
  Affluent: income >= metro p80 | product definition | none | unknown | not tested
  Elite: income >= metro p90 and home value >= metro p90 | product definition | none | unknown | not tested
Shared inputs with other pillars: housing_value reads the same median income and home value (as a price-to-income ratio); diversity supplies education to the
  composite only; no overlap for the label with social_fabric, economic_opportunity or quality_education inputs.
Pin-shift sensitivity: not run. Reads one geography at the pin, so it is a likely unstable class (principle 6). Needs Census tract lookups at shifted pins (API); asked below.
Independent validation source and result: none yet. Candidate that needs no download: compare each place's class with its stored median income against the
  national household income distribution (ACS B19001 bins), a different construction of the same ladder. Not run.
All-places check (date, n, summary): 2026-11-04, n=1,476. Middle 907 (61.5%), Affluent 252 (17.1%), Elite 152 (10.3%), Working 145 (9.8%), Struggling 14 (0.9%),
  no class 6 (0.4%: Bronzeville, Hegewisch, Old Town, Westwood, Chinatown, Midtown; income or home value missing). Affluent plus Elite is 27%, close to the
  designed 20%, because the catalog is skewed to affluent places. Cutoffs are tract-median percentiles weighted by households, so they sit below true
  household percentiles.
Fail-loud conditions: income missing returns no class; code falls back to a wealth-band class when the cutoffs table is missing (code path exists, no catalog
  place uses it).
Launch check pairs: not yet run. Face-validity misses found in the audit: Beverly Hills CA (median income $116,771, mean $231,792, home value at the
  $2,000,001 topcode) is Middle Class; Greenwood Village CO (median $139,144, mean $251,400, home value $1.14M) is Middle Class; Brookline MA (median $130,600,
  home value $1.18M) is Middle Class. All miss the metro p80 because the cutoff is a tract-median percentile and the label reads the median.
Known data limits: ACS income topcode $250,001 and home value topcode $2,000,001; place medians versus tract-median cutoffs (units differ); student areas
  show housing cost above income (University City PA is Struggling with composite 60.4).
Last re-validated: never.
```

### Part B: legacy 0 to 100 composite

```
Pillar: status_signal composite (0 to 100)
Construct (one sentence): Not defined. The code comment says "socioeconomic standing"; the hotness weights comment says "wealth/credential concentration".
  It blends an income and home value index with education and occupation shares.
Reference frame: metro norm (min-max against the metro tract range, and a z-score of income and home value against the metro tract distribution), then
  weights that change with the class chosen by Part A.
  Evidence for the frame: none. Tier unknown.
Measurement area: same stored geography as Part A. Reason: none stated.
Place context inputs used and remaining area-type uses: none from the place context. Area type is passed in only for the trajectory gate.
Inputs and data sources (with vintage): mean household income and median home value (ACS 2022), graduate and bachelor share (ACS, via the diversity pillar), white-collar
  share (ACS S2401 via economic_opportunity), metro baselines in data/status_signal_baselines.json.
  Luxury business signal: not in the composite. The code computes it in data_sources/status_signal_luxury_osm.py but the final score never reads it, and
  luxury_presence is null for all 1,476 stored places. The task brief's description of the composite is out of date on this point.
Parameters:
  wealth = 0.70 z(mean income) + 0.30 z(home value), capped at +/-3, mapped to 0 to 100 | unsourced | unknown | not tested
  base weights wealth .37, home cost .26, education .21, occupation .16 | "provisional" in code | unsourced | unknown | not tested
  class-specific weights (Elite .42/.20/.22/.16; Affluent .35/.18/.28/.19) | unsourced | unknown | not tested
  education = 0.80 graduate share + 0.20 bachelor share, min-max | unsourced | unknown | not tested
  min-max ends from metro tract extremes | method choice | outlier-set | not tested
  signal-strength bands 25/50/75 | unsourced | unknown | not tested
Shared inputs with other pillars: see section 3. Home value enters the composite twice (inside wealth at 0.30, and as home cost).
Pin-shift sensitivity: not run. Same single-geography read as Part A.
Independent validation source and result: none. No independent source for "standing" beyond the label's own inputs.
All-places check (date, n, summary): 2026-11-04, n=1,470 scored. Median 51 for Middle, 78 Affluent, 95.5 Elite, 31 Working, 33 Struggling. Components at the ceiling:
  wealth 105, home cost 175, education 117, occupation 155 places at exactly 100. Elite p90 is 100.0.
Fail-loud conditions: home cost missing is dropped and the weights renormalized (32 places); wealth, education and occupation missing are also dropped. Violations of
  principle 16: wealth uses a z of 0 when home value is missing; education uses 50 when a baseline is missing; occupation uses 50 when a baseline is missing.
Launch check pairs: not run. Internal check run: label versus composite. 11.5% of all class pairs are inverted (a lower class scores higher than a higher
  class); examples: Kenwood Chicago Working Class 82.7, Rosedale Austin Middle Class 94.2, Greenwood Village Middle Class 98.3, Odessa FL Elite 72.4.
Known data limits: same as Part A, plus ACS education and occupation shares are tract or place shares, not residents' own.
Last re-validated: never.
```

## 2. Should the 0 to 100 composite exist next to the label?

Not as it is. It measures no stated construct, its weights are unsourced, it shares a stored geography and a metro frame with the label yet disagrees with it
on 11.5% of class pairs, and the luxury signal the brief names has been dead code for the whole catalog. A number is still useful because hotness (weight 0.30)
and aura (weight 0.15) consume it and the UI shows signal-strength bands. Recommendation in section 5: keep a number, but derive it from the label's own inputs so
the two cannot disagree.

## 3. Overlap and double counting

Spearman against the composite, 1,466 to 1,470 places: quality_education 0.61, social_fabric 0.46, diversity -0.57, community_safety 0.29, natural_beauty 0.33,
healthcare 0.27, economic_opportunity 0.16, climate_risk 0.14, amenities 0.12, transit 0.13, housing_value 0.01.

Shared inputs found in code (these are the double counts):
- diversity: education attainment is read from the diversity pillar's own details. The strong negative correlation is a composition effect, not a shared formula.
- economic_opportunity: white-collar share is read from the pillar's breakdown, so the same ACS number feeds both.
- housing_value: same median income and home value, but housing_value scores their ratio, so correlation is near zero (0.01). Low double-count risk.
- social_fabric: stability is read only for trajectory; social_fabric also reads median home value (line 442 of its module). Low risk for the composite. The 0.46 is mostly income driving both.
- quality_education: school scores, not ACS attainment, so no shared input. The 0.61 is a place-income effect.

Test: dropping education and occupation from the composite changes the overlap very little (quality_education 0.61 to 0.60, social_fabric 0.46 to 0.44, diversity -0.57 to -0.52).
Most of the overlap is income itself, so removing those two inputs avoids the shared-input double count but does not reduce the correlation. Do not promise the overlap will fall.

## 4. Trajectory (kept as-is, documented only)

Decided 2026-10-08: no better replacement found; not rebuilt here. Fixed 2026-06-22: dead area_type literal, zip_code never threaded, education zeroing the Elite ceiling.
Known TODO, not new: the 3% decline cut and the 5% and 10% appreciation cuts were set by eyeballing and need Zillow, FHFA or academic grounding. Descriptive fact from the catalog:
306 of 1,476 places (21%) are Declining, concentrated in Austin 58, Dallas 33, Tampa 28, San Antonio 24; 43 are Up-and-Coming. The Up-and-Coming gate keys on the area-type label
(urban_core or urban_residential), which principle 14 says should move to a continuous place-context factor; recorded as gap G6.

## 5. Audit gap table

| # | Gap | Recommended fix | Expected score impact |
|---|---|---|---|
| G1 | Label and composite disagree: median income plus metro-p80 cut for the label, mean income z-score plus education and occupation for the composite. 11.5% of class pairs inverted. | Define the number from the label's inputs (see option C). | Composite moves a median 4.8 points, p90 11.9, max 24 (estimated from stored wealth and home cost). Label unchanged. |
| G2 | Luxury signal documented as part of the composite but not used; luxury_presence null in 1,476 of 1,476. | Remove from docs and the dead branch, or state it is retired. | None. |
| G3 | No stated construct or frame for the composite; weights unsourced; weights depend on the class. | Resolved by option C (no weights beyond the two inputs, each with a stated source). | See G1. |
| G4 | Neutral substitutions (principle 16): z of 0 for missing home value, 50 for missing education or occupation baseline. | Drop the component and scale over the rest, or mark degraded. | Small. Count of places affected not yet measured offline (needs the missing-baseline test, no API). |
| G5 | Affluent and Elite cutoffs have no evidence tier, and the label calls Beverly Hills, Greenwood Village and Brookline Middle Class. | Owner decision on the frame: national fixed ladder (Affluent above some multiple of national median) versus metro rank. Cannot be settled by data alone. | A national ladder would move many places in the Denver, LA and Boston metros up one class and some in cheap metros up as well; size unknown until built. |
| G6 | Up-and-Coming gate keys on the area-type label (principle 14). | Use the place context's activity per acre once a threshold has a source. | Small: 43 places carry the badge. |
| G7 | Tract-sized cutoffs compared to place medians (units differ), topcodes at $250,001 and $2,000,001. | Build cutoffs on the same geography the label reads, or label the topcode ceiling. | Unknown. |
| G8 | Pin-shift, independent validation, launch pairs never run. | Level 2 steps after approval. | None (measurement). |
| G9 | UAC cutoffs unsourced. | Known TODO; Zillow, FHFA or academic grounding. | Not scoped. |
| G10 | Status signal and the composites recompute: the recompute script with --no-census preserves the stored number, so any change needs its own offline recompute into new files. | Write `scripts/catalog/recompute_status_signal.py` that reads stored wealth, home cost and class inputs. | None. |

## 6. Options

A. Document only. Level 1 with TODOs recorded. Nothing changes. Keeps G1 and G3 open.

B. Drop education and occupation, keep the wealth and home-cost blend. Removes two shared inputs and the class-dependent weights. Estimated against the label: Spearman 0.689 versus 0.700 now, inversions 12.1% versus 11.5%. It fixes the double count but not the disagreement.

C. Recommended. Keep a 0 to 100 number, built from the label's inputs: a piecewise-linear position through the class cutoffs (poverty guideline, two-thirds of median, class boundaries, metro p80 and p90), so a higher class can never score lower than a lower class. Drop education and occupation (already in quality_education, economic_opportunity and diversity), drop the luxury code, add a degraded flag instead of neutral substitutions. Label unchanged. The frame question (G5) stays open for you and is a separate decision.

D. Retire the number. Hotness and aura would need a replacement input; more work and the UI bands go away.

Decision I need before changing anything: option A, B, C or D, and whether to take G5 (frame for Affluent and Elite) as a separate step.

Data a change needs: C uses only stored wealth inputs, class cutoffs and housing summary fields, so the catalog recompute is offline into new files. Level 2 needs data that is not stored and I will ask before each: tract lookups for pin-shift (Census geocoder, API), ACS B19001 bins for the independent check (small Census pull), nothing from Overpass.

## 7. Change made (option C, 2026-11-04, awaiting owner review of the diff, not pushed)

The 0 to 100 number is now the class-position score: 20 x class index + 20 x the place's median household income position inside its class income range. Range ends are the label's own
cutoffs (poverty guideline, national median, metro p80 and p90) and the ACS income topcode of $250,001 for Elite. Education, occupation and the housing-cost blend no longer enter it; a place
with no income gets no class and no score; a place with no housing cost keeps its score and is flagged degraded (`housing_cost_missing_burden_test_skipped`). The label's cutoffs and the
trajectory are unchanged. Index version 6 to 7.

Parameters of the new score: the only unsourced one is the equal 20-point class bands (a scale choice, plausible range unknown). An earlier draft added 2x and 1.5x ceilings; they were invented
numbers, removed the same day, and not shipped. The luxury code stays in the repo because other scripts import it; it is not in the score.

Catalog recompute (offline, new files in `data/status_class_position/`, originals untouched, `scripts/catalog/recompute_status_class_position.py`):
- Class re-derived from stored inputs matched the stored label for 1,476 of 1,476 places; the live function matched the recompute for 1,476 of 1,476 (checked on the earlier draft; rerun the check after review).
- Class inversions: 71,034 of 615,211 pairs (11.5%) before, 0 of 573,694 after pooling (section 9).
- Spread after pooling, n=1,469: 10th 41.4, median 52.7, 90th 80.0 (before pooling 38.4 / 52.5 / 80.5). By area type (10th / median / 90th): exurban 43.0 / 56.1 / 88.2; suburban 37.1 / 51.3 / 80.0; rural 41.5 / 53.7 / 84.8; urban residential 30.1 / 50.4 / 76.8.
- Ties (known limit, principle 10): after pooling 67 of 240 Affluent places tie at 80 (over the p90 income line, under the p90 home value line) and 35 of 138 Elite places tie at 100 (income at the topcode); all 6 Struggling places sit at exactly 20.0 (their income position is clipped). Nothing is at the floor.
- Downtown Los Angeles has no income and carried the default label Struggling; it now has no class and no score (1 place). No score now for 7 places in total.
- Examples: Beverly Hills 93.0 to 57.4, Greenwood Village 98.3 to 59.9, Kenwood 82.7 to 33.5, Odessa FL 72.4 to 81.8. Aura (status weight 0.15) moves 1.8 points on average, 8.7 at most.
- Overlap with the composite (Spearman, before to after, earlier draft): economic_opportunity 0.16 to 0.08, diversity -0.57 to -0.43, quality_education 0.61 to 0.63, social_fabric 0.46 to 0.43.
- Tests: `tests/test_status_signal_class_position.py` (7) and `tests/test_status_signal_strength.py` (2) pass. `test_preference_filters`, `test_composite_total_gap` and `test_metro_agent_changes` need pytest, not installed in the venv available, so they were not run.

## 8. Remaining area-type and neutral-value uses (principles 14 and 16)
- The Up-and-Coming trajectory gate reads the area-type label (urban_core or urban_residential). Reason: trajectory is kept as-is by the 2026-10-08 decision; moving it to the place context's activity per acre needs a sourced threshold. TODO.
- `compute_wealth` substitutes a z of 0 for a missing home value. It no longer feeds the score; it still feeds the trajectory's `_has_pressure` test and the display driver. TODO.

## 9. Level 2 results (2026-11-04, catalog and archived Census pull, no new Census calls, run by the builder so not independent)
Criteria were fixed in `docs/STATUS_SIGNAL_LEVEL2_BRIEF.md` before any run. First pass (single-tract label, section below) failed pin-shift. Fix applied: the label reads the same pooled tracts as the
housing pillar (D14: tracts under the pin and 8 ring points at 700 m, occupied-unit weighted). Live scoring gets this from `HOMEFIT_HOUSING_POOLED=true` with no code change here; the catalog uses
`scripts/catalog/pool_status_class_inputs_offline.py`, which reads the cached state pull from the archive folder (`home-fit-archive-2026-11-05/data/census_pull_2026-10-28`) and the tract centers table.
Pool membership is approximate (tract shape as a disk of its land area): the pooled home value differs from the live-geocoder pool by a median 2.8% (90th percentile 14.0%; 215 of 494 within 2%).
Monthly housing cost is not in that pull, so pooled places keep their single-tract burden ratio (cost over income) applied to the pooled income. Pooling changed the class of 132 of 495 single-tract places.

| Check | Result | Pass? |
|---|---|---|
| 1 Pin-shift (500 m N/E/S/W, 216 shifts, tract-level places; 54 places, not 60, because only 6 Struggling places read a tract) | pooled: median 1.4 points, p95 13.7, class unchanged 85.2%. For comparison, single-tract: median 1.3, p95 28.5, class unchanged 74.5% | PASS (limits 5, 20, 80%) |
| 1 Neighbor spread, 71 tract-level pairs within 1 km (amendment proxy, now superseded by the true shift) | median 4.1, p95 23.9, same class 69% | informational |
| 2 All places | 0 inversions in 573,694 pairs; none at the floor; largest tie share in an area type with 100+ places 8.6% | PASS |
| 3 Differ pairs | Scarsdale 100 vs Mount Vernon 43.9; Atherton 100 vs East Palo Alto 47.4; Highland Park 82.1 vs Englewood 21.3 pass; Palo Alto 72.3 vs East Palo Alto 47.4 is 24.9 apart (limit 25) | FAIL by 0.1 |
| 3 Similar pairs | Wicker Park 83.4 vs Bucktown 79.3 pass (was 85.7 vs 59.3); Park Slope 84.9 vs Carroll Gardens 59.7 fail (pooling moved Carroll Gardens from 81.8); Brookline 56.2 vs Newton 80.2 fail (both place-level, unaffected by pooling); 1 of 3, needed 2 | FAIL |
| 4 Independent proxy (B19001 income bins are not in the pull, so the original statistic was not run) | Spearman with mean household income 0.877 and median gross rent 0.664 pass; median home value 0.581 (limit 0.60) fail; median home value by class Struggling 533k, Working 345k, Middle 428k, Affluent 697k, Elite 1.15M, not strictly rising | FAIL (proxy); original NOT RUN |

Independent rerun (a separate agent session with its own code, same brief, 2026-11-04): checks 1 and 2 pass, check 3 fails, check 4 proxy fails on home value; original check 4 not run. Its 21 output files are byte-identical to the builder's.
Pin-shift pooled: median 1.80, p95 14.05, class unchanged 82.4% (single-tract p95 27.32, 77.6%). Four tract-level places shift more than 20 points (Tribeca 24.5, Bryker Woods 24.5, SoHo 21.9, Candler Park 21.5). Pair scores, inversions (0 of 573,694),
tie shares (largest 8.6%) and the Spearman values (0.877, 0.665, 0.581) match the builder's. Verdict matches on every check; small numeric differences come from the shift sampling (pin-shift) and rounding. Originals in `data/` unchanged (git diff empty).

Reading: the ladder, the ordering and the geography problem are fixed (pin-shift passes; single-tract fails the same test). Remaining misses are about what a median income can say. Brookline (median
$130,600) is Middle Class by metro rank while Newton is Elite; Palo Alto sits one 0.1-point short of a pair threshold I set; the 13-to-6 Struggling places are student and downtown tracts with high home
values. These are properties of the construct (typical household income against a metro rank), not bugs; changing them means changing the label's definition, which is the owner's call (gap G5).
Not run: B19001 share of households over $200,000 (needs data not in the repo); true live-geocoder lookups at shifted pins (membership is the disk approximation).

Level 1 (Converted) signed off. Level 2 proposal for owner decision (checks run and independently rerun; launch pairs and the home-value proxy still fail): Level 1 basis: spec sheet filled, frames declared with evidence tiers (Affluent and Elite frame: none), no shared place facts to take from the place context, remaining uses of the area-type label listed with reasons, no neutral value in the score.
Accepted TODOs to list in the sign-off line: equal 20-point bands unsourced; Affluent and Elite cutoffs (20% and 10% shares) are product definitions; UAC thresholds unsourced; trajectory area-type gate; compute_wealth neutral z; cutoffs are tract-median percentiles compared with place medians; Level 2 run offline and not met (section 9).
Sign-off: Level 1 (Converted), signed off by the owner (Adam Wright), 2026-11-04, with the TODOs listed above accepted.
Sign-off: Level 2 (Verified), signed off by the owner (Adam Wright), 2026-11-04. Checks run by the builder and independently rerun by a separate agent session. Accepted as TODOs: launch pairs (Palo Alto vs East Palo Alto 24.9 against 25; Park Slope vs Carroll Gardens and Brookline vs Newton not within 15); median home value proxy (Spearman 0.581 against 0.60, class ordering not strictly rising); original B19001 check not run; pin-shift uses approximate tract disks; four tract places shift over 20 points. Product copy must not call status signal validated.

## 10. Household route to Affluent (adopted 2026-11-05, owner approved; catalog files not yet swapped, not pushed)
Why: the label read the median income against a metro rank, so Beverly Hills, Brookline and Greenwood Village (43 to 48 percent of households at $150,000 or more) were Middle Class. Round 1 and round 2 tests are in docs/STATUS_SIGNAL_STEP2_TEST.md (round 1: dropping the burden test or using a national ladder fits household data worse, so both stay as they were; round 2: the household route passes all checks except the 15 percent movement limit, 15.2 percent, which the owner accepted).
Change: a place that would be Middle Class becomes Affluent (`class_affluent_households`) when the share of households at $150,000 or more (ACS B19001 bins 016 and 017) is at or above 37.55 percent, stored as `class_national.affluent_household_share_150k_cut`. It never lifts a place the burden tests demoted, and with no share the place is classified on income alone. Live scoring now fetches the two bins with the housing data (`share_households_150k_plus`, pooled by occupied units when pooling is on). The tooltip for these places says "Many households earn $150,000 or more, though the typical household sits below the top fifth of this metro."
Offline recompute (`scripts/catalog/recompute_status_class_position.py --pooled ... --out-dir data/status_class_position_v2`, new files only): 223 of 1,476 places change class, all Middle Class to Affluent (100 at pooled places, 123 at stored geography); only status_signal, its breakdown and aura (it_score) differ from the current files (0 other fields changed); 221 scores change (mean +5.5, max +14.9); aura moves in 220. Beverly Hills 57.4 to 60.0, Brookline 56.2 to 60.0, Greenwood Village 59.9 to 60.0, Carroll Gardens 59.7 to 60.0.
Checks on the new files: inversions 0 (class score ranges do not overlap: Working 21.3 to 39.4, Middle 40.2 to 59.9, Affluent 60.0 to 80.0, Elite 80.2 to 100.0). Largest tie 60.0 for 223 places (15.2 percent); by area type urban residential 21.8, suburban 17.3, exurban 10.9, rural 7.0, all under the 25 percent limit. Launch pairs: Brookline 60.0 vs Newton 80.2 (20.2 apart, limit 15), Park Slope 84.9 vs Carroll Gardens 60.0 (24.9 apart, limit 15), Palo Alto vs East Palo Alto unchanged at 24.9: still failing, as accepted on 2026-11-04.
Known limits and open gaps:
- All 223 places sit at exactly 60.0 because their median income is under the p80 line, so the position inside the Affluent band clips to 0. Spreading them would need a position scale that is not sourced; reported, not tuned.
- The share is stored per tract or place and is not pooled in the catalog (the pooled pull has no income bins), so pin-shift for this rule was not measured; live scoring pools it when HOMEFIT_HOUSING_POOLED is on, so live and catalog can differ for tract places.
- The 37.55 cut is a product definition from the catalog's own medians, and $150,000 is a national line applied in every metro (San Francisco carries 66 of the 223).
- The Explorer archetype compass and the live scorer's cached housing data: cached entries made before this change have no share and classify on income alone until they expire.
Level: the class rule changed, so the Level 2 sign-off of 2026-11-04 applies to the previous rule; this change is Level 1 (specified, tested offline) until the owner signs off Level 2 again.

## 11. Label pool narrowed to 350 m (owner decision 2026-11-05; catalog files not yet swapped, not pushed)
Why: the 700 m pool smeared neighbors into each other (Carroll Gardens $1,296 under the NYC p80 line, Gowanus $4,511 over the p90 line, order reversed against the pin tract). Test and criteria: docs/STATUS_SIGNAL_GEOGRAPHY_TEST.md. The 350 m pool met 3 of 4 named pairs within 15 points (700 m: 1 of 4), kept the pin-shift check passing (median 1.5, 95th percentile 16.2, class unchanged 89.2%), and failed the neighbor-spread proxy as every geography did (owner accepted).
Change: tract-level places read the tracts under the pin and an 8-point ring at 350 m for the status label (income, home value, monthly cost, mean income and the household share at $150,000 or more). Live: `census_api.get_status_pool_summary` (`STATUS_POOL_RING_M = 350`), applied in `main._housing_at_status_pool` only when the housing read is tract-level; place-level reads and a failed pool fall back to the housing pillar's summary. The housing value pillar keeps its own 700 m pool (D14), so the two use different geographies; this is a deliberate divergence, not an oversight. Catalog: `recompute_status_class_position.py --pooled pooled_350.json --ring-m 350` (pool built by `pool_status_class_inputs_offline.py --ring-m 350`), new files in `data/status_class_position_v3/`.
Offline recompute vs the current catalog files: 43 classes change (Elite to Affluent 5, Affluent to Elite 11, Middle Class to Affluent 3, Affluent to Middle Class 4, Working Class to Middle Class 6, Middle Class to Working Class 13, Working Class to Struggling 1); 339 scores change (mean absolute change 4.1, up to +28.4 and -23.1); aura moves for 338; no field outside the status signal, its breakdown and aura changes. Inversions 0 (class score ranges do not overlap); largest tie 60.0 for 216 places (14.7 percent), every area type under 25 percent (urban residential 21.8, suburban 16.2).
Named places (score before to after): Carroll Gardens Affluent 60.0 to Elite 83.6, Gowanus 81.1 to 81.7, Park Slope 84.9 to 90.5, Cobble Hill 83.6 to 82.7 (all Elite, within 9 points); Wicker Park 83.4 to 85.1 and Bucktown Affluent 79.3 to Elite 81.7; Murray Hill 75.3 to 64.9 (Affluent); Boerum Hill 78.0 to 70.7 (Affluent); Brookline and Newton unchanged at 60.0 and 80.2; Beverly Hills, Palo Alto, East Palo Alto, Coconut Grove unchanged.
Known and open: the catalog holds the single-tract burden ratio (the archive has no pooled monthly cost) while live pools the cost, so live and catalog can differ slightly; Coconut Grove and about 98 other neighborhoods are read at city level (a separate geography bug, not changed here); 13 places drop from Middle Class to Working Class because the narrower pool sees a poorer immediate area; Brookline and Newton remain 20 apart; Palo Alto above East Palo Alto remains 24.9 against a limit of 25.

## 12. Neighborhoods read as their whole city, repooled (offline, 2026-11-05; catalog files not swapped, not pushed)
Why: `get_housing_data` reads place-level data for any pin inside an incorporated place with 200,000 or fewer occupied units (the ceiling is unsourced), so Coconut Grove was read as the City of Miami (income $54,858, 70 percent renters, burden 33 percent: Working Class) while its household brackets came from its own tract (64 percent of households at $150,000 or more). The diversity read applies the same ceiling to adults, not occupied units, so the two reads disagreed. 99 catalog neighborhoods (type neighborhood, geo_level incorporated_place) were read this way, in Miami, Tampa, Raleigh, Oakland, Sacramento, Henderson, Phoenix and others.
Change (catalog only): `scripts/catalog/pool_neighborhood_city_level_offline.py` pools the tracts under the pin and an 8-point ring at 350 m from the archived pulls (housing_tract and div_tract, no Census calls); `recompute_status_class_position.py --pooled-nbhd` reads them for the status label (income, home value, share of households at $150,000 or more). The city burden ratio is held because the archive has no tract monthly cost. All 99 rows with before and after: docs/STATUS_SIGNAL_CITY_LEVEL_NEIGHBORHOODS.md.
Results vs the current catalog files: 42 of the 99 change class (Affluent to Elite 12, Middle Class to Affluent 13, Middle Class to Elite 4, Middle Class to Working Class 6, Affluent to Middle Class 4, Working Class to Affluent 1, Working Class to Elite 1, Working Class to Middle Class 1); 95 scores and 95 aura values change; no field outside the status signal, its breakdown and aura changes and nothing outside the 99 changes. Inversions 0; largest tie 60.0 for 198 places (13.5 percent); every area type under 25 percent (urban residential 21.2). Examples: Coconut Grove Working Class 32.2 to Elite 100.0 (its tract income is at the ACS cap of $250,001, so the true median is higher; flagged `income_topcoded`), Brickell Working Class to Affluent 76.6, Hyde Park (Tampa) Affluent 60.0 to Elite 83.5, Snell Isle Middle Class 48.8 to Elite 84.7, Anthem Middle Class 54.6 to Elite 86.8. Check: the pooled share for Coconut Grove (63.93) equals its stored tract brackets (63.9), so the pin tract matches the tract the diversity read used.
Open: the live scorer still cannot tell a neighborhood search from a city search, so live scores keep the place-level read until the geocoder's place type (or another rule) is used; the 495 tract-level places still carry an unpooled household share (the archive can pool it, not done here); the pin tract for these 99 is the nearest tract disk, not a live-geocoder lookup.
