"""
Shared helpers: Status Signal baselines for percentage metrics must stay in [0, 100]
so compute_education / compute_occupation min-max normalization is valid.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple

# When stored min/max are not valid percents, replace with defensible US-scale ranges.
_PCT_DEFAULTS: Dict[str, Tuple[float, float]] = {
    "grad_pct": (0.0, 45.0),
    "bach_pct": (3.0, 75.0),
    "self_employed_pct": (0.0, 100.0),
    "white_collar_pct": (0.0, 100.0),
    "finance_arts_pct": (0.0, 100.0),
}

# Metro keys: education min/max are metro-relative (narrower than national "all").
_METRO_EDUCATION_OVERRIDES: Dict[str, Dict[str, Dict[str, float]]] = {
    "nyc_metro": {
        "grad_pct": {"min": 0.0, "max": 50.0},
        "bach_pct": {"min": 3.0, "max": 80.0},
        "self_employed_pct": {"min": 0.0, "max": 100.0},
    },
    "la_metro": {
        "grad_pct": {"min": 0.0, "max": 48.0},
        "bach_pct": {"min": 3.0, "max": 78.0},
        "self_employed_pct": {"min": 0.0, "max": 100.0},
    },
}


def is_valid_pct_minmax(mn: Any, mx: Any) -> bool:
    if mn is None or mx is None:
        return False
    try:
        a, b = float(mn), float(mx)
    except (TypeError, ValueError):
        return False
    if a < 0.0 or b > 100.0 or a > 100.0 or a > b:
        return False
    return True


def coerce_pct_metric(metric: str, mn: float, mx: float) -> Optional[Dict[str, float]]:
    """If min/max are valid 0-100 percentiles, return them; else replace with defaults (and log)."""
    if is_valid_pct_minmax(mn, mx):
        return {"min": float(mn), "max": float(mx)}
    if metric in _PCT_DEFAULTS:
        a, b = _PCT_DEFAULTS[metric]
        print(
            f"  [baseline_pct] replaced corrupt {metric!r} min={mn!r} max={mx!r} -> min={a} max={b}"
        )
        return {"min": a, "max": b}
    print(f"  [baseline_pct] dropped unknown PCT metric {metric!r} min={mn!r} max={mx!r}")
    return None


def _sanitize_education_occupation_block(block: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(block, dict):
        return out
    for metric, d in block.items():
        if not (isinstance(d, dict) and "min" in d and "max" in d):
            continue
        if not str(metric).endswith("_pct"):
            continue
        fixed = coerce_pct_metric(str(metric), d["min"], d["max"])
        if fixed is not None:
            out[metric] = fixed
    return out


def sanitize_baseline_entry(comps: Dict[str, Any], region_key: str) -> Dict[str, Any]:
    """Return a copy of one region's baseline dict with education/occupation PCT min/max coerced."""
    c = deepcopy(comps) if isinstance(comps, dict) else {}
    if "education" in c:
        c["education"] = _sanitize_education_occupation_block(c.get("education"))
    if "occupation" in c:
        c["occupation"] = _sanitize_education_occupation_block(c.get("occupation"))
    return c


def apply_metro_education_overrides(baselines: Dict[str, Any]) -> None:
    """
    Set nyc_metro / la_metro education to metro-relative PCT ranges when missing
    (no block or not all three PCT series). Does not replace data-driven CBSA
    baselines that were emitted from build_status_signal_baselines_from_results.
    """
    required = ("grad_pct", "bach_pct", "self_employed_pct")
    for metro, edu in _METRO_EDUCATION_OVERRIDES.items():
        if metro not in baselines:
            continue
        if not isinstance(baselines[metro], dict):
            baselines[metro] = {}
        cur = baselines[metro].get("education")
        if isinstance(cur, dict) and all(k in cur for k in required):
            continue
        baselines[metro]["education"] = deepcopy(edu)
        print(
            f"  [baseline_pct] set {metro!r} education to metro override "
            f"(was missing or incomplete)"
        )


def sanitize_full_baselines_file(
    data: Dict[str, Any], *, apply_metro_overrides: bool = True
) -> Dict[str, Any]:
    """Return a new dict with all regions sanitized; cbsa_to_baseline is left as-is (mapping only)."""
    out: Dict[str, Any] = {}
    for k, v in data.items():
        if k == "cbsa_to_baseline":
            out[k] = deepcopy(v)
            continue
        if not isinstance(v, dict):
            out[k] = v
            continue
        out[k] = sanitize_baseline_entry(v, k)
    if apply_metro_overrides:
        apply_metro_education_overrides(out)
    return out


def validate_pct_for_build(metric: str, mn: float, mx: float) -> bool:
    """
    If False, do not write this metric to baselines (build_status_signal_baselines_from_results).
    Log expected before calling; caller logs skip.
    """
    return is_valid_pct_minmax(mn, mx)


def default_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "status_signal_baselines.json",
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Coerce *._pct min/max in status_signal_baselines.json to [0, 100].")
    ap.add_argument("--input", default=default_path(), help="Path to status_signal_baselines.json")
    ap.add_argument(
        "--output",
        default=None,
        help="Default: overwrite --input",
    )
    ap.add_argument(
        "--no-metro-override",
        action="store_true",
        help="Do not set nyc_metro / la_metro education to fixed metro ranges",
    )
    args = ap.parse_args()
    outp = args.output or args.input
    with open(args.input, "r", encoding="utf-8") as f:
        raw = json.load(f)
    fixed = sanitize_full_baselines_file(raw, apply_metro_overrides=not args.no_metro_override)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(fixed, f, indent=2, sort_keys=True)
    print(f"Wrote {outp}")
