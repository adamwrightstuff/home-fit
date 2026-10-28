#!/usr/bin/env python3
"""
Offline: replace the single-tract housing value score of tract-level catalog places with the pooled score (D14).

Reads analysis/audit_housing_d14_areal_places.jsonl (written by analysis/audit_housing_d14_scripts/pool_areal_checks.py
from the cached Census state pull). The pooled score is the stored score plus (pooled minus single-tract rebuild), so
the Zillow override and metro multiplier already in the stored score are kept and only the pooling effect is added.
Pool: tracts containing the pin or any of 8 ring points at 700 m (0.43 mile), occupied-unit weighted. Sub-scores in
the breakdown stay single-tract and are labelled in summary.pooling; only the total, contribution and the
total_score_breakdown entry change. Run recompute_catalog_composites.py --no-census afterwards for the composites.

  PYTHONPATH=. python3 scripts/catalog/recompute_housing_pooled_offline.py                          # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_housing_pooled_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RADIUS = 700


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--pooled", default=str(ROOT / "analysis" / "audit_housing_d14_areal_places.jsonl"))
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    pooled = {}
    for l in Path(a.pooled).read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            pooled[(r["metro"], r["name"])] = r
    done, skipped, moves = 0, [], []
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out, changed = [], False
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            s = rec.get("score") or {}
            h = (s.get("livability_pillars") or {}).get("housing_value")
            p = pooled.get((metro, (rec.get("catalog") or {}).get("name")))
            if p and isinstance(h, dict) and (h.get("summary") or {}).get("pooling"):   # already pooled: start from the original
                h["score"] = h["summary"]["pooling"]["single_tract_score"]
            ok = (p and isinstance(h, dict) and h.get("score") is not None and (h.get("summary") or {}).get("geo_level") == "tract"
                  and abs(h["score"] - p["stored"]) < 0.05 and p.get(f"pooled_{RADIUS}") is not None)
            if not ok:
                if p:
                    skipped.append((metro, p["name"]))
                out.append(line)
                continue
            new = round(min(100.0, max(0.0, h["score"] + p[f"pooled_{RADIUS}"] - p["rebuilt"])), 1)
            moves.append(new - h["score"])
            h["summary"]["pooling"] = {"radius_m": RADIUS, "rule": "pin plus 8 ring points", "weights": "occupied units",
                                       "tracts_in_pool": p.get(f"tracts_{RADIUS}"), "single_tract_score": h["score"],
                                       "breakdown_is_single_tract": True}
            h["score"] = new
            h["contribution"] = round(new * (h.get("weight") or 0) / 100.0, 4)
            tb = (s.get("total_score_breakdown") or {}).get("housing_value")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = new, h["contribution"]
            out.append(json.dumps(rec, ensure_ascii=False))
            done += 1
            changed = True
        if a.write and changed:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            bd = Path(a.backup_dir)
            bd.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, bd / os.path.basename(path))
            Path(path).write_text("\n".join(out), encoding="utf-8")
    ab = sorted(abs(m) for m in moves)
    print(f"{'WROTE' if a.write else 'dry run'}: {done} places updated, {len(skipped)} skipped {skipped[:5]}")
    if ab:
        print(f"abs change: median {ab[len(ab)//2]:.1f}, p90 {ab[int(.9*len(ab))]:.1f}, max {ab[-1]:.1f}; over 10: {sum(x > 10 for x in ab)}")
    if a.write:
        print("next: PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --input <file> --in-place --no-census (each metro)")


if __name__ == "__main__":
    main()
