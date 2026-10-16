#!/usr/bin/env python3
"""
Pull whole states from SchoolDigger into the local snapshot (500 schools per request).

  PYTHONPATH=. python3 scripts/catalog/fetch_school_snapshot.py --states NY,NJ,CT
  PYTHONPATH=. python3 scripts/catalog/fetch_school_snapshot.py --states PA --force

About 1 call per 500 schools in the state (CT 3, NY about 14, CA about 27). A state already in the
snapshot is skipped unless --force or the snapshot is older than --max-age-days (default 330), so a
new metro in a covered state costs nothing. Ratings update yearly: refresh once a year.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from data_sources import school_snapshot as ss  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--states", required=True, help="comma-separated, e.g. NY,NJ,CT")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-age-days", type=int, default=330)
    args = ap.parse_args()
    app_id, app_key = os.getenv("SCHOOLDIGGER_APPID"), os.getenv("SCHOOLDIGGER_APPKEY")
    if not app_id or not app_key:
        print("SCHOOLDIGGER_APPID / SCHOOLDIGGER_APPKEY not set")
        return 1
    total = 0
    for st in [s.strip().upper() for s in args.states.split(",") if s.strip()]:
        snap = ss.load_state(st)
        if snap and not args.force:
            age = (time.time() - os.path.getmtime(ss._path(st))) / 86400
            if age < args.max_age_days:
                print(f"{st}: snapshot is {age:.0f} days old ({snap['meta']['count']} schools), skipping")
                continue
        meta = ss.fetch_state(st, app_id, app_key)
        total += meta["calls"]
        print(f"{st}: {meta['count']} schools in {meta['calls']} calls")
    print(f"done, {total} SchoolDigger calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
