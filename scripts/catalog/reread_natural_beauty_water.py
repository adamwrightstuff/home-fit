#!/usr/bin/env python3
"""
Re-read water (OSM, private Overpass) for the stored natural beauty places whose water read failed
(water_status "unavailable"), and rescore them offline from the stored GEE reads.  Overpass only: no GEE, no
other API.  Reads are cached in analysis/water_reread_cache.json as they complete, so it is safe to stop and
rerun; a failed read leaves the place as stored (still flagged).  Dry run by default; --write needs --backup-dir.

  cd /Users/adamwright/Dev/home-fit && OVERPASS_URL=http://localhost:12345/api/interpreter PYTHONPATH=. python3 scripts/catalog/reread_natural_beauty_water.py
  ... --write --backup-dir data/backups_nb_water_reread_2026-10-29
Then: PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --in-place --no-census
"""
import argparse, copy, glob, json, os, shutil, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "catalog"))
from pillars import natural_beauty as NB  # noqa: E402
from data_sources import osm_api  # noqa: E402

# The private Overpass server holds only these states.  An uncovered state returns an EMPTY result that would be
# scored as "no water within 15 km", so those places must never be read through it.
STATES = {"NY", "NJ", "CT", "CA", "WA", "TX", "IL", "IN", "PA", "DE", "MD"}
CACHE = ROOT / "analysis" / "water_reread_cache.json"
GLOB = str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")


def v9_of(nb):
    d = nb.get("details") or {}
    return next((c for c in (d.get("v9_breakdown"), nb.get("v9_breakdown")) if isinstance(c, dict) and "gvi_score" in c), None)


def targets():
    for path in sorted(glob.glob(GLOB)):
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            v = v9_of(nb) if isinstance(nb.get("score"), (int, float)) else None
            if v and v.get("water_status") == "unavailable" and r["catalog"].get("state_abbr") in STATES:
                c = r["score"]["coordinates"]
                yield f'{Path(path).name.split("_metro")[0]}|{r["catalog"]["name"]}', float(c["lat"]), float(c["lon"])


def read_water(item):
    key, lat, lon = item
    try:
        return key, osm_api.query_water_features(lat, lon, 15000)
    except Exception:
        return key, None


def water_status(data):
    if not isinstance(data, dict):
        return "unavailable"
    if data.get("nearest_distance_km") is None:
        return "none_within_15km" if data.get("source") == "osm_empty" else "unavailable"
    return "measured"


def rescore(nb, coords, data):
    """Update the natural_beauty pillar dict in place from a fresh water read; returns new score or None."""
    status = water_status(data)
    if status == "unavailable":
        return None
    v9 = v9_of(nb)
    ta = (nb.get("details") or {}).get("tree_analysis") or {}
    has_cs = bool((ta.get("natural_context") or {}).get("component_scores"))
    nearest = (data.get("nearest_waterbody") or {}) if status == "measured" else {}
    if has_cs:
        ta2 = copy.deepcopy(ta)
        ta2["water_read_status"] = status
        dbg = ta2["natural_context"].setdefault("debug_breakdown", {})
        dbg["water_proximity_type"] = nearest.get("type")
        dbg["water_proximity_nearest_km"] = data.get("nearest_distance_km") if status == "measured" else None
        dbg["water_by_type"] = NB._water_by_type(data)
        new, v9n = NB._apply_v9_formula({}, ta2, lat=coords.get("lat"), lon=coords.get("lon"))
    else:  # older shape: recompute from the stored per-dimension scores
        wt = nearest.get("type")
        ws = NB._v9_score_water(data.get("nearest_distance_km"), wt, status)
        comps = {k: v9.get(k) for k in ("gvi_score", "canopy_score", "topo_score")}
        comps["water_score"] = ws
        parts = NB.nb_two_part(comps, None, None)
        v9n = dict(v9, water_score=ws, water_status=status, streets_score=parts["streets"], scenery_score=parts["scenery"],
                   blend_raw=parts["blend"], streets_share=parts["streets_share"], method="two_part_v10", degraded_reasons=None, low_confidence=None)
        v9n["inputs"] = dict(v9.get("inputs") or {}, water_type=wt, water_dist_km=data.get("nearest_distance_km") if status == "measured" else None)
        new = parts["score"]
    d = nb.setdefault("details", {})
    if has_cs:
        d["tree_analysis"] = ta2  # keep the stored inputs consistent so the score reproduces from them
    d.setdefault("score_before_water_reread", nb["score"])
    nb["score"] = round(float(new), 2)
    d["score_v9"] = nb["score"]
    d["v9_breakdown"] = v9n
    if isinstance(nb.get("v9_breakdown"), dict):
        nb["v9_breakdown"] = v9n
    if isinstance(nb.get("weight"), (int, float)):
        nb["contribution"] = round(nb["weight"] * nb["score"] / 100.0, 4)
    dq = nb.get("data_quality") if isinstance(nb.get("data_quality"), dict) else {}
    left = [r for r in (dq.get("degraded_reasons") or []) if "water_read_unavailable" not in str(r)]
    left += [f"natural_beauty: {r}" for r in (v9n.get("degraded_reasons") or []) if f"natural_beauty: {r}" not in left]
    dq["degraded_reasons"], dq["degraded"] = left, bool(left)
    nb["data_quality"] = dq
    return nb["score"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [t for t in targets() if t[0] not in cache]
    print(f"{len(cache)} reads cached, {len(todo)} to read", flush=True)
    if todo and not os.getenv("OVERPASS_URL"):
        sys.exit("OVERPASS_URL not set (open the tunnel)")
    with ThreadPoolExecutor(a.workers) as ex:
        for i, (key, data) in enumerate(ex.map(read_water, todo), 1):
            if isinstance(data, dict):
                cache[key] = data
                CACHE.write_text(json.dumps(cache))
            if i % 20 == 0:
                print(f"  read {i}/{len(todo)}", flush=True)
    tally, rows = {"changed": 0, "still_unavailable": 0}, []
    for path in sorted(glob.glob(GLOB)):
        metro = Path(path).name.split("_metro")[0]
        mtime, out, changed = os.path.getmtime(path), [], False
        for line in open(path, encoding="utf-8").read().split("\n"):
            if not line.strip():
                out.append(line); continue
            r = json.loads(line)
            nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            key = f'{metro}|{r["catalog"]["name"]}'
            v = v9_of(nb) if isinstance(nb.get("score"), (int, float)) else None
            if not (v and v.get("water_status") == "unavailable"):
                out.append(line); continue
            old = nb["score"]
            try:
                new = rescore(nb, r["score"]["coordinates"], cache[key]) if key in cache else None
            except NB.NaturalBeautyNoData:
                new = None
            if new is None:
                tally["still_unavailable"] += 1; out.append(line); continue
            tb = (r["score"].get("total_score_breakdown") or {}).get("natural_beauty")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = nb["score"], nb.get("contribution", 0.0)
            tally["changed"] += 1; rows.append((metro, r["catalog"]["name"], old, new))
            out.append(json.dumps(r, ensure_ascii=False)); changed = True
        if a.write and changed:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir); b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8"); os.replace(path + ".tmp", path)
    d = [n - o for _, _, o, n in rows]
    print("mode:", "WRITE" if a.write else "DRY RUN", tally)
    if d:
        big = sorted(rows, key=lambda x: -abs(x[3] - x[2]))[:8]
        print(f"scored places changed {len(d)} | mean {sum(d)/len(d):+.2f} | min {min(d):+.1f} | max {max(d):+.1f} | moved >10: {sum(abs(x) > 10 for x in d)}")
        for m, n, o, nw in big:
            print(f"   {m} {n}: {o:.1f} -> {nw:.1f}")


if __name__ == "__main__":
    main()
