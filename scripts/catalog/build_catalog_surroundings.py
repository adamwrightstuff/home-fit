#!/usr/bin/env python3
"""
Build data/catalog_surroundings.json: median household income, median home value and community safety around each
catalog place, next to the place's own figures. Display only (docs/SURROUNDINGS.md). The method and every rule live
in surroundings.py, shared with the API's /catalog/surroundings so stored and live figures match.

Offline: reads only numbers already stored in the catalog, never calls an API.

  PYTHONPATH=. python3 scripts/catalog/build_catalog_surroundings.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import catalog_api  # noqa: E402
from surroundings import (  # noqa: E402,F401  (re-exported for tests)
    INCOME_CAP, MAX_MILES, MIN_WEIGHT, SCALE_MILES, metro_rows, safety_key, surroundings_for,
)

OUT = ROOT / "data" / "catalog_surroundings.json"
_safety_key = safety_key


def main() -> None:
    places: Dict[str, Any] = {}
    counts = []
    for metro in catalog_api.live_metros():
        if not catalog_api._metro_file(metro).is_file():
            continue
        rows = metro_rows(metro, log=print)
        s = surroundings_for(rows)
        counts.append(f"{metro} {len(s)}/{len(rows)}")
        places.update({f"{metro}::{k}": v for k, v in s.items()})
    doc = {
        "method": f"catalog places within {MAX_MILES:g} mi, weight exp(-(d/{SCALE_MILES:g} mi)^2), min weight {MIN_WEIGHT:g}; "
                  "Census ACS 2022 from housing_value.summary; display only (docs/SURROUNDINGS.md)",
        "places": places,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(places)} places ({', '.join(counts)})")


if __name__ == "__main__":
    main()
