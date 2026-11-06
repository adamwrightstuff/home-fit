# Social proximity (personal priority): DPv2 spec sheet and audit

Level: 0 (audit only, 2026-11-05, no scoring change made). Proposed after an approved fix: Level 1.
Scope: a personal, client-side priority (closeness to the user's own family and friends). Not a pillar, not in the general happiness index. Frontend id: `social_connection`; map label "Social proximity"; weight panel label "Closeness to people you know".

Verification key: VERIFIED = I read the source text or abstract in this session (a fetch summary counts as an abstract read, not a full-text read). SUMMARY = seen only in a search snippet or press release. UNVERIFIED = not seen.

## 1. Spec sheet

```
Pillar: Social proximity (personal priority, key social_connection)
Construct (one sentence): Exposure to the user's own people, how far (as estimated drive minutes) a place is
  from each person the user entered, combined across people.
Reference frame: fixed standard (distance to a specific person is the same cost for every place)
  Evidence for the frame (tier 1 published study | tier 2 revealed-preference proxy | tier 3 survey):
  Tier 1, narrow. Distance matters most at short range: hours of help to disabled older parents fall steeply
  out to about 2-5 miles and then are flat (Schoeni, Cho and Choi 2022, VERIFIED abstract-level read); losing
  a relative within 1 km, or a non-relative within about 5 km, raises loneliness in older Europeans (Sun and
  Schafer 2023, VERIFIED abstract-level read). Both are older-adult samples. Moves of 50+ miles go with less
  in-person contact with family and friends (Cho and Smith 2019, conference abstract, VERIFIED abstract only).
  Relationship quality matters more than distance (Shen, Chen and Ruan 2021, from the earlier check). No tier 2
  (price or migration) source was searched in depth; Choi et al. 2020 (SUMMARY) says 74.8% of PSID adults
  have a parent or adult child within 30 miles, which is a distance distribution, not a valuation.
  No evidence supports a personal-priority frame for adults who are not older or not in need of care.
Measurement area: other. Origin = each person's geocoded address; destination = catalog place centroid (or
  searched-address pin). Straight line x 1.3 road circuity, then an area-type speed to get minutes.
  Reason: none recorded for the 1.3 or for converting to minutes. The studies above are in miles and km, so
  minutes add an unsourced step.
Place context inputs used and remaining area-type uses:
  Reads the place's area_type label (not the place context) to pick a drive speed:
  urban_core 33, urban 38, urban_residential 40, dense_suburban 45, suburban 52, exurban 65, rural 72 km/h,
  default 50. This is a scoring input keyed on the label (principle 14 gap, no stated reason). The speed table is
  reused from the air-travel dealbreaker and has no source for this use.
Inputs and data sources (with vintage):
  Person address and tier (close | acquaintance), user entered, geocoded through /api/geocode, stored in the
  browser (localStorage key homefit_people_you_know). Place coordinates and area_type from the catalog row.
  No API call beyond geocoding.
Parameters: name | value | source | plausible range | sensitivity result
  close curve plateau | 100 through 15 min (about 6 mi suburban) | Healy and Dunifon 2025 as read in code comment; 208 hrs figure UNVERIFIED | unknown | not run
  close knot 40 min | 72 | same, 186 hrs/yr is ~89% of 208 (but 72 is not 89) | unknown | not run
  close knot 120 min | 65 | Cho and Smith, "no difference under 50 mi" (the abstract I read does not report that contrast) | unknown | not run
  close floor | 40, reached at 240 min | none | unknown | not run
  close interpolation between knots | linear | none | n/a | n/a
  acquaintance curve | 100 to 18 min, 55 at 30, 10 at 60, 0 at 75 | "convenient driving distance" mean 17.9 min, SD 10.8 (study not named in code, UNVERIFIED) | unknown | not run
  drive speeds by area type | see above | reused, unsourced here | unknown | not run
  road circuity | 1.3 | none | 1.2 to 1.5 typical, unsourced | not run
  combine rule | best person + 5 per extra person at or above threshold, max 2 extras | none (code says "round placeholder") | unknown | not run
  bonus threshold | close 70, acquaintance 60 | derived from the curves above | unknown | not run
  priority weight | Low 1, Medium 2, High 3 tokens, same scale as every pillar | design | n/a | see section 2, gap 5
Shared inputs with other pillars: none by data. Overlap in meaning with social fabric (see "How it combines").
Pin-shift sensitivity: not run. Person address is exact; place pin shift of 0.5 mi moves minutes by at most
  about 1.2 min suburban (0.5 x 2.4), so only the 5 to 15 minute knot region is sensitive.
Independent validation source and result: none exists for the curve (no dataset gives wellbeing by distance to
  one's own people for a US general population). A check of curve behavior against a distance-hours
  study is proposed in section 5.
All-places check: not run. No catalog data is stored for this priority.
Fail-loud conditions: a person with a failed geocode is rejected with an error and not stored. A place with
  non-numeric lat/lon gets no social proximity pillar (drops out, weight renormalizes). A missing area_type
  silently falls back to 50 km/h (principle 16 gap: a neutral number replaces a missing fact).
Launch check pairs: not defined (see section 5).
Known data limits: straight line distance, not routed; the user's own address choices are untested for
  entry errors; family and friends are not told apart (tiers are close vs acquaintance).
Last re-validated: never.
```

### What the user enters
A list of people. For each: a name (optional), an address (geocoded), and a tier: Close ("family or a close friend") or Acquaintance ("someone you know, casually"). There is no separate family versus friends field. Then a priority level (None, Low, Medium, High) in the weight panel, default None. Entry is on the profile page and the catalog people picker.

### How distance becomes a score
For each person: straight-line miles x 1.3 circuity, divided by an area-type speed taken from the place's label, gives minutes. Minutes go through the tier's curve (0 to 100). The place's social proximity score is the best person's score plus 5 points for each other person at or above the tier threshold (maximum 2 extras), capped at 100.

### The curve and its shape
Measured offline from the code (suburban speed shown; the label changes it, see gap 1):

| Miles to a close person | Suburban minutes | Close-tie score |
|---|---|---|
| 5 | 12 | 100 |
| 10 | 24 | 90 |
| 25 | 60 | 70 |
| 50 | 121 | 65 |
| 100 | 241 | 40 (floor) |
| 3,000 | far past 240 | 40 (floor) |

Shape: flat plateau to about 6 miles, a 28 point drop over the next 11 miles, a near-flat tail to about 50 miles, then a slide to a floor of 40. The evidence read above has steep fall-off inside 2 to 5 miles and a flat tail beyond, which is a different shape: the code is steepest at 6 to 17 miles and gives a person 3,000 miles away the same 40 points as one 100 miles away.

Same person, same distance, different place label (close tie):

| Miles | urban_core | suburban | rural |
|---|---|---|---|
| 10 | 74 | 90 | 97 |
| 25 | 67 | 70 | 72 |
| 50 | 50 | 65 | 68 |

### How family and friends are weighted
They are not distinguished. Close covers family and close friends on one curve. Acquaintance uses a steeper curve that reaches 0 at 75 minutes. Evidence that kin and non-kin differ (kin within 1 km, non-kin within 5 km in Sun and Schafer) is about losing a tie, not about where to live, and does not justify two separate curves.

### How it combines with the other priorities and with social fabric
Social proximity is injected as a synthetic pillar and weighted by the same Low 1, Medium 2, High 3 tokens as every pillar. Its share of the headline is its tokens divided by all tokens. With only social fabric and social proximity set to Medium, the split is exactly 50/50; set one to High and it is 60/40. No study supports any split between them (the October 2026 check, section 2c of HAPPINESS_EVIDENCE_NOTES.md). The two measure different things: social fabric is a place trait (stability, civic groups, gathering places), social proximity is the user's own network. They share no inputs. Social proximity is not in the general happiness index (frontend/lib/pillars.ts weights contain no `social_connection`), so it moves only the personalized total.

## 2. Gap table

| # | Gap | Recommended fix | Expected score impact |
|---|---|---|---|
| 1 | Minutes use the place's area-type label as a speed input (principle 14); the same distance scores 74 in an urban core and 97 in a rural place at 10 miles | Score on miles directly (studies are in miles and km); drop the speed table, circuity and minutes step | Large at 10 to 50 miles. Urban places gain up to about 20 points at 10 miles, rural places lose up to about 30. Places within 5 miles unchanged |
| 2 | Curve shape does not match the evidence: steepest at 6 to 17 miles; evidence is steepest inside 2 to 5 miles then flat | Re-anchor knots to Schoeni, Cho and Choi 2022 (see option B) | Moderate: 5 to 10 mile places fall about 30 points, mid-distance places fall a few points |
| 3 | Floor 40 with no distance dependence beyond 240 min; a person in another country scores the same as 100 miles away | Floor from the data (about 50% of the near value, range 20 to 80, VERIFIED ratio from adjusted hours 0.58 vs 1.16), flat beyond 100 miles | Places 100+ miles from a person move from 40 to about 50 |
| 4 | The 208 and 186 hours figures: 186 is VERIFIED (Cornell release, grandparents gave 186 hours at 1 to 5 miles, an average); 208 is UNVERIFIED in the paper and a secondary source says 128 hours returned | Remove 208 and the "89% retained" construction from comments and docs | None to score; copy only |
| 5 | Share of headline is set by token count, so equal Medium with social fabric is 50/50 with no source | Keep the user's level but state in the card that the weight is the user's choice; do not default it above None; no change to the token rule | None to scores; transparency only |
| 6 | Combine rule (bonus 5, cap 2, thresholds 70 and 60) and acquaintance curve unsourced | List as TODO with range "unknown"; run a perturbation (section 5) | None |
| 7 | Missing area_type silently becomes 50 km/h (principle 16) | Resolved by gap 1 (no label used) | None after gap 1 |
| 8 | UI copy says "a rough estimate", and the evidence is older adults only | Add one line: "Based on studies of older adults and caregiving; your own preference, not a research-backed score" | None; copy only |
| 9 | Family and friends not distinguished | No change; say so in the picker help text | None |
| 10 | No tests exist for the curve or combine rule | Add a node test file like tests/commute_time.test.mjs | None |

## 3. Options and recommendation

- A. Keep the curve, fix copy only (gaps 4, 8, 9). Cheapest, but the 74 vs 97 label effect and the unsourced shape stay.
- B. Flatten and re-anchor to the one study that matches the construct. Score in miles. Close curve: 100 through 5 miles, 68 at 7.5 miles (5 to 10 mile adjusted-hours ratio 0.79 / 1.16), linear to 50 at 100 miles, flat beyond. Every knot except the 100% anchor and the ratios is TODO: the 10 to 30 and 30 to 100 mile bands were not retrieved. Acquaintance curve scaled the same way with its own TODO. Disclose as "shape from help-to-older-parents data, not wellbeing."
- C. Mark it a pure user preference with no claimed evidence: a simple, transparent decay (for example 100 at 0 to 5 miles, 0 at 100 miles, linear), no research language anywhere.

Recommendation: B, with the copy from A and the disclosure line in gap 8. The evidence is real but narrow, so B uses it where it exists (steep inside 5 miles, small tail) and says plainly it is a preference everywhere else. C is the fallback if you do not want to lean on a single care-hours study. Nothing here changes scoring until you approve.

## 4. Change (not started, waiting for approval)
Files: `frontend/lib/reweight.ts` (curves, remove speed use for this priority), `frontend/lib/personalOverlay.ts` and `frontend/app/catalog/catalog-page-client.tsx` (pass miles), copy in `ScoreDisplay.tsx`, `NeighborhoodPersonal.tsx`, `PeopleYouKnowPicker.tsx`, tests in `tests/social_proximity.test.mjs`.

## 5. Level 2 checks adapted to a personal priority (plan, pass criteria fixed now)

1. Curve behavior across distances: score at 0, 1, 2, 5, 7.5, 10, 25, 50, 100, 500 miles. Pass: non-increasing everywhere, no jump over 10 points between adjacent tested distances, and no dependence on the place's area_type (identical output for the same miles).
2. Launch pairs, near and far from the same person, on the stored catalog (NYC, LA, SF): for each of 5 persons placed at known addresses, a place within 3 miles must score at least 25 points above a place 50+ miles away, in 5 of 5 persons and for both tiers; two places equidistant from the person within 1 mile must differ by under 3 points; a place 100 miles away must score at least 5 points above one 3,000 miles away only if option B keeps the floor-flat rule (stated now: B has them equal, so this pair is expected to tie).
3. Sensitivity to inputs: perturb each knot and the floor by the recorded range, shift a person's address by 0.5 and 1 mile, change the combine bonus 0 to 10. Pass: median place score change under 3 points for a 0.5 mile shift, rank correlation with the unperturbed run at least 0.95 for knot perturbations within range.
4. Independent check, brief for another agent (to be written as docs/SOCIAL_PROXIMITY_VALIDATION_BRIEF.md after approval): reproduce the adjusted help-hours by distance band from Schoeni, Cho and Choi 2022 and the 1 km and 5 km bands from Sun and Schafer 2023 from the papers' tables, then compare the curve's relative values at those distances. Pass: the curve's score ratio between the 5 to 10 mile band and the up-to-5-mile band is within 0.15 of the paper's ratio; the 100+ mile ratio within the paper's confidence interval.

## 6. Results and proposed level
Not run. Pending approval of an option in section 3.

## Sources checked this session
- Sun and Schafer 2023, J Gerontol B 78(11):1917-1926, SHARE waves 4 and 6, n=18,055, fixed effects: relative within 1 km and non-kin within about 5 km (odds ratios about 1.7 and 1.3 for severe loneliness); losses farther away not significant; a new core member offsets most of it. VERIFIED abstract-level. Correction to the earlier note in HAPPINESS_EVIDENCE_NOTES.md section 2c ("losing a child raises loneliness at any distance"): the version I read does not say that, and the code comment claiming it supports decline "through 25 km" for kin is not supported (kin effect only within 1 km).
- Schoeni, Cho and Choi 2022, Soc Sci Med 292:114627, PSID 2011 and 2013, 810 parents 55+ with ADL or IADL limits, 1,767 dyads: adjusted weekly hours of help coresident 5.99, same block 3.16, 2 to 5 miles 1.16, 5 to 10 miles 0.79, over 100 miles 0.58; little help beyond 2 to 5 miles. Possible endogeneity, wide intervals. VERIFIED abstract-level (via PMC page).
- Healy and Dunifon 2025, Demographic Research 52:34: 13% of grandchild households within 1 mile, almost half within 10 miles; 186 hours given by grandparents at 1 to 5 miles per the Cornell release (SUMMARY, not read in the paper); 208 hours not found. The paper PDF could not be read (compressed text).
- Cho and Smith 2019, Innovation in Aging 3(S1):S177, HRS, n=5,159: moving 50+ miles goes with less in-person contact with family (-0.31) and friends (-0.32); conference abstract only; no under-50 comparison reported.
- Not found or not retrieved: Compton and Pollak 2015 (citation only), Choi et al. 2020 beyond a SUMMARY, a Dutch distance paper (blocked 403).
- Not cited, per your list: Waldinger and Schulz 2010, Scellato et al. 2011, World Happiness Report 2025 household size, "Song et al. 2023".
