#!/usr/bin/env python3
"""
Summarize pillar-level health across a batch JSONL file (e.g. from batch_score_place_catalog.py).

Reads one JSON object per line with optional keys: success, error, catalog, score.

Writes:
  - *_summary.csv   — counts by issue type (and optional pillar)
  - *_locations.csv — one row per catalog place (last row wins if duplicates)
  - *_details.csv   — long format: pillar × place with issue codes

Usage:

  python3 scripts/report_catalog_pillar_health.py \\
    --jsonl data/nyc_metro_place_catalog_scores.jsonl

  python3 scripts/report_catalog_pillar_health.py \\
    --jsonl data/chicago_metro_catalog_scores.jsonl \\
    --outdir data/metros/chicago_health
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSONL = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores.jsonl"

# Match frontend/lib/pillars.ts PILLAR_ORDER for display consistency.
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


def catalog_label(cat: Dict[str, Any]) -> str:
    return ", ".join(
        str(x)
        for x in (cat.get("name"), cat.get("county_borough"), cat.get("state_abbr"))
        if x
    )


def classify_pillar(
    pillar_name: str,
    pillar: Any,
    *,
    treat_schools_disabled_as_ok: bool,
) -> Optional[str]:
    """
    Return None if we treat this pillar as OK for reporting.
    Otherwise return a short issue code.
    """
    if pillar is None:
        return "missing_pillar_object"

    if not isinstance(pillar, dict):
        return "invalid_pillar_shape"

    err = pillar.get("error")
    if err:
        return "pillar_error"

    status = str(pillar.get("status") or "").lower()
    if status == "failed":
        return "pillar_status_failed"

    dq = pillar.get("data_quality") or {}
    if not isinstance(dq, dict):
        dq = {}

    reason = str(dq.get("reason") or "").lower()
    if treat_schools_disabled_as_ok and pillar_name == "quality_education":
        if "disabled" in reason or "school" in reason:
            return None

    fb = dq.get("fallback_used") is True
    conf = pillar.get("confidence")
    if fb and (conf is None or conf == 0 or conf == 0.0):
        return "low_confidence_fallback"

    sc = pillar.get("score")
    if sc is None:
        return "missing_score"

    return None


def load_last_row_per_place(path: Path) -> Tuple[Dict[str, Dict[str, Any]], int]:
    """Return mapping catalog_key -> last JSON object per key, and total line count."""
    last: Dict[str, Dict[str, Any]] = {}
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            cat = obj.get("catalog")
            if not isinstance(cat, dict):
                continue
            last[catalog_key(cat)] = obj
    return last, n


def main() -> int:
    ap = argparse.ArgumentParser(description="Report pillar health from catalog batch JSONL.")
    ap.add_argument(
        "--jsonl",
        type=Path,
        default=DEFAULT_JSONL,
        help=f"Input JSONL (default: {DEFAULT_JSONL})",
    )
    ap.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Directory for CSV outputs. Default: <jsonl.parent>/<jsonl.stem>_health/",
    )
    ap.add_argument(
        "--no-treat-schools-disabled-as-ok",
        action="store_true",
        help="Flag quality_education even when disabled by policy (schools off).",
    )
    args = ap.parse_args()
    jsonl_path = args.jsonl
    if not jsonl_path.is_file():
        print(f"File not found: {jsonl_path}", file=sys.stderr)
        return 1

    outdir = args.outdir
    if outdir is None:
        outdir = jsonl_path.parent / f"{jsonl_path.stem}_health"
    outdir.mkdir(parents=True, exist_ok=True)

    treat_schools = not args.no_treat_schools_disabled_as_ok

    last_by_place, line_count = load_last_row_per_place(jsonl_path)

    summary_counts: Counter = Counter()
    pillar_issue_counts: Counter = Counter()
    detail_rows: List[Dict[str, Any]] = []
    location_rows: List[Dict[str, Any]] = []

    healthy_places = 0
    places_with_issues = 0

    for place_key in sorted(last_by_place.keys()):
        obj = last_by_place[place_key]
        cat = obj.get("catalog") or {}
        if not isinstance(cat, dict):
            cat = {}

        row_ok = bool(obj.get("success"))
        row_err = obj.get("error") if not row_ok else ""

        pillar_issues: List[str] = []
        if not row_ok:
            code = "whole_row_failed"
            summary_counts[code] += 1
            if row_err:
                summary_counts[f"{code}:{str(row_err)[:80]}"] += 1
            places_with_issues += 1
            location_rows.append(
                {
                    "place_key": place_key,
                    "label": catalog_label(cat),
                    "name": cat.get("name", ""),
                    "county_borough": cat.get("county_borough", ""),
                    "state_abbr": cat.get("state_abbr", ""),
                    "row_success": False,
                    "row_error": row_err,
                    "pillar_issue_count": "",
                    "pillars_flagged": "",
                }
            )
            continue

        score = obj.get("score") or {}
        if not isinstance(score, dict):
            summary_counts["invalid_score_object"] += 1
            places_with_issues += 1
            location_rows.append(
                {
                    "place_key": place_key,
                    "label": catalog_label(cat),
                    "name": cat.get("name", ""),
                    "county_borough": cat.get("county_borough", ""),
                    "state_abbr": cat.get("state_abbr", ""),
                    "row_success": True,
                    "row_error": "invalid score object in JSONL",
                    "pillar_issue_count": "",
                    "pillars_flagged": "",
                }
            )
            continue

        pillars = score.get("livability_pillars") or {}
        if not isinstance(pillars, dict):
            summary_counts["invalid_livability_pillars"] += 1
            places_with_issues += 1
            location_rows.append(
                {
                    "place_key": place_key,
                    "label": catalog_label(cat),
                    "name": cat.get("name", ""),
                    "county_borough": cat.get("county_borough", ""),
                    "state_abbr": cat.get("state_abbr", ""),
                    "row_success": True,
                    "row_error": "invalid livability_pillars in score",
                    "pillar_issue_count": "",
                    "pillars_flagged": "",
                }
            )
            continue

        for pname in PILLAR_ORDER:
            issue = classify_pillar(
                pname,
                pillars.get(pname),
                treat_schools_disabled_as_ok=treat_schools,
            )
            if issue is None:
                continue

            detail_rows.append(
                {
                    "place_key": place_key,
                    "label": catalog_label(cat),
                    "name": cat.get("name", ""),
                    "county_borough": cat.get("county_borough", ""),
                    "state_abbr": cat.get("state_abbr", ""),
                    "pillar": pname,
                    "issue": issue,
                    "score": (pillars.get(pname) or {}).get("score") if isinstance(pillars.get(pname), dict) else "",
                    "pillar_error": (pillars.get(pname) or {}).get("error") if isinstance(pillars.get(pname), dict) else "",
                    "confidence": (pillars.get(pname) or {}).get("confidence") if isinstance(pillars.get(pname), dict) else "",
                    "fallback_used": (pillars.get(pname) or {}).get("data_quality", {}).get("fallback_used")
                    if isinstance(pillars.get(pname), dict)
                    else "",
                    "reason": (pillars.get(pname) or {}).get("data_quality", {}).get("reason")
                    if isinstance(pillars.get(pname), dict)
                    else "",
                }
            )
            summary_counts[issue] += 1
            pillar_issue_counts[f"{pname}:{issue}"] += 1
            pillar_issues.append(f"{pname}:{issue}")

        if pillar_issues:
            places_with_issues += 1
            location_rows.append(
                {
                    "place_key": place_key,
                    "label": catalog_label(cat),
                    "name": cat.get("name", ""),
                    "county_borough": cat.get("county_borough", ""),
                    "state_abbr": cat.get("state_abbr", ""),
                    "row_success": True,
                    "row_error": "",
                    "pillar_issue_count": len(pillar_issues),
                    "pillars_flagged": "; ".join(pillar_issues),
                }
            )
        else:
            healthy_places += 1
            location_rows.append(
                {
                    "place_key": place_key,
                    "label": catalog_label(cat),
                    "name": cat.get("name", ""),
                    "county_borough": cat.get("county_borough", ""),
                    "state_abbr": cat.get("state_abbr", ""),
                    "row_success": True,
                    "row_error": "",
                    "pillar_issue_count": 0,
                    "pillars_flagged": "",
                }
            )

    summary_path = outdir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["issue_type", "count"])
        for k, v in summary_counts.most_common():
            w.writerow([k, v])

    pillar_summary_path = outdir / "summary_by_pillar.csv"
    with pillar_summary_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pillar", "issue_type", "count"])
        for k, v in sorted(pillar_issue_counts.items(), key=lambda x: (-x[1], x[0])):
            pillar, issue = k.split(":", 1) if ":" in k else (k, "")
            w.writerow([pillar, issue, v])

    locations_path = outdir / "locations.csv"
    with locations_path.open("w", newline="", encoding="utf-8") as f:
        if location_rows:
            fieldnames = list(location_rows[0].keys())
            dw = csv.DictWriter(f, fieldnames=fieldnames)
            dw.writeheader()
            dw.writerows(location_rows)

    details_path = outdir / "pillar_details.csv"
    with details_path.open("w", newline="", encoding="utf-8") as f:
        if detail_rows:
            fieldnames = list(detail_rows[0].keys())
            dw = csv.DictWriter(f, fieldnames=fieldnames)
            dw.writeheader()
            dw.writerows(detail_rows)

    print(f"Input JSONL lines read: {line_count}")
    print(f"Unique catalog places (last row wins): {len(last_by_place)}")
    print(f"Places with no pillar issues: {healthy_places}")
    print(f"Places with issues: {places_with_issues}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {pillar_summary_path}")
    print(f"Wrote: {locations_path}")
    print(f"Wrote: {details_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
