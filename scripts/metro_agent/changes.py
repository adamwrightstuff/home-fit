"""What changed in a catalog file since the last commit (or any git ref): catches a script that moved scores it shouldn't.

    PYTHONPATH=. python -m scripts.metro_agent diff --metro nyc
Reports places changed, per-pillar change counts, and the biggest moves in the composite fields. A status_signal move with
no matching input change is the signature of a live Census lookup during recompute; revert with `git checkout -- <file>`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
COMPOSITES = ("status_signal", "happiness_index", "longevity_index", "total_score")


def _key(r: Dict[str, Any]) -> Tuple:
    c = r.get("catalog") or {}
    return (c.get("name"), c.get("county_borough"), c.get("state_abbr"))


def _load_lines(text: str) -> Dict[Tuple, Dict[str, Any]]:
    out = {}
    for line in text.splitlines():
        if line.strip():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            out[_key(r)] = r
    return out


def compare(old: Dict[Tuple, Dict[str, Any]], new: Dict[Tuple, Dict[str, Any]], threshold: float = 3.0) -> Dict[str, Any]:
    pillar_changes: Dict[str, int] = {}
    big: List[Tuple[float, str, str, Any, Any]] = []
    changed_places = 0
    for k, n in new.items():
        o = old.get(k)
        if o is None:
            continue
        osc, nsc = o.get("score") or {}, n.get("score") or {}
        changed = False
        for p, nv in (nsc.get("livability_pillars") or {}).items():
            ov = (osc.get("livability_pillars") or {}).get(p) or {}
            if ov.get("score") != (nv or {}).get("score"):
                pillar_changes[p] = pillar_changes.get(p, 0) + 1
                changed = True
        for f in COMPOSITES:
            a, b = osc.get(f), nsc.get(f)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) >= threshold:
                big.append((abs(b - a), k[0], f, a, b))
                changed = True
        changed_places += changed
    big.sort(reverse=True)
    return {"places_changed": changed_places, "added": len(set(new) - set(old)), "removed": len(set(old) - set(new)),
            "pillar_changes": dict(sorted(pillar_changes.items(), key=lambda x: -x[1])), "big_moves": big}


def diff_against(path: Path, ref: str = "HEAD", threshold: float = 3.0) -> Dict[str, Any]:
    rel = str(path.resolve().relative_to(REPO))
    old_text = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=REPO, capture_output=True, text=True).stdout
    return compare(_load_lines(old_text), _load_lines(path.read_text(encoding="utf-8")), threshold)


def format_report(name: str, r: Dict[str, Any], limit: int = 15) -> str:
    lines = [f"{name}: {r['places_changed']} places changed, {r['added']} added, {r['removed']} removed"]
    if r["pillar_changes"]:
        lines.append("  pillar scores changed: " + ", ".join(f"{p} {n}" for p, n in r["pillar_changes"].items()))
    for d, place, field, a, b in r["big_moves"][:limit]:
        lines.append(f"  {field:<16} {place}: {a} -> {b}  ({b - a:+.1f})")
    if len(r["big_moves"]) > limit:
        lines.append(f"  … and {len(r['big_moves']) - limit} more large moves")
    return "\n".join(lines)
