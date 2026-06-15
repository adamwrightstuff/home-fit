# Pillar Deep-Dive: Neighborhood Amenities

How `pillars/neighborhood_amenities.py` scores a location.

## What it measures
Walkable local life — the density, variety, and proximity of (mostly independent) businesses
and daily-needs within walking distance.

## Components
| component | cap | signal |
|---|---|---|
| walkable density | 0–50 | count of walkable businesses (`_score_walkable_density`) |
| variety | 0–25 | spread across business tiers t1–t4 (`_score_walkable_variety`) |
| essentials proximity | 0–25 | proximity of daily-needs businesses (`_score_essentials_proximity`) |
| location quality | 0–40 | quality/character of the business mix (`_score_location_quality`) |

Inputs are OSM businesses with a Places fallback (`data_source: blended` when the fallback is
used). Current model is tagged `amenities_v3_walkable_density` in the catalog.

## Gotcha — point placement
The score depends on the catalog/query **coordinate**. If a place's point sits in its
residential interior, the walkable-radius can **miss the commercial strip** and undercount —
e.g. Larchmont Village amenities 47.7 despite the famous Larchmont Blvd. Spot-check a specific
place against its real main street if the score looks off. See PILLAR_DATA_QUALITY.
