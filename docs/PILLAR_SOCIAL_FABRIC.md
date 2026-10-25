# Pillar Deep-Dive: Social Fabric

How `pillars/social_fabric.py` scores a location. Current model: v17 fail-loud blend (base weights unchanged
from v16b). Updated 2026-10-24; replaces the older v14 description.

## What it measures
The strength of local community life: organizational engagement and volunteering, bonding cohesion,
residential stability, and walkable civic gathering places.

## Components and base weights
| Component | Base weight | Source |
|---|---|---|
| Participation | 0.60 | Engagement: IRS BMF nonprofits per 1k (area-type baselines) and volunteering, 50/50 (`community_participation`); then 65/35 with the Social Capital Atlas civic-organization rate |
| Cohesion | 0.20 | Social Capital Atlas ZIP clustering and support ratio, peer-normalized by area type |
| Rootedness | 0.10 | Residential stability: 0.8 x ACS B25038 long-tenure housing + 0.2 x B07003 same-house, blended 0.7 tract / 0.3 place, scored against regional bands. The above-85% penalty is suppressed when median home value is at least $350k (F15) |
| Civic | 0.10 | OSM / Google Places civic nodes (library, community centre, worship, clubs, cafes ...) by type weight, peer-normalized by area type; search radius 600 / 1200 / 3000 m by density |

## Fail-loud blend (changed 2026-10-24)
A component that cannot be measured is left out, the remaining base weights are scaled proportionally to
sum to 1 (`pillars/social_fabric_blend.py`), and the pillar is marked degraded with the reason. Nothing is
scored as zero because it is missing. Before this, a missing component handed its weight to participation
(cohesion missing: participation 0.80; civic nodes zero: 0.70) and a missing stability reading counted as 0.
Civic nodes found to be zero are also left out (reported as `no_civic_nodes_found`, not degraded). Fewer than
two components, or no participation, means no score. The response carries `summary.weights_used` and
`summary.components_missing`. 286 of 1,476 catalog places changed score (mean +0.41).

## IRS nonprofit data coverage (changed 2026-10-24)
The IRS tract-count files have no tracts for DE, DC, IL, IN, IA, KY, MD, MI, MN, NC, OH, PA, SC, VA, WV, WI and
almost none for NE, ND, SD (the IRS regional file for them was never ingested). A state counts as covered only if the
files hold at least 30 tracts for it (`irs_bmf.state_has_coverage`). In an uncovered state the nonprofit rate is "no
data", not zero: participation uses volunteering and the Atlas civic-organization rate only
(`participation_mix: vol_only`), `summary.irs_bmf_status` is `no_state_coverage`, and the pillar is marked degraded.
If both inputs are missing there is no participation and no score (the old code returned a made-up 50). Rebuilding
the IRS files makes these states covered again with no code change. The IRS rate also showed no within-metro link to
loneliness in the CDC test and the baseline is dominated by outliers, so it is a weak input even where it exists.

## Caveats
- About 60% of the score comes from one source, the Social Capital Atlas (Facebook friendships). The base
  weights were chosen by validating against that same Atlas, so that validation is circular. Treat the
  weights as a judgment call. See `analysis/pillar_audit_tracker_v2.md`, D7.
- Our components track the Atlas economic connectedness (the measure that best predicts upward mobility)
  only weakly: cohesion 0.24, civic 0.11, rootedness -0.07; participation 0.36, almost all through Atlas
  volunteering. The registered-nonprofit rate has about zero correlation with any Atlas measure.
- Low-density affluent areas tended to score low under earlier versions (fewer walkable third places).
  That pattern was recorded under v14 and has not been re-checked under the current weights.

## Catalog
Rescored offline by `scripts/catalog/recompute_social_fabric_failloud_offline.py`, then
`recompute_catalog_composites.py --no-census` for longevity, happiness and aura.
