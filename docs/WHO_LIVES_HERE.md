# Who lives here (descriptive panel), DPv2 spec sheet

Written 2026-11-05. Step 1 of docs/PRODUCT_MODEL_PLAN.md. Status: built locally (not pushed), Level 0 until the owner signs off Level 1.

## Job and construct
Answers "who lives in this place": plain facts about residents' money, education, tenure and age. It is a description. It has no score, no weight, no filter of its own and is not counted in any total. Because nothing is scored, there are no scoring parameters to source and no reference frame to choose: each number is the Census figure for the place, shown as is.

## What it shows
| Group | Rows | Source (ACS 2022 5-year) | Stored field |
|---|---|---|---|
| Income and wealth | median household income, mean household income, median home value | B19013, B19025 aggregate over B19001 households (mean), B25077 | housing_value.summary |
| Education (adults 25 and over) | bachelor's degree or higher, graduate degree (master's or higher) | B15003 (022 to 025, 023 to 025) | diversity.education_attainment |
| Households | renters, homeowners | B25003 | housing_value.summary.renter_pct |
| Age | under 18, 18 to 64, 65 and over | B01001 | diversity.raw_shares.age (existing, kept) |

## Deliberately not shown
Race and ethnicity, and the income distribution (brackets): the owner ruled on 2026-10-28 that nothing filters, ranks, scores or displays by race or income distribution (docs/PILLAR_DIVERSITY.md). Median and mean income are shown because they are plain wealth facts that already appear in the housing card. Household type (families with children, single-person households) is not stored yet; it is step 5 of the plan.

## Display rules
- Missing data shows "n/a", never zero (principle 9).
- Census caps: median income shows "$250,000+" at the cap and median home value "$2,000,000+"; the panel says so.
- The measured geography (surrounding tracts, or the whole city or town) is named in the caption, from the stored geo_level.
- Name: schools quality is a pillar (quality education). This panel's education rows are about residents and sit under "Education (adults 25 and over)".

## Audit gap table
| # | Gap | Principle | Size | Action |
|---|---|---|---|---|
| G1 | Single-tract places read one tract, so a 500 m pin shift changes the figures (the pooled-tract rule D14 is not applied to this panel's income or home value) | 6 sensitivity, 3 measurement area | Pin-shift not measured for this panel; for housing the single-tract 95th percentile was large | Use the pooled values where the catalog has them; measure pin-shift before Level 2 |
| G2 | No spot check against the Census source | 7 validation | Not run; stored values agree with each other | Run a 10-place check across the five classes if the owner wants certification evidence; needs Census calls, ask first |
| G3 | Coverage | 8 all places | 1,476 places: none empty; income group missing for 7, household group 7, education 3, age 4; median home value n/a for 26 | Disclosed; shown as n/a |
| G4 | Users may read the facts as a ranking or a class | place context | Comprehension not tested | Run the comprehension test from the v3 spec idea (state what the panel means, without reading it about their own income) |
| G5 | ACS sampling error not shown | 4 | Margins of error not stored | Disclose; add if stored later |
| G6 | Vintage 2022 is not the newest | 4 | One release behind | Refresh with the yearly release |

## Evidence tier
Descriptive facts from the Census (tier 1 data, no inference). The mental model (that people want to know who their neighbors are) is not tested yet; see G4.

## Checks run (2026-11-05)
- Type check of the frontend passes with the new component.
- Offline field coverage over all 21 stored metro files: 1,476 places, none with an empty panel; see G3 for the gaps.
- Browser check on the Tribeca neighborhood page: the panel renders all four groups (income $250,000+ capped, mean $534,105, home value $2,000,000+, bachelor's or higher 94%, graduate 38%, renters 55%, age 20 / 70 / 10); the only console errors were /api/health 502s because the backend was not running, unrelated to the panel.
- Not run: pin-shift, Census spot check, comprehension.

## Sign-off
Level 1 sign-off pending (owner).
