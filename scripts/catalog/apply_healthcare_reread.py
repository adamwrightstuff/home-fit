#!/usr/bin/env python3
"""
Apply a re-read of healthcare_access for catalog places whose first read had failed (stored confidence 10 or less, the
cap the old scorer applied after a failed Overpass query).

Input is a JSON of {"<metro>|<name>": {"score": ..., "det": {...}}} produced by calling get_healthcare_access_score
through the private Overpass server. A re-read is only trusted for metros whose state the private server covers
(--covered-metros); an empty answer from a state it does not cover is missing data, not zero facilities. Every other
failed-read row is set to no data in the stored-gap shape (score None, contribution 0.0, status no_data) so the total
redistributes its weight; run recompute_catalog_composites.py --no-census on the changed rows afterwards.

  PYTHONPATH=. python3 -I scripts/catalog/apply_healthcare_reread.py --results <json> --covered-metros a,b --backup-dir <dir>
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
FIELDS = ("breakdown", "bonuses", "summary", "data_quality", "area_classification", "places_augmentation")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--covered-metros", required=True)
    ap.add_argument("--backup-dir", required=True)
    a = ap.parse_args()
    res = json.loads(Path(a.results).read_text())
    covered = set(a.covered_metros.split(","))
    n_new = n_gap = 0
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
            h = P.get("healthcare_access")
            name = (rec.get("catalog") or {}).get("name")
            key = f"{metro}|{name}"
            if not h or h.get("score") is None or (h.get("confidence") or 0) > 10:
                out.append(line)
                continue
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            old_vals[key] = {"healthcare_access": json.loads(json.dumps(h)), "total_score": old_total}
            r = res.get(key)
            if metro in covered and r and "det" in r:
                for f in FIELDS:
                    if f in r["det"]:
                        h[f] = r["det"][f]
                h["score"] = r["score"]
                h["confidence"] = (h.get("data_quality") or {}).get("confidence", h.get("confidence"))
                if isinstance(h.get("weight"), (int, float)):
                    h["contribution"] = round(h["weight"] * h["score"] / 100.0, 4)
                n_new += 1
            else:
                h["score"], h["contribution"], h["confidence"], h["status"] = None, 0.0, 0, "no_data"
                dq = h.get("data_quality") or {}
                dq["degraded"] = True
                dq["degraded_reasons"] = list(dict.fromkeys(list(dq.get("degraded_reasons") or []) + ["healthcare_read_failed_not_yet_retried"]))
                h["data_quality"] = dq
                n_gap += 1
            tb = (s.get("total_score_breakdown") or {}).get("healthcare_access")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = h["score"], h["contribution"]
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
            (b / f"{metro}_old_healthcare_reread_values.json").write_text(json.dumps(old_vals))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print(f"re-read applied {n_new} | set to no data {n_gap}")


if __name__ == "__main__":
    main()
