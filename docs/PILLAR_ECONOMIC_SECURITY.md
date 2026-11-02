# Pillar Deep-Dive: Economic Security

How `pillars/economic_security.py` scores a location today.

## What it measures — and what it deliberately does NOT
Economic security = **the job-market opportunity a place's residents can reach** — plus the
**quality** of that market. It is deliberately NOT:
- the metro a place is administratively filed under (commute-sheds cross CBSA lines), nor
- the current residents' outcomes (income/poverty). *Living in Harlem doesn't block your
  access to Manhattan's jobs.* Resident affluence is a **status_signal** concern, not this one.

The litmus test that settled the design: "does living in Harlem block your economic security?"
No — so the pillar must reward Harlem's excellent job access, not penalize its residents'
circumstances. (Full reasoning in the economic-security-design memory.)

## Two terms
```
economic_security = 0.55 · job_access  +  0.45 · market_quality
```
(falls back to `market_quality` alone where the LODES grid has no coverage)

### Term 1 — job_access (reachable market, the fix)
`data_sources/job_accessibility.py` — a gravity model over the LODES H8 workplace-job grid:
```
access(lat,lon) = Σ_hex  workplace_jobs(hex) · exp(−dist_km / 20)   over hexes < 75 km
score = logscale(access) → 0–100        (LOG_LO=2.5, LOG_HI=6.6)
```
- Near a big job center → high; isolated town → low; **anchored to the *reachable* market,
  not the administrative one.**
- Validated: Harlem 99, Midtown 100, Scarsdale 91, **Greenwich 88 (anchors to NYC, not its
  Bridgeport-Stamford CBSA)**, exurban Palmdale 72, isolated Montauk 46.
- This single term does all the *legitimate* differentiation: metro vs isolated, and
  within-metro proximity to jobs. It does NOT use resident outcomes.

### Term 2 — market_quality (existing components)
The pre-existing CBSA labor-market score: Density / Mobility / Ecosystem / Resilience built
from ACS, BDS, Census County Business Patterns and the BLS OEWS wage file (employment ratio, wages,
job growth, establishment churn, industry diversity), normalized against a **national,
population-weighted baseline** over all US metro and micro areas (changed 2026-10-24; it was
Census Division × area-type cells with a median of 8 reference areas). Job growth and market size
come from County Business Patterns 2022 to 2023 because BLS QCEW blocks scripted access; that
source covers private payroll jobs only. Wages are available for metro areas only. The baseline is
sourced and reproducible (`scripts/baselines/build_economic_national_baseline.py`) but not validated
against an outcome (`analysis/economic_national_baseline_estimate_2026-10-24.md`): treat it as a
judgment call. Captures how *good* the reachable market is (wages, growth, diversity), not its size.

## Why the blend, and why uniformity is correct
Before this, the pillar was market_quality alone at CBSA level → **47% of NYC places shared
71.5, 83% of LA shared 58.8**, and Greenwich scored 46 (Bridgeport's market, not NYC's).

Adding job_access:
- Fixes wrong-CBSA anchoring (Greenwich 46 → 69; same for Cos Cob, Old Greenwich, Norwalk).
- Restores differentiation (NYC 8 → 78 distinct values, LA 4 → 51).
- **Keeps metro neighbors similar on purpose.** Harlem ≈ Scarsdale ≈ Compton on economic
  security because they share the same reachable market — that's *correct*. The difference
  between Compton and Beverly Hills is resident outcomes, which belong in status_signal. A
  tight within-metro spread (esp. LA, a single sprawling market) is honest, not a bug.

## Coverage & data
- LODES parquet `data/lodes_h8_jobs_national.parquet` (H3 res-8, LODES 2022, all states, 794,259 cells,
  142.8 million jobs). Updated 2026-11-02: the older text here named a four-state file
  (`lodes_h8_commuter.parquet`, now used only by community safety). A point counts as covered when a cell
  lies within 15 km; every catalog place has `job_access` (0 of 1,476 are null). Where the grid does not
  cover a point, `job_access` is `None` and the pillar uses market_quality only, flagged degraded.

## Live vs catalog
- Live: `get_economic_security_score` computes market_quality fresh, fetches job_access from
  the parquet, blends, and exposes `job_access_score` + `market_quality_score` in the summary.
- Catalog: blended offline by `scripts/apply_econ_job_access.py` (0.55·job_access + 0.45·
  *stored* market_quality). Because the stored market_quality is older than a live recompute,
  catalog and live can differ a few points (Greenwich catalog 69 vs live 72.7) — ordinary
  staleness, same blend formula. See LIVE_SCORER_VS_EXPLORER.

## Known residual
The market_quality half is still CBSA-anchored, so Greenwich's *quality* term is still
Bridgeport's. Minor now that job_access dominates the blend; revisit only if it surfaces.

## Where it feeds
`total_score` (one of 14 pillars) and the longevity index (linear factor). Cascade handled by
the apply script.

---

## DPv2 spec sheet and audit (2026-11-02, Level 0 until signed off)

Everything below was computed offline from the stored catalog (1,476 places, 21 metro files, `*.composites_recomputed.jsonl`)
and the local jobs grid. No API call, no Overpass read, no download. Scripts are in the session scratchpad, not the repo.
The pin-shift and weight tests below were run by the builder and are not the independent Level 2 check.

```
Pillar: economic_opportunity (public name: economic security)
Level: 1, signed off by the owner 2026-11-02 "yes for now". TODOs accepted: all unsourced numbers (blend, decay, cutoff,
  component and sub-weights, growth floor, remote reweight, fallback thresholds); weak frame evidence; metro-level market
  quality (Palo Alto and Greenwich); double-counted industry diversity left as is; opt-in overlay path's area-bucket use
  (cell baselines not verified); gravity not on the place context. Level 2 in progress; brief:
  `docs/ECONOMIC_SECURITY_LEVEL2_BRIEF.md`.
Construct (one sentence): Opportunity: the size and quality of the job market a resident can reach by commuting,
  not the metro the place is filed under and not the residents' own outcomes.
Reference frame: absolute (no peer norm). Job access is on a fixed log scale (0 at 10^2.5, 100 at 10^6.6 distance-decayed
  jobs). Market quality is scored against a national population-weighted baseline of all US metro and micro areas.
  Evidence for the frame: tier 1 but indirect, and weak. Moretti (summaries only, full papers not read): large labor markets
  attract workers and give more potential employers, and commute time sharply cuts the estimated gain from a big market.
  Tier 2 (migration or price proxy that prices market potential): none found. Tier 3: none sought. No study found that
  tests a market-potential score as a migration or price predictor. Relative-income studies (Luttmer, Deaton and Stone)
  are about happiness, not job access, and do not bear on this frame. Status: frame is a design choice with indirect support.
Measurement area: other. Job access is a distance-decayed sum over all jobs within 75 km of the pin (H3 cells of about
  0.46 km edge). Market quality is one county or metro (CBSA) value for the whole place.
  Reason: commute-shed reach is the construct. The metro value is a data limit, not a choice (it is the finest geography for
  the wage, growth and business-dynamics inputs), and it makes 45 percent of the score constant across a metro.
Place context inputs used (fields) and remaining area-type uses (with reason): reads area_type and density from the context
  but only for the data-quality completeness check and output metadata. The default scoring path does not key on the label:
  `_area_bucket` and `division` are passed to the normalizer, which ignores them (national baseline). One remaining use: the
  opt-in job-category overlay path passes division and area bucket to the older cell baselines (whether those cells are still
  populated since the 2026-10-24 baseline change is NOT verified). Gravity is computed in the pillar from the local jobs grid;
  it is not on the context (single consumer; see gap 8).
Inputs and data sources (with vintage): LODES 2022 workplace jobs (H3 res 8, all states); ACS 2022 DP03 and B01001 at CBSA
  (county fallback); Census Business Dynamics Statistics (vintage not checked); County Business Patterns 2022 and 2023
  (private payroll jobs only); BLS OEWS metro wages (25th and 75th percentile; metro areas only; vintage not checked);
  national baseline data/economic_baselines.json built 2026-10-24.
Parameters:
  name | value | source | plausible range | sensitivity result (final score, all 1,476 places)
  blend job access / market quality | 0.55 / 0.45 | unsourced (TODO) | 0.40 to 0.70 job | job 0.40 or 0.70: median change 3.1, p95 5.4, Spearman 0.97; 0.30 or 0.80: median 5.1, p95 8.9, Spearman 0.92
  commute decay D0 | 20 km exponential | unsourced (see below) | 15 to 30 km | 15: median 2 (p95 3.4); 30: median 2 (p95 4.0); 10: median 5.0 (p95 9.0); 40: median 3.3
  reach cutoff | 75 km | unsourced (TODO) | 50 to 100 km | 50: median 0.2 (p95 1.9, max 15.0); 100: median 0.0 (p95 0.2)
  log scale low end | 2.5 | data-derived (small local economy), no source | 2.0 to 3.5 | median change 1.0 to 3.0, Spearman at least 0.993
  log scale high end | 6.6 | data-derived: NYC core, catalog max 6.63 | 6.0 to 7.0 | 6.0: median 7.3 and 38 percent of places clip at 100; 7.0: median 4.1; Spearman 0.95 to 0.999
  component weights density / mobility / ecosystem / resilience | 0.40 / 0.15 / 0.20 / 0.25 | unsourced (TODO) | each plus or minus 0.10 | 2,000 random draws: median change 0.35, p95 1.25, max 3.6; equal weights: median 0.8, max 2.0; drop density entirely: median 2.5, max 6.5, Spearman 0.88
  sub-metric weights inside each component | density 0.25/0.30/0.25/0.20; mobility 0.40/0.35/0.25; ecosystem 0.70/0.30; resilience 0.60/0.40 | unsourced (TODO) | unknown | not run
  anchor growth floor | growth set to at least 40 when anchored balance score is above 75 | unsourced (TODO) | unknown | not run
  remote-only reweight | ecosystem 0.444, resilience 0.556 | unsourced (TODO) | unknown | opt-in path, not run
  fallback normalization thresholds | hard-coded bands in `_fallback_normalize` | unsourced (TODO) | unknown | 0 catalog places use them
  Decay source (asked 2026-11-02): no published US decay parameter for this model was found in two standard searches. Found,
  from search summaries only: BTS 2003 Omnibus Household Survey, average one-way commute about 15.3 miles (24.6 km), a tier 3
  survey, 23 years old; literature disagrees on exponential versus power-law decay (a Chicago LODES study reports a power-law
  exponent near 0.53; a mobile-phone study finds power law slightly better; a Danish study finds neither fits). The code comment
  "mean metro commute 25-30 km by car" has no source. A real fit needs LODES origin-destination files (a download, not done).
  Until then D0 = 20 km is a TODO with the range 15 to 30 km, inside which scores move about 2 points at the median.
Effective weights inside market quality (computed from the code): industry diversity 0.29 (counted in both ecosystem and
  resilience), establishments per 1,000 residents 0.16 (density and ecosystem), scale 0.12, employment ratio 0.10, anchored
  balance 0.10, wage 25th percentile 0.08, job growth 0.06, establishment entry 0.0525, wage 75th percentile 0.0375.
  Times 0.45, industry diversity alone is 13 percent of the final score. Unemployment rate is normalized but never used.
Shared inputs with other pillars: status_signal reads white_collar_pct, which main.py injects into this pillar's breakdown;
  happiness_index, the longevity index and total_score read the score. Overlap test (builder run 2026-11-02, stored
  catalog, 1,476 places, Spearman): status_signal 0.16 (within metro 0.22), so no double counting; housing_value -0.48
  (within metro -0.50), a trade-off (job-rich places cost more), not a shared input; public transit 0.53 (job access alone
  0.69), a shared driver (centrality), not a shared input; amenities 0.42, healthcare 0.50, air travel 0.42. Independent
  rerun is V5 in the Level 2 brief.
Pin-shift sensitivity (shift distance, median and p95 score change; builder run 2026-11-02, offline, 1,476 places, worst of
  four directions per place, job-access term only): 500 m: median 0.07, p95 0.12, max 0.38. 1 km: 0.15, 0.23, 0.55.
  2 km: 0.30, 0.47, 1.33. Not tested: a shift across a CBSA line, where the market-quality half changes (see gap 1).
Independent validation source and result (2026-11-02, run by a separate Haiku agent from `docs/ECONOMIC_SECURITY_LEVEL2_BRIEF.md`;
  criteria fixed before the comparison; full catalog, n=1,476, all matched to a block group): EPA Smart Location Database v3,
  field D5AR (jobs within 45 minutes by car, time-decay weighted, network travel time; confirmed from the geodatabase
  catalog), against our distance-decayed gravity. Spearman of log10 values 0.909 (need 0.80) PASS; within metro 0.930 (need
  0.60) PASS; median per-metro Spearman 0.939 over 20 metros (need 0.60) PASS, lowest SF 0.716 and Denver 0.819; 33 places
  (2.24 percent) differ by more than 30 percentile points (need at most 5 percent) PASS, 18 of them in the SF metro. Limits:
  SLD is built from LODES jobs too, so this tests the travel-time method (network drive time against straight-line decay),
  not the jobs data; D5AR is probably 2017-era jobs against our LODES 2022 (inferred, not confirmed); pin accuracy not
  checked; the SF concentration of misses is not explained (a pass on the national cap does not catch a weak metro; a
  per-metro floor is a criterion change for you to decide). This validates the job-access half only; market quality has no
  independent validation (no outcome-matched source found). Files: `analysis/economic_level2_results_V1_2026-11-02.md`.
Checks V2 to V5 rerun independently (same date, separate agent, `analysis/economic_level2_results_2026-11-02.md`): all-places
  PASS; 1 km pin shift median 0.10, p95 0.20, max 0.70 (limits 1.0 and 3.0) PASS; launch pairs 6 of 7 PASS, Palo Alto vs
  East Palo Alto FAIL as expected (7.6, open limit); overlap with status_signal 0.16 and housing_value -0.48 PASS.
All-places check (date, n, summary): 2026-11-02, n=1,476. Score median 74.1, 5th to 95th percentile 62.3 to 83.2, range
  36.6 to 85.7. No place at 5 or below or at 95 or above; 2.1 percent of places have job access of 100. By area type (median,
  10th to 90th): urban core 82.4 (79.4 to 83.4, n=14); urban residential 80.8 (73.4 to 83.7); suburban 74.7 (68.4 to 80.5);
  exurban 71.7 (65.1 to 76.7); rural 68.4 (58.0 to 74.4). Within a metro the standard deviation is 1.8 to 4.4 points (Las Vegas 7.1).
  Market quality takes 25 distinct values across 1,476 places (one or two per metro). Stored blend matches 0.55/0.45 for all places.
Fail-loud conditions (what is rejected, what is flagged): flagged degraded: grid does not cover the point or errors (scored on
  market quality alone), baseline fallback used. Changed 2026-11-02 (option A, gap 4): unresolved geography, a jobs-grid read
  error, or no scorable market metric now raises `EconomicDataUnavailable`, so the pillar shows as no data, its weight is
  redistributed, and it is retried. Before this, unresolved geography returned 0.0 and a grid error silently scored market
  quality alone. Tests: `tests/test_economic_fail_loud.py`. The unused `division` and `area_bucket` arguments were removed
  from the normalizer (gap 7); scoring values are unchanged.
Launch check pairs (should differ / should be similar) and result (stored scores, 2026-11-02):
  should differ: Midtown Manhattan 83.7 vs Galt CA 65.8 (pass); Harlem 83.2 vs Spring Branch TX (San Antonio) 57.8 (pass);
  Downtown Las Vegas 61.5 vs Mesquite NV 37.4 (pass). Intended similarity by design: Harlem 83.2, Park Slope 83.2, Compton 82.7
  vs Beverly Hills 83.1 (pass). FAIL: Palo Alto 68.5 vs East Palo Alto 76.1, adjacent, same job access (84.9 vs 85.2), 7.6 apart
  only because Palo Alto is filed under the San Jose metro (market quality 48.5) and East Palo Alto under San Francisco (65.1).
  Greenwich 73.3 vs Scarsdale 78.9 is the same effect (market quality 55.8 vs 63.7).
Known data limits: market quality is metro-level; private payroll jobs only for growth and scale; OEWS wages are metro-only;
  LODES excludes some self-employed and federal jobs (stated from general knowledge, not checked here); straight-line, not
  road, distance; catalog market quality was stored earlier than a live recompute, so live and catalog can differ a few points
  (not re-measured).
Last re-validated: 2026-11-02 (all-places, pin shift, launch pairs, overlap, independent validation of job access).
Proposed level: 2, for owner sign-off (not yet signed). Accepted-TODO list to carry: Level 1 list above, plus market quality has
  no independent validation, metro-line pin shift untested, Palo Alto pair open, SLD vintage gap, SF weak-metro agreement.
  Not met for Level 3: the unsourced parameters.
```

### Audit gap table (no code changed)

Not re-surfaced: the FEMA flood and job-grid coverage fixes of 2026-10-22 to 24.

| # | Gap | Evidence | Recommended fix | Expected score impact |
|---|---|---|---|---|
| 1 | Market quality is a metro constant. 45 percent of the score has no within-metro variation, and a CBSA line splits neighbors | 25 values over 1,476 places; Palo Alto 68.5 vs East Palo Alto 76.1 (3 km apart); Greenwich 73.3 | Weight the metro quality values by where the reachable jobs are (needs a cell-to-county crosswalk, a download), so Palo Alto and Greenwich anchor to the metro they commute into | About 30 places in four secondary metros (Bridgeport 13, San Jose 15, Oxnard 1, Bremerton 1) plus 3 with no metro name move; at most +7.5 (Palo Alto toward SF) and +3.6 (Greenwich toward NYC) by arithmetic, others none. Not computed place by place |
| 2 | Weights 0.40/0.15/0.20/0.25, sub-weights, 0.55/0.45, growth floor, remote reweight have no source | One search for a published composite with these dimensions found none (Baltimore opportunity mapping used stakeholder weights; Milwaukee used equal rank) | Mark all as TODO with ranges (done above). Do not change values without a source | None. Sensitivity is low: weights plus or minus 0.10 move the median place 0.35 |
| 3 | Industry diversity is double counted (0.29 of market quality, 13 percent of final) and rewards diversified over specialized markets | San Jose has wage 25th and 75th percentile scores of 100 and 100 yet market quality 48.5, below San Antonio 49.6; Boston diversity score 12 | Do not change yet: no evidence in hand that resilience from diversification beats cluster strength (Moretti points the other way on size). Run a targeted evidence search first | Counting each metric once (tested) moves the median place 2.9, p95 3.7, max 4.4, Spearman 0.90: NYC +6.6, Boston +6.8, LA -8.0, Charlotte -9.3 in market quality. A reshuffle with no evidence for it |
| 4 | Fail-loud (principle 9): unresolved geography returns a score of 0.0 with an empty breakdown; `final_score or 0.0` turns a missing value into 0 | Code path; 0 catalog places affected (no null, no degraded, no fallback in the 1,476) | Return no data when geography is unresolved; treat a job-access read error as no data (retry) rather than a market-only score that changes the construct | Catalog 0. Live only |
| 5 | Decay D0 = 20 km and cutoff 75 km unsourced | See parameter table | Fit from LODES origin-destination files (download, needs your OK) or keep as TODO with range 15 to 30 km | If D0 moved to 15 or 30: median 2 points, Spearman at least 0.989 |
| 6 | Log scale high end 6.6 is set by NYC core; it is the most sensitive scale constant | Lowering to 6.0 clips 38 percent of places at 100 | Record as data-derived (catalog and grid maximum 6.63). Do not move | None |
| 7 | Dead and stale area-type arguments; opt-in overlay path still on older cell baselines | `_area_bucket`, `division` ignored by the national normalizer; overlay path unverified | Remove the dead arguments (no score change). Overlay path: check cell coverage before deciding | Default 0. Overlay: unknown |
| 8 | Gravity jobs not on the place context | Computed in the pillar; context holds only `jobs_1km` | Leave as is: one consumer, and live and catalog already use the same helper. Add to context only if a second pillar needs it (principle 15) | None |
| 9 | Employment-to-population ratio (0.10 of market quality) is a resident-outcome measure inside an opportunity construct; unemployment rate computed but unused | Code | Record in the spec as a judgment; no change | None |
| 10 | Doc was stale (four-state grid, "validated" numbers from the old model) | Doc vs code | Fixed above | None |
| 11 | Overlap with status_signal, housing_value, happiness not tested | Wage and earnings inputs | Level 2 overlap check | Unknown |

### Options

- **A. Conformance only (recommended).** Doc and spec sheet as above, fail-loud fix (gap 4), remove dead arguments (gap 7), tests for both. Catalog scores do not change (0 of 1,476 hit the new paths), so the recompute is a check that the new files equal the old. Gets Level 1 now, and Level 2 after the checks. Weights stay TODOs with ranges.
- **B. A plus the metro-quality fix (gap 1).** Fixes the only failed launch pair and the Greenwich residual. Needs a download of a cell-to-county crosswalk and a design choice on how to weight metros. Changes about 33 catalog places.
- **C. A plus recount of duplicated metrics (gap 3).** Not recommended: changes every place by up to 4.4 with no evidence for the new weights.

**Recommendation: A now, then B as a separate step once you approve a download.** What I need from you: (1) approve A; (2) say whether I may download LODES origin-destination files to fit the decay (size not checked; I would ask again with the exact file list) and a cell-to-county crosswalk for B; (3) confirm independent validation may use a downloaded EPA Smart Location Database file. Nothing is committed or pushed.
