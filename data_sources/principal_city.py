"""
Is a pin inside a principal city?

OMB lists the principal cities of every metropolitan and micropolitan area (List 2, July 2023). People call a
dense place inside the central city "urban" far more often than the same density in a separate town next to
it (HUD's Urbanization Perceptions Small Area Index: 73% of catalog places inside a principal city are labeled
urban, 13% of those outside). The area type uses this as a second cutoff.

Data: data/principal_city_places.parquet, built by scripts/baselines/build_principal_city_layer.py. It holds
the outlines of the principal-city places in the states it covers (file metadata "covered_states"). Only those
whose name is part of their metro's OMB title count (the metro's major cities; OMB also lists large suburbs such as
Plano or Sunnyvale as principal cities, and HUD's labels agree better without them). For a pin in any other state the
answer is None (unknown), never False.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from logging_config import get_logger

logger = get_logger(__name__)

_PATH = os.getenv("HOMEFIT_PRINCIPAL_CITY_LAYER",
                  os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "principal_city_places.parquet"))

_loaded = False
_tree = None
_geoms = None
_names = None
_covered = frozenset()


def _load() -> None:
    global _loaded, _tree, _geoms, _names, _covered
    if _loaded:
        return
    _loaded = True
    if not os.path.isfile(_PATH):
        logger.warning("principal city layer missing: %s (area type uses the single urban cutoff)", _PATH)
        return
    import pyarrow.parquet as pq
    from shapely import wkb
    from shapely.strtree import STRtree
    t = pq.read_table(_PATH)
    meta = t.schema.metadata or {}
    _covered = frozenset(json.loads(meta.get(b"covered_states", b"[]")))
    d = t.to_pydict()
    keep = [i for i, n in enumerate(d["named_in_title"]) if n]
    _geoms = [wkb.loads(d["wkb"][i]) for i in keep]
    _names = [(d["name"][i], d["cbsa_title"][i]) for i in keep]
    _tree = STRtree(_geoms)


def covered_states() -> frozenset:
    _load()
    return _covered


def principal_city_at(lat: float, lon: float, state_fips: Optional[str] = None) -> Optional[bool]:
    """
    True when the pin is inside a principal-city place, False when it is in a covered state but inside none,
    None when that cannot be decided (state not covered, state not given and the pin is in no principal city,
    or the layer is missing).
    """
    _load()
    if _tree is None:
        return None
    from shapely.geometry import Point
    if len(_tree.query(Point(lon, lat), predicate="intersects")):
        return True
    if state_fips and str(state_fips).zfill(2) in _covered:
        return False
    return None
