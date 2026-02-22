"""
Economic Security & Opportunity (Career Ecosystem)

Score: S = w1·D + w2·M + w3·E + w4·R (0–100)

Pillar weights: Density 0.40, Mobility 0.15, Ecosystem 0.20, Resilience 0.25 (capacity and
stability over velocity).

- D = Density: volume and depth — employment ratio, scale (log10 jobs + estabs), estabs/1k, wage floor. Rewards market size.
- M = Mobility: upward trajectory — job growth, establishment churn, wage upside. Growth sub-score has a floor (40) when anchor is high.
- E = Ecosystem: industry diversity and establishment density.
- R = Resilience: industry diversification and anchored vs cyclical balance.

All inputs from free public APIs (Census ACS/BDS, BLS QCEW/OEWS). Normalized within
(Census Division × area-type bucket). Scale metrics use log10(employment+1) and log10(establishments+1).
"""

from __future__ import annotations

import math
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
from data_sources import bls_data
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
        # total establishments per 1k residents (scale/depth)
        "estabs_per_1k": (15.0, 25.0, 35.0, 50.0, 75.0),
        # anchored-cyclical balance (-1..+1)
        "anchored_balance": (-0.15, -0.05, 0.0, 0.08, 0.18),
        # OEWS wage distribution (annual $)
        "wage_p25_annual": (22000, 32000, 42000, 55000, 75000),
        "wage_p75_annual": (45000, 65000, 90000, 120000, 180000),
        # QCEW demand-side
        "qcew_employment_per_1k": (200, 350, 500, 700, 1000),
        "qcew_employment_growth_pct": (-3.0, 0.0, 2.0, 4.0, 8.0),
        # Scale (log10 of absolute counts): employment ~10k–2M, estabs ~300–30k
        "log10_employment": (4.0, 4.5, 5.0, 5.5, 6.3),
        "log10_establishments": (2.5, 3.0, 3.5, 4.0, 4.5),
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

    # Supplemental ACS table (population for BDS per-capita)
    pop_row = fetch_acs_table(year=year_now, geo=geo, variables=["B01001_001E"]) or {}

    # BDS establishment dynamics (latest aligned year)
    bds_row = fetch_bds_establishment_dynamics(year=year_now, geo=geo) or {}

    # If CBSA queries fail (some CBSA codes can yield empty/204 responses),
    # fall back to county-level data when possible.
    if geo.level == "cbsa" and geo.county_fips:
        needs_fallback = (not dp03_now) or (not pop_row)
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
            if not pop_row:
                pop_row = fetch_acs_table(year=year_now, geo=county_geo, variables=["B01001_001E"]) or {}
            if not bds_row:
                bds_row = fetch_bds_establishment_dynamics(year=year_now, geo=county_geo) or {}

    pop16 = dp03_now.get("DP03_0001E")
    employed = dp03_now.get("DP03_0004E")
    unemp_rate = dp03_now.get("DP03_0009PE")
    earnings = dp03_now.get("DP03_0092E")

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

    # Business dynamism: net establishment entry and establishment density (per 1k residents)
    net_estab_entry_per_1k = None
    estabs_per_1k = None
    total_establishments = None
    if isinstance(total_pop, (int, float)) and total_pop > 0:
        entry = bds_row.get("ESTABS_ENTRY")
        exit_ = bds_row.get("ESTABS_EXIT")
        if isinstance(entry, (int, float)) and isinstance(exit_, (int, float)):
            net_estab_entry_per_1k = (float(entry) - float(exit_)) / float(total_pop) * 1000.0
        total_estab = bds_row.get("ESTAB")
        if isinstance(total_estab, (int, float)) and float(total_estab) >= 0:
            total_establishments = float(total_estab)
            estabs_per_1k = total_establishments / float(total_pop) * 1000.0

    # BLS QCEW: employment level and YoY growth (demand-side)
    qcew_employment_per_1k = None
    qcew_employment_growth_pct = None
    total_employment = None
    if effective_geo.level == "cbsa" and effective_geo.cbsa_code:
        qcew_area = bls_data.cbsa_to_qcew_area_code(effective_geo.cbsa_code)
    elif effective_geo.county_fips and effective_geo.state_fips:
        qcew_area = bls_data.county_to_qcew_area_code(effective_geo.state_fips, effective_geo.county_fips)
    else:
        qcew_area = ""
    if qcew_area:
        qcew_row = bls_data.fetch_qcew_annual_for_area(qcew_area, year=CURRENT_ACS_YEAR)
        if qcew_row and isinstance(total_pop, (int, float)) and total_pop > 0:
            empl = qcew_row.get("annual_avg_emplvl")
            if isinstance(empl, (int, float)) and empl >= 0:
                total_employment = float(empl)
                qcew_employment_per_1k = total_employment / float(total_pop) * 1000.0
            pct = qcew_row.get("oty_annual_avg_emplvl_pct_chg")
            if isinstance(pct, (int, float)):
                qcew_employment_growth_pct = float(pct)

    # BLS OEWS: 25th and 75th percentile wages by metro (wage distribution)
    wage_p25_annual = None
    wage_p75_annual = None
    oews_area = effective_geo.cbsa_code if effective_geo.level == "cbsa" else None
    if not oews_area and effective_geo.state_fips and effective_geo.county_fips:
        oews_area = effective_geo.state_fips + effective_geo.county_fips
    if oews_area:
        oews_row = bls_data.get_oews_wage_distribution(oews_area)
        if oews_row:
            wage_p25_annual = oews_row.get("wage_p25_annual")
            wage_p75_annual = oews_row.get("wage_p75_annual")
            if wage_p25_annual is not None:
                wage_p25_annual = float(wage_p25_annual)
            if wage_p75_annual is not None:
                wage_p75_annual = float(wage_p75_annual)

    # Scale: log10 of absolute counts (reward market depth, not just per-capita)
    log10_employment = math.log10(total_employment + 1) if isinstance(total_employment, (int, float)) and total_employment >= 0 else None
    log10_establishments = math.log10(total_establishments + 1) if isinstance(total_establishments, (int, float)) and total_establishments >= 0 else None

    # Normalize to 0-100 submetric scores
    sub_scores = {
        # Lower unemployment is better → invert
        "unemployment_rate": _normalize(metric="unemployment_rate", value=unemp_rate, division=division, area_bucket=bucket, invert=True),
        "emp_pop_ratio": _normalize(metric="emp_pop_ratio", value=emp_pop_ratio, division=division, area_bucket=bucket),
        "net_estab_entry_per_1k": _normalize(metric="net_estab_entry_per_1k", value=net_estab_entry_per_1k, division=division, area_bucket=bucket),
        "estabs_per_1k": _normalize(metric="estabs_per_1k", value=estabs_per_1k, division=division, area_bucket=bucket),
        # Wage distribution (OEWS 25th/75th)
        "wage_p25_annual": _normalize(metric="wage_p25_annual", value=wage_p25_annual, division=division, area_bucket=bucket),
        "wage_p75_annual": _normalize(metric="wage_p75_annual", value=wage_p75_annual, division=division, area_bucket=bucket),
        # Demand-side (QCEW)
        "qcew_employment_per_1k": _normalize(metric="qcew_employment_per_1k", value=qcew_employment_per_1k, division=division, area_bucket=bucket),
        "qcew_employment_growth_pct": _normalize(metric="qcew_employment_growth_pct", value=qcew_employment_growth_pct, division=division, area_bucket=bucket),
        # Scale (log10 absolute counts)
        "log10_employment": _normalize(metric="log10_employment", value=log10_employment, division=division, area_bucket=bucket),
        "log10_establishments": _normalize(metric="log10_establishments", value=log10_establishments, division=division, area_bucket=bucket),
        # Lower HHI is better (more diversified) → invert
        "industry_diversity": _normalize(metric="industry_hhi", value=industry_hhi, division=division, area_bucket=bucket, invert=True),
        "anchored_balance": _normalize(metric="anchored_balance", value=anchored_balance, division=division, area_bucket=bucket),
    }

    # Scale score: average of normalized log10 employment and establishments (rewards market depth)
    scale_vals = [sub_scores.get("log10_employment"), sub_scores.get("log10_establishments")]
    scale_vals = [v for v in scale_vals if isinstance(v, (int, float))]
    if scale_vals:
        sub_scores["scale"] = sum(scale_vals) / len(scale_vals)

    # Anchor floor: high-anchor markets (gov/health/edu) don't get crushed by low growth
    if sub_scores.get("anchored_balance") is not None and sub_scores["anchored_balance"] > 75:
        growth = sub_scores.get("qcew_employment_growth_pct")
        if growth is not None:
            sub_scores["qcew_employment_growth_pct"] = max(float(growth), 40.0)

    # Career ecosystem: S = w1·D + w2·M + w3·E + w4·R
    density_weights = {"emp_pop_ratio": 0.25, "scale": 0.30, "estabs_per_1k": 0.25, "wage_p25_annual": 0.20}
    density_score, density_renorm = _weighted_avg(
        {k: sub_scores.get(k) for k in density_weights.keys()},
        density_weights,
    )

    mobility_weights = {"qcew_employment_growth_pct": 0.40, "net_estab_entry_per_1k": 0.35, "wage_p75_annual": 0.25}
    mobility_score, mobility_renorm = _weighted_avg(
        {k: sub_scores.get(k) for k in mobility_weights.keys()},
        mobility_weights,
    )

    ecosystem_weights = {"industry_diversity": 0.70, "estabs_per_1k": 0.30}
    ecosystem_score, ecosystem_renorm = _weighted_avg(
        {k: sub_scores.get(k) for k in ecosystem_weights.keys()},
        ecosystem_weights,
    )

    resilience_weights = {"industry_diversity": 0.60, "anchored_balance": 0.40}
    resilience_score, resilience_renorm = _weighted_avg(
        {k: sub_scores.get(k) for k in resilience_weights.keys()},
        resilience_weights,
    )

    components = {
        "density": density_score,
        "mobility": mobility_score,
        "ecosystem": ecosystem_score,
        "resilience": resilience_score,
    }
    component_weights = {"density": 0.40, "mobility": 0.15, "ecosystem": 0.20, "resilience": 0.25}

    base_final_score, base_component_renorm = _weighted_avg(components, component_weights)
    base_final_score = float(base_final_score or 0.0)

    selected = parse_job_categories(job_categories)
    overlays_payload: Optional[Dict[str, Any]] = None
    personalized_density: Optional[float] = None

    if selected:
        overlays_payload = compute_job_category_overlays(
            year=year_now,
            geo=effective_geo,
            division=division,
            area_bucket=bucket,
            base_job_market_strength=float(density_score or 0.0),
            public_admin_share_pct=dp03_now.get("DP03_0045PE") if isinstance(dp03_now.get("DP03_0045PE"), (int, float)) else None,
        )
        overlays = (overlays_payload or {}).get("job_category_overlays", {}) or {}
        vals: List[float] = []
        for k in selected:
            v = (overlays.get(k, {}) or {}).get("final_job_market_score")
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if vals:
            personalized_density = sum(vals) / len(vals)

    if isinstance(personalized_density, (int, float)):
        components["density"] = float(personalized_density)
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
            "net_estab_entry_per_1k": net_estab_entry_per_1k,
            "estabs_per_1k": estabs_per_1k,
            "wage_p25_annual": wage_p25_annual,
            "wage_p75_annual": wage_p75_annual,
            "qcew_employment_per_1k": qcew_employment_per_1k,
            "qcew_employment_growth_pct": qcew_employment_growth_pct,
            "anchored_balance": anchored_balance,
            "total_employment": total_employment,
            "total_establishments": total_establishments,
            "log10_employment": log10_employment,
            "log10_establishments": log10_establishments,
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
        "density": {
            "score": float(components["density"] or 0.0),
            "weights": density_renorm,
            "metrics": {k: sub_scores.get(k) for k in density_weights.keys()},
        },
        "mobility": {
            "score": float(components["mobility"] or 0.0),
            "weights": mobility_renorm,
            "metrics": {k: sub_scores.get(k) for k in mobility_weights.keys()},
        },
        "ecosystem": {
            "score": float(components["ecosystem"] or 0.0),
            "weights": ecosystem_renorm,
            "metrics": {k: sub_scores.get(k) for k in ecosystem_weights.keys()},
        },
        "resilience": {
            "score": float(components["resilience"] or 0.0),
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
        "net_estab_entry_per_1k": round(float(net_estab_entry_per_1k), 2) if isinstance(net_estab_entry_per_1k, (int, float)) else None,
        "estabs_per_1k": round(float(estabs_per_1k), 2) if isinstance(estabs_per_1k, (int, float)) else None,
        "wage_p25_annual": int(wage_p25_annual) if isinstance(wage_p25_annual, (int, float)) else None,
        "wage_p75_annual": int(wage_p75_annual) if isinstance(wage_p75_annual, (int, float)) else None,
        "qcew_employment_per_1k": round(float(qcew_employment_per_1k), 2) if isinstance(qcew_employment_per_1k, (int, float)) else None,
        "qcew_employment_growth_pct": round(float(qcew_employment_growth_pct), 2) if isinstance(qcew_employment_growth_pct, (int, float)) else None,
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

