#!/usr/bin/env python3
"""
Rescore one place's neighborhood_amenities pillar in-process (Google Places fallback on),
merge it into the NYC composites_recomputed catalog, then recompute totals, composites and Aura.

Usage: PYTHONPATH=. HOMEFIT_PLACES_FALLBACK_ENABLED=1 HOMEFIT_PLACES_COMPLETENESS_THRESHOLD=1.01 python3 scripts/manual/rescore_amenities_places.py "Cold Spring Harbor"
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts" / "catalog"))
from pillars.neighborhood_amenities import get_neighborhood_amenities_score  # noqa: E402
from pillars.composite_indices import recompute_composites_from_payload  # noqa: E402
from rerun_failed_catalog_pillars import recompute_totals  # noqa: E402
from recompute_catalog_composites import _merge_composites_into_score  # noqa: E402

PATH = ROOT / "data" / "nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
name = sys.argv[1]
rows = [json.loads(l) for l in PATH.read_text().splitlines() if l.strip()]
for d in rows:
    if d["catalog"]["name"] != name:
        continue
    s = d["score"]
    lat, lon = s["coordinates"]["lat"], s["coordinates"]["lon"]
    area = (s.get("data_quality_summary") or {}).get("area_type") or "suburban"
    score, det = get_neighborhood_amenities_score(lat, lon, area_type=area)
    if det is None or score is None:
        sys.exit(f"amenities returned None for {name}; nothing written")
    old = s["livability_pillars"]["neighborhood_amenities"]
    new = dict(old)
    bd = {**(det.get("breakdown") or {}), "business_list": det.get("business_list") or [],
          "diagnostics": det.get("diagnostics") or {}}
    new.update({"score": score, "breakdown": bd, "summary": det.get("summary", {}),
                "confidence": (det.get("data_quality") or {}).get("confidence", 0),
                "data_quality": det.get("data_quality", {}), "area_classification": det.get("area_classification", {}),
                "data_source": det.get("data_source"), "version": det.get("version"),
                "places_fallback": det.get("places_fallback")})
    s["livability_pillars"]["neighborhood_amenities"] = new
    old_total = s["total_score"]
    recompute_totals(s)
    _merge_composites_into_score(s, recompute_composites_from_payload(s))
    if (det.get("places_fallback") or {}).get("used"):
        s["local_scene_source"] = "google_places"
    else:
        s.pop("local_scene_source", None)
    print(f"{name}: amenities {old.get('score')} -> {score}; total {old_total} -> {s['total_score']}; businesses {len(bd['business_list'])}")
PATH.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in rows) + "\n")
