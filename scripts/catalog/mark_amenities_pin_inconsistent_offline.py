#!/usr/bin/env python3
"""
Offline: mark amenities as no data for places whose stored business list does not match the stored pin and whose re-read at
the stored pin found no business (so the old score cannot be trusted and the new zero may only reflect a mis-placed pin).

Input: JSON list of {metro, q} (search_query). Pillar becomes no data (score None, contribution 0.0, status no_data) with the
reason pin_inconsistent_unresolved; fix the pin, then re-read. Cascade composites afterwards (--no-census).

  PYTHONPATH=. python3 scripts/catalog/mark_amenities_pin_inconsistent_offline.py targets.json [--write --backup-dir D]
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
sys.path.insert(0, str(ROOT / "scripts" / "catalog"))
from recompute_amenities_nodata_offline import make_no_data  # noqa: E402

REASON = "pin_inconsistent_unresolved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    targets = {(t["metro"], t["q"]) for t in json.load(open(a.targets))}
    hits = []
    for path in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        metro = os.path.basename(path).split("_metro")[0]
        out, old_vals = [], {}
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            cat = rec.get("catalog") or {}
            s = rec.get("score") or {}
            h = (s.get("livability_pillars") or {}).get("neighborhood_amenities")
            if (metro, cat.get("search_query")) not in targets or not isinstance(h, dict):
                out.append(line)
                continue
            old_vals[f"{metro}|{cat.get('name')}"] = {"neighborhood_amenities": json.loads(json.dumps(h)), "total_score": s.get("total_score")}
            make_no_data(h, REASON)
            tb = (s.get("total_score_breakdown") or {}).get("neighborhood_amenities")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = None, 0.0
            hits.append((metro, cat.get("name"), cat.get("search_query")))
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write and old_vals:
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_amenities_pin_values.json").write_text(json.dumps(old_vals))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| places:", len(hits))
    for h in hits:
        print("  ", *h)


if __name__ == "__main__":
    main()
