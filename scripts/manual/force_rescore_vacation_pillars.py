#!/usr/bin/env python3
"""
Force-rescore specific pillars for vacation destinations regardless of existing scores.
Use after adding airports or changing scoring logic to pick up improvements.

Usage:
  cd /path/to/home-fit
  HOMEFIT_PROXY_SECRET=<secret> python3 scripts/manual/force_rescore_vacation_pillars.py
"""
from __future__ import annotations
import json, os, time, requests
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
JSONL = REPO_ROOT / "data" / "vacation_destinations_scores.jsonl"
BASE_URL = os.environ.get("HOMEFIT_API_URL", "https://home-fit-production.up.railway.app")
HEADERS = {"X-HomeFit-Proxy-Secret": os.environ["HOMEFIT_PROXY_SECRET"]}
TRIP_TYPE_MONTH = {"beach": 7, "mountain": 7, "city": 10}

# Rescore air_travel for places that had 0.0 because airports were missing from DB.
# Rescore active_outdoors for all mountain destinations with the new is_mountain_town fix.
FORCE_AIR_TRAVEL = {
    "Virginia Beach, VA",
    "Bar Harbor, ME",
    "Kill Devil Hills, NC",
    "Bend, OR",
    "Moab, UT",
    "Telluride, CO",
    "Memphis, TN",
}

FORCE_ACTIVE_OUTDOORS_MOUNTAIN = True  # rescore AO for all mountain trip_type


def poll_job(job_id: str, timeout: int = 600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        r = requests.get(f"{BASE_URL}/score/jobs/{job_id}", headers=HEADERS, timeout=15)
        r.raise_for_status()
        pj = r.json()
        status = pj.get("status")
        if status == "done":
            return pj.get("result") or pj
        if status not in ("pending", "running", "queued"):
            raise ValueError(f"Job status={status}")
    raise TimeoutError(f"Job {job_id} timed out")


def rescore_pillars(location: str, trip_type: str, pillars: list) -> dict:
    travel_month = TRIP_TYPE_MONTH.get(trip_type, 7)
    params = {
        "location": location,
        "mode": "vacation",
        "trip_type": trip_type,
        "travel_month": travel_month,
        "only": ",".join(pillars),
    }
    if trip_type == "beach":
        params["natural_beauty_preference"] = '["ocean"]'
    elif trip_type == "mountain":
        params["natural_beauty_preference"] = '["mountains"]'
    r = requests.post(f"{BASE_URL}/score/jobs", params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    job = r.json()
    job_id = job.get("job_id") or job.get("id")
    if not job_id:
        raise ValueError(f"No job_id: {job}")
    return poll_job(job_id)


def load_rows() -> dict:
    rows = {}
    if not JSONL.exists():
        return rows
    for line in JSONL.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        k = (r.get("location"), r.get("trip_type"))
        prev = rows.get(k)
        if prev is None:
            rows[k] = r
        else:
            def good(o):
                return sum(1 for v in o.get("pillars", {}).values()
                           if (v.get("score") or 0) > 0)
            if good(r) > good(prev):
                rows[k] = r
    return rows


def save_rows(rows: dict):
    lines = [json.dumps(r) for r in rows.values()]
    JSONL.write_text("\n".join(lines) + "\n")


def main():
    rows = load_rows()

    todo: dict[tuple, list] = {}
    for (loc, tt), row in rows.items():
        pillars_to_rescore = []
        if loc in FORCE_AIR_TRAVEL:
            pillars_to_rescore.append("air_travel_access")
        if FORCE_ACTIVE_OUTDOORS_MOUNTAIN and tt == "mountain":
            ao = row.get("pillars", {}).get("active_outdoors", {})
            # Only rescore if confidence is 0 (Overpass timeout) or score suspiciously low for a mountain resort
            if (ao.get("confidence") or 0) == 0 or (ao.get("score") or 0) < 20:
                pillars_to_rescore.append("active_outdoors")
        if pillars_to_rescore:
            todo[(loc, tt)] = pillars_to_rescore

    print(f"{len(todo)} places to force-rescore\n")

    for (loc, tt), pillars in sorted(todo.items()):
        print(f"  {loc} ({tt}) → rescoring {pillars}")
        try:
            t0 = time.time()
            result = rescore_pillars(loc, tt, pillars)
            elapsed = time.time() - t0

            new_pillars = {
                k: {"score": v.get("score"), "weight": v.get("weight"), "confidence": v.get("confidence")}
                for k, v in result.get("livability_pillars", {}).items()
            }

            row = rows[(loc, tt)]
            merged = {**row.get("pillars", {}), **new_pillars}

            total_w = sum((v.get("weight") or 0) for v in merged.values())
            total_score = (
                sum((v.get("score") or 0) * (v.get("weight") or 0) for v in merged.values()) / total_w
                if total_w > 0 else 0
            )

            old_score = row.get("total_score", 0)
            row["pillars"] = merged
            row["total_score"] = round(total_score, 1)

            for p in pillars:
                old = row.get("pillars", {}).get(p, {})
                new = new_pillars.get(p, {})
                print(f"    {p}: {old.get('score','?')} → {new.get('score','?')} (conf={new.get('confidence','?')})")
            print(f"    total: {old_score} → {total_score:.1f}  ({elapsed:.0f}s)")

        except Exception as e:
            print(f"    ❌ {e}")

    save_rows(rows)

    print(f"\nDone. Rankings:")
    ranked = sorted(rows.values(), key=lambda r: r.get("total_score") or 0, reverse=True)
    for r in ranked:
        ao = r.get("pillars", {}).get("active_outdoors", {})
        at = r.get("pillars", {}).get("air_travel_access", {})
        print(f"  {r.get('total_score',0):5.1f}  {r['location']:35s} ({r['trip_type']:8s})  "
              f"AO={ao.get('score','?')}/c{ao.get('confidence','?')}  Air={at.get('score','?')}/c{at.get('confidence','?')}")


if __name__ == "__main__":
    main()
