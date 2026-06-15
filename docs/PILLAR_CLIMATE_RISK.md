# Pillar Deep-Dive: Climate Risk

How `pillars/climate_risk.py` scores a location.

## What it measures
Forward-looking environmental risk, as a 0–100 score where **higher = safer** (lower risk),
built from four sub-scores:

| sub-score | signal | source |
|---|---|---|
| `lst_score` | heat exposure / urban heat island (land surface temp) | satellite LST |
| `aqi_score` | air quality | AQI |
| `flood_score` | flood risk | FEMA flood data |
| `trend_score` | forward climate trend | trend model |

Each is a capped point bucket (`heat_pts/HEAT_MAX_PTS`, etc.) converted to 0–100, then
combined.

## Reading the score
- It's **regional** in character — places in the same metro share similar climate, so within-
  metro variance is modest (and legitimate). Coastal places correctly carry higher flood risk
  (Marina del Rey / Manhattan Beach score lower on flood — real, not a bug).
- A coastal high-flood signal is the main intra-metro differentiator.

## Gotcha
- Low within-metro spread is expected (shared climate); don't mistake it for a coarse-geo bug.
- Higher score = lower risk (safer) — note the polarity when interpreting.
