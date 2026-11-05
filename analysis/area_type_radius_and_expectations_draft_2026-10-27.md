# Draft: radii and expectations for urban residential after the area type change (2026-10-27)

Status: DRAFT FOR DECISION. Nothing here is implemented. Read-only inspection of `data_sources/radius_profiles.py` and `data_sources/regional_baselines.py` on branch `area-type-circle-density`.

## Why this matters

The area type now puts 470 of 1,476 catalog places in urban residential (197 before), and 447 places change type. Every pillar that uses the area type picks its search radius and its expected values from tables keyed by type. Those tables were written when the classes were urban core, suburban, exurban and rural, with urban residential added later.

## What each table gives urban residential today

Search radii (`radius_profiles.py`):

| Pillar | Urban core | Urban residential | Suburban | Exurban | Rural |
|---|---|---|---|---|---|
| Active outdoors, local radius | 800 m | 1,000 m (own branch) | 1,500 m | 2,000 m | 2,000 m |
| Transit routes radius | 3,000 m | 1,500 m (default bucket) | 2,000 m | 1,500 m | 1,500 m |
| Healthcare facilities / pharmacies | 5 km / 2 km | 20 km / 8 km (default bucket) | 10 km / 3 km | 15 km / 5 km | 20 km / 8 km |
| Schools (legacy radius model) | 1.5 mi | 3 mi (default bucket) | 2 mi | 3 mi | 3 mi |
| Tree canopy (built environment, natural beauty) | 1,000 m | 800 m (own branch) | 2,000 m | 2,000 m | 2,000 m |

Expected values (`regional_baselines.py`), the numbers a place is scored against:

| Pillar and measure | Urban core | Urban residential | Suburban | Exurban |
|---|---|---|---|---|
| Amenities, businesses within 1 km | 170 | 180 | 65 | 40 |
| Transit, bus routes | 18 | 35 | 13 | 2 |
| Healthcare, urgent care within 5 km | 17 | 17 | 3 | 1 |
| Healthcare, hospitals within 10 km | 5 | 5 | 1 | 0 |
| Active outdoors, parks within 1 km | 8 | 90 | 64 | 1 |

## Findings

1. The urban core branches are now dead code. The classifier no longer returns urban core (pushed in `b73836b`), so a place the old rule called urban core now takes the urban residential column. In the catalog that is 2 places (Midtown, Midtown East). Live, it is any dense commercial place the old rule labeled urban core. Their radii change as follows: active outdoors 800 to 1,000 m, transit 3,000 to 1,500 m, healthcare 5 to 20 km, schools 1.5 to 3 miles. I do not know how many live requests this touches.
2. The 20 km healthcare radius for urban residential looks inconsistent but may be intended. The expected values say urban residential reuses the urban core sample, but that sample was gathered in 20 km (hospitals), 8 km (pharmacies) and 5 km (clinics) windows (code comments), which match the default bucket. The same applies to transit: its urban residential expectations come from n=16 urban residential locations collected 2024-11-24, when the class already used the 1,500 m default. So the radii are probably consistent with how each expectation was calibrated. I earlier called this a likely bug; the calibration comments say it may not be one.
3. The jumps in the live sample come mainly from the expectation tables, not from the radii. A place promoted from suburban to urban residential is held to 17 urgent care clinics within 5 km instead of 3, 180 businesses instead of 65, and 35 bus routes instead of 13.
4. The active outdoors values for urban residential are estimates. The code comments say "Est. P50 at 1000m radius" and "will be refined after rescore produces empirical 1000m distributions" (90 parks within 1 km, 380 within 5 km, 60 ha). That class was small (197 places) when those were set; it is now 470 places.

## Options

A. Leave the radii and expected values alone. Rescore the 445 catalog places whose radius changes, then refit the active outdoors urban residential expectations from the rescored places (the note in the code already calls for this). Lowest risk to the design; scores shift for the places that change type, by design.
B. Give urban residential the urban core radii for transit and healthcare. Changes scores for all 470 places and would need new calibration of the expected values, because they were gathered at the current radii. Not recommended without a new calibration sample.
C. Soften the cliffs: interpolate the expected values between neighboring types by activity density instead of switching at the cutoff. A larger design change that removes jumps of 15 to 38 points at a boundary. Needs design review and its own tests.

## Recommendation

A now, C as a separate piece of work once the catalog is rescored. B only if a new calibration sample is collected.

## Cost of A

- Catalog places needing new data for at least one pillar: 445 of 1,476. By pillar: healthcare 440, active outdoors 416, transit 387, schools (legacy radius) 387, built environment and natural beauty 47 each. Amenities radius does not depend on type.
- It needs the private Overpass server (states covered: NY NJ CT CA WA TX IL IN PA DE MD; the catalog's other states are not covered) and no paid calls beyond the Places top-up for thin areas.
- Pilot first: 5 places per changed transition against stored values, per the pilot rule.

## Open questions for the owner

1. Accept option A (keep radii, rescore, refit active outdoors) or ask for C first?
2. Rescore the catalog before pushing the area type change, or push first and accept the live versus Explorer gap?
3. Do the formerly-core places need their old radii preserved while we decide? Live frequency is unknown.
