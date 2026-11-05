# Brief: independent timetable check of commute times (NYC, Metro-North)

For an agent that did not build or audit the commute feature. Written 2026-11-05. Pass criteria below are fixed before any result is read. Do not change them after you see numbers; if you think one is wrong, say so in your report and still report against it.

## What is being tested
HomeFit stores a transit time from each NYC catalog place to the hub `nyc_midtown_east` (Grand Central, pin 40.7527, -73.9772) in `data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl`, field `work_commute.nyc_midtown_east.transit_station`. It was built with the r5py router on the schedule labelled 2026-10-13 as the best-timed trip departing the station between 7:30 and 8:45. For rail towns it starts at the station platform. The question: does that number match what the published Metro-North timetable says?

## Rules (read first)
- Work offline from the repo plus published timetables. No Google calls, no API keys, no live HomeFit scoring.
- Downloads: ask the owner first, state filename, source and size. Put each in its own new empty folder. Run Python with `-I` and pass paths as arguments; do not run scripts from inside the download folder.
- Do NOT open `work_commute` for the sample towns until you have written down every timetable time. Record them in a file first (town, station, train departure, scheduled arrival at Grand Central, running time in minutes, source URL, timetable effective date). Only then read the stored numbers.
- No em dashes in any output. Say plainly what you verified and what you could not.

## Sample
Every catalog town served by Metro-North whose station is listed in `MNR_NEW_HAVEN`, `MNR_HARLEM` or `MNR_HUDSON` in `scripts/manual/fix_cbd_station_coords.py` and that has a `transit_station` value for `nyc_midtown_east`. Expect about 30 towns. Do not use LIRR or NJ Transit towns (they end at Penn Station or Grand Central Madison, a different destination).

## Timetable measure
For each town's station: among weekday trains that depart that station between 7:30 and 8:45, take the shortest scheduled running time to Grand Central Terminal (use the published schedule that was in effect for the week of 2026-10-13 if you can find it; otherwise the nearest current one and say which). That is the timetable running time. Use the agency's own published timetable only. A third-party app is not a source.

## Comparison
difference = stored `transit_station` minutes minus timetable running time. The stored number also includes a short walk from the platform to the hub pin, so expect it to be slightly higher than the timetable.

## Pass criteria (fixed)
1. Median absolute difference at most 6 minutes.
2. No town differs by more than 15 minutes in either direction.
3. At least 80% of towns within 8 minutes.
(An earlier note said "median under 5". It was set to 6 before any result was read, to allow for the walk from the platform to the pin.)

## Report
Per-town table (town, station, timetable minutes, stored minutes, difference), the three criteria with pass or fail, the source and effective date of each timetable, towns you could not check and why, and any pattern in the misses (line, express vs local, early vs late). State plainly what is verified and what is not.

## Not covered by this check
SF and LA (no timetable comparison planned), drive times, and hub-snap error.
