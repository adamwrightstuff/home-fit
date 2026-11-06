# Brief: independent check of the refit social proximity curve (version 3)

For an agent that did not build or audit this feature. Written 2026-11-05. Pass criteria are fixed before any result from this check is read. Do not change them after you see numbers; if you think one is wrong, say so and still report against it. This replaces the earlier brief, whose out-of-fit bands became fit bands when the curve was refit.

## What is being tested
`frontend/lib/socialProximity.ts` scores a place for one close person by straight-line miles from a fit to Appendix Table A2 of Schoeni, Cho and Choi 2022 (Soc Sci Med 292:114627, PMC8806164): adjusted weekly hours of help from an adult child to parents 55+ with an ADL or IADL limit, by distance band. The fit is isotonic (non-increasing) regression weighted by inverse variance, with SE = interval width / 3.92. The claim to test: the fit is reproducible from the paper's numbers, the curve implements it, and the construct is a fair basis. Out-of-sample evidence is separate: the Healy and Dunifon 2025 grandparent paper and the Sun and Schafer 2023 loneliness paper.

## Rules (read first)
- Work offline from the repo plus the published papers. No live HomeFit scoring, no API keys.
- Downloads: ask the owner first, state filename, source and size. Put each in its own new empty folder. Run Python with `-I` and pass paths as arguments. Prefer reading pages over downloading.
- Write every number you read from the papers (paper, table, band, value, interval) to a file BEFORE you open `frontend/lib/socialProximity.ts` or `docs/SOCIAL_PROXIMITY.md`.
- Do not fill an unreadable number from memory. No em dashes. Say plainly what you verified and what you could not.

## Steps and pass criteria (fixed)
1. Transcription: read all eight distance bands of Table A2 (coresident, same block, up to 2, 2 to 5, 5 to 10, 10 to 30, 30 to 100, over 100 miles) with intervals. PASS if each band's hours agree with the owner's notes (1.20, 1.56, 0.73, 0.43, 0.75, 0.56 for the six non-coresident bands, 5.34 and 4.16 for coresident and same block) within 0.05.
2. Reproduction: from your own numbers, compute the inverse-variance-weighted isotonic fit over the six bands from up to 2 miles outward, then express each pooled level relative to the pooled near level (up to 5 miles). PASS if your 5 to 10 mile and 10 mile and beyond values are within 3 points of 57 and 39.
3. Implementation: recompute the curve from the current file at 3.5, 7.5, 20 and 100 miles. PASS if they are 100, 57, 39 and 39 within 0.5.
4. Out-of-sample, report only unless stated: (a) Healy and Dunifon 2025 (Demographic Research 52:34): any hours of help by distance band. PASS only if you can read a table with at least three distance bands; compare the ratio of the band beyond 10 miles to the nearest band with the curve's 39 percent, and call it consistent if inside a published interval. If you cannot read a table, say so; that is not a failure. (b) Sun and Schafer 2023: whether anything contradicts a steep drop between 3.5 and 7.5 miles for relatives.

## Report
Per band table, each criterion pass or fail, where in each paper each number came from, what you could not read, and your own view of whether help to disabled older parents is a fair stand-in for choosing where to live. State plainly what is verified and what is not.

## Not covered
The acquaintance curve (no source), the combine rule, any wellbeing outcome, and adults who are not older or not in need of care.
