"""
Job category overlays for Economic Opportunity (economic_security).

These overlays are an optional personalization layer:
- Base pillar remains profession-agnostic.
- If a user selects job categories, we adjust the job_market_strength sub-index
  and recompute the pillar score (and thus total_score).

Data sources (Census only):
- ACS 5-year subject table S2401 for occupation counts (density shares)
- ACS 5-year detailed table B08301 for worked-from-home share (remote_flexible)

Overlay score is density-only (no earnings-to-rent). Normalization uses
mean/std baselines for jobcat_density_* via normalize_metric_to_0_100(); missing → 0.5.
"""

from __future__ import annotations

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

# Worked from home share
B08301_TOTAL = "B08301_001E"
B08301_WFH = "B08301_021E"


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


def compute_job_category_overlays(
    *,
    year: int,
    geo: EconomicGeo,
    division: str,
    area_bucket: str,
    base_job_market_strength: float,
    public_admin_share_pct: Optional[float],
) -> Dict[str, Any]:
    """
    Compute overlays for ALL categories (callers may filter for selected).
    Score is density-only (no earnings-to-rent).
    """
    s2401_vars = [S2401_TOTAL_EMPLOYED, *sorted(set(S2401_COUNTS.values()))]
    s2401_row = fetch_acs_table(year=year, geo=geo, variables=s2401_vars, dataset="acs/acs5/subject") or {}

    wfh_row = fetch_acs_table(year=year, geo=geo, variables=[B08301_TOTAL, B08301_WFH], dataset="acs/acs5") or {}

    overlays: Dict[str, Any] = {}

    for cat in JOB_CATEGORIES:
        density_share: Optional[float] = None

        if cat in CATEGORY_GROUPS:
            groups = CATEGORY_GROUPS[cat]
            density_share = _compute_category_density_share_from_s2401(s2401_row, group_keys=groups)

        elif cat == "public_sector_nonprofit":
            if isinstance(public_admin_share_pct, (int, float)):
                density_share = max(0.0, min(1.0, float(public_admin_share_pct) / 100.0))

        elif cat == "remote_flexible":
            total = wfh_row.get(B08301_TOTAL)
            wfh = wfh_row.get(B08301_WFH)
            if isinstance(total, (int, float)) and total > 0 and isinstance(wfh, (int, float)) and wfh >= 0:
                density_share = float(wfh) / float(total)

        density_pct = _percentile(
            metric=f"jobcat_density_{cat}",
            value=density_share,
            division=division,
            area_bucket=area_bucket,
        )

        # Density-only: job_fit_raw = density_pct; adjustment ±15 from neutral 0.5
        adjustment = _clamp((density_pct - 0.5) * 30.0, -15.0, 15.0)
        final_job_market = _clamp(float(base_job_market_strength) + adjustment, 0.0, 100.0)

        overlays[cat] = {
            "adjustment": round(adjustment, 2),
            "final_job_market_score": round(final_job_market, 1),
            "density_percentile": round(density_pct, 3),
        }

    return {"job_category_overlays": overlays}

