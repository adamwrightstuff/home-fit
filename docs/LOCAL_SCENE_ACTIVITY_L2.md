# Local scene activity tag: Level 1 spec sheet and Level 2 plan (written 2026-11-08, before any Level 2 result was run)

Status: nothing here changes scoring. No "validated" claim is allowed. Written by a session that did not build the tag (DPv2 adoption rule, section 2), but that read the 2026-11-06 decision notes first, which matters for the launch pairs (section 2b).

## 0. The Level 1 sign-off covers a different measure than the one that ships
Level 1 was signed on 2026-11-05 for two measures, the pin-circle culture-and-hangout mix and the town-boundary hybrid (docs/LOCAL_SCENE.md sections 10 and 16). On 2026-11-06 the visible tag became something else: a count of independent named venues within 1,200 m, cut into Quiet, Some and Vibrant. Aura became an and-rule on that count plus the mix reading plus status class plus a job-center exclusion. The signed measure no longer sets the tag; it survives only as one input to Aura. Under the DPv2 adoption rule a change to a signed-off scoring definition drops it back to Level 1 until re-specified and re-signed. So the activity tag and the Aura rule currently have no Level 1 sign-off at all. This sheet is that spec.

## 1. Level 1 spec sheet: the activity tag
```
Pillar: Local scene activity tag (not a pillar, not in any total)
Construct (one sentence): how many independent, named eating, drinking and culture venues sit within a short walk of the catalog pin. A count of activity, not quality, not coolness, not who lives there.
Reference frame: catalog-relative cuts (peer norm). Quiet and Vibrant are the catalog median and 85th percentile of the count on 2026-11-06, not a fixed standard and not the nation (the catalog is 1,476 selected places in 18 states).
  Evidence for the frame: none (tier 3 or better absent). The ingredient has tier 1 support only for a narrow population: walking-time restaurant and nightlife density explains young college graduates' location choices (Couture and Handbury, in DPv2 Part 4b). No study supports three tiers or these cuts.
Measurement area: pin + 1,200 m circle (a 15-minute walk).
  Reason: matches the amenities walk-time radius for dense places. A pin plus circle is a design choice (principle 3); consequence is pin sensitivity (Level 2 a) and towns whose main street is off the pin.
Place context inputs: none. No area-type label, no density. (The mix facts that Aura uses read activity per acre; the tag does not.)
Inputs and data sources (vintage): OpenStreetMap named venues of seven types (cafe, bar, restaurant, gallery, bookstore, records, theater) from the private Overpass server read of 2026-11-05, 1,476 places, 107,207 venues, 8,184 with a brand or brand:wikidata tag. A venue counts as independent when it has neither tag.
Parameters:
  name | value | source | plausible range | sensitivity result
  radius | 1,200 m | owner decision (amenities) | unknown | not run for the count
  Quiet below | 13 | catalog median 2026-11-06 | unknown | not run
  Vibrant from | 71 | catalog 85th percentile 2026-11-06 | unknown | not run
  venue types | seven, restaurants included | judgment | unknown | not run (restaurants are what make strips read busy)
  independence rule | no OSM brand tag | OSM convention | misses untagged chains | not run
Shared inputs with other pillars: the amenities pillar reads the same venue types (acceptable because the tag is not scored, principle 5). Aura reads the tag, the mix reading (local_scene_v2.combined), status class and LODES jobs per resident.
Pin-shift sensitivity: not run (Level 2 a).
Independent validation: none (Level 2 c, d).
All-places check: stated 2026-11-06 as about half Quiet and about 15% Vibrant; recomputed in section 5 of this file after the run.
Fail-loud conditions: a place with no venue read gets no tag (None), never Quiet. NOT flagged: a place whose OSM coverage is thin but nonzero reads Quiet (Rye, 7 venues). That is a believable wrong number (principle 9) and is gap A3 below.
Launch check pairs: section 2b, results in section 4.
Known data limits: OSM coverage and tagging vary by place (Rye, Hastings-on-Hudson, Pelham Manor, Irvington, Ardsley map too thin for any measure); long commercial strips count as much as compact centers (Sunnyside, Bay Ridge read Vibrant, Bronxville and Silver Lake read Some); straight-line distance, not walking network; no opening hours; pin may sit off the main street.
Last re-validated: never.
```

### Gap table
| # | Gap | Principle | Action |
|---|---|---|---|
| A1 | Reference frame is the catalog's own distribution; no evidence for peer-relative cuts | 1, 4 | State as unsourced; keep until Level 2 labels say whether three tiers match anyone's sense |
| A2 | All parameters unsourced (radius, both cuts, venue types) | 4 | Listed above with range "unknown"; cut sensitivity is a Level 2 TODO, not run |
| A3 | Sparse-OSM places read Quiet with no flag | 9, 11 | Accept as open or fix first; a fix changes scoring and needs your approval, none proposed here |
| A4 | Pin-based; sensitivity not yet measured for the count | 3, 6 | Level 2 a |
| A5 | No independent labels | 7 | Level 2 c |
| A6 | Strips read as busy as centers; owner's sense of busyness disagrees | 10 | Known limit, shown in launch pairs |
| A7 | Live scorer still uses the old scene formula; live and catalog differ | 12 | Out of scope, documented in docs/LIVE_SCORER_VS_EXPLORER.md |
| A8 | Raw venue reads are an untracked local file (data/local_scene_brand_reads.jsonl, in the status-signal worktree only) | 12 | Re-validation needs it; decide where it lives |

### Proposed Level 1 line (for your sign-off)
"Level 1 (Specified), for the local scene activity tag (independent named venues within 1,200 m; Quiet under 13, Some 13 to 70, Vibrant 71 or more) and for the Aura and-rule (Vibrant, mix reading 65 or more with 15 or more venues, Affluent or Elite class, not a job center), signed off by the owner on <date>, with gaps A1 to A8 accepted as open, A3 (unflagged sparse-map Quiet) accepted as an exception to principle 9, and every parameter recorded as an unsourced judgment. Level 2 not passed; 'validated' may not be claimed."

## 2. Level 2 plan, criteria fixed before any result (all limits are judgments, not research values, as in earlier sections of docs/LOCAL_SCENE.md)

Data: stored venue reads only (`local_scene_brand_reads.jsonl`, 1,476 places, each read within 1,500 m of the pin on 2026-11-05) and stored catalog fields. No API, no Overpass tunnel.

### 2a. Pin-shift of the activity tier and of Aura
Coverage problem, decided before running: a 1,200 m circle moved 500 m reaches 1,700 m from the original pin, beyond the stored 1,500 m reads. So the gated test uses a radius that stays inside the reads and the shipped radius is reported but not gated.
- Primary (gated), covered form: count independent venues within **1,000 m** of the pin and of each shifted pin (500 m north, south, east, west; venues counted are only those within 1,000 m of the shifted pin, all of which lie inside the 1,500 m reads). Cuts re-derived by the shipped rule on the baseline 1,000 m counts: Quiet below the catalog median, Vibrant at or above the 85th percentile (numpy linear percentile, rounded up to an integer). First check that the same rule applied to the baseline 1,200 m counts reproduces 13 and 71; if it does not, that is reported before anything else.
- Secondary (reported, not gated): the shipped 1,200 m radius with the shipped cuts 13 and 71, shifted circles truncated where they pass 1,500 m. Biased toward fewer venues on the far side; the direction of tier changes is reported.
- Gates, all required: (1) the tier is unchanged in at least 85% of all shifts; (2) among baseline-Vibrant places, at least 80% of shifts stay Vibrant; (3) no more than 1% of shifts jump two tiers (Quiet to Vibrant or back).
- Reported only: median and 95th percentile of the change in count (absolute and relative); tier stability by baseline tier (the overall number is flattered by the many Quiet places, as in section 11); places whose tier changes in at least 2 of 4 shifts; the 11 labeled places and Larchmont, Bronxville, Pelham, Rye.
- Aura, covered form: conditions recomputed at the shifted pin: Vibrant count (1,000 m, re-derived cut); for pin-circle places the mix reading recomputed from venues within 1,000 m with each shifted share ranked against the baseline distribution of its (geography, density band) group, combined at least 65 and at least 15 venues; for town-boundary places the mix is pin-independent and held as stored. Held at stored values because they cannot be recomputed offline: status class, jobs per resident, density band. Baseline Aura set in this form is reported with its overlap against the stored 49.
- Aura gates, both required: (1) among baseline-Aura places, Aura is kept in at least 80% of shifts; (2) no more than 10 places that are not baseline-Aura gain Aura in at least one shift (names reported).
- Not tested: whether a shifted pin crosses a town boundary (the boundary geometry is not stored here; about 6.5% of shifts crossed in the earlier test); tract and LODES changes at the shifted pin.

### 2b. Launch pairs (named from place names only, before any score was looked at)
Rule: the first place's stored tier (shipped `local_scene_bucket`, 1,200 m) must be strictly higher than the second's. Pass: at least 5 of 6. Counts and ratios reported per pair.
1. West Village over Pelham Bay (NYC)
2. Tribeca over Battery Park City
3. Carroll Gardens over Pelham (Westchester)
4. Bronxville over Pelham Manor
5. Silver Lake (Los Angeles) over Sunnyside (Queens)
6. Park Slope over Bay Ridge
Disclosure: I had read the 2026-11-06 note that Sunnyside and Bay Ridge read Vibrant, so pairs 5 and 6 are included on purpose because your sense is that they differ and the note says the tag does not separate them. Expect them to fail; with a 5-of-6 rule one more miss fails the set. Pairs 1 to 4 were chosen on lay knowledge of the places alone.

### 2c. Independent labels
- At least three raters who are neither the owner nor the builder, each answering Quiet, Some or Vibrant for at least 25 places they know, from the fixed list of 45 in `docs/LOCAL_SCENE_LABEL_SHEET.md` (all eleven required places, Silver Lake's neighbors Echo Park, Los Feliz and Atwater Village, the Aura checks you named, and filler across NYC, LA, Bay Area, Boston, Chicago, Philadelphia). The list was chosen from names and shuffled with a fixed seed; no count was looked at. 29 of 45 are New York area, so raters need to know that region (or accept answering fewer elsewhere); a sheet with fewer than 25 known places is reported and does not count toward the three.
- Per person, all three required (principle 7 sets Spearman 0.7 for perceptual pillars): (1) Spearman rank correlation between the person's answer (Quiet 0, Some 1, Vibrant 2) and the independent venue count within 1,200 m at least 0.70; (2) among pairs of that person's places with different answers, the count ranks at least 80% in the right order; (3) no more than 10% of that person's answered places are a two-tier miss (they say Quiet and the tag says Vibrant, or the reverse).
- Pass for 2c: all raters pass all three. A rater who fails is reported, never dropped. Also reported: agreement among raters (pairwise Spearman). If raters agree with each other below 0.70, their labels are not a standard to hold the tag to, and that is reported instead of a pass or fail.

### 2d. Aura against the same labels
Question F on the sheet (only for places marked Vibrant) asks whether the place is vibrant mainly because of independent cafes, bars, restaurants and culture spots.
- Gates, both required: (1) every Aura place on the list that at least two raters rated gets a majority rating of Vibrant, and at least 80% of them also get a majority "yes" on F; (2) no Aura place gets a majority Quiet or Some.
- Reported only: Aura recall (Aura is rare by design); for every place the majority calls Vibrant with "yes" that lacks Aura, which condition failed (count, mix, class, job center).
- Not tested by these labels: the status class and job-center conditions. Raters are not asked about wealth or demographics (your 2026-10-28 ruling).

### Proposed outcome mapping (fixed now)
All of 2a, 2b, 2c, 2d pass: propose Level 2 for sign-off. Any fails: the tag stays Level 1 with the failure recorded; I do not tune a cut to pass. Either way, "validated" is not claimed: the adoption doc (section 1) allows it only for independent validation passed on the full catalog, not a subset, and 45 places is a subset. Whether 45 labeled places counts is your call; my recommendation is no.

## 3. Label sheet
`docs/LOCAL_SCENE_LABEL_SHEET.md` and `docs/local_scene_label_sheet.csv`. Instructions are on the sheet. Nothing on it reveals a score.

## 4. Results of 2a and 2b (run 2026-11-08, offline, criteria as fixed above; `scripts/catalog/local_scene_activity_l2_check.py`)
Data checks first: all 1,476 places have a stored read; recomputing the independent count at 1,200 m from the reads matches the stored `independent_venues_1200m` for all 1,476 (0 mismatches); stored distances agree with coordinates to 0.5 m; the cut rule applied to the 1,200 m counts gives 13 and 71, as shipped. At 1,000 m the same rule gives Quiet below 10 and Vibrant from 58. Baseline tiers at 1,000 m: Quiet 716, Some 535, Vibrant 225.

**2a activity tier, covered form (1,000 m, 5,904 shifts): PASS on all three gates.** Tier unchanged in 89.1% of shifts (gate 85%); baseline-Vibrant places stay Vibrant in 86.2% of shifts (gate 80%); two-tier jumps 0.05% (gate 1%). By baseline tier: Quiet 94.0%, Some 83.7%, Vibrant 86.2% unchanged (the overall number is lifted by Quiet places). Median change in count 2, 95th percentile 40; median relative change 14%, 95th percentile 100%. 188 places change tier in 2 or more of 4 shifts. Secondary, shipped 1,200 m with cuts 13 and 71, truncated beyond the reads (not gated): 92.5% unchanged; of 445 changes, 307 went down and 138 up, the downward lean being the truncation. Named: Los Feliz 62 at the pin, 22 shifted north, 103 south (Vibrant to Some in two shifts); Silver Lake 46, one shift reaches Vibrant (59); Hastings-on-Hudson 10 (Some, stored Low at 1,200 m); Rye 7, Pelham 18 and Bronxville 34 do not move; Murray Hill, Hell's Kitchen, Battery Park City, Santa Monica, Sunnyside, Bay Ridge stay Vibrant in every shift though counts swing (Battery Park City 66 to 392).

**2a Aura, covered form: FAIL on both gates.** The baseline Aura set at 1,000 m has 50 places, 44 shared with the stored 49 (stored only: Downtown Denver, Arts District, Long Island City, West Village, Inner Sunset; covered form only: Ansley Park, Decatur, Society Hill, Kirkland, Alamo Square, Lower Haight). Retention 75.0% of shifts (gate 80%). Eighteen places that are not baseline Aura gain it in at least one shift (gate 10): Bouldin Creek, Clarksville, Somerville, Lincoln Square, The Loop, Houston Midtown, Gramercy Park, West Village, Lake Eola Heights, Bella Vista, Queen Village, Elmwood, Grand Lake, Jack London Square, Mission District, Noe Valley, Palo Alto, Rockridge. Least stable: Ansley Park, Berkeley, Fitler Square, Russian Hill, The Castro (1 of 4 shifts); Hayes Valley, Dogpatch, Greenwich Village, Windsor Terrace, Hyde Park (2 of 4). Stable at 4 of 4: SoHo, Park Slope, Prospect Heights, Cobble Hill, Carroll Gardens (Tribeca 3 of 4). Held at stored values, so not tested: status class, jobs per resident, density band.

**2b launch pairs: FAIL, 3 of 6 (rule 5 of 6).** Passed: West Village (818, Vibrant) over Pelham Bay (11, Quiet); Carroll Gardens (213, Vibrant) over Pelham (18, Some); Bronxville (34, Some) over Pelham Manor (8, Quiet). Failed (same tier): Tribeca (669) and Battery Park City (349), both Vibrant; Park Slope (361) and Bay Ridge (144), both Vibrant; Silver Lake (60, Some) below Sunnyside (156, Vibrant), the reverse of your sense. Pairs 5 and 6 were expected to fail (section 2b); pair 2 was not, and fails because Battery Park City's 1,200 m circle reaches Tribeca and the Financial District.

## 5. All-places check on stored tiers (2026-11-08, 1,476 places, no failures to read)
Quiet 732 (49.6%), Some 520 (35.2%), Vibrant 224 (15.2%). The cuts therefore behave as described on 2026-11-06. 144 places have zero independent venues in the 1,200 m read and are tagged Quiet (gap A3: no flag separates sparse mapping from an empty place). By metro Vibrant share is highest in Chicago (24 of 103), NYC (62 of 193), SF (35 of 113) and lowest in Houston, San Antonio, Orlando (2 each); small metros with few catalog places (Seattle has 5) say little.

## 6. Where the tag reads differently than your sense (stored counts, nothing changed)
Your judgments are "has it" or "does not", from docs/VIBE_VALIDATION.md, which is the earlier vibe construct, not busyness; where your sense of busyness differs, I have not guessed.
- Has it, tag below Vibrant: Larchmont 41 (Some), Bronxville 34 (Some), Silver Lake 60 (Some), Venice 65 (Some), Rye 7 (Quiet, pin off the downtown and thin OSM, known).
- Does not have it, tag Vibrant: Sunnyside 156, Murray Hill 628, Battery Park City 349, Bay Ridge 144, Forest Hills 109, Flushing 91.
- Does not have it, tag Some: Pelham 18, Brighton Beach 54. Quiet as you would expect: Pelham Bay 11, Yonkers 4.
- "Some of it", tag Vibrant: Astoria 92, Windsor Terrace 116, Upper East Side 395, Long Island City 156, Financial District 335, Clinton Hill 242, Beacon Hill 343.
- Has it and Vibrant, agrees: West Village 818, Tribeca 669, Chelsea 675, Hell's Kitchen 652, Boerum Hill 381, Greenpoint 363, Park Slope 361, Hayes Valley 340, Fort Greene 338, Williamsburg 323, Rittenhouse Square 273, Back Bay 251, Wicker Park 221, Carroll Gardens 213, Santa Monica 129, Cambridge 124, Fishtown 97.
Pattern: the tag follows count, so dense places read Vibrant regardless of feel (6 of your 10 "does not" places and all 7 "some of it" places), and small or thinly mapped places read low (5 of your 22 "has it" places). Whether that is a defect depends on whether the tag means busy or has-it; the labels in section 2c will say which one raters hear in "Vibrant".

## 7. Status
Done offline: 2a, 2b, all-places, section 6. Not run: 2c, 2d (need raters; sheet in docs/LOCAL_SCENE_LABEL_SHEET.md). Level 1 not yet signed. Nothing pushed.

## 8. Sign-off
Level 1 (Specified), signed off by the owner (Adam Wright), 2026-11-08, for the local scene activity tag (independent named venues within 1,200 m; Quiet under 13, Some 13 to 70, Vibrant 71 or more) and for the Aura and-rule (Vibrant, mix reading 65 or more with 15 or more venues, Affluent or Elite class, not a job center), with gaps A1 to A8 accepted as open, A3 (unflagged sparse-map Quiet) accepted as an exception to principle 9, and every parameter recorded as an unsourced judgment. Level 2 not passed (section 4: Aura pin-shift and launch pairs failed; labels not yet collected); "validated" may not be claimed.

## 9. Rater 1 (returned 2026-11-08; identity not stated, counts toward 2c only if neither the owner nor the builder)
Sheet: 45 places answered, 31 "well" or "a bit" known per row as marked (all 45 answered), 31 Vibrant, 13 Some, 1 Quiet. Scored against the stored independent count and tier at 1,200 m, criteria as fixed in section 2c.
- (1) Spearman between answer and count: 0.35, limit 0.70, FAIL (the rater used one Quiet, so ties limit the ceiling, but the criterion was fixed before this result and is not changed).
- (2) Pairs with different answers ranked correctly by count: 308 of 428 = 72.0%, limit 80%, FAIL.
- (3) Two-tier misses: 0 of 45, limit 10%, pass. Exact tier match 31 of 45.
Rater read higher than the tag: Echo Park 57, Silver Lake 60, Venice 65, Hermosa Beach 66, Manhattan Beach 33, Montclair 30 (all Vibrant by the rater, Some by the tag); Rye 7, Hastings-on-Hudson 11, Pelham Bay 11 (Some by the rater, Quiet by the tag). Rater read lower than the tag: Battery Park City 349, Kips Bay 575, Carnegie Hill 291, Sunnyside 156, Murray Hill 628 (Some by the rater, Vibrant by the tag).
2d, indicative only (needs at least two raters per place): 14 stored-Aura places are on the list; this rater called all 14 Vibrant, and 13 of 14 "yes" on F (SoHo "no").
Status: 2c and 2d are not complete. One rater of the required three; this one fails two of three criteria. Level 2 stays unpassed.

## 10. Rater 2 (returned 2026-11-08; identity not stated) and two-rater read
Rater 2 knew 36 of 45 places (9 marked "no"), answered 1 Quiet, 11 Some, 24 Vibrant. Section 2c criteria: (1) Spearman 0.338, limit 0.70, FAIL; (2) pairs ranked correctly 210 of 299 = 70.2%, limit 80%, FAIL; (3) two-tier misses 0 of 36, pass. Exact tier match 23 of 36. Rater higher than the tag: Echo Park 57, Silver Lake 60, Manhattan Beach 33, Hermosa Beach 66, Bronxville 34, Rye 7. Rater lower than the tag: Palo Alto 101, Culver City 121, Brooklyn Heights 234, Bay Ridge 144, Sunnyside 156, Battery Park City 349, Kips Bay 575.
Agreement between raters 1 and 2 on the 36 shared places: Spearman 0.641 (under the 0.70 fixed in section 2c), exact agreement 30 of 36. They split on Palo Alto, Culver City, Brooklyn Heights, Bay Ridge, Venice (rater 1 Vibrant, rater 2 Some) and Bronxville (rater 1 Some, rater 2 Vibrant).
2c as fixed: both raters fail criteria 1 and 2, so 2c cannot pass whatever a third rater says. By the agreement rule fixed in 2c the labels are also not a firm standard (0.641 under 0.70), so the honest reading is: the tag's ordering by count does not match either rater's sense, and the raters only partly agree with each other.
2d with two raters (a place counts as majority only when both agree; a split is no majority): 12 stored-Aura places were rated by both. Both said Vibrant for 10; Culver City and Brooklyn Heights split (rater 1 Vibrant, rater 2 Some), so criterion (1) first clause FAILS. No Aura place got a majority Quiet or Some, so criterion (2) passes. On F, both said "yes" for 8 of the 10 (Tribeca split, SoHo both "no"), 80%. Indicative only until a third rater, and 2d as fixed needs criterion (1) to hold.
Status: 2a Aura and 2b failed; 2c failed for both raters returned; 2d failed on the split places. Level 2 not passed. A third rater would not change the 2c outcome; it would only sharpen the agreement number and 2d.

## 11. Correction on who rated (2026-11-08)
The owner states that the two returned sheets were filled out by the owner and by one other person (Muse). Section 2c requires raters other than the owner and the builder, so the owner's sheet does not count; one counting rater remains. It is not recorded which sheet was whose, but both fail criteria 1 and 2 (Spearman 0.35 and 0.34 against 0.70; pairs 72.0% and 70.2% against 80%), so 2c fails for the counting rater whichever sheet it is. The rater-agreement number (0.641) and the two-rater Aura read in section 10 are void as evidence: they mixed the owner's sheet with an independent one, and 2d cannot be run with one counting rater (it needs two). Status: 2c failed on one independent rater; two independent raters (not the owner, not the builder) are still missing for 2c as specified; 2d not run. Level 2 not passed.

## 12. Sheet 3 (returned 2026-11-08; filler not stated, assumed independent of the owner and builder; confirm)
Sheet 3: all 45 known "well"; 3 Quiet, 10 Some, 32 Vibrant. Section 2c: (1) Spearman 0.412, limit 0.70, FAIL; (2) pairs ranked correctly 335 of 446 = 75.1%, limit 80%, FAIL; (3) two-tier misses 2 of 45 = 4.4%, limit 10%, pass (Battery Park City 349 and Carnegie Hill 291, rater Quiet, tag Vibrant). Exact tier match 31 of 45. Rater higher than the tag: Echo Park 57, Silver Lake 60, Atwater Village 36, Venice 65, Montclair 30, Hermosa Beach 66 (Vibrant, tag Some); Rye 7, Pelham Bay 11, Hastings-on-Hudson 11 (Some, tag Quiet). Rater lower than the tag: Battery Park City, Carnegie Hill, Fitler Square 171, Brooklyn Heights 234, Sunnyside 156.
Which of sheets 1 and 2 was the owner's is not recorded, so both independent pairings are shown. Agreement with sheet 3: sheet 1 Spearman 0.701 (45 places, exact 37), sheet 2 0.524 (36 places, exact 27). Sheets 1 and 2 agree at 0.641.
2d, strict rule (a place has a majority only when both independent raters agree), 14 Aura places on the list:
- If the other independent rater is sheet 1: 12 of 14 both Vibrant (Fitler Square and Brooklyn Heights split, rater 3 Some); both "yes" on F for 9 of 12 (not: Culver City, Tribeca, SoHo).
- If it is sheet 2: 9 of 12 rated by both are both Vibrant (Culver City, Fitler Square split; Brooklyn Heights Some by both, a majority Some); both "yes" on F for 7 of 9.
Either way 2d criterion (1) FAILS (not every Aura place is a Vibrant majority; in the sheet 2 case Brooklyn Heights is a majority Some, so criterion (2) also fails).
Status: every independent sheet returned so far fails 2c criteria 1 and 2; with sheet 3 there are two independent raters if the owner's sheet is excluded, so 2d is now testable and fails. Level 2 not passed. No cut or rule was changed.
