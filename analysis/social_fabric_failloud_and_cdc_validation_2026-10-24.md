# Social fabric: fail-loud blend and CDC PLACES validation (2026-10-24)

Status: applied locally, uncommitted. Backups in `data/backups_social_fabric_failloud_2026-10-24/` (full pre-change
copies of the 21 metro files plus per-place old social fabric values).

## Change applied
- `pillars/social_fabric_blend.py` (new): participation 0.60, cohesion 0.20, rootedness 0.10, civic 0.10; a missing
  component is left out and the rest scaled proportionally; fewer than two components or no participation means no score.
- `pillars/social_fabric.py` uses it; a missing stability reading is no longer scored as zero; the pillar is flagged
  degraded with the reason when cohesion, stability or the OSM civic read is missing or implausibly thin;
  `summary.weights_used` and `summary.components_missing` are returned. Version string v17_sf_failloud_blend.
- `pillars/composite_indices.py` F15 correction now calls the same blend instead of a second copy of the old weights.
- Docstring, comments and `docs/PILLAR_SOCIAL_FABRIC.md` rewritten to match the code.
- Tests: `tests/test_social_fabric_blend.py`; full suite 491 passed (one unrelated election-file test deselected).

## Catalog diff (1,476 places)
- Social fabric score changed for 286 places (mean +0.41, range -1.9 to +6.1); 1,190 unchanged.
- Newly flagged degraded: 391 places (missing cohesion, missing stability, OSM civic error, or implausibly thin civic read).
- Cascade (`recompute_catalog_composites.py --no-census`, changed rows only): longevity_index changed for 286 (mean +0.15),
  happiness_index for 239 (mean +0.12), it_score for 259; total_score for 286 places mean +0.03 (range -0.15 to +0.47) plus
  31 places moved by 0.01 from contribution rounding. No field outside social fabric, total, longevity, happiness and aura changed.
- Stability scores are recovered from stored scores (accurate to about 0.5, effect on new scores under 0.07).

## CDC PLACES validation (offline)
Data: CDC PLACES ZCTA Data, 2025 release (data.cdc.gov dataset kee5-23sr), 32,520 ZIP areas, 10 columns selected,
2.4 MB, saved in an isolated scratch folder. Outcomes: LONELINESS and EMOTIONSPT (lack of social and emotional support)
crude prevalence. Controls from ACS 2022 by ZCTA: median household income, bachelor's share, median age.
845 of 1,475 catalog places joined (ZIP not a ZCTA or missing).

| Score | Loneliness raw / partial | Lack of support raw / partial |
|---|---|---|
| Pillar (new) | -0.39 / -0.15 | -0.42 / -0.14 |
| Participation | -0.39 / -0.22 | -0.48 / -0.29 |
| Cohesion (Atlas) | -0.26 / -0.18 | -0.24 / -0.17 |
| Rootedness | -0.20 / -0.20 | -0.06 / -0.15 |
| Civic nodes | +0.06 / +0.05 | -0.05 / +0.07 |
| IRS nonprofits per 1k | +0.19 / +0.44 | +0.02 / +0.27 |

Reading: the pillar has the expected sign, but income, education and age alone explain 47% (loneliness) and 57%
(lack of support) of the variance across these ZIP areas, and adding the pillar score moves that by about one
percentage point or less. Civic nodes show no relationship; the registered-nonprofit rate points the wrong way after
controls (more nonprofits per 1,000 with more loneliness), which needs a closer look. Rootedness and cohesion point the
right way. Limits: PLACES values are modeled from demographics, so this test mostly reflects demographic structure; a
partial result near -0.15 is weak evidence of independent signal, not proof. No weights were changed on this basis.

## IRS coverage follow-up (applied 2026-10-24)
- Code: `irs_bmf.state_has_coverage` (a state needs at least 30 tracts in the IRS files), `get_civic_orgs_per_1k` returns None
  for uncovered states, `community_participation.blend_participation` (no silent 50.0), pillar reports `irs_bmf_status` and
  flags degraded. Tests added (493 passed, one unrelated election-file test deselected).
- Catalog: 252 places in NC (72), IL (97), PA (73), IN (6), MD (1) and DE (3) now use volunteering plus the Atlas civic-organization
  rate for participation (participation delta mean +0.36, range -8.9 to +14.9). Social fabric score changed for 248 (mean +0.22,
  range -5.7 to +8.9; 102 places moved more than 2 points); total_score mean +0.015 (range -0.44 to +0.69); longevity changed for 248
  (mean +0.07), happiness for 238 (mean +0.06), aura for 174. Two Philadelphia-area places were skipped by design (Radnor already
  volunteering-only; Yardley's tract is in a covered state). Delaware was added to the nine states you named because its IRS data is
  also absent.
- Backups: `data/backups_social_fabric_irs_2026-10-24/`. The IRS data and baselines were not rebuilt.

