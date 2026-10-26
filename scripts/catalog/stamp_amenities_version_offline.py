#!/usr/bin/env python3
"""
Offline: stamp every catalog row's neighborhood amenities pillar with the current scoring version tag.

Run after the catalog has been brought to the current formula (grocery rule, proximity decay, re-reads). Only the
_rescore_version field changes. The git history of the catalog file is the backup.

  PYTHONPATH=. python3 scripts/catalog/stamp_amenities_version_offline.py [--write]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "amenities_v3_1_decay_grocery_2026-10-26"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    changed = 0
    for path in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        out = []
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            h = ((rec.get("score") or {}).get("livability_pillars") or {}).get("neighborhood_amenities")
            if isinstance(h, dict) and h.get("_rescore_version") != VERSION:
                h["_rescore_version"] = VERSION
                changed += 1
                line = json.dumps(rec, ensure_ascii=False)
            out.append(line)
        if a.write:
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| rows stamped:", changed)


if __name__ == "__main__":
    main()
