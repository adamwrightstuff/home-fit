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
    --in-place --no-backup \\
    --pillars natural_beauty

Then refresh composites (longevity / status / happiness) from the merged file:

  PYTHONPATH=. python3 scripts/recompute_catalog_composites.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \\
    --output data/nyc_metro_place_catalog_scores_merged.jsonl

Re-score only rows where a pillar's confidence is below a threshold (e.g. built_beauty < 92),
with catalog centroids pinned (same coordinates as CSV):

  PYTHONPATH=. python3 scripts/rescore_catalog_pillar.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \\
    --in-place \\
    --pillars built_beauty \\
    --confidence-filter-pillar built_beauty \\
    --confidence-filter-lt 92 \\
    --use-catalog-coordinates

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
from typing import Any, Dict, List, Optional, Tuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass


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


def pillar_confidence(obj: Dict[str, Any], pillar_name: str) -> Optional[float]:
    """Return pillar headline confidence, or data_quality.confidence, or None."""
    score = obj.get("score")
    if not isinstance(score, dict):
        return None
    lp = score.get("livability_pillars")
    if not isinstance(lp, dict):
        return None
    p = lp.get(pillar_name)
    if not isinstance(p, dict):
        return None
    c = p.get("confidence")
    if c is None:
        dq = p.get("data_quality")
        if isinstance(dq, dict):
            c = dq.get("confidence")
    try:
        return float(c) if c is not None else None
    except (TypeError, ValueError):
        return None


def catalog_lat_lon(cat: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Parse catalog lat/lon (strings or floats)."""
    try:
        lat = cat.get("lat")
        lon = cat.get("lon")
        if lat is None or lon is None:
            return None, None
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None


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
        "--no-backup",
        action="store_true",
        help="With --in-place, write the output without creating a timestamped .bak copy.",
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
    ap.add_argument(
        "--confidence-filter-lt",
        type=float,
        default=None,
        metavar="N",
        help="If set, only rescore rows where PILLAR confidence is missing or < N (0-100).",
    )
    ap.add_argument(
        "--confidence-filter-pillar",
        type=str,
        default=None,
        help="Pillar key for --confidence-filter-lt (default: first --pillars key).",
    )
    ap.add_argument(
        "--use-catalog-coordinates",
        action="store_true",
        help="Pass catalog lat/lon to GET /score so scoring uses the same centroid as the catalog CSV.",
    )
    args = ap.parse_args()

    try:
        pillars = parse_pillars(args.pillars)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1

    cf_pillar: Optional[str] = args.confidence_filter_pillar
    if args.confidence_filter_lt is not None:
        if not (0.0 <= args.confidence_filter_lt <= 100.0):
            print("--confidence-filter-lt must be between 0 and 100.", file=sys.stderr)
            return 1
        cf_pillar = cf_pillar or pillars[0]
        if cf_pillar not in pillars:
            print(
                f"--confidence-filter-pillar {cf_pillar!r} must be one of --pillars: {pillars}",
                file=sys.stderr,
            )
            return 1

    inp = args.input
    if not inp.is_file():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    if args.in_place and args.output is not None:
        print("Use either --in-place or --output, not both.", file=sys.stderr)
        return 1
    if args.no_backup and not args.in_place:
        print("--no-backup only applies with --in-place.", file=sys.stderr)
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
        if args.confidence_filter_lt is not None and cf_pillar is not None:
            conf = pillar_confidence(obj, cf_pillar)
            if conf is not None and conf >= args.confidence_filter_lt:
                continue
        to_run.append(key)

    if args.max_places > 0:
        to_run = to_run[: args.max_places]

    print(f"Places in JSONL (last wins): {len(last)}")
    print(f"Rows selected to rescore: {len(to_run)}")
    print(f"Pillars: {', '.join(pillars)}")
    if args.confidence_filter_lt is not None and cf_pillar is not None:
        print(
            f"Confidence filter: {cf_pillar} < {args.confidence_filter_lt} (or missing)"
        )
    if args.use_catalog_coordinates:
        print("Using catalog lat/lon when present on each row.")

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
            plat: Optional[float] = None
            plon: Optional[float] = None
            if args.use_catalog_coordinates:
                plat, plon = catalog_lat_lon(cat)
            new_score = get_score(
                session,
                args.base_url,
                location=location,
                only=pillars,
                timeout=args.timeout,
                lat=plat,
                lon=plon,
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

    if args.in_place and not args.no_backup:
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
