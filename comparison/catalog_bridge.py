"""
Bridge from catalog places (metro key, city, state) to the metro-level relocation calculator.

The UI knows a place's catalog metro key ("nyc"), city ("New York") and state ("NY").  This maps
the key to a CBSA code and applies city income tax only for the cities that have a citable rate
(New York, Philadelphia, Yonkers) when the place is inside that city.  Returns both a renter
view and, when the user supplied their current monthly housing cost, an owner view.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from comparison.relocation_equivalency import ESTIMATE_NOTE, equivalent_income

with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "catalog_metro_cbsa.json"), "r", encoding="utf-8") as _f:
    _CBSA: Dict[str, str] = {k: v for k, v in json.load(_f).items() if not k.startswith("_")}

CITY_TAX_CITIES = {"new york": "New York", "philadelphia": "Philadelphia", "yonkers": "Yonkers"}


def known_metro(key: str) -> bool:
    return key in _CBSA


def _city(name: Optional[str]) -> Optional[str]:
    return CITY_TAX_CITIES.get((name or "").strip().lower())


def catalog_equivalency(origin_metro: str, dest_metro: str, income: float, *,
                        monthly_cost: Optional[float] = None,
                        origin_state: Optional[str] = None, dest_state: Optional[str] = None,
                        origin_city: Optional[str] = None, dest_city: Optional[str] = None) -> Dict[str, Any]:
    """Income needed in dest_metro to keep the money left over that `income` leaves in origin_metro.

    monthly_cost is the user's current monthly housing cost (profile).  With it we return a
    renter view (cost scaled by the BEA rent level) and an owner view (scaled by Zillow home
    values); without it only the renter view at the origin metro's median rent."""
    if origin_metro not in _CBSA or dest_metro not in _CBSA:
        raise KeyError("unknown catalog metro")
    kw = dict(origin_state=origin_state or None, dest_state=dest_state or None,
              origin_city=_city(origin_city), dest_city=_city(dest_city))
    o, d = _CBSA[origin_metro], _CBSA[dest_metro]
    yearly = monthly_cost * 12.0 if monthly_cost and monthly_cost > 0 else None
    out: Dict[str, Any] = {"estimate_note": ESTIMATE_NOTE, "same_metro": o == d, "rent": None, "own": None}
    if o == d:
        return out
    out["rent"] = equivalent_income(o, d, income, tenure="rent", housing_year=yearly, **kw)
    if yearly:
        out["own"] = equivalent_income(o, d, income, tenure="own", housing_year=yearly, **kw)
    return out
