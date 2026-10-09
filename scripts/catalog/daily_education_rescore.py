#!/usr/bin/env python3
"""
Daily SchoolDigger runner: rescore quality_education for catalog places that lack a real score,
one place at a time, saving after each success and stopping at the first bad (obfuscated or
zero) result, which is how SchoolDigger signals an exhausted daily quota.

  cd /Users/adamwright/Dev/home-fit
  # API must be running locally with SCHOOLDIGGER_APPID/APPKEY set
  PYTHONPATH=. python3 scripts/catalog/daily_education_rescore.py

State lives in analysis/education_queue_state.json (attempt counts per place). A place that
returns a bad result twice is skipped from then on (it may genuinely have no rated schools).
After a run, refresh composites:
  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --input FILE --output FILE
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "catalog"))

from rescore_catalog_pillar import (  # noqa: E402
    catalog_lat_lon,
    catalog_key,
    get_score,
    load_last_per_place,
    merge_pillar_response,
    proxy_headers,
)

PILLAR = "quality_education"
METRO_ORDER = ["nyc", "la", "seattle", "sf"]
STATE_PATH = REPO_ROOT / "analysis" / "education_queue_state.json"
MAX_ATTEMPTS = 2


def catalog_file(metro: str) -> Path:
    return REPO_ROOT / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"


def is_missing(obj: Dict[str, Any]) -> bool:
    p = ((obj.get("score") or {}).get("livability_pillars") or {}).get(PILLAR) or {}
    return not p.get("score") or (p.get("confidence") or 0) < 1


def write_atomic(path: Path, last: Dict[str, Dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for key in sorted(last):
            f.write(json.dumps(last[key], ensure_ascii=False) + "\n")
    tmp.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base-url", default=os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"))
    ap.add_argument("--delay", type=float, default=65.0, help="Seconds between places (plan limit is 1/min).")
    ap.add_argument("--max-places", type=int, default=0, help="Cap places this run (0 = until quota stops it).")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    state: Dict[str, int] = {}
    if STATE_PATH.is_file():
        state = json.loads(STATE_PATH.read_text())

    data: Dict[str, Dict[str, Dict[str, Any]]] = {}
    queue: List[tuple] = []
    for metro in METRO_ORDER:
        path = catalog_file(metro)
        if not path.is_file():
            continue
        data[metro] = load_last_per_place(path)
        for key in sorted(data[metro]):
            obj = data[metro][key]
            cat = obj.get("catalog") or {}
            if not obj.get("success") or not (cat.get("search_query") or "").strip():
                continue
            if is_missing(obj) and state.get(f"{metro}:{key}", 0) < MAX_ATTEMPTS:
                queue.append((metro, key))

    print(f"Queue: {len(queue)} places still missing education")
    if args.dry_run:
        for metro, key in queue[:20]:
            print(f"  {metro}: {data[metro][key]['catalog'].get('name')}")
        return 0

    session = requests.Session()
    session.headers.update(proxy_headers())
    done = 0
    for metro, key in queue:
        if args.max_places and done >= args.max_places:
            break
        obj = data[metro][key]
        cat = obj["catalog"]
        label = f"{metro}: {cat.get('name')}"
        lat, lon = catalog_lat_lon(cat)
        print(f"[{done + 1}] {label} ...", flush=True)
        try:
            resp = get_score(
                session, args.base_url,
                location=cat["search_query"].strip(), only=[PILLAR],
                timeout=args.timeout, lat=lat, lon=lon, enable_schools=True,
            )
        except Exception as e:
            print(f"    request failed ({e}); stopping without counting an attempt.")
            break
        new_p = (resp.get("livability_pillars") or {}).get(PILLAR) or {}
        if not new_p.get("score"):
            state[f"{metro}:{key}"] = state.get(f"{metro}:{key}", 0) + 1
            STATE_PATH.write_text(json.dumps(state, indent=1))
            print("    bad result (no score, likely quota exhausted). Stopping for today.")
            break
        data[metro][key] = merge_pillar_response(obj, resp, [PILLAR])
        write_atomic(catalog_file(metro), data[metro])
        done += 1
        print(f"    saved {PILLAR}={new_p['score']}", flush=True)
        time.sleep(args.delay)

    print(f"Done: {done} places scored today, {len(queue) - done} remaining.")
    if done:
        print("Next: recompute composites for the touched metro file(s), then commit and push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
