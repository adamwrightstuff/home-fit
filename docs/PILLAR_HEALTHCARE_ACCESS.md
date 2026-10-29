# Pillar Deep-Dive: Healthcare Access

How `pillars/healthcare_access.py` scores a location.

## What it measures
Access to medical facilities — hospitals, emergency services, clinics/primary care, and
pharmacies — by **count and proximity**. It does NOT measure quality of care or hospital
ratings (out of scope).

## Components (each a capped sub-score, summed)
| component | signal | approx cap |
|---|---|---|
| hospitals | count + distance to nearest | ~35 |
| emergency (ER) | hospitals with ER capability | — |
| clinics / primary care | count + proximity | — |
| pharmacies | count + proximity | ~15 |

- Each component has a **distance-decay** score (`_distance_to_hospital_score`) and a
  count-based score, with a small **minimum floor** (~2% of the cap) so "some access" never
  reads as zero.
- Components are summed and clamped to 0–100.

## Adequacy pillar (decided 2026-10-26)
Healthcare is an adequacy pillar: reaching the ceiling is a legitimate result, not a defect. In the catalog 579 of 1,476 places (39%) score exactly 100, all with a hospital within 5.6 km (median 1.4 km); 85% of urban residential places are at 100. The published evidence on drive time and mortality is mixed and shows no effect over short distances, so separating places inside about 5 km is not supported. The launch check will keep flagging healthcare for clumping at the maximum; that is expected. See `analysis/audit_healthcare_2026-10-25.md`.

## Failed reads and fallbacks (changed 2026-10-26)
A failed Overpass read now raises, so the pillar shows as no data and is retried; it is never scored as zero facilities. The invented component scores that used to apply after a failed read in urban and suburban areas (pharmacies 6 to 10, primary care 10 to 15, specialty 4 to 8) were removed. If Google Places (when enabled) supplies facilities after an OSM failure, the result is flagged degraded (`osm_query_failed_recovered_from_google_places`). When OSM succeeds but lists no hospital, the hard-coded `MAJOR_HOSPITALS` list supplies the distance to the nearest real hospital.

Catalog: 31 places carried the old failed-read marker (confidence 10 or less). They were re-read through the private Overpass server. Seventeen in California and Texas came back unchanged (the data is sparse there, so the low scores are real). Fourteen in Colorado, North Carolina, Nevada and Arizona are in states the private server does not cover, so an empty answer means no data: they are set to no data (reason `healthcare_read_failed_not_yet_retried`) and their weight is redistributed. Adding those states to the private server and re-reading them restores a score.

## Unsourced parameters (P4), all judgments with no cited source
Hospital distance curve 15 x exp(-km / 15) with a 14% floor; the ratio curve (50 at 1.0x expected, 85 at 1.5x and 2.5x, 95 at 3.0x); the area-type expected counts; the component caps 35/25/15/10/15; the 2% minimum floor. Recorded here as a TODO; no source was found for a distance plateau.

## Saturation (ℹ️ by-design, but worth knowing)
In a dense metro, most places are near multiple hospitals and pharmacies, so the pillar
**saturates at 100** — ~58 NYC catalog places across 10 counties hit exactly 100. That's a
legitimate ceiling (genuine abundance), not a coarse-geo bug, but it means healthcare doesn't
differentiate much within an urban core. See PILLAR_DATA_QUALITY.

## Gotchas
- High scores cluster at the ceiling in cities — don't expect healthcare to separate dense
  neighborhoods. It differentiates mainly in suburban/exurban/rural areas where distance bites.
- It's an *access* pillar (can you reach care), not a *quality* pillar (how good the care is).

---

## DPv2 spec sheet and audit (2026-10-29)

```
Pillar: healthcare_access
Construct (one sentence): Access to care near the pin: how close the nearest hospital, emergency room and pharmacy are,
  and how many clinics and doctors there are per resident within 10 km.
Reference frame: fixed standard for distance (published drive-time and pharmacy-desert thresholds); catalog-median scale for
  the per-resident clinic and doctor supply (descriptive, not an external standard).
  Evidence for the frame: tier 1 for distance anchors (emergency department access study, 2009; pharmacy desert thresholds,
  2024 national study). Supply scale: none yet (TODO).
Measurement area: pin + one 10 km radius for every place (no area type).
  Reason: matches the OpenStreetMap read; facilities and residents are counted in the same disk. A drive-time catchment would
  be better (TODO).
Inputs and data sources (with vintage): OpenStreetMap hospitals, urgent care, clinics, doctors, pharmacies (private Overpass
  read, fresh 2026-10-28); residents within 10 km from the 2020 tract tables (density x disk area, carried on the place
  context as people_10km); NPI registry for specialty counts when tags are absent (live only).
Parameters:
  hospital distance curve | 15 x exp(-km / 15), floor 14% | unsourced; close to published points under an assumed speed | unknown | not run
  clinics+doctors per 1,000 residents | 0.0747 (catalog median) | descriptive, TODO benchmark | not set | not run
  pharmacy distance | full to 0.5 mile, half at 1 mile, 5% at 10 miles | anchors published, shape is judgment | not set | not run
  emergency distance | same curve as hospital distance, 10 points | as above | unknown | not run
  point budgets 35/25/15/10/15 | inherited | unsourced | unknown | not run
Shared inputs with other pillars: none known.
Pin-shift sensitivity (2026-10-29, 60 places, 15 per area type, shifts north, east, south, west, 480 fresh reads):
  500 m shift: median score change 0.9, 95th percentile 5.5. 1,000 m shift: median 1.9, 95th percentile 11.4.
  By area type (median / 95th, both distances): urban residential 1.0 / 5.5; suburban 1.5 / 6.2; exurban 1.6 / 9.3.
  4.2 percent of shifted reads move the score by more than 10. One outlier: Spring Branch, TX (rural) fell from 79.4 to 4.4
  with a 1 km shift north, which cannot be real (a 1 km move cannot remove every facility within 10 km); it looks like a
  transient partial read recorded as empty, and it alone drives the rural 95th percentile of 62. Excluding it, the largest
  change is 16.4 (Steiner Ranch, TX). Finding: an all-empty read is accepted as a real zero (principle 9 risk).
Independent validation source and result: NOT RUN. Candidates: federal health professional shortage area designations,
  CMS hospital locations.
All-places check (date, n, summary): 2026-10-29, n=1,462. Mean 72.7, median 77.7, 10th to 90th percentile 44 to 96.
  By area type (10th / median / 90th): urban residential 77 / 88 / 99; suburban 55 / 79 / 96; exurban 41 / 66 / 92;
  rural 11 / 42 / 79. Only 1.8 percent score 99.9 or more and 1.0 percent score 10 or less, so no floor or ceiling clumping.
Fail-loud conditions: a failed OpenStreetMap read raises (no data); Places recovery is flagged degraded; residents
  unmeasurable leaves the capacity part out and scales over the rest; no pharmacy near mapped clinics or hospitals leaves
  pharmacies out (6 places) and flags it.
Launch check pairs: should differ: Park Slope 96.9 vs Magnolia TX 23.5 (pass); Midtown 95.4 vs Galt CA 4.4 (pass).
  Should be similar: Park Slope 96.9 and Brooklyn Heights 96.5 (pass); Palo Alto 96.6 and Park Slope 96.9 (pass).
Known data limits: 16 places show no facility of any kind within 10 km. Re-read at 20 km (2026-10-29), 8 of the 11 checked
  have hospitals 11 to 19 km away (Galt, CA 14 km, Elmendorf, TX 15 km), and Esparto, Georgetown and Comfort have almost
  nothing within 20 km, so these are real rural absences, not map gaps; the real-zero scoring stands; facilities are counted, not providers or
  capacity; straight-line distance, not drive time; specialty tags are sparse so specialized care mostly measures tagging;
  hospital count is not scored (decided 2026-10-28).
Last re-validated: 2026-10-29 (all-places and launch pairs only).
```

Open audit findings: (1) independent validation is not run (pin-shift is done, see above); (2) every curve parameter except the
pharmacy anchors lacks a source and a plausible range; (3) the nothing-mapped places are resolved (real absences); the open issue is an empty read being accepted as a real zero
(see the Spring Branch outlier), which a hospital-database cross-check could catch; (4) the supply scale and hospital curve need published benchmarks.
