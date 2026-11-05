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
Place context inputs used and remaining area-type uses: none. The searched-address fallback is distance
  only since 2026-11-05 (see change log).
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

Missing-data finding (2026-11-05): five places have no `work_commute` at all (NYC Maspeth, Southport; SF El Cerrito, Foster City, Los Altos Hills) although `r5_transit.csv` has non-null times for all five. Maspeth and Southport had it in the 2026-10-09 backup and lost it by 2026-10-16, when a `rescore_catalog_pillar` run rewrote their rows (the merge note starts `rescore_catalog_pillar_v1`). The three SF places show no `work_commute` in any backup I checked. Cause for SF is not proven. Fix 3 must score 0 only for a stored null on a place that has `work_commute`; the five are missing data and should be restored by rerunning the merge from the cached R5 output (offline, no API call). Genuine no-route places (Weston, Hidden Hills, far Marin hubs) have drive times 74 to 110 min; not checked against timetables.

## 5. Options (one recommendation)

- A: Document only. Keep curve, list unsourced knots. Fix gaps 3, 4, 5 only.
- B: A plus a straight line in minutes (100 at 0 or 10, zero at 120) instead of the plateau and the 90-minute zero. Matches revealed-preference linear cost, but the endpoints are still choices.
- C: A plus remove commute from the general happiness index (gap 7, decided: keep).

Recommendation: A, with gap 7 raised to you separately as a decision. Reason: no study supplies knots, so B swaps one unsourced shape for another; gap 3 is the only change with a clear evidence-based direction.

## 6. Level 2 checks adapted to a personal priority

Pass criteria, fixed before results:
1. All-places distribution: for each hub, no more than 15% of places at 0 or at 100 (SF Sunnyvale, Cupertino, San Jose currently fail the 0 side; Part of this is real geography).
2. Launch pairs (chosen 2026-11-05 from geography and place names before any score was read; all places confirmed present in the catalog; the earlier Montauk, Lancaster and Santa Clarita examples are not in it):
   Should differ (stored minutes in the faster usable mode at least 20 min apart, 20 min being about 20 score points in the 30 to 60 minute band):
   NYC to Midtown East: Murray Hill vs Babylon; Kips Bay vs Yorktown Heights; Bronxville vs Westfield; Chelsea vs Huntington.
   SF to Financial District: Russian Hill vs Livermore; Marina District vs Pleasanton; Mission District vs Novato; Nob Hill vs Walnut Creek.
   SF to Mountain View: Mountain View vs Pacifica; Palo Alto vs Novato.
   LA to Downtown: Little Tokyo vs Thousand Oaks; Koreatown vs Porter Ranch; Pasadena vs Palos Verdes Estates.
   Should be similar (within 10 min):
   NYC to Union Square: Flatiron vs Gramercy Park; Greenwich Village vs East Village.
   SF to Financial District: Noe Valley vs Bernal Heights; Pacific Heights vs Russian Hill.
   LA to Downtown: Los Feliz vs Silver Lake; Echo Park vs Silver Lake.
   Hub pair: for all places, Midtown East vs Midtown North (0.7 mi apart) median absolute transit difference at most 5 min.
   Pass: at least 80% of "differ" pairs and at least 80% of "similar" pairs, and the hub pair line.
3. Hub-snap error: median under 10 min for jobs within 5 miles (currently proxy 6 to 22 min by separation; NYC and SF within 4 miles pass, 4 to 8 mi fails).
4. R5 versus Google: 80% of pairs within 10 min and absolute bias under 3 min per hub (NYC passes: 89% within 10, per-hub bias at most 3.3, White Plains 3.3 narrowly fails the bias line); SF and LA need fresh Google transit calls. I am asking before any API call: it would need Google Distance Matrix transit calls for a sample of about 100 SF and 100 LA place-hub pairs.
5. Independent validation: brief written in docs/COMMUTE_TIME_VALIDATION_BRIEF.md (Metro-North towns to Grand Central vs published timetable; pass: median absolute difference at most 6 min, none over 15, 80% within 8). The 6 min median line replaces the earlier 5, changed before any result was read, to allow for the platform-to-pin walk. Not yet run.

Launch pair result (2026-11-05, stored times, criteria unchanged from above): PASS. "Differ" 13 of 13 (smallest gap 22 min, Marina District vs Pleasanton). "Similar" 5 of 6 (83%); the miss is Pacific Heights 32 min vs Russian Hill 12 min to Financial District, a 20 min gap (stored values, not investigated). Hub pair Midtown East vs Midtown North median absolute difference 5.0 min over 191 places, exactly at the limit. Bronxville and Westfield were not blind.

Independent timetable validation (2026-11-05, run by a separate session; timetable times written down before stored values were read): PASS. 34 Metro-North towns to Grand Central: median absolute difference 2 min (limit 6), largest 2 (limit 15), 100% within 8 (limit 80%). Stored is +2 min on 32 towns, Bronxville +1, Fairfield -1 (unexplained). Sources: MTA Hudson, Harlem and New Haven PDFs effective 2026-10-04 (Hudson revised 2026-10-15). Limits: times read by eye from PDFs by one reader with no second pass; the PDFs and the router likely share the same schedule source, so this tests routing and walk logic, not the schedule data; NYC Metro-North only.

Check 1 (all-places distribution): FAIL on the 0 side for SF Sunnyvale (24%), Cupertino (20%), San Jose (17%), North San Jose (16%), Mountain View (15%) and Jersey City (12%, NYC); stored times are genuine long trips, so this reflects geography, not a data error (not verified place by place).
Check 3 (hub snap error): FAIL for 4 to 8 mi separation (median 12 to 22 min).
Check 4 (R5 vs Google): NYC pass on agreement (89% within 10 min); White Plains bias +3.3 narrowly over the 3 min line; SF and LA not run (needs about 200 Google calls, not approved).

Proposed level: stays 0 for sign-off. Level 1 needs fix 3 and the removal or reasoned use of the area-type speed fallback (gap 5). Level 2 needs checks 1, 3 and 4 to pass or have their failures accepted in writing by you.

Results: other checks not yet run beyond what section 3 states. Proposed level: stays 0 until fix 3 is approved and shipped and checks 2 and 5 are run.

## 7. Open items for owner
1. Approve fix 3 (no route in chosen mode scores 0 and is labeled).
2. Decide gap 7 (happiness index commute term).
3. Approve the Google call for SF and LA R5 comparison (about 200 element calls), or skip it.
4. Citations still to verify from full text: Stutzer and Frey magnitude (the "+18 minutes, -0.09" figure in HAPPINESS_EVIDENCE_NOTES is UNVERIFIED by me; the PDF would not parse), Chatterjee 2020 mode ordering, van Ommeren and Fosgerau euro figure, Wardman multipliers, DOT 2016 guidance.

## Change log
2026-11-05: fix 3 implemented on branch commute-time-dpv2 (not pushed): a place routed to the hub but with no time in the user's chosen mode scores 0 (scaled by office days) and shows "No route to your work hub by your chosen mode", instead of dropping out. Also corrected: the explorer treated a stored no-route entry as "off zone". Curve unchanged. New pure module frontend/lib/commuteTime.ts, tests in tests/commute_time.test.mjs (7 pass), tsc clean. Card snap-distance note not done: the picker already shows it; place cards do not have the snapped distance available.

2026-11-05 (gap 5): the searched-address fallback no longer uses the area-type speed table. It is now minutes = 11 + 2.0 x straight-line miles (frontend/lib/commuteTime.ts), fitted on 2,696 stored Google drive times from NYC, SF and LA, area-type free. Split-half fits: a 11 b 2.0 and a 13 b 1.76. Held-out median error 8.2 to 8.6 min (p90 23) versus 11.6 (p90 32) for the old table. Plausible range a 11 to 13, b 1.76 to 2.0. Card shows "Rough estimate, about N min". Limits: three metros, peak Google times, drive only, few pairs beyond 60 miles; the 75 mile cutoff is still a round number. Tests: 8 pass, tsc clean. The shared estimatedDriveMinutes (social proximity, air travel) is unchanged and belongs to those specs.

## Owner acceptances
2026-11-05: owner accepted check 1 (places at 0 are real long trips) and the snap-error approach (show the snap distance and error band on the card, keep the 15 mile rule) as known limits, on condition that the work continues to Level 2. Level 2 is not yet reached: fix 3, the card disclosure, and check 4 for SF and LA are still open.

## Sign-off
Level: 2 (Verified). Date: 2026-11-05. Signed off by: Adam Wright (owner).
Level 1 met: spec sheet filled, reference frame declared (fixed standard, tier 1),
no scoring keys on the area-type label, no route in the chosen mode scores worst and is labeled.
Level 2 met: launch pairs passed (13 of 13, 5 of 6); independent timetable check passed
(34 Metro-North towns, median 2 min off); R5 vs Google passed for NYC only.
Exceptions accepted by the owner:
- 6 hubs have more than 15% of places at 0 (long real trips, not a data error).
- Hub-snap error is high for hubs 4 to 8 miles apart; the card shows the distance, the 15 mile rule stays.
- R5 vs Google not run for SF and LA (owner declined the Google calls).
Accepted TODOs (not Level 3): curve knots, office-days blend and 15 mile snap limit have no source.
Decided 2026-11-05 (owner): the general happiness index keeps its 5% commute term, using the place's area-average commute (a property of the place). Only the personal hub-based commute is excluded from the general score. Happiness index weights are reviewed in a separate session.
Limit: copy may not call commute "validated"; independent validation covered NYC Metro-North only.
