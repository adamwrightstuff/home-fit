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
