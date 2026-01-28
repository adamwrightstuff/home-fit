"""
Calibrated architectural beauty scoring (0–100).

This is a production-ready extraction of the calibration harness under `analysis/`.
It is intentionally lightweight and dependency-free so it can run inside the API path.

Design goals:
- Reward coherent historic fabric (including low-diversity rowhouse districts).
- Reward "cute/cozy" intentional uniformity (Carmel/Seaside).
- Penalize car-dominant / megaproject patterns (parking, wide streets, megablocks).
- Reduce the "diversity == good" bias with diminishing returns.

Inputs (existing model metrics):
- height_diversity: 0–100
- type_diversity: 0–100
- footprint_variation: 0–100
- built_coverage: 0–1

Optional proxy inputs (computed from existing pipeline where possible):
- ParkingFraction: 0–1
- BlockSize: meters (larger = worse)
- StreetWidthToHeight: ratio (larger = worse)
- FrontageContinuity: 0–100
- HistoricCoherence: 0–100
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _clamp01(x: float) -> float:
    return _clamp(x, 0.0, 1.0)


def _relu(x: float) -> float:
    return x if x > 0 else 0.0


def _gauss(x: float, mu: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    z = (x - mu) / sigma
    return math.exp(-(z * z))


def _sat01(x: float, cap: float) -> float:
    if cap <= 0:
        return 0.0
    return _clamp01(x / cap)


@dataclass(frozen=True)
class CalibratedWeights:
    base: float
    w_variety: float
    w_historic: float
    w_cozy: float
    p_parking: float
    p_megaproject: float
    p_strip: float
    p_sprawl: float
    p_extreme_foot: float
    softcap_k: float


# Default weights (fit against the enriched calibration set).
DEFAULT_WEIGHTS = CalibratedWeights(
    base=34.7411357283405,
    w_variety=31.088530924007067,
    w_historic=28.811659574812534,
    w_cozy=81.86515718499749,
    p_parking=20.969267448347715,
    p_megaproject=31.81532119073848,
    p_strip=58.66767938621183,
    p_sprawl=49.26322618795536,
    p_extreme_foot=19.821884527990665,
    softcap_k=1.466080745700029,
)


def compute_calibrated_architectural_beauty_score(
    row: Dict[str, Any],
    *,
    weights: CalibratedWeights = DEFAULT_WEIGHTS,
) -> float:
    """
    Compute calibrated architectural beauty score in 0–100.
    """
    height = float(row.get("height_diversity") or 0.0)
    typ = float(row.get("type_diversity") or 0.0)
    foot = float(row.get("footprint_variation") or 0.0)
    cov = float(row.get("built_coverage") or 0.0)

    # Normalize core metrics
    h = _clamp01(height / 100.0)
    t = _clamp01(typ / 100.0)
    f = _clamp01(foot / 100.0)
    c = _clamp01(cov)

    # Diminishing returns on diversity
    h_div = _sat01(min(h, 0.60), 0.60)
    t_div = _sat01(min(t, 0.55), 0.55)
    f_div = _sat01(min(f, 0.70), 0.70)
    variety = 0.45 * h_div + 0.40 * t_div + 0.15 * f_div

    # Coverage pleasant bands
    cov_mid = _gauss(c, mu=0.22, sigma=0.10)
    cov_spacious = _gauss(c, mu=0.14, sigma=0.07)
    coverage_pleasant = max(cov_mid, cov_spacious)

    # Historic fabric proxies
    rowhouse_hist = (
        _gauss(h, mu=0.14, sigma=0.14)
        * _gauss(t, mu=0.22, sigma=0.18)
        * _gauss(f, mu=0.88, sigma=0.14)
        * cov_mid
    )
    organic_hist = (
        _gauss(h, mu=0.50, sigma=0.22)
        * _gauss(t, mu=0.38, sigma=0.22)
        * _gauss(f, mu=0.90, sigma=0.12)
        * max(cov_mid, _gauss(c, mu=0.18, sigma=0.10))
    )
    spacious_hist = (
        _gauss(h, mu=0.22, sigma=0.22)
        * _gauss(t, mu=0.30, sigma=0.22)
        * _gauss(f, mu=0.92, sigma=0.10)
        * cov_spacious
    )
    mixed_use_hist = (
        _gauss(h, mu=0.70, sigma=0.22)
        * _gauss(t, mu=0.60, sigma=0.22)
        * _gauss(f, mu=0.78, sigma=0.20)
        * coverage_pleasant
    )
    village_mixed = (
        _gauss(h, mu=0.12, sigma=0.14)
        * _gauss(t, mu=0.55, sigma=0.22)
        * _gauss(f, mu=0.90, sigma=0.14)
        * max(_gauss(c, mu=0.18, sigma=0.08), cov_mid)
    )
    historic_fabric = max(rowhouse_hist, organic_hist, spacious_hist, mixed_use_hist, village_mixed)

    # Cozy charm proxy
    cozy_height = _gauss(h, mu=0.05, sigma=0.12)
    cozy_type = _gauss(t, mu=0.16, sigma=0.22)
    cozy_foot = _gauss(f, mu=0.32, sigma=0.28)
    cozy_cov = max(_gauss(c, mu=0.10, sigma=0.08), _gauss(c, mu=0.05, sigma=0.05))
    cozy_charm = cozy_height * cozy_type * cozy_foot * cozy_cov

    # Auto-oriented proxies
    parking_void_proxy = _relu((0.20 - c) / 0.20) * _relu((f - 0.70) / 0.30)
    megaproject_proxy = _relu((c - 0.26) / 0.22) * _relu((f - 0.82) / 0.18) * _relu((0.30 - t) / 0.30)
    strip_proxy = _relu((t - 0.35) / 0.65) * _relu((0.20 - c) / 0.20) * _relu((f - 0.55) / 0.45)
    lowrise_sprawl_proxy = _relu((0.14 - h) / 0.14) * _relu((t - 0.18) / 0.82) * _relu((c - 0.10) / 0.25)

    parking_frac_0_1: Optional[float] = None
    pf_in = row.get("ParkingFraction")
    if pf_in is not None:
        try:
            parking_frac_0_1 = _clamp01(float(pf_in))
            parking_void_proxy = max(parking_void_proxy, parking_frac_0_1)
        except (TypeError, ValueError):
            parking_frac_0_1 = None

    # Block size / street width / frontage proxies (optional)
    bs_in = row.get("BlockSize")
    if bs_in is not None:
        try:
            bs = float(bs_in)
            megaproject_proxy = max(megaproject_proxy, 0.75 * _clamp01((bs - 180.0) / 160.0))
        except (TypeError, ValueError):
            pass

    swh_in = row.get("StreetWidthToHeight")
    if swh_in is not None:
        try:
            swh = float(swh_in)
            parking_void_proxy = max(parking_void_proxy, 0.8 * _clamp01((swh - 1.6) / 1.4))
        except (TypeError, ValueError):
            pass

    fc_in = row.get("FrontageContinuity")
    if fc_in is not None:
        try:
            fc = _clamp01(float(fc_in) / 100.0)
            strip_proxy *= (1.0 + (1.0 - fc) * 0.6)
            historic_fabric = max(historic_fabric, 0.65 * fc * coverage_pleasant)
            cozy_charm *= (0.55 + 0.45 * fc)
        except (TypeError, ValueError):
            pass

    hc_in = row.get("HistoricCoherence")
    if hc_in is not None:
        try:
            hc = _clamp01(float(hc_in) / 100.0)
            historic_fabric = max(historic_fabric, hc)
        except (TypeError, ValueError):
            pass

    # Gate rewards by parking dominance when provided.
    if parking_frac_0_1 is not None:
        cozy_gate = 1.0 - _clamp01((parking_frac_0_1 - 0.18) / 0.35)
        historic_gate = 1.0 - _clamp01((parking_frac_0_1 - 0.25) / 0.45)
        cozy_charm *= (0.35 + 0.65 * cozy_gate)
        historic_fabric *= (0.55 + 0.45 * historic_gate)

    extreme_foot = _relu((f - 0.92) / 0.08) * _clamp01((0.30 - c) / 0.30)

    raw = (
        weights.base
        + weights.w_variety * variety
        + weights.w_historic * historic_fabric
        + weights.w_cozy * cozy_charm
        - weights.p_parking * parking_void_proxy
        - weights.p_megaproject * megaproject_proxy
        - weights.p_strip * strip_proxy
        - weights.p_sprawl * lowrise_sprawl_proxy
        - weights.p_extreme_foot * extreme_foot
    )

    # Soft cap to avoid trivial 100s.
    x = raw / 100.0
    capped = 100.0 * (math.tanh(weights.softcap_k * x) / math.tanh(weights.softcap_k))
    return float(_clamp(capped, 0.0, 100.0))

