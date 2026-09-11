# Quiz → Pillar Weight Mapping

Reference document for reviewing how each quiz question affects the 11 scored pillars.

---

## Default weights (before any question is answered)

| Pillar | Key | Default |
|---|---|---|
| Schools | `quality_education` | 2 — Medium |
| Walkability | `neighborhood_amenities` | 2 — Medium |
| Safety | `community_safety` | 2 — Medium |
| Nat. Beauty | `natural_beauty` | 2 — Medium |
| Transit | `public_transit_access` | 2 — Medium |
| Affordability | `housing_value` | 2 — Medium |
| Community | `social_fabric` | 1 — Low |
| Outdoor Life | `active_outdoors` | 1 — Low |
| Healthcare | `healthcare_access` | 1 — Low |
| Climate Risk | `climate_risk` | 1 — Low |
| Diversity | `diversity` | 1 — Low |

Scale: 0 = None, 1 = Low, 2 = Medium, 3 = High

Climate Risk and Diversity are never touched by the quiz — they stay at Low 1 throughout.

---

## Q1 — Who's this move for?

| Answer | Weight changes |
|---|---|
| Family with kids at home | Schools → 3, Safety → 3, Community +1 |
| Planning to have kids soon | Schools → 2, Safety → 3 |
| Me or us, no kids planned | Schools → 0 |
| Empty nesters or retiring | Schools → 0, Healthcare +1, Outdoor Life +1 |

---

## Q2 — How does work shape where you live?

| Answer | Weight changes |
|---|---|
| In office most days | _(no change)_ |
| Hybrid or flexible | _(no change)_ |
| Fully remote or self-employed | Transit → 0, Outdoor Life +1, Nat. Beauty +1 |

---

## Q3 — Do you need to be near a train line?

_Shown when Q2 = office or hybrid_

| Answer | Weight changes |
|---|---|
| Yes — train or subway | Transit → 3 |
| No — I'd drive | Transit → 1 |
| I travel by plane for work | Transit unchanged; sets `air_travel_access` dealbreaker |

---

## Q4 — What's your max commute each way?

_Shown when Q2 = office or hybrid AND Q3 ≠ fly. Filter only — no weight changes._

| Answer | Filter output |
|---|---|
| Under 30 minutes | `filterCommuteMax = '30'` |
| Under 45 minutes | `filterCommuteMax = '45'` |
| Under an hour | `filterCommuteMax = '60'` |
| No hard limit | `filterCommuteMax = 'all'` |

---

## Q5 — How much city do you want around you?

| Answer | Weight changes |
|---|---|
| Dense city neighborhood | Walkability → 3, Nat. Beauty → 2, Transit +1 |
| Walkable town or inner suburb | Walkability → 2, Nat. Beauty → 2 |
| Quiet suburb | Walkability → 1, Nat. Beauty → 2 |
| Small town or rural | Walkability → 1, Nat. Beauty → 3 |

---

## Q6 — What does the outdoors mean to you?

_Multi-select. Logic evaluates the full set of picks._

| Selection | Weight changes |
|---|---|
| Trails & Regional Parks (in picks) | Outdoor Life → 3 |
| Waterfront (in picks) | Outdoor Life → 3 |
| Local Parks only (no trails/waterfront) | Outdoor Life → 2 |
| Mostly indoors — not a factor (alone) | Outdoor Life → 0 |

---

## Q7 — What scenery matters most to you?

_Shown when Nat. Beauty ≥ 2 after Q5/Q2. Multi-select. Skipping leaves weights unchanged._

| Selection | Weight changes | Filter output |
|---|---|---|
| Any pick(s) | Nat. Beauty → 3 | `filterNbTypes` includes selected types |
| Skipped | _(no change)_ | `filterNbTypes` = [] |

Scenery type values: `mountains`, `ocean`, `lakes_rivers`, `canopy`

---

## Q8 — How does price factor into your search?

| Answer | Weight changes |
|---|---|
| I need the best value I can get | Affordability → 3 |
| I'll pay more for the right place | Affordability → 2 |
| Price isn't the main consideration | Affordability → 1 |

---

## Q9 — What kind of neighborhood are you looking for?

_Filter only — no weight changes._

| Answer | Filter output |
|---|---|
| Established and stable | `filterTrajectory = 'Arrived'` |
| Either works | `filterTrajectory = 'all'` |
| Up-and-coming with potential | `filterTrajectory = 'Up-and-Coming'` |

---

## Q10 — How important is a sense of community?

| Answer | Weight changes |
|---|---|
| A lot — I want to know my neighbors | Community → 3 |
| Nice to have, not a priority | Community → 2 |
| Not really — I'm more private | Community → 1 |

---

## Q11 — What housing type works for you?

_Multi-select. Filter only — no weight changes._

| Answer | Filter output |
|---|---|
| Single-family home | `filterHousingType` includes `'single_family'` |
| Rowhouse or townhouse | `filterHousingType` includes `'rowhouse'` |
| Apartment or condo | `filterHousingType` includes `'condo'` |
| (skipped) | `filterHousingType` = [] (no filter) |

---

## Q12 — Any weather you couldn't live with?

_Multi-select. Filter only — sets `climatePrefs` dealbreakers._

| Answer | Filter output |
|---|---|
| Brutal winters | `climatePrefs.cold_tolerance = 'dealbreaker'` |
| Sweltering summers | `climatePrefs.heat_tolerance = 'dealbreaker'` |
| Rain and grey skies | `climatePrefs.rain_tolerance = 'dealbreaker'` |
| Extreme seasonal swings | `climatePrefs.seasons = 'want_consistency'` |
| Weather isn't a factor | _(no filter)_ |

---

## Notes

- **bump +N** means `bumpWeight(key, N)` — relative to whatever value the pillar has at that moment, capped at 3.
- **→ N** means `setWeight(key, N)` — absolute override regardless of prior value.
- Healthcare starts at Low (1) and is only boosted for empty nesters.
- The quiz also outputs `filterAoTypes` (area type, driven by the urban context) and `filterPoliticalLean` (from a political dealbreaker chip question using the same mechanics as Q12).
- `air_travel_access` is a dealbreaker flag in the payload, not a weighted pillar.
