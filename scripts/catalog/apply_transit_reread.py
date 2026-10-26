#!/usr/bin/env python3
"""
Apply a re-read of public_transit_access for catalog places that scored 0 with no routes or carried the retired
fallback score (`fallback_applied`). Input is a JSON of {"<metro>|<name>": {"score": ..., "det": {...}}} produced by
get_public_transit_score with the fail-loud rules (a failed read raises and is not written here).

A re-read that finds service replaces the pillar's score, breakdown, summary, details, data_quality and confidence. A
re-read that confirms no service keeps score 0, replaces breakdown and summary (so `no_service_found` shows and any
fallback marker disappears) and adds the `no_transit_routes_found` warning. Contribution and total_score follow by the
delta method. Run recompute_catalog_composites.py --no-census on the changed rows afterwards.

  PYTHONPATH=. python3 -I scripts/catalog/apply_transit_reread.py --results <json> --backup-dir <dir>
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
    ap.add_argument("--results", required=True)
    ap.add_argument("--backup-dir", required=True)
    a = ap.parse_args()
    res = {k: v for k, v in json.loads(Path(a.results).read_text()).items() if "det" in v}
    n_service = n_zero = 0
    for path in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(path).split("_metro")[0]
        out, old_vals, mtime = [], {}, os.path.getmtime(path)
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            s = rec.get("score") or {}
            P = s.get("livability_pillars") or {}
            t = P.get("public_transit_access")
            key = f"{metro}|{(rec.get('catalog') or {}).get('name')}"
            r = res.get(key)
            if not t or t.get("score") is None or not r:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            old_vals[key] = {"public_transit_access": json.loads(json.dumps(t)), "total_score": old_total}
            det = r["det"]
            if r["score"] > 0:
                for f in ("breakdown", "summary", "details"):
                    if f in det:
                        t[f] = det[f]
                t["data_quality"] = det.get("data_quality") or t.get("data_quality")
                t["confidence"] = (t["data_quality"] or {}).get("confidence", t.get("confidence"))
                n_service += 1
            else:
                t["breakdown"], t["summary"] = det["breakdown"], det["summary"]
                dq = t.get("data_quality") or {}
                dq["data_warnings"] = list(dict.fromkeys(list(dq.get("data_warnings") or []) + ["no_transit_routes_found"]))
                t["data_quality"] = dq
                n_zero += 1
            t["score"] = r["score"]
            if isinstance(t.get("weight"), (int, float)):
                t["contribution"] = round(t["weight"] * t["score"] / 100.0, 4)
            tb = (s.get("total_score_breakdown") or {}).get("public_transit_access")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = t["score"], t["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
            out.append(json.dumps(rec, ensure_ascii=False))
        if old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            dst = b / os.path.basename(path)
            if not dst.exists():
                shutil.copy2(path, dst)
            (b / f"{metro}_old_transit_reread_values.json").write_text(json.dumps(old_vals))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print(f"service found {n_service} | confirmed no service {n_zero}")


if __name__ == "__main__":
    main()
