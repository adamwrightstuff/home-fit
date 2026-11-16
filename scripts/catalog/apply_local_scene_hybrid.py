#!/usr/bin/env python3
"""
Offline: write the Local Scene ladder level from the Overture hybrid (owner decision 2026-11-13). No API calls.

Needs score.local_scene_v2.overture (scripts/catalog/add_local_scene_overture_facts.py) next to the stored OpenStreetMap facts.

  volume   floor, Buzzing cut and blend weight from Overture counts (pillars/local_scene_v2.py OVERTURE_* constants)
  mix      the OSM mix when OSM mapped at least OSM_ENOUGH_VENUES venues in the measured area, else the Overture mix
           (each is the current mix blended with the restaurant-free mix by the volume weight)
Writes per place: score.local_scene_level, and in local_scene_v2: combined_new (OSM restaurant-free mix), mix_source ("osm" or
"overture"), blend_weight, combined_hybrid (the mix the level used), and overture.combined / overture.combined_new. The OSM combined, the stored
OSM counts and the Overture facts stay as they are. A place with no Overture venues gets level None (no data).

  python3 scripts/catalog/apply_local_scene_hybrid.py            # dry run
  python3 scripts/catalog/apply_local_scene_hybrid.py --write
Then re-run scripts/catalog/apply_aura.py (Aura reads the level).
"""
import argparse, glob, json, math, os, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars import local_scene_v2 as ls  # noqa: E402


def _apa(s):
    v2 = s.get("local_scene_v2") or {}
    if isinstance(v2.get("activity_per_acre"), (int, float)):
        return v2["activity_per_acre"]
    apa = (((s.get("livability_pillars") or {}).get("active_outdoors") or {}).get("dpv2_recompute") or {}).get("activity_per_acre")
    return apa if isinstance(apa, (int, float)) else None


def _osm_area(v2):
    if v2.get("geography") == "town_boundary":
        return v2.get("area_km2")
    r = v2.get("radius_m")
    return math.pi * (r / 1000.0) ** 2 if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    files = {}
    refs = []  # (path, row index)
    for path in sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))):
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        files[path] = rows
        for i, r in enumerate(rows):
            s = r.get("score") if r.get("success") else None
            if isinstance(s, dict) and isinstance(s.get("local_scene_v2"), dict):
                refs.append((path, i))
    scores = [files[p][i]["score"] for p, i in refs]
    v2s = [s["local_scene_v2"] for s in scores]
    densities = [_apa(s) for s in scores]
    # OSM restaurant-free mix, ranked against OSM peers of the same kind and density band
    osm_facts = [{**v, "geography": v.get("geography", "pin_circle")} for v in v2s]
    ls.apply_restaurant_free_reading(osm_facts, [_osm_area(v) for v in v2s], densities)
    # Overture mixes, ranked against Overture peers
    ov = []
    for v in v2s:
        o = dict(v.get("overture") or {})
        o.setdefault("geography", v.get("geography", "pin_circle"))
        if "venues_total" not in o:
            o["venues_total"] = 0
        o["geography"] = v.get("geography", "pin_circle")  # rank each place against its own kind, as the OSM read does
        ov.append(o)
    ls.apply_reading(ov, densities)
    ls.apply_restaurant_free_reading(ov, [(v.get("overture") or {}).get("area_km2") or _osm_area(v) for v in v2s], densities)
    counts = Counter()
    for (path, i), s, v, fo, o in zip(refs, scores, v2s, osm_facts, ov):
        if not v.get("overture") or not o.get("venues_total"):
            s["local_scene_level"] = None
            v.update({"mix_source": None, "blend_weight": None, "combined_hybrid": None})
            counts[None] += 1
            continue
        w = ls.blend_weight(o.get("independent_venues_1200m"))
        use_osm = (v.get("venues_total") or 0) >= ls.OSM_ENOUGH_VENUES
        if use_osm:
            mix = ls.hybrid_mix(v.get("combined"), fo.get("combined_new"), w)
        else:
            mix = ls.hybrid_mix(o.get("combined"), o.get("combined_new"), w)
        v["combined_new"] = fo.get("combined_new")
        v["mix_source"] = "osm" if use_osm else "overture"
        v["blend_weight"] = round(w, 3)
        v["combined_hybrid"] = mix
        v["overture"]["combined"] = o.get("combined")
        v["overture"]["combined_new"] = o.get("combined_new")
        v["overture"]["density_band"] = o.get("density_band")
        s["local_scene_level"] = ls.hybrid_level(o, mix)
        counts[s["local_scene_level"]] += 1
    print("levels:", dict(counts))
    if a.write:
        for path, rows in files.items():
            tmp = Path(path).with_name(Path(path).name + ".tmp")
            tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        print(f"written to {len(files)} catalog files")
    else:
        print("dry run: pass --write to save")


if __name__ == "__main__":
    main()
