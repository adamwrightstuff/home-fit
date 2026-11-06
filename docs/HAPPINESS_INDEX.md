# Happiness index: DPv2 spec sheet and audit

Level: 0 (audit in progress, 2026-11-05). Nothing in scoring has changed. Branch `happiness-dpv2`, worktree `home-fit-happiness`, cut from origin/main 02e03b31.

The happiness index is a composite beside the pillars, not a pillar. Weights, evidence and sensitivity history are in `HAPPINESS_WEIGHTS_PROPOSAL.md` (v5, applied October 2026) and `HAPPINESS_EVIDENCE_NOTES.md`; they are linked here, not repeated. Worked examples for the format: `PILLAR_ECONOMIC_SECURITY.md`, `PILLAR_SOCIAL_FABRIC.md`.

## 1. Spec sheet

```
Index: Happiness index (index version 5), 0 to 100
Construct (one sentence): a place-level estimate of resident wellbeing built from nine pillar scores;
  it is not any one person's happiness and it does not predict an individual's life satisfaction.
Reference frame: no frame of its own. Each component keeps the frame of its pillar (safety is a
  national percentile, most others are peer or area norms, housing is a fixed standard). The weights
  are a judgment about how much each matters, not a frame.
  Evidence for the frame (tier 1 published study | tier 2 price or migration proxy | tier 3 survey):
  Tier 1 exists for the direction of seven components (individual-level studies, section 2). Tier 2: none
  found for the bundle or its shares. Tier 3: none. No study ranks neighborhood factors against each
  other, so every share is judgment.
Measurement area: inherited from each pillar (pin and radius, tract, ZIP, place). The index adds none.
Place context inputs: none read directly. Area type is not used anywhere in the index formula.
Inputs: stored pillar scores, 1,476 catalog places (21 metros) and the live response. Commute is the
  place's area-mean commute score read from the public transit pillar's breakdown.
Formula: weighted mean over available components, renormalized. A pillar stored as failed (status
  failed, or score 0 with confidence 0) is missing, not zero (principle 9). Safety missing, commute
  missing and any other missing component renormalize out.
Parameters (weight | source | tested range | sensitivity):
  social fabric       0.26 | judgment | 0.13 to 0.52 | section 4
  community safety    0.18 | judgment | 0.09 to 0.36 | section 4
  housing             0.14 | judgment | 0.07 to 0.28 | section 4
  natural beauty      0.12 | judgment | 0.06 to 0.24 | section 4
  economic opportunity 0.08 | judgment | 0 to 0.16 | section 4
  active outdoors     0.07 | judgment | 0 to 0.14 | section 4
  climate and air     0.06 | judgment | 0 to 0.12 | section 4
  commute (area mean) 0.05 | judgment, owner decision 2026-11-05 to keep | 0 to 0.15 (COMMUTE_TIME.md) | section 4
  amenities           0.04 | judgment | 0 to 0.08 | section 4
  Held at 0 (reason): schools (average causal effect of schooling on life satisfaction is null, IZA DP
  16454), healthcare (links to self-rated health only), diversity (no link to trust, Sturgis 2011), air
  travel (noise lowers wellbeing, no access benefit found), built environment (scored for 17 percent
  of places), political lean (opt-in filter), status signal (not a residential wellbeing pillar).
  Ranges are my judgment: a plain halving and doubling for weights above 0.10, and 0 to double for the
  rest. They are not evidence-derived and are marked so.
Personal settings, not weights: commute time to the user's workplace, social proximity. Client side.
Shared inputs with other pillars: section 5.
Pin-shift sensitivity: inherited, not an index property. The index moves with each pillar's own result.
Independent validation: not yet run (brief in section 8).
All-places check: section 3.
Fail-loud conditions: failed pillar drops out; all components missing returns null. Gap: the response
  does not say which components were missing or how much weight was left (gap G6).
Launch check pairs: fixed in section 8, not yet scored.
Known data limits: 56 places have no safety score (about 4 percent, FL 18, GA 9, NC 8, NV 7, PA 5);
  271 places have no commute term (exurban 120, rural 100, suburban 49).
Last re-validated: never under DPv2.
```

## 2. Evidence audit: does each weight's evidence still fit the pillar that exists today?

Check 1. Pillars changed after v5 (8 October). The evidence for a weight is about a construct; if the pillar's construct moved, the evidence may no longer apply. Tiers: 1 = published individual-level study. "Catalog check" = our PLACES check on three metros, confounded by wealth and place type, run on the old pillars.

| Weight | Evidence used at v5 | Pillar since | Still applies? |
|---|---|---|---|
| Social 26 | Harvard study, Helliwell and Barrington-Leigh (cross-sectional, trust and ties); prospective perceived-cohesion studies; catalog check stable 2 of 3 | v18 final 2026-11-04: EC 0.20, participation 0.48, cohesion 0.16, rootedness 0.08, civic 0.08, objective proxies | Partly. Evidence is about relationship quality and perceived cohesion, which our objective inputs only approximate (said in the evidence notes). Catalog check was on the pre-EC pillar and was not rerun. New support: ZIP-level PLACES loneliness 0.467 and lack of support 0.540 (855 places), but the EC choice was made using that same test, so it cannot also validate the weight |
| Safety 18 | Catalog check strongest, all 3 outcomes; research mixed: victimization lowers trust and neighborhood satisfaction, not life satisfaction (verified) | crime-type weighting (property 0.098), new incident sources for 6 metros, fail-loud rules | Catalog evidence is on the old pillar and not rerun. Individual-level evidence for life satisfaction is the weakest of the top four. See G1 |
| Housing 14 | Cost burden raises depression, mostly renters (panel studies) | pooled tracts D14, 50/30/20 affordability, space, efficiency; rank correlation 0.67 with measured burden | About half. Affordability matches the burden evidence. Space and efficiency (half the pillar) rest on cross-sectional space studies, one of which loses the effect once perceived stress is controlled |
| Natural beauty 12 | Moving to greener areas improved mental health (Alcock, movers, verified) | two-part streets and scenery, one 800 m green view radius (2026-10-30) | Streets part: yes, it is greenness exposure. Scenery and water part: no wellbeing study in the notes |
| Economic 8 | Indirect (unemployment, income, individual level) | job-market gravity, national baseline, DPv2 step A | Never matched the construct (reachable jobs, not own job). Catalog sign unstable. Weight carries 0.1 percent of index variance, see G2 |
| Active outdoors 7 | Exercise lowers depression; 120 or more minutes a week in nature | typed parks, clean trail count (2026-11-03 and 04) | No. Evidence is about activity done; the pillar measures access to parks and trails. Catalog check held for 1 outcome, on the old pillar |
| Climate and air 6 | PM2.5 and SO2 lower life satisfaction; heat raises mental-health ER visits (IRR 1.08) | measured tract PM2.5 (replaced aerosol proxy 2026-10-25), heat screen, flood tiers, trend | Better than at v5 for PM2.5 and heat. Flood and warming trend have no wellbeing study here |
| Commute 5 | Small mood and leisure cost; no general life-satisfaction effect in careful panels | unchanged term; transit pillar redone but the commute figure is the same Census commute | Decided: keep (owner, 2026-11-05). Not re-argued |
| Amenities 4 | none found | supermarket-only grocery, linear decay 400 to 1,200 m | No evidence existed; judgment at 4 |

Held-at-0 check, adding each at 5 percent: schools (rank correlation with current index 0.993), healthcare 0.992, diversity 0.999, air travel 0.999, built environment 0.999, transit 0.990. None of the holds is load-bearing for ranking. Healthcare, transit and air travel were redone under DPv2 but carry no weight, so those redos do not touch the index except through the commute term.

## 3. All-places check (2026-11-05, n = 1,476, 21 metros, stored data)

- Stored index equals the formula recomputed from stored pillar scores for all 1,476 rows (no drift).
- Index mean 59.8, SD 9.1, 5th to 95th percentile 45.5 to 75.5, range 36.7 to 81.0. No clumping at floor or ceiling.
- By area type (mean, SD): exurban 62.3, 8.8; rural 61.1, 8.4; suburban 59.3, 9.6; urban residential 55.8, 6.7. Dense places score lower on average. Cause: safety, housing space and green view favor low density. This is a construct property to disclose, not a bug.
- Component spread and share of index variance (nominal weight in brackets):

| Component | SD | Share of variance | Floor / ceiling |
|---|---|---|---|
| Safety (18) | 28.7 | 47.5 percent | 2.7 / 8.0 percent |
| Social (26) | 9.9 | 20.3 | 0 / 0 |
| Natural beauty (12) | 19.5 | 16.4 | 0 / 1.7 |
| Housing (14) | 13.7 | 9.4 | 0.1 / 0 |
| Active outdoors (7) | 15.7 | 4.4 | 0 / 1.5 |
| Climate (6) | 7.5 | 1.5 | 0 / 0 |
| Commute (5) | 14.3 | 0.5 | 0 / 0.4 |
| Amenities (4) | 23.8 | 0.4 | 0.3 / 4.1 |
| Economic (8) | 6.2 | 0.1 | 0 / 0 |

Weights are applied to scores on different scales, so a weight is not an influence. Safety is a national percentile (SD 28.7); social and economic are compressed (SD 6 to 10).

## 4. Weight sensitivity, extended (1,476 places; script in section 9)

Previous run: 411 places, three metros, plus or minus 30 percent. Now all 21 metros, plus 50 percent, and one weight at a time to 0 and to 2x.

- Joint plus or minus 30 percent: median place score SD 1.05, median 90 percent band 3.5 points, at most 6.8; median rank SD 32 of 1,476; 40 of the top 50 stay in the top 50 in 90 percent of draws.
- Joint plus or minus 50 percent: median SD 1.75, band 5.7, at most 11.3; 33 of the top 50 stable.
- Equal weights: rank correlation 0.914 with current. Drop safety: 0.850. Drop social: 0.969.
- One weight to zero (mean score change, rank correlation): safety 3.98 points, 0.850; social 3.87, 0.969; green 1.90, 0.970; housing 1.76, 0.978; economic 1.30, 0.998; active outdoors 1.03, 0.993; climate 0.97, 0.999; commute 0.94, 0.996; amenities 0.88, 0.994.
- One weight doubled: safety 2.75, 0.980; social 2.24, 0.984; green 1.48, 0.985; housing 1.32, 0.985; the other five under 1.1 and 0.994 or higher.
- Reading: precision is limited by pillar quality more than by weights, as before. Treat index gaps under about 3.5 points as ties (the median 90 percent band), a wider margin than the earlier 1.5.

## 5. Double counting (reported, decisions not reopened)

Spearman across 1,476 places, unless noted.

| Pair | Result | Reading |
|---|---|---|
| Economic opportunity and status signal | 0.08 | Almost none |
| Economic opportunity and housing | minus 0.48 | They work against each other (job-rich dense places are costly). Together with economic's 0.1 percent variance share, the 8 percent weight has no effect on ranking |
| Active outdoors and natural beauty | 0.19 | Low overlap in outcomes, kept separate as decided |
| Safety and social fabric | 0.38 | Moderate. Both move with affluence (status signal 0.45 with each) |
| Safety and housing | 0.43 | Moderate; affluent places score well on both |
| Social and natural beauty | 0.33 | Moderate |
| Status signal and the index as a whole | 0.57 | Not an input, but the index tracks affluence. Same pattern as the PLACES check |

## 6. Live and catalog parity

Frontend `computeHappinessIndex` in `frontend/lib/pillars.ts` against stored catalog index, run in Node on all 1,476 rows: 1,475 match within 0.05; one differs by 0.1 (Montclair, Denver metro; exact value 52.85, a rounding tie that Python and JavaScript break differently). Weights and null rules are identical. Stale text: the pillar-card tag set `HAPPINESS_PILLAR_KEYS` lists transit, social fabric, housing and natural beauty only, so safety, economic, active outdoors, climate and amenities carry no happiness tag (gap G7).

## 7. Audit gap table

| # | Gap | Fix | Expected score impact |
|---|---|---|---|
| G1 | Safety carries 47.5 percent of index variance on an 18 percent weight; its individual-level life-satisfaction evidence is mixed. The index is nearly a safety index with a social term | Owner decision (section 10, options B to C) | Option B: rank correlation 0.96, Midtown 683 to 228, Mesquite 607 to 1,101. Option A: none |
| G2 | Economic (8), commute (5) and amenities (4) carry 1.0 percent of variance together; climate (6) 1.5 percent. Their weights are inert | Disclose; no change (commute decided; the rest unsupported either way) | None |
| G3 | No tested range recorded per weight; sensitivity covered 411 places and three metros | Add ranges to the script and docs (done in section 4) | None |
| G4 | Social fabric, safety, active outdoors and natural beauty changed after the catalog check that justified their shares; the check was not rerun | Rerun `pillar_vs_places_check.py` on the current pillars, all metros | None to scores; may change the evidence tier of a weight. Needs the PLACES ZIP file again (12 MB download, permission) |
| G5 | No independent validation of the index | Section 8 brief | None |
| G6 | 56 places have no safety score and 271 no commute term; the response and catalog do not say so. Imputing the national median safety for the 56 changes them by minus 0.6 on average, up to 3.8; commute median imputation plus 1.2, up to 2.6 | Add `components_missing` and `weight_covered` to the breakdown; no change to the number | None to scores. Field added in catalog and live response |
| G7 | Happiness tag dots cover 4 of 9 components | Update `HAPPINESS_PILLAR_KEYS` to the 9 weighted pillars | None to scores; frontend change, needs lint and tsc |
| G8 | Docstring still says version 5 and the weights are called judgment in prose, but ranges and variance shares are missing | Docstring and doc update | None |
| G9 | Sensitivity script reads the `_merged` files for 3 metros; the Explorer serves `composites_recomputed` | Point it at all 21 `composites_recomputed` files | None |
| G10 | Dense places score 6.5 points lower on average (urban residential 55.8 against exurban 62.3) | Disclose in copy and in this sheet; no change | None |

## 8. Level 2 plan: pass criteria fixed before any result

Written 2026-11-05 before running any of these. The builder does not run the validation.

Launch pairs (named without looking at index values; first place should score higher):
- Should differ by 6 points or more: Scarsdale NY over Mount Vernon NY; Palo Alto CA over East Palo Alto CA; Beverly Hills CA over Compton CA.
- Should be within 5 points: Larchmont NY and Mamaroneck NY; Chatham NJ and Summit NJ; Newton MA and Brookline MA.
- Pass: at least 5 of 6 behave as stated. The 6-point rule is about the median 90 percent band of 3.5 plus margin; it is a judgment.

Independent validation brief (for another agent; PLACES ZIP file qnzd-25i4, 2025 release, crude prevalence, LONELINESS, EMOTIONSPT, GHLTH; one download into its own empty folder, run Python with `-I`, ask the owner before downloading):
1. T1: index with social fabric removed and renormalized, against LONELINESS and EMOTIONSPT, sign set so higher is better. Social fabric is excluded because its blend was chosen using these measures. The other eight weights were checked only against frequent mental distress, depression and short sleep. Pass: Spearman 0.20 or higher on both, and partial Spearman after the place's median income rank 0.10 or higher.
2. T2: full index against GHLTH (fair or poor self-rated health, not used for tuning anything). Pass: Spearman 0.20 or higher and partial after income 0.10 or higher.
3. T3: weights versus no judgment. Full index against equal-weight index on T1 and T2. Pass: current weights are no worse than 0.03 below equal weights on either test. A fail is reported, not hidden.
4. T4: sign consistency. Same sign in every metro with at least 30 matched places.
5. Coverage: report n and the states missing (PA, CO, OR are in neither release). The index may not be called validated in user copy unless n covers the full catalog (DPv2 adoption rule). Expected status: ZIP file covers about 58 percent, so the label would be "checked on a subset".
6. Report any result that comes out as tracking affluence (partial under half of raw) as that, not as validation.

## 9. Offline scripts

- `scripts/catalog/happiness_weight_sensitivity.py`: to be extended (all `composites_recomputed` files, per-weight ranges, one-at-a-time to 0 and 2x, variance share). Not yet changed in the repo; the results above came from a scratch copy.
- Recompute: `scripts/catalog/recompute_happiness_only.py` into new files, not in place.

## 10. Options (owner decision; recommendation first)

A (recommended): no score change. Keep v5 weights as documented judgments with tested ranges; add `components_missing` and `weight_covered` to the breakdown (no change to any score); fix tag dots, docstring, script; add parity test. Result: Level 1 now, Level 2 after the brief runs. Cost: the index stays dominated by safety and the sheet says so.

B: standardize components before weighting so each weight equals its influence. Rank correlation with current 0.960; dense and urban places rise, low-crime exurbs fall. No evidence says influence should equal weight, so this is a design judgment, and it contradicts how safety was scored on purpose (national percentile).

C: lower safety's weight. No evidence gives a number; I would be inventing one. Not recommended.

D: drop the inert terms (economic, amenities). Against the commute decision and leaves the zero-weight list longer without evidence; not recommended.

Decision needed: A, or B.

## Level sign-off

Level 1, owner, 2026-11-05. Accepted TODOs: weights are unsourced judgments with recorded ranges (Level 3 not met); safety carries about 48 percent of index variance (option A kept); T3 and launch pairs failed in the independent run, so the index may be called "checked on a subset" and not validated; PLACES coverage is a subset (no Pennsylvania or Maryland; no loneliness or support values for CO, FL, WA, most of TX); catalog-versus-PLACES weight check not rerun on current pillars (G4); T4 skipped 8 metros. Next: decide whether the 5-point similarity rule for launch pairs was the right rule; any scoring change drops the index back to Level 1 pending reruns.

## Independent validation results (run 2026-11-05 by the independent session)

Full tables, coverage and caveats: `analysis/happiness_validation_2026-11-05.md`. Criteria in section 8 were not altered. Overall: not all pass.

| Test | n | Raw Spearman | Partial (income) | Result |
|---|---|---|---|---|
| T1 loneliness (social fabric removed) | 850 | 0.577 | 0.416 | PASS |
| T1 emotional support (social fabric removed) | 850 | 0.610 | 0.405 | PASS |
| T2 full index vs fair/poor health | 1,314 | 0.550 | 0.196 | PASS, tracks affluence (partial under half of raw; income alone 0.678) |
| T3 current vs equal weights | 850 / 1,314 | gap +0.087, +0.042, -0.047 | gap +0.140, +0.081, -0.095 | FAIL (T2 below equal weights by more than 0.03) |
| T4 sign in metros with 30 or more | 9 metros | all positive | | PASS |
| Launch pairs | 6 | | | FAIL, 3 of 6 (the three "within 5" pairs differ by 5.6 to 7.5) |

Coverage: T2 n 1,314 of 1,476 (89.0 percent), T1 n 850 (57.6 percent). No matches in Pennsylvania or Maryland; no T1 outcomes in Colorado, Florida, Washington and nearly all of Texas. Allowed label: "checked on a subset", not validated. Not verified: PLACES ZIP values are modeled estimates, crude not age-adjusted, 304 matched places share a ZIP.

Level 2, owner, 2026-11-05. Level 2 here means the checks were run by an independent session against criteria fixed beforehand, not that all passed. Results: T1, T2, T4 pass; T2 tracks affluence; T3 and launch pairs fail (3 of 6). Accepted TODOs are the Level 1 list above plus these failures. User copy may say "checked on a subset", never "validated".
