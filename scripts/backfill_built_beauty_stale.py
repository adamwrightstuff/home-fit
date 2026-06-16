#!/usr/bin/env python3
"""
Faithful backfill of built_beauty for catalog places with stale ZERO building data.

~34% of catalog places carry built_beauty scores computed from coverage-0 / zero-diversity
OSM data (build-time Overpass timeouts), then a prior `rescore_built_beauty_full.py` reused
those zeros and HARDCODED confidence 90 — so they look fine (East Village 94.2, conf 90) but
their architectural-diversity signal is empty; the score rides the historic-coherence
fallback.

This RE-FETCHES OSM buildings (`compute_arch_diversity`, radius 2000m, same as main.py) and
re-scores via `calculate_built_beauty(precomputed_arch_diversity=fresh, ...)` — the same call
main.py makes (avoids the ±10pt drift of the standalone `get_built_beauty_score` loop).

GUARDED: if the re-fetch STILL returns zero coverage (Overpass failed again), the place is
quarantined — its old score is kept, never overwritten with another fabricated number.
Resumable; throttled (Overpass is rate-limit-prone — see transit-fetch-noisy memory).

Phases:
  fetch -> data/built_beauty_backfill.jsonl   (rerun skips done)
  apply -> rewrites catalogs (.bakBB), cascades total_score + happiness 'built' (weight 0.05)

Usage: python3 scripts/backfill_built_beauty_stale.py fetch
       python3 scripts/backfill_built_beauty_stale.py apply
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
SIDECAR = "data/built_beauty_backfill.jsonl"
PILLAR = "built_beauty"
THROTTLE = 1.5  # Overpass is rate-limit-prone; go slow


def _stored_metrics(bb):
    det = bb.get("details", {}) or {}
    aa = det.get("architectural_analysis", {}) or {}
    m = {**aa, **(aa.get("metrics", {}) or {})}
    cov = m.get("osm_building_coverage")
    if cov is None:
        cov = m.get("built_coverage_ratio")
    return cov, m.get("height_diversity"), m.get("type_diversity")


def is_stale(bb):
    cov, hd, td = _stored_metrics(bb)
    if cov is not None and cov <= 0.0:
        return True
    if (hd in (0, 0.0, None)) and (td in (0, 0.0, None)):
        return True
    return False


def iter_stale():
    seen = set()
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        for line in open(fn):
            try:
                r = json.loads(line)
            except Exception:
                continue
            bb = r.get("score", {}).get("livability_pillars", {}).get(PILLAR)
            cat = r.get("catalog", {})
            nm = cat.get("name", "")
            if not bb or nm in seen or not is_stale(bb):
                continue
            try:
                lat, lon = float(cat["lat"]), float(cat["lon"])
            except (TypeError, ValueError, KeyError):
                continue
            seen.add(nm)
            at = (r["score"].get("data_quality_summary", {})
                  .get("area_classification", {}).get("effective_area_type"))
            yield {"name": nm, "lat": lat, "lon": lon, "area_type": at,
                   "city": cat.get("county_borough", ""), "old": bb.get("score")}


def load_done():
    d = {}
    if os.path.isfile(SIDECAR):
        for line in open(SIDECAR):
            try:
                row = json.loads(line)
                d[row["name"]] = row
            except Exception:
                pass
    return d


def fetch():
    from data_sources.arch_diversity import compute_arch_diversity
    from pillars.built_beauty import calculate_built_beauty

    done = load_done()
    targets = [t for t in iter_stale() if t["name"] not in done]
    print(f"{len(targets)} stale places to backfill ({len(done)} done).", flush=True)
    out = open(SIDECAR, "a")
    n_ok = n_q = 0
    for i, t in enumerate(targets, 1):
        try:
            ad = compute_arch_diversity(t["lat"], t["lon"], radius_m=2000)
            cov = (ad or {}).get("built_coverage_ratio") or 0.0
            if not ad or cov <= 0.0:
                row = {"name": t["name"], "old": t["old"], "new": None, "coverage": cov,
                       "quarantined": True}
                n_q += 1
            else:
                res = calculate_built_beauty(
                    t["lat"], t["lon"], city=t["city"], area_type=t["area_type"],
                    location_scope="neighborhood", precomputed_arch_diversity=ad,
                )
                row = {"name": t["name"], "old": t["old"], "new": round(res["score"], 1),
                       "coverage": round(cov, 3),
                       "height_div": ad.get("levels_entropy"),
                       "type_div": ad.get("building_type_diversity"), "quarantined": False}
                n_ok += 1
        except Exception as e:
            row = {"name": t["name"], "old": t["old"], "new": None, "error": str(e)[:60],
                   "quarantined": True}
            n_q += 1
        out.write(json.dumps(row) + "\n")
        out.flush()
        tag = " QUARANTINED" if row.get("quarantined") else ""
        print(f"[{i}/{len(targets)}] {t['name']:22s} {str(t['old']):>5} -> {row.get('new')}"
              f" cov={row.get('coverage')}{tag}", flush=True)
        time.sleep(THROTTLE)
    print(f"fetch complete. ok={n_ok} quarantined={n_q}", flush=True)


def apply():
    res = load_done()
    good = {nm: r for nm, r in res.items() if not r.get("quarantined") and r.get("new") is not None}
    if not good:
        print("no good backfills — run 'fetch' first.", flush=True)
        return
    shifts = []
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        shutil.copyfile(fn, fn + ".bakBB")
        tmp = fn + ".new"
        n = 0
        with open(fn) as src, open(tmp, "w") as outf:
            for line in src:
                try:
                    row = json.loads(line)
                except Exception:
                    outf.write(line)
                    continue
                nm = row.get("catalog", {}).get("name", "")
                sc = row.get("score", {})
                bb = sc.get("livability_pillars", {}).get(PILLAR)
                if nm in good and bb:
                    new = good[nm]["new"]
                    old = bb["score"]
                    w = bb.get("weight") or 0.0
                    bb["score"] = new
                    bb["contribution"] = round(new * w / 100.0, 4)
                    bb["confidence"] = 85
                    bb["_rescore_version"] = "built_beauty_stale_backfill"
                    tsb = sc.get("total_score_breakdown", {}).get(PILLAR)
                    if tsb:
                        oc = tsb["contribution"]
                        nc = round(new * (tsb.get("weight") or 0.0) / 100.0, 4)
                        tsb["score"] = new
                        tsb["contribution"] = nc
                        sc["total_score"] = round(sc["total_score"] - oc + nc, 4)
                    # happiness 'built' component (weight 0.05)
                    hb = sc.get("happiness_index_breakdown")
                    if hb and "built" in hb:
                        w_b = (hb.get("component_weights", {}) or {}).get("built", 0.05)
                        old_b = hb["built"]
                        hb["built"] = new
                        if sc.get("happiness_index") is not None:
                            sc["happiness_index"] = round(
                                sc["happiness_index"] - w_b * old_b + w_b * new, 4)
                    shifts.append((nm, old, new))
                    n += 1
                outf.write(json.dumps(row) + "\n")
        os.replace(tmp, fn)
        print(f"{fn}: backfilled {n} places (backup: {fn}.bakBB)", flush=True)
    import numpy as np
    d = np.array([n - o for _, o, n in shifts])
    print(f"\nΔ mean={d.mean():+.1f} min={d.min():+.0f} max={d.max():+.0f} | "
          f"raised={(d>0).sum()} lowered={(d<0).sum()}", flush=True)
    print("biggest changes:")
    for nm, o, nw in sorted(shifts, key=lambda x: abs(x[2]-x[1]), reverse=True)[:12]:
        print(f"   {nm:22s} {o:5.1f} -> {nw:5.1f} ({nw-o:+.1f})", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    {"fetch": fetch, "apply": apply}.get(cmd, lambda: print(__doc__))()
