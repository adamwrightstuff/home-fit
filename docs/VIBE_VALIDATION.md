# Vibe validation: which measure separates the places the owner says have it (criteria fixed before running, 2026-11-05)

Why: the local scene tag started from Larchmont having a vibe that Pelham lacked, and independent share does not separate them (11 of 12 hangout venues independent in Larchmont, 4 of 4 in Pelham). The owner's judgments are the test (survey-level evidence, one person, so a first pass only). Read-only, offline, from the brand-tag re-read (data/local_scene_brand_reads.jsonl, 1,476 places) and stored catalog fields.

## The owner's judgments (2026-11-05)
- Have it: Larchmont, Bronxville, Carroll Gardens, Tribeca, West Village. Montclair NJ "I hear", so reported but not counted.
- Do not have it: Pelham, Pelham Bay, Sunnyside.
- Less than Carroll Gardens and Tribeca: Windsor Terrace. Ambiguous, reported only: Kips Bay (might, but does not feel like it).

## Candidate measures (all computed for every catalog place; hangout venues = cafe, bar, gallery, bookstore, records, theater)
1. Hangout venues within the place's amenities radius (1,200 or 1,500 m).
2. Hangout venues within 400 m of the pin, and within 600 m.
3. Core density: the most hangout venues inside any 400 m circle centered on a hangout venue (finds the village center even when the pin is off it); same at 250 m.
4. Hangout share of all venues.
5. Independent hangout venues (no OSM brand tag) and their share of hangout venues.
6. Cultural venues (gallery, bookstore, records, theater) and their share.
7. Types present among hangout venues (variety, 0 to 6).
8. Stored scores for context: amenities, built environment, natural beauty, social fabric, active outdoors.

## Pass criteria
A measure separates the owner's places if (a) every counted place that has it ranks above every counted place that does not, by percentile among all catalog places with a value, and (b) Windsor Terrace ranks below both Carroll Gardens and Tribeca. Reported for each measure: the percentile of every named place and the gap between the lowest "has it" and the highest "does not". With 5 and 3 places, passing is a first signal, not proof; the 10 percent of places with no venue data are excluded from percentiles.

## Results (run 2026-11-05; 1,383 places with venue data; percentiles among them)
Raw counts (hangout venues, within 400 m, core density at 400 m, independent, cultural, types): Larchmont 13 / 6 / 6 / 12 / 4 / 4; Bronxville 17 / 11 / 11 / 15 / 3 / 4; Carroll Gardens 121 / 14 / 38 / 119 / 23 / 6; Tribeca 311 / 47 / 93 / 260 / 68 / 6; West Village 629 / 73 / 122 / 565 / 146 / 6; Pelham 4 / 1 / 2 / 4 / 2 / 4; Pelham Bay 2 / 0 / 1 / 1 / 0 / 2; Sunnyside 57 / 25 / 27 / 55 / 1 / 3; Windsor Terrace 116 / 7 / 38 / 113 / 12 / 6; Kips Bay 276 / 34 / 72 / 217 / 16 / 6; Montclair NJ 13 / 0 / 7 / 12 / 3 / 3.

| Measure | Has it (Larchmont, Bronxville, Carroll Gardens, Tribeca, West Village) | Does not (Pelham, Pelham Bay, Sunnyside) | Windsor Terrace | Separates? |
|---|---|---|---|---|
| Hangout venues in the radius | 67, 74, 95, 99, 100 | 38, 23, 90 | 95 | no (Sunnyside) |
| Within 400 m | 79, 88, 91, 99, 100 | 50, 22, 96 | 82 | no (Sunnyside) |
| Core density 400 m | 62, 77, 95, 99, 99 | 33, 17, 91 | 95 | no |
| Independent hangout venues | 69, 74, 95, 99, 100 | 43, 18, 90 | 95 | no |
| Independent share | 55, 45, 66, 38, 48 | 83, 10, 63 | 65 | no |
| Cultural venues (gallery, bookstore, records, theater) | 74, 68, 96, 99, 100 | 59, 17, 44 | 91 | yes, gap 9; Windsor Terrace below Carroll Gardens and Tribeca |
| Cultural share | 77, 50, 53, 60, 63 | 92, 15, 29 | 35 | no |
| Active outdoors score (context) | 100, 85, 98, 99, 97 | 82, 47, 82 | 78 | passes with gap 2; not a vibe measure, treated as chance with n of 5 and 3 |
Other context scores (amenities, built environment, natural beauty, social fabric) do not separate. Reported only: Kips Bay is at the 93rd percentile for cultural venues and the 98th for hangout venues (79 percent independent, the lowest share of the named places, and only 6 percent of its hangouts are cultural); Montclair NJ is at the 68th for cultural venues and the 22nd within 400 m (owner has only heard it has the vibe).

Result: one measure passes, cultural venue count, and the margin is thin (lowest "has it" 68, Bronxville with 3 venues; highest "does not" 59, Pelham with 2). Counts of cafes and bars alone do not separate: Sunnyside is a busy commercial strip with 57 hangout venues and 1 cultural venue. Post-hoc, not pre-registered: the mean of the cultural-venue and within-400 m percentiles also separates all eight (lowest "has it" 76.5, highest "does not" 70.0, Windsor Terrace 86.5 below Carroll Gardens 93.5 and Tribeca 99.0) and puts Kips Bay at 95.5 and Montclair NJ at 45. Limits: eight places, one judge, venue counts in suburbs are small and depend on OSM coverage.

## Evidence policy (owner decision, 2026-11-05)
The published "coolest places" lists (Time Out 2019 to 2026, Matador, Budget Travel, real-estate blogs, APA Great Neighborhoods) are not used to define, choose or tune the measure. Their criteria mix in diversity, community spirit, affordability, "right now" energy and editorial taste, and most state no scoring method, so they would import those choices into the score. They are used only as a sanity check, reported separately and never fed back into the measure. The labels that count are the owner's own judgments, plus whatever the owner adds. The measure itself rests on what the urban-vitality literature supports (density and mix of third places and cultural venues, Jacobs), and is then checked against the owner's places.
Sanity check already run (not used for any decision): 17 Time Out US picks that exist in the catalog (exact matches only) have a median rank at the 89th percentile for cultural venues, 11 of 17 in the top quarter; the lower ones (Astoria, Flatbush, Glen Park, Coral Gables, Brewerytown) are picks Time Out makes for food, diversity and community more than culture.

## Owner answers log (recorded before any new measure is computed on them; unknown or skipped places are left out)
Round 1 (2026-11-05): Astoria, Queens: some of it. Fort Greene, Brooklyn: has it. Hastings-on-Hudson: does not know it (skipped). Hoboken NJ: skipped (no preference given).
Round 2 (2026-11-05): Park Slope: has it. Rye: has it. Mamaroneck and Scarsdale: does not know them (skipped). Note: Rye has 0 cultural venues and 1 hangout venue within the catalog pin's radius in the stored data (pin off the downtown), so the current measure reads Rye as having none of it while the owner says it has it.
Round 3 (2026-11-05): Williamsburg: has it. Tarrytown, New Rochelle, Dobbs Ferry: does not know them (skipped). Owner also said other metros can be used.
Round 4 (2026-11-05, other metros): Wicker Park, Chicago: has it. Silver Lake, Los Angeles: has it. Evanston and Brookline MA: does not know them (skipped).
Tally so far: has it (11): Larchmont, Bronxville, Carroll Gardens, Tribeca, West Village, Fort Greene, Park Slope, Rye, Williamsburg, Wicker Park, Silver Lake. Some of it (2): Astoria, Windsor Terrace. Does not have it (3): Pelham, Pelham Bay, Sunnyside. Unconfirmed: Montclair NJ (hearsay), Kips Bay (ambiguous).
Round 5 (2026-11-05): Murray Hill: does not have it. Forest Hills, Queens: does not have it. Naperville and Plano: does not know them (skipped).
Tally: has it (11), some of it (2: Astoria, Windsor Terrace), does not have it (5: Pelham, Pelham Bay, Sunnyside, Murray Hill, Forest Hills).

## Extended test (criteria fixed before running, 2026-11-05)
With 11 "has it" and 5 "does not" places the strict separation rule is too brittle for one-off cases, so the extended test uses pairwise ranking: for each measure, the share of the 55 (has it, does not) pairs where the "has it" place ranks higher by percentile among catalog places (1.0 is perfect, 0.5 is chance). Pass: at least 0.80 (judgment limit, fixed here). Windsor Terrace must rank below Carroll Gardens and Tribeca, as before. Measures: the eight from the first test plus two combinations fixed now: C1 = mean of the cultural-venue percentile and the within-400 m hangout percentile; C2 = the larger of the two percentiles. Known data problem reported separately, not removed: Rye (a "has it" place) has almost no venues near the catalog pin, so any pin-based measure will rank it low; the test is also reported without Rye.

## Extended test results (run 2026-11-05; 11 has-it, 5 does-not; 55 pairs)
Pairwise ranking (1.0 perfect, 0.5 chance; limit 0.80) and the Windsor Terrace ordering: cultural venues 0.82 (0.89 without Rye), Windsor ordering holds: PASS. Hangout share of venues 0.84, but Windsor ordering fails (Larchmont at the 34th percentile): not a pass. Everything else fails: hangout venues in the radius 0.67, within 400 m 0.56, within 600 m 0.60, core density 0.66, independent hangouts 0.68, independent share 0.66, cultural share 0.72, variety 0.74, C1 0.72, C2 0.65. The combinations do not beat cultural venues alone.
Two stubborn cases: Rye (has it; 17th percentile, venues are off the catalog pin) and Murray Hill (does not have it; 96th percentile on cultural venues because Manhattan is dense, 24 venues of which 12 are theaters).
Post-hoc, not pre-registered (the counts were looked at against these labels): dropping theaters and venues with an OSM brand tag improves the ranking: cultural venues without theaters 0.85 (0.92 without Rye), without chains 0.85, both 0.87 (0.94 without Rye), Windsor ordering holds in all. Murray Hill stays at the 93rd percentile with 10 independent galleries, bookstores and record stores, and Silver Lake is at the 72nd with 2.

## Candidate frozen for a holdout test (2026-11-05, before any new answers)
Independent galleries, bookstores and record stores within the place's amenities radius (cultural venues excluding theaters and any venue carrying an OSM brand or brand:wikidata tag). Places the owner labels from now on are the holdout: the same pairwise test, limit 0.80, run only on places labeled after this line, with no change to the candidate.

## Holdout answers (labeled after the candidate was frozen; the candidate's percentile in brackets, recorded from the frozen definition)
Round 6 (2026-11-05): Boerum Hill, Brooklyn: has it (98th). Bay Ridge, Brooklyn: does not have it (87th). Garden City NY and Lincoln Park Chicago: does not know them (skipped).
Round 7 (2026-11-05): Greenpoint, Brooklyn: has it (97th). Flushing, Queens: does not have it (25th). Great Neck and Jersey City: does not know them (skipped).
Holdout result so far (frozen candidate, 2 has-it and 2 does-not, 4 pairs): 4 of 4 pairs ranked correctly (Boerum Hill 98 and Greenpoint 97 above Bay Ridge 87 and Flushing 25). Too few places to count as a test; it is a first signal only.
Round 8 (2026-11-05): Cambridge MA: has it (94th). Venice, Los Angeles: has it (72nd). Hayes Valley, San Francisco: has it (96th). Fishtown, Philadelphia: has it (90th).
Round 9 (2026-11-05): Rittenhouse Square, Philadelphia: has it (93rd). Scottsdale: skipped (no preference). Oak Park IL and Decatur GA: does not know them (skipped).
Round 10 (2026-11-05): Upper East Side: some of it (96th). Battery Park City: does not have it (95th). Long Island City: some of it (93rd). Midtown East: skipped (no preference).

## Holdout result (frozen candidate; places labeled after the freeze)
Has it (7): Boerum Hill 98, Greenpoint 97, Cambridge 94, Venice 72, Hayes Valley 96, Fishtown 90, Rittenhouse Square 93. Does not (3): Bay Ridge 87, Flushing 25, Battery Park City 95. In between: Upper East Side 96, Long Island City 93.
Pairwise ranking on the holdout: 16 of 21 pairs correct = 0.76, below the 0.80 limit, so the frozen candidate is NOT validated. The misses: Battery Park City (95th, a planned residential and office area that does not feel like it) outranks four has-it places, Bay Ridge (87th) outranks Venice (72nd), and the two "some of it" places (Upper East Side, Long Island City) rank above Cambridge and Fishtown. The common cause is that raw counts reward dense Manhattan whatever the feel.

## Exploratory after the holdout failed (post-hoc; 18 has-it vs 8 does-not including Battery Park City, Bay Ridge, Flushing)
Pairwise ranking: cultural venues 0.81; independent cultural venues without theaters 0.83 (the frozen candidate); independent cultural venues as a share of all venues nearby 0.88; same as a share of hangouts 0.82; hangout share of venues 0.83; cultural share of hangouts 0.80; core density 0.58. The share measure ranks the dense places that do not feel like it low (Murray Hill 48th, Battery Park City 57th, Forest Hills 47th, Bay Ridge 54th, Flushing 23rd) while keeping most has-it places above them, but it is not clean (Silver Lake 52nd and Venice 54th sit below Bay Ridge 54th; Rye 23rd is the pin problem). Reading: raw counts reward density, a mix measure ("what share of nearby places are independent galleries, bookstores and record stores") reads character instead.

## Candidate 2 frozen for a second holdout (2026-11-05, before any new answers)
Independent galleries, bookstores and record stores (no theaters, no OSM brand or brand:wikidata tag) as a percent of all named venues of the seven types within the place's amenities radius, ranked as a percentile among catalog places with venue data. Same test: pairwise ranking, limit 0.80, run only on places labeled after this line.

## Holdout 2 answers (labeled after candidate 2 was frozen; candidate 2 percentile in brackets)
Round 11 (2026-11-05): Chelsea: has it (98th; candidate 1 count 100th). Financial District: some of it (56th; count 94th). Clinton Hill: some of it (75th; count 98th). Ridgewood, Queens: skipped. No "does not" place in this round, so the pairwise test cannot run yet; directionally the share measure puts the two "some of it" places well below Chelsea (56 and 75 against 98) where the count measure put them at 94 and 98.
Round 12 (2026-11-05): Back Bay, Boston: has it (candidate 2: 92nd). Beacon Hill, Boston: some of it (73rd). Santa Monica: has it (56th, a miss for candidate 2). Hollywood, Los Angeles: skipped (no preference).
Round 13 (2026-11-05): Yonkers: does not have it (candidate 2: 23rd). Brighton Beach: does not have it (61st). Hell's Kitchen: has it (48th, a miss). Jackson Heights: skipped.

## Holdout 2 result (candidate 2, places labeled after the freeze)
Has it (4): Chelsea 98, Back Bay 92, Santa Monica 56, Hell's Kitchen 48. Does not (2): Yonkers 23, Brighton Beach 61. In between (3): Financial District 56, Clinton Hill 75, Beacon Hill 73. Pairwise ranking: 6 of 8 pairs = 0.75, below the 0.80 limit: candidate 2 is NOT validated either (tiny sample). The misses are Santa Monica and Hell's Kitchen, which have it for dining, nightlife and street energy more than galleries and bookstores.

## Are hangouts relevant? (owner challenge, 2026-11-05; exploratory on all 32 labeled places, 22 has-it vs 10 does-not)
Raw hangout counts fail because they reward density (0.69 to 0.77). Hangouts as a share of nearby venues is the best single measure (0.87, 0.90 without Rye), and the mean of the culture-share percentile and the hangout-share percentile ranks 92 percent of pairs correctly (0.96 without Rye): culture share alone 0.86, hangout share alone 0.87, minimum of the two 0.89, maximum 0.90. Hangouts add information: Larchmont is at the 34th percentile on hangout share but the 87th on culture share, and Hell's Kitchen is at the 48th on culture share but the 78th on hangout share. Misses that remain: Battery Park City (mean 64) and Brighton Beach (57) sit above Venice (53) and Silver Lake (59); Rye is the pin problem.
Not validated: the combination was found on the same labels, so it needs a fresh test.

## Candidate 3 frozen (2026-11-05, before any new answers)
Mean of two percentile ranks among catalog places with venue data: (a) independent galleries, bookstores and record stores (no theaters, no OSM brand tag) as a share of all named venues of the seven types in the place's radius; (b) hangout venues (cafe, bar, gallery, bookstore, records, theater) as a share of the same venues. Test: pairwise ranking on places labeled after this line, limit 0.80.

## Holdout 3 answers (labeled after candidate 3 was frozen; candidate 3 percentile in brackets)
Round 14 (2026-11-05): Gowanus: has it (82nd). SoHo: has it (79th). Upper West Side: has it (59th). Harlem: skipped (no preference).
Round 15 (2026-11-05): Bensonhurst: does not have it (23rd). Huntington NY: some of it (67th). Mount Vernon and Port Washington: skipped.
Round 16 (2026-11-05): Sheepshead Bay: does not have it (24th). Rego Park, Elmhurst and Rockville Centre: skipped.

## Holdout 3 result (candidate 3, places labeled after the freeze)
Has it (3): Gowanus 82, SoHo 79, Upper West Side 59. Does not (2): Bensonhurst 23, Sheepshead Bay 24. In between (1): Huntington 67. Pairwise ranking: 6 of 6 pairs correct (1.00). Too few places to count as a pass (5 places, and the two "does not" places are easy low scorers; the hard ones, Battery Park City 64, Murray Hill 59, Brighton Beach 57, came from the earlier rounds); directionally consistent with the exploratory 0.92 on all 32 labeled places, which was found on the same labels and is not independent evidence. Known limit unchanged: towns whose main street is off the catalog pin (Rye, Hastings-on-Hudson, Dobbs Ferry, Great Neck, Garden City, Ossining all in the bottom fifth) read low.

## Owner decision (2026-11-05): rank within density bands
The owner approved ranking each share against places of similar density (five bands of activity per acre, the continuous factor Active Outdoors uses) instead of against the whole catalog. Exploratory evidence behind it (same labels, 25 has-it vs 12 does-not): combined shares 0.93 across all places, 0.96 within density bands; culture venue count 0.89 to 0.93. Peer-based, so the expected values are unsourced (DPv2). Data only; no UI change, nothing pushed.

## Catalog results with density-band ranking (2026-11-05; data only, not in the live catalog; CSV: analysis/local_scene_v2_catalog.csv)
1,476 places: 93 have no venue data, 538 have fewer than 15 venues near the pin (cannot be lively), 845 are eligible. "Lively" (top quarter of its density band, at least 15 venues): 260 places (18%). By density band, sparse to dense: 15, 46, 62, 62, 73 lively. Neighborhoods 143 of 567 (25%), suburbs 116 of 904 (13%). Owner's labeled places: lively 15 of 28 "has it" (Bronxville, Carroll Gardens, Tribeca, West Village, Fort Greene, Park Slope, Wicker Park, Boerum Hill, Greenpoint, Fishtown, Chelsea, Back Bay, Gowanus, SoHo, East Village) and 0 of 12 "does not". Not lively among "has it", with the within-band reading: Larchmont 65.3, Hayes Valley 68.2, Mission District 66.7, Williamsburg 61.7, Marina District 60.4, Cambridge 57.6, Silver Lake 55.9, Rittenhouse Square 55.3, Hell's Kitchen 50.2, Venice 49.1, Santa Monica 45.1, Upper West Side 42.8, Rye 24.1 (few venues). Highest "does not": Battery Park City 52.1, Pelham 42.6, Brighton Beach 41.7, Murray Hill 39.9.
Cut-offs on the within-band reading (eligible places only): at 45 keeps 26 of 28 has-it and 1 of 12 does-not, passing 529 places (36% of the catalog); at 52.5 keeps 23 and 0, passing 430 (29%); at 55 keeps 23 and 0, passing 405 (27%); at 60 keeps 20 and 0, passing 352 (24%); at 70 keeps 15 and 0, passing 238 (16%); at 75 keeps 12 and 0, passing 175 (12%). The gap between Battery Park City (52.1) and the next has-it places (55.3 and up) is what a cut near 53 to 55 would sit in; that placement is read off these labels, so it is a judgment, not a sourced cut.

## Town labels for the boundary test (2026-11-05)
Asked about towns that have a place or county subdivision boundary. Has it: Manhattan Beach CA, Beverly Hills CA. Some of it: Culver City CA. Does not have it: Hempstead NY. Skipped (does not know): Nyack, White Plains, Summit NJ, Ridgewood NJ, Mill Valley, Compton, Cicero, Revere, Valley Stream, Freeport, Upper Darby, Berwyn. With the earlier labels, the in-scope has-it towns are Bronxville, Rye, Cambridge, Santa Monica, Manhattan Beach, Beverly Hills (6) and the does-not towns Pelham and Hempstead (2), so the ordering check (at least 3 of each) cannot run.

## Pre-registration: what counts as "it" (2026-11-06, written before the run)
Owner direction: "coolest" is the only thing that matters (friendliness, "best" and livability lists are not relevant). New labels from the owner: Los Feliz has it, Hermosa Beach has it, Redondo Beach some of it, Mar Vista does not, Marina del Rey does not; Koreatown ("a bit ethnic") and Atwater Village (unsure) are not used. Silver Lake and Venice were already labels. Time Out's resident-voted LA index (Silver Lake coolest, Los Feliz runner-up) agrees and is a sanity check only.
Candidates, fixed now, all ranked within geography (town or pin circle) and density band, with places that have no density figure given no reading (the Mar Vista fix): A = current (mean of culture-share and hangout-share ranks); B = the larger of those two ranks; F = mean of three ranks, culture share, hangout share and independent food-and-drink share (cafes, bars and restaurants with no OSM brand tag, as a share of all venues). Test: pairwise ranking of has-it against does-not places on all labels, pass at 0.80 or more. All labels have been seen, so this is exploratory: a candidate that passes still needs labels from places not yet named before it counts.

## Result of the pre-registered "it" test (run 2026-11-06; 32 has-it, 13 does-not, 416 pairs; exploratory, all labels seen)
Pairwise ranking: A (current) 0.938, B (larger rank) 0.901, F (adds independent food and drink share) 0.882. All pass 0.80, and neither change beats the current measure, so the venue definition is not what is wrong. Pelham Bay and Mar Vista have no density figure and get no reading under the fix (Mar Vista previously read 80.0 against only four peers).
Where it breaks (A, reading within peers): has-it places at 41 to 49 are Upper West Side 41, Venice 42, Los Feliz 46, Silver Lake 48, Beverly Hills 48, Hell's Kitchen 49 (Chelsea 26 and Rye 21 below); does-not places above them are Pelham 53 and Battery Park City 50. Silver Lake outranks 11 of the 13 does-not places but sits under a cut of 55. The ranking is mostly right; two does-not outliers (Pelham, a town on the boundary measure, and Battery Park City) force any single cut above several has-it places. Not validated: no fresh labels, and the cut remains an unsourced judgment.

## Pre-registration: wider venue set (2026-11-06, written before the read)
Why: the Silver Lake read (owner, 2026-11-06) found the Echo, Echoplex, Los Globos, Sleeper and independent clothing and vintage shops, none of which count in the seven types, while 53 of 182 named places were restaurants. The seven types were inherited from the amenities business list, not chosen for "cool"; coolness was never validated (the measure was only checked for ranking the owner's labels).
Read (OpenStreetMap, private server, all 1,476 places; pin circle at the place's radius, town boundary for the 552 towns): named places with amenity = nightclub, music_venue, cinema, arts_centre; craft = brewery or microbrewery = yes; shop = clothes, second_hand, boutique, fashion_accessories, music, musical_instrument, antiques, art, craft, tattoo, comics. Raw tags, brand and brand:wikidata are stored.
Candidate G, fixed now: venues = the seven old types plus all of the new types above. Culture venues = old culture venues + arts (arts_centre, shop=art, shop=craft) + independent shops (the shop list above, with no OSM brand or brand:wikidata tag). Hangouts = old hangouts + nightclub, music_venue, brewery, cinema, arts_centre. Reading = mean of the culture-share and hangout-share ranks within geography and density band, no reading without density, at least 15 venues, same as the current measure.
Pass criteria: (1) pairwise ranking on all labels at least 0.938 (the current measure's score on the same labels); (2) the median reading of the has-it places that currently read below 50 (Upper West Side, Venice, Los Feliz, Silver Lake, Beverly Hills, Hell's Kitchen, Chelsea, Rye) rises. If G fails either, the current measure stays. All labels have been seen, so a pass is still exploratory and needs fresh labels before it counts. Limits: brand tags miss some chains (Madewell, Buck Mason carry none in the Silver Lake read), and nightlife and boutiques depend on OSM mapping.

## Result: wider venue set, candidate G (run 2026-11-06; 32 has-it, 13 does-not, 416 pairs; exploratory)
Read: 1,476 places, 0 failed (data/local_scene_cool_reads.jsonl, untracked). 10 places had no matching new read in the test join and were scored on the old types only.
Criterion 1 FAILED: pairwise ranking 0.883 for G against 0.938 for the current measure on the same labels (below the pre-registered 0.938). Criterion 2 passed narrowly: the median reading of the eight has-it misses rose from 43.9 to 45.8 (Venice 42 to 59, Silver Lake 48 to 51, Hell's Kitchen 49 to 53; Los Feliz 46 to 44, Upper West Side 41 to 44, Chelsea 26 to 25, Rye 22 to 15).
Why it fails: the new types also appear on ordinary commercial strips, so does-not places rose more than has-it places: Hempstead 36 to 57, Bay Ridge 36 to 56, Brighton Beach 40 to 55, Pelham 53 to 51, Battery Park City 50 to 48. Clothing, second-hand and nightlife counts do not separate cool from busy.
Decision under the pre-registration: the current measure stays. Silver Lake's own read (107 places, culture 11.2%, hangouts 37.4% under G) shows the venues exist, but counting them as a share does not rank it above the ordinary strips in the owner's labels. No change shipped.

## Pre-registration: candidate G2, chain test by repeated name (2026-11-06, written before the run)
Why: G counted ordinary discount clothing stores (Bay Ridge 47, Hempstead 10) as independent because only OSM brand tags marked chains. G2 = G with one change: a venue (any type in the measure) counts as independent only if it has no brand or brand:wikidata tag AND its lower-cased name appears at most twice across all venue reads (old and new) in the 1,476 places. No new read; no other change. Pass criteria are the same as G: pairwise ranking on all labels at least 0.938, and the median reading of the eight has-it misses (Upper West Side, Venice, Los Feliz, Silver Lake, Beverly Hills, Hell's Kitchen, Chelsea, Rye) rises above 43.9. Exploratory (all labels seen).

## Result: G2 (repeated-name chain test) FAILS (run 2026-11-06; same labels, 416 pairs)
Pairwise ranking 0.75 against 0.938 for the current measure: criterion 1 failed. The median of the eight has-it misses rose to 49.6 (Venice 57, Silver Lake 55, Upper West Side 54, Hell's Kitchen 54) but Tribeca fell to 21, SoHo 29, West Village 36 and Los Feliz 35, while Bay Ridge stayed at 59, Brighton Beach 56, Pelham 54 and Hempstead 52. Bay Ridge's 47 clothing shops mostly have different names (local discount stores), so a name test cannot tell them from boutiques. The current measure stays; wider-venue work (G, G2) is closed unless a source for curated versus everyday retail is found.

## Correction (2026-11-06): label "Chelsea" matched the wrong place in the earlier tests
The 2026-11-06 pairwise tests above matched the label "Chelsea" to Chelsea, MA (Boston metro, reading 26) instead of Chelsea, Manhattan (reading 97.8). Rerun with the right place: current measure A 0.954 (was 0.938), B 0.913, F 0.911, G 0.907 (was 0.883), G2 0.779 (was 0.75). Pass criteria were not met by G or G2 either way (current measure still the best), and the median of the has-it misses is now 47.0 for A, 49.5 for G and 53.9 for G2 with Chelsea no longer a miss. Conclusions unchanged; the misses are Upper West Side 41, Venice 42, Los Feliz 46, Silver Lake 48, Beverly Hills 48, Hell's Kitchen 49 and Rye 22 (8 mapped venues).
Missed places, venue mix (2026-11-06): Silver Lake, Los Feliz, Venice and Beverly Hills are 59 to 69% restaurants with 1 to 13% bars and 12 to 29 independent cafes and bars, close to Marina del Rey and Mar Vista (64 to 69% restaurants, 6 to 9% bars), which the owner says do not have it. Upper West Side (60% restaurants) and Hell's Kitchen read like Murray Hill (57%). Ranking within metro instead of nationally lifts the misses (Silver Lake 48 to 57, Venice 42 to 49) but lifts Murray Hill (38 to 52) and Bay Ridge (36 to 52) as much, so it is no fix.
