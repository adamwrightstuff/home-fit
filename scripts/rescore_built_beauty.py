#!/usr/bin/env python3
"""
Live re-score of Built Beauty to repair the ~34% of catalog places whose building
fetch timed out at build time (coverage 0 / confidence 0, then laundered into a ~57
floor). The in-pillar reliability guard retries the building query; any place that
STILL comes back zero-coverage/zero-confidence is quarantined (kept at its old score),
never overwritten with a fabricated number.

Resumable: writes as it goes; rerun skips finished. --retry-suspect re-attempts quarantined.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pillars.built_beauty import get_built_beauty_score  # noqa: E402

CATALOGS = [
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
    "data/la_metro_place_catalog_scores_merged.jsonl",
]
OUT = "data/built_beauty_rescore.jsonl"
SUSPECT = "data/built_beauty_rescore.suspect.jsonl"
THROTTLE = 1.0


def iter_catalog():
    for fn in CATALOGS:
        if not os.path.isfile(fn):
            continue
        for line in open(fn):
            try:
                r = json.loads(line)
            except Exception:
                continue
            cat = r.get("catalog", {})
            sc = r.get("score", {})
            bb = sc.get("livability_pillars", {}).get("built_beauty", {})
            if not bb:
                continue
            try:
                lat = float(cat.get("lat"))
                lon = float(cat.get("lon"))
            except (TypeError, ValueError):
                continue
            at = (sc.get("data_quality_summary", {}).get("area_classification", {}).get("effective_area_type")
                  or bb.get("area_classification", {}).get("area_type"))
            yield {
                "name": cat.get("name", ""), "lat": lat, "lon": lon,
                "city": cat.get("county_borough", ""), "area_type": at,
                "old": bb.get("score"),
            }


def load_done(path):
    d = {}
    if os.path.isfile(path):
        for line in open(path):
            try:
                row = json.loads(line)
                d[row["name"]] = row
            except Exception:
                pass
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retry-suspect", action="store_true")
    args = ap.parse_args()

    done = load_done(OUT)
    suspect = load_done(SUSPECT)
    targets = list(iter_catalog())
    if args.retry_suspect:
        targets = [t for t in targets if t["name"] in suspect]
        open(SUSPECT, "w").close()
    else:
        targets = [t for t in targets if t["name"] not in done]
    if args.limit:
        targets = targets[: args.limit]

    print(f"{len(targets)} to score ({len(done)} done).", flush=True)
    out_f = open(OUT, "a"); sus_f = open(SUSPECT, "a")
    n_ok = n_sus = n_err = 0
    for i, t in enumerate(targets, 1):
        try:
            score, details = get_built_beauty_score(
                t["lat"], t["lon"], city=t["city"], area_type=t["area_type"],
                location_name=t["name"],
            )
        except Exception as e:
            n_err += 1
            print(f"[{i}/{len(targets)}] {t['name']:22s} ERROR {str(e)[:60]}", flush=True)
            time.sleep(THROTTLE); continue
        aa = (details or {}).get("architectural_analysis", {})
        cov = aa.get("osm_building_coverage") or aa.get("metrics", {}).get("built_coverage_ratio") or 0.0
        conf = aa.get("confidence_0_1")
        conf = conf if conf is not None else 0.0
        row = {"name": t["name"], "old": t["old"], "new": round(score, 1),
               "coverage": round(cov, 3), "confidence": conf, "area_type": t["area_type"]}
        if cov <= 0.0 or conf <= 0.0:
            n_sus += 1; sus_f.write(json.dumps(row) + "\n"); sus_f.flush(); tag = "  QUARANTINED(no data)"
        else:
            n_ok += 1; out_f.write(json.dumps(row) + "\n"); out_f.flush(); tag = ""
        print(f"[{i}/{len(targets)}] {t['name']:22s} {(t['old'] or 0):5.1f} -> {score:5.1f}  "
              f"cov={row['coverage']} conf={conf}{tag}", flush=True)
        time.sleep(THROTTLE)
    print(f"\nDone. ok={n_ok} quarantined={n_sus} errors={n_err}", flush=True)


if __name__ == "__main__":
    main()
