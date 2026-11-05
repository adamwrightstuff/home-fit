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
(to be filled after the run)
