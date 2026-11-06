# Brief: independent check of the social proximity curve against published distance data

For an agent that did not build or audit this feature. Written 2026-11-05. Pass criteria are fixed before any result from this check is read. Do not change them after you see numbers; if you think one is wrong, say so and still report against it.

## What is being tested
`frontend/lib/socialProximity.ts` scores a place for one close person by straight-line miles: 100 through 5 miles, 68 at 15 miles, linear to 50 at 100 miles (changed from 7.5 miles on 2026-11-05; read the current file), flat beyond. The 68 at 15 miles and the 50 floor were set from one study. The question: does that curve agree with the distance-and-help data in the study, especially in bands that were not used to set it, and does the second cited study contradict the plateau?

## Rules (read first)
- Work offline from the repo plus the two published papers below. No live HomeFit scoring, no API keys.
- Downloads: ask the owner first, state filename, source and size. Put each in its own new empty folder. Run Python with `-I` and pass paths as arguments; do not run scripts from inside the download folder.
- Write down every number you read from the papers (paper, table or figure, band, value, confidence interval) in a file BEFORE you open `frontend/lib/socialProximity.ts` or `docs/SOCIAL_PROXIMITY.md`.
- No em dashes. Say plainly what you verified and what you could not.

## Sources
1. Schoeni, Cho and Choi 2022, "Close enough? Adult child-to-parent caregiving and residential proximity", Social Science and Medicine 292:114627 (PMC author manuscript). Adjusted weekly hours of help received from an adult child, parents 55+ with ADL or IADL limits, by distance band: coresident, same block, up to 2 miles, 2 to 5, 5 to 10, 10 to 30, 30 to 100, over 100.
2. Sun and Schafer 2023, "Distance in Disconnection", J Gerontol B 78(11):1917-1926 (PMC10645308). Loneliness effects of losing a core network member by distance band (0 to 1 km, 1 to 5, 5 to 25, over 25).

## Measure
Reference hours H_ref = adjusted hours in the 2 to 5 mile band (the curve's 100). For each band, ratio = band hours / H_ref, with a conservative interval [band_lo / ref_hi, band_hi / ref_lo] from the published 95 percent intervals. Curve value for a band = the curve at the band midpoint divided by 100: up to 2 mi use 1 mi, 5 to 10 use 7.5 (curve 92 on the current file, the band average is not a point value), 10 to 30 use 20, 30 to 100 use 65, over 100 use 150.

## Pass criteria (fixed)
1. Transcription: your adjusted hours for the 2 to 5, 5 to 10 and over 100 mile bands match the values the owner's notes give (1.16, 0.79, 0.58) within 0.05 hours. This checks the citation. The curve was fitted to these three, so it is not evidence about the curve.
2. Out of fit: the curve value at 20 miles (0.669) and at 65 miles (0.574), recomputed by you from the current file each fall inside the conservative ratio interval of the 10 to 30 and 30 to 100 mile bands. These two bands were not used to build the curve.
3. Inside 5 miles: the point-estimate ratio for the up-to-2-mile band is at most 1.5. The curve is flat inside 5 miles (ratio 1.0). The owner already knows the same-block hours (3.16) are about 2.7 times H_ref, so a failure here is plausible and is a finding, not a surprise.

Not pass or fail, report only: what Sun and Schafer say about distance bands for relatives and for non-kin, and whether anything in either paper contradicts a flat plateau inside 5 miles.

## Report
A table of every band (hours, interval, ratio, ratio interval, curve value, inside or outside), the three criteria with pass or fail, exactly where in each paper each number came from, anything you could not read, and your own view of whether the construct (help to disabled older parents) is a fair stand-in for choosing where to live. State plainly what is verified and what is not.

## Not covered by this check
Acquaintance curve (no source), the combine rule, any wellbeing outcome, adults who are not older or not in need of care.
