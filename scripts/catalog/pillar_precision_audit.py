#!/usr/bin/env python3
"""
Which pillars limit happiness index precision? Offline audit of stored catalog scores.

Per pillar: places scored, share failed / low confidence / degraded / using fallback, share at the
ceiling (>= 99.5) or floor (<= 0.5), and score spread (SD, interquartile range). A pillar that sits at
a ceiling or relies on fallbacks cannot separate nearby places well.

  PYTHONPATH=. python3 scripts/catalog/pillar_precision_audit.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
FILES = ["nyc", "la", "sf"]
IN_INDEX = ["social_fabric", "community_safety", "housing_value", "natural_beauty", "economic_opportunity",
            "active_outdoors", "climate_risk", "public_transit_access", "neighborhood_amenities"]
OTHER = ["quality_education", "healthcare_access", "diversity", "air_travel_access"]


def main():
    rows = []
    for f in FILES:
        for line in (REPO / "data" / f"{f}_metro_place_catalog_scores_merged.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("success"):
                    rows.append(r["score"]["livability_pillars"])
    n = len(rows)
    print(f"{n} places (NYC, LA, SF)\n")
    hdr = f"{'pillar':<24}{'scored':>7}{'failed':>8}{'lowconf':>9}{'degrad':>8}{'fallbk':>8}{'ceiling':>9}{'floor':>7}{'SD':>7}{'IQR':>7}"
    for title, names in (("IN THE HAPPINESS INDEX", IN_INDEX), ("NOT IN THE INDEX", OTHER)):
        print(title); print(hdr)
        for k in names:
            sc, failed, low, deg, fb = [], 0, 0, 0, 0
            for p in rows:
                d = p.get(k) or {}
                s = d.get("score")
                if d.get("status") == "failed" or (d.get("confidence") == 0 and s == 0) or not isinstance(s, (int, float)):
                    failed += 1
                    continue
                sc.append(float(s))
                c = d.get("confidence")
                if isinstance(c, (int, float)) and c < 50:
                    low += 1
                dq = d.get("data_quality") if isinstance(d.get("data_quality"), dict) else {}
                if dq.get("degraded") or d.get("degraded"):
                    deg += 1
                if dq.get("fallback_used") or dq.get("needs_fallback"):
                    fb += 1
            a = np.array(sc) if sc else np.array([np.nan])
            m = len(sc)
            q = np.percentile(a, [25, 75])
            print(f"{k:<24}{m:>7}{failed/n:>8.0%}{low/max(m,1):>9.0%}{deg/max(m,1):>8.0%}{fb/max(m,1):>8.0%}"
                  f"{(a>=99.5).mean():>9.0%}{(a<=0.5).mean():>7.0%}{a.std():>7.1f}{q[1]-q[0]:>7.1f}")
        print()


if __name__ == "__main__":
    main()
