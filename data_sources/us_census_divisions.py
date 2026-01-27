"""
US Census Regions & Divisions mapping.

Used for within-division normalization (e.g. Pacific vs South Atlantic) so scores
reflect local conditions rather than national scale.
"""

from __future__ import annotations

from typing import Optional


# Full state names → abbreviations (lowercase keys).
# This mirrors the mapping used in geocoding so callers can pass either "WA" or "Washington".
_STATE_NAME_TO_ABBREV = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "puerto rico": "PR",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


# Source: US Census Bureau regions/divisions (standard 9-division schema)
_STATE_TO_DIVISION = {
    # New England
    "CT": "new_england",
    "ME": "new_england",
    "MA": "new_england",
    "NH": "new_england",
    "RI": "new_england",
    "VT": "new_england",
    # Middle Atlantic
    "NJ": "middle_atlantic",
    "NY": "middle_atlantic",
    "PA": "middle_atlantic",
    # East North Central
    "IL": "east_north_central",
    "IN": "east_north_central",
    "MI": "east_north_central",
    "OH": "east_north_central",
    "WI": "east_north_central",
    # West North Central
    "IA": "west_north_central",
    "KS": "west_north_central",
    "MN": "west_north_central",
    "MO": "west_north_central",
    "NE": "west_north_central",
    "ND": "west_north_central",
    "SD": "west_north_central",
    # South Atlantic
    "DE": "south_atlantic",
    "DC": "south_atlantic",
    "FL": "south_atlantic",
    "GA": "south_atlantic",
    "MD": "south_atlantic",
    "NC": "south_atlantic",
    "SC": "south_atlantic",
    "VA": "south_atlantic",
    "WV": "south_atlantic",
    # East South Central
    "AL": "east_south_central",
    "KY": "east_south_central",
    "MS": "east_south_central",
    "TN": "east_south_central",
    # West South Central
    "AR": "west_south_central",
    "LA": "west_south_central",
    "OK": "west_south_central",
    "TX": "west_south_central",
    # Mountain
    "AZ": "mountain",
    "CO": "mountain",
    "ID": "mountain",
    "MT": "mountain",
    "NV": "mountain",
    "NM": "mountain",
    "UT": "mountain",
    "WY": "mountain",
    # Pacific
    "AK": "pacific",
    "CA": "pacific",
    "HI": "pacific",
    "OR": "pacific",
    "WA": "pacific",
}


def get_division(state_abbrev: Optional[str]) -> str:
    """
    Return the Census Division key for a state abbreviation.

    Falls back to 'unknown' if state is missing/unrecognized.
    """
    if not state_abbrev:
        return "unknown"
    raw = state_abbrev.strip()
    # Accept full names as well as 2-letter abbreviations
    if len(raw) > 2:
        raw = _STATE_NAME_TO_ABBREV.get(raw.lower(), raw)
    return _STATE_TO_DIVISION.get(raw.upper(), "unknown")

