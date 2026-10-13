"""Health agent: audit every launched metro the way the launch playbook does, and optionally fix what can be fixed.

For each metro it checks, from the stored catalog (no scoring API needed unless --fix):
  * the scores file exists and covers every place in the place list (no missing, no failed rows)
  * pins in the scores match the place list (a changed pin means the stored score is for the wrong spot)
  * the playbook prerequisites still hold (baseline, precinct file, crime source, frontend registration)
  * diagnose: every failed/empty/degraded pillar, by cause, with accepted gaps honoured
  * validate (unless --offline): stored values checked against Census and neighbouring places
Verdict per metro: HEALTHY, ATTENTION (non-blocking oddities) or UNHEALTHY (would be blocked at the publish gate).
--fix runs the resolver on metros whose problems are retryable, then re-audits.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import diagnose as dg
from . import preflight as pf
from . import validate as vd

REPO = pf.REPO
HEALTHY, ATTENTION, UNHEALTHY = "HEALTHY", "ATTENTION", "UNHEALTHY"


def known_metros() -> List[str]:
    import sys
    sys.path.insert(0, str(REPO))
    from scripts.baselines.build_metro_baselines_from_cbsa import CBSA_TO_KEY
    return sorted({k.removesuffix("_metro") for k in CBSA_TO_KEY.values()})


def paths(metro: str):
    return (REPO / "data" / f"{metro}_metro_place_catalog.csv",
            REPO / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl")


def _key(name, county, state):
    return (name, county, state)


def coverage(csv_rows: List[Dict[str, str]], score_rows: List[Dict[str, Any]], tol: float = 0.0005) -> Dict[str, List[str]]:
    want = {_key(r["name"], r["county_borough"], r["state_abbr"]): (float(r["lat"]), float(r["lon"])) for r in csv_rows}
    have: Dict[tuple, Dict[str, Any]] = {}
    for r in score_rows:
        c = r.get("catalog") or {}
        have[_key(c.get("name"), c.get("county_borough"), c.get("state_abbr"))] = r
    missing = sorted(k[0] for k in want if k not in have)
    extra = sorted(k[0] for k in have if k not in want)
    failed = sorted(k[0] for k, r in have.items() if not r.get("success"))
    moved = []
    for k, r in have.items():
        c = r.get("catalog") or {}
        try:
            la, lo = float(c["lat"]), float(c["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        w = want.get(k)
        if w and (abs(w[0] - la) > tol or abs(w[1] - lo) > tol):
            moved.append(k[0])
    return {"missing": missing, "extra": extra, "failed": failed, "pin_changed": sorted(moved)}


def audit(metro: str, offline: bool = False, validate_fn: Callable = vd.validate,
          static_checks: Optional[Callable] = None) -> Dict[str, Any]:
    csv_path, out_path = paths(metro)
    rep: Dict[str, Any] = {"metro": metro, "problems": [], "notes": [], "retryable": False}
    P = rep["problems"]
    if not csv_path.is_file():
        P.append(f"no place list at {csv_path.name}")
    if not out_path.is_file():
        P.append(f"no scores file {out_path.name}")
        rep["verdict"] = UNHEALTHY
        return rep
    rows = dg.load_rows(out_path)
    csv_rows = pf.read_csv(csv_path) if csv_path.is_file() else []
    rep["places"] = len(rows)

    cov = coverage(csv_rows, rows) if csv_rows else {"missing": [], "extra": [], "failed": [], "pin_changed": []}
    rep["coverage"] = cov
    if cov["missing"]:
        P.append(f"{len(cov['missing'])} places in the place list were never scored: {', '.join(cov['missing'][:6])}")
    if cov["failed"]:
        P.append(f"{len(cov['failed'])} places failed to score at all: {', '.join(cov['failed'][:6])}")
    if cov["pin_changed"]:
        P.append(f"{len(cov['pin_changed'])} places were scored at an old pin (rescore): {', '.join(cov['pin_changed'][:6])}")
    if cov["extra"]:
        rep["notes"].append(f"{len(cov['extra'])} scored places are not in the place list: {', '.join(cov['extra'][:6])}")

    checks = (static_checks or _static_checks)(metro, csv_rows)
    for c in checks:
        if c.status == pf.FAIL:
            P.append(f"{c.name}: {c.detail}")
        elif c.status == pf.WARN:
            rep["notes"].append(f"{c.name}: {c.detail}")

    accepted = dg.load_accepted(out_path)
    result = dg.diagnose(rows, accepted=accepted)
    rep["diagnosis"] = {"clean": result["clean"], "material_places": result["material_places"],
                        "counts": result["counts"], "systemic": result["systemic"]}
    material = [f for f in result["findings"] if f["material"]]
    by: Dict[str, List[str]] = {}
    for f in material:
        by.setdefault(f"{f['pillar']} ({f['cause']})", []).append(f["place"])
    for k, places in sorted(by.items()):
        P.append(f"{k}: {len(places)} places ({', '.join(places[:5])}{', ...' if len(places) > 5 else ''})")
    rep["retryable"] = any(f["remedy"] in (dg.RETRY, dg.VERIFY) for f in material)

    rep["validation"] = None
    if not offline:
        try:
            verdicts = validate_fn(rows)
            rep["validation"] = {k: [f"{v.place} / {v.pillar}: {v.evidence}" for v in verdicts if v.kind == k]
                                 for k in (vd.CONTRADICTED, vd.SUSPICIOUS, vd.INCONCLUSIVE, vd.CONSISTENT)}
            for line in rep["validation"][vd.CONTRADICTED]:
                P.append(f"contradicted by independent data: {line}")
            if rep["validation"][vd.SUSPICIOUS]:
                rep["notes"].append(f"{len(rep['validation'][vd.SUSPICIOUS])} values collapsed vs neighbours "
                                    f"(e.g. {rep['validation'][vd.SUSPICIOUS][0]})")
        except Exception as e:  # noqa: BLE001 - validation is best effort
            rep["notes"].append(f"validation skipped: {type(e).__name__}: {str(e)[:80]}")

    rep["verdict"] = UNHEALTHY if P else (ATTENTION if rep["notes"] else HEALTHY)
    return rep


def _static_checks(metro: str, csv_rows: List[Dict[str, str]]):
    out = [pf.check_baseline(metro)]
    if csv_rows:
        out += pf.check_precincts(csv_rows)
    out += [pf.check_crime_source(metro), *pf.check_registration(metro)]
    return out


def audit_all(metros: Optional[List[str]] = None, **kw) -> List[Dict[str, Any]]:
    return [audit(m, **kw) for m in (metros or known_metros())]


def format_report(reports: List[Dict[str, Any]]) -> str:
    lines = ["METRO HEALTH", "=" * 70]
    for r in reports:
        lines.append(f"{r['verdict']:<10} {r['metro']:<14} {r.get('places', '-'):>4} places")
    for r in reports:
        if r["verdict"] == HEALTHY:
            continue
        lines += ["", f"{r['metro'].upper()}  [{r['verdict']}]"]
        lines += [f"  PROBLEM  {p}" for p in r["problems"]]
        lines += [f"  note     {n}" for n in r["notes"]]
        if r["retryable"]:
            lines.append("  -> some of this is retryable: rerun with --fix")
    bad = [r["metro"] for r in reports if r["verdict"] == UNHEALTHY]
    lines += ["", f"{len(reports) - len(bad)} of {len(reports)} metros publishable"
              + (f"; blocked: {', '.join(bad)}" if bad else "")]
    return "\n".join(lines)


def fix(reports: List[Dict[str, Any]], api_base: str, log: Callable[[str], None] = print,
        resolve_fn: Optional[Callable] = None, rounds: int = 3) -> List[str]:
    from . import resolve as rs
    resolve_fn = resolve_fn or rs.resolve
    fixed = []
    for r in reports:
        if r["verdict"] == HEALTHY or not (r.get("retryable") or (r.get("coverage") or {}).get("failed")):
            continue
        _, out = paths(r["metro"])
        log(f"\n--- fixing {r['metro']} (resolve) ---")
        try:
            resolve_fn(out, api_base, max_rounds=rounds)
            fixed.append(r["metro"])
        except Exception as e:  # noqa: BLE001 - one metro failing must not stop the others
            log(f"!! {r['metro']}: fix stopped ({type(e).__name__}: {str(e)[:120]}). Its pillar fixes are saved but its "
                "composites were not recomputed; rerun after the cause (often a Census timeout) clears: "
                f"PYTHONPATH=. python scripts/catalog/recompute_catalog_composites.py --no-census --input {out} --output {out}")
            fixed.append(r["metro"])
    return fixed
