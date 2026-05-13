"""
Status Signal: Universal Logic Engine (status + desirability).

Data-driven principles (no location-specific tuning):
- Credential-First Education: 80% graduate/professional, 20% bachelors (no self-employed).
- Authority-First Occupation: S2401 Management/Business/Science/Arts concentration, CBSA-normalized.
- Multi-Modal Wealth: Elite Uniformity (median > 2x CBSA median, low gap) or Elite Outlier (median near CBSA, high gap).
- CBSA Mapping: Baselines selected by tract CBSA code only (Palo Alto vs San Jose, Bronxville vs NYC).

Baselines from data/status_signal_baselines.json; keys_to_try = CBSA key first (from cbsa_to_baseline), then division, then "all".
Luxury: dedicated OSM luxury Overpass (wealth offices, etc.) merged with deduped OSM+Places ``business_list``
(per-bucket max); brand fallback when both are empty and Overpass fails; no coordinates → brand fallback.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# High-barrier services for Status Signal luxury presence (brand fallback when merged list / OSM luxury unavailable).
# business_list comes from deduped OSM+Places neighborhood amenities; we use simple
# name-based matching here as a proxy for richer tagging:
# - Architectural firms (e.g. "Architects", "Architecture")
# - Art galleries ("Gallery", "Galleries")
# - Private marinas / yacht clubs ("Marina", "Yacht Club")
# - High-end wellness studios ("Pilates", "Reformer", "Barre")
STATUS_SIGNAL_BRAND_CONFIG = {
    "architect_firms": {
        "weight": 0.30,
        "brand_names": ["Architects", "Architecture", "Architectural"],
    },
    "art_galleries": {
        "weight": 0.30,
        "brand_names": ["Gallery", "Galleries", "Art Gallery"],
    },
    "private_marinas": {
        "weight": 0.20,
        "brand_names": ["Marina", "Yacht Club", "YachtClub"],
    },
    "high_end_wellness": {
        "weight": 0.20,
        "brand_names": ["Pilates", "Reformer", "Barre"],
    },
}

_BASELINES_CACHE: Optional[Dict[str, Any]] = None


def _load_baselines() -> Dict[str, Any]:
    global _BASELINES_CACHE
    if _BASELINES_CACHE is not None:
        return _BASELINES_CACHE
    path = os.getenv(
        "STATUS_SIGNAL_BASELINES_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "status_signal_baselines.json"),
    )
    if not path or not os.path.isfile(path):
        _BASELINES_CACHE = {}
        return _BASELINES_CACHE
    try:
        with open(path, "r", encoding="utf-8") as f:
            _BASELINES_CACHE = json.load(f)
    except Exception:
        _BASELINES_CACHE = {}
    return _BASELINES_CACHE


def _normalize_min_max(value: float, min_val: float, max_val: float) -> float:
    if max_val <= min_val:
        return 50.0
    x = (value - min_val) / (max_val - min_val)
    return max(0.0, min(100.0, x * 100.0))


def _get_baseline_key_from_cbsa(
    tract: Optional[Dict[str, Any]],
    baselines: Dict[str, Any],
    city: Optional[str],
    state_abbrev: Optional[str],
    division: str,
) -> Optional[str]:
    """
    CBSA mapping: select baselines using the tract's CBSA code only (universal logic, no location-name list).
    Ensures Palo Alto vs San Jose and Bronxville vs NYC use the same regional baseline.
    """
    cbsa_to_baseline = (baselines.get("cbsa_to_baseline") or {}) if isinstance(baselines.get("cbsa_to_baseline"), dict) else {}
    cbsa_code = (tract or {}).get("cbsa_code")
    if cbsa_code is not None and cbsa_to_baseline:
        key = cbsa_to_baseline.get(str(cbsa_code).strip())
        if key and key in baselines and key != "cbsa_to_baseline":
            return key
    return None


def _get_baseline(
    baselines: Dict[str, Any],
    keys_to_try: List[str],
    component: str,
    metric: str,
) -> Tuple[Optional[float], Optional[float]]:
    """Try each key in order; return (min, max) from the first key that has data for this component/metric."""
    for key in keys_to_try:
        div_data = baselines.get(key) or {}
        comp = div_data.get(component, {})
        m = comp.get(metric, {})
        if isinstance(m, dict) and "min" in m and "max" in m:
            return float(m["min"]), float(m["max"])
    return None, None


def _get_archetype_weights(archetype: str) -> Tuple[float, float, float, float]:
    """Weights (wealth, home_cost, education, occupation) for archetype. Sum = 1."""
    if archetype == "Established":
        return (0.45, 0.15, 0.20, 0.20)
    if archetype == "Professional":
        return (0.20, 0.15, 0.35, 0.30)
    if archetype == "Up-and-Coming":
        return (0.30, 0.45, 0.15, 0.10)
    if archetype == "Rooted":
        return (0.40, 0.20, 0.20, 0.20)
    return (W_WEALTH, W_HOME_COST, W_EDUCATION, W_OCCUPATION)


def _get_status_label(archetype: str) -> str:
    """UI badge label for archetype."""
    return {
        "Established": "Established",
        "Professional": "Professional",
        "Up-and-Coming": "Up-and-Coming",
        "Rooted": "Rooted",
        "Working Class": "Working Class",
        "Unclassified": "Unclassified",
    }.get(archetype, "Working Class")


def _signal_strength_band(score: float) -> Tuple[str, str]:
    """
    Map composite Status Signal (0-100) to a strength tier (clarity of the archetype-weighted blend).

    Bands: faint [0,25), moderate [25,50), strong [50,75), dominant [75,100].
    """
    s = float(score)
    if s < 25.0:
        return "faint", "Faint signal"
    if s < 50.0:
        return "moderate", "Moderate signal"
    if s < 75.0:
        return "strong", "Strong signal"
    return "dominant", "Dominant signal"


def _get_status_insight(archetype: str) -> str:
    """One-sentence tooltip 'why' for the UI."""
    return {
        "Established": "Legacy capital and long-rooted residents — wealth and community stability aligned.",
        "Professional": "Credential and career driven — high education and white-collar occupation with moderate asset wealth.",
        "Up-and-Coming": "Home values repricing ahead of resident wealth — a neighborhood actively transforming.",
        "Rooted": "Tight-knit, long-tenured community holding ground under housing cost pressure.",
        "Working Class": "Broadly stable community without dominant elite or credential-class signatures.",
        "Unclassified": "Insufficient residential data to classify — likely non-residential or data gap.",
    }.get(archetype, "Broadly stable community without dominant elite or credential-class signatures.")


_DRIVER_LABELS: Dict[str, str] = {
    "wealth": "Asset Stability",
    "home_cost": "Home Value",
    "education": "Education",
    "occupation": "Occupation Mix",
}

_DRIVER_LABELS_AFFLUENT: Dict[str, str] = {
    "wealth": "Income Velocity",
}


def _build_top_drivers(
    wealth: Optional[float],
    home_cost: float,
    education: Optional[float],
    occupation: Optional[float],
    archetype: str,
) -> List[Dict[str, Any]]:
    """Top 3 components by score for tooltip; labels vary by archetype."""
    labels = dict(_DRIVER_LABELS)
    if archetype in ("Established", "Professional", "Up-and-Coming"):
        labels.update(_DRIVER_LABELS_AFFLUENT)
    items: List[Tuple[str, float]] = []
    if wealth is not None:
        items.append(("wealth", round(wealth, 1)))
    items.append(("home_cost", round(home_cost, 1)))
    if education is not None:
        items.append(("education", round(education, 1)))
    if occupation is not None:
        items.append(("occupation", round(occupation, 1)))
    items.sort(key=lambda x: -x[1])
    out: List[Dict[str, Any]] = []
    for key, score in items[:3]:
        out.append({"label": labels.get(key, key), "score": score})
    return out


# Luxury OSM sub-weights (sum to 1). If specialist_healthcare count < 3, HC is excluded and 15% redistributed.
_LUX_W_WEALTH = 0.35
_LUX_W_PRIVATE = 0.25
_LUX_W_ARTS = 0.20
_LUX_W_HC = 0.15
_LUX_W_RETAIL = 0.05

_LUX_METRICS = {
    "wealth_offices": "wealth_offices_count",
    "private_recreation": "private_recreation_count",
    "arts_culture": "arts_culture_count",
    "specialist_healthcare": "specialist_healthcare_count",
    "luxury_retail": "luxury_retail_count",
}

_LUXURY_COUNT_KEYS = (
    "wealth_offices",
    "private_recreation",
    "arts_culture",
    "specialist_healthcare",
    "luxury_retail",
)

# When baselines lack luxury min/max, map raw counts to 0–100 without early saturation at low counts.
_LUXURY_COUNT_FALLBACK_SCALE = 50.0


def _luxury_count_to_score(
    count: int,
    baselines: Dict[str, Any],
    keys_to_try: List[str],
    metric: str,
) -> float:
    mn, mx = _get_baseline(baselines, keys_to_try, "luxury", metric)
    if mn is None or mx is None:
        c = float(max(0, count))
        if c <= 0:
            return 0.0
        return min(100.0, 100.0 * (1.0 - math.exp(-c / _LUXURY_COUNT_FALLBACK_SCALE)))
    return _normalize_min_max(float(max(0, count)), mn, mx)


def _luxury_score_detail_from_counts(
    counts: Dict[str, int],
    keys_to_try: List[str],
    baselines: Dict[str, Any],
    detail_head: Dict[str, Any],
) -> Tuple[float, Dict[str, Any]]:
    """Shared 0–100 luxury score from per-bucket integer counts (healthcare < 3 redistributes weights)."""
    detail = dict(detail_head)
    c = {k: int((counts or {}).get(k) or 0) for k in _LUXURY_COUNT_KEYS}
    detail["counts"] = dict(c)
    hc_n = int(c.get("specialist_healthcare") or 0)
    hc_active = hc_n >= 3

    s_wealth = _luxury_count_to_score(
        int(c.get("wealth_offices") or 0), baselines, keys_to_try, _LUX_METRICS["wealth_offices"]
    )
    s_priv = _luxury_count_to_score(
        int(c.get("private_recreation") or 0), baselines, keys_to_try, _LUX_METRICS["private_recreation"]
    )
    s_arts = _luxury_count_to_score(
        int(c.get("arts_culture") or 0), baselines, keys_to_try, _LUX_METRICS["arts_culture"]
    )
    s_hc = _luxury_count_to_score(hc_n, baselines, keys_to_try, _LUX_METRICS["specialist_healthcare"])
    s_ret = _luxury_count_to_score(
        int(c.get("luxury_retail") or 0), baselines, keys_to_try, _LUX_METRICS["luxury_retail"]
    )

    detail["bucket_scores"] = {
        "wealth_offices": round(s_wealth, 1),
        "private_recreation": round(s_priv, 1),
        "arts_culture": round(s_arts, 1),
        "specialist_healthcare": round(s_hc, 1) if hc_active else None,
        "luxury_retail": round(s_ret, 1),
    }

    if hc_active:
        w = (_LUX_W_WEALTH, _LUX_W_PRIVATE, _LUX_W_ARTS, _LUX_W_HC, _LUX_W_RETAIL)
        score = w[0] * s_wealth + w[1] * s_priv + w[2] * s_arts + w[3] * s_hc + w[4] * s_ret
        detail["weights"] = {
            "wealth_offices": _LUX_W_WEALTH,
            "private_recreation": _LUX_W_PRIVATE,
            "arts_culture": _LUX_W_ARTS,
            "specialist_healthcare": _LUX_W_HC,
            "luxury_retail": _LUX_W_RETAIL,
        }
        detail["healthcare_included"] = True
    else:
        base_sum = _LUX_W_WEALTH + _LUX_W_PRIVATE + _LUX_W_ARTS + _LUX_W_RETAIL
        extra = _LUX_W_HC
        w_w = _LUX_W_WEALTH + extra * (_LUX_W_WEALTH / base_sum)
        w_p = _LUX_W_PRIVATE + extra * (_LUX_W_PRIVATE / base_sum)
        w_a = _LUX_W_ARTS + extra * (_LUX_W_ARTS / base_sum)
        w_r = _LUX_W_RETAIL + extra * (_LUX_W_RETAIL / base_sum)
        score = w_w * s_wealth + w_p * s_priv + w_a * s_arts + w_r * s_ret
        detail["weights"] = {
            "wealth_offices": round(w_w, 4),
            "private_recreation": round(w_p, 4),
            "arts_culture": round(w_a, 4),
            "specialist_healthcare": 0.0,
            "luxury_retail": round(w_r, 4),
        }
        detail["healthcare_included"] = False
        detail["healthcare_excluded_reason"] = "count_lt_3"

    detail["luxury_presence"] = round(max(0.0, min(100.0, score)), 1)
    return float(detail["luxury_presence"]), detail


def compute_luxury_presence_osm(
    lat: float,
    lon: float,
    keys_to_try: List[str],
    baselines: Dict[str, Any],
    radius_m: int = 1500,
) -> Tuple[float, Dict[str, Any]]:
    """
    Luxury presence 0–100 from dedicated OSM tag buckets. Falls back to zeros if query fails.
    Healthcare bucket omitted (and weight redistributed) when specialist_healthcare count < 3.
    """
    try:
        from data_sources.status_signal_luxury_osm import query_status_signal_luxury_osm
    except Exception:
        return 0.0, {"source": "osm", "error": "import_failed", "radius_m": int(radius_m)}

    raw = query_status_signal_luxury_osm(lat, lon, radius_m=radius_m)
    detail_head: Dict[str, Any] = {"source": "osm", "radius_m": int(radius_m)}
    if not raw or not raw.get("counts"):
        detail_head["error"] = "no_osm_result"
        return 0.0, detail_head

    rc = raw["counts"]
    c = {k: int(rc.get(k) or 0) for k in _LUXURY_COUNT_KEYS}
    return _luxury_score_detail_from_counts(c, keys_to_try, baselines, detail_head)


def compute_luxury_presence_osm_with_merged_supplement(
    lat: float,
    lon: float,
    business_list: Optional[List[Dict[str, Any]]],
    keys_to_try: List[str],
    baselines: Dict[str, Any],
    radius_m: int = 1500,
) -> Tuple[float, Dict[str, Any]]:
    """
    Luxury 0–100: always use dedicated OSM luxury Overpass (lawyers / wealth offices, etc.),
    then per-bucket max with merged OSM+Places amenities ``business_list`` so Places-only signal is kept.
    If both are empty and OSM failed, fall back to brand name matching on ``business_list``.
    """
    _osm_score, osm_detail = compute_luxury_presence_osm(lat, lon, keys_to_try, baselines, radius_m=radius_m)
    osm_err = osm_detail.get("error")
    raw_osm = osm_detail.get("counts") if isinstance(osm_detail.get("counts"), dict) else {}
    counts_osm = {k: int(raw_osm.get(k) or 0) for k in _LUXURY_COUNT_KEYS}

    merged_detail: Optional[Dict[str, Any]] = None
    counts_m = {k: 0 for k in _LUXURY_COUNT_KEYS}
    if merged_business_list_has_coordinates(business_list or []):
        _, merged_detail = compute_luxury_presence_from_business_list(
            lat, lon, business_list, keys_to_try, baselines, radius_m=radius_m
        )
        if isinstance(merged_detail.get("counts"), dict):
            mc = merged_detail["counts"]
            counts_m = {k: int(mc.get(k) or 0) for k in _LUXURY_COUNT_KEYS}

    combined = {k: max(counts_osm[k], counts_m[k]) for k in _LUXURY_COUNT_KEYS}
    total_c = sum(combined.values())

    if total_c == 0 and osm_err in ("no_osm_result", "import_failed"):
        brand = compute_brand(business_list or [], keys_to_try, baselines)
        return brand, {
            "source": "brand_fallback",
            "reason": osm_err or "osm_unavailable",
            "radius_m": int(radius_m),
            "counts": dict(combined),
            "counts_dedicated_osm_luxury": dict(counts_osm),
            "counts_merged_business_list": dict(counts_m),
        }

    head: Dict[str, Any] = {
        "source": "osm_with_merged_amenities_supplement",
        "radius_m": int(radius_m),
        "counts_dedicated_osm_luxury": dict(counts_osm),
        "counts_merged_business_list": dict(counts_m),
    }
    if osm_err:
        head["osm_error"] = osm_err
    if merged_detail:
        if "rows_in_radius" in merged_detail:
            head["merged_rows_in_radius"] = merged_detail["rows_in_radius"]
        if merged_detail.get("error"):
            head["merged_error"] = merged_detail["error"]
    return _luxury_score_detail_from_counts(combined, keys_to_try, baselines, head)


def _luxury_tags_from_business_row(b: Dict[str, Any]) -> Dict[str, str]:
    """Build OSM-style tag keys from a merged amenities business dict."""
    out: Dict[str, str] = {}
    for k in ("shop", "leisure", "amenity", "tourism", "office", "sport", "healthcare", "access"):
        v = b.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out[k] = s
    return out


# Amenities ``type`` (OSM routing or Places-mapped) → buckets not always inferable from tag columns alone.
_MERGED_BUSINESS_TYPE_LUXURY: Dict[str, frozenset] = {
    "museum": frozenset({"arts_culture"}),
    "gallery": frozenset({"arts_culture"}),
    "theater": frozenset({"arts_culture"}),
}


def _merged_luxury_buckets_for_business_row(b: Dict[str, Any]) -> Set[str]:
    from data_sources.status_signal_luxury_osm import classify_luxury_osm_tags

    buckets: Set[str] = set(classify_luxury_osm_tags(_luxury_tags_from_business_row(b)))
    a = (b.get("amenity") or "").strip().lower()
    if a == "cinema":
        buckets.add("arts_culture")
    t = (b.get("type") or "").strip().lower()
    extra = _MERGED_BUSINESS_TYPE_LUXURY.get(t)
    if extra:
        buckets |= extra
    return buckets


def merged_business_list_has_coordinates(business_list: Optional[List[Dict[str, Any]]]) -> bool:
    """True if at least one business row has parsable lat/lon (required for merged-list luxury)."""
    if not business_list:
        return False
    for b in business_list:
        if not isinstance(b, dict):
            continue
        blat, blon = b.get("lat"), b.get("lon")
        if blat is None or blon is None:
            continue
        try:
            plat, plon = float(blat), float(blon)
        except (TypeError, ValueError):
            continue
        if math.isfinite(plat) and math.isfinite(plon):
            return True
    return False


def compute_luxury_presence_from_business_list(
    lat: float,
    lon: float,
    business_list: Optional[List[Dict[str, Any]]],
    keys_to_try: List[str],
    baselines: Dict[str, Any],
    radius_m: int = 1500,
) -> Tuple[float, Dict[str, Any]]:
    """
    Luxury 0–100 from deduped OSM+Places amenities ``business_list`` within ``radius_m`` of (lat, lon).
    Uses the same buckets and baselines as ``compute_luxury_presence_osm`` (no second Overpass query).
    """
    from data_sources.utils import haversine_distance

    detail: Dict[str, Any] = {"source": "merged_business_list", "radius_m": int(radius_m)}
    if not business_list:
        detail["error"] = "empty_list"
        return 0.0, detail
    if not merged_business_list_has_coordinates(business_list):
        detail["error"] = "no_row_coordinates"
        return 0.0, detail

    counts = {
        "wealth_offices": 0,
        "private_recreation": 0,
        "arts_culture": 0,
        "specialist_healthcare": 0,
        "luxury_retail": 0,
    }
    rows_in_radius = 0
    for b in business_list:
        if not isinstance(b, dict):
            continue
        blat, blon = b.get("lat"), b.get("lon")
        if blat is None or blon is None:
            continue
        try:
            plat, plon = float(blat), float(blon)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(plat) or not math.isfinite(plon):
            continue
        d = haversine_distance(float(lat), float(lon), plat, plon)
        if d > float(radius_m):
            continue
        rows_in_radius += 1
        for bucket in _merged_luxury_buckets_for_business_row(b):
            if bucket in counts:
                counts[bucket] += 1

    detail["rows_in_radius"] = rows_in_radius
    return _luxury_score_detail_from_counts(counts, keys_to_try, baselines, detail)


def _get_cbsa_median_income(baselines: Dict[str, Any], keys_to_try: List[str]) -> Optional[float]:
    """CBSA median household income for multi-modal wealth (from first baseline key)."""
    for key in (keys_to_try or []):
        if key in ("cbsa_to_baseline",):
            continue
        data = baselines.get(key) or {}
        med = data.get("cbsa_median_income")
        if med is not None and isinstance(med, (int, float)) and med > 0:
            return float(med)
    return None


def compute_wealth(
    housing_details: Dict[str, Any],
    keys_to_try: List[str],
    baselines: Dict[str, Any],
) -> Optional[float]:
    """Multi-Modal Wealth. Elite Uniformity: median > 2x CBSA median and low gap -> 95. Elite Outlier: median near CBSA but high mean (high gap) -> gap-weighted score. Else: 60% mean + 40% gap, CBSA-normalized."""
    summary = housing_details.get("summary") or housing_details
    mean_income = summary.get("mean_household_income")
    median_income = summary.get("median_household_income")
    if median_income is None or not isinstance(median_income, (int, float)) or median_income <= 0:
        return None
    if mean_income is None or not isinstance(mean_income, (int, float)):
        mean_income = median_income
    median_f = float(median_income)
    mean_f = float(mean_income)
    wealth_gap = (mean_f - median_f) / median_f if median_f else 0.0

    cbsa_median = _get_cbsa_median_income(baselines, keys_to_try)
    if cbsa_median is not None and cbsa_median > 0:
        if median_f > 2.0 * cbsa_median and wealth_gap < 0.25:
            return 95.0  # Elite Uniformity: status multiplier

    min_mean, max_mean = _get_baseline(baselines, keys_to_try, "wealth", "mean_hh_income")
    min_gap, max_gap = _get_baseline(baselines, keys_to_try, "wealth", "wealth_gap_ratio")
    if min_mean is None or max_mean is None:
        return None
    n_mean = _normalize_min_max(mean_f, min_mean, max_mean)
    n_gap = 50.0
    if min_gap is not None and max_gap is not None:
        n_gap = _normalize_min_max(wealth_gap, min_gap, max_gap)

    if cbsa_median is not None and cbsa_median > 0:
        if 0.8 * cbsa_median <= median_f <= 1.2 * cbsa_median and wealth_gap >= 0.50:
            return round(max(0.0, min(100.0, 0.3 * n_mean + 0.7 * n_gap)), 1)  # Elite Outlier

    return 0.6 * n_mean + 0.4 * n_gap


# Home cost: fallback when no division baselines ($1M threshold, linear 0->100 from $1M to $3M)
HOME_COST_THRESHOLD = 1_000_000
HOME_COST_MAX = 3_000_000


def compute_home_cost(
    median_home_value: Optional[float],
    keys_to_try: Optional[List[str]] = None,
    baselines: Optional[Dict[str, Any]] = None,
) -> float:
    """Desirability: normalized by baseline median_home_value min/max when available; else 0 below $1M, linear 0-100 from $1M to $3M."""
    if median_home_value is None or not isinstance(median_home_value, (int, float)):
        return 0.0
    val = float(median_home_value)
    if keys_to_try and baselines:
        min_v, max_v = _get_baseline(baselines, keys_to_try, "home_cost", "median_home_value")
        if min_v is not None and max_v is not None and max_v > min_v:
            return _normalize_min_max(val, min_v, max_v)
    # Fallback: fixed $1M-$3M band
    if val < HOME_COST_THRESHOLD:
        return 0.0
    if val >= HOME_COST_MAX:
        return 100.0
    return 100.0 * (val - HOME_COST_THRESHOLD) / (HOME_COST_MAX - HOME_COST_THRESHOLD)


def _wealth_character(housing_details: Dict[str, Any]) -> str:
    """Quality-control label from wealth gap: super_zip (widespread affluence) vs unequal (few ultra-wealthy) vs typical."""
    summary = housing_details.get("summary") or housing_details
    mean_income = summary.get("mean_household_income")
    median_income = summary.get("median_household_income")
    if median_income is None or not isinstance(median_income, (int, float)) or median_income <= 0:
        return "typical"
    if mean_income is None or not isinstance(mean_income, (int, float)):
        mean_income = median_income
    median_f = float(median_income)
    mean_f = float(mean_income)
    gap = (mean_f - median_f) / median_f if median_f else 0.0
    if median_f >= 150_000 and gap < 0.25:
        return "super_zip"
    if gap >= 0.5:
        return "unequal"
    return "typical"


def compute_education(
    social_fabric_details: Dict[str, Any],
    keys_to_try: List[str],
    baselines: Dict[str, Any],
) -> Optional[float]:
    """Credential-First Education: 80% graduate/professional attainment, 20% bachelors. No self-employed (avoids urban bias). 0-100 scale, CBSA-normalized."""
    edu = social_fabric_details.get("education_attainment") or {}
    grad_pct = edu.get("grad_pct")
    bach_pct = edu.get("bachelor_pct")
    if grad_pct is None and bach_pct is None:
        return None

    if grad_pct is not None:
        grad_pct = max(0.0, min(100.0, float(grad_pct)))
    if bach_pct is not None:
        bach_pct = max(0.0, min(100.0, float(bach_pct)))

    min_grad, max_grad = _get_baseline(baselines, keys_to_try, "education", "grad_pct")
    min_bach, max_bach = _get_baseline(baselines, keys_to_try, "education", "bach_pct")

    n_grad = 50.0
    if grad_pct is not None and min_grad is not None and max_grad is not None:
        n_grad = _normalize_min_max(grad_pct, min_grad, max_grad)
    n_bach = 50.0
    if bach_pct is not None and min_bach is not None and max_bach is not None:
        n_bach = _normalize_min_max(bach_pct, min_bach, max_bach)
    return 0.80 * n_grad + 0.20 * n_bach


# S2401 (Occupation by Industry): 001=total, 004=management, 005=business/financial, 007=computer, 008=arch/eng, 012=legal, 013=education, 017=health practitioners
_S2401_VARS = [
    "S2401_C01_001E", "S2401_C01_004E", "S2401_C01_005E", "S2401_C01_007E", "S2401_C01_008E",
    "S2401_C01_012E", "S2401_C01_013E", "S2401_C01_017E",
]
# Indices 1,5,7 = management, legal, health (for Patrician 80% weight)
_S2401_MGMT_LEGAL_HEALTH_INDICES = (1, 5, 7)


def _fetch_s2401_occupation_shares(tract: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """Fetch S2401 at tract level. Returns white_collar_pct and management_legal_healthcare_pct (Management+Legal+Healthcare)."""
    from data_sources.census_api import CENSUS_API_KEY, CENSUS_BASE_URL, _make_request_with_retry
    if not tract or not CENSUS_API_KEY:
        return None
    state_fips = tract.get("state_fips")
    county_fips = tract.get("county_fips")
    tract_fips = tract.get("tract_fips")
    if not all([state_fips, county_fips, tract_fips]):
        return None
    url = f"{CENSUS_BASE_URL}/2022/acs/acs5/subject"
    params = {
        "get": ",".join(_S2401_VARS),
        "for": f"tract:{tract_fips}",
        "in": f"state:{state_fips} county:{county_fips}",
        "key": CENSUS_API_KEY,
    }
    try:
        r = _make_request_with_retry(url, params, timeout=15, max_retries=2)
        if not r or r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, list) or len(data) < 2:
            return None
        row = data[1]
        total = row[0]
        err = (None, "", "-666666666", "-999999999")
        if total in err or not total:
            return None
        t = float(total)
        if t <= 0:
            return None
        white = sum(
            float(row[i]) if i < len(row) and row[i] not in err else 0
            for i in range(1, len(_S2401_VARS))
        )
        mgmt_legal_health = sum(
            float(row[i]) if i < len(row) and row[i] not in err else 0
            for i in _S2401_MGMT_LEGAL_HEALTH_INDICES
        )
        return {
            "white_collar_pct": 100.0 * white / t,
            "management_legal_healthcare_pct": 100.0 * mgmt_legal_health / t,
        }
    except Exception:
        return None


def _fetch_white_collar_pct_tract(tract: Optional[Dict[str, Any]]) -> Optional[float]:
    """Fetch S2401 at tract level for white collar % (management + professional + related)."""
    out = _fetch_s2401_occupation_shares(tract)
    return out.get("white_collar_pct") if out else None


def compute_occupation(
    economic_security_details: Dict[str, Any],
    social_fabric_details: Dict[str, Any],
    tract: Optional[Dict[str, Any]],
    keys_to_try: List[str],
    baselines: Dict[str, Any],
    archetype: Optional[str] = None,
) -> Optional[float]:
    """Occupation: S2401 Management/Business/Science/Arts (white_collar_pct) normalized against CBSA."""
    white_collar_pct = (economic_security_details.get("breakdown") or {}).get("white_collar_pct")
    if white_collar_pct is None and tract:
        white_collar_pct = _fetch_white_collar_pct_tract(tract)
    if white_collar_pct is None:
        return None
    min_wc, max_wc = _get_baseline(baselines, keys_to_try, "occupation", "white_collar_pct")

    def _n(val: Optional[float], mn: Optional[float], mx: Optional[float], default: float = 50.0) -> float:
        if val is None or mn is None or mx is None:
            return default
        return _normalize_min_max(val, mn, mx)

    return _n(white_collar_pct, min_wc, max_wc)


def _brand_matches_for_business_list(business_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return per-category match details (category, weight, cat_score, matched_names) for inspection.
    Name-only matching: only businesses whose name matches a configured brand name count."""
    if not business_list:
        return []
    out: List[Dict[str, Any]] = []
    for category, config in STATUS_SIGNAL_BRAND_CONFIG.items():
        weight = config.get("weight", 0.25)
        names_re = config.get("brand_names", [])
        if not names_re:
            continue
        pattern = re.compile("|".join(re.escape(n) for n in names_re), re.I)
        matches = [b for b in business_list if (b.get("name") and pattern.search(b.get("name", "")))]
        if not matches:
            cat_score = 0.0
        else:
            # Universal logic: at least one matching brand in this category
            # earns full credit for that category.
            cat_score = 1.0
        matched_names = [b.get("name") or "(no name)" for b in matches]
        out.append({
            "category": category,
            "weight": weight,
            "cat_score": cat_score,
            "matched_names": matched_names,
        })
    return out


def brand_raw_score(business_list: List[Dict[str, Any]]) -> float:
    """Raw luxury-presence score 0-100 (same scale used for baselines). Exported for baseline script."""
    if not business_list:
        return 0.0
    raw = 0.0
    for item in _brand_matches_for_business_list(business_list):
        raw += item["cat_score"] * item["weight"]
    return min(100.0, raw * 100.0)


def compute_brand(
    business_list: List[Dict[str, Any]],
    keys_to_try: Optional[List[str]] = None,
    baselines: Optional[Dict[str, Any]] = None,
) -> float:
    """Luxury presence 0-100; normalized by baselines when available."""
    raw = brand_raw_score(business_list or [])
    if not keys_to_try or not baselines:
        return raw
    min_b, max_b = _get_baseline(baselines, keys_to_try, "brand", "brand_raw_score")
    if min_b is not None and max_b is not None:
        return _normalize_min_max(raw, min_b, max_b)
    return raw


# Weights: wealth 37%, home_cost 26%, education 21%, occupation 16%
W_WEALTH = 0.37
W_HOME_COST = 0.26
W_EDUCATION = 0.21
W_OCCUPATION = 0.16

PROVISIONAL_COMPOSITE_WEIGHTS = (W_WEALTH, W_HOME_COST, W_EDUCATION, W_OCCUPATION)




def _composite_score_from_weights(
    w_wealth: float,
    w_home: float,
    w_edu: float,
    w_occ: float,
    wealth: Optional[float],
    home_cost: float,
    education: Optional[float],
    occupation: Optional[float],
) -> Optional[float]:
    """Weighted mean; mirrors final Status Signal aggregation (missing occupation drops occ weight)."""
    total_w = 0.0
    score = 0.0
    if wealth is not None:
        total_w += w_wealth
        score += w_wealth * wealth
    total_w += w_home
    score += w_home * home_cost
    if education is not None:
        total_w += w_edu
        score += w_edu * education
    if occupation is not None:
        total_w += w_occ
        score += w_occ * occupation
    if total_w <= 0:
        return None
    return score / total_w


def _classify_archetype(
    *,
    education: Optional[float],
    wealth: Optional[float],
    home_cost: float,
    wealth_gap: Optional[float],
    occupation_neutral: Optional[float],
    stability: Optional[float] = None,
) -> Tuple[str, str]:
    """
    5-archetype chain: Established → Professional → Up-and-Coming → Rooted → Working Class.
    stability (0-100) from social_fabric.breakdown.stability.
    Returns (archetype, archetype_rule) for debug.
    """
    edu_val = float(education) if education is not None else 0.0
    occ_val = float(occupation_neutral) if occupation_neutral is not None else 0.0
    wealth_val = float(wealth) if wealth is not None else 0.0
    stab_val = float(stability) if stability is not None else None

    # Non-residential / data-sparse tracts (Red Hook industrial, Downtown LA, etc.)
    if home_cost == 0 and wealth_val < 25:
        return "Unclassified", "insufficient_data"

    # Established: ultra-high wealth qualifies only when housing costs confirm a prestige enclave.
    # home_cost >= 50 screens out inequality-inflated tracts (a few wealthy households in an
    # otherwise moderate neighborhood) and transient/rental areas with no real estate premium.
    if wealth_val >= 90 and home_cost >= 50:
        return "Established", "established_ultra_wealth"

    # Professional: credential class fires before stab-gated Established so that credential-dense
    # moderate-wealth neighborhoods (West Village, Carroll Gardens) classify correctly.
    if edu_val >= 78 and occ_val >= 80:
        return "Professional", "professional_credential_class"

    # Established: very high wealth — less stability required (executive, transient-elite markets)
    if wealth_val > 85 and stab_val is not None and stab_val > 35:
        return "Established", "established_high_wealth"

    # Established: capital wealth + community roots (W=75-85 range needs stronger stability signal)
    if wealth_val > 75 and stab_val is not None and stab_val > 45:
        return "Established", "established_capital_wealth"

    # Up-and-Coming: home values repricing ahead of resident wealth (gentrifying / recently gentrified)
    if home_cost >= 65 and wealth_val < 85 and (stab_val is None or stab_val < 45):
        return "Up-and-Coming", "upandcoming_gentrifying"

    # Rooted: tight-knit community holding ground under housing cost pressure
    if stab_val is not None and stab_val >= 55 and wealth_val < 65 and home_cost > 50:
        return "Rooted", "rooted_stable_community"

    return "Working Class", "working_class_community"


def _merge_social_and_diversity_for_signal(
    social_fabric_details: Optional[Dict[str, Any]],
    diversity_details: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Diversity pillar wins on education_attainment and self_employed_pct for Status Signal."""
    merged: Dict[str, Any] = dict(social_fabric_details or {})
    div = diversity_details or {}
    if div.get("education_attainment") is not None:
        merged["education_attainment"] = div["education_attainment"]
    if div.get("self_employed_pct") is not None:
        merged["self_employed_pct"] = div["self_employed_pct"]
    return merged


def _backfill_status_signal_social_inputs(
    merged_sf: Dict[str, Any],
    tract: Optional[Dict[str, Any]],
    lat: Optional[float],
    lon: Optional[float],
) -> Dict[str, Any]:
    """
    Preserve Social Fabric split while restoring Status Signal classifier inputs.
    Backfill only missing education_attainment / self_employed_pct from census diversity data.
    """
    needs_edu = not isinstance(merged_sf.get("education_attainment"), dict)
    needs_se = merged_sf.get("self_employed_pct") is None
    if not (needs_edu or needs_se):
        return merged_sf
    if lat is None or lon is None:
        return merged_sf
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return merged_sf
    if not math.isfinite(float(lat)) or not math.isfinite(float(lon)):
        return merged_sf

    try:
        from data_sources import census_api as _ca

        fallback = _ca.get_diversity_data(float(lat), float(lon), tract=tract) or {}
    except Exception:
        fallback = {}

    out = dict(merged_sf)
    if needs_edu and isinstance(fallback.get("education_attainment"), dict):
        out["education_attainment"] = fallback["education_attainment"]
    if needs_se and fallback.get("self_employed_pct") is not None:
        out["self_employed_pct"] = fallback["self_employed_pct"]
    return out


def compute_status_signal(
    housing_details: Optional[Dict[str, Any]],
    social_fabric_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    business_list: Optional[List[Dict[str, Any]]],
    tract: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
    diversity_details: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """
    Compute Status Signal (0-100): wealth + home_cost + education + occupation + luxury_presence.

    Returns None if required data is missing.
    """
    result, _ = compute_status_signal_with_breakdown(
        housing_details,
        social_fabric_details,
        economic_security_details,
        business_list,
        tract,
        state_abbrev,
        diversity_details=diversity_details,
    )
    return result


def compute_status_signal_with_breakdown(
    housing_details: Optional[Dict[str, Any]],
    social_fabric_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    business_list: Optional[List[Dict[str, Any]]],
    tract: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    luxury_radius_m: Optional[int] = None,
    diversity_details: Optional[Dict[str, Any]] = None,
    area_type: Optional[str] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Returns (score, breakdown) with components 0-100, wealth_character, archetype, status_label.
    Archetype chain: Established → Professional → Rising → Blue Collar → Middle Class.
    Final composite uses archetype weights (no luxury signal).
    Baselines: tract CBSA mapped via cbsa_to_baseline; else division then \"all\".
    """
    breakdown: Dict[str, Any] = {
        "wealth": None,
        "home_cost": None,
        "education": None,
        "occupation": None,
        "luxury_presence": None,
        "luxury_presence_detail": None,
        "wealth_character": "typical",
        "archetype": "Blue Collar",
        "archetype_rule": "blue_collar_default",
        "classifier_inputs": {},
        "provisional_composite_score": None,
        "status_label": "Blue Collar",
        "status_insight": "",
        "top_drivers": [],
        "analysis_radius_note": None,
        "signal_strength": None,
        "signal_strength_label": None,
        "composite_score": None,
        "downgrade_reason": None,
        "original_archetype": None,
        "original_archetype_rule": None,
        "rerun_inputs": None,
    }
    if not housing_details or not economic_security_details:
        return None, breakdown
    merged_sf = _merge_social_and_diversity_for_signal(social_fabric_details, diversity_details)
    merged_sf = _backfill_status_signal_social_inputs(merged_sf, tract, lat, lon)
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"
    baselines = _load_baselines()
    if not baselines:
        keys_to_try = [division, "all"]
    else:
        cbsa_baseline_key = _get_baseline_key_from_cbsa(tract, baselines, city, state_abbrev, division)
        if cbsa_baseline_key and baselines.get(cbsa_baseline_key):
            keys_to_try = [cbsa_baseline_key]
        else:
            keys_to_try = []
        if division not in keys_to_try:
            keys_to_try.append(division)
        if "all" not in keys_to_try:
            keys_to_try.append("all")

    wealth = compute_wealth(housing_details, keys_to_try, baselines)
    summary = housing_details.get("summary") or housing_details
    median_home = summary.get("median_home_value")
    home_cost = compute_home_cost(median_home, keys_to_try, baselines)
    education = compute_education(merged_sf, keys_to_try, baselines)

    wealth_character = _wealth_character(housing_details)
    wealth_gap: Optional[float] = None
    med = summary.get("median_household_income")
    mean = summary.get("mean_household_income")
    if med is not None and isinstance(med, (int, float)) and med > 0:
        if mean is not None and isinstance(mean, (int, float)):
            wealth_gap = (float(mean) - float(med)) / float(med)

    occupation_neutral = compute_occupation(
        economic_security_details,
        merged_sf,
        tract,
        keys_to_try,
        baselines,
    )

    pw, ph, pe, po = PROVISIONAL_COMPOSITE_WEIGHTS
    provisional = _composite_score_from_weights(
        pw, ph, pe, po,
        wealth,
        home_cost,
        education,
        occupation_neutral,
    )

    stability: Optional[float] = None
    sf_breakdown = (social_fabric_details or {}).get("breakdown") or {}
    _stab = sf_breakdown.get("stability")
    if _stab is not None:
        try:
            stability = float(_stab)
        except (TypeError, ValueError):
            pass

    archetype, archetype_rule = _classify_archetype(
        education=education,
        wealth=wealth,
        home_cost=home_cost,
        wealth_gap=wealth_gap,
        occupation_neutral=occupation_neutral,
        stability=stability,
    )

    w_wealth, w_home_cost, w_education, w_occupation = _get_archetype_weights(archetype)
    status_label = _get_status_label(archetype)
    status_insight = _get_status_insight(archetype)
    top_drivers = _build_top_drivers(wealth, home_cost, education, occupation_neutral, archetype)

    breakdown["wealth"] = wealth
    breakdown["home_cost"] = home_cost
    breakdown["education"] = education
    breakdown["occupation"] = occupation_neutral
    breakdown["wealth_character"] = wealth_character
    breakdown["archetype"] = archetype
    breakdown["archetype_rule"] = archetype_rule
    breakdown["classifier_inputs"] = {
        "education": education,
        "home_cost": home_cost,
        "wealth_character": wealth_character,
        "occupation": occupation_neutral,
        "wealth": wealth,
        "wealth_gap": wealth_gap,
        "stability": stability,
    }
    breakdown["provisional_composite_score"] = (
        round(provisional, 1) if provisional is not None else None
    )
    breakdown["status_label"] = status_label
    breakdown["status_insight"] = status_insight
    breakdown["top_drivers"] = top_drivers

    if wealth is None and education is None and occupation_neutral is None:
        return None, breakdown

    total_w = 0.0
    score = 0.0
    if wealth is not None:
        total_w += w_wealth
        score += w_wealth * wealth
    total_w += w_home_cost
    score += w_home_cost * home_cost
    if education is not None:
        total_w += w_education
        score += w_education * education
    if occupation_neutral is not None:
        total_w += w_occupation
        score += w_occupation * occupation_neutral

    if total_w <= 0:
        return None, breakdown
    raw = score / total_w
    final = round(max(0.0, min(100.0, raw)), 1)
    ss_key, ss_label = _signal_strength_band(final)
    breakdown["composite_score"] = final
    breakdown["signal_strength"] = ss_key
    breakdown["signal_strength_label"] = ss_label
    return final, breakdown
