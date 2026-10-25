# Pillar Deep-Dive: Active Outdoors

How `pillars/active_outdoors.py` scores a location (`get_active_outdoors_score_v2`).

## What it measures
Access to outdoor recreation, on three objective components (same 0–100 scale as the
Natural-Beauty-style pillars):

| component | signal |
|---|---|
| **daily urban outdoors** | parks, playgrounds, recreational facilities nearby |
| **wild adventure** | trails / wilderness / large natural areas reachable |
| **water lifestyle** | water-based recreation access |

Each is scored relative to area-type expectations, then combined. Inputs are OSM/Places
features for parks, trails, playgrounds, rec facilities, and water.

## Gotchas
- Area-type-relative — a dense urban park-rich neighborhood and a trail-rich exurb can both
  score well for different reasons (daily vs wild).
- Distinct from Natural Beauty: this is about *doing* things outdoors (recreation access), not
  scenic quality.

## Scaling and failed reads (changed 2026-10-25)
The three component budgets (daily 35, wild 50, water 25) summed to 110 and the total was clipped at 100, so 15% of
catalog places sat at exactly 100. The total is now the sum scaled by 100/110 (no clip), a documented judgment that keeps
the budget ratios. A component whose Overpass read failed (error or timeout; for the local-park read in a populated area
type, also an empty result) is no data, not zero: the score is rescaled from the components that read, the pillar is marked
degraded (`active_outdoors_missing_components`), and fewer than two components means no score. Exurban and rural places with
zero local parks are still treated as a real zero. Catalog: 1,476 rows rescored offline by
`scripts/catalog/recompute_active_outdoors_budget_offline.py` (mean 78.5 to 72.3; share at 100 from 15.2% to 0.5%; 45 places
degraded), then composites recomputed.

The 45 places with a failed read were then re-read through the private Overpass server (all components read) and written back by `scripts/catalog/apply_active_outdoors_retry.py`; none is degraded now.
