# Longevity index: DPv2 spec sheet and audit

Level: 0 today (no spec sheet before this one). Proposed after audit: 1 at most, pending owner approval. Nothing in scoring or copy has changed. Branch `longevity-dpv2`, worktree `home-fit-longevity`, cut from origin/main 88c31ed1 (fetched 2026-11-06). Old design notes: `analysis/LONGEVITY_INDEX.md` (v5, 2026-10-08). Format follows `HAPPINESS_INDEX.md`.

Method limits, stated once: no source was re-read in this session. Study names below are as written in the code or recalled, and are marked "unverified" where I could not confirm them. Offline numbers come from stored catalog files only (1,476 places, 21 metros, no API calls).

## 1. Spec sheet

```
Index: Longevity index (index version 5), 0 to 100, a composite beside the pillars, not a pillar
Construct (one sentence): a fixed-weight summary of seven neighborhood conditions that health research
  links to longer lives, describing the place; it does not forecast how long anyone who lives there will
  live, and no test so far shows it tracks measured life expectancy beyond local income and education.
Reference frame: none of its own. Each component keeps its pillar's frame. Weights are judgments.
  Evidence for the frame (tier 1 published study | tier 2 price or migration proxy | tier 3 survey):
  Tier 1 exists for the direction of five inputs at the individual level (section 2). Tier 1 for the
  bundle or the shares: none. Tier 2: none. Tier 3: none.
Measurement area: inherited from each pillar (pin and radius, tract, ZIP, place). Index adds none.
Place context inputs: none read directly. Area type is not used in the formula.
Inputs: stored pillar scores (live response and catalog). Climate slot is air quality (5/8) and heat (3/8)
  from stored sub-scores aqi_score and lst_score; flood and warming trend are excluded.
Formula: weighted mean over usable pillars, renormalized. Backend drops a pillar that failed, has
  no data, has confidence 0, or (when a token allocation is present) has allocation weight 0.
Parameters (weight | source | plausible range | sensitivity | tier):
  social fabric          35 | Holt-Lunstad 2015 meta-analysis, as cited in code (unverified here) | TODO | drop it: rank corr 0.954, mean move 6.1, max 17.0 | 1 for individual isolation, none for the area proxy
  active outdoors        22 | "Li 2019 JAMA" and "Kokkinos 2022 NEJM" as cited in code; attribution not confirmed, see 2 | TODO | drop it: rank corr 0.946, mean move 3.2, max 12.4 | 1 for greenness, none for park and trail access
  neighborhood amenities 15 | Blue Zones "move naturally" idea, no study | TODO | none | none
  climate (air and heat)  8 | Pope 2009 (as cited in code); PM2.5 mortality literature | TODO | | 1 for air, weak for satellite heat
  community safety        8 | "chronic stress", no citation in code | TODO | | 1 for homicide and violence as causes of death, none for stress pathway
  natural beauty          5 | "stress reduction", no citation | TODO | | none
  quality education       3 | Cutler and Lleras-Muney 2008 (as cited in code) | TODO | drop it: rank corr 0.998, mean move 0.4 | 1 for adult schooling, not school quality
  Ranges: no evidence-derived ranges exist for any weight. Every range is TODO, not invented.
Excluded (reason): healthcare (removed v3 because the pillar then measured OSM clinic density; the pillar
  was rebuilt as drive time to hospitals, so the reason is stale, see G5), housing value and economic
  opportunity (income is the confounder, not a neighborhood mechanism), public transit, air travel,
  diversity, built environment, political lean (no individual-level mortality evidence found or relevant).
Personal settings, not weights: none today.
Shared inputs with other pillars: climate_risk feeds both this index and happiness; status-like wealth
  leaks in through safety and education (section 3).
Pin-shift sensitivity: inherited, not an index property.
Independent validation: failed to show signal in 2026-10-09 test (section 3). Fixed-criteria rerun in section 5, not yet run.
All-places check: section 4.
Fail-loud conditions: failed pillar drops out and renormalizes. No field says which pillars were dropped
  or how much weight remained (gap G6). Climate falls back to the full pillar score when a sub-score is
  missing (gap G4).
Launch check pairs: section 5, written before any score is looked at.
Known data limits: education missing for 527 of 1,476 places (allocation 0), safety missing for 56,
  amenities missing for 45; 15 places use the full climate score because lst_score is absent.
Last re-validated: never under DPv2.
```

## 2. Construct audit: does each weight's evidence apply to today's pillar?

Check 1. Individual-level evidence is about a person's exposure. Each pillar now measures something else, so the match is the question.

| Pillar (weight) | Individual-level evidence | Pillar as it stands (DPv2 rebuilds) | Evidence still applies? |
|---|---|---|---|
| Social fabric (35) | Social isolation, loneliness and living alone each raise mortality about 26 to 32 percent in a meta-analysis (Holt-Lunstad 2015, tier 1, individual relationships, unverified here) | Area proxy: economic connectedness 0.20, participation 0.48, cohesion 0.16, rootedness 0.08, civic 0.08 (v18, 2026-11-04). Objective area rates, not any person's ties | Direction yes, size no. No study links these area rates to mortality. Chetty 2022 links economic connectedness to upward mobility, not death |
| Active outdoors (22) | Greenness exposure and lower mortality (recalled as Rojas-Rueda 2019 Lancet Planetary Health, not "Li 2019 JAMA"; the "12 to 24 percent" in code does not match my memory, unverified). Physical activity and mortality is strong (tier 1) | Typed parks and clean trail count within a walk radius (2026-11-03 and 04). Access to parks, not greenness exposure or activity done | No for the construct. The nearest match to the greenness evidence is the green-view part of natural beauty, weighted 5. Fix the citation before reuse (G2) |
| Amenities (15) | None found for the pillar. Walking for transport has individual benefit but the pillar is not walking time | Supermarket-only grocery access, linear decay 400 to 1,200 m (per `HAPPINESS_INDEX.md`; not re-checked in code) | No. Construct is food access. Weight has no source. Stored sign against life expectancy is negative (section 3) |
| Climate air and heat (8) | PM2.5 and mortality is the strongest tier 1 here (Pope 2009 as cited; Di 2017 NEJM individual-level, cited in `PILLAR_CLIMATE_RISK.md`, not re-read here) | Air is measured tract PM2.5 (since 2026-10-25, replaced a dust-sensitive proxy). Heat is satellite land surface temperature at 500 m | Air: yes, better than at v5. Heat: weak, heat mortality is about air temperature and heat waves, LST is a proxy |
| Safety (8) | Homicide and violence are causes of death (tier 1, obvious). "Chronic stress" has no study cited | National percentile of Part I crime, property crime weight 0.098, by crime type | Partly. Violent crime is the part with a mortality route; the Part I blend is mostly property crime. The 2026-10-09 test found only violent crime |
| Natural beauty (5) | Greenness and mental health yes; scenery and water no mortality study | Two-part streets and scenery, one 800 m green view radius | Streets part loosely; scenery no |
| Education (3) | Each extra year of adult schooling lowers mortality (Cutler and Lleras-Muney 2008 as cited) | Assigned-school proficiency, state percentile (children's school quality). Missing for 527 places | No. The evidence is about a person's own schooling. School quality of an area is a different construct and here it proxies area affluence (section 3) |

## 3. Confounding: what the index adds after controlling for wealth and education

Control set, stated before the numbers: stored wealth percentile (`status_signal_breakdown.wealth`) and stored education percentile (`classifier_inputs.education`). Outcome: CDC USALEEP tract life expectancy 2010 to 2015 (e0), mapped by `scripts/catalog/map_catalog_to_usaleep.py` at the pin tract. This is exploratory, not the section 5 test: controls are place-level and may be metro-relative, the sample is New York 174, Los Angeles 96, San Francisco 105, Seattle 2 (n = 376 with controls; the 2026-10-09 run reported 385, I did not recover why), and the pin tract may not represent a town.

| Score | Raw r | Partial r (after wealth and education) | Added R2 |
|---|---|---|---|
| Controls alone | | | 0.304 |
| Longevity index | +0.38 | +0.07 | +0.003 |
| Social fabric (35) | +0.34 | +0.10 | +0.006 |
| Active outdoors (22) | +0.11 | -0.09 | +0.006 |
| Amenities (15) | -0.15 | -0.12 | +0.010 |
| Climate air and heat (8) | +0.22 | +0.01 | 0.000 |
| Natural beauty (5) | +0.35 | +0.07 | +0.004 |
| Education (3) | +0.52 | +0.27 | +0.051 |
| Safety (8) | +0.48 | +0.25 | +0.045 |

By metro, index partial r: New York +0.03, Los Angeles +0.20, San Francisco +0.15.

Reading: this reproduces the 2026-10-09 result. The index adds nothing measurable beyond wealth and education. The two inputs that do carry signal are the two with the smallest weights (education 3, safety 8). Education's signal after the controls reads as a leftover wealth and age proxy, not a schooling effect, so it should not be promoted. Weights that survive: none of the heavy ones. Social fabric keeps the right sign and a small partial (0.10); active outdoors and amenities do not hold. Not verified: whether the controls are loose enough to hide a real effect (they explain 30 percent of e0, so a stronger control set could move these).

## 4. All-places check (stored data, n = 1,476, 2026-11-06)

- Stored index equals the backend formula recomputed from stored pillars for all 1,476 rows.
- Mean 59.8, SD 9.9, 5th to 95th percentile 43.5 to 75.7, range 29.7 to 81.5. Spearman with the happiness index 0.712, with the stored wealth percentile 0.547.
- Pillars used in the stored index: social fabric 1,476, active outdoors 1,476, climate 1,476, natural beauty 1,475, amenities 1,431, safety 1,420, education 949.
- Share of index variance versus nominal weight: social fabric 28.6 (35), active outdoors 26.6 (22), amenities 21.2 (15), safety 10.4 (8), education 4.0 (3), natural beauty 3.5 (5), climate 2.7 (8). Amenities and active outdoors do more work than their weights say; climate does less. Covariance-based and approximate (shares sum to about 97).
- Weight sensitivity (drop one input, renormalize; rank correlation, mean and max move in index points): education 0.998, 0.4, 1.9; social fabric 0.954, 6.1, 17.0; active outdoors 0.946, 3.2, 12.4; education plus amenities plus natural beauty 0.940, 3.0, 10.7. Ranges for scaled weights are TODO until sources exist.
- Launch pairs: not run (section 5).

## 5. Independent validation brief (for another agent; criteria fixed before any result)

Why a stronger test than 2026-10-09: that test had 3 affluent metros, no outside-metro places, no weight-free baseline, and no pass rule written first. This one fixes all of those. I saw the old result and my section 3 numbers before writing the thresholds, so the thresholds are marked judgment, not derived.

- Outcome: CDC USALEEP tract life expectancy at birth, 2010 to 2015, 2010 tract codes (the TIGERweb Census2010 layer, as in the mapping script). Not used to tune any weight. Level: tract.
- Match rule: a place matches if its pin falls in a USALEEP tract with a stored e0, and the place is neighborhood-scale or a small town (one pin tract is a fair stand-in). Places whose boundary spans many tracts (large cities, whole counties) do not match. Population field to apply this rule: TODO, the catalog does not store place population in a field I confirmed. Fallback rule if absent: type in neighborhood or suburb or town as labelled in `catalog.type`, with the excluded list published.
- Minimum matched places: 600, at least 100 outside New York, Los Angeles and San Francisco, in at least 8 metros. Fewer means the test is reported as not run, not as pass or fail.
- Controls (fixed): ACS 5-year 2010 to 2014 tract median household income, bachelor's share of adults 25 and over, and median age; plus a metro fixed effect. Ranks, not raw values.
- Metrics: partial Spearman of the index with e0 after the controls (P); added R2 over controls (D); partial for each input (reported, not a criterion).
- Pass, all required: P at least 0.15; D at least 0.02; P has the same sign in every metro with at least 30 matched places; the index beats a baseline index of equal weights over the same inputs by no less than 0.03 on P (a fail means the weights add nothing); P is not under half of the raw Spearman (otherwise the result is reported as tracking affluence).
- Launch pairs, set from names only (should differ by 6 points or more): Bronxville NY over Yonkers NY; Manhattan Beach CA over Inglewood CA; Wellesley MA over Chelsea MA. Should be within 7: Wilmette IL and Winnetka IL; Glen Rock NJ and Ridgewood NJ; Needham MA and Lexington MA. Pass 5 of 6. Note these pairs separate rich from poor, so a pass shows the index separates affluence, not longevity; stated so it is not over-read.
- Data needed before any run (not downloaded, needs your yes): the USALEEP national file `US_A.CSV` (about 30 MB, CDC) is not in the repo, only the 416-place map is; ACS tract tables from the Census API (free, needs the Census key). TIGERweb point lookups for roughly 1,000 more places are free API calls. Each goes in its own empty folder, Python run with `-I`.
- Not testable here: individual lifespan; causal effect of any pillar; vintage gap (outcome 2010 to 2015, pillars 2020s).
- Expected status if it fails any criterion: Level 1 with the failure recorded as an accepted gap.

## 6. What the live product claims

| Where | Words | Supported? |
|---|---|---|
| `LONGEVITY_COPY.full` and `.tooltip` (catalog, neighborhood page, place view, pillar cards, bottom sheet) | "Blue Zone-inspired score of the neighborhood conditions linked to long, healthy lives. Same formula for everyone, ignores your weights." | Mostly no. "Conditions linked to long, healthy lives" is true for individual-level air, isolation, activity. It is not shown for these area measures, and the one test found no added signal |
| `LONGEVITY_COPY.short` (ScoreDisplay) | "Seven research-based pillars (social fabric, outdoors, amenities, air and heat, safety, nature, schools)" | "Research-based" overstates: weights are judgment, amenities and nature have no study, schools measures children's school quality |
| `INDEX_COPY.longevity.body` | "How many of the everyday conditions that health research links to longer lives this place has" | Same gap |
| `INDEX_COPY.longevity.detail` | "It describes the neighborhood, not a forecast of how long you will live. Healthcare access is not included." | Supported and worth keeping |
| Catalog sort and map label "Longevity" | Bare word "Longevity" | A reader will take it as predicted life expectancy. Not supported |
| Saved list "Lon", compare "Longevity 71.2", `LONGEVITY_COPY.distinction` ("Longevity = Blue Zone-inspired conditions for health over time") | Number labelled Longevity | Same |
| `LongevityInfo` aria label "What is the Longevity Score?" | | Neutral |

No sentence says "predicts", which was removed 2026-10-09 (commit 4516e9e). The remaining problem is the label itself and "research-based".

## 7. Audit gap table

| # | Gap | Recommended fix | Expected impact on scores | Impact on claim |
|---|---|---|---|---|
| G1 | Index adds nothing beyond wealth and education (section 3); heaviest weights carry the least signal | Do not reweight to the catalog result (that is tuning on the test). Run the section 5 test first | None until a decision | Cannot claim any link to life expectancy |
| G2 | Active outdoors citation unconfirmed; pillar measures parks access, evidence is greenness | Verify the citation in the primary source; record the mismatch in the spec | None | Weight source is TODO |
| G3 | Frontend recompute ignores token-allocation eligibility; backend drops allocation-0 pillars. Same pillars, different index | Add the allocation rule to the frontend or drop it from both (owner decision, changes scores for 516 rows by up to 3.87 points; mean not computed) | Catalog rows unchanged if the frontend adopts the backend rule; live place view and saved pages change for places where education or beauty is allocation 0 | Removes a visible mismatch between catalog and place view |
| G4 | 15 places fall back to the full climate score (includes flood and trend) when lst_score is missing | Score air alone for those, or mark degraded (principle 9, 16) | 15 places move, size not computed | Matches the stated formula |
| G5 | Healthcare exclusion reason is stale (pillar rebuilt as hospital drive time, tier 1 evidence for drive time and mortality) | Re-examine as a candidate with the section 5 test; no change on assertion | Unknown until tested | None yet |
| G6 | Response gives no list of dropped pillars or covered weight | Add `components_missing` and `weight_covered` (no score change), as proposed for happiness | None | Meets principle 9 and 11 |
| G7 | Education (3) measures the wrong construct; amenities (15) has no source and wrong stored sign | Hold both at 0 until sourced, or keep and record as accepted TODO | Education off: rank 0.998, mean 0.4. Amenities off: not computed alone, shown with beauty and education in section 4 | Removes two unsupported inputs from "research-based" |
| G8 | Label "Longevity" reads as predicted lifespan | Rename or reframe (section 8) | None | Main claim fix |
| G9 | Nominal weights differ from real influence (amenities 21 percent of variance versus 15 nominal; climate 3 versus 8) | Record in spec; do not rebalance without evidence | None | Disclosure only |

## 8. Options (owner decision; recommendation first)

A (recommended): keep the number, no score change, honest copy and placement. Rename the label to "Health-linked conditions" (placeholder, owner to choose), drop "research-based" and "linked to long, healthy lives", state "built from judgment weights; not validated against life expectancy; adds no signal beyond local income and education in our test". Add `components_missing`, fix parity (G3) and G4. Run the section 5 brief. Level 1 now; Level 2 only if it passes. Cost: a weaker headline, but it says what the evidence supports.

B: reweight toward inputs with individual-level evidence (air, violence, social, greenness). No source gives shares; any numbers would be invented and would partly be fitted to the section 3 result. Not recommended before the section 5 test.

C: move to a personal setting, with the user choosing which health conditions matter. Fits the product (fixed formula for everyone is the weakest claim), but removes the sortable column and is a larger change. Reasonable second step after the test.

D: retire the number. Honest if section 5 fails, and cheaper than keeping a column nobody can defend. Premature before the stronger test, since the old test was narrow.

Decision needed: A, or something else. Then approve (1) the section 5 data downloads, (2) the G3 direction (frontend adopts backend rule, or both drop it), (3) the placeholder label.

## Level sign-off

Level 0 now. Proposed: Level 1 on approval of option A with TODOs accepted (every weight unsourced, active outdoors citation unconfirmed, education and amenities constructs mismatched, no independent validation). If section 5 fails, Level 1 stands with the failure recorded as an accepted gap.

## 9. Proposal v6: "Blue Zone fit" redesign (draft for approval, 2026-11-08, nothing applied)

Owner direction: design the index to fit the Blue Zones idea. Power 9 list below is from memory, not checked this session (TODO verify against Buettner's published list before it goes in copy).

Construct (one sentence): how many of the Blue Zone traits a place can support (daily movement and belonging) it makes easy; it is not a prediction of life expectancy and has not been tested against it.

| Power 9 trait | Place-measurable? | Input | Stored today? |
|---|---|---|---|
| Move naturally | Yes | Home walkability (amenities breakdown) and daily urban outdoors (active outdoors breakdown), averaged | Yes |
| Belong, right tribe | Yes, partly | Social fabric pillar score | Yes. Faith participation specifically: no stored field (worship nodes are folded into the civic node count). Needs a new OSM read, TODO, ask first |
| Plant slant | Dropped (owner, 2026-11-08) | A supermarket is a weak proxy: it says nothing about what people eat | n/a |
| Loved ones first | Personal, not a place | Social proximity setting | Already a personal setting, stays out |
| Purpose, downshift, 80 percent rule, wine | No | none | n/a |

Dropped from the index: air and heat, safety, education, natural beauty, wild adventure and waterfront (trip recreation, not daily movement). None is a Blue Zone trait. Safety and air stay as pillars; they are just not part of this number.

Weights: equal halves across the two inputs. Equal is the least invented option, not evidence; no source gives shares. Recorded as TODO.

Offline prototype (all 1,476 places, stored data only, no missing inputs):
- Mean 43.7, SD 10.4 (current 59.8, 9.9); 5th to 95th percentile 25.1 to 58.7. The level drops about 16 points because walkability and daily outdoors score lower than the old blend; the label and any "good score" bands must not be reused from the old index.
- Rank correlation with the current index 0.83; mean move 16.1 points (mostly the level shift), max 39.5. Dense walkable places rise relative to low-density ones.
- Raw correlation with USALEEP life expectancy on the 377 matched places: +0.12 (current index +0.38). Not a tracker of measured life expectancy; copy must never imply a lifespan link.

What validation means for this construct: (1) every input maps to a named trait, with the mapping written in the spec; (2) launch pairs set from names first (suggest Brooklyn Heights over Stamford CT suburb on movement, Ridgewood NJ over an exurb on walkability; owner to pick); (3) section 5 life expectancy test kept as informational only, reported not graded. Level 2 is reachable on (1) and (2). "Validated" never appears in copy.

Copy: label "Blue Zone fit" (not "Longevity"); body "How well this place supports two Blue Zone habits: walking in daily life and belonging to a community. It does not predict how long you will live." Replaces every string in section 6.

Cost and risk: every score changes and the catalog column, map and saved pages change with it; the frontend formula needs the new inputs from the stored breakdown (parity test on all rows). Index version 5 becomes 6; the index drops to Level 1 until section 5 items run.

Decisions needed: (a) approve the two-input design and equal halves; (b) faith participation: leave out for now (recommended, needs a new OSM read) or approve one; (c) label "Blue Zone fit".

## 10. Owner decision (2026-11-08)

Retire the longevity index unless it passes the section 5 brief at Level 2. The Blue Zone fit redesign (section 9) is not pursued: the traits it would use (belonging, nature, walking) are already in the happiness index (social fabric 0.26, natural beauty 0.12, active outdoors 0.07, amenities 0.04), and changing happiness would drop it from Level 2. Walkability stays out of happiness for now (weakest evidence, see `HAPPINESS_EVIDENCE_NOTES.md`).

Status: section 5 not yet run. The exploratory offline result (section 3, partial r +0.07, added R2 +0.003) already points to failing. Next step needs owner approval for downloads (USALEEP national file, ACS tract tables). If section 5 fails, or is not run, the index is retired in a separate approved change (remove from API response, catalog sort, saved and compare pages, map layer, frontend formula; keep the stored values in the data files until you say otherwise). No scoring or copy has changed.

## 11. Section 5 brief: results (run 2026-11-08)

Run by the same session that wrote the brief, not an independent one (you asked me to run it). Criteria were not changed after seeing results. Scripts are in the session scratchpad (`lv_scripts/map_and_acs.py`, `validate.py`), not in the repo. Data, each in its own folder: CDC USALEEP `US_A.CSV` (2.6 MB, ftp.cdc.gov, 67,148 tracts); ACS 2014 5-year tract median income, bachelor's share and median age for 18 states (Census API, 44,790 tracts); 1,476 TIGERweb Census2010 point lookups (all found a tract).

Match rule applied: catalog type neighborhood or suburb (the fallback rule, since no population field was found), tract has a life expectancy and ACS controls. 1,335 of 1,476 matched (5 excluded by type, 136 with no USALEEP value). 959 are outside New York, Los Angeles and San Francisco, across 21 metros. Controls: ranks of income, bachelor's share and median age plus metro fixed effects.

| Criterion | Threshold | Result | |
|---|---|---|---|
| Matched places | 600 or more | 1,335 | pass |
| Outside NYC, LA, SF | 100 or more | 959 | pass |
| Metros | 8 or more | 21 | pass |
| Partial Spearman P | 0.15 or higher | +0.036 (raw +0.451) | FAIL |
| Added R2 D | 0.02 or higher | +0.0006 (controls alone 0.553) | FAIL |
| Same sign in every metro with 30 or more | all positive | 8 of 19 non-positive (Austin, Boston, NYC, Philadelphia, Phoenix, Raleigh, Sacramento, Tampa) | FAIL |
| P above equal-weight baseline by 0.03 or more | P minus P(equal) 0.03 or more | +0.036 minus +0.097 = -0.061 | FAIL |
| P at least half of raw | 0.226 or more | 0.036 | FAIL (tracks affluence) |
| Launch pairs | 5 of 6 | 6 of 6 (differences 16.4, 18.9, 17.9; within-7 pairs 4.0, 0.7, 6.0) | pass, but see below |

Per-input partials (reported, not graded): social fabric +0.012, active outdoors -0.041, amenities -0.040, climate -0.017, natural beauty +0.052, education +0.144, safety +0.112. Equal weights beat the current weights, which means the weights add nothing.

Reading: the index fails every statistical criterion. The raw 0.45 is income and education; after controls nothing is left. Launch pairs pass because they separate rich towns from poor ones, which any affluence measure does; they do not show a life expectancy link (stated in the brief). Not verified: the pin tract stands in for the whole town, which is weak for suburbs that span many tracts (a population-weighted multi-tract match would be the stronger test); outcome years 2010 to 2015 against pillars from the 2020s; shared tracts make places non-independent; no significance tests.

## Level sign-off (current)

Level 0 and not raised. Section 5 failed its fixed criteria, so under the section 10 decision the index is retired. Next step, awaiting owner approval: a separate change removing it from the API response, catalog sort and map layer, saved and compare pages, and the frontend formula, with the stored values left in the data files.
