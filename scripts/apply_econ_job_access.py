#!/usr/bin/env python3
"""
Blend job-accessibility into the catalog's economic_security scores.

economic_security now = 0.55 * job_access (reachable job market, gravity over LODES) +
0.45 * market_quality (the existing CBSA labor-market score). This fixes wrong-CBSA anchoring
(Greenwich anchors to NYC, not Bridgeport) and adds within-metro differentiation by proximity
to jobs (Harlem high), while NOT using resident outcomes (those belong to status_signal).

Fully offline + deterministic: job_access comes from the LODES parquet (no network), and the
stored economic_security score IS the market_quality term (it predates this blend). Cascades
total_score (economic_security feeds total_score; also a longevity input — recomputed if present).

Backup .bakEcon. Usage: python3 scripts/apply_econ_job_access.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources.job_accessibility import job_access_score  # noqa: E402

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
PILLAR = "economic_security"
W_ACCESS = 0.55
VERSION = "econ_job_access_blend"


def main():
    shifts = []
    n_nocover = 0
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakEcon")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as out:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    out.write(line)
                    continue
                cat = row.get("catalog", {})
                sc = row.get("score", {})
                ta = sc.get("livability_pillars", {}).get(PILLAR)
                if ta and ta.get("_rescore_version") != VERSION:
                    quality = ta.get("score")
                    try:
                        access = job_access_score(float(cat["lat"]), float(cat["lon"]))
                    except Exception:
                        access = None
                    if access is not None and quality is not None:
                        new = round(W_ACCESS * access + (1 - W_ACCESS) * quality, 1)
                        old = quality
                        w = ta.get("weight") or 0.0
                        ta["score"] = new
                        ta["contribution"] = round(new * w / 100.0, 4)
                        ta["_rescore_version"] = VERSION
                        ta.setdefault("summary", {})["job_access_score"] = access
                        ta.setdefault("summary", {})["market_quality_score"] = round(old, 1)
                        tsb = sc.get("total_score_breakdown", {}).get(PILLAR)
                        if tsb:
                            oc = tsb["contribution"]
                            nc = round(new * (tsb.get("weight") or 0.0) / 100.0, 4)
                            tsb["score"] = new
                            tsb["contribution"] = nc
                            sc["total_score"] = round(sc["total_score"] - oc + nc, 4)
                        # longevity input (linear factor), if economic_security is in it
                        lb = sc.get("longevity_index_breakdown", {})
                        if isinstance(lb, dict) and PILLAR in lb and old:
                            factor = lb[PILLAR] / old
                            old_l = lb[PILLAR]
                            new_l = round(new * factor, 4)
                            lb[PILLAR] = new_l
                            if PILLAR in (sc.get("longevity_index_contributions", {}) or {}):
                                sc["longevity_index_contributions"][PILLAR] = new_l
                            if sc.get("longevity_index") is not None:
                                sc["longevity_index"] = round(sc["longevity_index"] - old_l + new_l, 4)
                        shifts.append((cat.get("name", ""), old, new, access))
                        n += 1
                    elif access is None:
                        n_nocover += 1
                out.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: blended {n} places (backup: {fn}.bakEcon)", flush=True)
    if n_nocover:
        print(f"  {n_nocover} places had no LODES coverage (kept market-quality score)", flush=True)
    import numpy as np
    d = np.array([nw - o for _, o, nw, _ in shifts])
    print(f"\nΔ mean={d.mean():+.1f} min={d.min():+.0f} max={d.max():+.0f}", flush=True)
    print("biggest rises (wrong-CBSA fixes):")
    for nm, o, nw, a in sorted(shifts, key=lambda x: x[2] - x[1], reverse=True)[:8]:
        print(f"   {nm:18s} {o:5.1f} -> {nw:5.1f}  (access {a})", flush=True)


if __name__ == "__main__":
    main()
