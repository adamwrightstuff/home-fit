# Rent in the same-size housing comparison (plan, not built)

Status: teed up 2026-11-27, nothing in code yet. Owner asked for rent alongside buy, with a simple rent vs buy toggle.

## Goal

The same-size comparison scores every place as "what a home this size costs me here each month, as a share of my income". Today that cost is always a purchase (Zillow ZIP value, 7% mortgage, ZIP tax, insurance). Renters need the same comparison on rent.

## Data (both free downloads, no API key)

- Zillow ZORI by ZIP, current typical asking rent, all unit sizes combined:
  `https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv` (about 10 MB, monthly, latest column 2026-10-31). Example: ZIP 11231 (Carroll Gardens) $4,565.
- Census ACS 2023 5-year table B25031, median gross rent by bedrooms (no bedroom, 1 to 5+), every geography:
  `https://www2.census.gov/programs-surveys/acs/summary_file/2023/table-based-SF/data/5YRData/acsdt5y2023-b25031.dat` (38 MB, pipe-delimited; ZCTA rows start `860Z200US`, metro rows `310M700US<CBSA>`, nation `0100000US`).
- The Census API path is blocked here: the connected credential does not reach api.census.gov, which takes its key only in the query string (requests redirect to missing_key / invalid_key). The file download above needs no key.

## Why not Census rent alone

ACS median gross rent is what current tenants pay, including long-time and rent-stabilized leases, not what a mover would pay. ZIP 11231 3-bedroom: ACS $2,392 (margin of error plus or minus $1,080) against a $4,565 typical asking rent for all sizes. Shown as a moving cost it would be a believable wrong number (DPv2 principle 9). ZIP-level bedroom figures are also noisy (11231: 3-bed below 2-bed).

## Method (proposed)

rent for N bedrooms at a place = ZORI for the place's ZIP x (metro ACS median rent for N bedrooms / metro ACS median rent, all sizes). Metro = the place's CBSA; fall back to the national ratio when the metro row is missing. Ratios, national: studio 0.88, 1-bed 0.88, 2-bed 0.99, 3-bed 1.11, 4-bed 1.38, 5+ 1.47. NYC metro (35620): 1-bed 0.92, 2-bed 1.02, 3-bed 1.17, 4-bed 1.34. Carroll Gardens 3-bed comes out about $5,360.

This is a modeling choice, not a finding: Zillow sets the level, the Census sets only the size ratio. Record it as such in the spec. Known limit: rent-stabilized metros flatten the Census ratios, so large units are understated there.

## Build steps

1. New script `scripts/baselines/add_catalog_rents.py`: download both files into data_cache (git-ignored, or a temp dir), map each place's metro to its CBSA (the metro agent registry has CBSA codes; data/metro_registry.json does not), write `rent: [studio, 1, 2, 3, 4, 5+]` per place into `data/catalog_housing_costs.json` plus top-level `rent_as_of` and `rent_method`. A ZIP with no ZORI gets `rent: null` (no fill).
2. Frontend `lib/budgetCost.ts`: `HousingCost.rent`, `BudgetFilter.tenure: 'buy' | 'rent'` (default buy), cost for rent = the rent figure (no mortgage, tax or insurance). `bestCost`, the list row and the cost reason text read tenure.
3. Rent vs buy toggle: in the Explorer budget filter next to bedrooms (UX rule 2, one home per action; the profile's "Home you need" summary reads it and links back). Hide down payment when Rent is selected (UX rule 3, controls follow selection). Saved with the budget in the profile.
4. Same-size comparison (`lib/reweight.ts` `applySameSizeHousingToScore`) uses rent when tenure is rent; the housing narrative says "to rent" instead of "to buy (7% mortgage, tax and insurance)".
5. Checks: coverage of places with a rent, Carroll Gardens and two suburbs by hand against listings, the all-places spread at two incomes (same as the buy check in the 2026-11-26 session).
