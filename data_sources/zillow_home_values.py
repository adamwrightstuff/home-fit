"""
Zillow ZHVI (Home Value Index) lookup by ZIP code.
Used to override Census ACS median home values that are capped at $2,000,001.
Data: data/zillow_zhvi_zip.json — generated from Zillow Research public CSV.
"""

import json
import os
from typing import Optional

_CACHE: Optional[dict] = None
CENSUS_CAP = 2_000_001


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        path = os.path.join(os.path.dirname(__file__), '..', 'data', 'zillow_zhvi_zip.json')
        with open(os.path.normpath(path)) as f:
            _CACHE = json.load(f)
    return _CACHE


def get_zhvi(zip_code: str) -> Optional[int]:
    """Return Zillow ZHVI for a ZIP code, or None if not found."""
    if not zip_code:
        return None
    data = _load()
    return data['values'].get(zip_code.zfill(5))


def get_home_value(census_value: Optional[int], zip_code: Optional[str]) -> tuple[Optional[int], bool]:
    """
    Return (home_value, zillow_used).
    Uses Zillow when Census hits its $2,000,001 cap and a Zillow value is available.
    """
    if census_value == CENSUS_CAP and zip_code:
        zhvi = get_zhvi(zip_code)
        if zhvi and zhvi > CENSUS_CAP:
            return zhvi, True
    return census_value, False
