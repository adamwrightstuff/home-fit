# Local scene ladder: Level 1 spec sheet and Level 2 plan (written 2026-11-11, before any Level 2 result was run)

Status: built 2026-11-11 (variant B). The ladder is stored as score.local_scene_level (quiet, low_key, lively, buzzing; None = no data) in all 21 catalog files, replaces the 3-tier tag and the lively flag in the Explorer, Aura is rebuilt on it (Buzzing, Affluent or Elite, not a job center: 62 places, was 49; all 49 kept) and the twin finder reads the mix reading. Level 1 is not signed off. No "validated" claim is allowed. This replaces the 3-tier activity tag in `docs/LOCAL_SCENE_ACTIVITY_L2.md` once built (a change to a signed-off measure drops it back to Level 1, DPv2 adoption rule section 2). Written by the session that designed the ladder, so it must not grade it: the Level 2 checks in section 3 are to be run by a different session, against the pass criteria in this file, which are fixed by this commit.

Level names (owner decision 2026-11-11): level 0 Sleepy, level 1 Flat, level 2 Lively, level 3 Buzzing. Stored keys stay quiet, low_key, lively, buzzing. The checks refer to levels 0 to 3.
UPDATE 2026-11-13 (owner decision): level 0 is defined only by having fewer than 15 mapped venues, so it is thin data and not a finding. The Explorer now shows it as "Limited data" and does not offer it as a filter choice; "Sleepy" is retired as a display word. The stored key stays quiet and no catalog file changes. A place with enough mapped venues and a weak mix reads Flat.

## 1. Level 1 spec sheet

```
Pillar: Local scene ladder (not a pillar, not in any total)
Construct (one sentence): how much independent activity sits near a place, and whether it is places to linger (cafes, bars,
  galleries, bookstores, record stores, theaters) rather than mostly restaurants. A description of character, not quality, not
  coolness, not who lives there. It does not count errands (grocery, salon, fitness).
Reference frame: peer norm for character (each place's culture share and hangout share ranked among places of similar density,
  towns ranked only against towns); catalog-relative cut for volume (median and 85th percentile of the venue count).
  Evidence for the frame: tier 3 only, one person's labels (the owner, 47 places, docs/VIBE_VALIDATION.md). The ingredient (walking-time
  restaurant and nightlife density) has tier 1 support only for young college graduates' location choices (Couture and Handbury,
  DPv2 Part 4b). No study supports four levels, these cuts, or ranking against similar-density peers.
Measurement area: towns with a Census place or county subdivision boundary inside a 6 km search circle use every named venue inside
  the boundary; everything else uses the pin plus a 1,200 or 1,500 m circle. Reason: a town's main street is often off the catalog
  pin (Rye, Scarsdale); neighborhoods have no boundary to use. Principle 3 judgment, owner decision 2026-11-05.
Place context inputs: activity per acre (people plus jobs per gross acre) for the five density bands. No area-type label is a scoring
  input; "town versus pin circle" is a measurement geography, not an area type.
Inputs and data sources (vintage): OpenStreetMap named venues of seven types (cafe, bar, restaurant, gallery, bookstore, records,
  theater) from the private Overpass server read of 2026-11-05 (1,476 places; brand and brand:wikidata tags kept) and a fresh NYC
  re-read of 2026-11-11 (193 places). Independent means neither tag.
Parameters (all unsourced, so all are TODOs under principle 4):
  name | value | source | plausible range | sensitivity result
  venue types | seven, restaurants included | inherited from the amenities list | unknown | not run
  minimum venues for a character reading | 15 | carried over from the old formula | unknown | not run
  density bands | 5 equal bands | judgment | 3 to 8 | not run
  character cut (Lively and above) | mix reading at least 55 | chosen 2026-11-11 on the owner's labels (in-sample); must exceed Pelham 53.1 | 45 to 65 | label pairs 0.82 at 45, 0.79 at 55 to 60, 0.75 at 65
  top-volume cut (level 3) | 71 independent venues at the pin | catalog 85th percentile 2026-11-06 | unknown | not run
  large-place mix cut (level 2 for large places) | mix reading at least 50 | 50 is the median place for its density band (the mix is a percentile); checked on the owner's labels 2026-11-12 (in-sample): cuts of 40 to 52.5 give 20 to 22 of 25 has-it and 13 or 14 of 14 does-not; 50 keeps all 14 | 40 to 52.5 | pin-shift section 6
  floor | fewer than 15 named venues in the measured area is Quiet | consistent with the minimum above | 10 to 20 | not run
  independence rule | no OSM brand tag | OSM convention | misses untagged chains (6.2% of NYC venues carry a tag) | not run
Rule (variant B, recommended): fewer than 15 named venues in the measured area gives level 0 (Quiet). No density figure gives level 1.
  Otherwise: a mix reading of 55 or more gives level 2, or level 3 when the pin has 71 or more independent venues. A LARGE place (71 or more
  independent venues) with a mix of 50 or more but under 55 is also level 2 (added 2026-11-12, see section 6). Anything else is level 1
  (mostly restaurants, few cafes, bars or culture venues compared with similar places).
  Variant A (floor on the independent count at the pin) was tested and rejected: it reads 126 of 552 towns as Quiet at the pin even
  though each has 15 or more venues in the town (Cornelius 6 and 19, Dunwoody 8 and 58).
Shared inputs with other pillars: the seven types overlap the amenities pillar's types (acceptable, the ladder is not scored,
  principle 5). Aura reads the ladder.
Pin-shift sensitivity: not run (Level 2 a). Prior result for the mix on the pin circle: 95th percentile change 28 points (failed).
Independent validation: none yet (Level 2 d).
All-places check (2026-11-12, n 1,476, with the large-place level 2): level 0 502, level 1 474, level 2 304, level 3 127, no level 69.
  (2026-11-11, before the large-place tier: 502, 489, 289, 127, 69.)
Fail-loud conditions: a place with no venue read must be None, not level 0. Built and confirmed 2026-11-11: 69 places have no named venue in
  the measured area and show no level. 4 towns whose boundary held none but whose pin circle did (Golden Beach FL, Terrell Hills TX, Belvedere CA,
  Hillsborough CA) are measured at the pin circle instead (2026-11-12; flagged measured_by_fallback; from the stored business list, so culture
  venues are not filtered to independent ones until a full rebuild from the brand reads): three read level 0, Hillsborough level 1.
Launch check pairs: section 3 (b).
Known data limits: OSM coverage (Rye 8 venues, Hastings-on-Hudson 11); seven types miss independent clothing, music venues and clubs
  (Silver Lake, Venice, Hell's Kitchen read low); restaurants-heavy dense places read level 1 whatever their feel (Upper West Side);
  mix is a rank so it moves when the pin moves; brand tags miss untagged chains.
Last re-validated: never.
```

Level 1 requirements check (adoption draft section 1): spec sheet filled (yes), reference frame declared with tier (yes, tier 3), shared facts from place context (density yes), no scoring on the area-type label (yes), failed data left out or flagged (open item above). Level 1 is claimable once the None rule is confirmed in the build and the owner signs.

## 2. Accepted gaps (for the sign-off line)

1. Frame has no study behind it (tier 3, one judge).
2. Every parameter is unsourced; the 55 cut was chosen on the same labels it is checked against.
3. Restaurants are counted as venues but not as hangouts, so restaurant-dense places read level 1.
4. Seven venue types miss clubs, music venues and independent shops.
5. Towns use the boundary, neighborhoods use the pin circle; the two are ranked separately and are not comparable across kinds.
6. The mix moves with the pin (prior failed check).

## 3. Level 2 plan: criteria fixed before any result

Run by a session that did not design the ladder. Offline from stored data first; the private Overpass server only if a check needs fresh reads, and only when the owner asks.

(a) Pin-shift. Shift each pin 500 m north, south, east and west and recompute the level from the stored 1,500 m reads. Pass: level unchanged in at least 85% of all shifts; places at level 2 or 3 stay at level 2 or 3 in at least 80% of shifts; two-level jumps in at most 1% of shifts. Reported: by baseline level, and Larchmont, Bronxville, Pelham, Rye. Expected to fail on the second criterion (the mix lost 24% of lively places in the earlier check); a failure is recorded, and the cut is not tuned to pass.

(b) Launch pairs, named before scoring, first place strictly higher: Larchmont over Pelham; Carroll Gardens over Sunnyside; Tribeca over Murray Hill; Park Slope over Bay Ridge; Bronxville over Pelham Manor; Fort Greene over Flushing. Pass: at least 5 of 6. Pairs 2 to 6 use owner labels the cut was tuned on, so they are in-sample and reported as such.

(c) All-places check. Report spread by geography (town, pin circle) and density band, and clumping. Pass: no level except level 0 holds more than 45% of places, and no density band has more than 80% of its places in one level. Report the places that move between variant A and variant B.

(d) Independent validation against labels the design did not use. Source: the raters in `docs/LOCAL_SCENE_ACTIVITY_L2.md` section 9 (rater 1 returned 2026-11-08, not used in tuning) plus at least two more raters who are neither the owner nor a builder, each answering from the 45-place list in `docs/LOCAL_SCENE_LABEL_SHEET.md`, using the final four level names. Pass per person: Spearman at least 0.70 between answer and level; at least 80% of that person's differing pairs ranked correctly; at most 10% two-level misses. If raters agree with each other below 0.70, their labels are not a standard and that is reported instead.

(e) Owner labels (47 places) are reported only: has-it places at level 2 or 3, does-not places at level 0 or 1, current result 19 of 25 and 14 of 14. They do not count toward pass because the cut was chosen on them.

Level 2 is passed only if (a) to (d) all pass. If any fails, the failure is recorded and the as-built version stays labeled "not validated".

## 4. What still needs the owner

1. Final level names.
2. DONE 2026-11-11: Aura is level 3 plus status class plus not a job center (62 places; 13 gained: Alamo Square, Ansley Park, Bella Vista, Bernal Heights, Lincoln Square, Lower Haight, Marina District, Mission District, Noe Valley, Palo Alto, Society Hill, The Loop, Wrigleyville).
3. Whether the old lively flag is retired (the new level 2 is a different definition and would collide with the name).
4. Sign-off line for Level 1 once the None rule is confirmed.


---

## 5. Level 2 run, 2026-11-12 (criteria as fixed in section 3; not changed)

**Independence.** Run by the session that built the ladder, so it is indicative and cannot certify; the checks should be repeated by another session. Everything is offline from stored data and the NYC brand reads; no live call.

| Check | Result | Verdict |
|---|---|---|
| (a) Pin-shift | See below | FAIL (one of three gates) |
| (b) Launch pairs | 6 of 6 (Larchmont over Pelham; Carroll Gardens over Sunnyside; Tribeca over Murray Hill; Park Slope over Bay Ridge; Bronxville over Pelham Manor; Fort Greene over Flushing). Pairs 2 to 6 use owner labels the cut was tuned on. | PASS (needs 5) |
| (c) All-places | Sleepy 34%, Flat 33%, Lively 20%, Buzzing 9%, no label 5% (n 1,476). No level above Sleepy holds more than 45%. No density band has more than 80% in one level (sparsest band is 73% Sleepy). | PASS |
| (d) Independent raters | Not run. The two raters from 2026-11-08 answered with the three old words and their per-place answers are not in the repo; the criteria need at least three raters answering with the final four names. | NOT RUN |
| (e) Owner labels, reported only | Has-it at Lively or Buzzing 19 of 25; does-not at Sleepy or Flat 14 of 14; pairs 271 of 350 = 0.77. Misses: Rye, Silver Lake, Venice, Rittenhouse Square, Hell's Kitchen, Upper West Side. | reported |

**(a) Pin-shift detail.** Only the NYC places have brand reads, so this covers the 121 NYC pin-circle places (the 72 NYC town-boundary places are skipped: their measure does not move with the pin). Each pin shifted 500 m north, south, east and west; venues counted within 1,000 m of the shifted pin from the stored 1,500 m reads; the top-volume cut scaled by area to 49 (71 at 1,200 m); each place ranked against every stored pin-circle place in its density band (the production pool). That baseline equals the shipped level for 109 of the 121 places. 452 shifts:
- Level unchanged in 86.5% of shifts (needs 85%): pass.
- Lively or Buzzing places stay Lively or Buzzing in 91.1% of 124 shifts (needs 80%): pass.
- Two-level jumps in 5.97% of shifts (needs 1% or less): FAIL. 27 jumps: Flat to or from Buzzing 22, Sleepy to or from Lively 5.
- By baseline level, unchanged: Sleepy 94%, Buzzing 91%, Flat 85%, Lively 56% (of 16 shifts). 18 places change level in at least 2 of 4 shifts (for example Battery Park City, Greenwich Village, Long Island City, Red Hook, West Village).

Why the jumps. In a dense place the mix reading is the only thing separating Flat from Buzzing, so a place near the 55 cut flips two levels at once, skipping Lively (Lively exists only for places under 71 venues). That is built into the shape of the ladder, not noise: any dense place sitting near the cut will fail a one-level-at-a-time criterion. An earlier run that ranked places only against the other NYC places gave a different baseline for Tribeca and West Village than production; the production pool is the fair one and is what is reported above.

Limits of this run: NYC only (121 places), a 1,000 m radius instead of the shipped 1,200 or 1,500 m, an area-scaled volume cut, shifts of 500 m only. A complete check needs the brand reads for all 1,476 places (about 75 minutes on the private server).

**Level 2 is not passed** (section 3: all of (a) to (d) are required; (a) fails a gate and (d) was not run). The ladder stays "not validated".

**Level 1.** The one open item from section 1 is closed: places with no named venue show no level (69 places), and four towns whose boundary held none are measured at the pin circle. Level 1 is ready for the owner's sign-off line with the gaps in section 2 accepted.

**Options for the jump failure (not decided, criteria not changed).** (1) Leave as built and record the failure. (2) Accept Flat and Buzzing as adjacent for dense places and rewrite the criterion before the next run (a change made after seeing this result, so it would be labeled as such). (3) Add a Lively tier for large places, so the ladder moves one level at a time.


---

## 6. Large-place Lively tier, 2026-11-12 (owner decision after the section 5 failure)

**Change.** A place with 71 or more independent venues and a mix reading of 50 or more but under 55 is now Lively (it was Flat). Everything else is as before, so Buzzing and Aura do not change (127 Buzzing, 58 Aura). The goal: a dense place whose mix wobbles around the cut moves one level at a time (Flat to Lively to Buzzing) instead of jumping from Flat to Buzzing. 50 is the median place for its density band; the owner's labels were used to check it (in-sample, so a judgment, not a finding): of cuts from 40 to 52.5, 50 is the lowest that keeps all 14 "does not" places at Sleepy or Flat (45 and below pull Battery Park City up to Lively).

**Effect on the catalog.** Flat 489 to 474, Lively 289 to 304 (15 large places moved up: South End, Andersonville, South Loop, Hollywood, Downtown Las Vegas, Rittenhouse Square, Cow Hollow, Redwood City and others).

**Effect on the owner labels (reported only).** Has-it at Lively or Buzzing 19 to 20 of 25 (Rittenhouse Square now reads Lively); does-not at Sleepy or Flat still 14 of 14; pairs 0.77 to 0.81.

**Level 2 re-run with the new rule (same method as section 5, so the criteria are unchanged; the rule changed after seeing the result, so this is not a clean pre-registered pass).**

| Gate | Section 5 (before) | After | Needs |
|---|---|---|---|
| Level unchanged under a 500 m shift | 86.5% | 84.1% | 85% |
| Lively or Buzzing stay Lively or Buzzing | 91.1% | 87.5% | 80% |
| Two-level jumps | 5.97% (27) | 3.54% (16) | 1% or less |

Launch pairs still 6 of 6; no density band has more than 80% in one level. Jumps now: Flat to or from Buzzing 11, Sleepy to or from Lively 5. By baseline level, unchanged: Sleepy 94%, Buzzing 91%, Flat 87%, Lively 31% (of 36 shifts).

**Reading.** The new tier cuts the two-level jumps by more than a third but does not reach 1%, and it makes things slightly worse on the other gate: a narrow Lively band for large places (mix 50 to 55) is crossed easily, so Lively is the least stable level. The remaining Flat to Buzzing jumps are shifts where the mix moves by 5 or more points at once (a shifted circle picks up a different block), which no tier boundary can absorb. The mix reading itself, a rank within a band, is what moves under a shift. Level 2 is still not passed.

**Options now (not decided).** (1) Accept this and record that the one-level criterion is likely unreachable for a rank-based mix at a 500 m shift. (2) Rewrite the jump criterion before the next run (a post-hoc change, to be labeled). (3) Make the mix steadier before ranking it (pool venues across the shifted circles, or shrink small samples toward the band average); both were tried on the old pin-circle measure and failed (docs/VIBE_VALIDATION.md sections 12 and 13), so this is the least promising.
