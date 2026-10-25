# Pillar Deep-Dive: Climate Risk

How `pillars/climate_risk.py` scores a location.

## What it measures
Forward-looking environmental risk, as a 0–100 score where **higher = safer** (lower risk),
built from four sub-scores:

| sub-score | signal | source |
|---|---|---|
| `lst_score` | heat exposure / urban heat island (land surface temp) | satellite LST |
| `aqi_score` | air quality: annual mean PM2.5 for the census tract | CDC Tracking Network tract PM2.5 (EPA Downscaler), `data/pm25_tract_annual.json` |
| `flood_score` | flood risk | FEMA flood data |
| `trend_score` | forward climate trend | trend model |

Each is a capped point bucket (`heat_pts/HEAT_MAX_PTS`, etc.) converted to 0–100, then
combined.

## Air quality (changed 2026-10-24)
The old component was a Sentinel-5P aerosol index scaled to a fake "PM2.5 proxy"; it tracked desert dust and
smoke (rank correlation about -0.14 with measured PM2.5) and gave 86% of places full points. It is replaced by
measured annual PM2.5 per census tract (2021 to 2022 mean, extended as CDC adds years), built by
`scripts/baselines/build_pm25_tract_table.py`. Points: 20 at 5 ug/m3 (WHO 2021 annual guideline) falling
linearly to 0 at 35 (WHO interim target 1). The 5 end is evidence-based; the 35 end is a judgment that only
sets the slope (no US place is near 35), so treat the air weight as an unvalidated choice (tracker D13). A tract
with no value means no data for this component (the climate score uses the other three, flagged degraded).
Wildfire smoke is part of PM2.5 and is kept.

## Fail loud (changed 2026-10-24)
A component that cannot be measured is no data, not a neutral value; the score is built from the rest and marked
degraded, and fewer than three of four components means the pillar fails.

## Reading the score
- It's **regional** in character — places in the same metro share similar climate, so within-
  metro variance is modest (and legitimate). Coastal places correctly carry higher flood risk
  (Marina del Rey / Manhattan Beach score lower on flood — real, not a bug).
- A coastal high-flood signal is the main intra-metro differentiator.

## Gotcha
- Low within-metro spread is expected (shared climate); don't mistake it for a coarse-geo bug.
- Higher score = lower risk (safer) — note the polarity when interpreting.
