# Pillar Deep-Dive: Social Fabric

How `pillars/social_fabric.py` scores a location (current model `v14_two_morphology`).

## What it measures
The strength of local community — residential stability, civic/organizational engagement, and
social cohesion infrastructure.

## Components
- **Stability** — residential same-house share (ACS `B07003` blended with `B07013`):
  `0.7×tract + 0.3×place`. Higher "lived here a year ago" = more stable community. z-scored vs
  regional baselines (`_score_stability_from_z`).
- **Engagement** — civic/nonprofit organizations per 1k (IRS BMF + community-participation
  data), z-scored (`_score_engagement_from_rate`).
- **Cohesion / infrastructure** — the "two-morphology" channels (civic nodes, bonding vs
  bridging fabric) added in v14.

Normalized against regional baselines (stability baselines per region), combined into 0–100.

## Known pattern (ℹ️ not a bug)
Social fabric **systematically scores low-density affluent areas low** — Westport 33,
Weston 37, Hollywood Hills 23, Larchmont Village 34 (all high-confidence). This is real signal
about walkable community fabric (car-dependent suburbs have fewer third places / civic nodes
within reach), but it **stacks the deck against suburbs** in the overall ranking. Either
accept it as correct, or note that suburban community forms (clubs, HOAs, schools-as-hub) are
under-credited. See PILLAR_DATA_QUALITY.

## Catalog
Rescored offline as `v14_two_morphology` (`scripts/apply_social_fabric_rescore.py`); cascades
total_score + happiness/longevity inputs. See CATALOG_RESCORE_RUNBOOK.
