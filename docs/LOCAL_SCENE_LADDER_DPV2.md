# Local scene ladder: Level 1 spec sheet and Level 2 plan (written 2026-11-11, before any Level 2 result was run)

Status: built 2026-11-11 (variant B). The ladder is stored as score.local_scene_level (quiet, low_key, lively, buzzing; None = no data) in all 21 catalog files, replaces the 3-tier tag and the lively flag in the Explorer, and Aura is unchanged. Level 1 is not signed off. No "validated" claim is allowed. This replaces the 3-tier activity tag in `docs/LOCAL_SCENE_ACTIVITY_L2.md` once built (a change to a signed-off measure drops it back to Level 1, DPv2 adoption rule section 2). Written by the session that designed the ladder, so it must not grade it: the Level 2 checks in section 3 are to be run by a different session, against the pass criteria in this file, which are fixed by this commit.

Level names (owner decision 2026-11-11): level 0 Sleepy, level 1 Flat, level 2 Lively, level 3 Buzzing. Stored keys stay quiet, low_key, lively, buzzing. The checks refer to levels 0 to 3.

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
  floor | fewer than 15 named venues in the measured area is Quiet | consistent with the minimum above | 10 to 20 | not run
  independence rule | no OSM brand tag | OSM convention | misses untagged chains (6.2% of NYC venues carry a tag) | not run
Rule (variant B, recommended): fewer than 15 named venues in the measured area gives level 0 (Quiet). No density figure gives level 1.
  Otherwise a mix reading below 55 gives level 1 (mostly restaurants, few cafes, bars or culture venues). A mix reading of 55 or more
  gives level 2, or level 3 when the pin has 71 or more independent venues.
  Variant A (floor on the independent count at the pin) was tested and rejected: it reads 126 of 552 towns as Quiet at the pin even
  though each has 15 or more venues in the town (Cornelius 6 and 19, Dunwoody 8 and 58).
Shared inputs with other pillars: the seven types overlap the amenities pillar's types (acceptable, the ladder is not scored,
  principle 5). Aura reads the ladder.
Pin-shift sensitivity: not run (Level 2 a). Prior result for the mix on the pin circle: 95th percentile change 28 points (failed).
Independent validation: none yet (Level 2 d).
All-places check (2026-11-11, n 1,476, variant B): level 0 572, level 1 488, level 2 289, level 3 127. Variant A: 732, 384, 233, 127.
Fail-loud conditions: a place with no venue read must be None, not level 0. 73 places have no named venue in the measured area; the
  stored rule must give them None. OPEN: confirm the build does this before sign-off.
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
2. Whether Aura becomes "level 3 plus status class plus not a job center" (all 49 current Aura places are level 3 under this rule).
3. Whether the old lively flag is retired (the new level 2 is a different definition and would collide with the name).
4. Sign-off line for Level 1 once the None rule is confirmed.
