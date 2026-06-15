#!/usr/bin/env python3
"""
Repair pass after the anomaly sweep + a normalization bug introduced by the education
reweight:

1. Maspeth diversity=0 was a transient census failure; it now resolves consistently to
   72.5 across 5 retries. Apply it.
2. Southport diversity=0 is persistent: the pillar's tract lookup fails and the
   county_subdivision fallback returns zero population, so it can't resolve. Mark it
   no-data (score=None, weight 0) rather than leaving a fabricated 0 dragging the total.
   (The diversity pillar's geography-fallback chain is the real fix — tracked separately.)
3. Weight normalization: enable_education_weight counted pillars that had a weight but a
   null score (community_safety on the COMING_SOON places) in the divisor, then zeroed
   them — so those 4 places summed to 92.86%, not 100. Renormalize EVERY place over its
   actually-scored pillars: active = pillars with a non-null score (political_lean
   excluded, always null). w = 100/len(active); recompute contributions + total_score.

This is a no-op for the ~287 already-correct places and corrects the rest. Backup .bakRepair.
"""
from __future__ import annotations

import json
import os
import shutil

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
EXCLUDE = {"political_lean"}  # always null / disabled


def renormalize(sc: dict):
    lp = sc.get("livability_pillars", {})
    active = [p for p, v in lp.items() if p not in EXCLUDE and v.get("score") is not None]
    w = 100.0 / len(active) if active else 0.0
    tsb = sc.get("total_score_breakdown", {})
    total = 0.0
    for p, v in lp.items():
        if p in active:
            v["weight"] = w
            v["contribution"] = round(v["score"] * w / 100.0, 4)
            total += v["score"] * w / 100.0
        else:
            v["weight"] = 0.0
            v["contribution"] = 0.0
        if p in tsb:
            tsb[p]["weight"] = v["weight"]
            tsb[p]["contribution"] = v["contribution"]
    sc["total_score"] = round(total, 4)


def main():
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakRepair")
        tmp = fn + ".new"
        n_renorm = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line)
                    continue
                nm = row.get("catalog", {}).get("name", "")
                sc = row.get("score", {})
                lp = sc.get("livability_pillars", {})
                div = lp.get("diversity")
                if nm == "Maspeth" and div:
                    div["score"] = 72.5
                    div["confidence"] = 85
                    div["status"] = "success"
                    div["_rescore_version"] = "diversity_transient_refetch"
                elif nm == "Southport" and div:
                    div["score"] = None
                    div["confidence"] = 0
                    div["status"] = "degraded"
                    div["_rescore_version"] = "diversity_nodata_unresolvable"
                if sc:
                    renormalize(sc)
                    n_renorm += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: renormalized {n_renorm} places (backup: {fn}.bakRepair)", flush=True)


if __name__ == "__main__":
    main()
