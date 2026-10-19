#!/usr/bin/env python3
"""
Turn on quality_education in the catalog default weighting.

The catalog already holds real, high-confidence education scores (status=success,
confidence=85, e.g. Ardsley 92, Astoria 67) — but every place carries weight=0 for the
pillar, so a top home-buying signal contributes nothing to rankings. This was the
schools-disabled weight override (main.py _apply_schools_disabled_weight_override) zeroing
the pillar even though the data was computed. Since the scores exist, enabling the weight
is a free offline reweight — no re-fetch.

Education feeds only total_score (happiness/longevity don't reference it; status_signal's
'education' is a separate census-attainment input, not this pillar). So the cascade is:
add quality_education to each place's active pillar set, renormalize equal weights to 100,
recompute every pillar's contribution and the total.

Backup .bakEdu. Usage: python3 scripts/catalog/enable_education_weight.py

Re-run after any education rescore: the live /score call used by the rescore runners returns
weight 0 for the pillar and overwrites the catalog weight.
"""
from __future__ import annotations

import json
import os
import shutil

CATALOGS = [
    f"data/{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    for m in ("nyc", "la", "sf", "seattle", "austin", "chicago", "philadelphia", "dallas", "houston")
]
EDU = "quality_education"
# The 13 default pillars. A null score on one of these is a data gap: it keeps its weight with
# contribution 0 and the total is scaled by 100/(100 - gap weight), so the place is not penalised
# (same convention check_catalog_health.py uses for total_score drift).
STANDARD = {
    "active_outdoors", "natural_beauty", "neighborhood_amenities", "air_travel_access",
    "public_transit_access", "healthcare_access", "economic_opportunity", "quality_education",
    "housing_value", "climate_risk", "social_fabric", "diversity", "community_safety",
}


def reweight(sc: dict) -> tuple[float, float] | None:
    lp = sc.get("livability_pillars", {})
    edu = lp.get(EDU) or {}
    # no usable signal (failed lookup / no rated schools): leave education out of the total
    if not edu.get("score") or (edu.get("confidence") or 0) < 1:
        return None
    # active = pillars that currently carry weight, plus education (preserves any
    # per-place dropping of null pillars like a missing community_safety).
    active = [p for p, v in lp.items()
              if (v.get("weight") or 0) > 0 or (p in STANDARD and p != EDU and v.get("score") is None)]
    if EDU not in active:
        active.append(EDU)
    w = 100.0 / len(active)
    old_total = sc.get("total_score")

    tsb = sc.get("total_score_breakdown", {})
    new_total = 0.0
    gap_w = 0.0
    for p in lp:
        v = lp[p]
        score = v.get("score")
        if p in active and score is not None:
            v["weight"] = w
            v["contribution"] = round(score * w / 100.0, 4)
            new_total += score * w / 100.0
        elif p in active:  # data gap on a default pillar
            v["weight"] = w
            v["contribution"] = 0.0
            gap_w += w
        else:
            v["weight"] = 0.0
            v["contribution"] = 0.0
        if p in tsb:
            tsb[p]["weight"] = v["weight"]
            tsb[p]["score"] = score if score is not None else tsb[p].get("score")
            tsb[p]["contribution"] = v["contribution"]
    if gap_w > 0:
        new_total = new_total * 100.0 / (100.0 - gap_w)
    sc["total_score"] = round(min(100.0, new_total), 4)
    lp[EDU]["_rescore_version"] = "education_weight_enabled"
    return old_total, sc["total_score"]


def main():
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakEdu")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line)
                    continue
                if reweight(row.get("score", {})):
                    n += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: reweighted {n} places (backup: {fn}.bakEdu)", flush=True)


if __name__ == "__main__":
    main()
