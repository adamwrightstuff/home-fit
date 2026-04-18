#!/usr/bin/env python3
"""
Verify the Rescore Pillar (single-pillar score) flow works end-to-end.

This exercises the same path the frontend uses when the user clicks
"Rescore this pillar": API creates a job with only=<pillar>, backend runs
only that pillar, returns a ScoreResponse with that pillar + total_score.

Usage:
  python scripts/catalog/verify_rescore_pillar.py [BASE_URL]

  BASE_URL defaults to http://localhost:8000 (no proxy auth when HOMEFIT_PROXY_SECRET is unset).
  For Railway/production, set BASE_URL and ensure X-HomeFit-Proxy-Secret is set in the env
  (this script does not send it; use from a context that has it if needed).
"""
import json
import sys
import time

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

DEFAULT_BASE = "http://localhost:8000"
LOCATION = "Capitol Hill Seattle WA"
PILLAR = "neighborhood_amenities"
POLL_INTERVAL = 2.0
MAX_WAIT = 120


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE).rstrip("/")
    print(f"Rescore pillar verification: {base}")
    print(f"  Location: {LOCATION}")
    print(f"  Pillar:   {PILLAR}")
    print()

    # 1) Create job with only=<pillar> (same as frontend getScoreSinglePillar -> only param)
    create_url = f"{base}/score/jobs"
    params = {
        "location": LOCATION,
        "only": PILLAR,
        "include_chains": "true",
        "enable_schools": "false",
    }
    # Backend expects GET-style query params; POST with params= is correct for requests
    try:
        r = requests.post(create_url, params=params, timeout=30)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to {create_url}")
        print("  Start backend: uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if r.status_code == 401:
        print("ERROR: 401 Unauthorized. Set HOMEFIT_PROXY_SECRET or run without it (local).")
        sys.exit(1)
    if r.status_code != 200:
        print(f"ERROR: Create job returned {r.status_code}")
        print(r.text[:500])
        sys.exit(1)

    data = r.json()
    job_id = data.get("job_id")
    if not job_id:
        print("ERROR: No job_id in response")
        print(json.dumps(data, indent=2))
        sys.exit(1)
    print(f"  Job created: {job_id}")

    # 2) Poll until done or error
    poll_url = f"{base}/score/jobs/{job_id}"
    start = time.time()
    while True:
        time.sleep(POLL_INTERVAL)
        if time.time() - start > MAX_WAIT:
            print("ERROR: Timeout waiting for job")
            sys.exit(1)
        try:
            r = requests.get(poll_url, timeout=10)
        except Exception as e:
            print(f"  Poll error: {e}")
            continue
        if r.status_code == 404:
            print("ERROR: Job not found (404)")
            sys.exit(1)
        if r.status_code != 200:
            print(f"ERROR: Poll returned {r.status_code}")
            sys.exit(1)
        data = r.json()
        status = data.get("status", "")
        if status == "error":
            detail = data.get("error") or data.get("detail") or "Unknown error"
            print(f"ERROR: Job failed: {detail}")
            sys.exit(1)
        if status == "done":
            result = data.get("result")
            if not result:
                print("ERROR: status=done but no result")
                sys.exit(1)
            break
        print(f"  status={status} ...")

    # 3) Assert rescore response shape and content
    pillars = result.get("livability_pillars") or {}
    if PILLAR not in pillars:
        print(f"ERROR: Result missing requested pillar '{PILLAR}'")
        print("  Keys in livability_pillars:", list(pillars.keys()))
        sys.exit(1)

    p = pillars[PILLAR]
    if not isinstance(p, dict):
        print(f"ERROR: livability_pillars.{PILLAR} is not a dict: {type(p)}")
        sys.exit(1)
    score = p.get("score")
    if not isinstance(score, (int, float)):
        print(f"ERROR: livability_pillars.{PILLAR}.score missing or not numeric: {score}")
        sys.exit(1)
    if not (0 <= score <= 100):
        print(f"ERROR: livability_pillars.{PILLAR}.score out of range [0,100]: {score}")
        sys.exit(1)

    total = result.get("total_score")
    if not isinstance(total, (int, float)):
        print(f"ERROR: total_score missing or not numeric: {total}")
        sys.exit(1)

    meta = result.get("metadata") or {}
    requested = meta.get("pillars_requested")
    if requested is not None and PILLAR not in requested:
        print(f"ERROR: metadata.pillars_requested should include '{PILLAR}': {requested}")
        sys.exit(1)

    print()
    print("  Result:")
    print(f"    livability_pillars.{PILLAR}.score = {score}")
    print(f"    total_score = {total}")
    print(f"    metadata.pillars_requested = {requested}")
    print()
    print("OK Rescore pillar flow is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
