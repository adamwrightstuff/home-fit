#!/usr/bin/env python3
"""
Pass/fail check for the quality_education pillar in a metro catalog. Offline, no API calls.

A metro passes when there are no FAILURES. Warnings are listed but do not fail. Known, accepted
gaps live in data/education_check_exceptions.json as {"<metro>:<place>": "reason"} and are
reported as exceptions instead of failures.

Failures (per place):
  no_score         scoring row has no usable education score and is not an accepted exception
  no_school_list   scored, but breakdown.rated_schools is missing (cannot be audited or split)
  weight_zero      has a usable score but weight 0 while its other default pillars are weighted
  no_split         rated_schools present but breakdown.split is missing
  formula_mismatch score (or split) does not equal the formula applied to rated_schools
  thin_big_district  fewer than 3 rated schools although its Census district has 6+ schools
                     (a radius limit, not a real shortage). Needs the Census + NCES files;
                     without them this downgrades to the warning thin_unverified.
  mostly_outside_district  half or more of the matched stored schools are in other districts

Warnings: thin_small_district (fewer than 3 rated but the district itself is small, so real),
thin_unverified, some_outside_district (>= 25% of matched schools elsewhere; name collisions
make this noisy), no_charter_data.

  PYTHONPATH=. python3 scripts/catalog/check_education.py            # all six metros
  PYTHONPATH=. python3 scripts/catalog/check_education.py --metro la
Exit code 1 when any metro fails.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

METROS = ("nyc", "la", "sf", "seattle", "austin", "chicago")
EXCEPTIONS_PATH = REPO / "data" / "education_check_exceptions.json"
NCES_CSV = REPO / "data_cache" / "nces_ccd_2324" / "ccd_sch_029_2324_w_1a_073124.csv"
MIN_RATED = 3
BIG_DISTRICT_SCHOOLS = 6
STATE_ABBR = {
    "New York": "NY", "New Jersey": "NJ", "Connecticut": "CT", "California": "CA",
    "Washington": "WA", "Texas": "TX", "Illinois": "IL", "Indiana": "IN",
}

_nces_cache: Dict[str, Any] = {}


def _norm(s: str) -> str:
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\bthe\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _nces():
    """(name index {(st, norm name): [(leaid, charter)]}, regular school count per LEA) or None."""
    if "v" in _nces_cache:
        return _nces_cache["v"]
    if not NCES_CSV.is_file():
        _nces_cache["v"] = None
        return None
    try:
        import pandas as pd
        df = pd.read_csv(NCES_CSV, dtype=str, low_memory=False,
                         usecols=["ST", "SCH_NAME", "LEAID", "CHARTER_TEXT", "SY_STATUS", "SCH_TYPE", "LEVEL"])
    except Exception:
        _nces_cache["v"] = None
        return None
    idx: Dict[tuple, list] = collections.defaultdict(list)
    for st, nm, lea, ch in zip(df.ST, df.SCH_NAME, df.LEAID, df.CHARTER_TEXT):
        idx[(st, _norm(str(nm)))].append((lea, ch == "Yes"))
    reg = df[(df.SY_STATUS == "1") & (df.SCH_TYPE == "1") & (df.LEVEL.isin(["Elementary", "Middle", "High"]))]
    counts = reg.groupby("LEAID").size().to_dict()
    _nces_cache["v"] = (idx, counts)
    return _nces_cache["v"]


def _districts(lat: float, lon: float, st: str) -> List[Dict[str, str]]:
    try:
        from data_sources.school_districts import districts_for_point
        return districts_for_point(lat, lon, st)
    except Exception:
        return []


def load_exceptions() -> Dict[str, str]:
    try:
        return json.loads(EXCEPTIONS_PATH.read_text())
    except Exception:
        return {}


def evaluate(rows: List[Dict[str, Any]], metro: str = "", exceptions: Optional[Dict[str, str]] = None,
             use_district_checks: bool = True) -> Dict[str, Any]:
    """Run the checks on catalog rows ({'catalog': {...}, 'score': {...}, 'success': bool})."""
    from pillars.schools import headline_from_levels, score_from_ratings, split_scores

    exceptions = load_exceptions() if exceptions is None else exceptions
    nces = _nces() if use_district_checks else None
    failures: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    excepted: List[Dict[str, str]] = []
    stats = collections.Counter()

    def add(kind: str, place: str, detail: str, hard: bool) -> None:
        key = f"{metro}:{place}"
        item = {"check": kind, "place": place, "detail": detail}
        if hard and key in exceptions:
            excepted.append({**item, "reason": exceptions[key]})
        else:
            (failures if hard else warnings).append(item)

    for row in rows:
        cat = row.get("catalog") or {}
        place = cat.get("name") or cat.get("search_query") or "?"
        stats["places"] += 1
        if not row.get("success"):
            add("no_score", place, "scoring row failed", True)
            continue
        sc = row.get("score") or {}
        lp = sc.get("livability_pillars") or {}
        p = lp.get("quality_education") or {}
        b = p.get("breakdown") or {}
        score = p.get("score")
        usable = bool(score) and (p.get("confidence") or 0) >= 1
        if not usable:
            add("no_score", place, "no usable education score", True)
            continue
        stats["scored"] += 1
        rs = b.get("rated_schools")
        if not rs:
            add("no_school_list", place, "rated_schools missing", True)
            continue

        others = [v for k, v in lp.items() if k != "quality_education" and isinstance(v, dict)]
        if (p.get("weight") or 0) <= 0 and any((v.get("weight") or 0) > 0 for v in others):
            add("weight_zero", place, "usable score but weight 0 (not in the total)", True)

        early = float(b.get("early_ed_bonus") or 0)
        zoned_model = b.get("model") == "zoned_v1"
        if zoned_model:
            derived = headline_from_levels(b.get("levels") or {}, early)
        else:
            derived = score_from_ratings([float(s["rating"]) for s in rs], early)["score"]
        if derived is None or abs(derived - float(score)) > 0.05:
            add("formula_mismatch", place, f"stored {score} vs {derived} from its schools", True)

        split = b.get("split")
        if not split:
            add("no_split", place, "breakdown.split missing", True)
        elif not zoned_model and split != split_scores(rs, early):
            add("formula_mismatch", place, "split does not match rated_schools", True)

        if zoned_model:
            levels = b.get("levels") or {}
            missing = [lv for lv, v in levels.items() if v.get("score") is None]
            nearest = [lv for lv, v in levels.items() if v.get("source") == "nearest"]
            stale = [lv for lv, v in levels.items() if v.get("source") == "zone" and v.get("zone")]
            if len(levels) and len(missing) == len(levels):
                add("no_levels_scored", place, "no level has a rated school", True)
            elif len(missing) >= 2:
                add("thin_levels", place, f"only {len(levels) - len(missing)} of 3 levels have a rated school", True)
            for lv in nearest:
                if len(levels[lv]["schools"]) < 3:
                    add("thin_level_set", place, f"{lv}: {len(levels[lv]['schools'])} rated schools within 3 mi", False)
            for lv in stale:
                z = levels[lv]["zone"]
                if (z.get("vintage") or "")[:4] < "2024":
                    add("old_zone_map", place, f"{lv} zone map {z.get('vintage')}", False)
            continue

        n = len(rs)
        # district checks need Census polygons + the NCES directory
        st = STATE_ABBR.get((sc.get("location_info") or {}).get("state", ""), "") or \
            str(cat.get("search_query", "")).split(",")[-1].strip()[:2].upper()
        ds: List[Dict[str, str]] = []
        try:
            ds = _districts(float(cat["lat"]), float(cat["lon"]), st) if (nces and use_district_checks) else []
        except (KeyError, TypeError, ValueError):
            ds = []
        nyc_doe = any("New York City Department" in d["name"] for d in ds)

        if n < MIN_RATED:
            if ds and not nyc_doe:
                avail = sum(nces[1].get(d["id"], 0) for d in ds)
                if avail >= BIG_DISTRICT_SCHOOLS:
                    add("thin_big_district", place, f"{n} rated of {avail} schools in its district", True)
                else:
                    add("thin_small_district", place, f"{n} rated; district has {avail} schools", False)
            elif nyc_doe:
                add("thin_small_district", place, f"{n} rated (NYC community district)", False)
            else:
                add("thin_unverified", place, f"{n} rated; district size unknown (no Census/NCES files)", False)

        if ds and nces and not nyc_doe:
            ids = {d["id"] for d in ds}
            inn = outn = 0
            for s in rs:
                cands = nces[0].get((st, _norm(s["name"])), [])
                if not cands:
                    continue
                if any(lea in ids or ch for lea, ch in cands):
                    inn += 1
                else:
                    outn += 1
            if inn + outn >= MIN_RATED and outn >= 0.5 * (inn + outn):
                add("mostly_outside_district", place, f"{outn} of {inn + outn} matched schools in other districts", True)
            elif outn >= 0.25 * max(1, inn + outn) and outn > 0:
                add("some_outside_district", place, f"{outn} of {inn + outn} matched schools in other districts", False)

    return {
        "metro": metro,
        "verdict": "PASS" if not failures else "FAIL",
        "places": stats["places"],
        "scored": stats["scored"],
        "failures": failures,
        "warnings": warnings,
        "exceptions": excepted,
        "district_checks": bool(nces),
    }


def format_report(rep: Dict[str, Any], limit: int = 8) -> str:
    lines = [f"EDUCATION CHECK  {rep['verdict']}  {rep['metro']}: {rep['scored']}/{rep['places']} places scored, "
             f"{len(rep['failures'])} failures, {len(rep['warnings'])} warnings, {len(rep['exceptions'])} accepted exceptions"
             + ("" if rep["district_checks"] else "  (district checks skipped: Census/NCES files missing)")]
    for title, items in (("FAIL", rep["failures"]), ("warn", rep["warnings"]), ("exception", rep["exceptions"])):
        by: Dict[str, list] = collections.defaultdict(list)
        for it in items:
            by[it["check"]].append(it)
        for check, its in sorted(by.items()):
            names = ", ".join(i["place"] for i in its[:limit]) + (f", +{len(its) - limit} more" if len(its) > limit else "")
            lines.append(f"  {title:<9} {check:<24} {len(its):>3}  {names}")
    return "\n".join(lines)


def run_file(path: Path, metro: str) -> Dict[str, Any]:
    last: Dict[str, Dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            o = json.loads(line)
            c = o.get("catalog") or {}
            last[f"{c.get('name')}|{c.get('county_borough')}|{c.get('state_abbr')}"] = o
    return evaluate(list(last.values()), metro)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pass/fail education check")
    ap.add_argument("--metro", choices=METROS, action="append", help="default: all six")
    args = ap.parse_args()
    bad = 0
    for m in args.metro or METROS:
        rep = run_file(REPO / "data" / f"{m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl", m)
        print(format_report(rep))
        bad += rep["verdict"] == "FAIL"
    print(f"\n{'FAIL' if bad else 'PASS'}: {bad} of {len(args.metro or METROS)} metros fail the education check")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
