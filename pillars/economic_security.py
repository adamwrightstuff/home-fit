"""
Economic Security & Opportunity (profession-agnostic)

Core idea: How strong and resilient is the local economic ecosystem for a typical worker,
regardless of occupation?

This pillar is area-level (not person-level) and normalized within
(Census Division × area-type bucket) so rural economies aren't punished for being smaller.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, Any

from data_sources.data_quality import assess_pillar_data_quality
from data_sources.economic_security_data import (
    EconomicGeo,
    get_economic_geography,
    fetch_acs_profile_dp03,
    fetch_acs_table,
    fetch_bds_establishment_dynamics,
    compute_industry_hhi,
    compute_anchored_vs_cyclical_balance,
)
from data_sources.normalization import normalize_metric_to_0_100
from data_sources.us_census_divisions import get_division
from data_sources.job_category_overlays import (
    compute_job_category_overlays,
    parse_job_categories,
)


CURRENT_ACS_YEAR = 2022


def _area_bucket(area_type: Optional[str]) -> str:
    if not area_type:
        return "all"
    at = area_type.lower()
    if at in {"urban_core", "urban_residential", "historic_urban", "urban_core_lowrise"}:
        return "urban"
    if at in {"suburban", "exurban"}:
        return "suburban"
    if at == "rural":
        return "rural"
    return "all"


def _fallback_normalize(metric: str, value: Optional[float], *, invert: bool = False) -> Optional[float]:
    """
    Fallback normalization when baselines are missing.

    These are conservative nationwide heuristics; the baseline file is preferred.
    """
    if value is None:
        return None

    v = float(value)
    # Heuristic bands → 0..100
    thresholds = {
        # unemployment rate (percent)
        "unemployment_rate": (2.5, 4.0, 6.0, 8.0, 12.0),
        # employment-to-population ratio (percent)
        "emp_pop_ratio": (45.0, 52.0, 58.0, 63.0, 70.0),
        # 5y employment growth (percent)
        "employment_growth_5y": (-10.0, -2.0, 3.0, 8.0, 15.0),
        # industry HHI (0..1), lower better
        "industry_hhi": (0.07, 0.09, 0.12, 0.15, 0.20),
        # median earnings (dollars)
        "median_earnings": (28000, 38000, 48000, 60000, 80000),
        # 5y earnings growth (percent)
        "earnings_growth_5y": (-5.0, 0.0, 6.0, 12.0, 20.0),
        # net establishment entry per 1k residents
        "net_estab_entry_per_1k": (-2.0, -0.5, 0.5, 1.5, 3.0),
        # anchored-cyclical balance (-1..+1)
        "anchored_balance": (-0.15, -0.05, 0.0, 0.08, 0.18),
    }

    t = thresholds.get(metric)
    if not t:
        return None
    p05, p25, p50, p75, p95 = t

    # Piecewise-linear mapping
    def seg(x0: float, x1: float, y0: float, y1: float) -> float:
        if x1 == x0:
            return (y0 + y1) / 2.0
        return y0 + (y1 - y0) * ((v - x0) / (x1 - x0))

    if v <= p05:
        score = 0.0
    elif v <= p25:
        score = seg(p05, p25, 0.0, 25.0)
    elif v <= p50:
        score = seg(p25, p50, 25.0, 50.0)
    elif v <= p75:
        score = seg(p50, p75, 50.0, 75.0)
    elif v <= p95:
        score = seg(p75, p95, 75.0, 100.0)
    else:
        score = 100.0

    if invert:
        score = 100.0 - score
    return max(0.0, min(100.0, score))


def _normalize(
    *,
    metric: str,
    value: Optional[float],
    division: str,
    area_bucket: str,
    invert: bool = False,
) -> Optional[float]:
    score = normalize_metric_to_0_100(
        metric=metric,
        value=value,
        division=division,
        area_bucket=area_bucket,
        invert=invert,
    )
    if score is None:
        return _fallback_normalize(metric, value, invert=invert)
    return score


def _weighted_avg(scores: Dict[str, Optional[float]], weights: Dict[str, float]) -> Tuple[Optional[float], Dict[str, float]]:
    present = {k: v for k, v in scores.items() if isinstance(v, (int, float))}
    if not present:
        return None, {}
    total_w = sum(weights.get(k, 0.0) for k in present.keys())
    if total_w <= 0:
        total_w = float(len(present))
        renorm = {k: 1.0 / total_w for k in present.keys()}
    else:
        renorm = {k: weights.get(k, 0.0) / total_w for k in present.keys()}
    out = sum(float(present[k]) * renorm[k] for k in present.keys())
    return out, renorm


def get_economic_security_score(
    lat: float,
    lon: float,
    *,
    city: Optional[str] = None,
    state: Optional[str] = None,
    area_type: Optional[str] = None,
    census_tract: Optional[Dict[str, Any]] = None,
    job_categories: Optional[str] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute Economic Security & Opportunity score (0-100).
    """
    geo = get_economic_geography(lat, lon, tract=census_tract)

    division = get_division(state)
    bucket = _area_bucket(area_type)

    # If we can't resolve geography, return 0 with low confidence but consistent shape.
    if geo is None:
        combined_data = {"metrics_present": [], "raw": {}, "geo": None}
        dq = assess_pillar_data_quality("economic_security", combined_data, lat, lon, area_type or "suburban")
        return 0.0, {
            "score": 0.0,
            "breakdown": {},
            "summary": {"division": division, "area_bucket": bucket, "geo": None},
            "data_quality": dq,
            "area_classification": {"area_type": area_type},
        }

    effective_geo = geo
    year_now = CURRENT_ACS_YEAR

    dp03_vars = [
        "DP03_0001E",  # pop 16+
        "DP03_0004E",  # employed
        "DP03_0009PE",  # unemployment rate
        "DP03_0092E",  # median earnings for workers
        # industry shares
        "DP03_0033PE",
        "DP03_0034PE",
        "DP03_0035PE",
        "DP03_0036PE",
        "DP03_0037PE",
        "DP03_0038PE",
        "DP03_0039PE",
        "DP03_0040PE",
        "DP03_0041PE",
        "DP03_0042PE",
        "DP03_0043PE",
        "DP03_0044PE",
        "DP03_0045PE",
    ]

    dp03_now = fetch_acs_profile_dp03(year=year_now, geo=geo, variables=dp03_vars) or {}

    # Supplemental ACS tables
    rent_row = fetch_acs_table(year=year_now, geo=geo, variables=["B25064_001E"]) or {}
    pop_row = fetch_acs_table(year=year_now, geo=geo, variables=["B01001_001E"]) or {}

    # BDS establishment dynamics (latest aligned year)
    bds_row = fetch_bds_establishment_dynamics(year=year_now, geo=geo) or {}

    # If CBSA queries fail (some CBSA codes can yield empty/204 responses),
    # fall back to county-level data when possible.
    if geo.level == "cbsa" and geo.county_fips:
        needs_fallback = (not dp03_now) or (not rent_row) or (not pop_row)
        if needs_fallback:
            county_geo = EconomicGeo(
                level="county",
                name=None,
                state_fips=geo.state_fips,
                county_fips=geo.county_fips,
                cbsa_code=None,
            )
            effective_geo = county_geo
            if not dp03_now:
                dp03_now = fetch_acs_profile_dp03(year=year_now, geo=county_geo, variables=dp03_vars) or {}
            if not rent_row:
                rent_row = fetch_acs_table(year=year_now, geo=county_geo, variables=["B25064_001E"]) or {}
            if not pop_row:
                pop_row = fetch_acs_table(year=year_now, geo=county_geo, variables=["B01001_001E"]) or {}
            if not bds_row:
                bds_row = fetch_bds_establishment_dynamics(year=year_now, geo=county_geo) or {}

    pop16 = dp03_now.get("DP03_0001E")
    employed = dp03_now.get("DP03_0004E")
    unemp_rate = dp03_now.get("DP03_0009PE")
    earnings = dp03_now.get("DP03_0092E")

    median_rent_monthly = rent_row.get("B25064_001E")
    total_pop = pop_row.get("B01001_001E")

    emp_pop_ratio = None
    if isinstance(pop16, (int, float)) and pop16 > 0 and isinstance(employed, (int, float)):
        emp_pop_ratio = 100.0 * float(employed) / float(pop16)

    # Industry shares (broad)
    industry_shares = {
        "ag_mining": dp03_now.get("DP03_0033PE"),
        "construction": dp03_now.get("DP03_0034PE"),
        "manufacturing": dp03_now.get("DP03_0035PE"),
        "wholesale": dp03_now.get("DP03_0036PE"),
        "retail": dp03_now.get("DP03_0037PE"),
        "transport_util": dp03_now.get("DP03_0038PE"),
        "information": dp03_now.get("DP03_0039PE"),
        "finance_realestate": dp03_now.get("DP03_0040PE"),
        "prof_services": dp03_now.get("DP03_0041PE"),
        "educ_health": dp03_now.get("DP03_0042PE"),
        "leisure_hospitality": dp03_now.get("DP03_0043PE"),
        "other_services": dp03_now.get("DP03_0044PE"),
        "public_admin": dp03_now.get("DP03_0045PE"),
    }
    industry_hhi = compute_industry_hhi(industry_shares)
    anchored_balance = compute_anchored_vs_cyclical_balance(industry_shares)

    # Resilience: net establishment entry per capita (1k residents)
    net_estab_entry_per_1k = None
    if isinstance(total_pop, (int, float)) and total_pop > 0:
        entry = bds_row.get("ESTABS_ENTRY")
        exit_ = bds_row.get("ESTABS_EXIT")
        if isinstance(entry, (int, float)) and isinstance(exit_, (int, float)):
            net_estab_entry_per_1k = (float(entry) - float(exit_)) / float(total_pop) * 1000.0

    # Normalize to 0-100 submetric scores
    sub_scores = {
        # Lower unemployment is better → invert
        "unemployment_rate": _normalize(metric="unemployment_rate", value=unemp_rate, division=division, area_bucket=bucket, invert=True),
        "emp_pop_ratio": _normalize(metric="emp_pop_ratio", value=emp_pop_ratio, division=division, area_bucket=bucket),
        "net_estab_entry_per_1k": _normalize(metric="net_estab_entry_per_1k", value=net_estab_entry_per_1k, division=division, area_bucket=bucket),
        # Lower HHI is better (more diversified) → invert
        "industry_diversity": _normalize(metric="industry_hhi", value=industry_hhi, division=division, area_bucket=bucket, invert=True),
        "anchored_balance": _normalize(metric="anchored_balance", value=anchored_balance, division=division, area_bucket=bucket),
    }

    # 3-sub-index structure (job market, dynamism, resilience). Renormalize if missing.
    job_market_weights = {"unemployment_rate": 0.60, "emp_pop_ratio": 0.40}
    base_job_market_score, job_market_renorm = _weighted_avg(
        {k: sub_scores.get(k) for k in job_market_weights.keys()},
        job_market_weights,
    )

    dynamism_score = sub_scores.get("net_estab_entry_per_1k")

    resilience_weights = {"industry_diversity": 0.60, "anchored_balance": 0.40}
    resilience_score, resilience_renorm = _weighted_avg(
        {k: sub_scores.get(k) for k in resilience_weights.keys()},
        resilience_weights,
    )

    components = {
        "job_market_strength": base_job_market_score,
        "business_dynamism": dynamism_score,
        "resilience_and_diversification": resilience_score,
    }

    component_weights = {
        "job_market_strength": 0.54,
        "business_dynamism": 0.23,
        "resilience_and_diversification": 0.23,
    }

    base_final_score, base_component_renorm = _weighted_avg(components, component_weights)
    base_final_score = float(base_final_score or 0.0)

    selected = parse_job_categories(job_categories)
    overlays_payload: Optional[Dict[str, Any]] = None
    personalized_job_market: Optional[float] = None

    if selected:
        overlays_payload = compute_job_category_overlays(
            year=year_now,
            geo=effective_geo,
            division=division,
            area_bucket=bucket,
            base_job_market_strength=float(base_job_market_score or 0.0),
            median_gross_rent_monthly=median_rent_monthly if isinstance(median_rent_monthly, (int, float)) else None,
            overall_median_earnings=earnings if isinstance(earnings, (int, float)) else None,
            public_admin_share_pct=dp03_now.get("DP03_0045PE") if isinstance(dp03_now.get("DP03_0045PE"), (int, float)) else None,
        )
        overlays = (overlays_payload or {}).get("job_category_overlays", {}) or {}
        vals: List[float] = []
        for k in selected:
            v = (overlays.get(k, {}) or {}).get("final_job_market_score")
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if vals:
            personalized_job_market = sum(vals) / len(vals)

    # If personalized job-market is available, replace only that component and recompute pillar.
    if isinstance(personalized_job_market, (int, float)):
        components["job_market_strength"] = float(personalized_job_market)
        final_score, component_renorm = _weighted_avg(components, component_weights)
    else:
        final_score, component_renorm = base_final_score, base_component_renorm
    final_score = float(final_score or 0.0)

    metrics_present = [k for k, v in sub_scores.items() if isinstance(v, (int, float))]
    combined_data = {
        "metrics_present": metrics_present,
        "raw": {
            "unemployment_rate_pct": unemp_rate,
            "employment_to_population_pct": emp_pop_ratio,
            "industry_hhi": industry_hhi,
            "median_earnings": earnings,
            "median_gross_rent_monthly": median_rent_monthly,
            "net_estab_entry_per_1k": net_estab_entry_per_1k,
            "anchored_balance": anchored_balance,
        },
        "geo": {
            "level": effective_geo.level,
            "name": effective_geo.name,
            "state_fips": effective_geo.state_fips,
            "county_fips": effective_geo.county_fips,
            "cbsa_code": effective_geo.cbsa_code,
            "year": year_now,
        },
    }
    dq = assess_pillar_data_quality("economic_security", combined_data, lat, lon, area_type or "suburban")

    breakdown = {
        "job_market_strength": {
            "score": float(components["job_market_strength"] or 0.0),
            "weights": job_market_renorm,
            "metrics": {k: sub_scores.get(k) for k in job_market_weights.keys()},
        },
        "business_dynamism": {
            "score": dynamism_score,
            "weights": {"net_estab_entry_per_1k": 1.0} if isinstance(dynamism_score, (int, float)) else {},
            "metrics": {"net_estab_entry_per_1k": sub_scores.get("net_estab_entry_per_1k")},
        },
        "resilience_and_diversification": {
            "score": resilience_score,
            "weights": resilience_renorm,
            "metrics": {k: sub_scores.get(k) for k in resilience_weights.keys()},
        },
        "component_weights": component_renorm,
    }

    if overlays_payload:
        breakdown.update(overlays_payload)

    summary = {
        "division": division,
        "area_bucket": bucket,
        "geo_level": effective_geo.level,
        "geo_name": effective_geo.name,
        "unemployment_rate_pct": round(float(unemp_rate), 1) if isinstance(unemp_rate, (int, float)) else None,
        "employment_to_population_pct": round(float(emp_pop_ratio), 1) if isinstance(emp_pop_ratio, (int, float)) else None,
        "median_earnings": int(earnings) if isinstance(earnings, (int, float)) else None,
        "median_gross_rent_monthly": int(median_rent_monthly) if isinstance(median_rent_monthly, (int, float)) else None,
        "net_estab_entry_per_1k": round(float(net_estab_entry_per_1k), 2) if isinstance(net_estab_entry_per_1k, (int, float)) else None,
        "industry_diversity_hhi": round(float(industry_hhi), 4) if isinstance(industry_hhi, (int, float)) else None,
        "anchored_balance": round(float(anchored_balance), 3) if isinstance(anchored_balance, (int, float)) else None,
    }

    return round(final_score, 1), {
        "score": round(final_score, 1),
        "base_score": round(base_final_score, 1),
        "selected_job_categories": selected,
        "breakdown": breakdown,
        "summary": summary,
        "data_quality": dq,
        "area_classification": {"area_type": area_type},
    }

