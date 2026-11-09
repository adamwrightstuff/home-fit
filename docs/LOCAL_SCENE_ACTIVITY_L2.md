# Local scene activity tag: Level 1 spec sheet and Level 2 plan (written 2026-11-08, before any Level 2 result was run)

Status: nothing here changes scoring. No "validated" claim is allowed. Written by a session that did not build the tag (DPv2 adoption rule, section 2), but that read the 2026-11-06 decision notes first, which matters for the launch pairs (section 4b).

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
Launch check pairs: section 4b.
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
3. Carroll Gardens over Pelham Bay's neighbor Pelham (Westchester)
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
