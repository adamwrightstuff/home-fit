"""Make every row's pillar weights sum to 100 and rebuild its totals from the stored pillar scores (offline, no API).

Why: ``recompute_totals`` (used by retries) re-weighted only the pillars in PILLAR_ORDER and left natural_beauty's old weight on
top, so retried rows had weights summing to 108-111 and totals about 5-8 points too high, next to untouched rows at 100.

Rule (the one the well-formed rows already follow): equal weight over 13 pillars (the 12 in PILLAR_ORDER plus natural_beauty);
quality_education counts only when it has a real score (status success), otherwise it is out and the rest share its weight; a
counted pillar without a score is a data gap (weight kept, contribution 0, total scaled up) exactly as before.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import diagnose as dg

REPO = Path(__file__).resolve().parents[2]
BASE = ["quality_education", "neighborhood_amenities", "economic_opportunity", "climate_risk", "active_outdoors", "diversity",
        "social_fabric", "healthcare_access", "public_transit_access", "air_travel_access", "housing_value", "community_safety",
        "natural_beauty"]


def _education_counts(p: Dict[str, Any]) -> bool:
    return isinstance(p, dict) and p.get("status") == "success" and isinstance(p.get("score"), (int, float))


def weights_for(pillars: Dict[str, Any]) -> Dict[str, float]:
    active = [k for k in BASE if k in pillars and (k != "quality_education" or _education_counts(pillars[k]))]
    w = 100.0 / len(active) if active else 0.0
    return {k: (w if k in active else 0.0) for k in BASE if k in pillars}


def row_weight_sum(row: Dict[str, Any]) -> float:
    return sum((v.get("weight") or 0) for v in ((row.get("score") or {}).get("livability_pillars") or {}).values()
               if isinstance(v, dict))


def reweight_row(row: Dict[str, Any], recompute: Optional[Callable] = None) -> Dict[str, Any]:
    row = copy.deepcopy(row)
    s = row["score"]
    P = s["livability_pillars"]
    alloc = weights_for(P)
    for k, p in P.items():
        if not isinstance(p, dict):
            continue
        w = alloc.get(k, 0.0)
        p["weight"] = w
        sc = p.get("score")
        p["contribution"] = round(float(sc) * w / 100.0, 4) if isinstance(sc, (int, float)) else 0.0
    s["token_allocation"] = alloc
    s["allocation_type"] = ("equal_13_schools_on" if alloc.get("quality_education") else "equal_12_schools_off")
    if recompute is None:
        sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "catalog"))
        import data_sources.census_api as _c
        _c.get_census_tract = lambda *a, **k: None  # type: ignore[assignment]  # no live lookups: keep status_signal stable
        from pillars.composite_indices import recompute_composites_from_payload
        from recompute_catalog_composites import _merge_composites_into_score
        _merge_composites_into_score(s, recompute_composites_from_payload(s))
    else:
        recompute(s)
    return row


def plan(rows: List[Dict[str, Any]]) -> List[int]:
    """Indexes of rows whose weights do not sum to 100 (within 1)."""
    return [i for i, r in enumerate(rows) if r.get("success") and abs(row_weight_sum(r) - 100.0) > 1.0]


def run(path: Path, dry_run: bool = False, all_rows: bool = False, log: Callable[[str], None] = print) -> int:
    from . import resolve as rs
    rows = dg.load_rows(path)
    idx = list(range(len(rows))) if all_rows else plan(rows)
    moves = []
    for i in idx:
        if not rows[i].get("success"):
            continue
        new = reweight_row(rows[i])
        a, b = rows[i]["score"].get("total_score"), new["score"].get("total_score")
        moves.append((rows[i]["catalog"].get("name"), a, b, row_weight_sum(rows[i])))
        if not dry_run:
            rows[i] = new
    for name, a, b, ws in sorted(moves, key=lambda m: -abs((m[2] or 0) - (m[1] or 0)))[:10]:
        log(f"  {name}: total {a} -> {b}  (weights summed to {ws:.0f})")
    if moves and not dry_run:
        rs._write_atomic(path, rows)
    log(f"{len(moves)} rows {'would be ' if dry_run else ''}reweighted")
    return len(moves)
