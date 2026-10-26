#!/usr/bin/env python3
"""
Offline: add data-limit fields (DPv2 P11) to each catalog row's neighborhood amenities pillar, from the stored business list.

Adds data_source ("osm" or "blended"), source_counts (OSM and Google Places records), pin_sensitivity (score range under
a 200 m pin shift, same function as the live scorer) and limits (chains included; Overpass and Places counts). Scores do
not change. The git history of the catalog file is the backup.

  PYTHONPATH=. python3 scripts/catalog/add_amenities_source_metadata_offline.py [--write]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    from pillars.neighborhood_amenities import _pin_sensitivity

    changed = 0
    for path in sorted(glob.glob(str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        out = []
        for line in Path(path).read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                out.append(line)
                continue
            rec = json.loads(line)
            s = rec.get("score") or {}
            h = (s.get("livability_pillars") or {}).get("neighborhood_amenities")
            co = s.get("coordinates") or {}
            if not isinstance(h, dict) or h.get("score") is None or "lat" not in co:
                out.append(line)
                continue
            bl = (h.get("breakdown") or {}).get("business_list") or []
            places = sum(1 for b in bl if b.get("source") == "google_places")
            at = ((s.get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")
            h["data_source"] = "blended" if places else "osm"
            h["source_counts"] = {"osm": len(bl) - places, "google_places": places}
            h["limits"] = {"chains_included": True, "osm_with_places_fallback": bool(places)}
            h["pin_sensitivity"] = _pin_sensitivity(bl, co["lat"], co["lon"], at, False, 800)
            changed += 1
            out.append(json.dumps(rec, ensure_ascii=False))
        if a.write:
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8")
            os.replace(path + ".tmp", path)
    print("mode:", "WRITE" if a.write else "DRY RUN", "| rows updated:", changed)


if __name__ == "__main__":
    main()
