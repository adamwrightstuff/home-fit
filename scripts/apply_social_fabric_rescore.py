#!/usr/bin/env python3
"""
Apply re-scored Social Fabric values to a catalog with full cascade into the
dependent composites (total_score, happiness_index, longevity_index). All three
are linear in the pillar score (verified: longevity factor constant 0.408,
happiness social weight 0.30, total contribution = score*weight/100), so each
place's own stored weights/factors reproduce its totals exactly.

Only places present in the clean rescore file are updated; quarantined / missing
places pass through untouched. Writes to a NEW file (review the diff before shipping).
"""
from __future__ import annotations

import json
import os
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "data/nyc_metro_place_catalog_scores_merged.jsonl"
OUT = sys.argv[2] if len(sys.argv) > 2 else SRC.replace(".jsonl", ".v14.jsonl")
RESCORE = "data/social_fabric_rescore.jsonl"


def load_rescore():
    by_name = {}
    for line in open(RESCORE):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("reliability") == "ok":
            by_name[r["name"]] = r
    return by_name


def apply_cascade(sc, new):
    """Mutate one place's score dict in place. Returns (old_total, new_total)."""
    lp = sc["livability_pillars"]["social_fabric"]
    old_sf = lp["score"]
    new_sf = new["new"]

    # --- pillar ---
    weight = lp["weight"]
    lp["score"] = new_sf
    lp["contribution"] = round(new_sf * weight / 100.0, 4)
    # enrich breakdown with the new two-morphology channels (stability/civic/engagement
    # stay as stored; they're unchanged inputs)
    bd = lp.setdefault("breakdown", {})
    bd["cohesion"] = new.get("cohesion")
    bd["bonding_cohesion"] = new.get("bond")
    bd["infrastructure_density"] = new.get("infra")
    lp.setdefault("summary", {})["civic_node_count_rescored"] = new.get("civic_nodes")
    lp["_rescore_version"] = "v14_two_morphology"

    # --- total_score ---
    tsb = sc["total_score_breakdown"]["social_fabric"]
    old_contrib = tsb["contribution"]
    new_contrib = round(new_sf * tsb["weight"] / 100.0, 4)
    tsb["score"] = new_sf
    tsb["contribution"] = new_contrib
    old_total = sc["total_score"]
    sc["total_score"] = round(old_total - old_contrib + new_contrib, 4)

    # --- happiness_index (social component, weight from component_weights) ---
    hb = sc.get("happiness_index_breakdown")
    if hb and "social" in hb:
        w_soc = hb.get("component_weights", {}).get("social", 0.3)
        old_soc = hb["social"]
        hb["social"] = new_sf
        sc["happiness_index"] = round(
            sc.get("happiness_index", 0) - w_soc * old_soc + w_soc * new_sf, 4
        )

    # --- longevity_index (linear factor = old_contrib / old_score) ---
    lb = sc.get("longevity_index_breakdown")
    if lb and "social_fabric" in lb and old_sf:
        factor = lb["social_fabric"] / old_sf
        old_l = lb["social_fabric"]
        new_l = round(new_sf * factor, 4)
        lb["social_fabric"] = new_l
        if "social_fabric" in sc.get("longevity_index_contributions", {}):
            sc["longevity_index_contributions"]["social_fabric"] = new_l
        sc["longevity_index"] = round(sc.get("longevity_index", 0) - old_l + new_l, 4)

    return old_total, sc["total_score"]


def main():
    rescore = load_rescore()
    n_upd = n_skip = 0
    shifts = []
    with open(OUT, "w") as out_f:
        for line in open(SRC):
            try:
                row = json.loads(line)
            except Exception:
                out_f.write(line)
                continue
            name = row.get("catalog", {}).get("name", "")
            sc = row.get("score", {})
            if name in rescore and sc.get("livability_pillars", {}).get("social_fabric"):
                old_sf = sc["livability_pillars"]["social_fabric"]["score"]
                apply_cascade(sc, rescore[name])
                new_sf = sc["livability_pillars"]["social_fabric"]["score"]
                shifts.append((name, old_sf, new_sf))
                n_upd += 1
            else:
                n_skip += 1
            out_f.write(json.dumps(row) + "\n")

    print(f"Wrote {OUT}")
    print(f"Updated {n_upd} places (cascade), passed through {n_skip} (quarantined/missing).")
    import statistics
    if shifts:
        deltas = [b - a for _, a, b in shifts]
        print(f"social_fabric mean {statistics.mean(a for _, a, _ in shifts):.1f} -> "
              f"{statistics.mean(b for _, _, b in shifts):.1f}  (mean |delta| {statistics.mean(abs(d) for d in deltas):.1f})")


if __name__ == "__main__":
    main()
