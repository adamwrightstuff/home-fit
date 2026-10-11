#!/usr/bin/env python3
"""
Re-score catalog places whose Overpass queries failed upstream, until clean or out of rounds.

The API reports a pillar as "success" with a score of 0 when Overpass is throttled, so a
failed query is invisible unless you read the stored summary.  Active Outdoors is the pillar
that records it (summary.overpass.{local,trail,regional}); the other Overpass-backed pillars
do not surface their failures.

Each round re-scores (via POST /score/jobs, sequentially) every place that still has a failed
query and keeps the attempt with the fewest failures (ties go to the newer result).  Places
that never come back clean are listed, never silently accepted.  The rewritten rows lose
their post-scoring fields (housing stock, ZIP, political lean, scene, labels), so run
the later score_metro.py phases afterwards (they only fill what is missing / are idempotent).

Usage:
    HOMEFIT_API_BASE=... HOMEFIT_PROXY_SECRET=... PYTHONPATH=. \\
      python3 scripts/catalog/retry_overpass_errors.py --input data/xx_metro_..._recomputed.jsonl
    # report only:
    ... --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

QUERIES = ("local", "trail", "regional")
# A place is "material" when its parks or water query failed; a trail-only miss is tolerated
# after the last round (existing catalogs carry those).
MATERIAL = ("local", "regional")


def overpass_failures(row: Dict[str, Any]) -> List[str]:
    if not row.get("success"):
        return list(QUERIES)
    ao = ((row.get("score") or {}).get("livability_pillars") or {}).get("active_outdoors") or {}
    op = (ao.get("summary") or {}).get("overpass") or {}
    return [q for q in QUERIES if op.get(q) == "overpass_error"]


def _write_atomic(path: Path, rows: List[Dict[str, Any]]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def score_place(session, base_url: str, catalog: Dict[str, Any], poll: float, job_timeout: int) -> Optional[Dict[str, Any]]:
    location = (catalog.get("search_query") or "").strip()
    r = session.post(
        f"{base_url}/score/jobs",
        params={"location": location, "enable_schools": "false", "lat": catalog["lat"],
                "lon": catalog["lon"], "test_mode": "true"},
        timeout=120,
    )
    r.raise_for_status()
    job_id = r.json().get("job_id")
    if not job_id:
        raise RuntimeError(f"no job_id: {r.json()}")
    deadline = time.time() + job_timeout
    while time.time() < deadline:
        time.sleep(poll)
        sr = session.get(f"{base_url}/score/jobs/{job_id}", timeout=120)
        sr.raise_for_status()
        st = sr.json()
        status = (st.get("status") or "").lower()
        if status == "done":
            return st.get("result")
        if status == "error":
            raise RuntimeError(f"job failed: {st.get('detail') or st.get('error')}")
    raise TimeoutError(f"job {job_id} timed out")


def run(path: Path, rounds: int, delay: float, dry_run: bool, base_url: str, secret: str,
        poll: float = 2.0, job_timeout: int = 900) -> int:
    import requests

    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    session = requests.Session()
    if secret:
        session.headers.update({"X-HomeFit-Proxy-Secret": secret})

    def pending(material_only: bool = False) -> List[int]:
        want = MATERIAL if material_only else QUERIES
        return [i for i, r in enumerate(rows) if any(q in want for q in overpass_failures(r))]

    print(f"{path.name}: {len(rows)} places, {len(pending())} with failed Overpass queries")
    if dry_run:
        for i in pending():
            print(f"  {rows[i]['catalog'].get('name')}: {overpass_failures(rows[i])}")
        return 0

    for rnd in range(1, rounds + 1):
        # First two rounds chase every failed query; later rounds only parks/water failures.
        todo = pending(material_only=rnd > 2)
        if not todo:
            break
        print(f"\n--- round {rnd}/{rounds}: {len(todo)} places ---", flush=True)
        improved = 0
        for n, i in enumerate(todo, 1):
            cat = rows[i]["catalog"]
            before = overpass_failures(rows[i])
            try:
                result = score_place(session, base_url, cat, poll, job_timeout)
            except Exception as e:  # noqa: BLE001 - keep looping; the place stays pending
                print(f"  [{n}/{len(todo)}] {cat.get('name')}: ERROR {e}", flush=True)
                time.sleep(delay)
                continue
            cand = {"catalog": cat, "success": True, "score": result}
            after = overpass_failures(cand)
            if len(after) <= len(before) or not rows[i].get("success"):
                rows[i] = cand
                _write_atomic(path, rows)
            flag = "improved" if len(after) < len(before) else "same" if len(after) == len(before) else "worse (kept old)"
            if len(after) < len(before):
                improved += 1
            print(f"  [{n}/{len(todo)}] {cat.get('name')}: {len(before)} -> {len(after)} failed {flag}", flush=True)
            time.sleep(delay)
        print(f"round {rnd}: {improved} improved, {len(pending())} still pending", flush=True)

    left = pending()
    material = [i for i in left if any(q in MATERIAL for q in overpass_failures(rows[i]))]
    print(f"\nDone. {len(left)} places still have a failed query; {len(material)} are material (parks/water).")
    for i in material:
        print(f"  UNRESOLVED {rows[i]['catalog'].get('name')}: {overpass_failures(rows[i])}")
    return 1 if material else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--delay", type=float, default=6.0, help="Seconds between places (be gentle on Overpass).")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    return run(a.input, a.rounds, a.delay, a.dry_run,
               os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000").rstrip("/"),
               os.environ.get("HOMEFIT_PROXY_SECRET", "").strip())


if __name__ == "__main__":
    sys.exit(main())
