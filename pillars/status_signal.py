"""
Status Signal: Universal Logic Engine (status + desirability).

Data-driven principles (no location-specific tuning):
- Credential-First Education: 80% graduate/professional, 20% bachelors (no self-employed).
- Authority-First Occupation: S2401 Management/Business/Science/Arts concentration, CBSA-normalized.
- Multi-Modal Wealth: Elite Uniformity (median > 2x CBSA median, low gap) or Elite Outlier (median near CBSA, high gap).
- CBSA Mapping: Baselines selected by tract CBSA code only (Palo Alto vs San Jose, Bronxville vs NYC).

Baselines from data/status_signal_baselines.json; keys_to_try = CBSA key first (from cbsa_to_baseline), then division, then "all".
Luxury: OSM Overpass query; fallback to brand matching when unavailable.
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


# Status Signature: archetype classifier. Density/vibe fix: Patrician/Poseur from raw stats first.
def _get_archetype(
    education: Optional[float],
    wealth: Optional[float],
    home_cost: float,
    luxury_detail: Optional[Dict[str, Any]],
    luxury_score: float,
    median_income: Optional[float] = None,
    wealth_gap: Optional[float] = None,
    grad_pct: Optional[float] = None,
    white_collar_mgmt: Optional[float] = None,
    self_employed_pct: Optional[float] = None,
) -> str:
    """
    Classify into Patrician, Parvenu, Poseur, Plebeian, or Typical.
    Classification flip: grad_pct + white_collar -> Patrician (Bronxville); self_employed + home_value -> Poseur (Carroll Gardens).
    """
    counts = (luxury_detail or {}).get("counts") or {}
    luxury_retail = int(counts.get("luxury_retail") or 0)
    wealth_val = wealth if wealth is not None else 0.0
    edu_val = education if education is not None else 0.0

    # 1. Patrician (Bronxville fix): raw grad_pct > 80% and white_collar_mgmt > 70%
    if (
        grad_pct is not None
        and float(grad_pct) > 80.0
        and white_collar_mgmt is not None
        and float(white_collar_mgmt) > 70.0
    ):
        return "Patrician"

    # 2. Poseur (Carroll Gardens normalizer): self_employed > 25% and home_value_score > 90
    if (
        self_employed_pct is not None
        and float(self_employed_pct) > 25.0
        and home_cost > 90
    ):
        return "Poseur"

    # 3. Patrician (legacy): median > 200k, low gap, education > 60 (normalization can be harsh; 60 = strong)
    if (
        median_income is not None
        and median_income > 200_000
        and wealth_gap is not None
        and wealth_gap < 0.30
        and education is not None
        and education > 60
    ):
        return "Patrician"

    # 4. Parvenu: requires high wealth gap (wealthy+uniform cannot be Parvenu)
    if wealth_gap is not None and wealth_gap > 0.50:
        return "Parvenu"
    if wealth_gap is not None and wealth_gap > 0.40 and wealth_val > 85 and luxury_retail > 3:
        return "Parvenu"

    # 5. Poseur: high home cost, lower wealth
    if home_cost > 80 and wealth_val < 65:
        return "Poseur"

    # 6. Plebeian: low across wealth, education, home cost
    if wealth_val < 40 and edu_val < 40 and home_cost < 40:
        return "Plebeian"

    return "Typical"


def _get_archetype_weights(archetype: str) -> Tuple[float, float, float, float, float]:
    """Weights (wealth, home_cost, education, occupation, luxury) for archetype. Sum = 1."""
    if archetype == "Patrician":
        # Patrician lens: W_EDUCATION=0.50, W_OCCUPATION=0.30 (Bronxville fix)
        return (0.10, 0.08, 0.50, 0.30, 0.02)
    if archetype == "Parvenu":
        # Parvenu lens: W_INCOME_VELOCITY=0.50 (Tribeca fix)
        return (0.50, 0.15, 0.10, 0.10, 0.15)
    if archetype == "Poseur":
        # Poseur lens: W_WEALTH=0.40 (Carroll Gardens normalizer; income-to-home penalty applied separately)
        return (0.40, 0.15, 0.15, 0.05, 0.25)
    return (W_WEALTH, W_HOME_COST, W_EDUCATION, W_OCCUPATION, W_LUXURY)


def _get_status_label(archetype: str) -> str:
    """UI badge label for archetype."""
    return {
        "Patrician": "Legacy Establishment",
        "Parvenu": "High-Velocity Wealth",
        "Poseur": "Lifestyle Premium",
        "Plebeian": "Traditional Community",
        "Typical": "Typical",
    }.get(archetype, "Typical")


def _get_status_insight(archetype: str) -> str:
    """One-sentence tooltip 'why' for the UI."""
    return {
        "Patrician": "High-floor exclusivity driven by educational pedigree and stable assets.",
        "Parvenu": "Elite status driven by extreme income outliers and luxury consumption.",
        "Poseur": "Aspirational status driven by brand-name zip code and cultural amenities.",
        "Plebeian": "Functional profile with no dominant elite signatures.",
        "Typical": "Standard socio-economic profile with no dominant elite signatures.",
    }.get(archetype, "Standard socio-economic profile with no dominant elite signatures.")


_DRIVER_LABELS: Dict[str, str] = {
    "wealth": "Asset Stability",
    "home_cost": "Home Value",
    "education": "Education",
    "occupation": "Occupation Mix",
    "luxury_presence": "Luxury Presence",
}

_DRIVER_LABELS_PARVENU: Dict[str, str] = {
    "wealth": "Income Velocity",
    "luxury_presence": "Luxury Retail",
}


def _build_top_drivers(
    wealth: Optional[float],
    home_cost: float,
    education: Optional[float],
    occupation: Optional[float],
    luxury: float,
    archetype: str,
) -> List[Dict[str, Any]]:
    """Top 3 components by score for tooltip; labels vary by archetype."""
    labels = dict(_DRIVER_LABELS)
    if archetype == "Parvenu":
        labels.update(_DRIVER_LABELS_PARVENU)
    items: List[Tuple[str, float]] = []
    if wealth is not None:
        items.append(("wealth", round(wealth, 1)))
    items.append(("home_cost", round(home_cost, 1)))
    if education is not None:
        items.append(("education", round(education, 1)))
    if occupation is not None:
        items.append(("occupation", round(occupation, 1)))
    items.append(("luxury_presence", round(luxury, 1)))
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
    """
    Occupation. Authority-First default: S2401 Management/Business/Science/Arts (white_collar_pct) normalized against CBSA.
    When archetype is set: Patrician 80% Mgmt/Legal/Health + 20% Finance; Parvenu 50% Finance + 30% Self-Employed + 20% Mgmt; Poseur 60% Arts + 40% Self-Employed.
    """
    industry = economic_security_details.get("industry_shares_pct") or {}
    fr = industry.get("finance_realestate")
    lh = industry.get("leisure_hospitality")
    finance_pct = float(fr) if fr is not None and isinstance(fr, (int, float)) else None
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
    management_legal_healthcare_pct: Optional[float] = None
    if archetype == "Patrician" and tract:
        s2401 = _fetch_s2401_occupation_shares(tract)
        management_legal_healthcare_pct = (s2401 or {}).get("management_legal_healthcare_pct")

    self_employed_pct = social_fabric_details.get("self_employed_pct")
    arts_pct = float(lh) if lh is not None and isinstance(lh, (int, float)) else None

    min_fa, max_fa = _get_baseline(baselines, keys_to_try, "occupation", "finance_arts_pct")
    min_wc, max_wc = _get_baseline(baselines, keys_to_try, "occupation", "white_collar_pct")
    min_se, max_se = _get_baseline(baselines, keys_to_try, "occupation", "self_employed_pct")
    min_mlh, max_mlh = _get_baseline(baselines, keys_to_try, "occupation", "management_legal_healthcare_pct")
    if min_mlh is None:
        min_mlh, max_mlh = min_wc, max_wc

    def _n(val: Optional[float], mn: Optional[float], mx: Optional[float], default: float = 50.0) -> float:
        if val is None or mn is None or mx is None:
            return default
        return _normalize_min_max(val, mn, mx)

    # Patrician: 80% Management/Legal/Healthcare (S2401), 20% Finance, 0% self-employed
    if archetype == "Patrician":
        if management_legal_healthcare_pct is None and finance_pct is None:
            return None
        n_mlh = _n(management_legal_healthcare_pct, min_mlh, max_mlh)
        n_fin = _n(finance_pct, min_fa, max_fa) if finance_pct is not None else 50.0
        return 0.8 * n_mlh + 0.2 * n_fin

    # Parvenu: 50% Finance, 30% Self-Employed, 20% Management (white_collar)
    if archetype == "Parvenu":
        if finance_pct is None and white_collar_pct is None and self_employed_pct is None:
            return None
        n_fin = _n(finance_pct, min_fa, max_fa)
        n_se = _n(float(self_employed_pct) if self_employed_pct is not None else None, min_se, max_se)
        n_wc = _n(white_collar_pct, min_wc, max_wc)
        return 0.50 * n_fin + 0.30 * n_se + 0.20 * n_wc

    # Poseur: 60% Arts/Entertainment/Media, 40% Self-Employed
    if archetype == "Poseur":
        if arts_pct is None and self_employed_pct is None:
            return None
        n_arts = _n(arts_pct, min_fa, max_fa)
        n_se = _n(float(self_employed_pct) if self_employed_pct is not None else None, min_se, max_se)
        return 0.60 * n_arts + 0.40 * n_se

    # Universal default: Authority-First Occupation = S2401 Management/Business/Science/Arts (white_collar) normalized against CBSA
    if white_collar_pct is None:
        return None
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
    Baselines: tract CBSA (from get_census_tract) is mapped via cbsa_to_baseline in baselines JSON (e.g. 35620->nyc_metro);
    if no CBSA match, falls back to division then "all" (national).
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
        "status_insight": "",
        "top_drivers": [],
        "analysis_radius_note": None,
    }
    if not housing_details or not social_fabric_details or not economic_security_details:
        return None, breakdown
    from data_sources.us_census_divisions import get_division
    division = get_division(state_abbrev) if state_abbrev else "all"
    baselines = _load_baselines()
    if not baselines:
        keys_to_try = [division, "all"]
    else:
        # Geo-targeted: tract CBSA (from get_census_tract) -> baseline key via cbsa_to_baseline; else city fallback; else national
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
    education = compute_education(social_fabric_details, keys_to_try, baselines)
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
    median_income: Optional[float] = None
    wealth_gap: Optional[float] = None
    med = summary.get("median_household_income")
    mean = summary.get("mean_household_income")
    if med is not None and isinstance(med, (int, float)) and med > 0:
        median_income = float(med)
        if mean is not None and isinstance(mean, (int, float)):
            wealth_gap = (float(mean) - float(med)) / float(med)

    # Raw stats for classification flip (grad_pct + white_collar -> Patrician; self_employed + home -> Poseur)
    edu_attainment = social_fabric_details.get("education_attainment") or {}
    grad_pct_raw = edu_attainment.get("grad_pct")
    if grad_pct_raw is not None:
        grad_pct_raw = float(grad_pct_raw)
    self_employed_pct_raw = social_fabric_details.get("self_employed_pct")
    if self_employed_pct_raw is not None:
        self_employed_pct_raw = float(self_employed_pct_raw)
    white_collar_mgmt: Optional[float] = (economic_security_details.get("breakdown") or {}).get("white_collar_pct")
    if white_collar_mgmt is None and tract:
        white_collar_mgmt = _fetch_white_collar_pct_tract(tract)
    if white_collar_mgmt is not None:
        white_collar_mgmt = float(white_collar_mgmt)

    # Wealth-based Patrician trigger (priority): Elite Uniformity at regional scale
    cbsa_median = _get_cbsa_median_income(baselines, keys_to_try)
    if (
        cbsa_median is not None
        and cbsa_median > 0
        and median_income is not None
        and float(median_income) > 2.0 * cbsa_median
        and wealth_gap is not None
        and wealth_gap < 0.25
    ):
        archetype = "Patrician"
    elif (
        median_income is not None
        and float(median_income) > 200_000
        and wealth_gap is not None
        and wealth_gap < 0.25
    ):
        # Fallback when no CBSA median: absolute threshold (wealthy + uniform -> Patrician)
        archetype = "Patrician"
    else:
        archetype = _get_archetype(
            education, wealth, home_cost, luxury_detail, luxury,
            median_income=median_income, wealth_gap=wealth_gap,
            grad_pct=grad_pct_raw, white_collar_mgmt=white_collar_mgmt, self_employed_pct=self_employed_pct_raw,
        )
    occupation = compute_occupation(
        economic_security_details, social_fabric_details, tract, keys_to_try, baselines,
        archetype=archetype,
    )
    # Patrician: re-run luxury at 4km to capture estates/country clubs
    analysis_radius_note: Optional[str] = None
    if archetype == "Patrician" and lat is not None and lon is not None and isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and math.isfinite(float(lat)) and math.isfinite(float(lon)):
        luxury, luxury_detail = compute_luxury_presence_osm(
            float(lat), float(lon), keys_to_try, baselines, radius_m=4000
        )
        analysis_radius_note = "Analyzed within a 4km estate radius."

    w_wealth, w_home_cost, w_education, w_occupation, w_luxury = _get_archetype_weights(archetype)
    status_label = _get_status_label(archetype)
    status_insight = _get_status_insight(archetype)
    top_drivers = _build_top_drivers(wealth, home_cost, education, occupation, luxury, archetype)

    breakdown["wealth"] = wealth
    breakdown["home_cost"] = home_cost
    breakdown["education"] = education
    breakdown["occupation"] = occupation
    breakdown["luxury_presence"] = luxury
    breakdown["luxury_presence_detail"] = luxury_detail
    breakdown["wealth_character"] = wealth_character
    breakdown["archetype"] = archetype
    breakdown["status_label"] = status_label
    breakdown["status_insight"] = status_insight
    breakdown["top_drivers"] = top_drivers
    breakdown["analysis_radius_note"] = analysis_radius_note

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
    # Poseur lens: penalize weak income-to-home-value ratio (high debt/high vibe -> cap ~78)
    if archetype == "Poseur" and median_income is not None and median_home is not None and isinstance(median_home, (int, float)) and float(median_home) > 0:
        income_to_home = float(median_income) / float(median_home)
        if income_to_home < 0.12:
            final = min(final, 78.0)
    return final, breakdown
