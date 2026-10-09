#!/usr/bin/env python3
"""
Rescore the area-type-dependent pillars for ONE catalog place under its corrected area type.

Corrected type = classify_morphology(stored tract density, stored businesses within 1 km).
Rescored live: active_outdoors, public_transit_access, healthcare_access; air_travel_access is
recomputed from the stored airport list. community_safety and natural_beauty are NOT rescored.
Then recomputes totals and composites for the row.

Usage: PYTHONPATH=. python3 scripts/manual/rescore_place_area_type.py "Financial District" sf
Follow with: PYTHONPATH=. python3 scripts/catalog/apply_aura.py sf
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts" / "catalog"))
from data_sources.data_quality import classify_morphology  # noqa: E402
from pillars.active_outdoors import get_active_outdoors_score  # noqa: E402
from pillars.public_transit_access import get_public_transit_score  # noqa: E402
from pillars.healthcare_access import get_healthcare_access_score  # noqa: E402
from pillars.air_travel_access import get_air_travel_score  # noqa: E402
from pillars.composite_indices import recompute_composites_from_payload  # noqa: E402
from rerun_failed_catalog_pillars import recompute_totals  # noqa: E402
from recompute_catalog_composites import _merge_composites_into_score  # noqa: E402

name, metro = sys.argv[1], sys.argv[2]
PATH = ROOT / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
rows = [json.loads(l) for l in PATH.read_text().splitlines() if l.strip()]
hits = [d for d in rows if d["catalog"]["name"] == name]
assert len(hits) == 1, f"{len(hits)} rows named {name}"
d = hits[0]; s = d["score"]; P = s["livability_pillars"]
lat, lon = s["coordinates"]["lat"], s["coordinates"]["lon"]
city = (s.get("location_info") or {}).get("city")
density = float(re.search(r'"tract_population_density_sqmi": ([0-9.]+)', json.dumps(s)).group(1))
walk = P["neighborhood_amenities"]["breakdown"]["diagnostics"]["businesses_within_walkable"]
old_type = s["data_quality_summary"]["area_classification"]["area_type"]
new_type = classify_morphology(density, None, walk, None)
print(f"{name}: area_type {old_type} -> {new_type} (density {density:.0f}, {walk} businesses within 1 km)")
if new_type in ("unknown", old_type):
    sys.exit("nothing to correct; no changes written")

before = {k: P[k].get("score") for k in ("active_outdoors", "public_transit_access", "healthcare_access", "air_travel_access")}
calls = {
    "active_outdoors": lambda: get_active_outdoors_score(lat, lon, city=city, area_type=new_type),
    "public_transit_access": lambda: get_public_transit_score(lat, lon, area_type=new_type, city=city, density=density),
    "healthcare_access": lambda: get_healthcare_access_score(lat, lon, area_type=new_type, city=city, density=density),
    "air_travel_access": lambda: get_air_travel_score(lat, lon, area_type=new_type, density=density),
}
for k, fn in calls.items():
    sc, det = fn()
    if sc is None:
        sys.exit(f"{k} returned None; nothing written")
    P[k] = {**P[k], **det, "score": round(float(sc), 2), "status": "success"}
ac = s["data_quality_summary"]["area_classification"]
ac["area_type"] = ac["effective_area_type"] = new_type
old_total = s["total_score"]
recompute_totals(s)
_merge_composites_into_score(s, recompute_composites_from_payload(s))
for k in before:
    print(f"  {k}: {before[k]} -> {P[k]['score']}")
print(f"  total_score: {old_total} -> {s['total_score']}")
PATH.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
