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
