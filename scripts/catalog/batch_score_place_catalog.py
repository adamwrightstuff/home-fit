#!/usr/bin/env python3
"""
Batch-score every row in data/nyc_metro_place_catalog.csv against the HomeFit API.

- Schools are off by default (enable_schools=false).
- Writes one JSON object per line (JSONL) for easy streaming and resume.

Usage (API on localhost, no proxy secret in dev):

  cd /path/to/home-fit
  python3 scripts/catalog/batch_score_place_catalog.py

With catalog centroids pinned (POST /score/jobs + lat/lon from CSV; polls until done):

  python3 scripts/catalog/batch_score_place_catalog.py --use-catalog-coordinates

If HOMEFIT_PROXY_SECRET is set in the environment, sends X-HomeFit-Proxy-Secret automatically.

Resume: re-run with the same --output path; successful rows are skipped.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "data" / "nyc_metro_place_catalog.csv"
DEFAULT_OUT = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores.jsonl"


def catalog_key(row: Dict[str, str]) -> str:
    return f"{row.get('name', '')}|{row.get('county_borough', '')}|{row.get('state_abbr', '')}"


def proxy_headers() -> Dict[str, str]:
    secret = os.environ.get("HOMEFIT_PROXY_SECRET", "").strip()
    if not secret:
        return {}
    return {"X-HomeFit-Proxy-Secret": secret}


def load_completed_keys(path: Path) -> set:
    keys: set = set()
    if not path.exists():
        return keys
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not obj.get("success"):
                continue
            cat = obj.get("catalog")
            if isinstance(cat, dict):
                keys.add(catalog_key(cat))
    return keys


def read_catalog_rows(csv_path: Path) -> List[Dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score_sync(
    session: requests.Session,
    base_url: str,
    location: str,
    timeout: int,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/score"
    r = session.get(
        url,
        params={"location": location, "enable_schools": "false"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def score_via_job(
    session: requests.Session,
    base_url: str,
    location: str,
    lat: float,
    lon: float,
    poll_interval: float,
    job_timeout: int,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/score/jobs"
    r = session.post(
        url,
        params={
            "location": location,
            "enable_schools": "false",
            "lat": str(lat),
            "lon": str(lon),
        },
        timeout=120,
    )
    r.raise_for_status()
    body = r.json()
    job_id = body.get("job_id")
    if not job_id:
        raise RuntimeError(f"No job_id in response: {body}")

    status_url = f"{base_url.rstrip('/')}/score/jobs/{job_id}"
    deadline = time.time() + job_timeout
    while time.time() < deadline:
        time.sleep(poll_interval)
        sr = session.get(status_url, timeout=120)
        sr.raise_for_status()
        st = sr.json()
        status = (st.get("status") or "").lower()
        if status == "done":
            result = st.get("result")
            if result is None:
                raise RuntimeError("Job done but result is null")
            return result
        if status == "error":
            detail = st.get("detail") or st.get("error") or "unknown error"
            raise RuntimeError(f"Job failed: {detail}")

    raise TimeoutError(f"Job {job_id} did not finish within {job_timeout}s")


def main() -> int:
    p = argparse.ArgumentParser(description="Batch score NYC metro place catalog via HomeFit API.")
    p.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Catalog CSV path (default: {DEFAULT_CSV})",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"JSONL output path (default: {DEFAULT_OUT})",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"),
        help="API base URL (default: http://127.0.0.1:8000 or HOMEFIT_API_BASE)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait after each successful request (rate limiting).",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="HTTP timeout for GET /score (seconds).",
    )
    p.add_argument(
        "--job-timeout",
        type=int,
        default=900,
        help="Max seconds to wait for each job when using --use-catalog-coordinates.",
    )
    p.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between GET /score/jobs/{{id}} polls.",
    )
    p.add_argument(
        "--use-catalog-coordinates",
        action="store_true",
        help="Use POST /score/jobs with lat/lon from CSV (pinned centroid). Default is GET /score with search_query only.",
    )
    p.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="If set, only process this many rows (after resume skip), for testing.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rows that would be processed and exit.",
    )
    args = p.parse_args()

    csv_path = args.csv
    if not csv_path.is_file():
        print(f"Catalog not found: {csv_path}", file=sys.stderr)
        return 1

    rows = read_catalog_rows(csv_path)
    out_path = args.output
    done_keys = load_completed_keys(out_path)

    pending = [r for r in rows if catalog_key(r) not in done_keys]
    if args.max_rows > 0:
        pending = pending[: args.max_rows]

    print(f"Catalog rows: {len(rows)} | Already completed: {len(done_keys)} | To run: {len(pending)}")
    if args.dry_run:
        for r in pending[:15]:
            print(f"  would run: {catalog_key(r)} -> {r.get('search_query')}")
        if len(pending) > 15:
            print(f"  ... and {len(pending) - 15} more")
        return 0

    headers = proxy_headers()
    session = requests.Session()
    session.headers.update(headers)

    processed = 0
    with out_path.open("a", encoding="utf-8") as out:
        for i, row in enumerate(pending):
            key = catalog_key(row)
            location = (row.get("search_query") or "").strip()
            if not location:
                record = {
                    "catalog": row,
                    "success": False,
                    "error": "empty search_query",
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[{i + 1}/{len(pending)}] {key} SKIP (empty search_query)")
                continue

            print(f"[{i + 1}/{len(pending)}] {key} …", flush=True)
            try:
                if args.use_catalog_coordinates:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                    result = score_via_job(
                        session,
                        args.base_url,
                        location,
                        lat,
                        lon,
                        args.poll_interval,
                        args.job_timeout,
                    )
                else:
                    result = score_sync(session, args.base_url, location, args.timeout)

                record = {
                    "catalog": row,
                    "success": True,
                    "score": result,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                processed += 1
                print(f"    ok (total_score={result.get('total_score')!r})", flush=True)
            except Exception as e:
                record = {
                    "catalog": row,
                    "success": False,
                    "error": str(e),
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                print(f"    FAIL: {e}", flush=True)

            if i < len(pending) - 1 and args.delay > 0:
                time.sleep(args.delay)

    print(f"Done. Wrote {processed} new successful row(s) to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
