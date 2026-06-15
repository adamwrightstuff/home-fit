#!/usr/bin/env python3
"""
Hardened batch re-score of the Social Fabric pillar across the merged catalogs.

Reliability features (the whole point):
  - Serial with a polite throttle between places (avoids Overpass 429 cascades).
  - Resumable: writes results to a JSONL as it goes; rerun skips already-done places.
  - Quarantines low-confidence reads: any place whose civic query comes back
    `suspect_thin` (dense area, implausibly few nodes -> rate-limited/partial response)
    is written to a separate `*.suspect.jsonl` and NOT merged, so a 429 never silently
    corrupts a neighborhood's score. Rerun later to recover them.

Usage:
  python3 scripts/rescore_social_fabric.py            # full catalogs
  python3 scripts/rescore_social_fabric.py --limit 15 # quick sample
  python3 scripts/rescore_social_fabric.py --retry-suspect  # re-attempt quarantined
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars import social_fabric  # noqa: E402

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
OUT_PATH = "data/social_fabric_rescore.jsonl"
SUSPECT_PATH = "data/social_fabric_rescore.suspect.jsonl"
THROTTLE_S = 2.0  # polite gap between places


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
            name = cat.get("name", "")
            try:
                lat = float(cat.get("lat"))
                lon = float(cat.get("lon"))
            except (TypeError, ValueError):
                continue
            if not name:
                continue
            yield {
                "name": name,
                "lat": lat,
                "lon": lon,
                "zip": str(sc.get("location_info", {}).get("zip", "")),
                "city": cat.get("county_borough", ""),
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
        # clear suspect file so recovered ones don't linger
        open(SUSPECT_PATH, "w").close()
        suspect = {}
    else:
        targets = [t for t in targets if t["name"] not in done]
    if args.limit:
        targets = targets[: args.limit]

    print(f"{len(targets)} to score ({len(done)} already done). Throttle {THROTTLE_S}s.\n")
    n_ok = n_suspect = n_err = 0
    out_f = open(OUT_PATH, "a")
    sus_f = open(SUSPECT_PATH, "a")

    for i, t in enumerate(targets, 1):
        try:
            score, details = social_fabric.get_social_fabric_score(
                t["lat"], t["lon"], city=t["city"], zip_code=t["zip"]
            )
        except Exception as e:
            n_err += 1
            print(f"[{i}/{len(targets)}] {t['name']:22s} ERROR: {e}")
            time.sleep(THROTTLE_S)
            continue

        s = details.get("summary", {})
        rel = s.get("civic_reliability", "ok")
        row = {
            "name": t["name"], "old": t["old"], "new": score,
            "cohesion": details["breakdown"].get("cohesion"),
            "infra": details["breakdown"].get("infrastructure_density"),
            "bond": details["breakdown"].get("bonding_cohesion"),
            "density_km2": s.get("civic_density_per_km2"),
            "civic_nodes": s.get("civic_node_count"),
            "reliability": rel,
            "area_type": details.get("area_classification", {}).get("area_type"),
        }
        flag = ""
        if rel == "suspect_thin":
            n_suspect += 1
            sus_f.write(json.dumps(row) + "\n"); sus_f.flush()
            flag = "  ⚠ QUARANTINED (thin/rate-limited)"
        else:
            n_ok += 1
            out_f.write(json.dumps(row) + "\n"); out_f.flush()
        old = t["old"] or 0
        print(f"[{i}/{len(targets)}] {t['name']:22s} {old:5.1f} -> {score:5.1f}  "
              f"dens={row['density_km2']} nodes={row['civic_nodes']}{flag}")
        time.sleep(THROTTLE_S)

    print(f"\nDone. ok={n_ok} quarantined={n_suspect} errors={n_err}")
    if n_suspect:
        print(f"Recover quarantined later: python3 {sys.argv[0]} --retry-suspect")


if __name__ == "__main__":
    main()
