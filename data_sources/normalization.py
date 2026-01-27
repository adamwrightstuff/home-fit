"""
Normalization helpers for converting raw area-level metrics to 0–100 scores.

For economic_security, we normalize within (census_division × area_bucket) using
precomputed mean/std stored in `data/economic_baselines.json`, then convert z-scores
to percentiles (Normal CDF) and map to 0–100.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


BASELINES_PATH = Path("data/economic_baselines.json")


@lru_cache(maxsize=1)
def load_economic_baselines() -> Dict[str, Any]:
    if not BASELINES_PATH.exists():
        return {}
    try:
        return json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _normal_cdf(z: float) -> float:
    """
    Standard normal CDF Φ(z) using erf (good enough for scoring).
    """
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _zscore_to_0_100(value: float, *, mean: float, std: float) -> float:
    """
    Convert a raw value to 0–100 using z-score → percentile (Normal CDF).
    """
    if std <= 1e-12:
        return 50.0
    z = (value - mean) / std
    p = _normal_cdf(z)
    return max(0.0, min(100.0, 100.0 * p))


def normalize_metric_to_0_100(
    *,
    metric: str,
    value: Optional[float],
    division: str,
    area_bucket: str,
    invert: bool = False,
) -> Optional[float]:
    """
    Normalize a raw metric value into a 0–100 score using precomputed baselines.

    Falls back in this order:
    - division+area_bucket+metric
    - division+\"all\"+metric
    - \"all\"+area_bucket+metric
    - \"all\"+\"all\"+metric
    """
    if value is None:
        return None

    baselines = load_economic_baselines()
    if not isinstance(baselines, dict):
        return None

    def _get(division_key: str, area_key: str) -> Optional[Dict[str, Any]]:
        block = baselines.get(division_key, {})
        if not isinstance(block, dict):
            return None
        area_block = block.get(area_key, {})
        if not isinstance(area_block, dict):
            return None
        metric_block = area_block.get(metric)
        return metric_block if isinstance(metric_block, dict) else None

    stats = (
        _get(division, area_bucket)
        or _get(division, "all")
        or _get("all", area_bucket)
        or _get("all", "all")
    )

    if not stats:
        return None

    # New format: mean/std
    mean = stats.get("mean")
    std = stats.get("std")
    if isinstance(mean, (int, float)) and isinstance(std, (int, float)):
        score = _zscore_to_0_100(float(value), mean=float(mean), std=float(std))
    else:
        # Backward compatibility: if a quantile file is still present, fall back.
        # (Not used in the spec-aligned model once baselines are regenerated.)
        p05 = stats.get("p05")
        p95 = stats.get("p95")
        p50 = stats.get("p50")
        if isinstance(p05, (int, float)) and isinstance(p95, (int, float)) and isinstance(p50, (int, float)):
            # Approximate mean/std from p05/p50/p95 if needed.
            approx_mean = float(p50)
            approx_std = max(1e-6, (float(p95) - float(p05)) / 3.289707)  # ~ (p95-p05)/(2*1.64485)
            score = _zscore_to_0_100(float(value), mean=approx_mean, std=approx_std)
        else:
            return None
    if invert:
        score = 100.0 - score
    return max(0.0, min(100.0, score))

