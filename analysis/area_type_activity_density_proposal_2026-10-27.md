# Area type: proposal to measure the surrounding area, not one tract

Date: 2026-10-27. Status: PROPOSAL ONLY. Nothing here is implemented, no scoring code or catalog file was changed, and nothing was committed. Every number below was computed offline from stored catalog data, the Census 2023 tract Gazetteer, ACS 2022 tract tables and the repo's LODES hex file.

## The problem

The shared area type (`classify_morphology`) decides from two inputs: the population density of the single Census tract under the pin, and the OSM business count within 1 km. Both are weak:

- A pin on a low-population tract inside a busy area reads as suburban or rural whatever is around it. Glendale, NY: pin density 17 per square mile (a cemetery tract); the surrounding 1 km holds about 36,800 per square mile. Downtown LA: 1,977 at the pin, 13,716 around it. Bucktown, Chicago: 6,247 at the pin, 18,633 around it.
- The OSM business count is incomplete and uneven. Midtown East, NY has 76 OSM businesses and about 430,000 jobs per square mile.
- The cutoffs (ratio of businesses to density of 100, density 25,000, 12,000, 3,000, 800, business counts 100 and 150) carry no citation in the code. Treat them as unsourced.
- On the same stored density and count the classifier disagrees with the type stored in the catalog for 67 of 1,470 places, and 5 places come out "unknown" through the dead-tract guard. Some of that is count mismatch between the pre-pillar count and the amenities pillar count.

## Evidence

### What published sources say (verified unless marked)

| Source | What it gives | Limits |
|---|---|---|
| EU/OECD Degree of Urbanisation (Eurostat manual; Dijkstra et al. 2021, Journal of Urban Economics) | Urban center: contiguous 1 km cells, at least 1,500 people per km2 (about 3,900 per sq mi), at least 50,000 people in the cluster. Urban cluster: at least 300 per km2 (about 780 per sq mi), at least 5,000 people. | Population only. Read from the Eurostat page; the paper's full text not read. |
| NCES locale codes (city, suburb, town, rural) | City and suburb defined by relation: inside an urbanized area and its principal city, or inside the urbanized area but outside it. Town and rural graded by distance. | Relational, not density. Not adopted by the classifier today. |
| Census 2020 urban area criteria | Housing-unit density: 425 per sq mi initial core, 200 remainder, 1,275 nucleus. | Housing units, not jobs. Secondary slides, not the Federal Register notice. |
| Giuliano and Small (1991), via SCAG documentation | Employment subcenter: contiguous zones at least 10 jobs per acre and at least 10,000 jobs. | This marks job centers, not urban cores. Far too low for a core. SCAG uses it only as a sanity check. Full paper not read. |
| Puget Sound Regional Council (transit density paper, read directly) | Regional Growth Centers: at least 45 activity units (people plus jobs) per gross acre. Employment areas at 50 jobs per acre or more are preferred targets for high-capacity transit. Cites Pivo and Frank (1994): transit use climbs past 30 activity units per acre and most past 45 to 50. | A regional (Seattle) standard. Pivo and Frank not read directly. |
| Florida DOT TOD table (second-hand, via an Indian TOD guide) | Gross jobs per acre by center type and mode, for example Regional Center 200 to 250 (heavy rail), 100 to 200 (light rail), 50 to 125 (bus). | Florida, transit station targets, second-hand copy. Not a national standard. Do not build a rule on it. |
| Ewing and Cervero (2010), JAPA | Density alone is weakly linked to travel once destination accessibility, diversity and design are controlled. | Abstracts and summaries only. Challenged by Stevens (2016). |
| EPA Smart Location Database | Publishes gross employment density in jobs per acre for every block group. | I found no thresholds. Fact sheet PDF was unreadable. |

Not found: any published national cutoff for "urban core" or "downtown" by employment density. The advocacy figures for downtowns (Chicago 294, Center City Philadelphia 203, Des Moines 42 jobs per acre, from a Center City District deck) are examples, not a standard.

### What our own data shows (offline)

Method: for each catalog place, tracts whose Gazetteer center lies within 1 km of the pin (population and land area from ACS 2022 and the 2023 Gazetteer, both the 2020 tract layer), jobs from the LODES H3 res-8 hex file (hex centers within 1 km), commute shares from ACS B08301 over the same tracts. Fallback to the nearest tract when none is within 1 km.

Predicting commute behavior across 1,127 places with usable commute data (Spearman rank correlation):

| Measure | Transit commute share | Walk commute share |
|---|---|---|
| Single tract at the pin (today) | 0.62 | 0.49 |
| People in the 1 km circle | 0.67 | 0.54 |
| OSM business count (1 km) | 0.50 | 0.60 |
| Jobs per acre (1 km) | 0.41 | 0.63 |
| People plus jobs per acre (1 km) | 0.60 | 0.67 |

Median commute shares by people plus jobs per acre:

| Activity per acre | Places | Transit | Walk |
|---|---|---|---|
| 0 to 5 | 80 | 0.0% | 0.7% |
| 5 to 10 | 187 | 1.1% | 0.9% |
| 10 to 20 | 350 | 3.1% | 1.8% |
| 20 to 30 | 177 | 7.2% | 3.0% |
| 30 to 45 | 110 | 8.0% | 3.9% |
| 45 to 60 | 51 | 18.1% | 6.7% |
| 60 to 100 | 73 | 23.3% | 9.3% |
| 100 to 200 | 61 | 43.4% | 12.8% |
| 200 and above | 38 | 38.2% | 26.8% |

Transit use steps up between 30 to 45 and 45 to 60 per acre, which agrees with the Puget Sound figure. Walking rises most above 200.

Jobs per acre by stored type (median): rural 427 per sq mi, exurban 1,545, suburban 2,960, urban residential 16,850, urban core about 530,000 (two places). The classifier misses clear business cores: Financial District NY (206,000 jobs per sq mi), Financial District SF (164,000, stored suburban), Downtown Sacramento (68,000). 26 places exceed 200 jobs per acre and 50 exceed 100.

## Proposal (for decision, not implemented)

1. Replace the single-tract density with the density of the surrounding 1 km circle (people per square mile over tracts whose center lies within 1 km). Same footprint as the business count. Supported by the Degree of Urbanisation method (contiguous cells, not one unit) and by the correlations above.
2. Add jobs from the existing LODES hex file and use people plus jobs per gross acre as the density signal for the urban end of the scale. It predicts walking best and transit nearly as well.
3. Keep OSM business count only as a secondary signal, or drop it from the density decision, since it is the weakest predictor and varies with OSM completeness.
4. Retire the dead-tract guard once the circle density is in, after confirming it stops firing.
5. Set cutoffs from the behavior curve and the published anchors, not by picking numbers: urban/rural boundary near the Degree of Urbanisation values (about 780 and 3,900 per square mile), the core end where transit and walking behavior steps up (about 45 per acre for the first step). Any cutoff without a source stays marked TODO.
6. Urban core: owner decision 2026-10-27: drop it as a class. Its definition is subjective and changes by city, and no published cutoff exists. See the section below for what dropping it touches.

## Open questions for the owner

1. Should area type describe residents (density), activity (people plus jobs), or destination access? Ewing and Cervero favor access over density; the data favors activity for walking and circle density for transit.
2. Urban core: decided to drop (2026-10-27). Remaining question is the safest way to retire it, see below.
3. NCES-style city versus suburb (relation to a principal city) versus density-based suburban: keep density-based?
4. How should a metro without transit be treated? Dense places in car-oriented metros dilute the transit bins.
5. 1 km circle by tract-center membership is coarse (about 4 hexes, a few tracts). Is an area-weighted version worth the work?
6. Runtime source: a national tract table (population, land area, centers; about 85,000 rows) plus the LODES hex index would replace the live Census density call with a local lookup. It needs a national ACS population pull (about 51 calls) to build. Approve that build?

## What would change if adopted

- Circle density alone changes the type for 211 of 1,470 catalog places (14%): exurban to suburban 95, urban residential to suburban 24, rural to exurban 21, suburban to urban residential 19, suburban to exurban 18, rural to suburban 15, rural to unknown 8, and smaller groups. I have no labeled ground truth to say all of these are corrections; the clearest are listed above.
- Midtown NY would leave urban core under circle density alone (circle density 39,010, 1,228 businesses, ratio below 100), which is wrong; the jobs signal is what keeps it a core. Do not ship the density swap without the jobs signal.
- Pillars that read the area type: active outdoors, built environment, natural beauty, amenities, air travel, transit, healthcare, economic, housing (the Census lookup skips place-level data for urban core), climate (confidence only), social fabric, diversity, community safety, schools. Radii, expectations and baselines shift for every place whose type changes.
- The catalog cannot be fixed by recomputing stored numbers alone, because radii and Overpass queries depend on type. Places whose type changes would need those pillars re-scored, which needs the private Overpass server and the Places budget. This should be a separate branch with a before and after diff, as for the place-context work.
- Live scoring: a local lookup replaces a Census call, so request time should fall, but that is unmeasured.

## Housing units as an input (owner note, 2026-10-27)

We can also use the type of housing and housing-unit density: units per square mile and the structure mix (for example single-family versus multi-unit buildings, Census table B25024). The Census 2020 urban area criteria use housing-unit density (425 per square mile initial core, 200 for the remainder, 1,275 for a high-density nucleus), so there is a published anchor. The repo does not read B25024 or the housing-unit count today (it reads year-built, B25034), so using it needs one more state-level ACS pull and a test against the same commute outcomes before it is added to the rule. Open: does housing-unit density improve on people plus jobs per acre at predicting transit and walking, and is the structure mix worth the added complexity?

## Dropping urban core: what it touches (measured 2026-10-27, nothing changed)

- Only 2 of 1,470 catalog places are stored as urban core (Midtown NY and Midtown East NY). The class is rare in the catalog, but live scoring can assign it to any place with at least 100 OSM businesses within 1 km and a business-to-density ratio of 100 or more.
- The string `urban_core` appears about 287 times in Python outside tests and scripts, mainly in the architectural diversity data (46), natural beauty (38), data quality (24), regional baselines (14), active outdoors (11) and radius profiles (8). It also keys five baseline data files (IRS engagement stats, voter turnout stats, social cohesion bands, social fabric bands, launch-check contrasts). None of the frontend source references it.
- Lowest-risk way to retire it: the classifier never returns `urban_core` and returns `urban_residential` instead. The downstream urban core branches then become unreachable and can be removed pillar by pillar later. This changes scores only for places the classifier labels urban core today, and in the catalog that is the two Midtown places.
- Correction (2026-10-27, checked in `data_sources/census_api.py`): an earlier draft of this note said dropping urban core would give Midtown-like places city-wide housing data. That is wrong. Both `get_housing_data` and `get_diversity_data` already carry a size ceiling that rejects place-level data for large places (200,000 occupied housing units for housing, 200,000 adults 25 and over for diversity) and falls back to the tract. New York has millions of units, so Midtown goes to the tract with or without the urban core skip. The skip only matters for a small place labeled urban core, which the catalog has none of (the two urban core places are both New York and use tract data either way).

### Draft housing and diversity geography rule (not implemented)

1. Remove the `area_type == "urban_core"` condition from `get_housing_data` and `get_diversity_data`. Geography then depends only on place size, not on the area type.
2. Keep the existing ceiling: use the place or county subdivision when it is at or under the ceiling, otherwise use the tract. Housing measures size in occupied units and diversity in adults 25 and over; align them on one measure so a place cannot pass one and fail the other.
3. The 200,000 figure is unsourced. Mark it TODO in the code. The housing audit (D14) found the opposite weakness in medium places, where one place median is applied to every pin inside, and the tract instability in the other direction. The size rule and the D14 pooling decision belong together, so keep 200,000 until D14 is decided.
4. Effect: no catalog place changes geography (both urban core places already use tract data). Live, a small place that is labeled urban core today would move from tract to place data. That case is unmeasured and should be rare.
5. Test: a place at 199,999 and one at 200,001 units pick place and tract; a large-city neighborhood labeled urban residential picks tract; `urban_core` no longer changes the choice.

## Limits of this evidence

- Association, not cause. Rank correlations differ by only 0.05 to 0.13.
- Transit share depends on whether the metro has transit.
- 1,127 of 1,470 places had commute data in the circle; 3 places have no LODES hexes within 1 km.
- Catalog stored values, not live scores. The live-versus-catalog divergence in `docs/LIVE_SCORER_VS_EXPLORER.md` applies.
- Citations from search summaries are marked above; verify the originals before they go into a design document.

## Reproduction

Scratch scripts and outputs are in the session scratchpad (`circle_density_rows.json`, `lodes_circle_rows.json`, `behavior_rows.json`) with downloaded data in `gaz_tracts/` and `acs_pop/`, `acs_mode/`. They are not in the repo.
