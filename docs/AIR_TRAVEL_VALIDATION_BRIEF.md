# Air travel access: independent validation brief (for an agent that did not build the pillar)

Written 2026-11-04. Pass criteria are fixed here before any result exists. Do not change scoring, do not push, work offline from stored data except where a check below says it needs a read, and ask the owner before any API call or download (downloads go in their own empty folder; run Python on them with `python3 -I`). No em dashes.

## Inputs to read (do not edit)
- Pillar: `pillars/air_travel_access.py`; data: `data_sources/static/airports.json` (412 origins), `data_sources/static/airport_nonstop_served_2023.json` (served sets and CY2023 boardings, built from BTS T-100 and FAA, so they are NOT independent of the score).
- Catalog result: `analysis/air_travel_dpv2_recompute_2026-11-04/final/*.jsonl`, key `score.livability_pillars.air_travel_access`.
- Definition of served: at least 52 departures performed in 2023 and at least 5 passengers per departure, domestic destinations only.

## V1. Drive minutes against a second router
Sample 60 place-to-airport pairs from the catalog: 30 to airports added on 2026-11-04 (source `estimated_from_distance`), 30 to older airports (source `routed`). Stratify by area type. Get free-flow car minutes from a router other than the public OSRM demo server (the owner decides which; any paid or keyed service needs the owner's yes first).
- PASS: median absolute percentage error of the stored minutes <= 20 percent for both groups, and for the 30 estimated pairs the median absolute error <= 10 minutes.
- Report pairs off by more than 30 minutes. Do not drop water-crossing pairs; list them (Bainbridge Island to PAE is the known case).

## V2. Served destination counts against airports' published route lists
Pick 40 airports: 20 added on 2026-11-04 and 20 older, spanning large to small. For each, count nonstop domestic destinations from the airport's own published route map or timetable for 2023 or early 2024 (not BTS).
- PASS: Spearman correlation between our served-set size and the published count >= 0.85, and median absolute relative difference <= 30 percent (our 52-departure rule drops seasonal and very thin routes, so a modest undercount is expected). Report airports with a difference above 50 percent.

## V3. Pair spot check against an independent schedule source
Draw 100 origin-destination pairs we call served and 100 pairs we call not served (both endpoints among the top 50 airports by boardings, not served = not in our set).
- PASS: at least 95 of 100 served pairs confirmed as scheduled nonstop in 2023, and at most 5 of 100 not-served pairs found with at least weekly nonstop service in 2023.

## V4. Construct sanity (read-only, no pass gate)
For 10 catalog places the owner would call air-travel rich and 10 poor (agent proposes, owner confirms before scoring), report whether the score order matches. Written as findings only.

## Deliver
A short write-up with each check, sample sizes, the numbers, PASS or FAIL against the criteria above, and what could not be done. Do not edit the pillar doc's spec sheet; hand the write-up to the owner.
