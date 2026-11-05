# Commute time (personal priority): DPv2 spec sheet and audit

Level: 0 (audit done 2026-11-04, no scoring change made). Proposed after approved fixes: Level 1.
Scope: a personal, client-side priority (minutes from a place to the user's workplace). Not a pillar, not in the general score as designed. See "Discrepancy" below: the general happiness index still carries a 5% commute term.

Verification key: VERIFIED = I read the source text or abstract in this session. SUMMARY = seen only in a search summary or abstract listing. UNVERIFIED = not seen.

## 1. Spec sheet

```
Pillar: Commute time (personal priority, key commute_time)
Construct (one sentence): Exposure, the one-way door-to-door minutes from a place to the user's
  workplace hub, scaled by office days a week.
Reference frame: fixed standard (minutes of lost personal time, same for every place)
  Evidence for the frame (tier 1 published study | tier 2 revealed-preference proxy | tier 3 survey):
  Tier 1: longer commutes lower leisure and job satisfaction and raise strain (Clark et al. 2020,
  VERIFIED abstract); the effect on overall life satisfaction is contested (Stutzer and Frey 2008 find a
  loss, VERIFIED abstract; Clark 2020 and Dickerson, Hole, Munford 2014 find none in general, the latter
  VERIFIED by an earlier session, not rechecked here). Tier 2: workers' marginal cost of an hour of
  commuting about 17 euros in a Dutch search model (van Ommeren and Fosgerau 2009, SUMMARY). Time is a
  physical cost, so no peer norm applies.
Measurement area: other. Destination = nearest of 11 or 12 precomputed job hubs within 15 miles;
  origin = catalog place centroid, plus rail station for commuter-rail towns (faster kept).
  Reason: hubs are chosen from LODES job counts (greedy coverage, then moved to the nearest transit
  interchange). Reason for 15 miles: undocumented (TODO).
Place context inputs used and remaining area-type uses: none for catalog places. The fallback for a
  searched address (not in the catalog) uses straight line x area-type speed (estimatedDriveMinutes).
  That is an area-type scoring input and needs a reason or removal (principle 14).
Inputs and data sources (with vintage):
  Transit: r5py over agency GTFS, best-timed trip (1st percentile of departures swept every minute
    7:30 to 8:45), one typical weekday per agency, schedule label 2026-10-13, built 2026-10-09 (NYC, SF)
    and 2026-10-10 (LA). Includes walk to stop, waits and transfers.
  Drive: Google Distance Matrix, best_guess traffic, 7:30 and 8:15 departures, no parking time. Hidden for
    transitOnly hubs.
  Hubs: frontend/lib/workZones.json. NYC 12, SF 11, LA 12, Seattle 4 (no data stored, picker hides them).
Parameters:
  name | value | source | plausible range | sensitivity result
  plateau end | 15 min = 100 | none | unknown | not run
  anchor | 30 min = 80 | "Marchetti's constant" (cited in code) | unknown | not run
  knots | 60 min = 50, 90 min = 0, linear between | none | unknown | not run
  office-days blend | score = 100 - (100 - s) x days/5 | none (linear in exposure) | unknown | not run
  snap limit | 15 mi | none | unknown | error measured below
  mode rule | min(transit, drive); transitOnly hubs transit only | design | n/a | n/a
  happiness-index weight | 0.05 | HAPPINESS_WEIGHTS_PROPOSAL (judgment) | 0 to 0.15 | not run
Shared inputs with other pillars: public_transit_access stores an area-mean commute that feeds the
  general happiness index when no hub is set. Same Census commute source as the transit pillar.
Pin-shift sensitivity: not applicable to the destination; origin is the place centroid. Hub-snap error
  is the equivalent test (section 3).
Independent validation source and result: not yet run (brief in section 6).
All-places check: section 3, 2026-11-04.
Fail-loud conditions: no route in the chosen mode returns null and the pillar silently drops out of the
  place's total (gap 3). Transit-only hub with drive mode returns null.
Launch check pairs: proposed in section 6, not yet run.
Known data limits: only NYC, SF and LA have stored times (NYC 191 of 193 places, SF 110 of 113, LA 105
  of 105). 17 other metros have none. Rail-station access time (survey median 7 min, NYC only per the
  playbook) is not in the app. Drive excludes parking. Transit is the best-timed trip, drive is a peak
  trip.
Last re-validated: never.
```

## 2. The three parts

### Part 1: the times
- R5 versus Google, NYC only: Google transit times are not in the catalog any more (R5 replaced them), so I rebuilt them from git (parent of d6912ed6) and paired 1,899 place-hub pairs. Median absolute difference 3.0 min, 71% within 5 min, 89% within 10, p90 10.8 min, median signed difference +0.2 (R5 minus Google). Per hub the bias is within 3.3 min (Jersey City -2.2, White Plains +3.3, Stamford +2.4). No earlier recorded result exists in docs. SF and LA: no comparison possible, Google transit was never committed for them. `compare_r5_google.py` cannot rerun on the current catalog for the same reason.
- Hub snap (section 3 has the numbers): the error is large for jobs more than a few miles from a hub.
- Unreachable pairs: stored as null. NYC 11 transit pairs, SF 40, LA 23.

### Part 2: the curve
- Shape: flat 100 to 15 min, 80 at 30, 50 at 60, 0 at 90 and beyond. Same score per minute for transit and drive.
- Evidence check. The studies show a small cost that rises with duration (Clark 2020: strongest on leisure satisfaction; Chatterjee et al. 2020 review, SUMMARY: satisfaction falls as commute length grows whatever the mode). None gives knots. The flat plateau to 15 min and the 0 at 90 min have no support. Revealed-preference work prices an hour of commuting at a roughly constant amount (van Ommeren and Fosgerau, SUMMARY), which favors a straight line over a plateau.
- "Marchetti's constant" is not a wellbeing finding. It is a travel-time-budget hypothesis; a critical review (Mokhtarian and Chen 2003, SUMMARY, volume and pages UNVERIFIED) found expenditures are not constant except at the most aggregate level. It should not be cited as the anchor.
- Transit versus drive penalty: none in the code. Evidence for one: the Chatterjee review (SUMMARY) reports public transport users least satisfied, walkers and cyclists most. Time-value work (Wardman meta-analyses, SUMMARY) weights walk and wait time about 1.5 to 2 times in-vehicle time. R5 minutes already include walk, wait and transfers, so a blanket transit multiplier would count that twice. Evidence supports at most a small multiplier on the out-of-vehicle part only, and we do not store that split.

### Part 3: combining
- The user sets commute to Low, Medium or High (default None). Tokens are 1, 2, 3 like every pillar. With 12 other pillars at Medium (24 tokens), High is 3 of 27, about 11% of the total. The score is dropped (not zeroed) when null, and other weights renormalize.
- Office days scale the penalty linearly; 0 days removes commute entirely.

## 3. Measurements (offline, stored data only)

All-places distribution, current curve, faster usable mode (transitOnly hubs use transit):

| Metro | Place-hub pairs | Median minutes | Median score | At 100 | At 0 |
|---|---|---|---|---|---|
| NYC | 2,292 | about 54 | 56 | 3% | 6% |
| SF | 1,210 | about 55 | 55 | 5% | 12% |
| LA | 1,260 | about 41 | 66 | 8% | 1% |

Worst hubs: SF Sunnyvale 24% at 0, Cupertino 20%, San Jose 17%; NYC Jersey City 12%, Stamford 10%. No ceiling clumping. For non-transitOnly hubs transit beat drive in only 8% (NYC), 3% (SF), 3% (LA) of pairs, median transit/drive ratio 1.36, 1.67, 1.81.

Hub-snap error. Share of metro jobs (LODES H3 res-8 job counts, jobs within 40 miles of a hub; the 40-mile universe is my choice) by distance to the nearest hub:

| Metro | Within 0.6 mi | 0.6 to 3 mi | 3 to 15 mi | Beyond 15 mi (rejected) |
|---|---|---|---|---|
| NYC | 21% | 13% | 36% | 30% |
| SF | 18% | 28% | 33% | 21% |
| LA | 10% | 20% | 30% | 40% |

Error proxy: for every pair of hubs, the absolute difference in time from the same origin, grouped by hub separation. This is how far time moves when the destination moves that far. Median (p90) minutes, transit:

| Separation | NYC | SF | LA |
|---|---|---|---|
| under 2 mi | 6 (13) | 10 (17) | 8 (17) |
| 2 to 4 mi | 8 (19) | 9 (19) | 11.5 (34) |
| 4 to 8 mi | 12 (22) | 22 (36) | 21 (43) |
| 8 to 15 mi | 23 (35) | 30 (60) | 34 (59) |

Job-weighted median error among jobs within 15 miles: transit about 11 min NYC, 16 SF, 17 LA; drive about 12, 6, 8. At roughly 1 score point per minute in the 30 to 60 minute range, that is 10 to 17 commute-score points, or about 1 to 2 points on a total at High priority. Limit of this proxy: hub pairs are not workplace-to-hub pairs, and hubs sit on transit interchanges, so it likely overstates drive error and is rough for transit. It is a bound on order of magnitude, not an exact error.

## 4. Audit gap table

| # | Gap | Principle | Recommended fix | Expected score impact |
|---|---|---|---|---|
| 1 | Curve knots have no source; Marchetti cited as anchor | 4 | Record knots as unsourced with range; drop the Marchetti claim; keep the shape unless owner chooses a linear option | None if kept |
| 2 | Plateau at 15 min and zero at 90 min unsupported | 4 | Option B below | Under 1 point on total |
| 3 | No route in the chosen mode drops the pillar, so a place with no transit route beats one with a 90-minute route | 9, 16 | Score 0 and label "no route" when the user picked that mode; leave out only when no hub is set | NYC 11, SF 40, LA 23 pairs; for a place averaging 55, about 6 points on total at High |
| 4 | Hub snap: 21% to 40% of jobs are beyond 15 mi, and median error 11 to 17 min inside it | 6 | Show snap distance and an error band on the card; say the time is "to the nearest hub" | Display only |
| 5 | Searched-address fallback keys speed on area type | 14 | Use one fixed speed, flag as an estimate, or return null | Non-catalog places only |
| 6 | No transit versus drive penalty | 4 | Do not add; minutes already include walk and wait; record as a range (1.0 to 1.5 on out-of-vehicle time if split ever stored) | None |
| 7 | Happiness index keeps commute at 0.05 using area-mean commute when no hub is set; docs call commute "excluded from the general index" | docs vs code | Owner decision: remove the term (changes the general score) or correct the docs | Up to about 5% reweighting of every place's happiness index |
| 8 | Rail-station access time not in times (survey median 7 min, NYC only); drive excludes parking | 11 | Disclose on the card; no new data | About 7 min for rail towns |
| 9 | Transit is best-timed, drive is peak average; asymmetric | 11 | Disclose; R5 p50 exists but is not stored | Transit looks 0 to 10 min better than a typical untimed trip (p50 not measured here) |
| 10 | Coverage: 3 of 20 metros have times; Seattle hubs defined with no data | 11 | Surface "not available for this metro" in the picker | None |
| 11 | Office-days blend and snap limit unsourced | 4 | List as TODO with range unknown | None |
| 12 | SF and LA R5 never compared with another source | 7 | Independent check in section 6 | n/a |

## 5. Options (one recommendation)

- A: Document only. Keep curve, list unsourced knots. Fix gaps 3, 4, 5 only.
- B: A plus a straight line in minutes (100 at 0 or 10, zero at 120) instead of the plateau and the 90-minute zero. Matches revealed-preference linear cost, but the endpoints are still choices.
- C: A plus remove commute from the general happiness index (gap 7).

Recommendation: A, with gap 7 raised to you separately as a decision. Reason: no study supplies knots, so B swaps one unsourced shape for another; gap 3 is the only change with a clear evidence-based direction.

## 6. Level 2 checks adapted to a personal priority

Pass criteria, fixed before results:
1. All-places distribution: for each hub, no more than 15% of places at 0 or at 100 (SF Sunnyvale, Cupertino, San Jose currently fail the 0 side; Part of this is real geography).
2. Launch pairs: each should differ by at least 20 score points to the same hub. NYC to Midtown East: Bronxville (short) vs Montauk or Babylon (long). SF to Mountain View: Mountain View vs Pacifica. LA to Downtown: Pasadena vs Lancaster/Santa Clarita (all example places are unconfirmed: confirm each exists in the catalog before running). Pairs that should be similar: Midtown East vs Midtown North for the same place (within 5 min).
3. Hub-snap error: median under 10 min for jobs within 5 miles (currently proxy 6 to 22 min by separation; NYC and SF within 4 miles pass, 4 to 8 mi fails).
4. R5 versus Google: 80% of pairs within 10 min and absolute bias under 3 min per hub (NYC passes: 89% within 10, per-hub bias at most 3.3, White Plains 3.3 narrowly fails the bias line); SF and LA need fresh Google transit calls. I am asking before any API call: it would need Google Distance Matrix transit calls for a sample of about 100 SF and 100 LA place-hub pairs.
5. Independent validation brief for another agent: compare 30 NYC rail-town times to Midtown East against published MTA and NJ Transit timetable trip times for a 7:30 to 8:45 arrival-aligned departure; pass if the median absolute difference is under 5 min and none exceeds 15 min. The validator must not see the R5 output until it has written down the timetable times.

Results: not yet run beyond what section 3 states. Proposed level: stays 0 until fix 3 is approved and shipped and checks 2 and 5 are run.

## 7. Open items for owner
1. Approve fix 3 (no route in chosen mode scores 0 and is labeled).
2. Decide gap 7 (happiness index commute term).
3. Approve the Google call for SF and LA R5 comparison (about 200 element calls), or skip it.
4. Citations still to verify from full text: Stutzer and Frey magnitude (the "+18 minutes, -0.09" figure in HAPPINESS_EVIDENCE_NOTES is UNVERIFIED by me; the PDF would not parse), Chatterjee 2020 mode ordering, van Ommeren and Fosgerau euro figure, Wardman multipliers, DOT 2016 guidance.

## Sign-off
Level: 0. Date: 2026-11-04. TODOs accepted: none yet.
