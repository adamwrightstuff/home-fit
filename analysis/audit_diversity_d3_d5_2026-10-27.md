# Diversity pillar audit: D3, D4, D5 (2026-10-27)

Status: offline audit only. No scoring code, catalog files, or commits changed. No Census or paid API calls. Work was read from a detached worktree cut from origin/main (e0917b3); the one external input outside git is the untracked raw Census pull `data/backups_diversity_fix_2026-10-24/raw_race_counts.jsonl` (read-only).

## Method and what the data can and cannot say

- All 21 `*_composites_recomputed.jsonl` files were read (1,476 places). Each was last committed 2026-10-26, so they are current. Key used: `score.livability_pillars.diversity`.
- The stored record does NOT say which Census geography it used. So "which geography the stored score used" is inferred two ways: (1) reproduce the stored race and income entropy from the raw 24 Oct pull (which records the geography the current code picked); (2) compare the stored `population_25_plus` (taken from the same Census call as the stored score) with the total population of the geography the pull picked. These are inference, not a stored fact.
- The raw pull covers 1,451 places with data, 19 where the current code returned nothing, and 6 places not in the pull at all.

## Headline findings

1. 1,434 of 1,476 places (97.2%) are consistent: the stored race entropy equals the new seven-group formula recomputed on the current pick, and stored income entropy equals the recompute. For these, the geography is the same as the current code picks (both numbers matching under a different geography is not plausible).
2. 42 places (2.8%) are not consistent or not checkable: 17 do not reproduce, 19 return nothing now, 6 are absent from the pull.
3. 36 places that carry a race entropy are still on the OLD race formula (17 + 19). The tracker's "4 places" for D3 is an undercount.
4. Three places (Maspeth, Southport, Radnor) still show a diversity score of 0.0 with confidence 0 and weight 7.69 in their stored records, i.e. the fabricated-0 pattern the docs say was repaired. Whether `total_score` excludes them was not checked.

## D4 all-places table (geography consistency by metro)

| metro | places | consistent | does not reproduce | none now | not in pull |
|---|---|---|---|---|---|
| atlanta | 76 | 76 | 0 | 0 | 0 |
| austin | 58 | 58 | 0 | 0 | 0 |
| boston | 81 | 81 | 0 | 0 | 0 |
| charlotte | 41 | 41 | 0 | 0 | 0 |
| chicago | 103 | 103 | 0 | 0 | 0 |
| dallas | 81 | 79 | 2 | 0 | 0 |
| denver | 62 | 59 | 0 | 0 | 3 |
| houston | 74 | 72 | 2 | 0 | 0 |
| la | 105 | 105 | 0 | 0 | 0 |
| las_vegas | 30 | 30 | 0 | 0 | 0 |
| miami | 67 | 67 | 0 | 0 | 0 |
| nyc | 193 | 187 | 2 | 2 | 2 |
| orlando | 43 | 43 | 0 | 0 | 0 |
| philadelphia | 92 | 86 | 3 | 2 | 1 |
| phoenix | 64 | 56 | 2 | 6 | 0 |
| raleigh | 31 | 29 | 2 | 0 | 0 |
| sacramento | 58 | 55 | 1 | 2 | 0 |
| san_antonio | 49 | 49 | 0 | 0 | 0 |
| seattle | 5 | 4 | 1 | 0 | 0 |
| sf | 113 | 104 | 2 | 7 | 0 |
| tampa | 50 | 50 | 0 | 0 | 0 |
| total | 1,476 | 1,434 | 17 | 19 | 6 |

Geography the current code picks (1,451 with data): place 833, tract 564, county subdivision 54. I could not reconcile the tracker's "20" exactly; 17 + the 3 zero-score places is one possible reading, not verified.

### The 17 that do not reproduce: which way did the geography flip

Using stored `population_25_plus` against the current pick's total population (ratio under 0.4 means the stored value came from a smaller area; over 1.0 means a larger one):

- Stored place-sized, current code now picks tract (8): Croton-on-Hudson, Blue Bell, Doylestown, Sun Lakes, Youngtown, Apex, Foster City, Fremont. Their area types are suburban, exurban, or rural, so the code should prefer place data. The most likely cause is the place lookup failing on one run and the code silently falling back to the tract. That is the D4 mechanism, shown directly for 8 places.
- Stored tract-sized, current code now picks place (6): Carrollton, Southlake, Seabrook, Spring, Cold Spring Harbor, Somerton. Somerton is probably an artifact of the pull: it was labeled "place" with 1.59 million residents (Philadelphia), which the current 200,000-adult ceiling would reject and send to the tract, and the stored 3,882 adults is tract-sized. Not confirmed.
- Ambiguous (3): Benson, Rancho Murieta, Ballard (ratios 0.86, 0.80, 0.94). Ballard's 0.94 is higher than a single area normally gives, which points to a different tract. One hypothesis, untested: it was scored before the 2020 tract-boundary fix on 2026-10-06 (commit 74aeb16).

Same place under two geographies (14 clear cases, old formula, race entropy): median absolute difference 7.2 points, mean 8.1, max 27.8. Income entropy: median 4.2, mean 5.1, max 21.3. So geography choice is not cosmetic.

### The 19 where the current code returns nothing

Cranford, NoHo, Rittenhouse Square, Society Hill, Melrose District, Peoria, Scottsdale, Sun City, Surprise, Tolleson, Natomas, Oak Park, Almaden Valley, Bayview, Bernal Heights, Diamond Heights, Dogpatch, Evergreen (sf), Financial District (sf). They all hold plausible stored values (stored pop 25+ from 1,530 to 189,292), so the data existed at scoring time. Why the 24 Oct pull got nothing is unknown (transient API failure is the simplest guess; not tested). Under the current code these would raise and drop out of the headline, so the catalog and the live scorer disagree for them.

### Other D4 facts from the stored data

- 46 places typed "suburb" use tract data and 38 places typed "neighborhood" use place data. The 38 neighborhoods on place data share one city-wide value (for example seven Scottsdale-area neighborhoods all show 69.6; four Miami Beach and Miami neighborhoods share 77.0 or 78.5). Within a metro, 27 groups of places (67 places) share an identical race/income/age triple; 47 of those 67 are place-level.
- Mean stored headline by geography (consistent places only): place 72.7, tract 68.3, county subdivision 64.8. Mean age entropy: place 83.2, tract 70.0. Part of this is the neighborhood-versus-suburb mix, but within the same type the gap remains (neighborhoods: place 75.6 vs tract 68.2; suburbs: place 72.5 vs tract 70.5).
- The 200,000-adult ceiling that moves a place to tract is not sourced anywhere I found. Several tract picks for suburbs look structural, not a failure (Long Beach, Yonkers, Jersey City, Aurora are over the ceiling or in cities; NJ and PA townships such as Medford, Mount Laurel, Voorhees and Haverford may have no Census "place", and the code only uses county subdivisions for New England). That structural explanation is a hypothesis; I did not test it.

## D3: the four places

Stored record, current catalog:

| place | stored race / income / age / headline | what I could reproduce |
|---|---|---|
| Cold Spring Harbor (nyc) | 40.9 / 57.9 / (n/a here) / 61.2 | Current pick (place, 19,610 residents) gives old-formula race 32.9, income 79.2. No match. Stored pop 25+ is 1,861, tract-sized. |
| Ballard (seattle) | 45.9 / 83.3 / (n/a here) / 61.3 | Current pick (tract) gives old-formula race 63.4, income 91.0. No match. |
| Almaden Valley (sf) | 79.6 / 80.1 / 79.6 / 79.8 | Not reproducible: the 24 Oct pull got no data. Pop 25+ 3,160 (tract-sized). |
| Evergreen (sf) | 74.2 / 67.5 / 81.4 / 74.4 | Same: no data in the pull. Pop 25+ 4,198 (tract-sized). Denver also has an "Evergreen"; that one is consistent. |

All four were never rewritten to the new race formula (none appears in the old-values backup). For the two SF places I cannot confirm D3's claim ("matches no Census geography") from stored data alone; confirming it needs a Census pull, which I did not run. For Cold Spring Harbor and Ballard I reproduced it for the current pick only.

## D5: how the three terms combine, parameter by parameter

Headline = simple mean of whichever of race, income, age are present (equal thirds).

| parameter | what the code does | source found | published measure exists? |
|---|---|---|---|
| Equal weight of the three terms | mean of components | none | no standard; owner judgment |
| Race groups | B02001: six single-race groups plus "two or more" (7), entropy normalized by ln 7 | Census table definition; the multiracial double count was fixed 2026-10-24 | Census Bureau publishes a "Diversity Index" for the 2020 Census defined as the probability two random people differ in race/ethnicity, 0 to 1 (found only via secondary quotes; I did not reach the Bureau's blog page itself: census.gov/newsroom/blogs/random-samplings/2021/08/measuring-racial-ethnic-diversity-2020-census.html) |
| Hispanic origin | not included | Hispanic is an ethnicity separate from race; Hispanics can be of any race (Census Reporter, Pew); table B03002 crosses the two | yes, B03002. Evidence it matters: B02001 "some other race" is where many Hispanic respondents land; about 22.5 million Hispanics checked only that race in 2022 (Pew). In the catalog, mean "other race alone" share is 6.2% overall, 14.8% in LA, 8.8% in NYC; 242 of 1,451 places are at or above 10% and 98 at or above 20%. That is an indicator, not a Hispanic count |
| Income bins | B19001, 16 household income brackets of unequal width, normalized by the number of NON-EMPTY bins | none | the bins are Census-defined; the non-empty normalization has the same cliff the race fix removed. A published inequality measure exists (Gini, table B19083; tract availability not confirmed) but inequality is a different idea from mix |
| Age buckets | under 18, 18 to 64, 65 and over; entropy normalized by ln 3 | none for these cutpoints as a diversity target | Blau/Teachman-type variety indexes are the standard family for categorical mix (Harrison and Klein 2007, Academy of Management Review 32(4), found via secondary summaries only) |
| Guard: needs 2+ non-empty race or income groups | n >= 2 | none | not applicable |

Measured behavior across 1,470 places with all three terms:

- Race: mean 49.3, SD 16.1. Income: mean 84.6, SD 10.3. Age: mean 78.3, SD 13.8. Headline SD 8.0.
- Correlation with the headline: race 0.75, income 0.59, age 0.43. Race with income 0.35; age is slightly negative with both (-0.13).
- Age entropy peaks at equal thirds (100). A typical US mix of 22 / 62 / 17 scores about 85; a retirement community at 5 / 45 / 50 scores about 78; a young-family suburb at 30 / 62 / 8 scores about 78. So the term rewards a youth-prime-senior balance almost no real place has, and the top of its scale has no meaning. This is arithmetic, not a finding about people.
- Income fixed-16 test (using stored raw counts, consistent places only): 34.9% of places have fewer than 16 non-empty income bins; moving to fixed-16 normalization lowers the income term by a mean 1.7 points (5th percentile -7.8, worst -73.9, a place with 2 occupied bins). Headline change: mean -0.55, 20% of places move more than 1 point, 4% more than 3. This is a data-definition fix of the same kind as the race one.

## Options

### D3 (4 places on the old formula, but really 36)

- Option A, leave: costs nothing but leaves 36 places on a formula the other 1,434 no longer use, so within-metro comparisons are mixed. Not recommended.
- Option B, rescore from stored fields: not possible. The new race formula needs raw race counts that are not stored (the recompute script says so). Anything for these places needs fresh Census data.
- Option C, one Census re-pull for the 36 + 6 not-in-pull places (42, free API, same three queries as before), then run the existing offline recompute. This also resolves which geography the stored value came from. Recommended.

### D4 (geography)

- Option 1, fail loudly: if the preferred geography's lookup fails, raise (mark no data) instead of silently using the tract. Direct evidence: 8 of 1,451 places (0.6%) flipped place to tract in the pull. Movement per place when the alternative geography replaces the stored one: median 7.2 race points, up to 27.8. Plus the 19 that return nothing would show as "no data" until a retry succeeds. This keeps the current area-type rule (urban core uses tract; others use place under the ceiling) and removes the nondeterminism.
- Option 2, one fixed geography: all tract, or all place. All-tract is the only one that distinguishes neighborhoods (it would undo the 38 neighborhoods sharing city-wide values and the identical-value groups) but needs tract counts for the 887 places now on place or county-subdivision data, and tract counts are small (a few thousand people) and noisy. I cannot say how far those 887 would move: the tract counts are not stored. The only offline evidence is the 14 cases above (median 7.2 race points). Moving to all-place would erase neighborhoods in big cities, so it is not workable for urban cores.
- Option 3, hybrid with a recorded rule: use tract for anything typed neighborhood or located in a city over the ceiling, place for suburbs, and store the geography used (`geo_level`) in the record so the stored value can always be audited. This is Option 1 plus a stored field.
- Either way, store `geo_level` and the total population in the breakdown. Today the record cannot answer "what area was measured", which is itself a DPv2 gap.

### D5 (formula)

- Race: add Hispanic origin using B03002 (Hispanic plus non-Hispanic race groups). This changes what the pillar measures and is a large change in Hispanic-heavy metros (LA, NYC, Las Vegas, Miami, San Antonio). Impact cannot be sized offline; needs a Census pull of B03002 for 1,451 places.
- Index choice: the Census Bureau's own published measure is the Simpson/Blau type (probability two people differ), so that is the sourced choice; entropy is the incumbent. The earlier proposal doc compared both on race only (Spearman about 0.92 to 0.97 against today), so rank order is robust to the choice and the level changes. Scaling a Simpson index to 0 to 100 by dividing by 1 - 1/k is a judgment, not sourced.
- Income: smallest defensible change is fixed-16 normalization (above). Larger option: drop income from the diversity headline because it overlaps with status signal and housing (race-income correlation is only 0.35, so overlap is partial). Owner call.
- Age: either drop it from the headline, or keep it with the understanding that its scale tops out at equal thirds. No published source supports the cutpoints as a diversity target. Dropping it would change the headline for every place; effect not computed because raw age counts are not stored.
- Weights: equal thirds has no source. Race currently carries the most spread (correlation 0.75) simply because it varies the most.

## Who decides what

Data decides:
- That 36 places are still on the old race formula and need raw counts to update (arithmetic).
- That silent fallback exists and changes values (8 places shown directly).
- That the income term should not be normalized by non-empty bins if the race one was fixed (same defect, measurable).
- That age entropy's maximum is unreachable in practice (arithmetic).

Owner decides (judgment, data cannot settle):
- Fail loudly versus hybrid versus one fixed geography, including whether neighborhoods should ever show city-wide values.
- Whether the 200,000-adult ceiling stays, since it is unsourced.
- Whether Hispanic origin enters the pillar, and Simpson versus entropy.
- Whether income and age stay in a pillar called diversity, and whether equal thirds is acceptable.
- Whether the three zero-score places stay as zeros or become no data (this one is close to a bug; confirm how `total_score` treats confidence 0 first).

## Not verified

- Why the 24 Oct pull returned nothing for 19 places; why 8 place lookups failed.
- Whether the pre-2026-10-06 tract-boundary bug explains Ballard or others.
- That Somerton's pull label is an artifact.
- Tract availability of B19083.
- Census Bureau's Diversity Index blog page and the Harrison and Klein paper were not read in full; I relied on search summaries.

## Exact offline commands if approved

Nothing below has been run. Steps 1 and 3 touch only local files; step 2 calls the free Census API and was not run under this audit's rules, so it needs approval.

```bash
cd /Users/adamwright/Dev/home-fit && git fetch origin && git status --short data/ | head
```

1. Backup before anything is written (rollback):

```bash
cd /Users/adamwright/Dev/home-fit && mkdir -p data/backups_diversity_d3_2026-10-27 && cp data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl data/backups_diversity_d3_2026-10-27/
```

2. (Needs Census calls, approval required.) Re-pull raw counts for the 42 listed places only (36 old-formula + 6 not in pull) and record `geo_level`, total population, and the failure reason per place. A small pull script writing `data/backups_diversity_d3_2026-10-27/raw_race_counts_42.jsonl` does not exist yet; I would write it modeled on the 24 Oct pull and check its labels against `get_diversity_data` before use.

3. Dry-run the existing recompute against the new raw file, then write only if the skip counts are zero:

```bash
cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/recompute_diversity_race_offline.py --raw data/backups_diversity_d3_2026-10-27/raw_race_counts_42.jsonl
```

```bash
cd /Users/adamwright/Dev/home-fit && PYTHONPATH=. python3 scripts/catalog/recompute_diversity_race_offline.py --raw data/backups_diversity_d3_2026-10-27/raw_race_counts_42.jsonl --write --backup-dir data/backups_diversity_d3_2026-10-27
```

Caveat: that script skips places whose OLD formula does not reproduce the stored value, which is exactly the 17 mismatches. Those need either a script change (accept the fresh pull as the new truth and overwrite all three terms) or a decision under D4 first. I would not change that logic without approval.

## Staleness note (added 2026-10-27, after commit b73836b)

Every geography count in this audit (place 833, tract 564, county subdivision 54; the 17, 19 and 6 in the D4 table; the 38 neighborhoods on place data) comes from the raw pull of 2026-10-24, which ran under the OLD rule: urban_core places always used the tract. Commit b73836b (on origin/main, 2026-10-27) removed that rule, so geography now depends only on the 200,000-adult ceiling. In the pull, 97 places were typed urban_core and all took the tract. Under the new code some of them would try the place first, so the place/tract split and the per-metro counts can change. Which ones is not known until the pull is re-run. The "area type" column used in the tables is also the pre-change stored type, which the area type session is redefining. The stored-score reproduction (1,434 consistent places) is not affected, because it compared stored values with the pull, not with the new code. The brief for the 42-place pull uses the new size-ceiling-only rule.

## Update 2026-10-28: the 42-place recompute (from the Census cache pull)

Source: `analysis/diversity_42_recompute.jsonl`, built by `scripts/catalog/recompute_diversity_42_offline.py` from the state-level ACS pull in `data/census_pull_2026-10-28/` (267 calls, 0 failures; 5 more files for the Delaware test; later 52 calls for owner and renter counts for housing). Geography follows the current code (place unless over 200,000 adults, then tract; area type is not an input). Nothing was written to the catalog. I summarized the file; I did not re-derive its numbers.

- 39 of 42 recomputed; 3 have no data: Maspeth, Southport and Radnor (place and tract both unavailable). Their stored 0.0 with confidence 0 should be "no data", as the fail-loud rule says. This confirms the fabricated-0 finding above for all three.
- Geography used: 16 tract, 14 incorporated place, 9 CDP. Denver's Franktown, Idledale and Sedalia are CDPs with too few groups for a race term, so their headline is unchanged (97.6, 62.3, 75.0).
- Headline change across the 39 (Denver's three count as 0): mean -3.0, median -2.6, range -16.6 to +5.2. For the 36 that have a race term the race entropy falls by a similar amount to the whole catalog (the new formula normalizes by seven groups), except where the geography changed.
- Largest moves: Almaden Valley 79.8 to 63.2 (-16.6), Evergreen (SF) 74.4 to 58.5 (-15.9), Southlake 74.5 to 59.5 (-15.0), Benson 87.4 to 78.1 (-9.3), Tolleson 89.0 to 83.6 (-5.4). Up: Carrollton +5.2, Ballard +3.2, Cold Spring Harbor +2.2, Bayview +1.3.

Geography check: for 31 of the 39 the recomputed 25+ population equals the stored `population_25_plus` exactly, so the stored value and the recompute use the same geography and the change is the formula only (this includes Croton-on-Hudson, Blue Bell, Doylestown, Sun Lakes, Apex, Foster City, Fremont, Benson and Rancho Murieta, which my earlier ratio test had flagged as place-sized with the pull showing tract; the cache pull applies the ceiling properly, so that earlier flip was an artifact of the 24 Oct pull, not a lookup failure). Somerton also matches (3,882) as a tract, confirming it was a pull artifact. Eight places do not match, so their stored values came from a different geography or tract:

| place | stored 25+ | recomputed 25+ | geography now |
|---|---|---|---|
| Carrollton | 4,465 | 94,757 | place |
| Southlake | 3,476 | 19,318 | place |
| Seabrook | 4,661 | 9,014 | place |
| Spring | 3,447 | 41,481 | place |
| Cold Spring Harbor | 1,861 | 14,847 | place |
| Ballard | 3,456 | 2,806 | tract |
| Almaden Valley | 3,160 | 2,761 | tract |
| Evergreen (SF) | 4,198 | 2,372 | tract |

The first five were scored from a tract and now resolve to the place (the original place lookup probably failed, the D4 mechanism). The last three are tract to a different tract; the size of their moves (Almaden -16.6, Evergreen -15.9) is mostly that tract difference, not the formula. The 2020-tract fix of 2026-10-06 is one possible cause; I have not tested it.

What this changes in the D3 and D4 conclusions above:
- D4's "8 places flipped place to tract" is retracted: with the ceiling applied they match their stored (place) geography. The remaining real geography discrepancies in this set are the eight in the table.
- D3's four places: Cold Spring Harbor and the two SF places and Ballard are now explained as geography differences, and all four have a recomputed value to compare. Whether to rewrite them still depends on which geography the owner wants (the D4 decision).
- Before any write: owner decision on D4 (fail loudly versus one rule), then run the existing recompute script against this cache (not yet done).

## Decision 2026-10-28 (owner): D4 fail loudly

Keep the size-ceiling rule (place unless over 200,000 adults, then tract; area type is not an input). If the place lookup fails or returns an error, the pillar records no data (and is retried) instead of silently using the tract. Store `geo_level` and the total population with the diversity record so the measured area is always auditable. Not yet implemented: no code or catalog change has been made. Still open: the unsourced 200,000 ceiling, and D5 (Hispanic origin, income and age terms).
