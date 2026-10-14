"""Resolvers: act on `diagnose` findings instead of just reporting them.

Per cause:
  RETRY_PILLAR        re-run only that pillar for only the affected places, keep the better result
  RETRY_THEN_VERIFY   re-run ONCE; if still empty it is handed to a human, never retried blindly
  NEEDS_DATA_SOURCE   never retried (it cannot work); listed with exactly what is needed

Guards
  * systemic failure (one pillar failing for 40%+ of places): confirm the dependency (Overpass)
    is healthy before spending any calls; abort if it is not
  * a retry replaces a result only if it is not worse (fewer or equal material findings)
  * stop on: nothing actionable, max rounds, a round with no improvement, dependency down
  * the file is rewritten atomically after every place, so an interrupted run loses nothing
  * scoring logic is never changed here; that stays a human decision
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from . import diagnose as dg
from . import preflight as pf

REPO = Path(__file__).resolve().parents[2]


def _default_scorer(session, base_url: str, location: str, pillars: List[str],
                    lat: Optional[float], lon: Optional[float], timeout: int) -> Dict[str, Any]:
    sys.path.insert(0, str(REPO))
    from scripts.catalog.rescore_catalog_pillar import get_score
    return get_score(session, base_url, location=location, only=pillars, timeout=timeout,
                     lat=lat, lon=lon, enable_schools="quality_education" in pillars)


def _default_merge(existing: Dict[str, Any], new_score: Dict[str, Any], pillars: List[str]) -> Dict[str, Any]:
    sys.path.insert(0, str(REPO))
    from scripts.catalog.rescore_catalog_pillar import merge_pillar_response
    return merge_pillar_response(existing, new_score, pillars)


def _default_recompute(path: Path) -> None:
    subprocess.run([sys.executable, str(REPO / "scripts" / "catalog" / "recompute_catalog_composites.py"),
                    "--input", str(path), "--output", str(path),
                    # Live Census lookups at a single pin are tract-boundary-sensitive and move status_signal by up to
                    # ~9 pts with no data change; a pillar retry must not touch it.
                    "--no-census"],
                   env={**os.environ, "PYTHONPATH": str(REPO)}, check=True)


def _default_dependency_check(rows: List[Dict[str, Any]]) -> Optional[str]:
    """Return an error string if Overpass is unhealthy, else None."""
    coords = next(((float(r["catalog"]["lat"]), float(r["catalog"]["lon"])) for r in rows if r.get("catalog")), None)
    if coords is None:
        return None
    checks = pf.check_overpass(*coords)
    bad = [c for c in checks if c.status == pf.FAIL]
    return "; ".join(f"{c.detail} -> {c.fix}" for c in bad) if bad else None


def _default_lean_refresh(path: Path) -> None:
    """Political lean reads local precinct files (no API); rerun it so a changed radius or precinct file takes effect."""
    subprocess.run([sys.executable, str(REPO / "scripts" / "catalog" / "rescore_political_lean.py"),
                    "--input", str(path), "--in-place", "--no-backup"],
                   env={**os.environ, "PYTHONPATH": str(REPO)}, check=True)


def _write_atomic(path: Path, rows: List[Dict[str, Any]]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _badness(row: Dict[str, Any], pillars: Set[str]) -> int:
    """Lower is better. Material findings weigh 10x minor ones; severity counts failed parts."""
    return sum(f.severity * (10 if f.material else 1) for f in dg.classify_place(row) if f.pillar in pillars)


def resolve(
    path: Path,
    base_url: str,
    *,
    max_rounds: int = 3,
    delay: float = 2.0,
    timeout: int = 300,
    include_minor: bool = False,
    dry_run: bool = False,
    session: Any = None,
    scorer: Callable = _default_scorer,
    merge: Callable = _default_merge,
    recompute: Optional[Callable[[Path], None]] = _default_recompute,
    dependency_check: Callable = _default_dependency_check,
    lean_refresh: Optional[Callable[[Path], None]] = _default_lean_refresh,
    log: Callable[[str], None] = print,
) -> Dict[str, Any]:
    if session is None and not dry_run:
        import requests
        session = requests.Session()
        session.headers.update({"X-HomeFit-Proxy-Secret": os.environ.get("HOMEFIT_PROXY_SECRET", "")})

    valid_pillars: Optional[Set[str]] = None
    try:
        sys.path.insert(0, str(REPO))
        from scripts.catalog.rescore_catalog_pillar import PILLAR_ORDER
        valid_pillars = set(PILLAR_ORDER)
    except Exception:
        pass

    attempts: Dict[Tuple[str, str], int] = defaultdict(int)  # (place, pillar) -> retries made
    changed = False
    stop = "max_rounds"
    rounds_run = 0
    api_calls = 0

    if lean_refresh is not None and not dry_run:
        first = dg.diagnose(dg.load_rows(path), accepted=dg.load_accepted(path))
        if any(f["pillar"] == "political_lean" and f["remedy"] != dg.NONE for f in first["findings"]):
            log("political lean: refreshing from the local precinct files…")
            try:
                lean_refresh(path)
                changed = True
            except Exception as e:  # noqa: BLE001
                log(f"political lean refresh failed: {str(e)[:100]}")

    for rnd in range(1, max_rounds + 1):
        rows = dg.load_rows(path)
        result = dg.diagnose(rows, accepted=dg.load_accepted(path))

        todo: Dict[str, Set[str]] = defaultdict(set)
        for f in result["findings"]:
            # Crime has data-file fixes (data/crime_agency_map.json): a missing agency mapping can be added without
            # code, so give community_safety one retry per run even though it is a "needs data source" finding.
            retry_source = f["remedy"] == dg.SOURCE and f["pillar"] == "community_safety"
            if (f["remedy"] not in (dg.RETRY, dg.VERIFY) and not retry_source) or not (f["material"] or include_minor):
                continue
            if f["pillar"] == "(place)" or (valid_pillars is not None and f["pillar"] not in valid_pillars):
                continue
            limit = 1 if f["remedy"] in (dg.VERIFY, dg.SOURCE) else max_rounds
            if attempts[(f["place"], f["pillar"])] >= limit:
                continue
            todo[f["place"]].add(f["pillar"])

        if not todo:
            stop = "nothing_actionable"
            break

        # Most pillars query Overpass. If it is down, every retry just waits out timeouts (minutes per place) and
        # fails, so check once per round whenever any retry depends on it, not only for systemic failures.
        overpass_pillars = {"active_outdoors", "neighborhood_amenities", "healthcare_access", "natural_beauty",
                            "built_environment", "social_fabric", "public_transit_access"}
        if result["systemic"] or any(overpass_pillars & ps for ps in todo.values()):
            problem = dependency_check(rows)
            if problem:
                stop = "dependency_down"
                log(f"STOP: the data source these retries need is down, so retrying would only wait out timeouts: {problem}")
                break

        n_places = len(todo)
        log(f"\n--- round {rnd}/{max_rounds}: {n_places} places, "
            f"{sum(len(v) for v in todo.values())} pillar retries ---")
        if dry_run:
            for place, ps in sorted(todo.items()):
                log(f"  would retry {place}: {', '.join(sorted(ps))}")
            stop = "dry_run"
            rounds_run = rnd
            break

        index = {label: i for i, label in enumerate(dg.place_labels(rows))}
        improved = 0
        for n, (place, pillars) in enumerate(sorted(todo.items()), 1):
            i = index[place]
            row = rows[i]
            cat = row["catalog"]
            plist = sorted(pillars)
            try:
                new_score = scorer(session, base_url, (cat.get("search_query") or "").strip(), plist,
                                   float(cat["lat"]), float(cat["lon"]), timeout)
                api_calls += 1
                candidate = merge(copy.deepcopy(row), new_score, plist)
            except Exception as e:  # noqa: BLE001 - leave the row alone, try again next round
                log(f"  [{n}/{n_places}] {place}: ERROR {str(e)[:100]}")
                for p in plist:
                    attempts[(place, p)] += 1
                time.sleep(delay) if delay else None
                continue
            for p in plist:
                attempts[(place, p)] += 1
            before, after = _badness(row, set(plist)), _badness(candidate, set(plist))
            if after <= before:
                rows[i] = candidate
                _write_atomic(path, rows)
                changed = True
                tag = "fixed" if after < before else "unchanged"
                if after < before:
                    improved += 1
            else:
                tag = "worse, kept old"
            log(f"  [{n}/{n_places}] {place}: {', '.join(plist)} -> {tag}")
            if delay and n < n_places:
                time.sleep(delay)
        rounds_run = rnd
        log(f"round {rnd}: {improved} places improved")
        if improved == 0:
            stop = "no_progress"
            break

    if changed and recompute is not None and not dry_run:
        log("\nrecomputing composites…")
        recompute(path)

    final = dg.diagnose(dg.load_rows(path), accepted=dg.load_accepted(path))
    left = defaultdict(list)
    for f in final["findings"]:
        if f["material"]:
            left[f["remedy"]].append(f)
    summary = {
        "stopped": stop,
        "rounds": rounds_run,
        "api_calls": api_calls,
        "material_places_left": len(final["material_places"]),
        "needs_data_source": [dict(place=f["place"], pillar=f["pillar"], need=f["evidence"]) for f in left.get(dg.SOURCE, [])],
        "needs_human_check": [dict(place=f["place"], pillar=f["pillar"], evidence=f["evidence"]) for f in left.get(dg.VERIFY, [])],
        "still_failing_after_retries": [dict(place=f["place"], pillar=f["pillar"], evidence=f["evidence"]) for f in left.get(dg.RETRY, [])],
    }
    return summary


def format_summary(s: Dict[str, Any]) -> str:
    lines = ["", "RESOLUTION SUMMARY", "=" * 70,
             f"stopped: {s['stopped']} after {s['rounds']} round(s), {s['api_calls']} pillar calls",
             f"places still with a material gap: {s['material_places_left']}"]
    for key, title in (("needs_data_source", "NEEDS A DATA SOURCE (retrying cannot fix)"),
                       ("needs_human_check", "NEEDS A HUMAN CHECK (retried once; may genuinely have none)"),
                       ("still_failing_after_retries", "STILL FAILING AFTER RETRIES")):
        if s[key]:
            lines += ["", f"{title}: {len(s[key])}"]
            lines += [f"  {x['place']} / {x['pillar']}: {x.get('need') or x.get('evidence')}" for x in s[key][:25]]
            if len(s[key]) > 25:
                lines.append(f"  … {len(s[key]) - 25} more")
    lines += ["", "PUBLISH: " + ("OK, no material gaps" if not s["material_places_left"]
                                else "BLOCKED until the items above are resolved or consciously accepted")]
    return "\n".join(lines)
