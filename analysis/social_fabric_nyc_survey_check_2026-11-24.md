# Social Fabric against a surveyed measure: NYC "neighbors willing to help" (2026-11-24, offline, nothing in scoring changed)

Source: NYC Health Department, Community Health Profiles Public Use Dataset (2026 edition, `https://www.nyc.gov/assets/doh/downloads/excel/episrv/2026-chp-pud.xlsx`), variable `Helpful_Neighbor`: percentage of adults who strongly or somewhat agree that people around their neighborhood are willing to help their neighbors, NYC Community Health Survey 2021-2022, weighted, by community district (59 districts). This is a real survey item, not a modeled estimate. The file was fetched through the web-fetch agent (direct requests to nyc.gov return 403 here) and read from the harness-saved copy; it is not committed. Community district boundaries: NYC Open Data `5crt-au7u`. Scripts: `/tmp/claude-0/-home-user-home-fit/8e58f870-675d-5e0a-9287-bb5eddc329b2/scratchpad/cd_test.py`.

## Carroll Gardens' district

Community district 306, "Park Slope and Carroll Gardens", is surveyed at 76.5% agreement against 58.0% citywide, second of 59 districts (first is Tottenville and Great Kills at 77.5%; last is Fordham and University Heights at 32.9%). Five catalog places fall inside the district boundary: Carroll Gardens, Cobble Hill, Gowanus, Park Slope and Red Hook, so the district includes Red Hook. The v20 pillar averages 46.6 across them, which ranks 26th of the 50 districts that contain a catalog place.

## Pillar against the survey (Spearman; 81 places in 50 districts; district value is the mean of its catalog places)

| Measure | District level | 
|---|---|
| v18 pillar | 0.470 |
| v20 pillar | 0.469 |
| participation | 0.542 |
| economic connectedness | 0.482 |
| civic nodes | 0.201 |
| cohesion | -0.024 |
| rootedness | -0.197 |

Place level (81 places): v20 0.379, v18 0.394.

## Reading

The pillar tracks surveyed neighbor-helping moderately, mostly through participation and economic connectedness, and the district that includes Carroll Gardens is near the top of the survey but at the median of the pillar. Limits: one survey item covers one facet of connection; 1 to 5 places per district; the district also contains Park Slope; survey years differ from the Atlas and census inputs. Cohesion shows no relation and rootedness a negative one against this item, which conflicts with the CDC-based result for cohesion (0.31), so 50 districts cannot settle weights. Nothing was fitted to this result.
