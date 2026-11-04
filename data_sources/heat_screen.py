"""
Plausibility screen for the Landsat heat reading (DPv2, 2026-11-03).

A June-August afternoon land-surface temperature far below the normal summer air temperature of the same place is a bad
reading (cloud or shadow in the composite), not a cool place: a sunlit surface is not much cooler than the air above it.
Independent check against PRISM 1991-2020 normals found 6 of 1,467 catalog places 10 to 16 C below the air normal, all
with full heat points (Alamo Heights TX read 20.7 C against a 34.7 C air normal).

The margin is a JUDGMENT, not a sourced value, and its sensitivity has not been tested; the nearest place that passes
(Olmos Park TX) sits 9.8 C below. Catalog and live pillar share this function but not the reference: the catalog uses the PRISM
800 m JJA normal, the live pillar the TerraClimate 4 km JJA normal, so a place near the margin can be screened in one and
not the other. This file imports nothing heavy so offline catalog scripts can use it without starting Earth Engine.
"""
from typing import Optional

HEAT_MAX_BELOW_AIR_C = 10.0


def lst_implausible_vs_air(lst_c: Optional[float], air_tmax_jja_c: Optional[float], margin_c: float = HEAT_MAX_BELOW_AIR_C) -> bool:
    """True when the surface reading is more than margin_c below the normal summer air temperature. False when either is unknown."""
    if lst_c is None or air_tmax_jja_c is None:
        return False
    return float(lst_c) < float(air_tmax_jja_c) - margin_c
