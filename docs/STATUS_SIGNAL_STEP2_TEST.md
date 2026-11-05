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

## Results (run 2026-11-05, 1,469 classified places)
My re-implementation of A reproduces all 1,469 stored labels (0 mismatches).

| | A (current) | N0 (burden removed) | N1 (national ladder, burden removed) |
|---|---|---|---|
| Class counts (Struggling, Working, Middle, Affluent, Elite) | 6, 127, 958, 240, 138 | 0, 68, 1,023, 240, 138 | 0, 68, 1,122, 152, 127 |
| Median T1 (households at $150,000 or more) by class | 3.5, 8.0, 25.0, 50.1, 61.7 | none, 5.9, 24.0, 50.1, 61.7 | none, 5.9, 25.8, 56.2, 62.1 |
| Median T2 (households under $25,000) by class | 50.6, 25.1, 11.2, 6.3, 5.4 | none, 27.4, 11.5, 6.3, 5.4 | none, 27.4, 11.1, 6.1, 5.1 |
| Spearman with T1 / with negative T2 | 0.724 / 0.604 | -0.020 / -0.034 vs A | -0.026 / -0.066 vs A |
| Places changing class vs A | none | 69 (4.7%), largest move 2 | 230 (15.7%), largest move 2 |

Criterion 1 (strict ladder over five classes): A passes. N0 and N1 fail by the letter because they have no Struggling place (all 6 Struggling places in A were burden demotions; no place is under the poverty line). Over the four occupied classes both rise and fall strictly. The criterion could not be met by any candidate without burden, so this is a flaw in how I wrote it, reported as written.
Criterion 2 (no regress, limit 0.02): N0 is 0.0201 below A on T1 and 0.0336 below on negative T2; N1 is 0.0257 and 0.0656 below. Both FAIL.
Criterion 3 (burden test): D is the 69 places A demotes by burden (63 Working Class instead of Middle Class, 4 Struggling instead of Working, 2 Struggling instead of Middle). For the 63: T1 11.4 against 6.0 for Working Class and 25.0 for Middle Class; T2 21.4 against 27.3 and 11.2. D is closer to the class A gives them on both measures, so burden carries information. Burden stays.
Criterion 4 (reported): Beverly Hills, Brookline, Greenwood Village and Carroll Gardens stay Middle Class under all three. Tribeca, Park Slope, Newton stay Elite and Murray Hill and Palo Alto stay Affluent under N0 and N1. N1 moves 119 Affluent places to Middle Class (those between the metro p80 and $150,298), 31 Middle Class places to Affluent, and 11 Elite places to Middle Class.

Post-hoc control (not pre-registered; added because criterion 3 does not separate burden from income, since the demoted places also have lower incomes). Among places with income between two-thirds of the national median and the median, at the same income, places with burden over 30% against not:
- $50,099 to $63,877: burden over 30% (n=40) T1 10.1, T2 22.4; not (n=91) T1 9.8, T2 18.9.
- $63,877 to $75,149: burden over 30% (n=25) T1 15.2, T2 21.4; not (n=160) T1 16.3, T2 14.7.
So at the same income, high-burden places have more households under $25,000 (3.5 and 6.7 points more) and no fewer at $150,000 or more. Small samples; burden separates the low end, not the high end.

## Result
No candidate passes. A stays: the burden test is supported by household data at the low end, and the Pew national ladder fits the household distribution worse than the metro p80 line on this catalog (the catalog is all metros, so the metro line suits it). Beverly Hills as Middle Class is unchanged under every candidate. This reverses my earlier lean that housing does not belong in the label.

## Round 2: a household-distribution route to Affluent (criteria fixed before running, 2026-11-05)
Why: round 1 only tested rules that still read the median income, so it could not reach Beverly Hills, Brookline or Greenwood Village (Middle Class on the median, but 43 to 48 percent of households at $150,000 or more). Round 2 tests a rule that reads the household income distribution directly.

Rule input: T1, the share of households at $150,000 or more (the top two stored B19001 bins; $150,000 is about twice the national median, the Pew upper-income line). Cut: the midpoint between the median T1 of A's Middle Class places and the median T1 of A's Affluent places (a nearest-class cut from the data, not a chosen number). T1 is stored per tract or place, not pooled (known gap).
- H1: A, plus Middle Class places with T1 at or above the cut become Affluent. Nothing is demoted.
- H2: H1, plus Affluent places (not Elite) with T1 below the cut become Middle Class.
Elite, Struggling and Working Class are unchanged from A.

Targets that neither rule uses: stored mean household income, median gross rent, median home value, graduate degree share.

Pass criteria (a candidate replaces A only if all hold):
1. Spearman between the class ladder (0 to 4) and mean income, and between the ladder and rent, each improves on A by at least 0.02 (judgment limit, as in round 1).
2. The median mean income rises strictly across the occupied classes.
3. Nearest-class test on the moved set (places H changes), on mean income, home value and graduate share: the median of the moved set is closer to the class H gives them than to the class A gave them on all three.
4. No more than 15% of places change class, and none moves more than one class (judgment limits).
5. Reported only: Beverly Hills, Brookline, Greenwood Village, Newton, Palo Alto, East Palo Alto, Park Slope, Carroll Gardens, Murray Hill, Tribeca, and the moved places by metro.
If a candidate passes all five I propose it for sign-off; if none does, A stays and the Beverly Hills result is a known limit.

### Round 2 results (run 2026-11-05, 1,469 places, 1,465 with stored income brackets)
Cut: median T1 is 25.0 for A's Middle Class and 50.1 for A's Affluent, so the nearest-class cut is 37.55 percent of households at $150,000 or more.

| | A (current) | H1 (promote only) | H2 (promote and demote) |
|---|---|---|---|
| Places changing class | none | 223 (15.2%), all Middle Class to Affluent | 255 (17.4%): 223 up, 32 Affluent to Middle Class |
| Spearman with mean income / rent / home value / graduate share | 0.735 / 0.490 / 0.465 / 0.580 | 0.844 / 0.607 / 0.596 / 0.691 (+0.110 / +0.117 / +0.130 / +0.111) | 0.841 / 0.597 / 0.598 / 0.691 |
| Median mean income by occupied class | rises strictly | 40,104 / 68,554 / 107,823 / 185,241 / 301,654, rises strictly | rises strictly |
| Nearest-class test on the moved set (mean income, home value, graduate share) | n/a | closer to the new class on all three | closer to the new class on all three, both directions |
| Largest move | n/a | 1 class | 1 class |

Criterion 1 PASS (gains of 0.11 or more on all four targets, limit 0.02). Criterion 2 PASS. Criterion 3 PASS: the 223 promoted places have median mean income $171,518 (Middle Class $107,823, Affluent $196,358), median home value $758,755 ($372,349 and $696,500) and graduate share 30 percent (Middle Class 15, Affluent 31). Criterion 4 FAIL by the letter: H1 moves 15.2 percent of places against the 15 percent limit (H2 17.4 percent). The limit was a judgment I fixed; I have not relaxed it.
Criterion 5 (reported): Beverly Hills (T1 42.7), Brookline (45.0), Greenwood Village (48.3) and Carroll Gardens (55.7) become Affluent. Tribeca, Park Slope and Newton stay Elite; Murray Hill and Palo Alto stay Affluent; East Palo Alto (31.8) stays Middle Class. Moved places by metro: SF 66, NYC 29, Boston 27, LA 17, Denver 16, Philadelphia 16.

Readings and limits:
- Mean income is related to T1 by construction (both come from the same household distribution), so its gain is partly built in. Rent, home value and graduate share are less tied to T1 and still improve by 0.117, 0.130 and 0.111.
- T1 is a national line ($150,000 is about twice the national median) applied to places in expensive metros: SF carries 30 percent of the moves. Whether a place with 40 percent of households above the national upper-income line is Affluent when the metro median is high is the frame question again.
- T1 is stored per tract or place and is not pooled; the pooled Census pull has no income brackets, so pin-shift for this rule cannot be measured offline, and the live scorer does not fetch the bracket bins today (only the total). Adopting H1 means a new Census read of the B19001 bins for live scoring and for the pooled catalog places.
- Result: H1 passes every check except the 15 percent movement limit by 0.2 points. Adoption is the owner's call; I propose H1 for sign-off, with the live-scoring and pooling gaps accepted as open.
