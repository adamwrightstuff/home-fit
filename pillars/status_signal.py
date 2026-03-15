"""
Status Signal: post-pillars derived score (wealth, education, occupation, brands).

Only computed when all four pillars have data: housing_value, social_fabric,
economic_security, neighborhood_amenities. Uses per-division min-max baselines
from data/status_signal_baselines.json.

Composite: Brand×0.35 + Wealth×0.25 + Education×0.20 + Occupation×0.20
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# Brand categories for Status Signal (discriminating taste/status brands only).
# Whole Foods, Trader Joe's, Lululemon removed as too ubiquitous.
STATUS_SIGNAL_BRAND_CONFIG = {
    "personal_care": {
        "weight": 0.20,
        "partial_match_types": ["perfumery", "cosmetics"],
        "brand_names": ["Aesop", "Bluemercury", "Space NK", "Le Labo", "Diptyque", "Byredo", "Frederic Malle"],
    },
    "luxury_gym": {
        "weight": 0.17,
        "partial_match_types": ["fitness_centre", "sports_centre"],
        "brand_names": ["Equinox", "Barry's Bootcamp", "Barry's"],
    },
    "hospitality": {
        "weight": 0.17,
        "brand_names": ["Soho House", "Arlo Hotels", "Ace Hotel"],
    },
    "boutique_fitness": {
        "weight": 0.13,
        "partial_match_types": ["fitness_centre", "sports_centre"],
        "brand_names": ["Rumble Boxing", "Rumble", "Natural Pilates"],
    },
    "coffee": {
        "weight": 0.13,
        "partial_match_types": ["cafe"],
        "brand_names": ["Blue Bottle", "Intelligentsia", "Stumptown", "Verve"],
    },
    "grocery": {
        "weight": 0.11,
        "partial_match_types": ["supermarket", "greengrocer"],
        "brand_names": ["Erewhon", "Bristol Farms", "The Fresh Market", "Wegmans", "Citarella"],
    },
    "retail": {
        "weight": 0.09,
        "partial_match_types": ["clothes", "fashion", "boutique"],
        "brand_names": ["Reformation", "Aritzia", "Theory", "Faherty"],
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


def _get_baseline(
    baselines: Dict[str, Any],
    division: str,
    component: str,
    metric: str,
) -> Tuple[Optional[float], Optional[float]]:
    div_data = baselines.get(division) or baselines.get("all") or {}
    comp = div_data.get(component, {})
    m = comp.get(metric, {})
    if isinstance(m, dict) and "min" in m and "max" in m:
        return float(m["min"]), float(m["max"])
    return None, None


def compute_wealth(
    housing_details: Dict[str, Any],
    division: str,
    baselines: Dict[str, Any],
) -> Optional[float]:
    """Wealth Concentration: 60% mean income normalized + 40% wealth gap normalized."""
    summary = housing_details.get("summary") or housing_details
    mean_income = summary.get("mean_household_income")
    median_income = summary.get("median_household_income")
    if median_income is None or not isinstance(median_income, (int, float)) or median_income <= 0:
        return None
    if mean_income is None or not isinstance(mean_income, (int, float)):
        mean_income = median_income
    wealth_gap = (float(mean_income) - float(median_income)) / float(median_income)

    min_mean, max_mean = _get_baseline(baselines, division, "wealth", "mean_hh_income")
    min_gap, max_gap = _get_baseline(baselines, division, "wealth", "wealth_gap_ratio")
    if min_mean is None or max_mean is None:
        return None
    n_mean = _normalize_min_max(float(mean_income), min_mean, max_mean)
    n_gap = 50.0
    if min_gap is not None and max_gap is not None:
        n_gap = _normalize_min_max(wealth_gap, min_gap, max_gap)
    return 0.6 * n_mean + 0.4 * n_gap


def compute_education(
    social_fabric_details: Dict[str, Any],
    division: str,
    baselines: Dict[str, Any],
) -> Optional[float]:
    """Education Density: 50% grad_pct + 30% bach_pct + 20% self_employed_pct (all normalized)."""
    edu = social_fabric_details.get("education_attainment") or {}
    grad_pct = edu.get("grad_pct")
    bach_pct = edu.get("bachelor_pct")
    self_employed_pct = social_fabric_details.get("self_employed_pct")
    if grad_pct is None and bach_pct is None and self_employed_pct is None:
        return None

    min_grad, max_grad = _get_baseline(baselines, division, "education", "grad_pct")
    min_bach, max_bach = _get_baseline(baselines, division, "education", "bach_pct")
    min_se, max_se = _get_baseline(baselines, division, "education", "self_employed_pct")

    n_grad = 50.0
    if grad_pct is not None and min_grad is not None and max_grad is not None:
        n_grad = _normalize_min_max(float(grad_pct), min_grad, max_grad)
    n_bach = 50.0
    if bach_pct is not None and min_bach is not None and max_bach is not None:
        n_bach = _normalize_min_max(float(bach_pct), min_bach, max_bach)
    n_se = 50.0
    if self_employed_pct is not None and min_se is not None and max_se is not None:
        n_se = _normalize_min_max(float(self_employed_pct), min_se, max_se)
    return 0.5 * n_grad + 0.3 * n_bach + 0.2 * n_se


def _fetch_white_collar_pct_tract(tract: Dict[str, Any]) -> Optional[float]:
    """Fetch S2401 at tract level for white collar % (management + professional + related)."""
    from data_sources.census_api import CENSUS_API_KEY, CENSUS_BASE_URL, _make_request_with_retry
    if not tract or not CENSUS_API_KEY:
        return None
    state_fips = tract.get("state_fips")
    county_fips = tract.get("county_fips")
    tract_fips = tract.get("tract_fips")
    if not all([state_fips, county_fips, tract_fips]):
        return None
    vars_list = [
        "S2401_C01_001E", "S2401_C01_004E", "S2401_C01_005E", "S2401_C01_007E", "S2401_C01_008E",
        "S2401_C01_012E", "S2401_C01_013E", "S2401_C01_017E",
    ]
    url = f"{CENSUS_BASE_URL}/2022/acs/acs5/subject"
    params = {
        "get": ",".join(vars_list),
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
            for i in range(1, len(vars_list))
        )
        return 100.0 * white / t
    except Exception:
        return None


def compute_occupation(
    economic_security_details: Dict[str, Any],
    social_fabric_details: Dict[str, Any],
    tract: Optional[Dict[str, Any]],
    division: str,
    baselines: Dict[str, Any],
) -> Optional[float]:
    """Occupation Mix: 50% (finance+arts) + 30% white_collar + 20% self_employed (normalized)."""
    industry = economic_security_details.get("industry_shares_pct") or {}
    fr = industry.get("finance_realestate")
    lh = industry.get("leisure_hospitality")
    finance_arts_pct = None
    if fr is not None and lh is not None:
        try:
            finance_arts_pct = float(fr) + float(lh)
        except (TypeError, ValueError):
            pass
    elif fr is not None:
        finance_arts_pct = float(fr)
    elif lh is not None:
        finance_arts_pct = float(lh)

    white_collar_pct = _fetch_white_collar_pct_tract(tract) if tract else None
    self_employed_pct = social_fabric_details.get("self_employed_pct")

    if finance_arts_pct is None and white_collar_pct is None and self_employed_pct is None:
        return None

    min_fa, max_fa = _get_baseline(baselines, division, "occupation", "finance_arts_pct")
    min_wc, max_wc = _get_baseline(baselines, division, "occupation", "white_collar_pct")
    min_se, max_se = _get_baseline(baselines, division, "occupation", "self_employed_pct")

    n_fa = 50.0
    if finance_arts_pct is not None and min_fa is not None and max_fa is not None:
        n_fa = _normalize_min_max(finance_arts_pct, min_fa, max_fa)
    n_wc = 50.0
    if white_collar_pct is not None and min_wc is not None and max_wc is not None:
        n_wc = _normalize_min_max(white_collar_pct, min_wc, max_wc)
    n_se = 50.0
    if self_employed_pct is not None and min_se is not None and max_se is not None:
        n_se = _normalize_min_max(float(self_employed_pct), min_se, max_se)
    return 0.5 * n_fa + 0.3 * n_wc + 0.2 * n_se


def compute_brand(business_list: List[Dict[str, Any]]) -> float:
    """Brand score 0-100 from config categories (presence of status brands)."""
    if not business_list:
        return 0.0
    raw = 0.0
    for category, config in STATUS_SIGNAL_BRAND_CONFIG.items():
        weight = config.get("weight", 0.25)
        types_ok = config.get("partial_match_types", [])
        names_re = config.get("brand_names", [])
        if not names_re:
            continue
        pattern = re.compile("|".join(re.escape(n) for n in names_re), re.I)
        types_lower = [t.lower() for t in types_ok]
        matches = [
            b for b in business_list
            if (b.get("name") and pattern.search(b.get("name", "")))
            or (b.get("type") and str(b.get("type", "")).lower() in types_lower)
            or (b.get("shop") and str(b.get("shop", "")).lower() in types_lower)
            or (b.get("leisure") and str(b.get("leisure", "")).lower() in types_lower)
            or (b.get("amenity") and str(b.get("amenity", "")).lower() in types_lower)
            or (b.get("type") == "fitness" and any(t in ("fitness_centre", "sports_centre") for t in types_ok))
            or (b.get("type") == "grocery" and any(t in ("supermarket", "greengrocer") for t in types_ok))
        ]
        if not matches:
            cat_score = 0.0
        elif len(matches) >= 2:
            cat_score = 1.0
        else:
            cat_score = 0.5
        raw += cat_score * weight
    return min(100.0, raw * 100.0)


def compute_status_signal(
    housing_details: Optional[Dict[str, Any]],
    social_fabric_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    business_list: Optional[List[Dict[str, Any]]],
    tract: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
) -> Optional[float]:
    """
    Compute Status Signal (0-100) when all four pillar inputs are present.

    Returns None if any required data is missing.
    """
    if not housing_details or not social_fabric_details or not economic_security_details:
        return None
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"
    baselines = _load_baselines()
    if not baselines:
        division = "all"

    wealth = compute_wealth(housing_details, division, baselines)
    education = compute_education(social_fabric_details, division, baselines)
    occupation = compute_occupation(
        economic_security_details, social_fabric_details, tract, division, baselines
    )
    brand = compute_brand(business_list or [])

    if wealth is None and education is None and occupation is None:
        return None
    w_wealth = 0.25
    w_education = 0.20
    w_occupation = 0.20
    w_brand = 0.35
    total_w = 0.0
    score = 0.0
    if wealth is not None:
        total_w += w_wealth
        score += w_wealth * wealth
    if education is not None:
        total_w += w_education
        score += w_education * education
    if occupation is not None:
        total_w += w_occupation
        score += w_occupation * occupation
    score += w_brand * brand  # brand already 0-100, same scale as wealth/education/occupation
    total_w += w_brand
    if total_w <= 0:
        return None
    # Weighted average of 0-100 components -> already 0-100; do not multiply by 100
    raw = score / total_w
    final = round(max(0.0, min(100.0, raw)), 1)
    return final


def compute_status_signal_with_breakdown(
    housing_details: Optional[Dict[str, Any]],
    social_fabric_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    business_list: Optional[List[Dict[str, Any]]],
    tract: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
) -> Tuple[Optional[float], Dict[str, Optional[float]]]:
    """
    Same as compute_status_signal but also returns the four components (0-100 each).
    Returns (score, {"wealth": _, "education": _, "occupation": _, "brand": _}).
    """
    breakdown: Dict[str, Optional[float]] = {"wealth": None, "education": None, "occupation": None, "brand": None}
    if not housing_details or not social_fabric_details or not economic_security_details:
        return None, breakdown
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"
    baselines = _load_baselines()
    if not baselines:
        division = "all"

    wealth = compute_wealth(housing_details, division, baselines)
    education = compute_education(social_fabric_details, division, baselines)
    occupation = compute_occupation(
        economic_security_details, social_fabric_details, tract, division, baselines
    )
    brand = compute_brand(business_list or [])
    breakdown["wealth"] = wealth
    breakdown["education"] = education
    breakdown["occupation"] = occupation
    breakdown["brand"] = brand

    if wealth is None and education is None and occupation is None:
        return None, breakdown
    w_wealth = 0.25
    w_education = 0.20
    w_occupation = 0.20
    w_brand = 0.35
    total_w = 0.0
    score = 0.0
    if wealth is not None:
        total_w += w_wealth
        score += w_wealth * wealth
    if education is not None:
        total_w += w_education
        score += w_education * education
    if occupation is not None:
        total_w += w_occupation
        score += w_occupation * occupation
    score += w_brand * brand
    total_w += w_brand
    if total_w <= 0:
        return None, breakdown
    raw = score / total_w
    final = round(max(0.0, min(100.0, raw)), 1)
    return final, breakdown
