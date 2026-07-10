#!/usr/bin/env python3
"""
Batch-score top US vacation destinations in vacation mode.

Writes one JSON object per line (JSONL). Resumable — skips already-scored rows.

Usage:
  cd /path/to/home-fit
  HOMEFIT_PROXY_SECRET=<secret> python3 scripts/catalog/batch_score_vacation_destinations.py

Options:
  --output PATH    Output JSONL (default: data/vacation_destinations_scores.jsonl)
  --base-url URL   API base URL (default: https://home-fit-production.up.railway.app)
  --concurrency N  Parallel jobs (default: 3)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "vacation_destinations_scores.jsonl"

# Top 50 US vacation destinations with trip type
DESTINATIONS = [
    # Beach
    ("Miami Beach, FL",         "beach"),
    ("Myrtle Beach, SC",        "beach"),
    ("Virginia Beach, VA",      "beach"),
    ("Kill Devil Hills, NC",     "beach"),
    ("Hilton Head, SC",         "beach"),
    ("Key West, FL",            "beach"),
    ("Destin, FL",              "beach"),
    ("Santa Barbara, CA",       "beach"),
    ("Malibu, CA",              "beach"),
    ("Monterey, CA 93940",      "beach"),
    ("Newport, RI",             "beach"),
    ("Provincetown, MA",         "beach"),
    ("Bar Harbor, ME",          "beach"),
    ("Rehoboth Beach, DE",      "beach"),
    ("Galveston, TX",           "beach"),
    # Mountain
    ("Aspen, CO",               "mountain"),
    ("Sedona, AZ",              "mountain"),
    ("Park City, UT",           "mountain"),
    ("Jackson, WY",              "mountain"),
    ("Breckenridge, CO",        "mountain"),
    ("Vail, CO",                "mountain"),
    ("Telluride, CO",           "mountain"),
    ("Steamboat Springs, CO",   "mountain"),
    ("South Lake Tahoe, CA",    "mountain"),
    ("Bend, OR",                "mountain"),
    ("Gatlinburg, TN",          "mountain"),
    ("Asheville, NC",           "mountain"),
    ("Stowe, VT",               "mountain"),
    ("Moab, UT",                "mountain"),
    ("Santa Fe, NM",            "mountain"),
    # City
    ("New York, NY",            "city"),
    ("Las Vegas, NV",           "city"),
    ("New Orleans, LA",         "city"),
    ("Nashville, TN",           "city"),
    ("Chicago, IL",             "city"),
    ("San Francisco, CA",       "city"),
    ("New Orleans, LA",         "city"),
    ("Savannah, GA",            "city"),
    ("Charleston, SC",          "city"),
    ("Austin, TX",              "city"),
    ("Portland, OR",            "city"),
    ("Seattle, WA",             "city"),
    ("Boston, MA",              "city"),
    ("Philadelphia, PA",        "city"),
    ("Washington, DC",          "city"),
    ("Denver, CO",              "city"),
    ("Memphis, TN",             "city"),
    ("San Antonio, TX",         "city"),
    ("Scottsdale, AZ",          "city"),
    ("Napa, CA",                "city"),
]

# Deduplicate while preserving order
seen = set()
DESTINATIONS_DEDUPED = []
for d in DESTINATIONS:
    if d not in seen:
        seen.add(d)
        DESTINATIONS_DEDUPED.append(d)

TRIP_TYPE_MONTH = {"beach": 7, "mountain": 7, "city": 10}


def proxy_headers() -> Dict[str, str]:
    secret = os.environ.get("HOMEFIT_PROXY_SECRET", "").strip()
    if not secret:
        return {}
    return {"X-HomeFit-Proxy-Secret": secret}


MIN_CONFIDENCE = 50  # pillars below this are treated as failed

# These pillars are structurally low-confidence for vacation destinations
# (sparse healthcare data for small towns, no major airport = legitimate 0%)
CONFIDENCE_EXEMPT = {"healthcare_access", "air_travel_access"}


def _has_good_scores(obj: dict) -> bool:
    """Return True if the place has a complete set of pillar scores (score != None for all weighted pillars)."""
    pillars = obj.get("pillars", {})
    if not pillars:
        return False
    for name, pdata in pillars.items():
        if (pdata.get("weight") or 0) == 0:
            continue
        if pdata.get("score") is None:
            return False
    return True


def load_completed(path: Path) -> set:
    keys: set = set()
    if not path.exists():
        return keys
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("success") and _has_good_scores(obj):
                keys.add((obj.get("location"), obj.get("trip_type")))
    return keys


def _submit_and_poll(
    session: requests.Session,
    base_url: str,
    location: str,
    trip_type: str,
    travel_month: int,
    only_pillars: Optional[list] = None,
    timeout: int = 600,
) -> dict:
    headers = proxy_headers()
    params = {
        "location": location,
        "mode": "vacation",
        "trip_type": trip_type,
        "travel_month": travel_month,
    }
    if trip_type == "beach":
        params["natural_beauty_preference"] = '["ocean"]'
    elif trip_type == "mountain":
        params["natural_beauty_preference"] = '["mountains"]'
    if only_pillars:
        params["only"] = ",".join(only_pillars)

    r = session.post(f"{base_url}/score/jobs", params=params, headers=headers, timeout=30)
    r.raise_for_status()
    job = r.json()
    job_id = job.get("job_id") or job.get("id")
    if not job_id:
        raise ValueError(f"No job_id in response: {job}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        pr = session.get(f"{base_url}/score/jobs/{job_id}", headers=headers, timeout=15)
        pr.raise_for_status()
        pj = pr.json()
        status = pj.get("status")
        if status == "done":
            return pj.get("result") or pj
        if status not in ("pending", "running", "queued"):
            raise ValueError(f"Job ended with status={status}")
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def _low_conf_pillars(pillars: dict) -> list:
    """Pillars with no score at all (None) — these need a rescore."""
    return [k for k, v in pillars.items()
            if (v.get("weight") or 0) > 0 and v.get("score") is None]


def run_one(base_url: str, location: str, trip_type: str, output: Path,
            existing: Optional[dict] = None) -> dict:
    travel_month = TRIP_TYPE_MONTH.get(trip_type, 7)
    session = requests.Session()

    # Start from existing partial result if available
    result = existing.copy() if existing else {"location": location, "trip_type": trip_type}
    result["success"] = False
    existing_pillars = result.get("pillars", {})

    # Determine which pillars need scoring
    low = _low_conf_pillars(existing_pillars)
    only = low if existing_pillars and low else None  # full score if no existing data

    try:
        t0 = time.time()
        score_data = _submit_and_poll(session, base_url, location, trip_type, travel_month, only_pillars=only)
        elapsed = time.time() - t0

        new_pillars = {
            k: {"score": v.get("score"), "weight": v.get("weight"), "confidence": v.get("confidence")}
            for k, v in score_data.get("livability_pillars", {}).items()
        }

        # Merge: new scores overwrite old only for the pillars that were re-scored
        merged_pillars = {**existing_pillars, **new_pillars}

        # Recompute total from merged pillars
        total_weight = sum((v.get("weight") or 0) for v in merged_pillars.values())
        if total_weight > 0:
            merged_total = sum(
                (v.get("score") or 0) * (v.get("weight") or 0)
                for v in merged_pillars.values()
            ) / total_weight
        else:
            merged_total = score_data.get("total_score") or 0

        result.update({
            "elapsed_s": round(elapsed, 1),
            "total_score": round(merged_total, 1),
            "allocation_type": score_data.get("allocation_type") or score_data.get("metadata", {}).get("allocation_type") or result.get("allocation_type"),
            "pillars": merged_pillars,
            "score_data": score_data,
        })

        low_after = _low_conf_pillars(merged_pillars)
        if not low_after:
            result["success"] = True
            label = f"patched {low}" if only else "full score"
            print(f"  ✅ {location} ({trip_type}) → {merged_total:.1f}  [{elapsed:.0f}s] ({label})")
        else:
            result["error"] = f"low confidence pillars: {low_after}"
            print(f"  ⚠️  {location} ({trip_type}) → still low conf on {low_after}")
    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ {location} ({trip_type}) → {e}")

    with open(output, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    parser.add_argument("--base-url", default="https://home-fit-production.up.railway.app")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Load existing results: best entry per (location, trip_type)
    existing_map: dict = {}  # (loc, tt) -> best partial result so far
    if output.exists():
        with output.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = (obj.get("location"), obj.get("trip_type"))
                prev = existing_map.get(key)
                # Keep the entry with the most high-confidence pillars
                def _good_count(o):
                    return sum(1 for v in o.get("pillars", {}).values()
                               if (v.get("weight") or 0) > 0 and (v.get("confidence") or 0) >= MIN_CONFIDENCE)
                if prev is None or _good_count(obj) > _good_count(prev):
                    existing_map[key] = obj

    completed = {k for k, v in existing_map.items() if v.get("success") and _has_good_scores(v)}

    # Rewrite JSONL with only the best entry per location (drop duplicates/failures)
    with output.open("w") as f:
        for obj in existing_map.values():
            f.write(json.dumps(obj) + "\n")

    todo = [(loc, tt) for loc, tt in DESTINATIONS_DEDUPED if (loc, tt) not in completed]

    print(f"Vacation batch scoring: {len(todo)} to score/patch, {len(completed)} already done")
    print(f"Output: {output}\n")

    if not todo:
        print("All done.")
        return

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(run_one, args.base_url, loc, tt, output, existing_map.get((loc, tt))): (loc, tt)
            for loc, tt in todo
        }
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                loc, tt = futures[fut]
                print(f"  💥 {loc} ({tt}) uncaught: {e}")

    # Summary
    all_results = []
    with output.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    all_results.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    successes = [r for r in all_results if r.get("success")]
    print(f"\n{'='*60}")
    print(f"Done. {len(successes)}/{len(DESTINATIONS_DEDUPED)} scored successfully.")
    if successes:
        ranked = sorted(successes, key=lambda r: r.get("total_score") or 0, reverse=True)
        print("\nTop 10:")
        for r in ranked[:10]:
            print(f"  {r['total_score']:5.1f}  {r['location']} ({r['trip_type']})")


if __name__ == "__main__":
    main()
