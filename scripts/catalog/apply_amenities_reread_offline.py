#!/usr/bin/env python3
"""
Offline: write re-read neighborhood amenities results into the catalog, for places stored as no data.

Input is a JSON list of {metro, q (search_query), det (pillar details from get_neighborhood_amenities_score)}.
The stored weight is kept; the pillar is rebuilt in the catalog's stored shape; the stale
data_gaps entry and total_score_breakdown entry are updated. Composites are cascaded afterwards with
recompute_catalog_composites.py --no-census for the printed search queries.

  PYTHONPATH=. python3 scripts/catalog/apply_amenities_reread_offline.py reread.json                  # dry run
  PYTHONPATH=. python3 scripts/catalog/apply_amenities_reread_offline.py reread.json --write --backup-dir <dir>
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


def build_pillar(old: dict, det: dict) -> dict:
    weight = old.get("weight") or 0.0
    score = det["score"]
    bd = dict(det.get("breakdown") or {})
    bd["business_list"] = det.get("business_list") or []
    bd["diagnostics"] = det.get("diagnostics") or {}
    dq = det.get("data_quality") or {}
    return {
        "score": score,
        "weight": weight,
        "importance_level": old.get("importance_level"),
        "contribution": round(score * weight / 100, 4),
        "breakdown": bd,
        "summary": det.get("summary") or {},
        "confidence": dq.get("confidence"),
        "failure_reason": None,
        "data_quality": dq,
        "area_classification": old.get("area_classification") or {},
        "status": "success",
        "pin_sensitivity": det.get("pin_sensitivity"),
        "_rescore_version": "amenities_v3_1_decay_grocery_2026-10-26",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    results = {(r["metro"], r["q"]): r["det"] for r in json.load(open(a.results)) if r["det"].get("score") is not None}
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
            cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
            det = results.get((metro, cat.get("search_query")))
            s = rec.get("score") or {}
            P = s.get("livability_pillars") or {}
            old = P.get("neighborhood_amenities")
            if det is None or not isinstance(old, dict) or old.get("status") != "no_data":
                out.append(line)
                continue
            old = json.loads(json.dumps(old))
            new = build_pillar(old, det)
            P["neighborhood_amenities"] = new
            tb = (s.get("total_score_breakdown") or {}).get("neighborhood_amenities")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = new["score"], new["contribution"]
            dg = s.get("data_gaps")
            if isinstance(dg, dict) and "neighborhood_amenities" in (dg.get("pillars") or []):
                dg["pillars"] = [p for p in dg["pillars"] if p != "neighborhood_amenities"]
                if not dg["pillars"]:
                    s.pop("data_gaps", None)
            hits.append((metro, cat.get("name"), new["score"], cat.get("search_query")))
            old_vals[f"{metro}|{cat.get('name')}"] = {"neighborhood_amenities": old, "total_score": s.get("total_score"), "data_gaps": s.get("data_gaps")}
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_amenities_reread_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| places:", len(hits))
    for h in hits:
        print("  ", *h)
    json.dump([[m, n, sc, q] for m, n, sc, q in hits], open(os.environ.get("HITS_OUT", os.devnull), "w"))


if __name__ == "__main__":
    main()
