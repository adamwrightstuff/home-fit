# Who lives here (descriptive panel), DPv2 spec sheet

Written 2026-11-05. Step 1 of docs/PRODUCT_MODEL_PLAN.md. Status: Level 1 signed off 2026-11-05 and pushed to main.

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
Level 1 (Specified), signed off by the owner (Adam Wright), 2026-11-05, with gaps G1, G2, G4, G5 and G6 accepted as open. Level 2 not claimed: no pin-shift, Census spot check or comprehension test yet.

## Household type added (2026-11-05, plan step 5)
The panel now has a Household type card: households with children under 18, living alone, married-couple families, and with someone 65 or over (ACS 2022 5-year B11001, B11005, B11007), stored as `diversity.household_type` for 1,465 of 1,476 catalog places (11 have no identified geography; the group is omitted for them, not shown as zero). Pull: `scripts/catalog/pull_census_household_type.py` (18 catalog states, 38 calls, 68,195 rows, every row's parts equal its total; data in the archive folder). Join to the geography the diversity read used: `scripts/catalog/join_household_type_offline.py` (keys carry the state FIPS because Ridgewood NJ and Ridgewood NY share a metro and a name). Catalog write: `scripts/catalog/add_household_type_offline.py`, additive, nothing else in the files changes. Catalog medians: 29.5 percent of households with children (10th to 90th percentile 11 to 43), 27.7 percent living alone (15 to 49). Browser check on Murray Hill: 11 percent with children, 51 percent living alone, 30 percent married couples, 20 percent with someone 65 or over.
Caption changed: it no longer claims one geography, because income and home value follow the housing read while age and household type follow the diversity read and the two can differ (G1).
