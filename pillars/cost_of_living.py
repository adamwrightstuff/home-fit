"""
Cost of Living pillar — 0-100 score for the non-housing cost burden of a place:
income taxes plus groceries for a reference household, compared with US places
nationally.  Housing is NOT included (see housing_value).

Inputs
------
- A reference household income (the US median household income, ACS), the same for every
  place, so the score reflects prices and tax law and not how rich the place is.  A caller
  may pass a different income (e.g. a user's own) to personalise the burden.
- State income tax at that income (married filing jointly, Tax Foundation 2026 brackets),
  plus the city income tax where we have a citable rate (NYC, Philadelphia, Yonkers).
- Grocery cost: national average food-at-home spend (BLS Consumer Expenditure Survey)
  scaled by BEA's Regional Price Parity for goods in the place's metro (state fallback).

Scoring
-------
1. burden = (income tax + grocery cost) / reference income.
2. The same household is priced in every US place (grouped by state and city-tax
   jurisdiction, population-weighted); score = linear position of the burden between that
   distribution's 95th percentile (score 0) and 5th percentile (score 100), clipped.
   Linear, so a small price gap is a small score gap.  The reference distribution is
   recomputed for the household's income, so the score always means "versus other places,
   for a household like yours".

What varies and what does not
-----------------------------
Taxes vary by state (and a few cities); grocery prices vary by metro.  Towns in the same
metro, state and city score identically: this pillar separates metros, states and a few
cities, not neighbouring towns.  Place income is deliberately not used, so it does not
repeat economic_opportunity or status_signal.

Not covered: property tax (Census figure is top-coded in high-tax places), childcare and
transportation (no reliable national source), Pennsylvania suburban / Maryland county /
Indiana county / Delaware local income taxes, sales tax.

Data
----
- data/cost_of_living_state_tax.json     (hand-entered from Tax Foundation)
- data/cost_of_living_bea_goods_rpp.json (built from BEA MARPP/SARPP)
- data/cost_of_living_national_scale.json
Rebuild the last two with scripts/baselines/build_cost_of_living_national_scale.py.
"""

from __future__ import annotations

import bisect
import json
import os
from typing import Any, Dict, Optional, Tuple

from logging_config import get_logger

logger = get_logger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# BLS Consumer Expenditure Survey 2024, all consumer units, food at home (annual $).
GROCERY_SPEND_NATIONAL = 6224.0


def _load(name: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(_DATA_DIR, name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # missing data degrades the pillar, never crashes it
        logger.warning("cost_of_living: failed to load %s: %s", name, e)
        return {}


_tax = _load("cost_of_living_state_tax.json")
_rpp = _load("cost_of_living_bea_goods_rpp.json")
_scale = _load("cost_of_living_national_scale.json")


def state_income_tax(state: str, income: float) -> float:
    """State income tax (married filing jointly) on `income`, in dollars."""
    s = (_tax.get("states") or {}).get(state)
    if s is None:
        return 0.0
    taxable = max(0.0, income - s.get("deduction", 0) - s.get("exemption", 0))
    brackets = s.get("brackets") or []
    tax = 0.0
    for i, (lo, rate) in enumerate(brackets):
        hi = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if taxable > lo:
            tax += (min(taxable, hi) - lo) * rate / 100.0
    return max(0.0, tax - s.get("credit", 0))


def local_income_tax(city: Optional[str], state: str, income: float, state_tax: float) -> Tuple[float, Optional[str]]:
    """City income tax in dollars, plus the jurisdiction key if one applied."""
    if not city:
        return 0.0, None
    name = city.replace("City of ", "").replace("Village of ", "").strip()
    key = f"{name} city, {state}"
    rule = (_tax.get("local") or {}).get(key)
    if not rule:
        return 0.0, None
    if rule["type"] == "flat_pct_of_income":
        return income * rule["rate_pct"] / 100.0, key
    if rule["type"] == "pct_of_state_tax":
        return state_tax * rule["rate_pct"] / 100.0, key
    return 0.0, None


def goods_rpp(cbsa_code: Optional[str], state: str) -> Tuple[Optional[float], str]:
    """BEA RPP for goods (US = 100): metro if known, else the state, else None."""
    if cbsa_code and cbsa_code in (_rpp.get("msa") or {}):
        return _rpp["msa"][cbsa_code]["goods"], "msa"
    if state in (_rpp.get("state") or {}):
        return _rpp["state"][state]["goods"], "state"
    return None, "none"


ANCHOR_LOW_PCT = 5.0    # burden at/below this national percentile scores 100
ANCHOR_HIGH_PCT = 95.0  # burden at/above this national percentile scores 0


def _burden(state: str, local_key: Optional[str], goods: float, income: float) -> float:
    s_tax = state_income_tax(state, income)
    l_tax = 0.0
    rule = (_tax.get("local") or {}).get(local_key) if local_key else None
    if rule:
        l_tax = income * rule["rate_pct"] / 100.0 if rule["type"] == "flat_pct_of_income" else s_tax * rule["rate_pct"] / 100.0
    return (s_tax + l_tax + GROCERY_SPEND_NATIONAL * goods / 100.0) / income


def _weighted_percentile(pairs, pct: float) -> float:
    pairs = sorted(pairs)
    target = sum(w for _, w in pairs) * pct / 100.0
    cum = 0.0
    for v, w in pairs:
        cum += w
        if cum >= target:
            return v
    return pairs[-1][0]


def burden_anchors(income: float) -> Tuple[float, float]:
    """(5th, 95th) population-weighted percentile burden of a household of this income
    priced in every US place group."""
    key = int(round(income / 1000.0)) * 1000
    cached = _anchor_cache.get(key)
    if cached:
        return cached
    pairs = [(_burden(g["state"], g["local"], g["goods"], float(key)), g["pop"]) for g in _scale.get("groups", [])]
    out = (_weighted_percentile(pairs, ANCHOR_LOW_PCT), _weighted_percentile(pairs, ANCHOR_HIGH_PCT))
    _anchor_cache[key] = out
    return out


_anchor_cache: Dict[int, Tuple[float, float]] = {}


def reference_income() -> Optional[float]:
    return (_scale.get("_meta") or {}).get("reference_income")


def get_cost_of_living_score(
    state: Optional[str],
    *,
    cbsa_code: Optional[str] = None,
    city: Optional[str] = None,
    income: Optional[float] = None,
) -> Tuple[Optional[float], Dict[str, Any]]:
    """Return (score, details); score is None when inputs or reference data are missing.
    `income` defaults to the national reference income."""
    income = float(income) if income else reference_income()
    if not income or income <= 0 or not state or not _scale:
        return None, {"status": "DEGRADED", "confidence": 0, "summary": {}, "breakdown": {},
                      "data_quality": {"reason": "missing state or national scale"}}

    s_tax = state_income_tax(state, income)
    l_tax, local_key = local_income_tax(city, state, income, s_tax)
    rpp, rpp_level = goods_rpp(cbsa_code, state)
    if rpp is None:
        return None, {"status": "DEGRADED", "confidence": 0, "summary": {}, "breakdown": {},
                      "data_quality": {"reason": f"no goods price level for {state}"}}

    groceries = GROCERY_SPEND_NATIONAL * rpp / 100.0
    burden = (s_tax + l_tax + groceries) / income
    lo, hi = burden_anchors(income)
    score = round(max(0.0, min(100.0, 100.0 * (hi - burden) / (hi - lo))), 2) if hi > lo else 50.0

    confidence = 80 if rpp_level == "msa" else 60
    return score, {
        "status": "VERIFIED",
        "confidence": confidence,
        "summary": {
            "household_income": round(income),
            "income_basis": "caller" if income != reference_income() else "us_median_reference",
            "state_income_tax": round(s_tax),
            "local_income_tax": round(l_tax),
            "local_tax_jurisdiction": local_key,
            "grocery_cost": round(groceries),
            "grocery_premium_vs_us": round(groceries - GROCERY_SPEND_NATIONAL),
            "burden_pct_of_income": round(burden * 100, 2),
            "goods_price_index": round(rpp, 1),
            "goods_price_index_level": rpp_level,
        },
        "breakdown": {
            "tax_pct_of_income": round((s_tax + l_tax) / income * 100, 2),
            "grocery_pct_of_income": round(groceries / income * 100, 2),
            "burden_best_anchor_pct": round(lo * 100, 2),
            "burden_worst_anchor_pct": round(hi * 100, 2),
        },
        "data_quality": {
            "scale_population": _scale.get("_meta", {}).get("places_used"),
            "tax_year": _tax.get("_meta", {}).get("as_of"),
            "rpp_year": _rpp.get("_meta", {}).get("year"),
            "not_modelled": ["property_tax", "sales_tax", "childcare", "transportation",
                             "suburban_pa_md_in_de_local_income_tax"],
        },
    }
