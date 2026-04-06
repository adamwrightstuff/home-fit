#!/usr/bin/env python3
"""
Re-score one or more pillars for every successful row in a catalog JSONL via GET /score?only=...

Merges returned livability_pillars into the existing score, recomputes total_score (equal tokens,
schools off — same as rerun_failed_catalog_pillars.recompute_totals).

Typical use after changing pillar code (e.g. natural_beauty):

  cd /path/to/home-fit
  # API must be running with new code (e.g. uvicorn main:app)
  PYTHONPATH=. python3 scripts/rescore_catalog_pillar.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \\
    --in-place \\
    --pillars natural_beauty

Then refresh composites (longevity / status / happiness) from the merged file:

  PYTHONPATH=. python3 scripts/recompute_catalog_composites.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \\
    --output data/nyc_metro_place_catalog_scores_merged.jsonl

HOMEFIT_API_BASE and HOMEFIT_PROXY_SECRET are respected.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_rerun_module():
    path = REPO_ROOT / "scripts" / "rerun_failed_catalog_pillars.py"
    spec = importlib.util.spec_from_file_location("rerun_failed_catalog_pillars", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_rerun = _load_rerun_module()
catalog_key = _rerun.catalog_key
get_score = _rerun.get_score
load_last_per_place = _rerun.load_last_per_place
proxy_headers = _rerun.proxy_headers
recompute_totals = _rerun.recompute_totals
PILLAR_ORDER: List[str] = list(_rerun.PILLAR_ORDER)


def parse_pillars(raw: str) -> List[str]:
    parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    if not parts:
        raise ValueError("empty --pillars")
    unknown = [p for p in parts if p not in PILLAR_ORDER]
    if unknown:
        raise ValueError(f"Unknown pillar(s): {unknown}. Valid: {PILLAR_ORDER}")
    return parts


def merge_pillar_response(
    existing: Dict[str, Any],
    new_score: Dict[str, Any],
    pillars: List[str],
) -> Dict[str, Any]:
    merged = copy.deepcopy(existing)
    old = (merged.get("score") or {}) if isinstance(merged.get("score"), dict) else {}
    new_pillars = new_score.get("livability_pillars") or {}
    if not isinstance(old.get("livability_pillars"), dict):
        old["livability_pillars"] = {}
    lp = copy.deepcopy(old["livability_pillars"])

    if isinstance(new_pillars, dict):
        for k in pillars:
            if k in new_pillars:
                lp[k] = new_pillars[k]

    old["livability_pillars"] = lp
    for fld in ("input", "coordinates", "location_info"):
        if fld in new_score and new_score[fld]:
            old[fld] = new_score[fld]
    merged["score"] = old
    recompute_totals(merged["score"])
    merged["success"] = True
    merged.pop("error", None)
    merged["merge_note"] = f"rescore_catalog_pillar_v1|{','.join(pillars)}"
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Re-score selected pillar(s) for every catalog row via GET /score?only=..."
    )
    ap.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl",
        help="Source JSONL (last line per catalog key wins when reading)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL path. Use with --in-place omitted, or omit when using --in-place.",
    )
    ap.add_argument(
        "--in-place",
        action="store_true",
        help="Write back to --input after a timestamped .bak copy (same path as input).",
    )
    ap.add_argument(
        "--pillars",
        type=str,
        default="natural_beauty",
        help="Comma-separated pillar keys (default: natural_beauty).",
    )
    ap.add_argument(
        "--base-url",
        default=os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"),
        help="HomeFit API base URL",
    )
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between successful HTTP calls.")
    ap.add_argument("--timeout", type=int, default=900, help="Per-request timeout (seconds).")
    ap.add_argument(
        "--max-places",
        type=int,
        default=0,
        help="If set, only process this many places (after sort by key), for testing.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="List places that would be scored and exit.",
    )
    args = ap.parse_args()

    try:
        pillars = parse_pillars(args.pillars)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    inp = args.input
    if not inp.is_file():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    if args.in_place and args.output is not None:
        print("Use either --in-place or --output, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.in_place and args.output is None:
        print("Specify --output PATH or --in-place (not required for --dry-run).", file=sys.stderr)
        return 1

    out_path: Path
    if args.in_place:
        out_path = inp
    else:
        out_path = args.output  # type: ignore

    last = load_last_per_place(inp)
    session = requests.Session()
    session.headers.update(proxy_headers())

    keys_sorted = sorted(last.keys())
    if args.max_places > 0:
        keys_sorted = keys_sorted[: args.max_places]

    to_run: List[str] = []
    for key in keys_sorted:
        obj = last[key]
        if not obj.get("success"):
            continue
        cat = obj.get("catalog") or {}
        if not isinstance(cat, dict):
            continue
        if not (cat.get("search_query") or "").strip():
            continue
        to_run.append(key)

    print(f"Places in JSONL (last wins): {len(last)}")
    print(f"Successful rows with search_query to rescore: {len(to_run)}")
    print(f"Pillars: {', '.join(pillars)}")

    if args.dry_run:
        for k in to_run[:30]:
            print(f"  {k}")
        if len(to_run) > 30:
            print(f"  ... {len(to_run) - 30} more")
        return 0

    out_merged: Dict[str, Dict[str, Any]] = {}
    errors = 0

    for i, key in enumerate(to_run):
        obj = last[key]
        cat = obj.get("catalog") or {}
        location = (cat.get("search_query") or "").strip()
        label = cat.get("name", key)
        print(f"[{i + 1}/{len(to_run)}] {label} …", flush=True)
        try:
            new_score = get_score(
                session,
                args.base_url,
                location=location,
                only=pillars,
                timeout=args.timeout,
            )
            merged = merge_pillar_response(obj, new_score, pillars)
            out_merged[key] = merged
        except Exception as e:
            print(f"    FAIL: {e}", flush=True)
            errors += 1
            fail = copy.deepcopy(obj)
            fail["merge_note"] = f"rescore_catalog_pillar_error:{e}"
            out_merged[key] = fail

        if i < len(to_run) - 1 and args.delay > 0:
            time.sleep(args.delay)

    out_lines: List[str] = []
    for key in sorted(last.keys()):
        if key in out_merged:
            out_lines.append(json.dumps(out_merged[key], ensure_ascii=False))
        else:
            out_lines.append(json.dumps(last[key], ensure_ascii=False))

    if args.in_place:
        bak = inp.parent / f"{inp.name}.bak.{time.strftime('%Y%m%d-%H%M%S')}"
        bak.write_text(inp.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup: {bak}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for line in out_lines:
            f.write(line + "\n")

    ok = sum(
        1
        for k in out_merged
        if isinstance(out_merged[k].get("merge_note"), str)
        and str(out_merged[k]["merge_note"]).startswith("rescore_catalog_pillar_v1")
    )
    print(f"Wrote {len(out_lines)} lines to {out_path} ({ok} merged OK, {errors} errors)")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
