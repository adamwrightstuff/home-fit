#!/usr/bin/env python3
"""
Offline: mark catalog places whose neighborhood amenities result is unreadable or imputed as no data.

Targets two stored patterns: a pillar with score None and no recorded reason (an Overpass read that failed or
came back empty and was never confirmed), and status "fallback" (an imputed score from the retired fallback
path). The pillar becomes no data in the catalog's stored-gap shape (score None, contribution 0.0,
confidence 0, status no_data, degraded with the reason). Places that already had score None and
contribution 0.0 keep their totals; only imputed ones (La Crescenta) need the composites cascade
(recompute_catalog_composites.py --no-census, run for the printed search queries).

  PYTHONPATH=. python3 scripts/catalog/recompute_amenities_nodata_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_amenities_nodata_offline.py --write --backup-dir <dir>
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
UNREADABLE = "osm_unavailable_or_unconfirmed_empty"
IMPUTED = "imputed_fallback_score_removed"


def reason_for(a: dict):
    if a.get("status") == "fallback" or (a.get("data_quality") or {}).get("fallback_used"):
        return IMPUTED
    if a.get("score") is None and not a.get("failure_reason") and a.get("status") != "no_data":
        return UNREADABLE
    return None


def make_no_data(a: dict, reason: str) -> None:
    a["score"] = None
    a["contribution"] = 0.0
    a["confidence"] = 0
    a["status"] = "no_data"
    a["failure_reason"] = reason
    a["rescore_available"] = True
    dq = a.get("data_quality") or {}
    dq.update({"quality_tier": "none", "confidence": 0, "degraded": True, "fallback_used": False, "fallback_metadata": {"fallback_used": False}})
    dq["degraded_reasons"] = [f"neighborhood_amenities_no_data: {reason}"]
    a["data_quality"] = dq


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
            h = P.get("neighborhood_amenities")
            r = reason_for(h) if isinstance(h, dict) else None
            if not r:
                out.append(line)
                continue
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            old = json.loads(json.dumps(h))
            make_no_data(h, r)
            tb = (s.get("total_score_breakdown") or {}).get("neighborhood_amenities")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = None, 0.0
            hits.append((metro, cat.get("name"), old.get("score"), r, cat.get("search_query"), old.get("contribution")))
            old_vals[f"{metro}|{cat.get('name')}"] = {"neighborhood_amenities": old, "total_score": s.get("total_score")}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_amenities_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| places:", len(hits))
    for h in hits:
        print("  ", h[0], h[1], "old score", h[2], "old contribution", h[5], "|", h[3], "|", h[4])


if __name__ == "__main__":
    main()
