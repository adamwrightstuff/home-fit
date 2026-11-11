"""
Local scene v2 (docs/VIBE_VALIDATION.md, candidate 3): the mix of nearby places, as two facts and one coarse flag.

Facts, from the named venues of seven types around the pin (cafe, bar, restaurant, gallery, bookstore, records, theater),
within the place's amenities radius (1,200 or 1,500 m):
  culture_venues   independent galleries, bookstores and record stores (no OSM brand or brand:wikidata tag; no theaters)
  culture_share    culture_venues as a percent of all those venues
  hangout_share    cafes, bars, galleries, bookstores, record stores and theaters as a percent of all those venues
  hangouts_5min    cafes and bars within 400 m of the pin
Reading: each share is ranked among catalog places of similar density (activity per acre, five bands; owner decision 2026-11-05), and combined is the mean of the two ranks;
the ladder level (scene_level below) turns the venue count and that reading into four levels. Old local_scene_* fields are left untouched (Aura, twin finder and vibe
matching still read them).

Geography: places measured as a town or city (Census place or county subdivision with a boundary within a 6 km search circle) use every venue inside the boundary; neighborhoods and larger places use the pin circle. Each kind is ranked only against its own kind. Known limits: the pin may sit off a town's main street (Rye, Hastings-on-Hudson), counts depend on OpenStreetMap coverage,
MIN_VENUES (15, carried over from the old formula) and the level cuts are unsourced product choices, and the combination
was found on the same places it was checked against (hold-out: 6 of 6 pairs, n=5).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

CULTURE_TYPES = frozenset({"gallery", "bookstore", "records"})
HANGOUT_TYPES = frozenset({"cafe", "bar", "gallery", "bookstore", "records", "theater"})
VENUE_TYPES = frozenset({"cafe", "bar", "restaurant", "gallery", "bookstore", "records", "theater"})
WALK_5MIN_M = 400
MIN_VENUES = 15
METHOD = "culture_hangout_mix_v1"
# Activity tiers (the tag users see, owner decision 2026-11-06): independent named venues of the seven types within
# ACTIVITY_RADIUS_M of the pin. Cuts are the catalog's median (13) and 85th percentile (71) on that date: unsourced.
ACTIVITY_RADIUS_M = 1200
TOP_VOLUME_FROM = 71


def _has_brand(v: Dict[str, Any]) -> bool:
    return bool(v.get("brand") or v.get("brand_wikidata"))


def place_facts(venues: Iterable[Dict[str, Any]], radius_m: int) -> Dict[str, Any]:
    """Counts for one place from its named venues (each with type, distance_m, optional brand tags)."""
    total = hangouts = culture = cafes_bars_5min = 0
    for v in venues or []:
        if v.get("type") not in VENUE_TYPES or v.get("distance_m") is None or v["distance_m"] > radius_m:
            continue
        total += 1
        if v["type"] in HANGOUT_TYPES:
            hangouts += 1
        if v["type"] in CULTURE_TYPES and not _has_brand(v):
            culture += 1
        if v["type"] in ("cafe", "bar") and v["distance_m"] <= WALK_5MIN_M:
            cafes_bars_5min += 1
    return {
        "venues_total": total,
        "culture_venues": culture,
        "culture_share": round(100.0 * culture / total, 1) if total else None,
        "hangout_share": round(100.0 * hangouts / total, 1) if total else None,
        "hangouts_5min": cafes_bars_5min,
        "radius_m": radius_m,
        "few_venues": total < MIN_VENUES,
        "geography": "pin_circle",
        "method": METHOD,
    }


def percentile_ranks(values: List[Optional[float]]) -> List[Optional[float]]:
    """Mid-rank percentile (0 to 100) among the non-None values; None stays None."""
    present = sorted(v for v in values if v is not None)
    n = len(present)
    if not n:
        return [None] * len(values)
    out: List[Optional[float]] = []
    for v in values:
        if v is None:
            out.append(None)
        else:
            below = sum(1 for x in present if x < v)
            equal = sum(1 for x in present if x == v)
            out.append(100.0 * (below + 0.5 * equal) / n)
    return out


def density_bands(densities: List[Optional[float]], n_bands: int = 5) -> List[Optional[int]]:
    """Quintile band (0 = least dense) of each place by activity per acre; None when the density is missing."""
    idx = sorted((i for i, d in enumerate(densities) if d is not None), key=lambda i: densities[i])
    out: List[Optional[int]] = [None] * len(densities)
    for rank, i in enumerate(idx):
        out[i] = min(n_bands - 1, rank * n_bands // len(idx))
    return out


def apply_reading(facts: List[Dict[str, Any]], densities: Optional[List[Optional[float]]] = None) -> None:
    """
    Add combined (the mix reading) and density_band to each place's facts, in place. Each share is ranked among places in the
    same density band (activity per acre quintile; places with no density get no reading) and the same kind of geography
    (town or pin circle), and the two ranks are averaged.
    """
    n = len(facts)
    bands = density_bands(densities) if densities is not None else [0] * n  # no densities given at all: one band
    groups: Dict[Any, List[int]] = {}
    for i, b in enumerate(bands):
        # towns (boundary measure) and neighborhoods (pin circle) are different units: each is ranked only against its own kind
        facts[i].update({"combined": None, "density_band": None})
        if b is None:
            continue  # no density figure: no reading (ranking it against a handful of other density-less places gave Mar Vista 80)
        groups.setdefault((facts[i].get("geography", "pin_circle"), b), []).append(i)
    for (geo, b), members in groups.items():
        sub = [facts[i] for i in members]
        cs = percentile_ranks([f["culture_share"] for f in sub])
        hs = percentile_ranks([f["hangout_share"] for f in sub])
        combined = [(a + c) / 2 if a is not None and c is not None else None for a, c in zip(cs, hs)]
        for f, c in zip(sub, combined):
            f["combined"] = round(c, 1) if c is not None else None
            f["density_band"] = b + 1


def boundary_facts(venues: Iterable[Dict[str, Any]], area_km2: float) -> Dict[str, Any]:
    """
    Facts for a town from every named venue inside its Census boundary (no pin, no radius). The venues are already
    filtered to the boundary by scripts/catalog/reread_boundary_venues.py. hangouts_5min does not apply to a town and is None;
    cafes_bars_in_town counts cafes and bars in the whole boundary.
    """
    total = hangouts = culture = cafes_bars = 0
    for v in venues or []:
        if v.get("type") not in VENUE_TYPES:
            continue
        total += 1
        if v["type"] in HANGOUT_TYPES:
            hangouts += 1
        if v["type"] in CULTURE_TYPES and not _has_brand(v):
            culture += 1
        if v["type"] in ("cafe", "bar"):
            cafes_bars += 1
    return {
        "venues_total": total,
        "culture_venues": culture,
        "culture_share": round(100.0 * culture / total, 1) if total else None,
        "hangout_share": round(100.0 * hangouts / total, 1) if total else None,
        "hangouts_5min": None,
        "cafes_bars_in_town": cafes_bars,
        "radius_m": None,
        "area_km2": area_km2,
        "few_venues": total < MIN_VENUES,
        "geography": "town_boundary",
        "method": METHOD,
    }


def independent_venue_count(venues: Iterable[Dict[str, Any]], radius_m: int = ACTIVITY_RADIUS_M) -> int:
    """Named venues of the seven types within radius_m of the pin with no OSM brand or brand:wikidata tag."""
    return sum(
        1
        for v in venues or []
        if v.get("type") in VENUE_TYPES and v.get("distance_m") is not None and v["distance_m"] <= radius_m and not _has_brand(v)
    )


# Ladder (docs/LOCAL_SCENE_LADDER_DPV2.md, built 2026-11-11). Four levels from the mix reading and a volume floor:
#   quiet    fewer than MIN_VENUES named venues in the measured area
#   low_key  enough venues, mix reading below LEVEL_MIX_CUT (restaurant-heavy compared with similar places), or no density figure
#   lively   mix reading at least LEVEL_MIX_CUT, fewer than TOP_VOLUME_FROM independent venues at the pin
#   buzzing  mix reading at least LEVEL_MIX_CUT, TOP_VOLUME_FROM or more independent venues at the pin
# None when the place has no venue read or no named venue in the measured area: no data, never Quiet (principle 9).
# LEVEL_MIX_CUT was chosen on the owner's labels (in-sample, unsourced); both cuts are judgments.
LEVEL_MIX_CUT = 55.0
LEVELS = ("quiet", "low_key", "lively", "buzzing")


def scene_level(facts: Dict[str, Any]) -> Optional[str]:
    """Ladder level from a place's stored local_scene_v2 facts (venues_total, combined, independent_venues_1200m)."""
    total, n = facts.get("venues_total"), facts.get("independent_venues_1200m")
    if not total or n is None:
        return None
    if total < MIN_VENUES:
        return "quiet"
    combined = facts.get("combined")
    if combined is None or combined < LEVEL_MIX_CUT:
        return "low_key"
    return "buzzing" if n >= TOP_VOLUME_FROM else "lively"
