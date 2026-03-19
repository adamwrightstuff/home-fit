"""
Status Signal: post-pillars derived score (status + desirability).

Status = wealth + education + occupation. Desirability = home cost + luxury presence.
Uses per-division and per-CBSA min-max baselines from data/status_signal_baselines.json.
For each component we try baseline keys in order: CBSA (e.g. nyc_metro) when in a metro cluster, then Census division, then "all". If a key has no data for that component, we fall back to the next (so metro-only baselines still get division/all for education/occupation).

Weights: wealth 35%, home_cost 25%, education 20%, occupation 10%, luxury_presence 5%.
Luxury presence: dedicated OSM Overpass query (offices, recreation, arts, specialist healthcare, luxury retail);
healthcare bucket omitted and weight redistributed when fewer than 3 matching POIs. Falls back to name-based
brand matching when coordinates or OSM query are unavailable.
Wealth gap (mean vs median) is used as a quality-control label: super_zip vs unequal vs typical.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# High-barrier services for Status Signal luxury presence.
# business_list is expected to come from OSM / POI aggregation; we use simple
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


# Status Signature: archetype classifier (Patrician first so legacy beats retail e.g. Upper East Side)
def _get_archetype(
    education: Optional[float],
    wealth: Optional[float],
    home_cost: float,
    wealth_character: str,
    luxury_detail: Optional[Dict[str, Any]],
    luxury_score: float,
) -> str:
    """
    Classify into Patrician (Aspen/Bronxville), Parvenu (Tribeca/Star Island), Poseur (West Hollywood/Carroll Gardens), or Typical.
    Patrician is checked first so neighborhoods with both high education and high luxury retail (e.g. Upper East Side) get legacy status.
    """
    counts = (luxury_detail or {}).get("counts") or {}
    private_recreation = int(counts.get("private_recreation") or 0)
    luxury_retail = int(counts.get("luxury_retail") or 0)
    specialist_healthcare = int(counts.get("specialist_healthcare") or 0)

    # 1. Patrician first: super_zip + high education + legacy recreation (golf/tennis/yacht)
    if (
        wealth_character == "super_zip"
        and education is not None
        and education > 80
        and private_recreation > 0
    ):
        return "Patrician"

    # 2. Parvenu: unequal + high luxury retail + high med-spas
    if (
        wealth_character == "unequal"
        and luxury_retail > 3
        and specialist_healthcare >= 3
    ):
        return "Parvenu"

    # 3. Poseur: high home cost, stretched wealth, high luxury presence (arts/galleries/boutiques)
    wealth_val = wealth if wealth is not None else 0.0
    if home_cost > 80 and wealth_val < 65 and luxury_score > 60:
        return "Poseur"

    return "Typical"


def _get_archetype_weights(archetype: str) -> Tuple[float, float, float, float, float]:
    """Weights (wealth, home_cost, education, occupation, luxury) for archetype. Sum = 1."""
    if archetype == "Patrician":
        # Bronxville/Old Greenwich: JDs/MDs over Rolex stores
        return (0.177, 0.30, 0.45, 0.053, 0.02)
    if archetype == "Parvenu":
        # Tribeca/Star Island: financial horsepower + high-end services
        return (0.45, 0.182, 0.145, 0.073, 0.15)
    # Poseur, Typical: default
    return (W_WEALTH, W_HOME_COST, W_EDUCATION, W_OCCUPATION, W_LUXURY)


def _get_status_label(archetype: str) -> str:
    """UI badge label for archetype."""
    return {
        "Patrician": "Legacy Establishment",
        "Parvenu": "High-Velocity Wealth",
        "Poseur": "Lifestyle Premium",
        "Typical": "Typical",
    }.get(archetype, "Typical")


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


def _luxury_count_to_score(
    count: int,
    baselines: Dict[str, Any],
    keys_to_try: List[str],
    metric: str,
) -> float:
    mn, mx = _get_baseline(baselines, keys_to_try, "luxury", metric)
    if mn is None or mx is None:
        return min(100.0, float(max(0, count)) * 6.0)
    return _normalize_min_max(float(max(0, count)), mn, mx)


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
        return 0.0, {"source": "osm", "error": "import_failed"}

    raw = query_status_signal_luxury_osm(lat, lon, radius_m=radius_m)
    detail: Dict[str, Any] = {"source": "osm", "radius_m": radius_m}
    if not raw or not raw.get("counts"):
        detail["error"] = "no_osm_result"
        return 0.0, detail

    c = raw["counts"]
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
        score = (
            w[0] * s_wealth + w[1] * s_priv + w[2] * s_arts + w[3] * s_hc + w[4] * s_ret
        )
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


def compute_wealth(
    housing_details: Dict[str, Any],
    keys_to_try: List[str],
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

    min_mean, max_mean = _get_baseline(baselines, keys_to_try, "wealth", "mean_hh_income")
    min_gap, max_gap = _get_baseline(baselines, keys_to_try, "wealth", "wealth_gap_ratio")
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
    """Education Density: 65% grad_pct + 15% bach_pct + 20% self_employed_pct (all normalized). Uses 0-100 scale."""
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

    min_grad, max_grad = _get_baseline(baselines, keys_to_try, "education", "grad_pct")
    min_bach, max_bach = _get_baseline(baselines, keys_to_try, "education", "bach_pct")
    min_se, max_se = _get_baseline(baselines, keys_to_try, "education", "self_employed_pct")

    n_grad = 50.0
    if grad_pct is not None and min_grad is not None and max_grad is not None:
        n_grad = _normalize_min_max(grad_pct, min_grad, max_grad)
    n_bach = 50.0
    if bach_pct is not None and min_bach is not None and max_bach is not None:
        n_bach = _normalize_min_max(bach_pct, min_bach, max_bach)
    n_se = 50.0
    if self_employed_pct is not None and min_se is not None and max_se is not None:
        n_se = _normalize_min_max(float(self_employed_pct), min_se, max_se)
    return 0.65 * n_grad + 0.15 * n_bach + 0.20 * n_se


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
    keys_to_try: List[str],
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

    min_fa, max_fa = _get_baseline(baselines, keys_to_try, "occupation", "finance_arts_pct")
    min_wc, max_wc = _get_baseline(baselines, keys_to_try, "occupation", "white_collar_pct")
    min_se, max_se = _get_baseline(baselines, keys_to_try, "occupation", "self_employed_pct")

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
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    luxury_radius_m: int = 1500,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Returns (score, breakdown) with components 0-100, wealth_character, archetype, status_label.
    Breakdown: wealth, home_cost, education, occupation, luxury_presence, wealth_character,
    archetype (Patrician|Parvenu|Poseur|Typical), status_label (UI badge e.g. Legacy Establishment).
    Weights vary by archetype (Patrician: education/home_cost; Parvenu: wealth/luxury). Patrician checked before Parvenu.
    When city is provided, uses CBSA baseline (e.g. nyc_metro) if the location is in a known cluster and
    that key exists in baselines; otherwise uses Census division, then "all".
    """
    breakdown: Dict[str, Any] = {
        "wealth": None,
        "home_cost": None,
        "education": None,
        "occupation": None,
        "luxury_presence": None,
        "luxury_presence_detail": None,
        "wealth_character": "typical",
        "archetype": "Typical",
        "status_label": "Typical",
    }
    if not housing_details or not social_fabric_details or not economic_security_details:
        return None, breakdown
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"
    baselines = _load_baselines()
    if not baselines:
        keys_to_try = [division, "all"]
    else:
        # Try CBSA first when in a metro cluster, then division, then "all"
        cbsa_key = _get_cbsa_baseline_key(city, state_abbrev)
        baseline_key = cbsa_key if (cbsa_key and baselines.get(cbsa_key)) else division
        keys_to_try = [baseline_key]
        if division not in keys_to_try:
            keys_to_try.append(division)
        if "all" not in keys_to_try:
            keys_to_try.append("all")

    wealth = compute_wealth(housing_details, keys_to_try, baselines)
    summary = housing_details.get("summary") or housing_details
    median_home = summary.get("median_home_value")
    home_cost = compute_home_cost(median_home, keys_to_try, baselines)
    education = compute_education(social_fabric_details, keys_to_try, baselines)
    occupation = compute_occupation(
        economic_security_details, social_fabric_details, tract, keys_to_try, baselines
    )
    luxury_detail: Optional[Dict[str, Any]] = None
    if (
        lat is not None
        and lon is not None
        and isinstance(lat, (int, float))
        and isinstance(lon, (int, float))
        and math.isfinite(float(lat))
        and math.isfinite(float(lon))
    ):
        luxury, luxury_detail = compute_luxury_presence_osm(
            float(lat), float(lon), keys_to_try, baselines, radius_m=luxury_radius_m
        )
        if luxury_detail.get("error") in ("no_osm_result", "import_failed"):
            luxury = compute_brand(business_list or [], keys_to_try, baselines)
            luxury_detail = {
                "source": "brand_fallback",
                "reason": luxury_detail.get("error") or "osm_unavailable",
            }
    else:
        luxury = compute_brand(business_list or [], keys_to_try, baselines)
        luxury_detail = {"source": "brand_fallback", "reason": "no_coordinates"}

    wealth_character = _wealth_character(housing_details)

    # Status Signature: archetype (Patrician first) + dynamic weights + UI label
    archetype = _get_archetype(
        education, wealth, home_cost, wealth_character, luxury_detail, luxury
    )
    w_wealth, w_home_cost, w_education, w_occupation, w_luxury = _get_archetype_weights(archetype)
    status_label = _get_status_label(archetype)

    breakdown["wealth"] = wealth
    breakdown["home_cost"] = home_cost
    breakdown["education"] = education
    breakdown["occupation"] = occupation
    breakdown["luxury_presence"] = luxury
    breakdown["luxury_presence_detail"] = luxury_detail
    breakdown["wealth_character"] = wealth_character
    breakdown["archetype"] = archetype
    breakdown["status_label"] = status_label

    if wealth is None and education is None and occupation is None:
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
    if occupation is not None:
        total_w += w_occupation
        score += w_occupation * occupation
    total_w += w_luxury
    score += w_luxury * luxury

    if total_w <= 0:
        return None, breakdown
    raw = score / total_w
    final = round(max(0.0, min(100.0, raw)), 1)
    return final, breakdown
