#!/usr/bin/env python3
"""
LEAN Social Fabric re-score: only the OSM civic query changed in the redesign, so
that's the only thing we re-fetch. Stability, engagement, area_type, density, radius
all come straight from the existing catalog; cohesion + civic_orgs are local Atlas
lookups. One network call per place (OSM), no Census -> ~5x faster, no DNS failures.

Reliability: dense areas returning implausibly few civic nodes are retried with
backoff, then quarantined if still thin (never baked into the main output).

Usage:
  python3 scripts/rescore_social_fabric_lean.py            # full catalogs
  python3 scripts/rescore_social_fabric_lean.py --limit 20
  python3 scripts/rescore_social_fabric_lean.py --retry-suspect
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sources import osm_api  # noqa: E402
from data_sources import social_capital_cohesion as coh  # noqa: E402
from pillars.social_fabric import (  # noqa: E402
    _civic_node_type_weight,
    _infra_density_score,
    _soft_or,
)

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
OUT_PATH = "data/social_fabric_rescore.jsonl"
SUSPECT_PATH = "data/social_fabric_rescore.suspect.jsonl"
THROTTLE_S = 1.5


def density_floor(density: float) -> int:
    if density >= 10_000:
        return 12
    if density >= 5_000:
        return 8
    if density >= 2_500:
        return 4
    return 0


def fetch_civic_effective(lat, lon, radius, density):
    """Fresh OSM civic query with retry-on-thin; returns (effective, raw_count, reliability)."""
    floor = density_floor(density)
    result = None
    for attempt in range(3):
        result = osm_api.query_civic_nodes(lat, lon, radius_m=radius)
        nodes = [n for n in (result.get("nodes") or []) if isinstance(n, dict)]
        ok = result.get("source_status") == "ok"
        if ok and len(nodes) >= floor:
            break
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    nodes = [n for n in (result.get("nodes") or []) if isinstance(n, dict)]
    eff = sum(_civic_node_type_weight(n.get("type")) for n in nodes)
    reliability = "ok"
    if floor > 0 and not (result.get("source_status") == "ok" and len(nodes) >= floor):
        reliability = "suspect_thin"
    return eff, len(nodes), reliability


def iter_catalog():
    for fname in CATALOGS:
        if not os.path.isfile(fname):
            continue
        for line in open(fname):
            try:
                r = json.loads(line)
            except Exception:
                continue
            cat = r.get("catalog", {})
            sc = r.get("score", {})
            sf = sc.get("livability_pillars", {}).get("social_fabric", {})
            if not sf or not sf.get("breakdown"):
                continue
            try:
                lat = float(cat.get("lat"))
                lon = float(cat.get("lon"))
            except (TypeError, ValueError):
                continue
            sm = sf.get("summary", {})
            yield {
                "name": cat.get("name", ""),
                "lat": lat, "lon": lon,
                "zip": str(sc.get("location_info", {}).get("zip", "")),
                "area_type": sf.get("area_classification", {}).get("area_type"),
                "density": sm.get("tract_population_density_sqmi") or 0,
                "radius": sm.get("civic_search_radius_m") or 1200,
                "stability": sf["breakdown"].get("stability", 0),
                "engagement": sf["breakdown"].get("engagement") or 0,
                "old": sf.get("score"),
            }


def load_done(path):
    done = {}
    if os.path.isfile(path):
        for line in open(path):
            try:
                row = json.loads(line)
                done[row["name"]] = row
            except Exception:
                continue
    return done


def recompose(t, eff):
    """New two-morphology composite from catalog values + fresh civic effective nodes."""
    c, _ = coh.get_cohesion_score(t["zip"], t["area_type"])
    a = (0.8 * c + 0.2 * t["stability"]) if c is not None else t["stability"]
    b = _infra_density_score(eff, t["radius"])
    co = coh.get_civic_orgs_score(t["zip"], t["area_type"])
    e = 0.65 * t["engagement"] + 0.35 * co if co is not None else t["engagement"]
    score = max(0.0, min(100.0, round(0.75 * _soft_or(a, b, 0.55) + 0.25 * e, 1)))
    return score, c, round(a, 1), round(b, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retry-suspect", action="store_true")
    args = ap.parse_args()

    done = load_done(OUT_PATH)
    suspect = load_done(SUSPECT_PATH)
    targets = list(iter_catalog())
    if args.retry_suspect:
        targets = [t for t in targets if t["name"] in suspect]
        open(SUSPECT_PATH, "w").close()
    else:
        targets = [t for t in targets if t["name"] not in done]
    if args.limit:
        targets = targets[: args.limit]

    print(f"{len(targets)} to score ({len(done)} done). Lean (OSM-only), throttle {THROTTLE_S}s.", flush=True)
    out_f = open(OUT_PATH, "a")
    sus_f = open(SUSPECT_PATH, "a")
    n_ok = n_sus = 0
    for i, t in enumerate(targets, 1):
        try:
            eff, raw, rel = fetch_civic_effective(t["lat"], t["lon"], t["radius"], t["density"])
        except Exception as ex:
            print(f"[{i}/{len(targets)}] {t['name']:22s} ERROR {ex}", flush=True)
            time.sleep(THROTTLE_S); continue
        score, c, a, b = recompose(t, eff)
        dens = round(eff / (math.pi * (t["radius"] / 1000.0) ** 2), 1) if t["radius"] else None
        row = {"name": t["name"], "old": t["old"], "new": score, "cohesion": c,
               "bond": a, "infra": b, "density_km2": dens, "civic_nodes": raw,
               "reliability": rel, "area_type": t["area_type"]}
        if rel == "suspect_thin":
            n_sus += 1; sus_f.write(json.dumps(row) + "\n"); sus_f.flush()
            tag = "  QUARANTINED"
        else:
            n_ok += 1; out_f.write(json.dumps(row) + "\n"); out_f.flush(); tag = ""
        print(f"[{i}/{len(targets)}] {t['name']:22s} {(t['old'] or 0):5.1f} -> {score:5.1f}  "
              f"dens={dens} nodes={raw}{tag}", flush=True)
        time.sleep(THROTTLE_S)
    print(f"\nDone. ok={n_ok} quarantined={n_sus}", flush=True)


if __name__ == "__main__":
    main()
