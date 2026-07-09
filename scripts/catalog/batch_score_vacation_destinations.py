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
    ("Outer Banks, NC",         "beach"),
    ("Hilton Head, SC",         "beach"),
    ("Key West, FL",            "beach"),
    ("Destin, FL",              "beach"),
    ("Santa Barbara, CA",       "beach"),
    ("Malibu, CA",              "beach"),
    ("Monterey, CA",            "beach"),
    ("Newport, RI",             "beach"),
    ("Cape Cod, MA",            "beach"),
    ("Bar Harbor, ME",          "beach"),
    ("Rehoboth Beach, DE",      "beach"),
    ("Galveston, TX",           "beach"),
    # Mountain
    ("Aspen, CO",               "mountain"),
    ("Sedona, AZ",              "mountain"),
    ("Park City, UT",           "mountain"),
    ("Jackson Hole, WY",        "mountain"),
    ("Breckenridge, CO",        "mountain"),
    ("Vail, CO",                "mountain"),
    ("Telluride, CO",           "mountain"),
    ("Steamboat Springs, CO",   "mountain"),
    ("Lake Tahoe, CA",          "mountain"),
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


def _has_good_scores(obj: dict) -> bool:
    """Return True only if every weighted pillar has confidence >= MIN_CONFIDENCE."""
    pillars = obj.get("pillars", {})
    if not pillars:
        return False
    for pdata in pillars.values():
        weight = pdata.get("weight") or 0
        if weight == 0:
            continue
        conf = pdata.get("confidence")
        if conf is None or conf < MIN_CONFIDENCE:
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


def score_destination(
    session: requests.Session,
    base_url: str,
    location: str,
    trip_type: str,
    travel_month: int,
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


def run_one(base_url: str, location: str, trip_type: str, output: Path) -> dict:
    travel_month = TRIP_TYPE_MONTH.get(trip_type, 7)
    session = requests.Session()
    result = {"location": location, "trip_type": trip_type, "success": False}
    try:
        t0 = time.time()
        score_data = score_destination(session, base_url, location, trip_type, travel_month)
        elapsed = time.time() - t0
        pillars = {
            k: {"score": v.get("score"), "weight": v.get("weight"), "confidence": v.get("confidence")}
            for k, v in score_data.get("livability_pillars", {}).items()
        }
        result.update({
            "elapsed_s": round(elapsed, 1),
            "total_score": score_data.get("total_score"),
            "allocation_type": score_data.get("allocation_type") or score_data.get("metadata", {}).get("allocation_type"),
            "pillars": pillars,
            "score_data": score_data,
        })
        if _has_good_scores(result):
            result["success"] = True
            print(f"  ✅ {location} ({trip_type}) → {score_data.get('total_score', '?'):.1f}  [{elapsed:.0f}s]")
        else:
            low = [k for k, v in pillars.items() if (v.get("weight") or 0) > 0 and (v.get("confidence") or 0) < MIN_CONFIDENCE]
            result["error"] = f"low confidence pillars: {low}"
            print(f"  ⚠️  {location} ({trip_type}) → low conf on {low}, will retry")
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

    completed = load_completed(output)

    # Rewrite JSONL keeping only good entries so bad ones get replaced
    if output.exists():
        good_lines = []
        with output.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("success") and _has_good_scores(obj):
                        good_lines.append(line)
                except json.JSONDecodeError:
                    pass
        with output.open("w") as f:
            for line in good_lines:
                f.write(line + "\n")

    todo = [(loc, tt) for loc, tt in DESTINATIONS_DEDUPED if (loc, tt) not in completed]

    print(f"Vacation batch scoring: {len(todo)} to score, {len(completed)} already done")
    print(f"Output: {output}\n")

    if not todo:
        print("All done.")
        return

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(run_one, args.base_url, loc, tt, output): (loc, tt)
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
