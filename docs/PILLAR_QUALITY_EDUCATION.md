# Pillar Deep-Dive: Quality Education

How `pillars/schools.py` feeds the `quality_education` pillar.

## What it measures
School quality near a location — average rating of nearby schools, with small bonuses for
access (how many quality schools are reachable) and early-education availability.

## Scoring
- Pull nearby schools with ratings (state percentile / star ratings). Schools without rating
  data are ignored; if **none** have ratings, the pillar has no signal.
- `base_avg_rating` = average of available school ratings, plus:
  - `access_bonus` — credit for having multiple quality options reachable.
  - `early_ed_bonus` — early-education availability.
- Combined → 0–100.

## ⚠️ Gated behind a quota flag — the big Live-vs-Explorer divergence
School data is **expensive and quota-limited**, so `ENABLE_SCHOOL_SCORING` defaults to
**False** (`main.py:94`). When off, `_apply_schools_disabled_weight_override` zeros the
`quality_education` weight and redistributes.

- **Live (default):** education contributes **nothing** to a score.
- **Catalog / Explorer:** the catalog was built with schools **on**, so it carries real
  education scores (status=success, confidence=85) and the Explorer **weights** them.

So good-school suburbs rank higher in the Explorer than in a default live lookup. This is the
single biggest intentional divergence — see LIVE_SCORER_VS_EXPLORER. (Enabling it in the
catalog was a deliberate, free reweight since the scores already existed —
`enable_education_weight.py`.)

## Elite-district ceiling (ℹ️)
~23 catalog places score exactly **95** (Chappaqua, Darien, Short Hills, Westport, Great Neck,
...). Legitimate ceiling — schools are **district-administered**, so a top district's towns
share the same (capped) rating. Consequence: elite districts don't separate from each other.

## Gotchas
- A default live API score has education at weight 0; don't compare it to a catalog score that
  weights education.
- District-level resolution means neighboring towns in one district get the same school score
  by design — it's not a per-place signal.
