#!/usr/bin/env python3
"""
Offline: store no-data pillars in the stored-gap shape (score None, contribution 0.0) so totals redistribute.

Rows written with contribution None for a pillar that has no score and a positive weight (community_safety
no_data, neighborhood_amenities whose fabricated score was nullified) were not treated as gaps by the total-score
logic, so their totals were understated by about 4 points. This sets contribution 0.0 (also in
total_score_breakdown) and lists the rows; run recompute_catalog_composites.py --no-census on them afterwards
(the driver in the docs does this per metro file).

  PYTHONPATH=. python3 scripts/catalog/recompute_nodata_gap_shape_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_nodata_gap_shape_offline.py --write --backup-dir <dir>
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    hits = []
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        out, old_vals = [], {}
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            try:
                rec = json.loads(line)
            except Exception:
                out.append(line)
                continue
            s = rec.get("score") or {}
            P = s.get("livability_pillars") or {}
            fixed = [k for k, v in P.items() if isinstance(v, dict) and v.get("score") is None
                     and v.get("contribution") is None and (v.get("weight") or 0) > 0]
            if not fixed:
                out.append(line)
                continue
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            for k in fixed:
                P[k]["contribution"] = 0.0
                tb = (s.get("total_score_breakdown") or {}).get(k)
                if isinstance(tb, dict):
                    tb["contribution"] = 0.0
            hits.append((metro, cat.get("name"), fixed, s.get("total_score")))
            old_vals[f"{metro}|{cat.get('name')}"] = {"pillars": fixed, "total_score": s.get("total_score")}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_gap_rows.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| rows:", len(hits))
    for h in hits:
        print("  ", h[0], h[1], h[2], "total", h[3])


if __name__ == "__main__":
    main()
