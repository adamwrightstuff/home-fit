#!/usr/bin/env python3
"""
Derive the property-crime weight for community_safety from published harm estimates and write
data/community_safety_harm_weights.json.

    property_weight = H_property / (H_violent + H_property)
    H_group         = sum over offenses of (national rate per 100,000 x cost per offense)

Inputs (both published, both in the output file so the derivation can be checked):
- Cost per offense: McCollister, French & Fang (2010), "The cost of crime to society: new
  crime-specific estimates for policy and program evaluation", Drug and Alcohol Dependence 108,
  Table 5 (total cost, 2008 US dollars).  https://pmc.ncbi.nlm.nih.gov/articles/PMC2835847
- Offense rates: BJS, "Criminal Victimization / Crime in the Nation", NIBRS-based national estimates
  for 2023, per 100,000.  https://bjs.ojp.gov/document/ckle23.pdf

The headline weight uses every violent offense including murder.  The file also records the
sensitivity (murder excluded; direct victim cost only) because the answer depends on how murder
is valued.

Usage (from project root):
  PYTHONPATH=. python3 scripts/baselines/derive_community_safety_weight.py
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "community_safety_harm_weights.json")

RATES_PER_100K = {  # BJS NIBRS-based national estimates, 2023
    "murder": 5.9, "rape": 40.1, "aggravated_assault": 273.1, "robbery": 68.7,
    "burglary": 253.4, "larceny_theft": 1431.1, "motor_vehicle_theft": 330.7,
}
TOTAL_COST = {  # McCollister et al. 2010, Table 5, total cost per offense, 2008 USD
    "murder": 8982907, "rape": 240776, "aggravated_assault": 107020, "robbery": 42310,
    "burglary": 6462, "larceny_theft": 3532, "motor_vehicle_theft": 10772,
}
VICTIM_COST = {  # McCollister et al. 2010, Table 3, direct crime-victim cost, 2008 USD
    "murder": 737517, "rape": 5556, "aggravated_assault": 8700, "robbery": 3299,
    "burglary": 1362, "larceny_theft": 480, "motor_vehicle_theft": 6114,
}
VIOLENT = ("murder", "rape", "aggravated_assault", "robbery")
PROPERTY = ("burglary", "larceny_theft", "motor_vehicle_theft")


def property_share(cost: dict, drop=()) -> float:
    hv = sum(RATES_PER_100K[k] * cost[k] for k in VIOLENT if k not in drop)
    hp = sum(RATES_PER_100K[k] * cost[k] for k in PROPERTY)
    return hp / (hv + hp)


def main() -> None:
    weight = property_share(TOTAL_COST)
    out = {
        "_meta": {
            "description": "Weight of the property-crime slot in community_safety, derived from "
                           "published cost-of-crime estimates and national offense rates.",
            "formula": "property_weight = H_property / (H_violent + H_property); "
                       "H = sum(rate_per_100k x cost_per_offense)",
            "cost_source": "McCollister, French & Fang (2010), Drug and Alcohol Dependence 108, Table 5",
            "rate_source": "BJS NIBRS-based national estimates, 2023",
            "rebuild": "PYTHONPATH=. python3 scripts/baselines/derive_community_safety_weight.py",
        },
        "property_weight": round(weight, 3),
        "sensitivity": {
            "total_cost_murder_excluded": round(property_share(TOTAL_COST, ("murder",)), 3),
            "victim_cost_only": round(property_share(VICTIM_COST), 3),
            "victim_cost_only_murder_excluded": round(property_share(VICTIM_COST, ("murder",)), 3),
        },
        "inputs": {"rates_per_100k": RATES_PER_100K, "total_cost_2008usd": TOTAL_COST,
                   "victim_cost_2008usd": VICTIM_COST},
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(f"property_weight = {out['property_weight']}  sensitivity = {out['sensitivity']}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
