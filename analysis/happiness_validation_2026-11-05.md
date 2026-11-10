# Happiness index independent validation, section 8 (run 2026-11-05)

Run by the independent session. No scoring, weights, criteria, launch pairs or data files changed. Script: scratchpad val.py (run with python -I).

## Setup

Catalog: 1476 places, 21 metros, composites_recomputed files. Outcome file: CDC PLACES ZCTA 2025 release (data year 2023), crude prevalence, sign flipped so higher is better. Join by each place's own ZIP (score.location_info.zip, zero padded). Income: livability_pillars.housing_value.summary.median_household_income as stored. Places with a ZIP matched to the file: 1319; with income too: 1314. Components: stored happiness_index_breakdown, v5 weights.

## Tests T1, T2 (current weights)

| Test | n | Raw Spearman | Partial (income) | Raw pass | Partial pass | Verdict | Tracks affluence |
|---|---|---|---|---|---|---|---|
| T1a LONELINESS | 850 | 0.577 | 0.416 | yes | yes | PASS | no |
| T1b EMOTIONSPT | 850 | 0.610 | 0.405 | yes | yes | PASS | no |
| T2 GHLTH | 1314 | 0.550 | 0.196 | yes | yes | PASS | YES |

T1 overall (both outcomes): PASS. T2: PASS.

Reference: Spearman of median income alone with each outcome (same places): T1a LONELINESS 0.454, T1b EMOTIONSPT 0.539, T2 GHLTH 0.678.

## T3 current vs equal weights

| Outcome | Current raw | Equal raw | Raw gap (cur - eq) | Current partial | Equal partial | Partial gap | Verdict (gap >= -0.03 on raw and partial) |
|---|---|---|---|---|---|---|---|
| T1a LONELINESS | 0.577 | 0.489 | +0.087 | 0.416 | 0.276 | +0.140 | PASS |
| T1b EMOTIONSPT | 0.610 | 0.568 | +0.042 | 0.405 | 0.325 | +0.081 | PASS |
| T2 GHLTH | 0.550 | 0.597 | -0.047 | 0.196 | 0.291 | -0.095 | FAIL |

T3 overall: FAIL. The brief does not say whether the 0.03 margin applies to raw, partial or both; both are shown and the verdict requires both. T1 equal-weight index also drops social fabric (same components).

## T4 sign by metro (metros with 30 or more matched places)

| Metro | n | T1a raw | T1b raw | T2 raw |
|---|---|---|---|---|
| atlanta | 73 | +0.379 | +0.252 | +0.338 |
| austin | 56 | n<30 for an outcome: [0, 0, 56] (not tested) | | |
| boston | 77 | +0.742 | +0.630 | +0.501 |
| charlotte | 35 | +0.217 | +0.325 | +0.548 |
| chicago | 100 | +0.754 | +0.654 | +0.491 |
| dallas | 78 | n<30 for an outcome: [0, 0, 78] (not tested) | | |
| denver | 57 | n<30 for an outcome: [0, 0, 57] (not tested) | | |
| houston | 70 | n<30 for an outcome: [1, 1, 70] (not tested) | | |
| la | 94 | +0.627 | +0.558 | +0.647 |
| miami | 65 | n<30 for an outcome: [0, 0, 65] (not tested) | | |
| nyc | 183 | +0.794 | +0.813 | +0.639 |
| orlando | 41 | n<30 for an outcome: [0, 0, 41] (not tested) | | |
| phoenix | 60 | +0.440 | +0.429 | +0.551 |
| sacramento | 56 | +0.643 | +0.496 | +0.471 |
| san_antonio | 48 | n<30 for an outcome: [1, 1, 48] (not tested) | | |
| sf | 100 | +0.633 | +0.587 | +0.505 |
| tampa | 46 | n<30 for an outcome: [0, 0, 46] (not tested) | | |

T4 overall: PASS. Metros under 30 matched places (not tested): [('austin', 56, [0, 0, 56]), ('dallas', 78, [0, 0, 78]), ('denver', 57, [0, 0, 57]), ('houston', 70, [1, 1, 70]), ('las_vegas', 26), ('miami', 65, [0, 0, 65]), ('orlando', 41, [0, 0, 41]), ('philadelphia', 16), ('raleigh', 28), ('san_antonio', 48, [1, 1, 48]), ('seattle', 5), ('tampa', 46, [0, 0, 46])].

Partial correlations by metro (informational):

| Metro | T1a partial | T1b partial | T2 partial |
|---|---|---|---|
| atlanta | +0.331 | +0.143 | +0.080 |
| boston | +0.472 | +0.177 | -0.045 |
| charlotte | +0.071 | -0.028 | +0.120 |
| chicago | +0.614 | +0.413 | +0.034 |
| la | +0.244 | +0.188 | +0.342 |
| nyc | +0.577 | +0.568 | +0.138 |
| phoenix | +0.295 | +0.292 | +0.383 |
| sacramento | +0.593 | +0.436 | +0.369 |
| sf | +0.520 | +0.434 | +0.209 |

## Coverage

Matched n (ZIP in file and income stored): 1314 of 1476 (89.0 percent). Not the full catalog, so the index may be called "checked on a subset" only, not validated.

| State | Catalog places | Matched | Share |
|---|---|---|---|
| Arizona | 64 | 60 | 94% |
| California | 276 | 250 | 91% |
| Colorado | 62 | 57 | 92% |
| Connecticut | 13 | 13 | 100% |
| Delaware | 3 | 3 | 100% |
| Florida | 160 | 152 | 95% |
| Georgia | 76 | 73 | 96% |
| Illinois | 97 | 94 | 97% |
| Indiana | 6 | 6 | 100% |
| Maryland | 1 | 0 | 0% |
| Massachusetts | 81 | 77 | 95% |
| Nevada | 30 | 26 | 87% |
| New Jersey | 41 | 38 | 93% |
| New York | 152 | 145 | 95% |
| North Carolina | 72 | 63 | 88% |
| Pennsylvania | 75 | 0 | 0% |
| Texas | 262 | 252 | 96% |
| Washington | 5 | 5 | 100% |

States with no matched places: Pennsylvania, Maryland.

Places with no ZIP stored: 3. Places with ZIP not in the file: 154. Matched but missing income: 5. Places sharing a ZIP with another catalog place: 304 of 1314.

| Area type | Catalog | Matched | Share |
|---|---|---|---|
| None | 3 | 3 | 100% |
| exurban | 385 | 352 | 91% |
| rural | 142 | 132 | 93% |
| suburban | 743 | 660 | 89% |
| unknown | 4 | 3 | 75% |
| urban_core | 2 | 0 | 0% |
| urban_residential | 197 | 164 | 83% |

Spearman by area type (informational):

| Area type | n | T1a raw/partial | T1b raw/partial | T2 raw/partial |
|---|---|---|---|---|
| exurban | 352 | +0.478 / +0.228 | +0.626 / +0.420 | +0.638 / +0.315 |
| rural | 132 | +0.431 / -0.005 | +0.603 / +0.200 | +0.640 / +0.181 |
| suburban | 660 | +0.644 / +0.514 | +0.608 / +0.407 | +0.564 / +0.245 |
| urban_residential | 164 | +0.268 / +0.040 | +0.455 / +0.170 | +0.478 / +0.160 |

## T1 outcome coverage by state (LONELINESS and EMOTIONSPT present)

| State | Catalog | T2 matched | T1 matched |
|---|---|---|---|
| Arizona | 64 | 60 | 60 |
| California | 276 | 250 | 250 |
| Colorado | 62 | 57 | 0 |
| Connecticut | 13 | 13 | 13 |
| Delaware | 3 | 3 | 3 |
| Florida | 160 | 152 | 0 |
| Georgia | 76 | 73 | 73 |
| Illinois | 97 | 94 | 94 |
| Indiana | 6 | 6 | 6 |
| Maryland | 1 | 0 | 0 |
| Massachusetts | 81 | 77 | 77 |
| Nevada | 30 | 26 | 26 |
| New Jersey | 41 | 38 | 38 |
| New York | 152 | 145 | 145 |
| North Carolina | 72 | 63 | 63 |
| Pennsylvania | 75 | 0 | 0 |
| Texas | 262 | 252 | 2 |
| Washington | 5 | 5 | 0 |

States with no T1 matches: Colorado, Florida, Pennsylvania, Maryland, Washington. T1 n 850 of 1476 (57.6 percent).


## Launch pairs

- Scarsdale NY vs Mount Vernon NY (diff): Village of Scarsdale (nyc) 74.3 vs City of Mount Vernon (nyc) 50.1, diff 24.2, PASS
- Palo Alto CA vs East Palo Alto CA (diff): Palo Alto (sf) 70.1 vs East Palo Alto (sf) 59.6, diff 10.5, PASS
- Beverly Hills CA vs Compton CA (diff): Beverly Hills (la) 59.5 vs Compton (la) 41.4, diff 18.1, PASS
- Larchmont NY vs Mamaroneck NY (same): Village of Larchmont (nyc) 75.6 vs Town of Mamaroneck (nyc) 68.1, diff 7.5, FAIL
- Chatham NJ vs Summit NJ (same): Chatham (nyc) 76.8 vs Summit (nyc) 69.9, diff 6.9, FAIL
- Newton MA vs Brookline MA (same): Newton (boston) 75.3 vs Brookline (boston) 69.7, diff 5.6, FAIL

Launch pairs: 3 of 6 behave as stated (0 unresolved). Pass needs 5. FAIL.

## Summary of verdicts

- T1 PASS (raw 0.577 and 0.610, partial 0.416 and 0.405). T1 population is 850 places: Colorado, Florida, Washington and all but 2 Texas places have no LONELINESS or EMOTIONSPT values in the file.
- T2 PASS on the fixed criteria (raw 0.550, partial 0.196), but it tracks affluence: partial is 0.196 against raw 0.550 (under half), and median income alone correlates 0.678 with GHLTH, higher than the index does. Report as tracking affluence, not as validation.
- T3 FAIL: current weights are 0.047 below equal weights on T2 raw (and 0.095 on partial). They are ahead on both T1 outcomes. The brief gives no rule for raw versus partial; on raw alone T3 still fails because of T2.
- T4 PASS: same sign in all 9 metros testable on every outcome (atlanta, boston, charlotte, chicago, la, nyc, phoenix, sacramento, sf). Several metros had 30 or more places but fewer than 30 with T1 outcomes (austin, dallas, denver, houston, miami, orlando, san_antonio, tampa) so they could not be tested on T1 as written and are excluded from T4. Charlotte partials are near zero or negative on T1b (-0.028).
- Launch pairs FAIL: 3 of 6 (needs 5). All three "differ" pairs pass. All three "within 5 points" pairs fail: Larchmont/Mamaroneck 7.5, Chatham/Summit 6.9, Newton/Brookline 5.6.
- Name ambiguity: "Compton CA" matches three catalog rows with city field Compton (ZIPs 90220, 90022, 90274); two are mislabeled (inputs East Los Angeles and Rolling Hills Estates). The row whose input is "Compton, California" (90220, 41.4) was used. If any other row were used the pair result would change (69.8 would fail it), so this is stated. Larchmont and Mamaroneck share ZIP 10538, so their outcome values are identical; the pair test itself does not use outcomes. Mamaroneck is the "Town of Mamaroneck" row.

## Not verified

- PLACES ZIP values are modeled small-area estimates (MRP), not measured; they borrow from county and demographics, which can inflate correlation with income-linked pillars.
- Crude prevalence, not age-adjusted: older places look worse on GHLTH regardless of the index.
- Coverage is a subset: T2 n 1,314 of 1,476 (89.0 percent), T1 n 850 of 1,476 (57.6 percent). Pennsylvania and Maryland have no matches in either; Colorado, Florida, Washington (and Texas for T1) have no T1 outcomes. The label is "checked on a subset", not validated.
- 304 of the 1,314 matched places share a ZIP with another catalog place, so observations are not independent and many places get the same outcome value. Spearman significance was not computed.
- Income is the stored housing_value median household income at the place level, not ZIP level; ZIP and place can differ.
- T3 equal-weight index uses the same stored components with weight 1 each; for T1 it also drops social fabric.
- Which nine-minus-one components were missing per place was handled by renormalizing, as the brief says.
