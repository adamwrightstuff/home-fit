#!/usr/bin/env python3
"""
Write re-read active outdoors results (from get_active_outdoors_score_v2 run against the private Overpass) into the
catalog for places whose first read had a failed Overpass component. Input is a JSON of {"<metro>|<name>": {"new": score,
"det": details}}. Replaces the pillar's score, breakdown, summary, data_quality, area_classification and version, updates
contribution and total_score (delta method), and backs up each changed file. Run recompute_catalog_composites.py
--no-census on the changed rows afterwards.

  PYTHONPATH=. python3 scripts/catalog/apply_active_outdoors_retry.py --results <json> --backup-dir <dir>
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
FIELDS = ("breakdown", "summary", "data_quality", "area_classification", "confidence_notes", "version")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--backup-dir", required=True)
    a = ap.parse_args()
    res = json.loads(Path(a.results).read_text())
    n = 0
    for path in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(path).split("_metro")[0]
        out, old_vals, mtime = [], {}, os.path.getmtime(path)
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            name = (rec.get("catalog") or {}).get("name")
            r = res.get(f"{metro}|{name}")
            s = rec.get("score") or {}
            ao = (s.get("livability_pillars") or {}).get("active_outdoors")
            if not r or not ao or r["new"] is None:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in s["livability_pillars"].values() if isinstance(v, dict))
            old_total = s.get("total_score")
            old_vals[f"{metro}|{name}"] = {"active_outdoors": json.loads(json.dumps(ao)), "total_score": old_total}
            for k in FIELDS:
                if k in r["det"]:
                    ao[k] = r["det"][k]
            ao["score"] = r["new"]
            if isinstance(ao.get("weight"), (int, float)):
                ao["contribution"] = round(ao["weight"] * r["new"] / 100.0, 4)
            tb = (s.get("total_score_breakdown") or {}).get("active_outdoors")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = ao["score"], ao.get("contribution")
            new_sum = sum((v.get("contribution") or 0) for v in s["livability_pillars"].values() if isinstance(v, dict))
            if old_total is not None and abs(new_sum - old_sum) > 1e-9:
                s["total_score"] = round(new_sum, 2) if abs(round(old_sum, 2) - old_total) <= 0.0051 else round(old_total + (new_sum - old_sum), 2)
            n += 1
            out.append(json.dumps(rec, ensure_ascii=False))
        if old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            dst = b / os.path.basename(path)
            if not dst.exists():
                shutil.copy2(path, dst)
            (b / f"{metro}_old_active_outdoors_retry_values.json").write_text(json.dumps(old_vals))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print("rows rewritten", n)


if __name__ == "__main__":
    main()
