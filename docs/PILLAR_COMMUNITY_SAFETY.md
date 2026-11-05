# Pillar Deep-Dive: Community Safety

How `pillars/community_safety.py` scores a location (`get_community_safety_score`).

## What it measures
Crime safety from **agency-reported** rates: violent and property crimes per 1,000, scored
against the national scale (no area-type baselines), nudged by the recent trend.

## Inputs
- `get_crime_rates(lat, lon, city, state_abbr, area_type, population)` → FBI CDE
  (Crime Data Explorer), agency-level where available. `state` (2-letter) is required for CDE
  routing; population defaults to 10,000 for per-1k conversion.

## Scoring flow
1. **Rates per 1,000 people present.** Violent (murder, rape, robbery, aggravated assault) and
   property (burglary, larceny-theft, motor vehicle theft) offenses divided by residents plus
   workers for the share of the week they are at work (`data_sources/people_present.py`).
   Cities with an incident feed (NYC, LA, SF, Chicago, Philadelphia, Austin, Dallas, Boston) are
   measured in a circle around the place; everywhere else uses the police department's yearly total.
2. **Slots** (`_score_rates`): each rate becomes `100 - percentile` against the national scale
   (`data/community_safety_national_scale.json`, FBI per-agency data, population weighted).
3. **Blend:** `score = (1 - w) x violent slot + w x property slot`, with **w = 0.098**. One weight
   for every place; there is no retail-hub exception.
4. **Trend delta** (`_trend_delta`): a small +/- nudge from the recent violent-crime trend.
   `final = clamp(raw_score + trend_delta)`.

## Why property is weighted at about 10%
The weight is the property share of total harm from crime, so it is a formula with published
inputs, not a chosen number (`scripts/baselines/derive_community_safety_weight.py` writes
`data/community_safety_harm_weights.json`):

    w = H_property / (H_violent + H_property),   H = sum(national rate x cost per offense)

- **Cost per offense:** McCollister, French & Fang (2010), *The cost of crime to society*, Drug and
  Alcohol Dependence 108, Table 5 (total cost, 2008 US dollars): murder $8.98M, rape $241K,
  aggravated assault $107K, robbery $42K, burglary $6.5K, vehicle theft $10.8K, larceny $3.5K.
- **Offense rates:** BJS NIBRS-based national estimates for 2023, per 100,000 (violent 387.8,
  property 2,015.2).
- **Result:** property offenses are 5.2x as frequent as violent ones but 9.8% of total harm.

**Sensitivity (the answer depends on how murder and suffering are valued):** murder excluded 19.7%;
direct victim costs only (no pain and suffering) 29.9%, or 51.9% without murder. The previous
35% / 15% weights with an 8x retail-hub switch had no documented source; they match only the
narrowest direct-cost view. The standard in cost-benefit work is total social cost, hence 9.8%.

**Supporting research:** residents' perception of neighborhood crime tracks violent crime rates
most strongly (census-tract analysis of American Housing Survey data); Statistics Canada's Crime
Severity Index and the Cambridge Crime Harm Index also weight by seriousness (sentencing), which
ranks violent crime far above theft.

**Known limits:** costs are 2008 dollars from one study and rates are one year; the violent slot
counts offenses (murder is 1.5% of violent offenses by count but 56% of violent harm), so murder
is under-represented inside the violent slot. Re-run the derivation script when better inputs exist.

## Area of measure
For cities with an incident feed the circle is the smallest of 600, 800, 1000, 1200, 1500, 2000 m
holding at least 10,000 people (`MIN_NEIGHBORHOOD_RESIDENTS`). Tested alternatives (a minimum
radius of 800 or 1,000 m) reduce score movement when the pin moves but did not agree better with
third-party ratings, and the distance research (resident-drawn neighborhoods are smaller than a
census tract; crime effects on home prices act within about 0.1-0.25 mile) argues for the smallest
area with enough people, so 600 m stays.

## When it returns None (excluded from the composite)
The pillar deliberately returns `None` (rather than a misleading number) in three cases —
the catalog then drops it from the weight set:

| status | when | note |
|---|---|---|
| `DEGRADED` | no crime data at all | confidence 0 |
| `COMING_SOON` | jurisdiction not wired up in CDE yet | ⚠️ **coverage gap, NOT bad data** (Sleepy Hollow, Summit, Belmont Shore, Lakewood) |
| `DEGRADED` (state-aggregate) | only `fbi_cde_state` available | zero-tolerance: a state average is meaningless for one place, so it's withheld |

So a null community_safety is usually a **coverage gap**, not an error. Don't treat it as a
score of 0; the place is correctly weighted over its remaining pillars.

## Catalog / weighting
The 4 COMING_SOON places have `community_safety` weight 0; their other pillars renormalize to
sum to 100 (`repair_diversity_and_weights.py` ensured this). See CATALOG_RESCORE_RUNBOOK and
PILLAR_DATA_QUALITY.

## Gotchas
- Scores are **national**, not area-type-relative: one scale for every place, so an urban core with
  more reported crime than a suburb scores lower. Compare per-1k rates freely across area types.
- A place legitimately scoring low (Compton 6, Watts) reflects real reported crime, not a bug.
- The commuter-denominator boost relies on the LODES grid (same data as economic_security's
  job-accessibility); coverage gaps there fall back to no boost.

---

## DPv2 spec sheet and audit (2026-10-31, draft for owner approval, nothing in scoring changed)

```
Pillar: community_safety
Level: 2 (Verified), signed off by the owner 2026-11-04 with the independent validation waived (Level 1 signed 2026-11-01). The waiver and accepted gaps are recorded at the end of this document.
Construct (one sentence): Exposure to reported violent and property crime near the pin, expressed as the share of
  Americans who live somewhere with more of it. It measures reported risk, not felt safety and not cost to society.
Reference frame: fixed standard, expressed on a national scale (one curve for every place, 2024 breakpoints, no area type).
  The curve is the national population-weighted percentile of the rate. Because the breakpoints are fixed, a place that
  improves moves up the scale; it is not re-ranked against other places live.
  Evidence for the frame: tier 2 (revealed preference). Hedonic work shows people pay for lower crime (Bartley 2000;
  Gibbons 2004, London: criminal damage lowers prices, burglary showed no measurable effect). Neither study tests absolute
  versus relative rates, and I have not read either paper (summaries only, per the v2 draft). Tier 1 and tier 3 evidence for
  the percentile shape: none found. The percentile transform itself is a judgment.
Measurement area: two methods inside one pillar.
  369 places (HYPER_LOCAL, 8 to 11 cities with incident feeds): circle around the pin, smallest of 600, 800, 1,000, 1,200,
  1,500, 2,000 m holding at least 10,000 residents.
  893 (AGENCY_VERIFIED) and 158 (PRECINCT_PROXY): the whole police agency or county sheriff jurisdiction.
  Reason: incident feeds exist only for some cities; elsewhere the agency total is the finest public number. The 600 m floor
  follows distance research (resident-drawn neighborhoods, price effects within 0.1 to 0.25 mile), not verified here. The
  two methods are not shown to be comparable (mean score 42.9 circle, 58.6 agency, 58.4 proxy; the gap mixes real
  difference with method).
Place context inputs used (fields) and remaining area-type uses (with reason):
  Reads place_context.area_type only to pass it on; no scoring value keys on the label. The one remaining use is the
  census helper's fragment blend (urban or suburban label, areal estimate under 800), and the pillar rejects any place
  where that blend fires (raises, no data), so it is inert here. It does not read people density, activity per acre or
  people_10km from the context; the circle's residents come from the pillar's own areal tract estimate (disk, 600 to
  2,000 m), which is a different disk from any context field.
Inputs and data sources (with vintage): FBI Crime Data Explorer agency totals (Part I, last full year); city open-data
  incident feeds (NYC, LA, SF, Chicago, Philadelphia, Austin, Dallas, Boston, Denver, Charlotte, Las Vegas); NY state UCR;
  CA DOJ; LASD stations. National scale: 561 agencies, 2024 data, population weighted (data/community_safety_national_scale.json).
  Denominator: residents plus workers x 45/168 (ACS 2022, LODES).
Parameters:
  name | value | source | plausible range | sensitivity result
  property weight | 0.098 | McCollister et al. 2010 costs x BJS 2023 rates (as recorded in commit 1b6df81, inputs not re-checked) | 0.10 to 0.30 (outer bound 0.52) | 0.098 to 0.299 moves a place mean 3.4 points, 325 over 5, 59 over 10; no total moves over 1.4; rank Spearman 0.989 (audit_safety_weight_2026-10-25.md)
  trend cap | plus or minus 5 points, reached at plus or minus 100 percent | none | 0 to 5 (unknown) | dropping the trend: rank Spearman 0.998, mean absolute change 1.14, p95 4.0, 614 places move 1 or more, 226 move 2 or more (computed 2026-10-31 from stored trend_delta)
  circle minimum residents | 10,000 | none | unknown | not run (needs incident data)
  radius ladder | 600 to 2,000 m | distance research, unverified | unknown | 800 m floor cuts median pin-shift spread 13.7 to 9.6; 1,000 m gives 9.1
  work-week share | 45 of 168 hours | comment only | unknown | not run
  confidence by precision level | 93 / 82 / 69, minus 3 and 6 | none | unknown | not applicable (metadata, not score)
  national scale | 2024, 561 agencies | FBI CDE sample | sampling limits in the scale file | not run
Shared inputs with other pillars: LODES jobs grid in the people-present denominator (also used by economic security as a
  job-access input). No overlap test run. No other pillar uses crime.
Pin-shift sensitivity (2026-10-26, 500 m, 96 big-city places with incident feeds, 600 m circle): median score change across
  three pins 13.7, 95th percentile 34.3, max 46.3. 800 m floor: median 9.6. 1,000 m: median 9.1. Cause: real variation in
  crime over 500 m. The 1,051 agency-level places are not circle based and were not tested (they would not move with the pin
  except at jurisdiction borders). Disclosed limit, not fixed. Not shown in the API.
Independent validation source and result: none yet. No precinct, rating or price check of the score exists. Pass criteria
  to be fixed before any run (see Level 2 plan).
All-places check (2026-10-31, n=1,420 scored of 1,476; 56 no data): mean 54.3. At 95 or higher: 114 (8.0 percent); exactly
  100: 24; exactly 0: 4; 5 or lower: 38. Spread by area type: NOT reported, the stored catalog rows carry no area type.
Fail-loud conditions: no crime data returns no data (56 places); state-aggregate only is withheld; an empty or missing
  national scale raises; an assumed or floored residents estimate raises; missing trend is flagged degraded; tracts with
  ACS population 0 are valid, tracts with no ACS row are reported separately (0ecac19). Open: Sunnyside and Windsor Terrace
  tract gaps unresolved.
Launch check pairs: not defined yet. Proposed: should differ: Compton CA vs Palo Alto CA; Brownsville Brooklyn vs Park Slope.
  Should be similar: Park Slope vs Brooklyn Heights; Bethesda MD vs Chevy Chase MD. Pass criteria to be fixed first.
Known data limits: FBI sample of 561 agencies (large cities at citywide rate, so within-city variation is not in the scale);
  reported crime, which undercounts and varies by reporting practice; the violent slot counts offenses so murder is 1.5
  percent of violent offenses by count but 56 percent of violent harm; 2008-dollar costs from one study; 87 places have no
  trend; 129 tract populations came from the 2019 vintage; agency-level scores cannot see within-agency variation.
Last re-validated: never (re-validation not scheduled).
```

### Crime-type check (offline part, 2026-10-31)

What stored data can show: the catalog keeps only the violent and property rates per 1,000 and their slots, no per-offense counts. So the type question cannot be answered offline beyond these facts.
- Violent and property slots rank places similarly but not identically (Spearman 0.744 across 1,420 places).
- The property term barely changes the ranking: dropping it entirely (weight 0) gives rank Spearman 0.997 with mean change 1.6 points (audit_safety_weight_2026-10-25.md).
- Murder, rape and aggravated assault are not separated inside the violent slot, so the slot cannot reflect that a murder costs about 84 times an aggravated assault (McCollister Table 5, as recorded). This is the one type question that could move scores materially, and it cannot be sized offline.

### Absolute versus relative rates (decision input)

Today's score is already a fixed curve over rates (2024 breakpoints), so it is absolute in the sense that matters: the same rate gets the same score everywhere and does not change when other places change. What is relative is the shape: equal score steps are equal steps in population rank, not equal steps in risk. At the national breakpoints, the violent slot moves 10 points between 0.66 and 1.13 per 1,000 (a 0.47 gap) but also 10 points between 7.4 and 23.9 (a 16.5 gap). Every absolute-risk alternative I can write (linear or exponential in rate) needs a constant with no source. Evidence does not favor either; neither hedonic study tests it. So the rank shape stays as a documented judgment (tier 2 frame, shape unsourced).

### Audit gap table

| # | Gap | Principle | Recommended fix | Expected score impact |
|---|---|---|---|---|
| G1 | Construct was never one sentence; weight derivation (social cost) differs from the score's meaning (rank of reported risk) | P2 | Adopt the construct above; docs only | None |
| G2 | Frame evidence is tier 2 from summaries, absolute versus relative untested | P1 | Record as tier 2 with the limit; read Gibbons 2004 and a crime-severity index before any claim of validation | None |
| G3 | Violent slot ignores crime type (murder under-weighted) | P4, P7 | Crime-type check needs per-offense counts (FBI CDE) for a sample of agencies; then test a harm-weighted violent index against the current slot | Unknown until data is read; could move high-murder places by many points |
| G4 | Two measurement areas in one pillar, not shown comparable | P3 | Record the reason and the limit; compare circle versus agency for cities that have both after approval of a data read | None now; unknown after |
| G5 | Trend modifier unsourced | P4 | Option below | Dropping it: mean 1.14, p95 4.0, rank 0.998 |
| G6 | Circle minimum, radii, work-week share unsourced | P4 | Record as TODOs with range "unknown" | None |
| G7 | Pin shift moves circle scores a median 13.7 points | P6 | Already accepted as a disclosed limit; add to API confidence only if you approve a code change | None to score |
| G8 | No independent validation, no launch pairs | P7, P10 | Level 2 plan below | None |
| G9 | Clumping: 114 at 95 or more, 24 at 100, 4 at 0; area-type spread not reportable | P10 | Report spread by area type using context area type in the all-places check | None |
| G10 | Residents denominator is the pillar's own tract disk, not a context fact | P13 | Leave; context fields are 1 km and 10 km disks, a different area. Revisit only if a safety radius is added to the context | None |
| G11 | Trend code comment says 30 percent = 3 points; formula gives 1.5 | doc | Fix comment | None |
| G12 | 56 places no data (state aggregate only); 2 NYC tract gaps | P9 | Needs a live FBI check on a few places; not run | Adds scores for places now null |
| G13 | Docs said area-type-relative | doc | Fixed in this commit | None |

### Options for scoring

A. No scoring change (approved 2026-10-31, with the crime-type read above). Record every judgment with its range, fix the stale docs and the trend comment, run the Level 2 checks on today's scores. Reaches Level 2 at the lowest cost, but leaves G3 open.
B. A, plus remove the trend modifier (G5). Removes an unsourced parameter; mean 1.14 point shift, rank unchanged (0.998). Costs a rescoring of 1,420 composites and drops confidence in nothing.
C. A, plus a harm-weighted violent index by crime type (G3). Most defensible construct, but needs per-type counts we do not store and a data pull, and it changes scores by an unknown amount.

Recommendation: A now, and ask for one small data read to size G3 (per-offense counts for about 50 agencies from FBI CDE, no key beyond the one already in use). Decide B and C after seeing that size. Trend removal (B) is cheap but also not urgent: it is a listed TODO that Level 2 allows.

### Crime-type read result (2026-10-31, owner-approved FBI CDE read)

Data: FBI CDE summarized/agency, calendar 2024, seven Part I offenses, 50 agencies (20 large cities, 15 cities, 15 county sheriffs, random with a fixed seed from the saved national-scale samples). 47 had all four violent offenses for 12 months. Offense counts sum to the stored violent total within 3 (median 0). Raw rows: `analysis/safety_crime_type_sample_2026-10-31.jsonl`. About 350 requests, no downloads.

Test: rank the 47 agencies by violent offenses per 1,000 residents (what the slot uses) and by cost-weighted violent harm per 1,000 (McCollister costs as recorded in the harm-weights file). Ranks are within this sample, not population weighted, so this sizes the effect and is not a score.
- Rank correlation 0.833. Without murder it is 0.965, so almost all of the disagreement is murder.
- Median rank shift 4.3 percentile points, 90th percentile 27, max 67. 19 of 47 move more than 10 points, 7 more than 20.
- Murder is the median 31 percent of an agency's violent harm (0 to 97 percent); 19 of 47 agencies recorded no homicide in the year.
- The big movers are small places where one to three homicides swing the harm rank: Hancock County MS (0.6 violent per 1,000, 3 homicides) goes from rank 4 to 72; Lawrence County MO (1 homicide) 20 to 59. Large cities move for real reasons: Richmond VA (56 homicides) 61 to 89.

Reading: the violent slot does ignore crime type, and the choice matters. But a cost-weighted index is dominated by homicide counts that are tiny and noisy in the small agencies that make up most of the catalog, so option C as stated would trade a known blind spot for year-to-year noise in about 40 percent of places. This sample is too small to fit a fix and not population weighted. Conclusion: no scoring change; record it as a disclosed limit (the violent slot counts offenses equally) and treat any type weighting as a future option only with several years of pooled homicide counts.

### Level 2 results and proposed level (2026-11-01)

Run by a separate agent, report in `analysis/safety_level2_report_2026-11-01.md`; criteria fixed in `docs/PILLAR_COMMUNITY_SAFETY_LEVEL2_BRIEF.md` before any result.
- Launch pairs: PASS. Compton 6.5 vs Palo Alto 71.8, Camden 2.8 vs Newton 92.0, Compton vs Naperville 90.3 all differ by 30 or more; Newton vs Naperville within 2. Park Slope 71.9 vs Brooklyn Heights 46.9 (similar pair) fails, which is the pin-shift limit showing.
- All-places check: PASS. n=1,420. 114 at 95 or higher, 24 at 100, 4 at 0. Largest single value 1.76 percent. 10th / median / 90th by area type: urban residential 7.5 / 34.9 / 73.4; suburban 20.8 / 61.9 / 95.7; exurban 31.4 / 74.5 / 96.2; rural 39.3 / 70.6 / 98.0 (area type from offline place-context functions, approximate).
- Pin-shift: disclosure only. Circle places median 13.7, p95 34.3 (600 m). Agency-level places: no boundary file; a place-polygon proxy measured 388 of 1,051, 300 of them within 1 km of the edge.
- Independent validation: NOT DONE. 4b (FBI agency rate vs circle mean, 10 agencies): Spearman 0.115, inconclusive by prior agreement. 4a (NYPD precinct tallies, 20 precincts chosen in advance) was not run: the figures are PDF downloads and the owner chose not to download anything. No other city publishes an annual district table that I could find.

Proposed level: Level 1 (Converted). Level 2 is not reached because its independent validation did not run. Accepted TODOs to list at sign-off: independent validation (NYC precinct route ready if downloads are allowed later); crime-type weighting (left as disclosed limit); trend, 10,000-resident minimum, radii, work-week share and confidence values unsourced; mixed circle and agency areas; 56 places with no data; two NYC tract gaps; pin-shift not shown in the API. Last re-validated: 2026-11-01 (checks 1 to 3 only).

Sign-off: Level 1, owner, 2026-11-01. Accepted TODOs: as listed above.

### Level 2 sign-off with validation waived (owner, 2026-11-04)

Level 2 (Verified), signed off by the owner 2026-11-04. The independent validation was not run and is waived, not passed. The
planned NYPD precinct check would only test small-area ranking inside one city (a few hundred of 1,476 places) and says
nothing about the national scale the score is built on, so it would not have settled this. A real independent check needs a
second national source compared across the full catalog (for example county violent crime rates from CDC data); none has been
chosen or run. Accepted gaps: independent validation waived (FBI agency-rate comparison inconclusive, Spearman 0.115, n=10);
crime-type weighting left as a disclosed limit; trend, 10,000-resident minimum, radii, work-week share and confidence values
unsourced; mixed circle and agency areas; 56 places with no data; two NYC tract gaps; pin-shift not shown in the API and
disclosure only (circle places median 13.7, p95 34.3 at 600 m). Launch pairs and the all-places check passed (2026-11-01).
Last re-validated: 2026-11-01 (checks 1 to 3 only).
