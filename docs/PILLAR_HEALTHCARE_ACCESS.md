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

## Saturation (ℹ️ by-design, but worth knowing)
In a dense metro, most places are near multiple hospitals and pharmacies, so the pillar
**saturates at 100** — ~58 NYC catalog places across 10 counties hit exactly 100. That's a
legitimate ceiling (genuine abundance), not a coarse-geo bug, but it means healthcare doesn't
differentiate much within an urban core. See PILLAR_DATA_QUALITY.

## Gotchas
- High scores cluster at the ceiling in cities — don't expect healthcare to separate dense
  neighborhoods. It differentiates mainly in suburban/exurban/rural areas where distance bites.
- It's an *access* pillar (can you reach care), not a *quality* pillar (how good the care is).
