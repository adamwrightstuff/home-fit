"""
Metro-to-metro relocation equivalency: what income do you need in metro B to keep the same
amount of money left over as you have in metro A?

    left_over = income - state income tax - housing - everyday spending

Built only from national sources (data/relocation_rpp.json, rebuilt by
scripts/baselines/build_relocation_inputs.py), so it covers every BEA metro (387):

- Housing is ONE cost, scaled between metros:
    renter: the user's current rent (or A's median gross rent if not given) scaled by the
            ratio of the two metros' BEA housing (rent) price levels, which are quality
            adjusted; the Census median rent is not used for scaling because it reflects
            what existing renters pay (long leases, rent stabilisation) and understates
            what a mover pays in NYC, LA and Miami;
    owner:  the user's current all-in payment (mortgage, property tax, whatever they pay)
            scaled by the ratio of the two metros' median home values.
  No mortgage rate, down payment or separate property tax is assumed.  Owner scaling holds
  at any common rate and assumes the same loan terms and that tax moves with price (true in
  Texas, Illinois, California; weaker in the Northeast).  It answers "same relative home".
- State income tax (married filing jointly, Tax Foundation 2026) for the state the user will
  live in.  A metro can span states (New York-Newark-Jersey City is NY and NJ); the tax state
  defaults to the metro's first-listed state and can be overridden.  City income taxes (NYC,
  Philadelphia) are not applied: they depend on the exact city inside the metro.
- Everyday spending: a national average non-housing basket scaled by BEA's metro price levels
  for goods and other services.

Basket base: BLS Consumer Expenditure Survey 2024, total expenditures $78,535 minus housing
$26,266 minus personal insurance and pensions $9,797 (mostly Social Security and pension
contributions, not prices) = $42,472.  Utilities sit inside gross rent and housing, so the BEA
utilities line is not applied to the basket.  BEA's published line weights are not in its bulk
files; goods versus other services are weighted by a least-squares fit of the all-items index.

Not modelled: homeowners insurance, payroll tax (equal everywhere), childcare, transportation,
car and health insurance, sales tax, and anything that differs between towns inside a metro.
This is a metro-to-metro tool.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pillars.cost_of_living import state_income_tax

_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "relocation_rpp.json")
with open(_DATA, "r", encoding="utf-8") as _f:
    _d = json.load(_f)
_msa: Dict[str, Dict[str, Any]] = _d["msa"]
_w = _d["_meta"]["all_items_weights_by_line"]

BASKET_BASE = 78535.0 - 26266.0 - 9797.0  # BLS CE 2024, see module docstring

_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


ESTIMATE_NOTE = (
    "Estimate for comparing metros, not a quote. Uses state income tax only (no city, property or "
    "sales tax), a national average everyday basket, and metro median housing costs; "
    "owner results assume the same relative home."
)


def metro(code: str) -> Dict[str, Any]:
    if code not in _msa:
        raise KeyError(f"unknown metro code {code}")
    return _msa[code]


def find_metro(text: str) -> List[str]:
    """CBSA codes whose name contains `text` (case-insensitive)."""
    t = text.lower()
    return [c for c, m in _msa.items() if t in m["acs_name"].lower()]


def basket_index(code: str) -> float:
    """Weighted BEA price index (US = 100) for goods and other services in a metro."""
    m = metro(code)
    gw, ow = _w["goods"], _w["other_services"]
    return (gw * m["goods"] + ow * m["other_services"]) / (gw + ow)


def tax_state(code: str, override: Optional[str] = None) -> str:
    st = override or metro(code)["states"][0]
    return _ABBR.get(st, st)


def _housing_scale(origin: str, dest: str, tenure: str) -> float:
    key = "housing" if tenure == "rent" else "median_home_value"
    return metro(dest)[key] / metro(origin)[key]


def costs_in(code: str, income: float, housing: float, *, state: Optional[str] = None) -> Dict[str, float]:
    tax = state_income_tax(tax_state(code, state), income)
    everyday = BASKET_BASE * basket_index(code) / 100.0
    return {"tax": tax, "housing": housing, "everyday": everyday,
            "left_over": income - tax - housing - everyday}


def equivalent_income(origin: str, dest: str, income: float, *, tenure: str = "rent",
                      housing_year: Optional[float] = None,
                      origin_state: Optional[str] = None, dest_state: Optional[str] = None) -> Dict[str, Any]:
    """Income needed in `dest` to keep the money left over that `income` leaves in `origin`.

    tenure: "rent" or "own".  housing_year: the user's current yearly housing cost (rent, or
    all-in owner payment); required for "own", defaults to the origin metro's median rent
    for "rent".  Codes are CBSA codes (see find_metro)."""
    if tenure not in ("rent", "own"):
        raise ValueError("tenure must be 'rent' or 'own'")
    if tenure == "own" and not housing_year:
        raise ValueError("owner mode needs the user's current yearly housing cost")
    h_origin = housing_year or metro(origin)["median_gross_rent"] * 12.0
    h_dest = h_origin * _housing_scale(origin, dest, tenure)

    a = costs_in(origin, income, h_origin, state=origin_state)
    target = a["left_over"]
    lo, hi = 1000.0, max(income * 5, 500000.0)
    for _ in range(80):  # bisection; left-over rises with income
        mid = (lo + hi) / 2
        if costs_in(dest, mid, h_dest, state=dest_state)["left_over"] < target:
            lo = mid
        else:
            hi = mid
    need = (lo + hi) / 2
    b = costs_in(dest, need, h_dest, state=dest_state)
    rnd = lambda d: {k: round(v) for k, v in d.items()}
    return {
        "estimate_note": ESTIMATE_NOTE,
        "origin": metro(origin)["acs_name"], "dest": metro(dest)["acs_name"], "tenure": tenure,
        "tax_states": {"origin": tax_state(origin, origin_state), "dest": tax_state(dest, dest_state)},
        "income_in_origin": income,
        "equivalent_income_in_dest": round(need),
        "change_pct": round((need / income - 1) * 100, 1),
        "left_over_held_constant": round(target),
        "origin_costs": rnd(a),
        "dest_costs_at_equivalent_income": rnd(b),
        "housing_scale": round(h_dest / h_origin, 3),
    }


def rank_metros(origin: str, income: float, *, tenure: str = "rent", housing_year: Optional[float] = None,
                origin_state: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every metro ordered by the income needed there (lowest first)."""
    out = []
    for code in _msa:
        if code == origin:
            continue
        r = equivalent_income(origin, code, income, tenure=tenure, housing_year=housing_year, origin_state=origin_state)
        out.append({"code": code, "metro": r["dest"], "equivalent_income": r["equivalent_income_in_dest"],
                    "change_pct": r["change_pct"]})
    return sorted(out, key=lambda x: x["equivalent_income"])
