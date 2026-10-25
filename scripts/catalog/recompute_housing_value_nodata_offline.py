#!/usr/bin/env python3
"""
Offline: mark catalog places whose housing value score was invented or built on a missing input as no data.

Targets exactly two stored patterns: summary.fallback_applied (a hard-coded score by area type, used when the
tract has no median household income) and a scored pillar with no median room count (space and value
efficiency were scored as 0, leaving affordability alone). The pillar becomes no data in the catalog's
stored-gap shape (score None, contribution 0.0, confidence 0, status no_data) so the composites cascade
(recompute_catalog_composites.py --no-census, rows listed in the printed queries) redistributes its weight.

  PYTHONPATH=. python3 scripts/catalog/recompute_housing_value_nodata_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_housing_value_nodata_offline.py --write --backup-dir <dir>
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


def reason_for(h: dict):
    s = h.get("summary") or {}
    if s.get("fallback_applied"):
        return "median_household_income_unavailable_for_tract"
    if h.get("score") is not None and not s.get("median_rooms"):
        return "median_rooms_unavailable"
    return None


def make_no_data(h: dict, reason: str) -> None:
    h["score"] = None
    h["contribution"] = 0.0
    h["confidence"] = 0
    h["status"] = "no_data"
    h["rescore_available"] = True
    h["breakdown"] = {"local_affordability": None, "space": None, "value_efficiency": None}
    h["summary"] = {"no_data_reason": reason, "fallback_applied": False}
    dq = h.get("data_quality") or {}
    dq.update({"quality_tier": "none", "confidence": 0, "degraded": True, "fallback_used": False, "fallback_metadata": {"fallback_used": False}})
    dq["degraded_reasons"] = [f"housing_value_no_data: {reason}"]
    h["data_quality"] = dq


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
            h = P.get("housing_value")
            r = reason_for(h) if isinstance(h, dict) else None
            if not r:
                out.append(line)
                continue
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            old = json.loads(json.dumps(h))
            make_no_data(h, r)
            tb = (s.get("total_score_breakdown") or {}).get("housing_value")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = None, 0.0
            hits.append((metro, cat.get("name"), old.get("score"), r, cat.get("search_query")))
            old_vals[f"{metro}|{cat.get('name')}"] = {"housing_value": old, "total_score": s.get("total_score")}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_housing_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| places:", len(hits))
    for h in hits:
        print("  ", h[0], h[1], "old score", h[2], "|", h[3], "|", h[4])


if __name__ == "__main__":
    main()
