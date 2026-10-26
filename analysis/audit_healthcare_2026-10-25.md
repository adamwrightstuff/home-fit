# Healthcare access: v2 audit findings (2026-10-25, offline, no changes)

Scope: `pillars/healthcare_access.py` (1,210 lines), `docs/PILLAR_HEALTHCARE_ACCESS.md`, the stored catalog (1,476 places), a web search for the
evidence behind the distance curve. Nothing was changed.

## Finding
The pillar saturates because care within about 5 km really is adequate, and the published evidence does not support separating places
inside that distance. It also has parameters with no source and one fail-loud violation.

## What the catalog shows
- 579 places (39%) score exactly 100. All of them have a hospital within 5.6 km (median 1.4 km). By area type: urban residential 85% at 100,
  suburban 40%, exurban 26%, rural 5%.
- Distance to the nearest hospital drives the rest: 0 to 3 km mean 95; 3 to 6 km mean 89; 6 to 10 km mean 77; 20 km and more mean 26 (95 places).
  So the pillar does separate places where distance is large, which is the range the evidence cares about.
- Component caps are 35 hospitals, 25 primary care, 15 specialty, 10 emergency, 15 pharmacies (sum 100). Pharmacies and primary care are
  scored against area-type expected counts.

## Evidence (searched 2026-10-25, summaries only, full papers not read)
- Travel time to the nearest hospital and mortality is mixed. An English cohort of 22,772 emergency laparotomies found no association
  (odds ratio 1.02 per 10 minutes, 95% interval 0.97 to 1.06; median travel 16 minutes). A UK study of general emergencies found an adjusted
  odds ratio of 0.97 per 10 minutes with a wide interval (0.70 to 1.34). California ED closures (1999 to 2009) were studied for MI, stroke,
  sepsis and COPD; the result was not in the snippet, so it is not cited here. The Utah EMS finding (8% to 17% higher mortality per minute of
  response time) is response time, not drive time to the ED.
- National access (Carr et al., Annals of Emergency Medicine, 2009): 71% of Americans reach an ED within 30 minutes and 98% within 60.
  The figures are 17 years old.
- No source gives a threshold below which more proximity stops mattering, and none supports an exponential penalty from 0 km.

## Parameter table (P4)
| Parameter | Value | Source | Status |
|---|---|---|---|
| Hospital distance curve | 35 x exp(-km / 15), floor 14% | Comment says "data-backed"; no data cited | Unsourced. Penalises 6 to 10 km (about 6 to 10 minutes) where the evidence shows no effect |
| Ratio curve | 50 at 1.0x expected, 85 at 1.5x and 2.5x, 95 at 3.0x | Comment says "data-backed" | Unsourced; the 85 to 85 flat segment is odd |
| Expected counts by area type | per area type in regional baselines | Not traced in this pass | Unsourced |
| Component caps 35/25/15/10/15 | fixed | None | Unsourced |
| Minimum floor 2% of cap | fixed | None | Judgment |

## Fail-loud (P9)
- When the OSM query fails for an urban or suburban place, the code applies "conservative minimum scores for pharmacies and primary care"
  (lines near 640 to 665). That is an invented value. The stored catalog carries no marker for it (`fallback_used` is false everywhere and no
  warnings are stored), so how many places got it cannot be told from stored data.
- A hard-coded hospital list is used for distance when OSM finds none. It is a real list, not an invented number, but it is a silent fallback.
- 80 places have confidence under 50 (Sacramento 13, San Antonio 12, Denver 10, Austin and Phoenix 7 each).

## Launch check
FAIL because 39% sit at the maximum. That is the correct reading for an adequacy pillar; the check has no way to tell the difference.

## Options
1. **Document and fix fail-loud only (no score change).** State that it is an adequacy pillar with a ceiling, record the unsourced
   parameters with ranges, remove the invented pharmacy and primary-care fallback (missing components leave the score, flagged degraded),
   store a marker when a fallback is used. Cost: the launch check keeps failing healthcare; document why.
2. **Also replace the distance curve** with a plateau then decay. The evidence gives no plateau length (mixed results, none under about 30
   minutes), so any value is a judgment and the 6 to 10 km places (112) would rise. Not recommended until a source is found.

My recommendation is option 1.

## Outcome (2026-10-26)
Option 1 applied: failed OSM reads raise (no data), the invented pharmacy, primary-care and specialty fallbacks are removed, a Places
recovery is flagged degraded, and the pillar doc records the adequacy decision and the unsourced parameters. Catalog: 31 failed-read places
handled (17 re-read unchanged in CA and TX, 14 set to no data in CO, NC, NV and AZ, which the private Overpass server does not cover; total
score +2.2 on average for those rows because their weight is redistributed). Tests: `tests/test_healthcare_fail_loud.py`.
