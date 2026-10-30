#!/usr/bin/env python3
"""
Re-read the natural beauty green view at ONE radius (800 m) for every stored place and rescore natural beauty from the
stored inputs (design principles v2, P3: area type must not change how greenery is read).  GEE only: no Overpass, no
other API.  Evidence for 800 m: analysis in docs/PILLAR_NATURAL_BEAUTY.md (Place Pulse radius test and pin-shift test).

Two phases, so the slow live part can run unattended and the catalog is only touched after review:
  --read              live GEE reads, resumable, cached in analysis/gvi800_reread_cache.json (default phase)
  --apply             offline dry run from the cache: prints the score changes, writes nothing
  --apply --write --backup-dir DIR    writes the catalog (backup first), then run recompute_catalog_composites.py

Places already read at 800 m (urban residential) are skipped.  A place whose fresh read has no semantic green view, or
whose stored method is not semantic_gvi, stays as stored and is listed.
"""
import argparse, copy, glob, json, os, re, shutil, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pillars import natural_beauty as NB  # noqa: E402

RADIUS = 800
CACHE = ROOT / "analysis" / "gvi800_reread_cache.json"
GLOB = str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")
BOOST = re.compile(r"st_boost_(nyc_census|street_tree_feature)\((\d+),\+([\d.]+)pct\)")


def v9_of(nb):
    d = nb.get("details") or {}
    return next((c for c in (d.get("v9_breakdown"), nb.get("v9_breakdown")) if isinstance(c, dict) and "gvi_score" in c), None)


def area_type(r):
    return ((r["score"].get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")


def stored_radius(r, nb):
    d = nb.get("details") or {}
    rad = ((d.get("tree_analysis") or {}).get("green_view_details") or {}).get("radius_m") or (d.get("tree_analysis") or {}).get("gvi_radius_m")
    if rad:
        return int(rad)
    return {"urban_residential": 800, "urban_core": 1000}.get(area_type(r), 1200)  # the rule that stored them


_DUPS = None


def pkey(metro, r):
    """metro|name, plus |state when two places in one metro file share a name (nyc has Ridgewood NJ and Ridgewood NY)."""
    global _DUPS
    if _DUPS is None:
        seen, _DUPS = {}, set()
        for path in glob.glob(GLOB):
            m = Path(path).name.split("_metro")[0]
            for line in open(path, encoding="utf-8"):
                if line.strip():
                    n = json.loads(line)["catalog"]["name"]
                    (_DUPS.add((m, n)) if (m, n) in seen else seen.__setitem__((m, n), 1))
    n = r["catalog"]["name"]
    return f"{metro}|{n}|{r['catalog']['state_abbr']}" if (metro, n) in _DUPS else f"{metro}|{n}"


def places():
    for path in sorted(glob.glob(GLOB)):
        metro = Path(path).name.split("_metro")[0]
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            if isinstance(nb.get("score"), (int, float)) and v9_of(nb) and stored_radius(r, nb) != RADIUS:
                c = r["score"]["coordinates"]
                yield pkey(metro, r), float(c["lat"]), float(c["lon"])


def read_phase(threads):
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
    from data_sources.gee_api import get_urban_greenness_gee
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [p for p in places() if p[0] not in cache]
    print(f"R {len(cache)} cached, {len(todo)} to read", flush=True)

    def work(p):
        key, la, lo = p
        try:
            g = get_urban_greenness_gee(la, lo, radius_m=RADIUS)
        except Exception:
            g = None
        return key, g

    t0 = time.time()
    with ThreadPoolExecutor(threads) as ex:
        for k, fu in enumerate(as_completed([ex.submit(work, p) for p in todo]), 1):
            key, g = fu.result()
            if isinstance(g, dict) and (g.get("semantic_gvi") is not None):
                cache[key] = {x: g.get(x) for x in ("semantic_gvi", "visible_green_fraction", "street_level_ndvi", "green_space_ratio")}
                if k % 5 == 0:
                    CACHE.write_text(json.dumps(cache))
            if k % 25 == 0 or k == len(todo):
                CACHE.write_text(json.dumps(cache))
                print(f"R {k}/{len(todo)} read, {(time.time() - t0) / k:.1f}s per place (wall), {len(cache)} cached", flush=True)
    CACHE.write_text(json.dumps(cache))
    print("DONE", flush=True)


def synthetic_tree(nb, gvi_raw, vgf):
    """Older-format rows keep their inputs only in the breakdown; rebuild what the formula reads."""
    v9 = v9_of(nb); i = v9.get("inputs") or {}
    st = BOOST.search(str(i.get("gvi_source", "")))
    ta = {"green_view_index": gvi_raw, "green_view_details": {"method": "semantic_gvi", "radius_m": RADIUS},
          "gvi_metrics": {"semantic_gvi": gvi_raw, "visible_green_fraction": vgf, "radius_m": RADIUS},
          "weighted_canopy_pct": i.get("canopy_pct"), "water_read_status": v9.get("water_status") or "measured",
          "nyc_street_trees": int(st.group(2)) if st and st.group(1) == "nyc_census" else 0,
          "street_tree_feature_total": int(st.group(2)) if st and st.group(1) == "street_tree_feature" else 0,
          "natural_context": {"component_scores": {"topography_raw": i.get("topo_raw"), "landcover_raw": i.get("landcover_raw")},
                              "biodiversity_index": i.get("bio_val"),
                              "debug_breakdown": {"water_proximity_type": i.get("water_type"), "water_proximity_nearest_km": i.get("water_dist_km")}}}
    return ta


def rescore(nb, coords, fresh):
    """Update the natural_beauty dict in place; returns the new score or None when the place stays as stored."""
    sg = fresh.get("semantic_gvi")
    if not sg or sg <= 0:
        return None
    ta = (nb.get("details") or {}).get("tree_analysis") or {}
    new_shape = bool((ta.get("natural_context") or {}).get("component_scores"))
    if new_shape:
        if str((ta.get("green_view_details") or {}).get("method")) != "semantic_gvi":
            return None
        t2 = copy.deepcopy(ta)
        t2["green_view_index"] = round(float(sg), 2)
        t2["green_view_details"] = dict(t2.get("green_view_details") or {}, radius_m=RADIUS, semantic_gvi=round(float(sg), 2))
        t2["gvi_metrics"] = dict(t2.get("gvi_metrics") or {}, semantic_gvi=sg, visible_green_fraction=fresh.get("visible_green_fraction"), radius_m=RADIUS)
        t2["gvi_radius_m"] = RADIUS
        if "water_read_status" not in t2:  # rows stored before the field existed: infer it from the stored water reading
            v0 = v9_of(nb) or {}
            t2["water_read_status"] = ("measured" if v0.get("water_score") is not None and (v0.get("inputs") or {}).get("water_type")
                                       else "none_within_15km" if v0.get("water_score") == 3.0 else "unavailable")
    else:
        t2 = synthetic_tree(nb, round(float(sg), 2), fresh.get("visible_green_fraction"))
    new, v9n = NB._apply_v9_formula({}, t2, lat=coords.get("lat"), lon=coords.get("lon"))
    d = nb.setdefault("details", {})
    if new_shape:
        d["tree_analysis"] = t2
    d.setdefault("score_before_gvi800", nb["score"])
    nb["score"] = round(float(new), 2)
    d["score_v9"] = nb["score"]
    d["v9_breakdown"] = v9n
    if isinstance(nb.get("v9_breakdown"), dict):
        nb["v9_breakdown"] = v9n
    if isinstance(nb.get("weight"), (int, float)):
        nb["contribution"] = round(nb["weight"] * nb["score"] / 100.0, 4)
    return nb["score"]


def apply_phase(write, backup):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    rows, tally = [], {"changed": 0, "not_read": 0, "kept_as_stored": 0}
    for path in sorted(glob.glob(GLOB)):
        metro = Path(path).name.split("_metro")[0]
        mtime, out, changed = os.path.getmtime(path), [], False
        for line in open(path, encoding="utf-8").read().split("\n"):
            if not line.strip():
                out.append(line); continue
            r = json.loads(line)
            nb = (r["score"].get("livability_pillars") or {}).get("natural_beauty") or {}
            key = pkey(metro, r)
            if not (isinstance(nb.get("score"), (int, float)) and v9_of(nb) and stored_radius(r, nb) != RADIUS):
                out.append(line); continue
            if key not in cache:
                tally["not_read"] += 1; out.append(line); continue
            old = nb["score"]
            try:
                new = rescore(nb, r["score"]["coordinates"], cache[key])
            except NB.NaturalBeautyNoData:
                new = None
            if new is None:
                tally["kept_as_stored"] += 1; out.append(line); continue
            tb = (r["score"].get("total_score_breakdown") or {}).get("natural_beauty")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = nb["score"], nb.get("contribution", 0.0)
            tally["changed"] += 1; rows.append((metro, r["catalog"]["name"], old, new))
            out.append(json.dumps(r, ensure_ascii=False)); changed = True
        if write and changed:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(backup); b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            Path(path + ".tmp").write_text("\n".join(out), encoding="utf-8"); os.replace(path + ".tmp", path)
    d = [n - o for _, _, o, n in rows]
    print("mode:", "WRITE" if write else "DRY RUN", tally)
    if d:
        ad = sorted(abs(x) for x in d)
        print(f"changed {len(d)} | mean {sum(d)/len(d):+.2f} | median |change| {ad[len(ad)//2]:.1f} | p95 |change| {ad[int(.95*len(ad))]:.1f} | min {min(d):+.1f} | max {max(d):+.1f} | moved >10: {sum(abs(x) > 10 for x in d)}")
        for m, n, o, nw in sorted(rows, key=lambda x: -abs(x[3] - x[2]))[:8]:
            print(f"   {m} {n}: {o:.1f} -> {nw:.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--read", action="store_true"); ap.add_argument("--apply", action="store_true")
    ap.add_argument("--write", action="store_true"); ap.add_argument("--backup-dir"); ap.add_argument("--threads", type=int, default=3)
    a = ap.parse_args()
    if a.apply:
        if a.write and not a.backup_dir:
            sys.exit("--write requires --backup-dir")
        apply_phase(a.write, a.backup_dir)
    else:
        read_phase(a.threads)
