# Status signal step 2: housing burden and national lines (criteria fixed before running)

Written 2026-11-05. Step 2 of docs/PRODUCT_MODEL_PLAN.md. Read-only analysis on the stored catalog (pooled income and home value for single-tract places, as in docs/STATUS_SIGNAL.md section 9). No label, score or catalog is changed by this test. The owner decides any change after seeing the results.

Two questions: (1) does the housing-burden demotion in the class label carry information about the people living there, or can it come out; (2) does a national ladder from published lines (Pew, HHS) describe households as well as the current metro-rank top end.

## Candidates
- A (current): Struggling if income under the poverty guideline ($23,030) or burden over 50% with income under the national median ($75,149); Working Class if income under two-thirds of the national median or burden over 30% with income under the median; Affluent if income at or above the metro p80; Elite if income and home value both at the metro p90; otherwise Middle Class.
- N0: A with the burden tests removed (income lines only, same metro p80 and p90 top end).
- N1: national ladder, burden removed. Struggling under $23,030 (HHS); Working Class $23,030 up to two-thirds of the national median ($50,099); Middle Class up to twice the national median ($150,298, Pew upper-income line); Affluent at or above $150,298; Elite is Affluent plus the metro p90 income and home value rule from A (product definition, unsourced, unchanged).

## Targets that no candidate uses
The stored household income brackets (16 ACS B19001 bins, shares of households). Share of households at $150,000 or more (T1, about the Pew upper line) and share under $25,000 (T2, about the poverty line). Also stored mean household income and median gross rent. The label reads the median and a ratio; these read the household distribution.

## Pass criteria (fixed here)
1. Ladder consistency, per candidate: the median T1 rises strictly across the five classes and the median T2 falls strictly.
2. No regress: Spearman between the class ladder (0 to 4) and T1, and between the ladder and negative T2, is not more than 0.02 below A's for the candidate. A rise of 0.02 or more is reported as an improvement. The 0.02 is a judgment fixed here, not a published standard.
3. Burden test (answers question 1): let D be the places whose class is lower under A than under N0 (demoted by burden). On both T1 and T2, if the median of D is closer to the median of the class N0 gives them than to the class A gives them, the burden demotion is not supported by household data and may come out. If closer to A's class, burden carries information and stays.
4. Reported only: the number of places changing class against A, the direction, the largest move, and Beverly Hills, Brookline, Greenwood Village, Tribeca, Murray Hill, Palo Alto, East Palo Alto, Park Slope, Carroll Gardens, Newton.

If N1 passes 1 and 2 and the burden test supports removal, I propose N1 for sign-off; if only the burden test passes, I propose N0; if neither, A stays.
