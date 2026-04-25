"""Paired wealth baselines: mean_hh_income p5/p95, wealth_gap p5/p95, fixed national 'all' band."""
from __future__ import annotations

import math
from typing import Dict, List, Optional

# Pooled "all" key: ~US-tract p5 / p95 so premium suburbs hit W≈100 against national band
ALL_KEY_MEAN_HH_INCOME_MIN = 28_000.0
ALL_KEY_MEAN_HH_INCOME_MAX = 175_000.0
# Do not write baselines with mean_hh_income max at or above this (likely bad data)
MEAN_HH_INCOME_MAX_SANE = 750_000.0


def linear_percentile(values: List[float], p: float) -> float:
    """p in [0, 100], linear interpolation between order statistics."""
    if not values:
        raise ValueError("empty values")
    s = sorted(float(x) for x in values)
    n = len(s)
    if n == 1:
        return float(s[0])
    if p <= 0:
        return float(s[0])
    if p >= 100:
        return float(s[-1])
    k = (n - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    hi = min(hi, n - 1)
    w = k - lo
    return float(s[lo] * (1 - w) + s[hi] * w)


def _mean_hh_income_p5_p95(values: List[float], *, log_label: str) -> Optional[Dict[str, float]]:
    mn = linear_percentile(values, 5.0)
    mx = linear_percentile(values, 95.0)
    if mn > mx:
        mn, mx = mx, mn
    if mx >= MEAN_HH_INCOME_MAX_SANE:
        print(
            f"  [skip] {log_label} mean_hh_income: p95 {mx:,.0f} >= "
            f"${MEAN_HH_INCOME_MAX_SANE:,.0f} (census/anomaly; not written)"
        )
        return None
    if mn < 0:
        return None
    return {"min": float(mn), "max": float(mx)}


def build_paired_wealth_minmax(
    mean_list: Optional[List[float]],
    gap_list: Optional[List[float]],
    min_samples: int,
    *,
    all_key_income: bool,
    log_label: str,
) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Paired wealth: emit mean_hh_income + wealth_gap_ratio together, or return None.
    Per-region: p5/p95 of samples. "all" key: fixed 28k/175k for mean. Gap: always p5/p95.
    """
    if not gap_list or len(gap_list) < min_samples:
        return None
    if not mean_list or len(mean_list) < min_samples:
        return None
    g5 = linear_percentile(gap_list, 5.0)
    g95 = linear_percentile(gap_list, 95.0)
    if g5 == 0.0 and g95 == 0.0:
        return None
    if all_key_income:
        income: Dict[str, float] = {
            "min": ALL_KEY_MEAN_HH_INCOME_MIN,
            "max": ALL_KEY_MEAN_HH_INCOME_MAX,
        }
    else:
        got = _mean_hh_income_p5_p95(mean_list, log_label=log_label)
        if got is None:
            return None
        income = got
    if float(income["max"]) >= MEAN_HH_INCOME_MAX_SANE:
        return None
    return {
        "mean_hh_income": income,
        "wealth_gap_ratio": {"min": float(g5), "max": float(g95)},
    }
