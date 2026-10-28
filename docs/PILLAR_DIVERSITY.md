# Pillar Deep-Dive: Diversity

How `pillars/diversity.py` scores a location (`get_diversity_score`).

## What it measures
How **mixed/even** a tract's population is across three dimensions, via normalized (Shannon)
entropy — a perfectly even split scores high, a dominated-by-one-group split scores low.

| dimension | source (Census tract, ACS) | included when |
|---|---|---|
| race | `race_counts` (B02001) | ≥2 race categories present |
| income | `income_counts` | ≥2 income bins present |
| age | youth / prime / seniors buckets | any present |

```
dimension_score = normalized_entropy(counts) → 0–100
diversity_score = mean(available dimension scores)
```

**Race (changed 2026-10-24):** B02001 `_009` and `_010` are the two parts of `_008` (two or more
races), so they are dropped to avoid counting multiracial residents twice, and race entropy is
normalized by the fixed seven groups (six single-race groups plus two or more) instead of the number
of non-empty groups. Income and age still normalize by non-empty bins/buckets. Catalog values were
rewritten offline by `scripts/catalog/recompute_diversity_race_offline.py` (old values backed up).

## Preference (optional)
`diversity_preference` (subset of race / income / age) averages **only** the selected
dimensions instead of all available. `version: v2_preference_optional`.

## Geography & the fabricated-0 bug ⚠️
Data comes from the **tract** (`census_api.get_diversity_data` keyed on the resolved tract).
When the tract lookup fails, the fallback can resolve to a **zero-population
`county_subdivision`** → all race/income/age counts are 0 → no dimension qualifies → the score
defaults to **0.0** (an impossible "0% diverse").

- Confirmed persistent for **Southport** (marked no-data: score=None, weight 0).
- **Maspeth** was a *transient* 0 — retrying resolved it to 72.5. Retry distinguishes
  transient from persistent.
- Likely affects other small villages/CDPs not in this catalog.
- **Proper fix (open):** harden the fallback chain (tract → block group → place → county) so it
  never returns a zero-pop geography and never emits a fabricated 0. See PILLAR_DATA_QUALITY
  and the pillar-coverage-gaps memory.

## Also feeds Status Signal
The pillar surfaces `education_attainment` and `self_employed_pct` (from the same ACS pull)
for `status_signal` — these are separate from the diversity score itself.

## Catalog
The 2 broken records were repaired by `scripts/repair_diversity_and_weights.py` (Maspeth →
72.5; Southport → no-data), which **also renormalizes every place's weights to sum to 100**
(it fixed the education-enable weight bug at the same time). See CATALOG_RESCORE_RUNBOOK.

## Gotchas
- A diversity score of exactly **0 with confidence 0** is almost always the fabricated-0 bug,
  not a real value — quarantine, don't relaunder.
- Entropy rewards *evenness*, not the presence of any particular group — a uniformly
  single-group area scores low regardless of which group.

## Race and Hispanic origin (changed 2026-10-28)
The race term now uses ACS B03002: Hispanic or Latino (any race) plus the seven non-Hispanic race groups
(white, Black, American Indian and Alaska Native, Asian, Native Hawaiian and Pacific Islander, some other race,
two or more), eight groups, entropy normalized by ln 8. Hispanic origin was previously folded into "some other race".
Catalog effect: headline mean -0.3, up to -15.6 and +7.1; larger drops where the Hispanic share is 30 percent or more
(mean -3.3) and in LA, Miami and San Antonio. Geography fails loudly: a failed place lookup or place fetch is no data
(2026-10-28), and `measured_area` stores the geography used and total population. Unsourced: the 200,000-adult ceiling.
Open: income term still normalizes by non-empty brackets (fixed-16 test: headline mean -0.6), age term unsourced,
tract-level pin-shift 95th percentile 13.4 points (pooled 700 m: 8.8), independent validation not done.
