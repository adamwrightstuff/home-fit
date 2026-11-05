# Status signal: Affluent and Elite frame test (criteria fixed before running)

Written 2026-11-04. Read-only analysis on the stored catalog (pooled inputs for single-tract places, as in docs/STATUS_SIGNAL.md section 9). No label, score or catalog is changed by this test. DPv2 frame evidence order: published study, then price or migration proxy, then survey. No published study sets an "affluent" line, so this test selects among candidate rules using facts the rules do not use.

## Candidates (only the Affluent and Elite step changes; Struggling and Working Class are untouched)
- A (current): Affluent if income >= metro p80; Elite if income >= metro p90 and home value >= metro p90.
- B (home-value route): A, plus Affluent if home value >= metro p90 and income >= the national median ($75,149). Elite as in A.
- C (national ladder): Affluent if income >= national p80 ($109,440); Elite if income >= national p90 ($134,643) and home value >= national p90 ($659,200). Cutoffs are the stored `class_cuts.all`.

## Targets that no candidate uses
Stored mean household income (pooled-free, stored value) and median gross rent (pooled where the place reads a single tract). Home value is a candidate input for B and C, so it is not a target.

## Pass criteria (a candidate replaces A only if all hold)
1. Spearman between the class ladder (0 to 4) and mean household income improves on A by at least 0.02, and likewise for median gross rent.
2. The median mean household income rises strictly across the five classes.
3. No more than 15% of places change class, and no place moves more than one class.
4. Reported only: Beverly Hills, Brookline MA, Greenwood Village CO, Newton MA, Palo Alto, and the count of places moving by metro.
The 0.02 and 15% limits are judgment fixed here before results, not published standards. If no candidate passes, A stays and the Beverly Hills result is recorded as a known limit of a median-income label.

## Results
Run 2026-11-04 on 1,469 classified places (pooled inputs for single-tract places).

| Candidate | Places changing class | Largest move | Spearman with mean income / rent (A: 0.735 / 0.504) | Median mean income rises strictly? | Verdict |
|---|---|---|---|---|---|
| A current | 0 | 0 | 0.735 / 0.504 | yes | baseline |
| B home-value route | 78 (5.3%), all Middle to Affluent | 1 class | 0.752 / 0.523 (+0.017 / +0.019) | yes | FAIL criterion 1 by 0.003 and 0.001 |
| C national ladder | 375 (25.5%) | 2 classes | 0.850 / 0.674 (+0.115 / +0.170) | yes | FAIL criterion 3 (limits 15% and one class) |

Reported only: Beverly Hills, Brookline and Greenwood Village move Middle Class to Affluent under B; under C Beverly Hills and Brookline go to Affluent and Greenwood Village to Elite, Palo Alto goes Affluent to Elite. B moves places mostly in NYC (11), Philadelphia (9), Austin and Phoenix (8 each). C moves NYC 86, SF 83, Boston 48, LA 31, Denver 25.

Result: no candidate passes, so A stays. Two limits on reading this. B misses the improvement limit by under 0.003, so the criterion is the deciding factor, not the data; I did not relax it. C's gain is partly built in: the targets (mean income, rent) sit on the national scale, so a national cutoff ordering matches them better than a metro rank by construction, and the test cannot say whether a metro-relative or national frame is what people mean. That question has no published study behind it and stays an owner definition.
Beverly Hills as Middle Class is recorded as a known limit of a median-income label with a metro rank.

## Validation of the home-value route B (criteria fixed before running, 2026-11-05)
Question: are the places B would move from Middle Class to Affluent (set M) really Affluent-like? Read-only, stored catalog, pooled inputs where the place reads a single tract. Nothing changes.

Method: compare M with the places A already calls Affluent (set Aff) and the places A calls Middle Class and B leaves there (set Mid), on measures neither rule uses: (1) share of households at $150,000 or more (last two of the 16 stored income brackets; $150,000 is about twice the national median, the Pew Research Center upper-income line for middle-income households), (2) graduate degree share of adults 25 and over, (3) white-collar share of jobs, (4) stored mean household income.

Pass criteria (no tuned limits; only the nearest-class test):
1. On every one of the four measures the median of M is closer to the median of Aff than to the median of Mid.
2. On the share of households at $150,000 or more, the median of M is inside the Aff interquartile range.
3. No more than a quarter of M sits below the Mid median on the $150,000 share (reported as a count; the quarter is a judgment, flagged as such).
Reported only: the same table for Beverly Hills, Brookline and Greenwood Village; M by metro. If B passes all three it is a validated candidate for the owner to choose; it is still the owner's call whether to adopt it. If it fails, A stays.

### Validation results (run 2026-11-05; 78 places in M, 240 in Aff, 880 in Mid)
| Measure (median) | M | Aff | Mid | M closer to |
|---|---|---|---|---|
| Households at $150,000 or more (%) | 34.6 | 50.1 | 24.0 | Mid (15.5 below Aff, 10.6 above Mid) |
| Graduate degree share (%) | 30.4 | 31.4 | 16.2 | Aff |
| White-collar share (%) | 52.7 | 49.5 | 37.1 | Aff |
| Mean household income ($) | 160,037 | 196,358 | 112,110 | Aff |

1. FAIL: M is closer to Aff on three measures and closer to Mid on the $150,000 share.
2. FAIL: the M median on the $150,000 share (34.6) is below the Aff interquartile range (41.9 to 57.2).
3. PASS: 12 of 78 (15.4%) of M sit below the Mid median on the $150,000 share, under the quarter limit.
Reported only: Beverly Hills (42.7%), Brookline (45.0%) and Greenwood Village (48.3%) are each inside the Aff range on the $150,000 share, so the three named places look Affluent; the shortfall comes from other places in M, mostly metros where home values run high against incomes (NYC 11, Philadelphia 9, Austin 8, Phoenix 8).
Caveat: the stored income brackets are single-tract, while the rule uses pooled income and home value.

Result: B fails validation. It fixes the three named places but also moves places that are Affluent on education, occupation and mean income and Middle Class on how many households clear the Pew-style $150,000 line. A stays.
