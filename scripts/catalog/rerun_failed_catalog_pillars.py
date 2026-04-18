#!/usr/bin/env python3
"""
Re-run pillars that failed in a catalog batch JSONL, merge into the saved score, recompute total.

- Uses GET /score with only=pillar1,pillar2,... when some pillars failed (enable_schools=false).
- Uses full GET /score (no only=) when the row has success=false or invalid score.

Failure detection matches scripts/catalog/report_catalog_pillar_health.py (pillar error, failed status,
low-confidence fallback, missing score; quality_education optional when schools disabled).

Writes a new JSONL (does not overwrite input).

  python3 scripts/catalog/rerun_failed_catalog_pillars.py \\
    --input data/nyc_metro_place_catalog_scores.jsonl \\
    --output data/nyc_metro_place_catalog_scores_merged.jsonl

HOMEFIT_API_BASE and HOMEFIT_PROXY_SECRET are respected.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]

PILLAR_ORDER: List[str] = [
    "quality_education",
    "neighborhood_amenities",
    "economic_security",
    "climate_risk",
    "active_outdoors",
    "natural_beauty",
    "diversity",
    "social_fabric",
    "built_beauty",
    "healthcare_access",
    "public_transit_access",
    "air_travel_access",
    "housing_value",
]


def catalog_key(cat: Dict[str, Any]) -> str:
    return f"{cat.get('name', '')}|{cat.get('county_borough', '')}|{cat.get('state_abbr', '')}"


def classify_pillar(
    pillar_name: str,
    pillar: Any,
    *,
    treat_schools_disabled_as_ok: bool,
) -> Optional[str]:
    if pillar is None:
        return "missing_pillar_object"
    if not isinstance(pillar, dict):
        return "invalid_pillar_shape"
    if pillar.get("error"):
        return "pillar_error"
    if str(pillar.get("status") or "").lower() == "failed":
        return "pillar_status_failed"
    dq = pillar.get("data_quality") or {}
    if not isinstance(dq, dict):
        dq = {}
    reason = str(dq.get("reason") or "").lower()
    if treat_schools_disabled_as_ok and pillar_name == "quality_education":
        if "disabled" in reason or "school" in reason:
            return None
    if dq.get("fallback_used") is True and (pillar.get("confidence") is None or pillar.get("confidence") in (0, 0.0)):
        return "low_confidence_fallback"
    if pillar.get("score") is None:
        return "missing_score"
    return None


def apply_schools_disabled_weights(alloc: Dict[str, float]) -> Dict[str, float]:
    out = dict(alloc)
    out["quality_education"] = 0.0
    remaining = sum(float(v or 0.0) for k, v in out.items() if k != "quality_education")
    if remaining <= 0:
        return out
    scale = 100.0 / remaining
    for k in list(out.keys()):
        if k == "quality_education":
            continue
        out[k] = float(out.get(k, 0.0) or 0.0) * scale
    return out


def default_equal_allocation() -> Dict[str, float]:
    eq = 100.0 / len(PILLAR_ORDER)
    return {k: eq for k in PILLAR_ORDER}


def recompute_totals(score: Dict[str, Any]) -> None:
    pillars = score.get("livability_pillars")
    if not isinstance(pillars, dict):
        return
    alloc = apply_schools_disabled_weights(default_equal_allocation())
    score["token_allocation"] = alloc
    score["allocation_type"] = "equal_default_schools_off"
    total = 0.0
    for k in PILLAR_ORDER:
        p = pillars.get(k)
        if not isinstance(p, dict):
            continue
        s = float(p.get("score") or 0.0)
        w = float(alloc.get(k, 0.0) or 0.0)
        p["weight"] = w
        p["contribution"] = round(s * w / 100.0, 2)
        total += s * w / 100.0
        pillars[k] = p
    score["total_score"] = round(total, 2)


def load_last_per_place(path: Path) -> Dict[str, Dict[str, Any]]:
    last: Dict[str, Dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            cat = obj.get("catalog")
            if isinstance(cat, dict):
                last[catalog_key(cat)] = obj
    return last


def proxy_headers() -> Dict[str, str]:
    secret = os.environ.get("HOMEFIT_PROXY_SECRET", "").strip()
    if not secret:
        return {}
    return {"X-HomeFit-Proxy-Secret": secret}


def get_score(
    session: requests.Session,
    base_url: str,
    *,
    location: str,
    only: Optional[List[str]],
    timeout: int,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "location": location,
        "enable_schools": "false",
    }
    if only:
        params["only"] = ",".join(only)
    if lat is not None and lon is not None:
        params["lat"] = str(lat)
        params["lon"] = str(lon)
    url = f"{base_url.rstrip('/')}/score"
    r = session.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def failed_pillars_for_place(
    obj: Dict[str, Any],
    *,
    treat_schools: bool,
) -> Tuple[bool, List[str]]:
    if not obj.get("success"):
        return True, []
    score = obj.get("score")
    if not isinstance(score, dict):
        return True, []
    pillars = score.get("livability_pillars")
    if not isinstance(pillars, dict):
        return True, []

    bad: List[str] = []
    for pname in PILLAR_ORDER:
        issue = classify_pillar(pname, pillars.get(pname), treat_schools_disabled_as_ok=treat_schools)
        if issue is not None:
            bad.append(pname)
    return False, bad


def main() -> int:
    ap = argparse.ArgumentParser(description="Retry failed pillars from catalog batch JSONL.")
    ap.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "data" / "nyc_metro_place_catalog_scores.jsonl",
        help="Source JSONL from batch_score_place_catalog.py",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl",
        help="Merged JSONL output path",
    )
    ap.add_argument(
        "--base-url",
        default=os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"),
        help="HomeFit API base URL",
    )
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between HTTP calls.")
    ap.add_argument("--timeout", type=int, default=900, help="Per-request timeout seconds.")
    ap.add_argument(
        "--max-places",
        type=int,
        default=0,
        help="If set, only process this many places that need work (testing).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be retried without calling API.",
    )
    ap.add_argument(
        "--no-treat-schools-disabled-as-ok",
        action="store_true",
        help="Treat quality_education issues as failures even when schools are off.",
    )
    args = ap.parse_args()

    treat_schools = not args.no_treat_schools_disabled_as_ok
    inp = args.input
    if not inp.is_file():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    last = load_last_per_place(inp)
    session = requests.Session()
    session.headers.update(proxy_headers())

    work: List[Tuple[str, Dict[str, Any], bool, List[str]]] = []
    for key, obj in sorted(last.items(), key=lambda kv: kv[0]):
        full, bad = failed_pillars_for_place(obj, treat_schools=treat_schools)
        if full or bad:
            work.append((key, obj, full, bad))

    if args.max_places > 0:
        work = work[: args.max_places]

    print(f"Places in JSONL (last wins): {len(last)}")
    print(f"Places needing retry: {len(work)}")

    if args.dry_run:
        for key, obj, full, bad in work[:40]:
            cat = obj.get("catalog") or {}
            label = cat.get("name", key)
            if full:
                print(f"  FULL  {label!r}")
            else:
                print(f"  ONLY  {label!r} -> {','.join(bad)}")
        if len(work) > 40:
            print(f"  ... {len(work) - 40} more")
        return 0

    out_merged: Dict[str, Dict[str, Any]] = {}

    for key, obj, full, bad in work:
        cat = obj.get("catalog") or {}
        location = (cat.get("search_query") or "").strip()
        if not location:
            merged = copy.deepcopy(obj)
            merged.setdefault("merge_note", "skipped_no_search_query")
            out_merged[key] = merged
            continue

        label = cat.get("name", key)
        try:
            if full:
                print(f"[full] {label} …", flush=True)
                new_score = get_score(session, args.base_url, location=location, only=None, timeout=args.timeout)
            else:
                print(f"[only {len(bad)}] {label} …", flush=True)
                new_score = get_score(session, args.base_url, location=location, only=bad, timeout=args.timeout)

            merged = copy.deepcopy(obj)
            if not merged.get("success"):
                merged["success"] = True
                merged.pop("error", None)

            old = (merged.get("score") or {}) if isinstance(merged.get("score"), dict) else {}
            new_pillars = new_score.get("livability_pillars") or {}
            if not isinstance(old.get("livability_pillars"), dict):
                old["livability_pillars"] = {}
            lp = copy.deepcopy(old["livability_pillars"])

            if isinstance(new_pillars, dict):
                if full:
                    lp = new_pillars
                else:
                    for k in bad:
                        if k in new_pillars:
                            lp[k] = new_pillars[k]

            old["livability_pillars"] = lp
            for fld in ("input", "coordinates", "location_info"):
                if fld in new_score and new_score[fld]:
                    old[fld] = new_score[fld]
            merged["score"] = old
            recompute_totals(merged["score"])
            merged["merge_note"] = "rerun_failed_pillars_v1"
            out_merged[key] = merged
        except Exception as e:
            print(f"FAIL {label}: {e}", flush=True)
            fail = copy.deepcopy(obj)
            fail["success"] = False
            fail["error"] = f"rerun_failed_catalog_pillars: {e}"
            out_merged[key] = fail

        if args.delay > 0:
            time.sleep(args.delay)

    out_lines: List[str] = []
    for key, obj in sorted(last.items(), key=lambda kv: kv[0]):
        if key in out_merged:
            out_lines.append(json.dumps(out_merged[key], ensure_ascii=False))
        else:
            out_lines.append(json.dumps(obj, ensure_ascii=False))

    out_path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for line in out_lines:
            f.write(line + "\n")

    n_ok = sum(
        1
        for k in out_merged
        if out_merged[k].get("merge_note") == "rerun_failed_pillars_v1"
    )
    print(f"Wrote {len(out_lines)} lines to {out_path} ({n_ok} places successfully merged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
