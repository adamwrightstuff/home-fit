# Typical (median) transit commute times (plan, not built)

Status: teed up 2026-11-27, nothing in code yet. Companion to docs/RENT_PLAN.md for the next laptop session.

## Problem

Stored transit minutes in each place's `work_commute` are the best-timed trip: the 1st percentile of departures swept every minute 7:30 to 8:45 on one weekday (docs/COMMUTE_TIME.md, spec sheet). That is consistent across places but not neutral. A place with frequent direct service loses almost nothing between best and typical; a place with infrequent trains and a timed transfer (Glen Rock: Bergen County Line, change at Secaucus, 53 min best to Midtown West) can be 10 to 20 minutes worse on a typical day. Best times flatter infrequent, transfer-heavy suburbs relative to frequent direct service. COMMUTE_TIME.md gap 9 already notes "R5 p50 exists but is not stored".

Why best-timed was chosen is not recorded. The R5 script is not in the repo; the likely reason is matching Google transit (one scheduled trip per departure), which R5 replaced and was checked against (89% of NYC place-hub pairs within 10 min). Confirm from the owner's notes for the 2026-10-09 and 10-10 builds if they exist.

## Steps

1. Recreate the routing script in the repo (`scripts/catalog/build_r5_transit_times.py`): r5py `TravelTimeMatrixComputer`, origins = catalog place routing points (both origins the playbook uses, keep the faster), destinations = `frontend/lib/workZones.json` hubs, departure 7:30 with a 75-minute window swept every minute, `percentiles=[1, 50]`. Same weekday and schedule label as before so the 1st percentile reproduces the stored numbers.
2. Inputs, all free: OSM extract per metro (Geofabrik) and agency GTFS (NYC: NJ Transit rail and bus, MTA subway and bus, LIRR, Metro-North, PATH, NY Waterway; SF and LA agency lists as in WORK_COMMUTE_PLAYBOOK.md). GTFS via Transitland (TRANSITLAND_API_KEY) or agency feeds. Needs Java (r5py) and a few GB of memory; roughly 10 to 30 minutes per metro.
3. Reproduce first: the 1st percentile must match stored `transit` minutes (median absolute difference near 0). If it does not, stop and find out why before trusting the median.
4. Store `transit_p50` next to `transit` in `work_commute`, offline merge, no score change yet. Rebuild `data/` merged files the usual way (docs/CATALOG_TOOLKIT.md).
5. Report: per place and hub, median minus best; which places move most (expect transfer-heavy commuter-rail suburbs such as Glen Rock); rank changes in the commute pillar at a few hubs. Then the owner decides whether the commute score switches to p50.
6. If switched: frontend commute reads `transit_p50`, COMMUTE_TIME.md spec sheet and gap 9 updated, the "best-timed" disclosure becomes "typical".

## Not in scope

A separate per-transfer penalty. Time-value research weights waits about 1.5 to 2 times in-vehicle time, but stored minutes do not split waiting from riding, and p50 already captures realistic transfer waits.
