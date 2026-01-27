"""
Job category overlays for Economic Opportunity (economic_security).

These overlays are an optional personalization layer:
- Base pillar remains profession-agnostic.
- If a user selects job categories, we adjust the job_market_strength sub-index
  and recompute the pillar score (and thus total_score).

Data sources (Census only):
- ACS 5-year subject table S2401 for occupation counts (density shares)
- ACS 5-year detailed table B24011 for median earnings by occupation
- ACS 5-year detailed table B08301 for worked-from-home share (remote_flexible)
- ACS 5-year detailed table B24031 for median earnings by industry (public admin proxy)

Normalization:
We reuse the existing mean/std baselines + z→percentile mapping by calling
`normalize_metric_to_0_100()` and dividing by 100. If a baseline is missing,
we fall back to neutral percentile 0.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .economic_security_data import EconomicGeo, fetch_acs_table
from .normalization import normalize_metric_to_0_100


JOB_CATEGORIES: Tuple[str, ...] = (
    "tech_professional",
    "business_finance_law",
    "healthcare_education",
    "skilled_trades_logistics",
    "service_retail_hospitality",
    "public_sector_nonprofit",
    "remote_flexible",
)


S2401_TOTAL_EMPLOYED = "S2401_C01_001E"

# S2401 occupation counts (civilian employed 16+)
S2401_COUNTS = {
    "management_occupations": "S2401_C01_004E",
    "business_financial_ops": "S2401_C01_005E",
    "computer_math": "S2401_C01_007E",
    "arch_engineering": "S2401_C01_008E",
    "legal": "S2401_C01_012E",
    "education_library": "S2401_C01_013E",
    "health_practitioners": "S2401_C01_017E",
    "health_support": "S2401_C01_019E",
    "food_prep": "S2401_C01_023E",
    "building_grounds": "S2401_C01_024E",
    "personal_care": "S2401_C01_025E",
    "sales": "S2401_C01_027E",
    "office_admin": "S2401_C01_028E",
    "construction": "S2401_C01_031E",
    "installation_repair": "S2401_C01_032E",
    "production": "S2401_C01_034E",
    "transportation": "S2401_C01_035E",
    "material_moving": "S2401_C01_036E",
}

# B24011 median earnings by occupation group (dollars)
B24011_MEDIANS = {
    "management_occupations": "B24011_004E",
    "business_financial_ops": "B24011_005E",
    "computer_math": "B24011_007E",
    "arch_engineering": "B24011_008E",
    "legal": "B24011_012E",
    "education_library": "B24011_013E",
    "health_practitioners": "B24011_015E",
    "health_support": "B24011_019E",
    "food_prep": "B24011_023E",
    "building_grounds": "B24011_024E",
    "personal_care": "B24011_025E",
    "sales": "B24011_027E",
    "office_admin": "B24011_028E",
    "construction": "B24011_031E",
    "installation_repair": "B24011_032E",
    "production": "B24011_034E",
    "transportation": "B24011_035E",
    "material_moving": "B24011_036E",
}

# Worked from home share
B08301_TOTAL = "B08301_001E"
B08301_WFH = "B08301_021E"

# Public administration median earnings (industry proxy)
B24031_PUBLIC_ADMIN = "B24031_027E"


CATEGORY_GROUPS: Dict[str, List[str]] = {
    "tech_professional": ["computer_math", "arch_engineering"],
    "business_finance_law": ["management_occupations", "business_financial_ops", "legal"],
    "healthcare_education": ["health_practitioners", "health_support", "education_library"],
    "skilled_trades_logistics": ["construction", "installation_repair", "production", "transportation", "material_moving"],
    "service_retail_hospitality": ["food_prep", "building_grounds", "personal_care", "sales", "office_admin"],
}


def parse_job_categories(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    seen = set()
    out: List[str] = []
    for p in parts:
        if p in JOB_CATEGORIES and p not in seen:
            out.append(p)
            seen.add(p)
    return out


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _percentile(
    *,
    metric: str,
    value: Optional[float],
    division: str,
    area_bucket: str,
    invert: bool = False,
) -> float:
    """
    Return a percentile in [0,1]. Missing baselines → neutral 0.5.
    """
    if value is None:
        return 0.5
    s = normalize_metric_to_0_100(metric=metric, value=value, division=division, area_bucket=area_bucket, invert=invert)
    if not isinstance(s, (int, float)):
        return 0.5
    return _clamp(float(s) / 100.0, 0.0, 1.0)


def _weighted_mean(values: List[Tuple[float, float]]) -> Optional[float]:
    """
    Weighted mean of (value, weight) pairs.
    """
    if not values:
        return None
    total_w = sum(w for _, w in values if w > 0)
    if total_w <= 0:
        return None
    return sum(v * w for v, w in values if w > 0) / total_w


def _compute_category_density_share_from_s2401(
    s2401_row: Dict[str, Optional[float]],
    *,
    group_keys: Iterable[str],
) -> Optional[float]:
    total = s2401_row.get(S2401_TOTAL_EMPLOYED)
    if not isinstance(total, (int, float)) or total <= 0:
        return None
    num = 0.0
    ok = False
    for g in group_keys:
        var = S2401_COUNTS.get(g)
        if not var:
            continue
        v = s2401_row.get(var)
        if isinstance(v, (int, float)) and v >= 0:
            num += float(v)
            ok = True
    if not ok:
        return None
    return num / float(total)


def _compute_category_median_earnings_from_b24011(
    b24011_row: Dict[str, Optional[float]],
    s2401_row: Dict[str, Optional[float]],
    *,
    group_keys: Iterable[str],
) -> Optional[float]:
    pairs: List[Tuple[float, float]] = []
    for g in group_keys:
        med_var = B24011_MEDIANS.get(g)
        cnt_var = S2401_COUNTS.get(g)
        if not med_var or not cnt_var:
            continue
        median = b24011_row.get(med_var)
        count = s2401_row.get(cnt_var)
        if isinstance(median, (int, float)) and median > 0 and isinstance(count, (int, float)) and count > 0:
            pairs.append((float(median), float(count)))
    return _weighted_mean(pairs)


def compute_job_category_overlays(
    *,
    year: int,
    geo: EconomicGeo,
    division: str,
    area_bucket: str,
    base_job_market_strength: float,
    median_gross_rent_monthly: Optional[float],
    overall_median_earnings: Optional[float],
    public_admin_share_pct: Optional[float],
) -> Dict[str, Any]:
    """
    Compute overlays for ALL categories (callers may filter for selected).
    """
    # Fetch once per request
    s2401_vars = [S2401_TOTAL_EMPLOYED, *sorted(set(S2401_COUNTS.values()))]
    s2401_row = fetch_acs_table(year=year, geo=geo, variables=s2401_vars, dataset="acs/acs5/subject") or {}

    b24011_row = fetch_acs_table(year=year, geo=geo, variables=sorted(set(B24011_MEDIANS.values())), dataset="acs/acs5") or {}

    wfh_row = fetch_acs_table(year=year, geo=geo, variables=[B08301_TOTAL, B08301_WFH], dataset="acs/acs5") or {}
    b24031_row = fetch_acs_table(year=year, geo=geo, variables=[B24031_PUBLIC_ADMIN], dataset="acs/acs5") or {}

    annual_rent = None
    if isinstance(median_gross_rent_monthly, (int, float)) and median_gross_rent_monthly > 0:
        annual_rent = float(median_gross_rent_monthly) * 12.0

    def earnings_to_rent(earn: Optional[float]) -> Optional[float]:
        if not isinstance(earn, (int, float)) or earn <= 0 or not isinstance(annual_rent, (int, float)) or annual_rent <= 0:
            return None
        return float(earn) / float(annual_rent)

    overlays: Dict[str, Any] = {}

    for cat in JOB_CATEGORIES:
        density_share: Optional[float] = None
        cat_median_earn: Optional[float] = None

        if cat in CATEGORY_GROUPS:
            groups = CATEGORY_GROUPS[cat]
            density_share = _compute_category_density_share_from_s2401(s2401_row, group_keys=groups)
            cat_median_earn = _compute_category_median_earnings_from_b24011(b24011_row, s2401_row, group_keys=groups)

        elif cat == "public_sector_nonprofit":
            # Density via DP03 public admin industry share (percent)
            if isinstance(public_admin_share_pct, (int, float)):
                density_share = max(0.0, min(1.0, float(public_admin_share_pct) / 100.0))
            # Earnings via industry median earnings proxy
            cat_median_earn = b24031_row.get(B24031_PUBLIC_ADMIN) if isinstance(b24031_row.get(B24031_PUBLIC_ADMIN), (int, float)) else None

        elif cat == "remote_flexible":
            total = wfh_row.get(B08301_TOTAL)
            wfh = wfh_row.get(B08301_WFH)
            if isinstance(total, (int, float)) and total > 0 and isinstance(wfh, (int, float)) and wfh >= 0:
                density_share = float(wfh) / float(total)
            # Earnings proxy: overall median earnings (already used in pillar)
            cat_median_earn = overall_median_earnings if isinstance(overall_median_earnings, (int, float)) else None

        density_pct = _percentile(
            metric=f"jobcat_density_{cat}",
            value=density_share,
            division=division,
            area_bucket=area_bucket,
        )

        earn_ratio = earnings_to_rent(cat_median_earn)
        earnings_pct = _percentile(
            metric=f"jobcat_earnings_to_rent_{cat}",
            value=earn_ratio,
            division=division,
            area_bucket=area_bucket,
        )

        # Renormalize if one signal is effectively missing (we treat missing as 0.5, but
        # we still prefer density-driven overlays to have slightly more impact).
        job_fit_raw = 0.7 * density_pct + 0.3 * earnings_pct
        adjustment = _clamp((job_fit_raw - 0.5) * 30.0, -15.0, 15.0)
        final_job_market = _clamp(float(base_job_market_strength) + adjustment, 0.0, 100.0)

        overlays[cat] = {
            "adjustment": round(adjustment, 2),
            "final_job_market_score": round(final_job_market, 1),
            "density_percentile": round(density_pct, 3),
            "earnings_percentile": round(earnings_pct, 3),
        }

    return {"job_category_overlays": overlays}

