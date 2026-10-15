#!/usr/bin/env python3
"""
Fix catalog places whose stored amenities were collected off their catalog pin and/or whose stored
area_type disagrees with the current classifier.

Per place, in order:
  1. If the stored amenities distances disagree with the pin (median error > PIN_ERR_M): rescore
     neighborhood_amenities from the catalog pin.
  2. Reclassify (classify_morphology on stored tract density + current nearby business count). If the type
     changed: rescore active_outdoors, public_transit_access, healthcare_access live and air_travel_access
     from stored airports, and set the area type fields.
  3. Recompute totals and composites for the row.
All-or-nothing per place: any failed or errored query (None score, exception, overpass_error) skips the
place with nothing written. Metro files with uncommitted git changes are skipped.

Usage: PYTHONPATH=. python3 scripts/manual/fix_pin_and_area_type.py [--dry-run] [--metros nyc sf la seattle]
Follow with: PYTHONPATH=. python3 scripts/catalog/apply_aura.py nyc la sf seattle
"""
import argparse, copy, json, math, re, statistics as st, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts" / "catalog"))
from data_sources.data_quality import classify_morphology  # noqa: E402

PIN_ERR_M = 100
DENS = re.compile(r'"tract_population_density_sqmi": ([0-9.]+)')


def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def amen(s):
    return (s.get("livability_pillars") or {}).get("neighborhood_amenities") or {}


def pin_error(s):
    try:
        b = [x for x in amen(s)["breakdown"]["business_list"] if x.get("distance_m") is not None and x.get("lat")]
        c = (s["coordinates"]["lat"], s["coordinates"]["lon"])
    except Exception:
        return None
    return st.median(abs(hav(c, (x["lat"], x["lon"])) - x["distance_m"]) for x in b) if len(b) >= 5 else None


def density(s):
    m = DENS.search(json.dumps(s))
    return float(m.group(1)) if m else None


def stored_type(s):
    return ((s.get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")


def stored_walk(s):
    try:
        return amen(s)["breakdown"]["diagnostics"]["businesses_within_walkable"]
    except Exception:
        return None


def targets(rows):
    out = []
    for d in rows:
        s = d.get("score")
        if not d.get("success") or not isinstance(s, dict):
            continue
        pe = pin_error(s)
        pin_bad = pe is not None and pe > PIN_ERR_M
        dn, w, t = density(s), stored_walk(s), stored_type(s)
        type_bad = False
        if dn and w is not None and t:
            cur = classify_morphology(dn, None, w, None)
            type_bad = cur not in ("unknown", t)
        if pin_bad or type_bad:
            out.append((d["catalog"]["name"], round(pe) if pe else None, pin_bad, type_bad, (d["catalog"]["name"], str(d["catalog"].get("lat")), str(d["catalog"].get("lon")))))
    return out


def with_retry(fn, tries=3, wait=20):
    last = None
    for i in range(tries):
        try:
            r = fn()
            if r is not None:
                return r
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(wait)
    raise RuntimeError(f"failed after {tries} tries: {last}")


def fix_place(d):
    from pillars.neighborhood_amenities import get_neighborhood_amenities_score
    from pillars.active_outdoors import get_active_outdoors_score
    from pillars.public_transit_access import get_public_transit_score
    from pillars.healthcare_access import get_healthcare_access_score
    from pillars.air_travel_access import get_air_travel_score
    from pillars.composite_indices import recompute_composites_from_payload
    from rerun_failed_catalog_pillars import recompute_totals
    from recompute_catalog_composites import _merge_composites_into_score

    d = copy.deepcopy(d); s = d["score"]; P = s["livability_pillars"]
    lat, lon = s["coordinates"]["lat"], s["coordinates"]["lon"]
    city = (s.get("location_info") or {}).get("city")
    dn = density(s); cur_type = stored_type(s); log = []
    pe = pin_error(s)
    if pe is not None and pe > PIN_ERR_M:
        sc, det = with_retry(lambda: (lambda r: r if r[0] is not None and r[1] else None)(
            get_neighborhood_amenities_score(lat, lon, area_type=cur_type)))
        new = dict(amen(s))
        bd = {**(det.get("breakdown") or {}), "business_list": det.get("business_list") or [], "diagnostics": det.get("diagnostics") or {}}
        new.update({"score": sc, "breakdown": bd, "summary": det.get("summary", {}),
                    "confidence": (det.get("data_quality") or {}).get("confidence", 0),
                    "data_quality": det.get("data_quality", {}), "area_classification": det.get("area_classification", {}),
                    "data_source": det.get("data_source"), "version": det.get("version"), "places_fallback": det.get("places_fallback")})
        P["neighborhood_amenities"] = new
        s.pop("local_scene_source", None)
        log.append(f"amenities {amen(s).get('score')} (pin err {pe:.0f} m)")
    walk = stored_walk(s)
    new_type = classify_morphology(dn, None, walk, None) if dn and walk is not None else "unknown"
    if new_type not in ("unknown", cur_type):
        def ao():
            sc, det = get_active_outdoors_score(lat, lon, city=city, area_type=new_type)
            ov = ((det or {}).get("summary") or {}).get("overpass") or {}
            if sc is None or any(v == "overpass_error" for v in ov.values()):
                return None
            return sc, det
        res = {"active_outdoors": with_retry(ao),
               "public_transit_access": with_retry(lambda: (lambda r: r if r[0] is not None else None)(
                   get_public_transit_score(lat, lon, area_type=new_type, city=city, density=dn))),
               "healthcare_access": with_retry(lambda: (lambda r: r if r[0] is not None else None)(
                   get_healthcare_access_score(lat, lon, area_type=new_type, city=city, density=dn))),
               "air_travel_access": get_air_travel_score(lat, lon, area_type=new_type, density=dn)}
        for k, (sc, det) in res.items():
            if sc is None:
                raise RuntimeError(f"{k} returned None")
            log.append(f"{k} {P[k].get('score')} -> {round(float(sc), 2)}")
            P[k] = {**P[k], **det, "score": round(float(sc), 2), "status": "success"}
        ac = s["data_quality_summary"]["area_classification"]
        ac["area_type"] = ac["effective_area_type"] = new_type
        log.append(f"area_type {cur_type} -> {new_type}")
    if not log:
        return None, log
    recompute_totals(s)
    _merge_composites_into_score(s, recompute_composites_from_payload(s))
    return d, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--metros", nargs="*", default=["nyc", "sf", "la", "seattle"])
    a = ap.parse_args()
    for m in a.metros:
        rel = f"data/{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
        path = ROOT / rel
        dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        tg = targets(rows)
        print(f"\n== {m}: {len(tg)} targets{' (SKIPPED: file has uncommitted changes)' if dirty else ''}")
        for t in tg:
            print("  ", t[:4])
        if a.dry_run or dirty:
            continue
        ok = fail = 0
        for name, *_, key in tg:
            rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
            idx = next(i for i, r in enumerate(rows) if (r["catalog"]["name"], str(r["catalog"].get("lat")), str(r["catalog"].get("lon"))) == key)
            try:
                new, log = fix_place(rows[idx])
            except Exception as e:  # noqa: BLE001
                fail += 1; print(f"  FAIL {name}: {e}"); continue
            if new is None:
                continue
            rows[idx] = new
            path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
            ok += 1; print(f"  OK {name}: " + "; ".join(log))
        print(f"{m}: fixed {ok}, failed/skipped {fail}")


if __name__ == "__main__":
    main()
