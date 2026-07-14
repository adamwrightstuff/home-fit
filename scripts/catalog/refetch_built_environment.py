#!/usr/bin/env python3
"""
Live refetch of built_environment for the places whose stored data is unusable
(api_error fallbacks + the 2 misclassified hyper-dense Manhattan cores).

Runs the real scoring pipeline (live OSM + GHSL/Microsoft via current code) with
deliberate pacing between places to avoid self-inflicted Overpass rate limiting.
Writes results to a separate JSONL; never touches the source catalogs.

Usage:
  PYTHONPATH=. python3 scripts/catalog/refetch_built_environment.py \
    --worklist /tmp/refetch_worklist.json --tag nyc --out /tmp/refetch_nyc.jsonl --sleep 15
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

from pillars.built_environment import calculate_built_environment


def load_catalog_index(path):
    idx = {}
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        idx[r["catalog"].get("name")] = r
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worklist", required=True)
    ap.add_argument("--tag", required=True, choices=["la", "nyc"])
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sleep", type=float, default=15.0)
    args = ap.parse_args()

    wl = json.load(open(args.worklist))[args.tag]
    idx = load_catalog_index(args.catalog)
    out = open(args.out, "w")
    print(f"[refetch:{args.tag}] {len(wl)} places, sleep {args.sleep}s between", flush=True)

    for i, place in enumerate(wl, 1):
        name = place["name"]; lat = place["lat"]; lon = place["lon"]
        rec = idx.get(name, {})
        bb = rec.get("score", {}).get("livability_pillars", {}).get("built_environment", {})
        old = bb.get("score")
        det = bb.get("details", {}) if isinstance(bb, dict) else {}
        aa = det.get("architectural_analysis", {})
        cls = aa.get("classification", {})
        area_type = cls.get("base_area_type") or cls.get("effective_area_type")
        density = cls.get("density")
        stored_enh = det.get("enhancers") if isinstance(det, dict) else None

        # Retry on api_error: a fallback score is NOT real data and must never be written
        # as a result. Try up to MAX_TRIES; if every try comes back api_error, mark FAILED
        # (no score) so it's excluded and re-run later -- never emit fallback garbage.
        MAX_TRIES = 3
        rec_out = None
        for attempt in range(1, MAX_TRIES + 1):
            t0 = time.time()
            try:
                res = calculate_built_environment(
                    lat, lon,
                    area_type=area_type, density=density,
                    enhancers_data=stored_enh,
                    location_name=name,
                )
                warn = (res.get("architectural_details") or {}).get("data_warning")
                if warn == "api_error":
                    # OSM failed -> fallback score. Discard, retry after a backoff.
                    if attempt < MAX_TRIES:
                        time.sleep(args.sleep)
                        continue
                    rec_out = {"name": name, "reason": place["reason"], "ok": False,
                               "status": "FAILED_api_error", "old_score": old,
                               "tries": attempt, "secs": round(time.time() - t0, 1)}
                else:
                    rec_out = {
                        "name": name, "reason": place["reason"], "ok": True,
                        "status": "clean", "old_score": old, "new_score": round(res["score"], 2),
                        "component_0_50": round(res.get("component_score_0_50", 0.0), 2),
                        "effective_area_type": res.get("effective_area_type"),
                        "data_warning": warn, "tries": attempt,
                        "secs": round(time.time() - t0, 1),
                        # Full result, so the entire built_environment subtree can be replaced
                        # wholesale (no nested fields left stale from before this refetch).
                        "full_result": res,
                    }
                break
            except Exception as e:
                if attempt < MAX_TRIES:
                    time.sleep(args.sleep)
                    continue
                rec_out = {"name": name, "reason": place["reason"], "ok": False,
                           "status": "FAILED_exception", "old_score": old,
                           "error": repr(e)[:200], "tries": attempt, "secs": round(time.time() - t0, 1)}
        out.write(json.dumps(rec_out) + "\n"); out.flush()
        print(f"[{i}/{len(wl)}] {name:24s} {rec_out['status']:18s} old={old} new={rec_out.get('new_score')} "
              f"warn={rec_out.get('data_warning')} tries={rec_out.get('tries')} {rec_out['secs']}s", flush=True)
        if i < len(wl):
            time.sleep(args.sleep)

    out.close()
    print(f"[refetch:{args.tag}] done -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
