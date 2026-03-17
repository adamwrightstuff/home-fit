"""
Status Signal: post-pillars derived score (status + desirability).

Status = wealth + education + occupation. Desirability = home cost + luxury presence.
Uses per-division and per-CBSA min-max baselines from data/status_signal_baselines.json.
When (city, state) matches a metro cluster (e.g. NYC), uses that CBSA key first (e.g. nyc_metro), then division, then "all".

Weights: wealth 35%, home_cost 25%, education 20%, occupation 10%, luxury_presence 5%.
Wealth gap (mean vs median) is used as a quality-control label: super_zip vs unequal vs typical.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# Brand categories for Status Signal (discriminating taste/status brands only).
# Whole Foods, Trader Joe's, Lululemon removed as too ubiquitous.
# Name-only matching; luxury_gym merges Equinox/Barry's with Rumble/Natural Pilates to avoid double-counting.
STATUS_SIGNAL_BRAND_CONFIG = {
    "personal_care": {
        "weight": 0.20,
        "brand_names": ["Aesop", "Bluemercury", "Space NK", "Le Labo", "Diptyque", "Byredo", "Frederic Malle"],
    },
    "luxury_gym": {
        "weight": 0.30,
        "brand_names": ["Equinox", "Barry's Bootcamp", "Barry's", "Rumble Boxing", "Rumble", "Natural Pilates"],
    },
    "hospitality": {
        "weight": 0.17,
        "brand_names": ["Soho House", "Arlo Hotels", "Ace Hotel"],
    },
    "coffee": {
        "weight": 0.13,
        "brand_names": ["Blue Bottle", "Intelligentsia", "Stumptown", "Verve"],
    },
    "grocery": {
        "weight": 0.11,
        "brand_names": ["Erewhon", "Bristol Farms", "The Fresh Market", "Wegmans", "Citarella"],
    },
    "retail": {
        "weight": 0.09,
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


def _get_cbsa_baseline_key(city: Optional[str], state: Optional[str]) -> Optional[str]:
    """Return CBSA baseline key (e.g. nyc_metro) when (city, state) is in a known metro cluster; else None.
    Must match the same clusters as scripts/build_status_signal_baselines_from_results.get_cbsa_key.
    """
    if not city or not state:
        return None
    key = f"{city}, {state}".strip()
    nyc_cluster = {
        "New York, NY", "Brooklyn, NY", "Queens, NY", "Bronx, NY", "Scarsdale, NY",
        "The Hamptons, NY", "Greenwich, CT", "Westport, CT", "Princeton, NJ", "Ithaca, NY",
        "New York, New York", "City of New York, New York", "Brooklyn, New York",
        "Queens, New York", "Bronx, New York", "Scarsdale, New York", "Village of Scarsdale, New York",
        "The Hamptons, New York", "Greenwich, Connecticut", "Westport, Connecticut",
        "Princeton, New Jersey", "Ithaca, New York",
    }
    if key in nyc_cluster:
        return "nyc_metro"
    if key in {"Philadelphia, PA"}:
        return "philly_metro"
    if key in {"Washington, DC", "Bethesda, MD", "Arlington, VA", "Fairfax, VA"}:
        return "dc_metro"
    return None


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


# Home cost: fallback when no division baselines ($1M threshold, linear 0->100 from $1M to $3M)
HOME_COST_THRESHOLD = 1_000_000
HOME_COST_MAX = 3_000_000


def compute_home_cost(
    median_home_value: Optional[float],
    division: Optional[str] = None,
    baselines: Optional[Dict[str, Any]] = None,
) -> float:
    """Desirability: normalized by division median_home_value min/max when available; else 0 below $1M, linear 0-100 from $1M to $3M."""
    if median_home_value is None or not isinstance(median_home_value, (int, float)):
        return 0.0
    val = float(median_home_value)
    if division and baselines:
        min_v, max_v = _get_baseline(baselines, division, "home_cost", "median_home_value")
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
    division: str,
    baselines: Dict[str, Any],
) -> Optional[float]:
    """Education Density: 50% grad_pct + 30% bach_pct + 20% self_employed_pct (all normalized). Uses 0-100 scale."""
    edu = social_fabric_details.get("education_attainment") or {}
    grad_pct = edu.get("grad_pct")
    bach_pct = edu.get("bachelor_pct")
    self_employed_pct = social_fabric_details.get("self_employed_pct")
    if grad_pct is None and bach_pct is None and self_employed_pct is None:
        return None

    # Clamp to 0-100 so legacy/wrong-scale data does not break normalization
    if grad_pct is not None:
        grad_pct = max(0.0, min(100.0, float(grad_pct)))
    if bach_pct is not None:
        bach_pct = max(0.0, min(100.0, float(bach_pct)))

    min_grad, max_grad = _get_baseline(baselines, division, "education", "grad_pct")
    min_bach, max_bach = _get_baseline(baselines, division, "education", "bach_pct")
    min_se, max_se = _get_baseline(baselines, division, "education", "self_employed_pct")

    n_grad = 50.0
    if grad_pct is not None and min_grad is not None and max_grad is not None:
        n_grad = _normalize_min_max(grad_pct, min_grad, max_grad)
    n_bach = 50.0
    if bach_pct is not None and min_bach is not None and max_bach is not None:
        n_bach = _normalize_min_max(bach_pct, min_bach, max_bach)
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

    white_collar_pct = (economic_security_details.get("breakdown") or {}).get("white_collar_pct")
    if white_collar_pct is None and tract:
        white_collar_pct = _fetch_white_collar_pct_tract(tract)
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
    division: Optional[str] = None,
    baselines: Optional[Dict[str, Any]] = None,
) -> float:
    """Luxury presence 0-100; normalized by division baselines when available."""
    raw = brand_raw_score(business_list or [])
    if not division or not baselines:
        return raw
    min_b, max_b = _get_baseline(baselines, division, "brand", "brand_raw_score")
    if min_b is not None and max_b is not None:
        return _normalize_min_max(raw, min_b, max_b)
    return raw


# Weights: wealth 35%, home_cost 25%, education 20%, occupation 10%, luxury_presence 5% (normalized to sum 1)
W_WEALTH = 0.35 / 0.95
W_HOME_COST = 0.25 / 0.95
W_EDUCATION = 0.20 / 0.95
W_OCCUPATION = 0.10 / 0.95
W_LUXURY = 0.05 / 0.95


def compute_status_signal(
    housing_details: Optional[Dict[str, Any]],
    social_fabric_details: Optional[Dict[str, Any]],
    economic_security_details: Optional[Dict[str, Any]],
    business_list: Optional[List[Dict[str, Any]]],
    tract: Optional[Dict[str, Any]],
    state_abbrev: Optional[str],
) -> Optional[float]:
    """
    Compute Status Signal (0-100): wealth + home_cost + education + occupation + luxury_presence.

    Returns None if required data is missing.
    """
    result, _ = compute_status_signal_with_breakdown(
        housing_details, social_fabric_details, economic_security_details,
        business_list, tract, state_abbrev,
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
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Returns (score, breakdown) with components 0-100 and wealth_character (super_zip | unequal | typical).
    Breakdown: wealth, home_cost, education, occupation, luxury_presence, wealth_character.
    When city is provided, uses CBSA baseline (e.g. nyc_metro) if the location is in a known cluster and
    that key exists in baselines; otherwise uses Census division, then "all".
    """
    breakdown: Dict[str, Any] = {
        "wealth": None,
        "home_cost": None,
        "education": None,
        "occupation": None,
        "luxury_presence": None,
        "wealth_character": "typical",
    }
    if not housing_details or not social_fabric_details or not economic_security_details:
        return None, breakdown
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"
    baselines = _load_baselines()
    if not baselines:
        division = "all"
    # Prefer CBSA baseline (e.g. nyc_metro) when location is in a metro cluster and we have that baseline
    cbsa_key = _get_cbsa_baseline_key(city, state_abbrev)
    baseline_key = cbsa_key if (cbsa_key and baselines.get(cbsa_key)) else division

    wealth = compute_wealth(housing_details, baseline_key, baselines)
    summary = housing_details.get("summary") or housing_details
    median_home = summary.get("median_home_value")
    home_cost = compute_home_cost(median_home, baseline_key, baselines)
    education = compute_education(social_fabric_details, baseline_key, baselines)
    occupation = compute_occupation(
        economic_security_details, social_fabric_details, tract, baseline_key, baselines
    )
    luxury = compute_brand(business_list or [], baseline_key, baselines)
    wealth_character = _wealth_character(housing_details)

    breakdown["wealth"] = wealth
    breakdown["home_cost"] = home_cost
    breakdown["education"] = education
    breakdown["occupation"] = occupation
    breakdown["luxury_presence"] = luxury
    breakdown["wealth_character"] = wealth_character

    if wealth is None and education is None and occupation is None:
        return None, breakdown

    total_w = 0.0
    score = 0.0
    if wealth is not None:
        total_w += W_WEALTH
        score += W_WEALTH * wealth
    total_w += W_HOME_COST
    score += W_HOME_COST * home_cost
    if education is not None:
        total_w += W_EDUCATION
        score += W_EDUCATION * education
    if occupation is not None:
        total_w += W_OCCUPATION
        score += W_OCCUPATION * occupation
    total_w += W_LUXURY
    score += W_LUXURY * luxury

    if total_w <= 0:
        return None, breakdown
    raw = score / total_w
    final = round(max(0.0, min(100.0, raw)), 1)
    return final, breakdown
