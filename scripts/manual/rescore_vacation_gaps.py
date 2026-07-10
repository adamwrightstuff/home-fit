#!/usr/bin/env python3
"""
Rescore only the failing pillars (score=0/conf=0) for vacation destinations.
Merges results back into the existing JSONL.

Usage:
  cd /path/to/home-fit
  HOMEFIT_PROXY_SECRET=<secret> python3 scripts/manual/rescore_vacation_gaps.py
"""
from __future__ import annotations
import json, os, time, requests
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
JSONL = REPO_ROOT / "data" / "vacation_destinations_scores.jsonl"
BASE_URL = os.environ.get("HOMEFIT_API_URL", "https://home-fit-production.up.railway.app")
HEADERS = {"X-HomeFit-Proxy-Secret": os.environ["HOMEFIT_PROXY_SECRET"]}
TRIP_TYPE_MONTH = {"beach": 7, "mountain": 7, "city": 10}
EXEMPT = {"healthcare_access", "air_travel_access"}


def _failing_pillars(pillars: dict) -> list:
    return [k for k, v in pillars.items()
            if k not in EXEMPT
            and (v.get("weight") or 0) > 0
            and (v.get("score") is None or (v.get("confidence") or 0) == 0)]


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
            # Keep entry with most non-zero pillar scores
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

    todo = {k: _failing_pillars(r.get("pillars", {}))
            for k, r in rows.items()
            if _failing_pillars(r.get("pillars", {}))}

    print(f"{len(todo)} places need pillar rescores\n")

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

            # Merge new scores into existing
            row = rows[(loc, tt)]
            merged = {**row.get("pillars", {}), **new_pillars}

            # Recompute total
            total_w = sum((v.get("weight") or 0) for v in merged.values())
            total_score = (
                sum((v.get("score") or 0) * (v.get("weight") or 0) for v in merged.values()) / total_w
                if total_w > 0 else 0
            )

            row["pillars"] = merged
            row["total_score"] = round(total_score, 1)
            row["success"] = True

            still_bad = _failing_pillars(merged)
            if still_bad:
                print(f"    ⚠️  still failing: {still_bad}  ({elapsed:.0f}s)")
            else:
                print(f"    ✅ {loc} → {total_score:.1f}  ({elapsed:.0f}s)")

        except Exception as e:
            print(f"    ❌ {e}")

    save_rows(rows)

    print(f"\nDone. Rankings:")
    ranked = sorted(rows.values(), key=lambda r: r.get("total_score") or 0, reverse=True)
    for r in ranked:
        print(f"  {r.get('total_score',0):5.1f}  {r['location']} ({r['trip_type']})")


if __name__ == "__main__":
    main()
