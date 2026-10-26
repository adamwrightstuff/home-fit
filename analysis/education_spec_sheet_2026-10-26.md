# Education pillar spec sheet (DPv2 draft, 2026-10-26)

Owner decisions of 2026-10-26 are tier 3 (owner judgment), recorded as such. Items marked TODO have no source yet.

```
Pillar: quality_education
Construct (one sentence): Quality of the school a child at this address would be assigned to (zoned school, else the nearest rated
  schools of the home district; lottery levels show the district pool average), measured by statewide test-score percentile.
  [Owner decision 2026-10-26]
Reference frame: area-type norm replaced by state norm: statewide percentile, comparable only inside a state. [Owner decision, tier 3]
  Evidence for the frame: capitalization studies use standardized scores (Black 1999 and later work), tier 2, not re-verified.
Measurement area: pin + Census district polygon + zone polygon; nearest 3 within a radius when no zone.
  Reason: the assigned school is what a resident means by "my school"; radii 1.5/2/3 mi by area type are a judgment (TODO source).
Inputs and data sources (with vintage): SchoolDigger statewide percentile snapshot (18 states, fetched 2026-10-16, yearly);
  Census TIGER school districts; district zone maps (2018 to 2026-27); NCES 2015-16 attendance survey as fallback (77.7% of zoned levels).
Parameters:
  education weight | 7.69% (equal 1/13) | owner decision "everyone equally", confirmed 2026-10-26 after the P4 research pass; no study gives a weight | test range 0 to 2 times the current weight (judgment) | weight 0 moves totals a mean 1.6 (approximate). Survey evidence (NAR 2019, secondhand) says importance depends on having children; handled by the user priority panel, no "has children" input (later product decision)
  level weights (elementary, middle, high) | equal | judgment; research is mixed | doubling one level moves scores a mean 2.5 (p95 7.3 to 7.9)
  radius ratio 2.1 / 3.2 / 3.6 mi | sourced (NHTS 2017, PBIC brief) | n/a | n/a
  base radii 1.5 / 2 / 3 mi, nearest-3, caps, pool average | judgment, no source found | TODO | act only where no zone map applies: 366 of 1,476 places
  early-education points | 0 | no source for a size | n/a | access recorded as data only
  radii 1.5 / 2 / 3 mi | judgment | none | TODO | pin-shift median 5.8 pts
  nearest-3, 3 mi cap, 15 mi district-far, pool average, equal level weights | judgment | none | TODO | not tested
Shared inputs with other pillars: feeds the longevity index (weight 3.0, sourced to years of schooling, a different construct);
  overlap with housing value not tested.
Pin-shift sensitivity: 0.5 mi, largest of four directions: median 5.8, p90 32.0, p95 42.9 (2026-10-25). Owner decision: show as a
  confidence flag, no score change. TODO build the flag and its threshold.
Independent validation source and result: EDFacts proficiency 2017-18, Spearman 0.66 to 0.92 within districts (ratings only).
All-places check: 2026-10-25, n=1,476, early-education rebuild and no-data fix, check_education passes for 21 metros.
Fail-loud conditions: no rated school at any level = no data, degraded; failed early-education lookup = early_ed_missing;
  outside private server coverage = early_ed_missing. Open: live scorer main.py 2361 and 4046 still coerce to 0.0.
Launch check pairs: 6 approved 2026-10-26, all pass (3 differ, 3 match); see analysis/education_launch_pairs_2026-10-26.md.
  Mid-range pair (Babylon vs Tarrytown) added by the owner: FAIL (64.7 vs 49.4), cause is one-level scoring at Babylon; owner decision 2026-10-26: keep scoring from fewer levels, flagged degraded; recorded as a known limit.
Known data limits: 77.7% of zoned levels from 2015-16 survey; Austin zones stale; 541 places no early-education data; lottery
  districts (SF, NYC middle/high) score as a district pool, so every address in them gets nearly the same number.
Last re-validated: 2026-10-26 (this audit).
```

## Work this implies, in order

1. Fix the live scorer so a missing score stays no data (no catalog change).
2. Update `docs/PILLAR_QUALITY_EDUCATION.md` to match (bonus is data only, construct sentence, frame statement).
3. Build the pin-sensitivity confidence flag (needs a threshold; compute per place from stored shifts, then agree the cutoff).
4. Flag zone vintage (2015-16 levels) and thin levels in the degraded reasons.
5. Name launch-check pairs and record the result.
6. Source or range for weight and radii: each a research task before any change.
