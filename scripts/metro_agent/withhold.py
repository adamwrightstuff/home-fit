"""Withhold: show a pillar as unknown instead of publishing a score built on a failed lookup.

When an upstream (Overpass) stays down, a few places keep pillar scores that rest on partial data (a healthcare score
from one distant hospital, an outdoors score with a failed query). Publishing those misleads; leaving the whole metro
unpublished hides 100+ fixed places. Withholding blanks only the unreliable pillars (score None, like places with no
crime data), keeps them on the rescore list, and `resolve` fills them in once the upstream recovers.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import diagnose as dg

MARKER = "withheld_pending_rescore"


def _withheld_pillar(old: Dict[str, Any], reason: str) -> Dict[str, Any]:
    keep = {k: old[k] for k in ("weight", "importance_level") if k in old}
    return {**keep, "score": None, "status": "withheld", "summary": {}, "breakdown": {},
            "confidence": 0, "contribution": 0,
            "data_quality": {"degraded": True, "confidence": 0, "data_warnings": [MARKER],
                             "degraded_reasons": [reason]}}


def plan(rows: List[Dict[str, Any]], accepted: Optional[dict] = None) -> List[Tuple[int, str, str]]:
    """(row index, pillar, reason) for every unresolved lookup failure (a retry would fix it)."""
    labels = dg.place_labels(rows)
    index = {l: i for i, l in enumerate(labels)}
    out = []
    for f in dg.diagnose(rows, accepted=accepted)["findings"]:
        if f["remedy"] in (dg.RETRY, dg.VERIFY) and f["material"] and f["pillar"] != "(place)" \
                and f["cause"] in (dg.UPSTREAM_ERROR, dg.SUSPECTED_UPSTREAM):
            out.append((index[f["place"]], f["pillar"], f["evidence"]))
    return out


def withhold(path: Path, dry_run: bool = False, log: Callable[[str], None] = print,
             recompute: Optional[Callable[[Path], None]] = None) -> int:
    from . import resolve as rs
    rows = dg.load_rows(path)
    items = plan(rows, dg.load_accepted(path))
    for i, pillar, why in items:
        name = (rows[i].get("catalog") or {}).get("name")
        log(f"  {'would withhold' if dry_run else 'withholding'} {name} / {pillar}: {why[:90]}")
    if dry_run or not items:
        return len(items)
    for i, pillar, why in items:
        lp = rows[i]["score"]["livability_pillars"]
        lp[pillar] = _withheld_pillar(copy.deepcopy(lp.get(pillar) or {}), why[:120])
    rs._write_atomic(path, rows)
    (recompute or rs._default_recompute)(path)
    return len(items)
