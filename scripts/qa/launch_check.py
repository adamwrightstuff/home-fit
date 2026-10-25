#!/usr/bin/env python3
"""
Launch check (design principles v2, P10): do places that should differ actually differ?

Reads the stored catalog files (no network) and checks every scored pillar:
  1. Spread and clumping: FAIL if 25% or more of places sit at the pillar's maximum or minimum; WARN if the most common
     rounded score holds more than 15% of places or the standard deviation is below 5.
  2. Pre-registered contrasts from data/launch_check_contrasts.json (written by the owner BEFORE looking at results),
     plus an optional "expected_uniform" list of sub-metrics that are uniform within a metro by design.
  3. Coverage: no-data and degraded shares per pillar (reported), and degenerate metros: a sub-metric where 90% or more
     of a metro's places share one value while the rest of the catalog does not (WARN).
This is a tripwire for data or logic problems. A failure means investigate; never tune a parameter until a pillar passes.

  PYTHONPATH=. python3 scripts/qa/launch_check.py                       # all metros, writes analysis/launch_check_<date>.md
  PYTHONPATH=. python3 scripts/qa/launch_check.py --metro seattle       # one metro (gates need enough places to mean much)
  PYTHONPATH=. python3 scripts/qa/launch_check.py --out -               # print the report
Exit code 1 if any gate FAILs (also on WARN with --fail-on-warn), so metro_agent health and CI can call it.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pillar_registry import SCORED_PILLARS  # noqa: E402

# Gates (owner-approved defaults; change here or with the flags below).
EXTREME_FAIL_SHARE = 0.25     # share of places at the max or the min
MODAL_WARN_SHARE = 0.15       # share of places in the most common rounded score
SD_WARN_BELOW = 5.0
DEGENERATE_SHARE = 0.90       # share of a metro's places sharing one sub-metric value
DEGENERATE_MIN_PLACES = 10
CONTRAST_MIN_N = 10
DEFAULT_CATALOG_GLOB = str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")
DEFAULT_CONTRASTS = ROOT / "data" / "launch_check_contrasts.json"
AREA_TYPE_SOURCES = ("climate_risk", "diversity", "social_fabric", "economic_opportunity", "housing_value", "healthcare_access")


def _leaves(obj: Any, prefix: str = "", depth: int = 0) -> Iterable:
    """Numeric leaves of a nested dict as (dotted path, value); booleans, lists and strings are skipped."""
    if isinstance(obj, dict) and depth < 3:
        for k, v in obj.items():
            yield from _leaves(v, f"{prefix}.{k}" if prefix else str(k), depth + 1)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool) and math.isfinite(obj):
        yield prefix, float(obj)


def load_places(paths: List[str]) -> List[Dict[str, Any]]:
    places = []
    for path in paths:
        metro = os.path.basename(path).split("_metro")[0]
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                s = rec.get("score") or {}
                P = s.get("livability_pillars") or {}
                if not P:
                    continue
                cat = rec.get("catalog") if isinstance(rec.get("catalog"), dict) else {}
                area = next(((P.get(k) or {}).get("area_classification", {}).get("area_type") for k in AREA_TYPE_SOURCES
                             if (P.get(k) or {}).get("area_classification", {}).get("area_type")), None)
                pillars = {}
                for name in SCORED_PILLARS:
                    p = P.get(name)
                    if not isinstance(p, dict):
                        continue
                    sc = p.get("score")
                    dq = p.get("data_quality") or {}
                    pillars[name] = {
                        "score": float(sc) if isinstance(sc, (int, float)) and not isinstance(sc, bool) else None,
                        "status": p.get("status"),
                        "degraded": bool(dq.get("degraded")),
                        "leaves": dict(_leaves({"breakdown": p.get("breakdown"), "summary": p.get("summary")})),
                    }
                places.append({"metro": metro, "name": cat.get("name"), "state": cat.get("state_abbr"), "area_type": area, "pillars": pillars})
    return places


def _mean(x: List[float]) -> float:
    return sum(x) / len(x)


def _sd(x: List[float]) -> float:
    m = _mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


def pillar_stats(places: List[Dict[str, Any]], pillar: str) -> Optional[Dict[str, Any]]:
    scores = [(p["metro"], p["pillars"][pillar]["score"]) for p in places if pillar in p["pillars"]]
    vals = [v for _, v in scores if v is not None]
    total = len(scores)
    if not vals:
        return None
    mx, mn = max(vals), min(vals)
    rounded = collections.Counter(round(v) for v in vals)
    gm = _mean(vals)
    by_metro = collections.defaultdict(list)
    for m, v in scores:
        if v is not None:
            by_metro[m].append(v)
    between = sum(len(v) * (_mean(v) - gm) ** 2 for v in by_metro.values()) / len(vals)
    var = _sd(vals) ** 2
    nodata = sum(1 for p in places if pillar in p["pillars"] and p["pillars"][pillar]["score"] is None)
    degraded = sum(1 for p in places if pillar in p["pillars"] and p["pillars"][pillar]["degraded"])
    return {
        "n": len(vals), "places": total, "mean": gm, "sd": _sd(vals),
        "at_max": sum(v >= mx - 0.05 for v in vals) / len(vals), "at_min": sum(v <= mn + 0.05 for v in vals) / len(vals),
        "max": mx, "min": mn, "modal_share": rounded.most_common(1)[0][1] / len(vals), "modal_value": rounded.most_common(1)[0][0],
        "distinct": len(rounded), "between_metro": (between / var) if var > 0 else 0.0,
        "no_data": nodata / total if total else 0.0, "degraded": degraded / total if total else 0.0,
    }


def gate_stats(st: Dict[str, Any]) -> List[tuple]:
    """[(level, message)] for one pillar's stats; level is FAIL or WARN."""
    out = []
    if st["at_max"] >= EXTREME_FAIL_SHARE:
        out.append(("FAIL", f"{st['at_max']:.0%} of places are at the maximum ({st['max']:.1f})"))
    if st["at_min"] >= EXTREME_FAIL_SHARE:
        out.append(("FAIL", f"{st['at_min']:.0%} of places are at the minimum ({st['min']:.1f})"))
    if st["modal_share"] > MODAL_WARN_SHARE and not any(lvl == "FAIL" for lvl, _ in out):
        out.append(("WARN", f"{st['modal_share']:.0%} of places share the score {st['modal_value']}"))
    if st["sd"] < SD_WARN_BELOW:
        out.append(("WARN", f"standard deviation {st['sd']:.1f} is below {SD_WARN_BELOW:g}"))
    return out


def is_expected_uniform(item: Dict[str, Any], allowed: List[Dict[str, Any]]) -> bool:
    """True when the owner listed this pillar and sub-metric path (prefix match) as uniform by design."""
    for a in allowed:
        if a.get("pillar") == item["pillar"] and item["path"].startswith(a.get("path_prefix", "")):
            if not a.get("metros") or item["metro"] in a["metros"]:
                return True
    return False


def degenerate_metros(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sub-metrics where one metro's places share a single value while the rest of the catalog does not."""
    found = []
    for pillar in SCORED_PILLARS:
        by_metro = collections.defaultdict(lambda: collections.defaultdict(list))
        for p in places:
            for path, v in (p["pillars"].get(pillar) or {}).get("leaves", {}).items():
                by_metro[path][p["metro"]].append(v)
        for path, metros in by_metro.items():
            for metro, vals in metros.items():
                if len(vals) < DEGENERATE_MIN_PLACES:
                    continue
                value, count = collections.Counter(vals).most_common(1)[0]
                if count / len(vals) < DEGENERATE_SHARE:
                    continue
                rest = [v for m, vs in metros.items() if m != metro for v in vs]
                if len(rest) < DEGENERATE_MIN_PLACES or len(set(rest)) < 2:
                    continue
                if sum(1 for v in rest if v == value) / len(rest) >= 0.5:
                    continue  # the whole catalog does this; not specific to the metro
                found.append({"pillar": pillar, "path": path, "metro": metro, "value": value, "share": count / len(vals), "n": len(vals)})
    return found


def _select(places: List[Dict[str, Any]], sel: Dict[str, Any], pillar: str) -> List[float]:
    out = []
    names = set(sel.get("places") or [])
    for p in places:
        sc = (p["pillars"].get(pillar) or {}).get("score")
        if sc is None:
            continue
        if "area_type" in sel and p["area_type"] != sel["area_type"]:
            continue
        if "metro" in sel and p["metro"] != sel["metro"]:
            continue
        if "state" in sel and p["state"] != sel["state"]:
            continue
        if names and f"{p['metro']}|{p['name']}" not in names:
            continue
        out.append(sc)
    return out


def evaluate_contrasts(places: List[Dict[str, Any]], contrasts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for c in contrasts:
        a, b = _select(places, c.get("group_a") or {}, c["pillar"]), _select(places, c.get("group_b") or {}, c["pillar"])
        res = {"pillar": c["pillar"], "reason": c.get("reason", ""), "expected": c.get("expected"), "n_a": len(a), "n_b": len(b),
               "min_gap": float(c.get("min_gap", 0))}
        if len(a) < CONTRAST_MIN_N or len(b) < CONTRAST_MIN_N:
            res.update(level="WARN", gap=None, note=f"too few places (a={len(a)}, b={len(b)}; need {CONTRAST_MIN_N} each)")
        else:
            gap = _mean(a) - _mean(b)
            sign = 1 if c.get("expected") == "a_higher" else -1
            signed = gap * sign
            if signed >= res["min_gap"]:
                level, note = "PASS", ""
            elif signed > 0:
                level, note = "WARN", f"right direction but the gap is below the minimum {res['min_gap']:g}"
            else:
                level, note = "FAIL", "wrong direction"
            res.update(level=level, gap=gap, mean_a=_mean(a), mean_b=_mean(b), note=note)
        results.append(res)
    return results


def render(stats: Dict[str, Dict], gates: Dict[str, List[tuple]], contrast_results: List[Dict], degenerate: List[Dict], n_places: int, metros: List[str], suppressed: int = 0) -> str:
    L = [f"# Launch check, {date.today()}", "", f"{n_places} places, metros: {', '.join(sorted(metros))}.",
         "Gates: FAIL at 25% of places at the max or the min; WARN above 15% in one rounded score or sd below 5. "
         "A failure means investigate the data or logic, never tune a parameter until it passes.", "",
         "## 1. Spread and clumping", "",
         "| Pillar | n | mean | sd | at max | at min | top value | distinct | between-metro variance | no data | degraded | Result |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name in SCORED_PILLARS:
        st = stats.get(name)
        if not st:
            L.append(f"| {name} | 0 | | | | | | | | | | no scores |")
            continue
        g = gates[name]
        result = "FAIL" if any(l == "FAIL" for l, _ in g) else ("WARN" if g else "pass")
        L.append(f"| {name} | {st['n']} | {st['mean']:.1f} | {st['sd']:.1f} | {st['at_max']:.1%} | {st['at_min']:.1%} | {st['modal_share']:.1%} (at {st['modal_value']}) | "
                 f"{st['distinct']} | {st['between_metro']:.0%} | {st['no_data']:.1%} | {st['degraded']:.1%} | {result} |")
    issues = [(n, l, m) for n in SCORED_PILLARS for l, m in gates.get(n, [])]
    if issues:
        L += ["", "Findings:"] + [f"- {l}: {n}: {m}" for n, l, m in issues]
    L += ["", "## 2. Pre-registered contrasts", ""]
    if not contrast_results:
        L.append("None defined. Fill in data/launch_check_contrasts.json (before looking at results) and rerun.")
    else:
        L += ["| Pillar | Result | A mean | B mean | Gap | Expected | Min gap | n A / n B | Reason |", "|---|---|---|---|---|---|---|---|---|"]
        for r in contrast_results:
            L.append(f"| {r['pillar']} | {r['level']} | {r.get('mean_a', float('nan')):.1f} | {r.get('mean_b', float('nan')):.1f} | "
                     f"{(r['gap'] if r['gap'] is not None else float('nan')):+.1f} | {r['expected']} | {r['min_gap']:g} | {r['n_a']} / {r['n_b']} | {r['reason']} {r['note']} |")
    L += ["", "## 3. Degenerate metros (a sub-metric where 90% or more of a metro's places share one value while the rest of the catalog does not)", ""]
    if suppressed:
        L.append(f"{suppressed} metro-level findings are listed as uniform by design in data/launch_check_contrasts.json and are not shown.")
        L.append("")
    if not degenerate:
        L.append("None.")
    else:
        grouped = collections.defaultdict(list)
        for d in degenerate:
            grouped[(d["pillar"], d["path"])].append(d)
        L += ["| Pillar | Sub-metric | Metros (shared value, share of places) |", "|---|---|---|"]
        for (pillar, path), items in sorted(grouped.items()):
            cells = ", ".join(f"{d['metro']} ({d['value']:g}, {d['share']:.0%})" for d in sorted(items, key=lambda d: d["metro"]))
            L.append(f"| {pillar} | {path} | {cells} |")
    return "\n".join(L) + "\n"


def run(catalog_glob: str, contrasts_path: Path, metros: Optional[List[str]] = None):
    paths = sorted(glob.glob(catalog_glob))
    if metros:
        paths = [p for p in paths if os.path.basename(p).split("_metro")[0] in metros]
    places = load_places(paths)
    stats = {n: pillar_stats(places, n) for n in SCORED_PILLARS}
    gates = {n: (gate_stats(s) if s else []) for n, s in stats.items()}
    contrasts, allowed = [], []
    if contrasts_path and Path(contrasts_path).is_file():
        cfg = json.loads(Path(contrasts_path).read_text())
        contrasts, allowed = cfg.get("contrasts") or [], cfg.get("expected_uniform") or []
    results = evaluate_contrasts(places, contrasts)
    all_degenerate = degenerate_metros(places)
    degenerate = [d for d in all_degenerate if not is_expected_uniform(d, allowed)]
    suppressed = len(all_degenerate) - len(degenerate)
    fails = sum(1 for g in gates.values() for l, _ in g if l == "FAIL") + sum(1 for r in results if r["level"] == "FAIL")
    warns = sum(1 for g in gates.values() for l, _ in g if l == "WARN") + sum(1 for r in results if r["level"] == "WARN") + len({(d["pillar"], d["path"]) for d in degenerate})
    report = render(stats, gates, results, degenerate, len(places), sorted({p["metro"] for p in places}), suppressed)
    return report, fails, warns


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glob", default=DEFAULT_CATALOG_GLOB)
    ap.add_argument("--metro", action="append")
    ap.add_argument("--contrasts", default=str(DEFAULT_CONTRASTS))
    ap.add_argument("--out", default=str(ROOT / "analysis" / f"launch_check_{date.today()}.md"), help="report path, or - for stdout")
    ap.add_argument("--fail-on-warn", action="store_true")
    a = ap.parse_args()
    report, fails, warns = run(a.glob, Path(a.contrasts), a.metro)
    if a.out == "-":
        print(report)
    else:
        Path(a.out).write_text(report)
        print(f"wrote {a.out}")
    print(f"launch check: {fails} FAIL, {warns} WARN")
    return 1 if fails or (a.fail_on_warn and warns) else 0


if __name__ == "__main__":
    sys.exit(main())
