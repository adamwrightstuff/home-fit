#!/usr/bin/env python3
"""
Offline: recompute air_travel_access for the vacation destination records under the current nonstop-coverage model.

The vacation file predates the rebuild (no drive minutes, old airport list), so minutes come from the fitted
distance estimate (no routed times exist for vacation pins). Writes a NEW file; the input is not modified.
total_score is the weight-averaged pillar score (reproduces the stored value for all 49 records), so it is recomputed
the same way.

  PYTHONPATH=. python3 -I scripts/catalog/recompute_vacation_air_travel_offline.py --out <new.jsonl>
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from pillars.air_travel_access import score_location  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "data" / "vacation_destinations_scores.jsonl"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if Path(a.out).exists():
        sys.exit(f"{a.out} exists; refusing to overwrite")
    out, report = [], []
    for line in Path(a.input).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        co = (r.get("score_data") or {}).get("coordinates") or {}
        p = (r.get("pillars") or {}).get("air_travel_access")
        sp = ((r.get("score_data") or {}).get("livability_pillars") or {}).get("air_travel_access")
        if not (p and sp and co.get("lat") is not None):
            out.append(json.dumps(r, ensure_ascii=False))
            continue
        old_air, old_total = p["score"], r["total_score"]
        new, bd, _ = score_location(co["lat"], co["lon"])
        for k in ("primary_airport", "nearest_airports", "summary", "method"):
            sp[k] = bd[k]
        sp["score"] = p["score"] = new
        if isinstance(sp.get("weight"), (int, float)):
            sp["contribution"] = round(sp["weight"] * new / 100.0, 4)
        tw = sum(v["weight"] for v in r["pillars"].values())
        r["total_score"] = round(sum(v["weight"] * v["score"] for v in r["pillars"].values()) / tw, 1)
        if "total_score" in r["score_data"]:
            r["score_data"]["total_score"] = r["total_score"]
        report.append((r["location"], old_air, new, old_total, r["total_score"],
                       (bd.get("primary_airport") or {}).get("code")))
        out.append(json.dumps(r, ensure_ascii=False))
    Path(a.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    d = [x[2] - x[1] for x in report]
    print(f"rows {len(report)} | air delta mean {st.mean(d):.1f} min {min(d):.1f} max {max(d):.1f} | "
          f"total delta mean {st.mean(x[4]-x[3] for x in report):.2f}")
    for loc, o, n, ot, nt, ap_ in sorted(report, key=lambda x: x[2] - x[1])[:8]:
        print(f"  {loc}: air {o} -> {n} ({ap_}), total {ot} -> {nt}")


if __name__ == "__main__":
    main()
